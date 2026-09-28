import os
import re
import json
import time
import xbmc
import xbmcgui
import xbmcaddon
import xbmcvfs
import sqlite3
import urllib.request
from urllib.request import Request
import urllib.error
import urllib.parse
from datetime import datetime, timedelta

# Common config constants (avilable in all modules)
ADDON_NAME = "plugin.video.sc19"
ADDON_SHORTNAME = "SC19"
ADDON = xbmcaddon.Addon(id=ADDON_NAME)

# Module specific constants
DB_FAVOURITES_FILE = "favourites-sc.db"
DB_FAVOURITES = xbmcvfs.translatePath("special://profile/addon_data/%s/%s" % (ADDON_NAME, DB_FAVOURITES_FILE))
REQUEST_TIMEOUT = ADDON.getSettingInt('request_timeout')
DB_TEXTURES = xbmcvfs.translatePath("special://userdata/Database/Textures13.db")
PATH_THUMBS = xbmcvfs.translatePath("special://userdata/Thumbnails/")

# Queries
Q_THUMBNAILS = "SELECT url,cachedurl FROM texture WHERE url LIKE '%.doppiocdn.net%'"
Q_DEL_THUMBNAILS = "DELETE FROM texture WHERE url LIKE '%.doppiocdn.net%'"
Q_DEL_FAVOURITE = "DELETE FROM favourites WHERE user = ?"
Q_ADD_FAVOURITE = "INSERT INTO favourites (user, user_id) VALUES(?, ?)"
Q_GET_FAVOURITES = "SELECT * FROM favourites;"
Q_GET_USERS = "SELECT user FROM favourites;"
Q_GET_FILTERED_FAVOURITES = "SELECT user FROM favourites WHERE user_id IS NULL OR user_id = ''"
Q_TABLE_FAVOURITES = "CREATE TABLE IF NOT EXISTS favourites (user TEXT, user_id TEXT, PRIMARY KEY(user));"
Q_COLUMN_USER_ID = "ALTER TABLE favourites ADD COLUMN user_id TEXT;"
Q_UPDATE_USER_ID = "UPDATE favourites SET user_id = ? WHERE user = ?;"
Q_SCHEMA_INFO = "PRAGMA table_info(favourites);"

# API endpoints
API_ENDPOINT_BROADCASTS = "https://stripchat.com/api/front/v1/broadcasts/{0}"
API_ENDPOINT_USERID = "https://stripchat.com/api/front/users/user-ids/{0}"
API_ENDPOINT_VIDEOS_WITH_ID = "https://stripchat.com/api/front/v2/users/{0}/videos"

# Downloads
DOWNLOAD_CHUNK_SIZE = 256 * 1024
# REQUEST_TIMEOUT is a per-socket timeout tuned for small API calls. It never limits the total transfer time.
DOWNLOAD_TIMEOUT = max(REQUEST_TIMEOUT, 20)
MAX_FILENAME_LEN = 150
WIN_RESERVED = {'CON', 'PRN', 'AUX', 'NUL',
                *('COM%d' % i for i in range(1, 10)),
                *('LPT%d' % i for i in range(1, 10))}

# Threading
MAX_WORKERS = ADDON.getSettingInt('max_workers')

# HTTP request headers to forward when fetching original resources
FORWARD_HEADERS = {
    'Referer': 'https://stripchat.com',
    'Origin': 'https://stripchat.com',
    'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.7922.138 Safari/537.36",
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9'
}

def connect_favourites_db():
    "Connect to favourites database and create one, if it does not exist."

    db_con = sqlite3.connect(DB_FAVOURITES)
    c = db_con.cursor()

    try:
        c.execute(Q_GET_FAVOURITES)
    except sqlite3.OperationalError:
        c.executescript(Q_TABLE_FAVOURITES)
        db_con.commit()
        xbmc.log(ADDON_NAME + ": Created favourites table with user and user_id columns.", 1)
    
    # Always check schema and ensure user_id column exists (for legacy DBs)
    try:
        c.execute(Q_SCHEMA_INFO)
        rows = c.fetchall()

        cols = [row[1] for row in rows]
        if 'user_id' not in cols:
            c.execute(Q_COLUMN_USER_ID)
            db_con.commit()
            xbmc.log(ADDON_NAME + ": Added user_id column to favourites database.", 1)
            update_favourites_user_ids(True, True)
                
    except Exception as e:
        xbmc.log(ADDON_NAME + ": Error checking/updating favourites DB schema: %s" % str(e), 3)

    return db_con

def tool_thumbnails_delete():
    rc = tool_thumbnails_delete_from_db()
    # Summary dialog
    xbmcgui.Dialog().ok("Delete Thumbnails", "Deleted %s thumbnail files and database entries" % (str(rc)))
    xbmc.executebuiltin('Dialog.Close(busydialog)')

