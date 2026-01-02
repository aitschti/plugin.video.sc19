# proxy_module.py - Proxy logic for Kodi addon
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import urllib.request
import urllib.parse
import urllib.error
import socket
import base64
import hashlib
import gzip
import re
import os
import time
import json
import xbmc
import xbmcaddon
import xbmcgui

socket.setdefaulttimeout(5)  # Set default socket timeout

# --- safe xbmc logging wrapper ---
try:
    LOG_INFO = xbmc.LOGINFO
    LOG_ERROR = xbmc.LOGERROR

    def _log(msg, level=LOG_INFO): # type: ignore
        xbmc.log(f"SC19 Proxy: {msg}", level)
except Exception:
    def _log(msg, level=None):
        print(f"SC19 Proxy: {msg}")

# Verbosity control (ERROR|INFO|DEBUG). Default: ERROR
LOG_VERBOSITY = os.environ.get('SC19_PROXY_LOG', 'INFO').upper()

def _debug(msg: str):
    if LOG_VERBOSITY == 'DEBUG':
        _log(msg)

def _info(msg: str):
    if LOG_VERBOSITY in ('INFO', 'DEBUG'):
        _log(msg)

def _error(msg: str):
    _log(msg, level=globals().get('LOG_ERROR', None))

# Basic headers to forward when fetching original resources
FORWARD_HEADERS = {
    'Referer': 'https://stripchat.com/',
    'Origin': 'https://stripchat.com',
    'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.182 Safari/537.36",
    'Accept': '*/*'
}

# API Endpoints
API_ENDPOINT_MODEL = "https://stripchat.com/api/front/v2/models/username/{}/cam"
API_CONFIG_URL = "https://stripchat.com/api/front/v3/config/static"

# M3U8 URL Template and CDN
CDN_OPTIONS = {
    0: 'doppiocdn.org',
    1: 'doppiocdn.net',
    2: 'doppiocdn.com'
}

def _get_cdn_base_url():
    """Get the CDN base URL template from Kodi addon settings."""
    suffix = ""
    try:
        addon = xbmcaddon.Addon()
        choice_str = addon.getSetting('cdn_choice')
        use_variants = addon.getSettingBool('use_variants')
        suffix = "_auto" if use_variants else ""
        if choice_str:
            choice = int(choice_str)
            if choice in CDN_OPTIONS:
                domain = CDN_OPTIONS[choice]
                _debug("Using CDN choice from settings: %s (%s)" % (choice, domain))
                return f"https://edge-hls.{domain}/hls/{{}}/master/{{}}{suffix}.m3u8"
            else:
                _debug("Invalid CDN choice: %s, using default" % choice)
        else:
            _debug("CDN choice not set, using default")
        return f"https://edge-hls.doppiocdn.net/hls/{{}}/master/{{}}{suffix}.m3u8"
    except Exception as e:
        _error(f"Failed to read CDN choice from settings: {e}")
        return f"https://edge-hls.doppiocdn.net/hls/{{}}/master/{{}}{suffix}.m3u8"

# Tunables
REQUEST_TIMEOUT = 5
MAX_FETCH_RETRIES = 3
CHUNK_SIZE = 64 * 1024

# Global cache for init segments
_init_cache = {}

# Global flag to halt requests after key fault detection
_key_fault_detected = False

# Global flag to track if pkey mismatch warning has been shown
_pkey_mismatch_warned = False

# Global variable for the stream M3U8 URL (default if username provided at startup)
_stream_m3u8_url = None

# Global cache for username -> M3U8 URL (with timestamp for TTL)
_username_m3u8_cache = {}
CACHE_TTL_SECONDS = 300  # 5 minutes

# Global cache for decode key and pkey (synced with addon settings)
_decode_key = None
_pkey = None

def _get_decode_key():
    """Get the decode key from Kodi addon settings (cached globally)."""
    global _decode_key
    if _decode_key is None:
        try:
            addon = xbmcaddon.Addon()
            _decode_key = addon.getSetting('decode_key')
            if not _decode_key:
                _error("Decode key is empty in addon settings. Playback will fail for encrypted streams.")
                try:
                    xbmcgui.Dialog().notification(
                        'SC19 Proxy Error',
                        'Decode key (pdkey) is not set in addon settings',
                        xbmcgui.NOTIFICATION_ERROR,
                        5000
                    )
                except Exception:
                    pass
                return None
            _debug("Using decode key from addon settings")
        except Exception as e:
            _error(f"Failed to read decode key from addon settings: {e}")
            return None
    return _decode_key

