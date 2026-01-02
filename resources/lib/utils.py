import os
import json
import xbmc
import xbmcgui
import xbmcaddon
import xbmcvfs
import sqlite3
import urllib.request
from urllib.request import Request
import urllib.error
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
Q_THUMBNAILS = "SELECT url,cachedurl FROM texture WHERE url LIKE '%.strpst.com%'"
Q_DEL_THUMBNAILS = "DELETE FROM texture WHERE url LIKE '%.strpst.com%'"
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

# Threading
MAX_WORKERS = ADDON.getSettingInt('max_workers')

# HTTP request headers
SITE_URL = "https://stripchat.com"
SITE_REFFERER = "https://stripchat.com/"
SITE_ORIGIN = "https://stripchat.com"
SITE_ACCEPT = "text/html"

# User agent(s)
USER_AGENT = " Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.182 Safari/537.36"

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

def get_model_id_for_user(username):
    """Return (modelId (string) or None, error_message or None) for a given username.
       When the API returns JSON with only 'title' and 'description' (e.g. when account is deleted),
       the 'description' value is returned as error_message.
    """
    try:
        payload = get_data_from_page(API_ENDPOINT_BROADCASTS.format(username))
        data = json.loads(payload)
        model_id = None
        error_msg = None

        if isinstance(data, dict):
            # Common places to find the id
            if 'modelId' in data:
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

        if model_id:
            return str(model_id), None
        return None, error_msg

    except Exception as e:
        xbmc.log(f"{ADDON_SHORTNAME}: Error getting modelId for {username}: {str(e)}", xbmc.LOGERROR)
        return None, str(e)

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

def get_site_page_full_old(page):
    """Fetch HTML data from site"""

    req = urllib.request.Request(page)
    req.add_header('Referer', SITE_REFFERER)
    req.add_header('Origin', SITE_ORIGIN)
    req.add_header('User-Agent', USER_AGENT)
    req.add_header('Accept', SITE_ACCEPT)
    
    response = urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT)
    if response.getcode() != 200:
        xbmc.log(ADDON_SHORTNAME + ": Request failed with code " + response.getcode())
    
    return response.read().decode('utf-8')

def get_data_from_page(page):
    """Fetch HTML data from site"""
    req = urllib.request.Request(page)
    req.add_header('Referer', SITE_REFFERER)
    req.add_header('Origin', SITE_ORIGIN)
    req.add_header('User-Agent', USER_AGENT)
    req.add_header('Accept', SITE_ACCEPT)

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
        req = urllib.request.Request(url, method='HEAD')
        req.add_header('User-Agent', USER_AGENT)
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

def fetch_user_data_parallel(usernames, API_ENDPOINT_MODEL, max_workers=10):
    """
    Fetch user data for multiple usernames in parallel
    
    Args:
        usernames: List of usernames to fetch data for
        max_workers: Maximum number of concurrent threads
        
    Returns:
        Dictionary mapping username to user data (or None if failed)
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    results = {}
    
    def fetch_single_user(username):
        try:
            data = get_data_from_page(API_ENDPOINT_MODEL.format(username))
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