def tool_thumbnails_delete_from_db():   
    # Connect to textures db
    conn = sqlite3.connect(DB_TEXTURES)
    # Set cursors
    cur = conn.cursor()
    cur_del = conn.cursor()
    # Delete thimbnail files
    cur.execute(Q_THUMBNAILS)
    rc = 0
    rows = cur.fetchall()
    for row in rows:
        rc = rc + 1
        if os.path.exists(PATH_THUMBS + str(row[1])):
            os.remove(PATH_THUMBS + str(row[1]))
        else:
            #xbmc.log("The file does not exist.",1)
            pass
    # Delete entries from db
    cur_del.execute(Q_DEL_THUMBNAILS)
    conn.commit()
    # Close connection
    conn.close()
    # Return number of entries found and log
    xbmc.log(ADDON_SHORTNAME + ": Deleted %s thumbnail files and database entries" % (str(rc)),1)
    return rc

def tool_fav_backup():
    path = ADDON.getSetting('fav_path_backup')
    source = DB_FAVOURITES
    destination = path + DB_FAVOURITES_FILE
    
    if path == "":
        xbmcgui.Dialog().ok("Backup Favourites", "Backup path is empty. Please set a valid path in settings menu under \"Favourites\" first.")  
        xbmcaddon.Addon(id=ADDON_NAME).openSettings()
    else:
        # Ask for confirmation before backup
        if xbmcgui.Dialog().yesno("Backup Favourites", "Do you really want to backup your favourites database?\nThis will overwrite any existing backup file.",
                                  yeslabel="Yes, backup", nolabel="Cancel"):
            if xbmcvfs.exists(source):
                if xbmcvfs.copy(source, destination):
                    xbmcgui.Dialog().ok("Backup Favourites", "Backup of favourites to backup path succesful.")
                else:
                    xbmcgui.Dialog().ok("Backup Favourites", "Something went wrong.")
            else:
                xbmcgui.Dialog().ok("Backup Favourites", "Favourites file is empty. Nothing to backup.")

def tool_fav_restore():
    path = ADDON.getSetting('fav_path_backup')
    source = path + DB_FAVOURITES_FILE
    destination = DB_FAVOURITES
    
    if path == "":
        xbmcgui.Dialog().ok("Restore Favourites", "Restore path is empty. Please set a valid path in settings menu under \"Favourites\" first.")  
        xbmcaddon.Addon(id=ADDON_NAME).openSettings()
    else:
        if xbmcvfs.exists(source):
            # Ask for confirmation before restore
            if xbmcgui.Dialog().yesno("Restore Favourites", "Do you really want to restore your favourites database?\nThis will overwrite your current favourites!", 
                                      yeslabel="Yes, restore", nolabel="Cancel"):
                if xbmcvfs.copy(source, destination):
                    xbmcgui.Dialog().ok("Restore Favourites", "Restore of favourites succesful.")
                else:
                    xbmcgui.Dialog().ok("Restore Favourites", "Something went wrong.")
        else:
            xbmcgui.Dialog().ok("Restore Favourites", "No valid file found in restore location. Make a backup first or check location.")

def tool_fav_update():
    """Prompt user & run update_user_ids_db (force or only missing)."""
    if not xbmcvfs.exists(DB_FAVOURITES):
        xbmcgui.Dialog().ok("Update Favourites", "No favourites database found.")
        return

    # Ask whether to proceed
    if not xbmcgui.Dialog().yesno("Update Favourites", "This will query the site API for each favourite and update their model ID.", yeslabel="Update", nolabel="Cancel"):
        return

    # Ask to force overwrite existing user_id values
    force = xbmcgui.Dialog().yesno("Update Favourites", "Force update all entries (overwrite existing model ids)?", yeslabel="Force", nolabel="Only fill empty")

    # Run the update
    update_favourites_user_ids(force=force, show_dialog=True)