def _get_pkey():
    """Get the pkey from Kodi addon settings (cached globally)."""
    global _pkey
    if _pkey is None:
        try:
            addon = xbmcaddon.Addon()
            _pkey = addon.getSetting('pkey_key')
            if not _pkey:
                _error("pkey is empty in addon settings. Playback will fail for encrypted streams.")
                try:
                    xbmcgui.Dialog().notification(
                        'SC19 Proxy Error',
                        'pkey is not set in addon settings',
                        xbmcgui.NOTIFICATION_ERROR,
                        5000
                    )
                except Exception:
                    pass
                return None
            _debug("Using pkey from addon settings")
        except Exception as e:
            _error(f"Failed to read pkey from addon settings: {e}")
            return None
    return _pkey



def _pad_b64(s: str) -> str:
    if not s:
        return s
    return s + ("=" * ((4 - len(s) % 4) % 4))

def _mouflon_decrypt_b64(encrypted_b64: str, key: str) -> str:
    if not encrypted_b64:
        return ""
    try:
        data = base64.b64decode(_pad_b64(encrypted_b64))
    except Exception:
        return ""
    hash_bytes = hashlib.sha256(key.encode("utf-8")).digest()
    out = bytearray()
    for i, b in enumerate(data):
        out.append(b ^ hash_bytes[i % len(hash_bytes)])
    try:
        return out.decode("utf-8")
    except Exception:
        return out.decode("latin-1", errors="ignore")

def _is_valid_decrypted_url(url: str) -> bool:
    """Validate if the decrypted URL looks correct (e.g., ends with .mp4 and has part number)."""
    pattern = r'^https://.*\.mp4$'
    return bool(re.match(pattern, url))

def _decode_m3u8_mouflon_files(m3u8_text: str) -> str:
    """Find '#EXT-X-MOUFLON:URI:<url>' (v2) lines and decode by reversing and decrypting the segment."""
    if "#EXT-X-MOUFLON" not in m3u8_text:
        return m3u8_text
    
    lines = m3u8_text.splitlines()
    key = _get_decode_key()
    if key is None:
        _error("Decode key (pdkey) missing in addon settings. Encrypted streams will not play.")
        return m3u8_text  # Return original without decoding
    
    # Attempt decryption with v2 algorithm
    invalid_decryptions = 0
    for idx, line in enumerate(lines):
        # Handle v2: #EXT-X-MOUFLON:URI:<full_url_with_encrypted_segment>
        if line.startswith("#EXT-X-MOUFLON:URI:"):
            uri = line.split(":", 2)[-1].strip()
            # Extract encrypted segment from URI pattern: .../{segnum}_{encrypted}_{timestamp}_...
            match = re.search(r'_(\d+)_([^_]+)_(\d+)', uri)
            if match:
                encrypted_segment = match.group(2)
                # Reverse the segment, then apply decryption (v2 algorithm)
                reversed_segment = encrypted_segment[::-1]
                dec = _mouflon_decrypt_b64(reversed_segment, key)
                if dec:
                    # Replace encrypted segment in URI with decrypted value
                    new_uri = uri.replace(f'_{encrypted_segment}_', f'_{dec}_')
                    lines[idx] = f"#EXT-X-MOUFLON:URI:{new_uri}"
                    # Find next non-empty line and replace 'media.mp4' if present
                    for j in range(idx + 1, min(len(lines), idx + 6)):
                        candidate = lines[j]
                        if candidate.strip() == "":
                            continue
                        if "media.mp4" in candidate:
                            lines[j] = new_uri
                            break
                else:
                    invalid_decryptions += 1
    
    if invalid_decryptions > 0:
        _error(f"Decryption failed for {invalid_decryptions} segments. Check decode key in addon settings.")
        # If all decryptions fail, return original to avoid broken stream
        mouflon_count = len([l for l in lines if l.startswith("#EXT-X-MOUFLON:")])
        if mouflon_count > 0 and invalid_decryptions == mouflon_count:
            _error("All decryptions invalid. Returning original m3u8.")
            return m3u8_text
    
    return "\n".join(lines)

def _extract_psch_and_pkey(m3u8_text):
    """Return (psch_version, pkey) from #EXT-X-MOUFLON:PSCH line, preferring the one matching loaded pkey."""
    psch_lines = []
    for line in m3u8_text.splitlines():
        l = line.strip()
        if not l:
            continue
        if l.upper().startswith('#EXT-X-MOUFLON:PSCH'):
            psch_lines.append(l)

    if not psch_lines:
        return '', ''

    # Get loaded pkey to match against
    loaded_pkey = _get_pkey()
    
    # Collect all v2 PSCH lines
    v2_lines = []
    for l in psch_lines:
        parts_tmp = l.split(':', 3)
        if len(parts_tmp) > 2 and parts_tmp[2].lower().startswith('v2'):
            v2_lines.append(l)

    # If we have a loaded pkey, try to find matching v2 line
    global _pkey_mismatch_warned
    if loaded_pkey and v2_lines:
        for l in v2_lines:
            parts = l.split(':', 3)
            if len(parts) > 3 and parts[3] == loaded_pkey:
                version = parts[2].lower() if len(parts) > 2 else ''
                pkey = parts[3] if len(parts) > 3 else ''
                _debug(f"Found matching pkey in playlist: {pkey}")
                # Reset warning flag on successful match
                _pkey_mismatch_warned = False
                return version, pkey
        # Loaded pkey doesn't match any v2 line - show warning only once
        if not _pkey_mismatch_warned:
            _error(f"Loaded pkey '{loaded_pkey}' not found in playlist. Using last v2 line.")
            try:
                xbmcgui.Dialog().notification(
                    'SC19 Proxy Warning',
                    'Configured pkey not found in playlist',
                    xbmcgui.NOTIFICATION_WARNING,
                    4000
                )
            except Exception:
                pass
            _pkey_mismatch_warned = True
    
    # Fallback: use last v2 line if available, otherwise last PSCH line
    if v2_lines:
        selected_line = v2_lines[-1]
    else:
        selected_line = psch_lines[-1]
    parts = selected_line.split(':', 3)
    version = parts[2].lower() if len(parts) > 2 else ''
    pkey = parts[3] if len(parts) > 3 else ''
    return version, pkey


def _make_absolute(base, ref):
    return urllib.parse.urljoin(base, ref)

def _fetch_with_retries(url, headers=None, timeout=REQUEST_TIMEOUT, retries=MAX_FETCH_RETRIES):
    """Fetch URL with a few retries. Returns a response or raises last exception.
    If an HTTPError occurs it is returned (caller should inspect .code)."""
    last_exc = None
    hdrs = headers or FORWARD_HEADERS
    for attempt in range(1, retries + 1):
        req = urllib.request.Request(url, headers=hdrs)
        try:
            resp = urllib.request.urlopen(req, timeout=timeout)
            return resp
        except urllib.error.HTTPError as he:
            # return HTTPError so caller can inspect status (e.g. 418)
            return he
        except (urllib.error.URLError, socket.timeout) as e:
            last_exc = e
            time.sleep(0.2 * attempt)
    raise last_exc # type: ignore

def _normalize_strip_psch_pkey(url: str) -> str:
    """Return URL with psch/pkey removed from the query for cache lookups."""
    try:
        parsed = urllib.parse.urlsplit(url)
        q = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
        q.pop('psch', None)
        q.pop('pkey', None)
        new_q = urllib.parse.urlencode({k: v[0] for k, v in q.items()}) if q else ''
        return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, new_q, parsed.fragment))
    except Exception:
        return url