def tool_import_keys():
    """Import pkey and pdkey from a text file selected by the user."""
    # Open file browser to select text file
    selected_file = xbmcgui.Dialog().browseSingle(
        1,  # Type: ShowAndGetFile
        "Select Keys File (format: pkey:pdkey)",
        "files",
        "*.txt|*.TXT|*.*",
        False,
        False,
        ""
    )
    
    if not selected_file:
        # User cancelled
        return
    
    # Read and parse the file
    try:
        # Read file content
        file_handle = xbmcvfs.File(selected_file)
        content = file_handle.read()
        file_handle.close()
        
        # Decode if bytes
        if isinstance(content, bytes):
            content = content.decode('utf-8')
        
        # Strip whitespace
        content = content.strip()
        
        if not content:
            xbmcgui.Dialog().ok("Import Keys", "Error: File is empty.")
            return
        
        # Parse format: pkey:pdkey
        if ':' not in content:
            xbmcgui.Dialog().ok("Import Keys", "Error: Invalid format. Expected format: pkey:pdkey\nExample: Zeec...:ubah...")
            return
        
        parts = content.split(':', 1)
        if len(parts) != 2:
            xbmcgui.Dialog().ok("Import Keys", "Error: Invalid format. Expected format: pkey:pdkey")
            return
        
        pkey = parts[0].strip()
        pdkey = parts[1].strip()
        
        if not pkey or not pdkey:
            xbmcgui.Dialog().ok("Import Keys", "Error: pkey or pdkey is empty in the file.")
            return
        
        # Validate key lengths (both must be exactly 16 characters)
        if len(pkey) != 16:
            xbmcgui.Dialog().ok("Import Keys", f"Error: pkey must be exactly 16 characters long.\nCurrent length: {len(pkey)}")
            return
        
        if len(pdkey) != 16:
            xbmcgui.Dialog().ok("Import Keys", f"Error: pdkey must be exactly 16 characters long.\nCurrent length: {len(pdkey)}")
            return
        
        # Set both values in addon settings
        ADDON.setSetting('pkey_key', pkey)
        ADDON.setSetting('decode_key', pdkey)
        
        # Show success dialog and prompt to restart Kodi
        xbmcgui.Dialog().ok(
            "Import Keys - Success",
            f"Keys imported successfully!\n\npkey: {pkey[:20]}...\npdkey: {pdkey[:20]}...\n\nPlease restart Kodi to reload the proxy with the new keys."
        )
        
    except Exception as e:
        xbmcgui.Dialog().ok("Import Keys", f"Error reading or parsing file:\n{str(e)}")
        xbmc.log(f"SC19 Import Keys Error: {e}", level=xbmc.LOGERROR)

def format_timestamp_to_local(timestamp):
    """Convert UTC timestamp to local time"""
    try:
        if not timestamp:
            return "Unknown"
            
        # Create datetime object directly from ISO format
        utc_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        
        # Get local timezone offset
        import time
        offset = -time.timezone
        if time.daylight:
            offset = -time.altzone
            
        # Apply timezone offset
        local_time = utc_time + timedelta(seconds=offset)
        
        # Format according to locale settings
        local_format = "%Y-%m-%d %H:%M:%S"
        if xbmc.getRegion('datelong') and xbmc.getRegion('time'):
            local_format = f"{xbmc.getRegion('datelong')} {xbmc.getRegion('time')}"
            
        return local_time.strftime(local_format)
        
    except Exception as e:
        xbmc.log(f"{ADDON_SHORTNAME}: Error in format_timestamp_to_local: {str(e)}", xbmc.LOGERROR)
        return str(timestamp)

def format_timestamp_relative(timestamp):
    """Convert UTC timestamp to relative time difference"""
    try:
        if not timestamp:
            return "Unknown"
            
        # Create datetime object from ISO format
        utc_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        
        # Get current time in UTC
        now = datetime.now(utc_time.tzinfo)
        
        # Calculate time difference
        diff = now - utc_time
        
        # Convert to total seconds
        seconds = diff.total_seconds()
        
        # Less than an hour
        if seconds < 3600:
            minutes = int(seconds / 60)
            return f"{minutes} {'minute' if minutes == 1 else 'minutes'} ago"
            
        # Less than a day
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return f"{hours} {'hour' if hours == 1 else 'hours'} ago"
            
        # Less than a week
        elif seconds < 604800:
            days = int(seconds / 86400)
            return f"{days} {'day' if days == 1 else 'days'} ago"
            
        # Less than a month (approximately)
        elif seconds < 2592000:
            weeks = int(seconds / 604800)
            return f"{weeks} {'week' if weeks == 1 else 'weeks'} ago"
            
        # Less than a year
        elif seconds < 31536000:
            months = int(seconds / 2592000)
            return f"{months} {'month' if months == 1 else 'months'} ago"
            
        # More than a year
        else:
            years = int(seconds / 31536000)
            return f"{years} {'year' if years == 1 else 'years'} ago"
            
    except Exception as e:
        xbmc.log(f"{ADDON_SHORTNAME}: Error in format_timestamp_relative: {str(e)}", xbmc.LOGERROR)
        return str(timestamp)

def _extract_model_id(url, username):
    """Fetch url and return (modelId (string) or None, error_message or None, user_not_found).
       When the API returns JSON with only 'title' and 'description' (e.g. when account is deleted),
       the 'description' value is returned as error_message and user_not_found is True.
       user_not_found stays False for anything else (broken endpoint, network error), so the
       caller knows it is worth asking another endpoint.
    """
    try:
        payload = get_data_from_page(url.format(username))
        data = json.loads(payload)
        model_id = None
        error_msg = None
        not_found = False

        if isinstance(data, dict):
            # Common places to find the id
            if 'id' in data:
                model_id = data['id']
            elif 'modelId' in data:
                model_id = data['modelId']
            elif isinstance(data.get('item'), dict) and 'modelId' in data['item']:
                model_id = data['item']['modelId']
            elif isinstance(data.get('user'), dict) and 'modelId' in data['user']:
                model_id = data['user']['modelId']
            else:
                # If response is only a title & description (i.e. deleted profile),
                # use description as error message for better feedback.
                keys = set(data.keys())
                if keys == {'title', 'description'}:
                    error_msg = data.get('description', None)
                    not_found = True

        if model_id:
            return str(model_id), None, False
        return None, error_msg, not_found

    except Exception as e:
        xbmc.log(f"{ADDON_SHORTNAME}: Error getting modelId for {username} from {url}: {str(e)}", xbmc.LOGERROR)
        return None, str(e), False

def get_model_id_for_user(username):
    """Return (modelId (string) or None, error_message or None) for a given username.
       The site no longer serves the username based endpoints, so the id is needed
       for every model request.
    """
    model_id, error_msg, not_found = _extract_model_id(API_ENDPOINT_USERID, username)
    if model_id:
        return model_id, None

    # The API did not state that the user is gone, so the endpoint itself may be
    # at fault. Give the (older) broadcasts endpoint a try before giving up.
    if not not_found:
        fallback_id, fallback_err, _ = _extract_model_id(API_ENDPOINT_BROADCASTS, username)
        if fallback_id:
            return fallback_id, None
        error_msg = error_msg or fallback_err

    return None, error_msg

def update_favourites_user_ids(force=False, show_dialog=True):
    """Update the favourites database:
       - force (bool): overwrite existing user_id when True
       - show_dialog (bool): show progress dialog
    """
    db_con = None
    try:
        db_con = sqlite3.connect(DB_FAVOURITES)
        c = db_con.cursor()

        # Check if we have user_id column, else add it
        c.execute(Q_SCHEMA_INFO)
        rows = c.fetchall()
        cols = [row[1] for row in rows]
        if 'user_id' not in cols:
            c.execute(Q_COLUMN_USER_ID)
            db_con.commit()
            xbmc.log(ADDON_SHORTNAME + ": Added user_id column to favourites database.", 1)

        if force:
            c.execute(Q_GET_USERS)
        else:
            c.execute(Q_GET_FILTERED_FAVOURITES)
        rows = c.fetchall()
        total = len(rows)

        if total == 0:
            xbmc.log(ADDON_SHORTNAME + ": No favourites need updating (no rows to update).", 1)
            return ""

        prg = None
        if show_dialog:
            prg = xbmcgui.DialogProgress()
            prg.create("Update Favourites", "Fetching model IDs...")

        # Fetch all model IDs in parallel
        usernames = [username for (username,) in rows]
        results = fetch_model_ids_parallel(usernames, MAX_WORKERS)
        
        if prg and prg.iscanceled():
            xbmc.log(ADDON_SHORTNAME + ": Update cancelled by user.", 1)
            if prg:
                prg.close()
            return ""

        # Update database with results
        if prg:
            prg.update(50, "Updating database...")
        
        updated = 0
        failed = 0
        failed_users = []
        
        for username in usernames:
            model_id, model_err = results.get(username, (None, "no response"))
            
            try:
                if model_id:
                    c.execute(Q_UPDATE_USER_ID, (str(model_id), username))
                    db_con.commit()
                    updated += 1
                else:
                    # Prefer a specific error message from API if present
                    reason = model_err if model_err else "no modelId"
                    xbmc.log(f"{ADDON_SHORTNAME}: Could not determine modelId for user {username}: {reason}", level=xbmc.LOGWARNING)
                    failed += 1
                    failed_users.append(f"{username} ({reason})")

            except Exception as e:
                xbmc.log(f"{ADDON_SHORTNAME}: Error updating user_id for {username}: {str(e)}", level=xbmc.LOGERROR)
                failed += 1
                failed_users.append(f"{username} (error: {str(e)})")

        if prg:
            prg.close()

        # Build summary message; truncate failed list if too long so the dialog stays readable
        if failed > 0 and failed_users:
            failed_list = '\n'.join(failed_users)
            max_len = 1500
            if len(failed_list) > max_len:
                failed_list = failed_list[:max_len] + "\n...truncated..."
            message = f"Updated {updated} entries. Failed: {failed}.\n\nFailed entries:\n{failed_list}"
        else:
            message = f"Updated {updated} entries. Failed: {failed}."

        # Only show the dialog if requested, otherwise just log
        if show_dialog:
            xbmcgui.Dialog().ok("Update Favourites", message)

        xbmc.log(ADDON_SHORTNAME + f": Update completed. Updated {updated}, Failed {failed}.", 1)
        if failed > 0:
            xbmc.log(ADDON_SHORTNAME + f": Failed users: {', '.join(failed_users)}", xbmc.LOGWARNING)
        return ""

    except Exception as e:
        xbmc.log(ADDON_SHORTNAME + ": Error in update_favourites_user_ids: " + str(e), xbmc.LOGERROR)
        if show_dialog:
            xbmcgui.Dialog().ok("Update Favourites", "An error occurred while updating favourites.\nSee log for details.")
        return ""
    finally:
        if db_con:
            db_con.close()