class _ProxyHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    
    def log_message(self, format, *args):
        # Override to log GET requests to Kodi when LOG_VERBOSITY is DEBUG
        if LOG_VERBOSITY == 'DEBUG':
            message = format % args  # Format the message (e.g., "GET /username HTTP/1.1" 200 -)
            if message.startswith("GET"):  # Only log GET requests
                try:
                    xbmc.log(f"SC19 Proxy: {message}", xbmc.LOGINFO)
                except Exception:
                    print(f"SC19 Proxy: {message}")  # Fallback if xbmc unavailable
        # Otherwise, suppress default logging (do nothing)

    def handle_one_request(self):
        """Override to catch socket errors during request parsing (e.g., client disconnections)."""
        try:
            # Call the parent's method to handle request parsing and dispatch
            super().handle_one_request()
        except (ConnectionResetError, ConnectionAbortedError, OSError) as e:
            # Handle Windows-specific socket errors (10054: remote close, 10053: local abort, etc.)
            # These occur when the client disconnects during HTTP parsing; log at debug to reduce noise
            if hasattr(e, 'winerror') and e.winerror in (10054, 10053):
                _debug("Client disconnected during request parsing: %s" % e)
            elif isinstance(e, (ConnectionResetError, ConnectionAbortedError)):
                _debug("Client disconnected during request parsing: %s" % e)
            else:
                # Re-raise other OSError (e.g., network issues) or log if unexpected
                _error("Unexpected socket error during request parsing: %s" % e)
                raise
        except Exception as e:
            # Catch any other unhandled exceptions during parsing to prevent raw errors in Kodi log
            _error("Unhandled error during request parsing: %s" % e)

    def do_HEAD(self):
        """Handle HEAD requests so clients can probe resources (avoid 501)."""
        path = self.path
        qs = urllib.parse.urlparse(path).query
        params = urllib.parse.parse_qs(qs)
        
        if 'url' in params:
            orig = urllib.parse.unquote(params['url'][0])
        elif path == '/' and _stream_m3u8_url:
            orig = _stream_m3u8_url
        elif path.startswith('/') and len(path) > 1:
            username = path[1:]  # Extract username from /username
            orig = fetch_stream_url(username)
            if not orig:
                self.send_response(404)
                self.send_header('Connection', 'close')
                self.end_headers()
                return
        else:
            self.send_response(400)
            self.send_header('Connection', 'close')
            self.end_headers()
            return
        
        # normalized cache hit check (no body needed)
        norm = _normalize_strip_psch_pkey(orig)
        cached = _init_cache.get(orig) or _init_cache.get(norm)
        if cached:
            try:
                self.send_response(200)
                for h, v in cached.get('headers', {}).items():
                    self.send_header(h, v)
                self.send_header('Content-Length', str(len(cached['bytes'])))
                self.send_header('Connection', 'keep-alive')
                self.end_headers()
            except Exception as e:
                _error("Error serving cached HEAD for %s: %s" % (orig, e))
            return

        # build upstream headers to forward
        upstream_headers = dict(FORWARD_HEADERS)
        for hdr in ('Range', 'User-Agent', 'Accept', 'Accept-Encoding', 'Referer', 'Origin', 'If-None-Match', 'If-Modified-Since', 'Cookie'):
            v = self.headers.get(hdr)
            if v:
                upstream_headers[hdr] = v

        # try HEAD first, fall back to GET but do not read body
        try:
            req = urllib.request.Request(orig, headers=upstream_headers, method='HEAD')
            try:
                resp = urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT)
            except (urllib.error.HTTPError, urllib.error.URLError) as e:
                # some servers reject HEAD; try a short GET and only inspect headers
                if isinstance(e, urllib.error.HTTPError) and e.code in (405, 501):
                    req2 = urllib.request.Request(orig, headers=upstream_headers)
                    resp = urllib.request.urlopen(req2, timeout=REQUEST_TIMEOUT)
                else:
                    raise
        except Exception as e:
            try:
                self.send_response(502)
                self.send_header('Connection', 'close')
                self.end_headers()
            except Exception:
                pass
            _error("HEAD probe failed for %s: %s" % (orig, e))
            return

        # forward upstream status & headers, no body
        try:
            status = getattr(resp, 'status', None) or getattr(resp, 'code', None) or resp.getcode()
        except Exception:
            status = 200
        try:
            self.send_response(status)
            for h in ('Content-Type','Content-Length','Content-Range','Accept-Ranges','Transfer-Encoding','Content-Encoding','Cache-Control','ETag','Set-Cookie'):
                v = resp.headers.get(h)
                if v:
                    self.send_header(h, v)
            self.send_header('Connection', 'close')
            self.end_headers()
        except Exception as e:
            _error("Error forwarding HEAD response for %s: %s" % (orig, e))
        return

    def do_GET(self):
        try:  # Top-level try to catch any unhandled exceptions and log them gracefully
            _debug(f"Handling GET request for {self.path}")
            
            path = self.path
            qs = urllib.parse.urlparse(path).query
            params = urllib.parse.parse_qs(qs)
            
            if 'url' in params:
                orig = urllib.parse.unquote(params['url'][0])
            elif path == '/' and _stream_m3u8_url:
                orig = _stream_m3u8_url
            elif path.startswith('/') and len(path) > 1:
                username = path[1:]  # Extract username from /username
                xbmc.log(f"New connection request for username: {username}", 1)
                orig = fetch_stream_url(username)
                if not orig:
                    self.send_response(404)
                    self.send_header('Content-Type', 'text/plain')
                    self.send_header('Connection', 'close')
                    self.end_headers()
                    try:
                        self.wfile.write(b'Stream not found or offline')
                    except Exception:
                        pass
                    return
                # Log the proxy URL for the master playlist
                host, port = self.server.server_address  # type: ignore
                proxy_url = f"http://{host}:{port}/?url={urllib.parse.quote(orig)}"
                xbmc.log(f"Proxy URL for {username}: {proxy_url}", 1)
            else:
                self.send_response(400)
                self.send_header('Content-Type', 'text/plain')
                self.send_header('Connection', 'close')
                self.end_headers()
                try:
                    self.wfile.write(b'No url parameter or invalid path')
                except Exception:
                    pass
                return

            # Early halt if key fault detected and this is a segment request
            global _key_fault_detected
            is_playlist = orig.endswith('.m3u8')
            if _key_fault_detected and not is_playlist:
                _error("Key fault detected, halting segment request: %s" % orig)
                self.send_response(403)
                self.send_header('Content-Type', 'text/plain')
                self.send_header('Connection', 'close')
                self.end_headers()
                try:
                    self.wfile.write(b'Decode key error: Playback halted due to invalid key. Check key.txt.')
                except Exception:
                    pass
                return

            # Reset flag on playlist request (allow recovery)
            if is_playlist:
                _key_fault_detected = False

            # normalized incoming URL and check init cache (exact or normalized key)
            norm = _normalize_strip_psch_pkey(orig)
            cached = _init_cache.get(orig) or _init_cache.get(norm)
            if cached:
                try:
                    self.send_response(200)
                    for h, v in cached.get('headers', {}).items():
                        self.send_header(h, v)
                    self.send_header('Content-Length', str(len(cached['bytes'])))
                    self.send_header('Connection', 'keep-alive')
                    self.end_headers()
                    self.wfile.write(cached['bytes'])
                except Exception as e:
                    pass
                return

            _debug("Incoming request for: %s -> orig: %s" % (self.path, orig))

            # Build upstream headers and forward important client headers
            upstream_headers = dict(FORWARD_HEADERS)
            for hdr in ('Range', 'User-Agent', 'Accept', 'Accept-Encoding', 'Referer', 'Origin', 'If-None-Match', 'If-Modified-Since', 'Cookie'):
                v = self.headers.get(hdr)
                if v:
                    upstream_headers[hdr] = v

            try:
                resp = _fetch_with_retries(orig, headers=upstream_headers)
            except Exception as e:
                self.send_response(502)
                self.send_header('Connection', 'close')
                self.end_headers()
                try:
                    self.wfile.write(("Proxy fetch failure: %s" % str(e)).encode('utf-8'))
                except Exception:
                    pass
                _error("Proxy fetch final failure for %s: %s" % (orig, e))
                return

            # Check for 418 error (indicates invalid segment URL, likely due to wrong key)
            if isinstance(resp, urllib.error.HTTPError) and getattr(resp, 'code', None) == 418:
                _error(f"Upstream returned 418 (invalid segment URL) for {orig}. Decode key may be wrong or outdated.")
                _key_fault_detected = True  # Set flag to halt further segment requests
                # For playlists, return custom m3u8 to minimize error dialog
                if is_playlist:
                    custom_playlist = "#EXTM3U\n#EXT-X-VERSION:3\n# Decode key error: Check key.txt for the correct key.\n"
                    body = custom_playlist.encode('utf-8')
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/vnd.apple.mpegurl')
                    self.send_header('Content-Length', str(len(body)))
                    self.send_header('Cache-Control', 'no-cache')
                    self.send_header('Connection', 'keep-alive')
                    self.end_headers()
                    self.wfile.write(body)
                    return
                # For segments, return 403
                self.send_response(403)
                self.send_header('Content-Type', 'text/plain')
                self.send_header('Connection', 'close')
                self.end_headers()
                try:
                    self.wfile.write(b'Decode key error: Invalid segment URL. Check key.txt for the correct key.')
                except Exception:
                    pass
                return

            # Pass through other HTTPError statuses
            if isinstance(resp, urllib.error.HTTPError):
                code = getattr(resp, 'code', None)
                self.send_response(code or 502)
                self.send_header('Connection', 'close')
                self.end_headers()
                return

            try:
                content_type = resp.headers.get_content_type()
            except Exception:
                content_type = resp.headers.get('Content-Type', '') or ''

            is_playlist = orig.endswith('.m3u8') or content_type in (
                'application/vnd.apple.mpegurl', 'application/x-mpegURL', 'text/plain'
            )

            # Playlist path (rewrite LL-HLS attribute URIs and plain URLs, inject psch/pkey)
            if is_playlist:
                try:
                    raw = resp.read()
                    enc = (resp.headers.get('Content-Encoding') or '').lower()
                    if 'gzip' in enc:
                        try:
                            raw = gzip.decompress(raw)
                        except Exception as e:
                            _debug("Failed to gunzip playlist: %s" % e)
                    text = raw.decode('utf-8', errors='replace')

                    text = _decode_m3u8_mouflon_files(text)
                    psch, pkey = _extract_psch_and_pkey(text)
                    host, port = self.server.server_address  # type: ignore

                    def _inject_and_proxy(abs_url: str) -> str:
                        # Always use v2 (reverse + decrypt algorithm)
                        pr = urllib.parse.urlsplit(abs_url)
                        q = urllib.parse.parse_qs(pr.query, keep_blank_values=True)
                        # Always set psch to v2
                        q['psch'] = ['v2']
                        if pkey and 'pkey' not in q:
                            q['pkey'] = [pkey]
                        new_q = urllib.parse.urlencode({k: v[0] for k, v in q.items()})
                        abs2 = urllib.parse.urlunsplit((pr.scheme, pr.netloc, pr.path, new_q, pr.fragment))
                        return f'http://{host}:{port}/?url=' + urllib.parse.quote(abs2, safe='')

                    def _rewrite_uri_attr(line: str) -> str:
                        m = re.search(r'URI=(?:"([^"]+)"|([^,]+))', line, flags=re.IGNORECASE)
                        if not m:
                            return line
                        uri = (m.group(1) or m.group(2) or '').strip()
                        if not uri:
                            return line
                        absu = _make_absolute(orig, uri)
                        prox = _inject_and_proxy(absu)
                        return re.sub(r'URI=(?:"[^"]+"|[^,]+)', f'URI="{prox}"', line, flags=re.IGNORECASE)

                    out = []
                    for line in text.splitlines():
                        s = line.strip()
                        u = s.upper()
                        # Rewrite all attribute-URI tags including audio renditions
                        if (u.startswith('#EXT-X-MEDIA') or
                            u.startswith('#EXT-X-I-FRAME-STREAM-INF') or
                            u.startswith('#EXT-X-MAP') or
                            u.startswith('#EXT-X-PART') or
                            u.startswith('#EXT-X-PRELOAD-HINT') or
                            u.startswith('#EXT-X-RENDITION-REPORT')):
                            out.append(_rewrite_uri_attr(line))
                            continue

                        # Rewrite plain URL lines (variants or segments)
                        if s and not s.startswith('#'):
                            absu = _make_absolute(orig, s)
                            out.append(_inject_and_proxy(absu))
                            continue

                        out.append(line)

                    body = ("\n".join(out) + "\n").encode('utf-8')
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/vnd.apple.mpegurl')
                    self.send_header('Content-Length', str(len(body)))
                    self.send_header('Cache-Control', 'no-cache')
                    self.send_header('Connection', 'keep-alive')
                    self.end_headers()
                    self.wfile.write(body)
                    return
                except Exception as e:
                    self.send_response(502)
                    self.send_header('Connection', 'close')
                    self.end_headers()
                    _error("Error processing playlist response for %s: %s" % (orig, e))
                    return

            # Binary/segment path (supports ranges)
            upstream_status = getattr(resp, 'status', None) or resp.getcode() or 200
            try:
                self.send_response(upstream_status)
            except Exception:
                self.send_response(200)
            for h in ('Content-Type', 'Content-Length', 'Content-Range', 'Accept-Ranges', 'ETag', 'Last-Modified', 'Cache-Control'):
                v = resp.headers.get(h)
                if v:
                    self.send_header(h, v)
            te = resp.headers.get('Transfer-Encoding')
            if te:
                self.send_header('Transfer-Encoding', te)
            ce = resp.headers.get('Content-Encoding')
            if ce:
                self.send_header('Content-Encoding', ce)
            self.send_header('Connection', 'keep-alive')
            self.end_headers()

            # Streaming logic with improved exception handling
            first = True
            try:
                while True:
                    chunk = resp.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    if first:
                        if b'ftyp' in chunk or b'moov' in chunk or b'sidx' in chunk:
                            _debug("Atoms seen in first chunk from %s" % orig)
                        first = False
                    self.wfile.write(chunk)
                return
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError) as e:
                # Client disconnected (common with Kodi/VLC/Windows); log at debug to reduce noise
                _debug("Client disconnected during streaming for %s: %s" % (orig, e))
                return
            except OSError as e:
                # Handle Windows-specific socket errors (10054: remote close, 10053: local abort, etc.)
                if hasattr(e, 'winerror') and e.winerror in (10054, 10053):
                    _debug("Client disconnected during streaming for %s: %s" % (orig, e))
                    return
                else:
                    # Re-raise other OSError (e.g., network issues)
                    raise
        except Exception as e:
            # Catch any unhandled exceptions to prevent raw errors in Kodi log
            _error("Unhandled error in do_GET for %s: %s" % (self.path, e))
            try:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.send_header('Connection', 'close')
                self.end_headers()
                self.wfile.write(b'Internal server error')
            except Exception:
                pass  # If even this fails, just return
            return