def get_data_from_page(page):
    """Fetch HTML data from site"""
    req = urllib.request.Request(page, headers=FORWARD_HEADERS)

    try:
        response = urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT)
        code = response.getcode()
        if code != 200:
            xbmc.log(f"{ADDON_SHORTNAME}: Request returned status {code}", xbmc.LOGWARNING)
        return response.read().decode('utf-8')

    except urllib.error.HTTPError as e:
        # Some endpoints return useful JSON even on 404/4xx (e.g. {"title":"...","description":"..."}).
        # Read and return the response body so callers can parse the JSON.
        try:
            body = e.read().decode('utf-8')
            xbmc.log(f"{ADDON_SHORTNAME}: HTTPError {e.code} for {page}, returning body for parsing.", xbmc.LOGWARNING)
            return body
        except Exception as e2:
            xbmc.log(f"{ADDON_SHORTNAME}: HTTPError {e.code} and failed to read body for {page}: {str(e2)}", xbmc.LOGERROR)
            raise  # re-raise so calling code can handle it

    except Exception as e:
        xbmc.log(f"{ADDON_SHORTNAME}: Error fetching {page}: {str(e)}", xbmc.LOGERROR)
        raise

def get_json_from_api(url, timeout=4):
    """Fetch JSON from a URL and return parsed object. Simple wrapper that doesn't rely on get_data_from_page."""
    try:
        req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            # try to detect encoding, default to utf-8
            try:
                charset = resp.headers.get_content_charset() or 'utf-8'
            except Exception:
                charset = 'utf-8'
            text = raw.decode(charset, errors='replace')
            return json.loads(text)
    except Exception as e:
        xbmc.log(ADDON_NAME + f": Error fetching JSON from {url}: {e}", xbmc.LOGERROR)
        return None
    
def is_image_available(url):
    """Check if an image URL returns a valid response with minimal data transfer"""
    import urllib.request
    try:
        # Use HEAD request to check without downloading the full image
        req = urllib.request.Request(url, method='HEAD', headers=FORWARD_HEADERS)
        with urllib.request.urlopen(req, timeout=2) as response:
            # Check if response is successful and content-type is an image
            return response.status == 200 and 'image' in response.headers.get('Content-Type', '')
    except:
        return False
    
def check_images_parallel(url_list, max_workers=10):
    """
    Check multiple image URLs in parallel
    
    Args:
        url_list: List of tuples (username, url)
        max_workers: Maximum number of concurrent threads
        
    Returns:
        Dictionary mapping username to availability (True/False)
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    results = {}
    
    def check_single_image(username, url):
        return username, is_image_available(url)
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all checks
        future_to_username = {
            executor.submit(check_single_image, username, url): username 
            for username, url in url_list
        }
        
        # Collect results as they complete
        for future in as_completed(future_to_username):
            try:
                username, is_available = future.result()
                results[username] = is_available
            except Exception as e:
                username = future_to_username[future]
                xbmc.log(f"{ADDON_SHORTNAME}: Error checking image for {username}: {str(e)}", xbmc.LOGWARNING)
                results[username] = False
    
    return results

def fetch_user_data_parallel(usernames, API_ENDPOINT_MODEL_WITH_ID, max_workers=10):
    """
    Fetch user data for multiple usernames in parallel

    Args:
        usernames: List of usernames to fetch data for
        API_ENDPOINT_MODEL_WITH_ID: URL template taking the model id
        max_workers: Maximum number of concurrent threads

    Returns:
        Dictionary mapping username to user data (or None if failed)
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    results = {}

    def fetch_single_user(username):
        try:
            # The model id has to be resolved first, the username endpoint is gone
            model_id, model_err = get_model_id_for_user(username)
            if not model_id:
                xbmc.log(f"{ADDON_SHORTNAME}: Could not resolve model id for {username}: {model_err or 'no modelId'}", xbmc.LOGWARNING)
                return username, None
            data = get_data_from_page(API_ENDPOINT_MODEL_WITH_ID.format(model_id))
            return username, json.loads(data)
        except Exception as e:
            xbmc.log(f"{ADDON_SHORTNAME}: Error fetching data for {username}: {str(e)}", xbmc.LOGWARNING)
            return username, None
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all fetches
        future_to_username = {
            executor.submit(fetch_single_user, username): username 
            for username in usernames
        }
        
        # Collect results as they complete
        for future in as_completed(future_to_username):
            try:
                username, data = future.result()
                results[username] = data
            except Exception as e:
                username = future_to_username[future]
                xbmc.log(f"{ADDON_SHORTNAME}: Error processing result for {username}: {str(e)}", xbmc.LOGWARNING)
                results[username] = None
    
    return results

def fetch_model_ids_parallel(usernames, MAX_WORKERS):
    """
    Fetch model IDs for multiple usernames in parallel
    
    Args:
        usernames: List of usernames to fetch model IDs for
        max_workers: Maximum number of concurrent threads
        
    Returns:
        Dictionary mapping username to tuple (model_id, error_message)
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    results = {}
    
    def fetch_single_model_id(username):
        return username, get_model_id_for_user(username)
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS ) as executor:
        # Submit all fetches
        future_to_username = {
            executor.submit(fetch_single_model_id, username): username 
            for username in usernames
        }
        
        # Collect results as they complete
        for future in as_completed(future_to_username):
            try:
                username, result = future.result()
                results[username] = result
            except Exception as e:
                username = future_to_username[future]
                xbmc.log(f"{ADDON_SHORTNAME}: Error processing model ID for {username}: {str(e)}", xbmc.LOGWARNING)
                results[username] = (None, str(e))

    return results

def notify(heading, message, error=False):
    """Show a Kodi notification."""

    xbmcgui.Dialog().notification(
        heading,
        message,
        xbmcgui.NOTIFICATION_ERROR if error else xbmcgui.NOTIFICATION_INFO,
        6000 if error else 4000)

def is_hls_url(url):
    """True if the url points to a m3u8 playlist instead of a media file."""

    try:
        return urllib.parse.urlparse(url).path.lower().endswith('.m3u8')
    except Exception:
        return False

def ext_from_url(url):
    """Return the extension the download should be SAVED as, defaulting to .mp4.
       A m3u8 playlist becomes .ts, because we concatenate its MPEG-TS segments.
    """

    if is_hls_url(url):
        return '.ts'
    try:
        path = urllib.parse.urlparse(url).path
        ext = os.path.splitext(path)[1].lower()
        if re.fullmatch(r'\.[a-z0-9]{2,4}', ext or ''):
            return ext
    except Exception:
        pass
    return '.mp4'

def sanitize_filename_part(text, max_len=100):
    """Make a single filename component safe for NTFS, ext4 and SMB.
       Unicode is kept on purpose (Kodi paths are utf-8), only
       dangerous ascii characters are removed.
    """

    if not text:
        return ""
    text = str(text)
    # Replace control characters with a space, so newlines and tabs do not glue words together
    text = ''.join(ch if (ord(ch) >= 32 and ord(ch) != 127) else ' ' for ch in text)
    # Characters forbidden on Windows (and unsafe over SMB from any client)
    text = re.sub(r'[<>:"/\\|?*]', '', text)
    # Collapse whitespace runs into single spaces
    text = re.sub(r'\s+', ' ', text).strip()
    # Windows silently strips trailing dots and spaces, so do it ourselves
    text = text.rstrip(' .')
    if len(text) > max_len:
        text = text[:max_len].rstrip(' .')
    return text

def build_download_filename(username, title, url, video_id, is_trailer=False, folder=""):
    """Build the target filename: "<username> - <title>.<ext>"."""

    ext = ext_from_url(url)
    user = sanitize_filename_part(username, 60) or "unknown"
    name = sanitize_filename_part(title, 100)
    if not name:
        # Title was empty or consisted only of stripped characters
        name = str(video_id)

    stem = "%s - %s" % (user, name)
    if is_trailer:
        stem += " (trailer)"

    # Reserved Windows device names (the " - " normally prevents a match, but be safe)
    if stem.upper().split('.')[0] in WIN_RESERVED:
        stem = "_" + stem

    # Keep the whole path within sane limits (255 char component limit, MAX_PATH)
    budget = min(MAX_FILENAME_LEN, 250 - len(folder) - len(ext) - len(".part"))
    budget = max(budget, 24)
    if len(stem) + len(ext) > budget:
        stem = stem[:budget - len(ext)].rstrip(' .')

    return stem + ext

def join_vfs_path(folder, filename):
    """Join a folder setting and a filename. Works for local paths and vfs urls."""

    if not folder:
        return filename
    folder = xbmcvfs.translatePath(folder)
    sep = '/' if '://' in folder else os.sep
    if folder[-1] not in ('/', '\\'):
        folder += sep
    return folder + filename

def get_download_folder_or_prompt():
    """Return the configured download path or open the settings if it is not set."""

    path = ADDON.getSetting('download_path')
    if not path:
        xbmcgui.Dialog().ok("Download", "Download path is empty. Please set a valid path in settings menu under \"Downloads\" first.")
        xbmcaddon.Addon(id=ADDON_NAME).openSettings()
        return ""
    return path

class _ProgressBar:
    """Throttled wrapper around DialogProgressBG. update() is a cross thread gui
       call, so only push it when the percentage changed or twice a second.
    """

    def __init__(self, heading, display_name):
        self.heading = heading
        self.display_name = display_name
        self.last_pct = -1
        self.last_update = 0.0
        self.bg = xbmcgui.DialogProgressBG()
        self.bg.create(heading, display_name)

    def update(self, pct, detail):
        # Round to whole percent first, so the "changed" check actually throttles
        pct = min(100, max(0, int(pct)))
        now = time.time()
        if pct != self.last_pct or now - self.last_update > 0.5:
            self.bg.update(pct, self.heading, "%s  %s" % (self.display_name, detail))
            self.last_pct = pct
            self.last_update = now

    def close(self):
        try:
            self.bg.close()
        except Exception:
            pass

def get_playlist_text(url):
    """Fetch a m3u8 playlist as text."""

    req = urllib.request.Request(url, headers=FORWARD_HEADERS)
    response = urllib.request.urlopen(req, timeout=DOWNLOAD_TIMEOUT)
    try:
        return response.read().decode('utf-8', 'replace')
    finally:
        response.close()

def resolve_hls_segments(url, _depth=0):
    """Resolve a m3u8 url into (segments, init_url), where segments is a list of
       (segment_url, duration). Raise IOError for playlists we cannot concatenate byte for byte.
    """

    if _depth > 3:
        raise IOError("Too many nested playlists")

    lines = [l.strip() for l in get_playlist_text(url).splitlines() if l.strip()]
    if not lines or not lines[0].startswith('#EXTM3U'):
        raise IOError("Not a valid m3u8 playlist")

    # Master playlist: follow the best variant
    if any(l.startswith('#EXT-X-STREAM-INF') for l in lines):
        best_uri = None
        best_bandwidth = -1
        for index, line in enumerate(lines):
            if not line.startswith('#EXT-X-STREAM-INF'):
                continue
            match = re.search(r'BANDWIDTH=(\d+)', line)
            bandwidth = int(match.group(1)) if match else 0
            uri = next((l for l in lines[index + 1:] if not l.startswith('#')), None)
            if uri and bandwidth > best_bandwidth:
                best_uri = uri
                best_bandwidth = bandwidth
        if not best_uri:
            raise IOError("No variant stream found in master playlist")
        return resolve_hls_segments(urllib.parse.urljoin(url, best_uri), _depth + 1)

    # Media playlist. Bail out on anything a plain concatenation would get wrong.
    for line in lines:
        if line.startswith('#EXT-X-KEY') and 'METHOD=NONE' not in line:
            raise IOError("This video is an encrypted HLS stream and cannot be downloaded")
        if line.startswith('#EXT-X-BYTERANGE'):
            raise IOError("This video uses byte range segments, which are not supported")

    init_url = None
    segments = []
    duration = 0.0
    for line in lines:
        if line.startswith('#EXT-X-MAP'):
            match = re.search(r'URI="([^"]+)"', line)
            if match:
                init_url = urllib.parse.urljoin(url, match.group(1))
        elif line.startswith('#EXTINF'):
            try:
                duration = float(line.split(':', 1)[1].split(',')[0])
            except (ValueError, IndexError):
                duration = 0.0
        elif not line.startswith('#'):
            segments.append((urllib.parse.urljoin(url, line), duration))
            duration = 0.0

    if not segments:
        raise IOError("No segments found in playlist")
    return segments, init_url

def _stream_url_to_file(url, file_handle, monitor, on_progress=None):
    """Stream one url into an already open file handle.
       on_progress(bytes_done_in_this_url, content_length_or_0) is called per chunk.
       Returns the number of bytes written.
    """

    req = urllib.request.Request(url, headers=FORWARD_HEADERS)
    response = urllib.request.urlopen(req, timeout=DOWNLOAD_TIMEOUT)
    try:
        total = int(response.headers.get('Content-Length') or 0)
        done = 0
        while True:
            if monitor.abortRequested():
                raise IOError("Kodi is shutting down")
            chunk = response.read(DOWNLOAD_CHUNK_SIZE)
            if not chunk:
                break
            # write() returns False on a full disk or a dropped share, it does not raise
            if file_handle.write(bytearray(chunk)) is False:
                raise IOError("Write failed (disk full or share disconnected?)")
            done += len(chunk)
            if on_progress:
                on_progress(done, total)

        if total > 0 and done < total:
            raise IOError("Incomplete download (%d of %d bytes)" % (done, total))
        return done
    finally:
        response.close()

def _download_direct(url, file_handle, monitor, bar):
    """Download a plain media file (mp4)."""

    def on_progress(done, total):
        if total > 0:
            bar.update(done * 100.0 / total,
                       "%.1f / %.1f MB" % (done / 1048576.0, total / 1048576.0))
        else:
            # Without a Content-Length there is nothing honest to show but the counter
            bar.update(0, "%.1f MB" % (done / 1048576.0))

    return _stream_url_to_file(url, file_handle, monitor, on_progress)

def _download_hls(url, file_handle, monitor, bar):
    """Download an (unencrypted) HLS VOD playlist by concatenating its segments. 
    MPEG-TS segments can simply be appended."""

    segments, init_url = resolve_hls_segments(url)
    total_duration = sum(duration for _, duration in segments)
    count = len(segments)
    xbmc.log(ADDON_SHORTNAME + ": HLS download, %d segments, %.1f s total" % (count, total_duration), 1)

    written = 0
    done_duration = 0.0

    # A fragmented mp4 playlist needs its init segment first
    if init_url:
        written += _stream_url_to_file(init_url, file_handle, monitor)

    for index, (segment_url, duration) in enumerate(segments):
        if monitor.abortRequested():
            raise IOError("Kodi is shutting down")

        def on_progress(done, total, _index=index, _duration=duration):
            # Weight by playtime so the bar moves smoothly even with few large segments
            if total_duration > 0:
                fraction = (done / float(total)) if total > 0 else 0.0
                pct = (done_duration + fraction * _duration) / total_duration * 100.0
            else:
                pct = _index * 100.0 / count
            bar.update(pct, "segment %d/%d  %.1f MB" % (_index + 1, count, (written + done) / 1048576.0))

        written += _stream_url_to_file(segment_url, file_handle, monitor, on_progress)
        done_duration += duration

    return written

def _finalize_download(part_path, dest_path):
    """Move the finished part file onto the destination."""

    # rename does not overwrite an existing destination, so clear it first
    if xbmcvfs.exists(dest_path):
        xbmcvfs.delete(dest_path)
    if not xbmcvfs.rename(part_path, dest_path):
        if xbmcvfs.copy(part_path, dest_path):
            xbmcvfs.delete(part_path)
            xbmc.log(ADDON_SHORTNAME + ": Rename failed, used copy fallback for " + dest_path, xbmc.LOGWARNING)
        else:
            raise IOError("Could not move the finished file into place")

def download_file_with_progress(url, dest_path, heading, display_name):
    """Download url to dest_path showing a background progress bar. Handles both
       plain media files and unencrypted HLS VOD playlists (concatenated to .ts).
       Writes to a .part file and renames on success, so an interrupted
       download never looks like a finished one.
       Returns a tuple (ok, message).
    """

    part_path = dest_path + ".part"

    # Guard before the try block: the cleanup path below deletes the part file, so
    # bailing out from inside would kill the download that is already running.
    if xbmcvfs.exists(part_path):
        return False, "A download for this file seems to be running already."

    monitor = xbmc.Monitor()
    bar = _ProgressBar(heading, display_name)
    file_handle = None

    try:
        file_handle = xbmcvfs.File(part_path, 'w')

        if is_hls_url(url):
            written = _download_hls(url, file_handle, monitor, bar)
        else:
            written = _download_direct(url, file_handle, monitor, bar)

        file_handle.close()
        file_handle = None

        _finalize_download(part_path, dest_path)

        bar.close()
        xbmc.log(ADDON_SHORTNAME + ": Downloaded %s (%d bytes)" % (dest_path, written), 1)
        return True, dest_path

    except Exception as e:
        xbmc.log(ADDON_SHORTNAME + ": Download failed for %s: %s" % (url, str(e)), xbmc.LOGERROR)
        # Close the handle before deleting, removing an open file fails on Windows
        try:
            if file_handle:
                file_handle.close()
        except Exception:
            pass
        try:
            if xbmcvfs.exists(part_path):
                xbmcvfs.delete(part_path)
        except Exception:
            pass
        bar.close()
        return False, str(e)

def ctx_download_profile_video(model_id, username, video_id, kind="video"):
    """Download a profile video (or the trailer of a restricted one) to the
       configured download folder. Called from the context menu via RunScript.
    """

    is_trailer = (kind == "trailer")
    heading = ADDON_SHORTNAME + (" - Downloading trailer" if is_trailer else " - Downloading video")

    folder = get_download_folder_or_prompt()
    if not folder:
        return

    # Resolve a fresh url, listing time urls may already have expired
    try:
        if not model_id:
            model_id, model_err = get_model_id_for_user(username)
            if not model_id:
                raise IOError(model_err or "Could not resolve user id for " + username)

        data = json.loads(get_data_from_page(API_ENDPOINT_VIDEOS_WITH_ID.format(model_id)))
        item = next((v for v in data.get('videos', []) if str(v.get('id')) == str(video_id)), None)
        if not item:
            raise IOError("Video is no longer available")

        url = item.get('trailerUrl') if is_trailer else item.get('videoUrl')
        title = item.get('title') or ""
        if not url:
            raise IOError("No download url for this video")
    except Exception as e:
        xbmc.log(ADDON_SHORTNAME + ": Download lookup failed for %s/%s: %s" % (username, video_id, str(e)), xbmc.LOGERROR)
        notify("Download failed", str(e), error=True)
        return

    try:
        if not xbmcvfs.exists(folder):
            xbmcvfs.mkdirs(folder)
    except Exception as e:
        xbmc.log(ADDON_SHORTNAME + ": Could not create download folder %s: %s" % (folder, str(e)), xbmc.LOGWARNING)

    filename = build_download_filename(username, title, url, video_id, is_trailer, folder)
    destination = join_vfs_path(folder, filename)

    # Ask before anything is transferred
    if xbmcvfs.exists(destination):
        if not xbmcgui.Dialog().yesno("Download",
                                      "This file already exists:\n%s\n\nOverwrite it?" % filename,
                                      yeslabel="Overwrite", nolabel="Skip"):
            notify("Download", "Skipped: " + filename)
            return

    ok, message = download_file_with_progress(url, destination, heading, filename)
    if ok:
        notify("Download finished", filename)
    else:
        notify("Download failed", message, error=True)