class HLSProxy:
    def __init__(self, host='127.0.0.1', port=0):
        self.host = host
        self.port = int(port) if port is not None else 0
        self._server = None
        self._thread = None
        self._lock = threading.Lock()

    def start(self):
        with self._lock:
            if self._server:
                return (self.host, self._server.server_address[1])
            server = ThreadingHTTPServer((self.host, self.port), _ProxyHandler)
            self._server = server
            t = threading.Thread(target=server.serve_forever, daemon=True)
            t.start()
            self._thread = t
            _info("Proxy started on %s:%d" % (self.host, server.server_address[1]))
            return (self.host, server.server_address[1])

    def stop(self):
        _info("Stopping proxy...")
        with self._lock:
            if not self._server:
                _info("Proxy already stopped")
                return
            try:
                # Force close the socket
                if hasattr(self._server, 'socket') and self._server.socket:
                    self._server.socket.shutdown(socket.SHUT_RDWR)
                    self._server.socket.close()
                self._server.shutdown()
                self._server.server_close()
                _info("Server shutdown initiated")
            except Exception as e:
                _error(f"Error during server shutdown: {e}")
            self._server = None
            self._thread = None
            _info("Proxy stopped")

    def get_local_url(self, original_url):
        host, port = self.start()
        return f'http://{host}:{port}/?url=' + urllib.parse.quote(original_url, safe='')

def get_proxy(port=None):
    """Start a new proxy instance each time."""
    try:
        proxy = HLSProxy(port=port) # type: ignore
        proxy.start()
        return proxy
    except Exception as e:
        _error(f"Failed to start proxy: {e}")
        raise

def fetch_stream_url(username):
    """Fetch the M3U8 URL for the given username."""
    # Check cache first
    now = time.time()
    if username in _username_m3u8_cache:
        cached_time, cached_url = _username_m3u8_cache[username]
        if now - cached_time < CACHE_TTL_SECONDS:
            return cached_url
        else:
            del _username_m3u8_cache[username]  # Expired, remove
    
    api_url = API_ENDPOINT_MODEL.format(username)
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"https://www.stripchat.com/{username}",
        "User-Agent": FORWARD_HEADERS["User-Agent"]
    }
    try:
        req = urllib.request.Request(api_url, headers=headers)
        with urllib.request.urlopen(req) as res:
            data = json.load(res)
        if not data or not data.get("cam") or not data.get("user"):
            _error("Invalid API response or stream offline")
            return None
        user_data = data["user"]["user"]
        if not user_data["isLive"] or user_data["status"] != "public":
            _error(f"Stream offline or private (status: {user_data['status']})")
            return None
        stream_name = data["cam"]["streamName"]
        # Use the dynamic CDN base URL from settings
        base_url = _get_cdn_base_url()
        m3u8_url = base_url.format(stream_name, stream_name)
        # Cache the result
        _username_m3u8_cache[username] = (now, m3u8_url)
        return m3u8_url
    except Exception as e:
        _error(f"Failed to fetch stream URL for {username}: {e}")
        return None