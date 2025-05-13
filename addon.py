import os
import sys
import json
import xbmc
import xbmcgui
import xbmcaddon
import xbmcplugin
import xbmcvfs
import sqlite3
import re
import urllib.request
import urllib.parse
import urllib.error
import socket
from datetime import datetime, timedelta

# Config constants
ADDON_NAME = "plugin.video.sc19"
ADDON_SHORTNAME = "SC19"
BASE_DIR = os.path.dirname(__file__)
DB_FAVOURITES_FILE = "favourites-sc.db"
DB_FAVOURITES = xbmcvfs.translatePath("special://profile/addon_data/%s/%s" % (ADDON_NAME, DB_FAVOURITES_FILE))
DB_TEXTURES = xbmcvfs.translatePath("special://userdata/Database/Textures13.db")
PATH_THUMBS = xbmcvfs.translatePath("special://userdata/Thumbnails/")

# Queries
Q_THUMBNAILS = "SELECT url,cachedurl FROM texture WHERE url LIKE '%.strpst.com%'"
Q_DEL_THUMBNAILS = "DELETE FROM texture WHERE url LIKE '%.strpst.com%'"

# Addon init
PLUGIN_ID = int(sys.argv[1])
ADDON = xbmcaddon.Addon(id=ADDON_NAME)

# Paths
ART_FOLDER = ADDON.getAddonInfo('path') + '/resources/media/'

# URLs and headers for requests
SITE_URL = "https://stripchat.com"
SITE_REFFERER = "https://stripchat.com"
SITE_ORIGIN = "https://stripchat.com"
SITE_ACCEPT = "text/html"
API_ENDPOINT_MODELS = "https://stripchat.com/api/front/models"
API_ENDPOINT_MODELS_FILTER = "https://stripchat.com/api/front/models?&limit={0}&offset={1}&primaryTag={2}&filterGroupTags=[[\"{3}\"]]&sortBy={4}"
API_ENDPOINT_MODEL  = "https://stripchat.com/api/front/v2/models/username/{0}/cam"
API_ENDPOINT_MEMBERS = "https://stripchat.com/api/front/models/username/{0}/members"
API_ENDPOINT_ALBUMS = "https://stripchat.com/api/front/v2/users/username/{0}/albums"
API_ENDPOINT_ALBUM = "https://stripchat.com/api/front/users/username/{0}/albums/{1}/photos"
API_ENDPOINT_VIDEOS = "https://de.stripchat.com/api/front/v2/users/username/{0}/videos"
API_ENDPOINT_SEARCH = "https://stripchat.com/api/front/v4/models/search/group/username?query={0}&primaryTag={1}&limit=99"

SNAPSHOT_IMAGE = "https://img.strpst.com/{0}/thumbs/{1}/{2}_webp"

# User agent(s)
USER_AGENT = " Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.182 Safari/537.36"

# Site specific constants
LIST_LIMITS = [10, 25, 50, 75, 99]
LIST_LIMIT = LIST_LIMITS[ADDON.getSettingInt('list_limit')]
SORT_BY_OPTIONS = ["stripRanking", "trending"]
SORT_BY_STD = SORT_BY_OPTIONS[ADDON.getSettingInt('sort_by')]
PRIMARY_TAG = "girls"
DEL_THUMBS_ON_STARTUP = ADDON.getSettingBool('del_thumbs_on_startup')
REQUEST_TIMEOUT = ADDON.getSettingInt('request_timeout')

USER_STATES = {
    'public' : '',
    'private' : 'pvt',
    'p2p' : 'p2p',
    'virtualPrivate' : 'vPvt',
    'groupShow' : 'group',
    'p2pVoice' : 'p2pV',
    'idle' : 'idle',
    'off' : 'off'
}
USER_STATES_NICE = {
    'public' : 'Public',
    'private' : 'Private Session',
    'p2p' : 'Peer2Peer Session',
    'virtualPrivate' : 'Private Session (VR)',
    'groupShow' : 'Group Show',
    'p2pVoice' : 'Peer2Peer Session (VR)',
    'idle' : 'Public Idle',
    'off' : 'Offline'
}

# Tuples for menu and categories on site
SITE_MENU = (('Categories - Girls', "sitecat=cats-f", "Show girls cams only."), 
             ('Categories - Couples', "sitecat=cats-c", "Show couples cams only."), 
             ('Categories - Guys', "sitecat=cats-m", "Show guys cams only."), 
             ('Categories - Trans', "sitecat=cats-t", "Show trans cams only."),
             ("Favourites", "favourites", "Favourites list. Online status will be checked on opening the list."),
             ("Search", "fuzzy/girls", "Search for cams. Girls only. Search for other genres with search in each category."),
             ("Search Exact", "search", "Search for an exact username.\nA little more info about cam than normal search."),
             ("Tools", "sitecat=tools", "Some tools for cleanup and favourites.")
             )
SITE_CATS_F     = (("Search", "fuzzy/girls", "Search for cams in girls category"),
                   ("All", "category/girls", ""),
                   ("Recommended", "category/girls/recommended", ""),
                   ("VR cams", "category/girls/autoTagVr", ""),
                   ("New cams", "category/girls/autoTagNew", ""),
                   ("Teen 18-21", "category/girls/ageTeen", ""),
                   ("Young 22-34", "category/girls/ageYoung", ""),
                   ("MILF", "category/girls/ageMilf", ""),
                   ("Mature", "category/girls/ageMature", ""),
                   ("Granny", "category/girls/ageOld", ""),
                   ("Arab", "category/girls/ethnicityMiddleEastern", ""),
                   ("Asian", "category/girls/ethnicityAsian", ""),
                   ("Ebony", "category/girls/ethnicityEbony", ""),
                   ("Indian", "category/girls/ethnicityIndian", ""),
                   ("Latina", "category/girls/ethnicityLatino", ""),
                   ("White", "category/girls/ethnicityWhite", ""))
SITE_CATS_M     = (("Search", "fuzzy/men", "Search for cams in men category"),
                   ('All', "category/men", ""),
                   ("New cams", "category/men/autoTagNew", ""))
SITE_CATS_C     = (("Search", "fuzzy/couples", "Search for cams in couples category"),
                   ('All', "category/couples", ""),
                   ("New cams", "category/couples/autoTagNew", ""))
SITE_CATS_T     = (("Search", "fuzzy/trans", "Search for cams in trans category"),
                   ('All', "category/trans", ""),
                   ("New cams", "category/trans/autoTagNew", ""))
SITE_TOOLS = (("Backup Favourites", "tool=fav-backup", "Backup favourites (Set backup location in settings first). \nExisting favourites file will be overwritten without warning."),
              ("Restore Favourites", "tool=fav-restore", "Restore your favourites from backup location."),
              ("Delete Thumbnails", "tool=thumbnails-delete", "Delete cached stripchat related thumbnail files and database entries."))

# Strings
STRINGS = {
    'na' : 'User is not available',
    'last_status' : 'Last status: ',
    'unknown_status' : 'Unkown status: ',
    'not_live' : 'User is not live at the moment',
    'not_found' : 'Account not found. It may have been deleted.',
    'deactivated' : 'This account is deactivated'
}

def evaluate_request():
    """Evaluate what has been picked in Kodi"""
    
    if not sys.argv[2]:
        get_menu("main")
        return

    # URL decode the parameter
    param = urllib.parse.unquote(sys.argv[2])
    
    # Map parameters to functions
    param_map = {
        "sitecat=": get_menu,
        "favourites": get_favourites,
        "search": search_actor,
        "getProfile": get_profile_data,
        "fuzzy/": search_actor2,
        "tool=": handle_tool,
        "category": get_cams_by_category,
        "playactor=": play_actor,
        "getalbums=": get_albums,
        "getvideos=": get_videos,
        "getalbum=": get_album,
        "playurl=": play_url,
        "showpicture=": show_picture,
        "getpicture=": get_picture,
        "slideshow=": slideshow
    }

    # Find matching parameter and call corresponding function
    for key, func in param_map.items():
        if key in param:
            if key == "fuzzy/":
                func(param.split("fuzzy/")[1].split("?")[0])
                return
            if key == "sitecat=":
                func(re.findall(r'sitecat=(.*)', param)[0])
            elif key == "getProfile":
                func(re.findall(r'\?getProfile=(.*)', param)[0])
            elif key == "tool=":
                handle_tool(re.findall(r'\?tool=(.*)', param)[0])
            elif key == "playactor=":
                func(re.findall(r'\?playactor=(.*)', param)[0])
            elif key == "getalbums=":
                func(re.findall(r'\?getalbums=(.*)', param)[0])
            elif key == "getvideos=":
                func(re.findall(r'\?getvideos=(.*)', param)[0])
            elif key == "getalbum=":
                func(re.findall(r'\?getalbum=(.*)&', param)[0], re.findall(r'&id=(.*)', param)[0])
            elif key == "playurl=":
                func(re.findall(r'\?playurl=(.*)&', param)[0], re.findall(r'&title=(.*)', param)[0])
            elif key == "showpicture=":
                func(re.findall(r'\?showpicture=(.*)', param)[0])
            elif key == "getpicture=":
                func(re.findall(r'\?getpicture=(.*)', param)[0])
            elif key == "slideshow=":
                func(re.findall(r'\?slideshow=(.*)&', param)[0], re.findall(r'&id=(.*)', param)[0])
            else:
                func()
            return

    # If no matching parameter found
    xbmc.log(f"Unhandled parameter: {param}", level=xbmc.LOGERROR)

def handle_tool(tool):
    tool_map = {
        "fav-backup": tool_fav_backup,
        "fav-restore": tool_fav_restore,
        "thumbnails-delete": tool_thumbnails_delete
    }
    if tool in tool_map:
        tool_map[tool]()
    else:
        xbmc.log(f"Unhandled tool: {tool}", level=xbmc.LOGERROR)

def get_menu(param):
    """Decision tree. Shows main menu by default"""
    
    itemlist = SITE_MENU
    if param == "cats-f":
        itemlist = SITE_CATS_F
    elif param == "cats-m":
        itemlist = SITE_CATS_M
    elif param == "cats-c":
        itemlist = SITE_CATS_C
    elif param == "cats-t":
        itemlist = SITE_CATS_T
    elif param == "tools":
        itemlist = SITE_TOOLS
        
    # Build menu items
    items = []
    for item in itemlist:
        url = sys.argv[0] + '?' + item[1]
        li = xbmcgui.ListItem(item[0])
        vit = li.getVideoInfoTag()
        vit.setPlot(item[2])
        items.append((url, li, True))

    xbmcplugin.addDirectoryItems(PLUGIN_ID, items)
    xbmcplugin.endOfDirectory(PLUGIN_ID)

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

def connect_favourites_db():
    "Connect to favourites database and create one, if it does not exist."

    db_con = sqlite3.connect(DB_FAVOURITES)
    c = db_con.cursor()
    try:
        c.execute("SELECT * FROM favourites;")
    except sqlite3.OperationalError:
        c.executescript("CREATE TABLE favourites (user primary key);")
    return db_con

def get_profile_data(item):
    data = get_site_page_full(API_ENDPOINT_MODEL.format(item))
    data = json.loads(data)
    xbmc.log("AVATAR URL: " + data["user"]["user"]["avatarUrl"], 1)
    return data["user"]["user"]["avatarUrl"]

def get_favourites():
    """Get list of favourites from addon's db"""    
    
    # Clean Thumbnails before opening the list
    if DEL_THUMBS_ON_STARTUP:
        tool_thumbnails_delete2()

    # Connect to favourites db
    db_con = connect_favourites_db()
    c = db_con.cursor()
    c.execute("SELECT * FROM favourites")
    res = []
    for (user) in c.fetchall():
        res.append((user[0]))
    res.sort()

    # Settings
    fav_default_icon = ADDON.getSettingBool('fav_default_icon')
    fav_check_online_status = ADDON.getSettingBool('fav_check_online_status')

    # Progress bar
    prg = xbmcgui.DialogProgress()
    prg.create("Scanning favourites", "0 from " + str(len(res)) ) 
    n = 0
    i = 0
    chunk = 100/len(res)
    # Build kodi listitems for virtual directory
    items = []
    for item in res:
        # Cancel scanning
        if prg.iscanceled():
            fav_check_online_status = False
        n += 1
        i += chunk
        prg.update(int(i), "Favourite " + str(n) + " from " + str(len(res)) + " ( " + item + " )")
        url = sys.argv[0] + '?playactor=' + item
        li = xbmcgui.ListItem(item)
        vit = li.getVideoInfoTag()
        
        # Get JSON for model to load avatar, fanart and status
        try:
            if fav_check_online_status:
                data = get_site_page_full(API_ENDPOINT_MODEL.format(item))
                data = json.loads(data)
            
                status = data["user"]["user"]['status']
                username = get_username_string_from_status(item, status)
                # Show avatar if not live
                if not status == "public":
                    if fav_default_icon:
                        li.setArt({'icon': get_icon_from_status(status), 'fanart': data["user"]["user"]['previewUrl']})
                    else:
                        li.setArt({'icon': data["user"]["user"]["avatarUrl"], 'fanart': data["user"]["user"]['previewUrl']})
                else:
                    #SNAPSHOT_IMAGE = "https://img.strpst.com/thumbs/{0}/{1}_webp"
                    snap = "https://img.strpst.com/thumbs/{0}/{1}_webp".format(data["user"]["user"]['snapshotTimestamp'],data["user"]["user"]['id'])
                    li.setArt({'icon': snap, 'thumb': snap, 'fanart': data["user"]["user"]['previewUrl']})
            
                # Tag info
                plot = get_tag_string_for_plot(data["user"]["user"])
                # Status
                plot += "Status: " + status + "\n"
                # Prices
                plot += get_prices_string_for_plot(data["user"]["user"])
                # Set plot
                vit.setPlot(plot)
            # Just list names
            else:
                username = item
                li.setArt({'icon': 'DefaultVideo.png', 'thumb': 'DefaultVideo.png'})
                
        except Exception as e:
            # User does not exist anymore
            #xbmc.log("ERROR: " + str(e) + ". User " + item + " does not exist (anymore)!", 1)
            username = item + " (DEL)"
            vit.setPlot('Username does not exist (anymore)!')
            #pass
        li.setLabel(username)
        #Check offline etc. and add info to name!
        #Check for error if model deleted
        # Context menu        
        li.addContextMenuItems(get_ctx_for_cam_item(item, True), True)
        
        items.append((url, li, True))

    # Put items to virtual directory listing and set sortings
    xbmcplugin.setContent(int(sys.argv[1]), 'videos')
    xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_LABEL)
    xbmcplugin.addDirectoryItems(PLUGIN_ID, items)
    xbmcplugin.endOfDirectory(PLUGIN_ID)
    
# Old random 50 function    
def get_cams_from_json():
    """List available cams by category"""
    data = get_site_page_full('https://go.stripchat.com/api/models?limit=50')
    
    # JSON
    data = json.loads(data)
    
    # Build kodi list items for virtual directory
    items = []
    id = 0
    
    for item in data['models']:
        username = item['username']
        icon = item['snapshotUrl']
        #icon = item['avatarUrl']
        #if 'goalMessage' in item:
        #    message = item['goalMessage']
        #else:
        #    message = "n/a"
        
        viewers = item['viewersCount']
        
        url = sys.argv[0] + '?playactor=' + username
        xbmc.log("SC19: " + url,1)
        li = xbmcgui.ListItem(username)
        vit = li.getVideoInfoTag()
        
        li.setLabel(username)
        li.setArt({'icon': icon, 'thumb': icon, 'fanart': item['previewUrl']})
        vit.setSortTitle(str(id).zfill(2) + " - " + username)
        id = id + 1
        vit.setPlot(f"Status: {item['status']}\nViewers: {viewers}\nFavorited: {item['favoritedCount']}")
        vit.setPlaycount(int(viewers))
        
        # Context menu
        li.addContextMenuItems(get_ctx_for_cam_item(username), True)
        
        items.append((url, li, True))
        
    # Put items to virtual directory listing and set sortings
    put_virtual_directoy_listing(items)

def get_cams_by_category():
    """List available cams by category"""

    # Filter category
    cat = sys.argv[2].replace("%2f", "/")
    cat = cat.replace("?category/", "")

    # Default parameters
    limit = LIST_LIMIT
    sortBy = SORT_BY_STD
    primaryTag = PRIMARY_TAG
    filterGroupTags = ""
    offset = 0
    
    # Filter paramters
    paras = cat.split("/")
    
    if len(paras) == 1:
        primaryTag = paras[0]
    if len(paras) == 2:
        primaryTag = paras[0]
        filterGroupTags = paras[1]
    if len(paras) == 3:
        primaryTag = paras[0]
        filterGroupTags = paras[1]
        offset = int(paras[2])

    url = API_ENDPOINT_MODELS_FILTER.format(limit, offset, primaryTag, filterGroupTags, sortBy)
    xbmc.log("URL: " + url, 1)

    try:
        data = get_site_page_full(url)
        cams = json.loads(data)
        
        # result for category has a filteredCount value
        if "filteredCount" in cams:
            filteredCount = cams['filteredCount']
            totalCount = cams['filteredCount']
        # search results have totalCount value only
        else:
            filteredCount = cams['totalCount']
            totalCount = cams['totalCount']

        # Build kodi list items for virtual directory
        items = get_cam_infos_as_items(cams)

        # Pagination
        newOffset = offset + LIST_LIMIT
        if newOffset < filteredCount:
            nextpageurl = "category/" + primaryTag + "/" + filterGroupTags + "/" + str(newOffset)
            if newOffset+LIST_LIMIT > totalCount:
                li = xbmcgui.ListItem("Next (%s to %s)" % (str(newOffset+1),str(totalCount)))
            else:
                li = xbmcgui.ListItem("Next (%s to %s)" % (str(newOffset+1),str(newOffset+LIST_LIMIT)))
                
            vit = li.getVideoInfoTag()
            
            # Context menu
            commands = []
            commands.append(('Back first page',"Container.Update(%s?%s, replace)" % ( sys.argv[0],  "category/" + primaryTag + "/" + filterGroupTags)))
            commands.append(('Back main menu',"Container.Update(%s, replace)" % ( sys.argv[0])))
            li.addContextMenuItems(commands, False)
            
            li.setArt({'icon': 'DefaultFolder.png', 'thumb': 'DefaultFolder.png'})
            vit.setSortTitle(str(999).zfill(2) + " - Next Page")
            vit.setPlaycount(-1)
            vit.setPlot("Total cams: " + str(filteredCount))
            xbmc.log("NEXT PAGE URL: " + sys.argv[0] + '?'+nextpageurl, 1)
            items.append((sys.argv[0] + '?'+nextpageurl, li, True))
            
        # Put items to virtual directory listing and set sortings
        put_virtual_directoy_listing(items)
        return
    except:
        xbmcgui.Dialog().ok("Error", "Error filtering cams.")
        return

def put_virtual_directoy_listing(items):
    """Put items to virtual directory listing and set sortings"""
    xbmcplugin.setContent(PLUGIN_ID, 'videos')
    xbmcplugin.addSortMethod(PLUGIN_ID, xbmcplugin.SORT_METHOD_VIDEO_SORT_TITLE)
    xbmcplugin.addSortMethod(PLUGIN_ID, xbmcplugin.SORT_METHOD_PLAYCOUNT, "Viewers")
    xbmcplugin.addSortMethod(PLUGIN_ID, xbmcplugin.SORT_METHOD_LABEL)
    xbmcplugin.addDirectoryItems(PLUGIN_ID, items)
    xbmcplugin.endOfDirectory(PLUGIN_ID)

def get_viewers_count(actor):
    url = API_ENDPOINT_MEMBERS.format(actor)
    
    try:
        data = get_site_page_full(url)
        data = json.loads(data)
        viewers = data["guests"] + data["spies"] + data["invisibles"] + data["greens"] + data["golds"] + data["regulars"]
        return viewers
    except:
        return 0

def get_albums(actor):
    #xbmcgui.Dialog().ok("GET ALBUMS", "Get albums for: " + actor)
    # accessMode: friends|free|fanClub|paid
    # Get setting to show free plus restricted items
    show_all = ADDON.getSettingBool('ctx_show_all_albums')
    
    try:
        data = get_site_page_full(API_ENDPOINT_ALBUMS.format(actor))
        data = json.loads(data)
        data = data['albums']
        #xbmc.log(str(data), 1)
        
        # Just show directory if there is something to show
        if len(data) == 0:
            xbmcgui.Dialog().ok("Profile albums", "There are no albums available for this profile")
            return
        if not show_all:
            no_freeitems = True
            for item in data:
                if item['accessMode'] == 'free':
                    no_freeitems = False
            if no_freeitems:
                xbmcgui.Dialog().ok("Profile albums", "There are no free albums available for this profile")
                return
        
        # Parse items and build kodi listitems for virtual directory
        items = []
        for item in data:
            url = sys.argv[0] + '?getalbum=' + actor + "&id=" + str(item['id'])
            li = xbmcgui.ListItem(str(item['id']))
            
            #li.setInfo(type="Image", infoLabels={"Title": item['name'] + " "+ str(item['photosCount'])})
            li.setInfo('video', {'plot': "Photos: " + str(item['photosCount'])}) 
            if show_all:
                if not item['accessMode'] == 'free':
                    li.setArt({'icon': item['previewMicro'], 'thumb' : item['previewMicro']})
                    if item['accessMode'] == 'paid':
                        li.setLabel(item['name'] + " (" + str(item['cost']) + " tks)")
                    if item['accessMode'] == 'friends':
                        li.setLabel(item['name'] + " (friends)")
                    if item['accessMode'] == 'fanClub':
                        li.setLabel(item['name'] + " (fan club)")
                    if item['accessMode'] == 'verified':
                        li.setLabel(item['name'] + " (verified)")
                    items.append((url, li, True))
                    
                else:        
                    li.setLabel(item['name'])
                    li.setArt({'icon': item['preview'], 'fanart' : item['preview'], 'thumb' : item['preview']})
                    # Context menu
                    #commands = []
                    #commands.append(('Slideshow',"Container.Update(%s?%s)" % ( sys.argv[0],  "slideshow=" + actor + "&id=" + str(str(item['id'])))))
                    #li.addContextMenuItems(commands, False)
                    items.append((url, li, True))
            else:
                if item['accessMode'] == 'free':
                    li.setLabel(item['name'])
                    li.setArt({'icon': item['preview'], 'fanart' : item['preview'], 'thumb' : item['preview']})
                    items.append((url, li, True))
                    
        
        xbmcplugin.setContent(int(sys.argv[1]), 'images')
        xbmcplugin.addDirectoryItems(PLUGIN_ID, items)
        xbmcplugin.endOfDirectory(PLUGIN_ID)        
        
        #xbmcgui.Dialog().ok("Info", "Number of items: " + str(albums))
        
    except:
        xbmcgui.Dialog().ok("Error", "Error filtering albums.")
        return
    
def get_album(actor, id):
    try:
        data = get_site_page_full(API_ENDPOINT_ALBUM.format(actor,id))
        data = json.loads(data)
        
        data = data['photos']
        
        if len(data) == 0:
            xbmcgui.Dialog().ok("No photos", "Album contains no photos to display.")
        else:
            items = []
            i = 1
            for item in data:
                li = xbmcgui.ListItem(str(item['id']))
                li.setLabel("Photo " +  str(i).zfill(2))
                i += 1
                if not "url" in item:
                    li.setArt({'icon': item['urlThumbMicro'], 'thumb': item['urlThumbMicro']})
                    url = sys.argv[0] + '?showpicture=' + item['urlThumbMicro']
                else:
                    li.setArt({'icon': item['urlThumb'], 'thumb': item['urlThumb']})
                    url = sys.argv[0] + '?showpicture=' + item['url']
                li.setInfo(type='pictures', infoLabels={"title": "Photo " +  str(i).zfill(2), "picturepath": item['url']})
                #li.setProperty("IsPlayable", "true")
                #items.append((url, li, True))
                #items.append((url, li, False))
                xbmcplugin.addDirectoryItem(int(sys.argv[1]), url, li)
            xbmcplugin.setContent(int(sys.argv[1]), 'images')
            #xbmcplugin.addDirectoryItems(PLUGIN_ID, items)
            xbmcplugin.endOfDirectory(PLUGIN_ID)
    except:
        xbmcgui.Dialog().ok("Error", "Error getting album.")

def get_videos(actor):
    # accessMode: friends|free|fanClub|paid|verified
    # Get setting to show free plus restricted items
    show_all = ADDON.getSettingBool('ctx_show_all_videos')
    
    try:
        data = get_site_page_full(API_ENDPOINT_VIDEOS.format(actor))
        data = json.loads(data)
        data = data['videos']
        
        # Just show directory if there is something to show
        if len(data) == 0:
            xbmcgui.Dialog().ok("Profile videos", "There are no videos available for this profile")
            return
        if not show_all:
            no_freeitems = True
            for item in data:
                if item['accessMode'] == 'free':
                    no_freeitems = False
            if no_freeitems:
                xbmcgui.Dialog().ok("Profile videos", "There are no free videos available for this profile")
                return
                    
        
        # Parse items and build kodi listitems for virtual directory
        items = []
        for item in data:
            #url = sys.argv[0] + '?getalbum=' + actor + "&id=" + str(item['id'])
            li = xbmcgui.ListItem(str(item['id']))
            vit = li.getVideoInfoTag()
            
            li.setArt({'icon': item['coverUrl'], 'thumb': item['coverUrl']})
            
            if show_all:
                if not item['accessMode'] == 'free':
                    
                    if item['accessMode'] == 'paid':
                        li.setLabel(item['title'] + " (" + str(item['cost']) + " tks)")
                    if item['accessMode'] == 'friends':
                        li.setLabel(item['title'] + " (friends)")
                    if item['accessMode'] == 'fanClub':
                        li.setLabel(item['title'] + " (fan club)")
                    if item['accessMode'] == 'verified':
                        li.setLabel(item['title'] + " (verified)")
                        
                    vit.setDuration(item['duration'])
                    vit.setPlot("Restricted video: This is just a (shorter) trailer in lower quality.")
                    url = sys.argv[0] + '?playurl=' + item['trailerUrl']  + "&title=" + actor + " - " + item['title']
                    items.append((url, li, False))
                    
                else:        
                    li.setLabel(item['title'])
                    vit.setDuration(item['duration'])
                    #li.setArt({'icon': item['coverUrl'], 'thumb': item['coverUrl']})
                    url = sys.argv[0] + '?playurl=' + item['videoUrl']  + "&title=" + actor + " - " + item['title']
                    items.append((url, li, False))
                
            else:
                if item['accessMode'] == 'free':
                    li.setLabel(item['title'])
                    vit.setPlot("Duration in seconds: " + str(item['duration']))                    
                    #li.setArt({'icon': item['coverUrl']})
                    url = sys.argv[0] + '?playurl=' + item['videoUrl']
                    items.append((url, li, False))
        
        xbmcplugin.setContent(int(sys.argv[1]), 'videos')
        xbmcplugin.addDirectoryItems(PLUGIN_ID, items)
        xbmcplugin.endOfDirectory(PLUGIN_ID) 
    except:
        xbmcgui.Dialog().ok("Error", "Error filtering videos.")
        return
    
def play_url(url, title):
    xbmc.log("PLAY URL: " + url, 1)
    li = xbmcgui.ListItem(str("Profile Video"))
    vit = li.getVideoInfoTag()
    
    vit.setTitle(title)
    vit.setPlot(title)
    vit.setGenres(["Profile Video"])
    li.setLabel(title)
    
    # Get stream player setting
    stream_player = xbmcaddon.Addon().getSetting('stream_player')
    # Set inputstream addon based on setting
    if stream_player == "0":
        xbmc.log(ADDON_SHORTNAME + ": " + "Using default stream player", 1)
    if stream_player == "1":
        li.setProperty('inputstream', 'inputstream.ffmpegdirect')
        xbmc.log(ADDON_SHORTNAME + ": " + "Using InputStream FFmpegDirect", 1)
    
    xbmc.Player().play(url,li)
    
def show_picture(url):
    xbmc.executebuiltin('ShowPicture(%s)'%(url))

def slideshow2(actor, id):
    #xbmcgui.Dialog().ok("Slideshow", "Actor: " + actor + " Id: " + str(id))
    try:
        data = get_site_page_full(API_ENDPOINT_ALBUM.format(actor,id))
        data = json.loads(data)
        
        data = data['photos']
        
        if len(data) == 0:
            xbmcgui.Dialog().ok("No photos", "Album contains no photos to display.")
        else:
            items = []
            urls = []
            i = 1
            for item in data:
                li = xbmcgui.ListItem(str(item['id']))
                #li.setLabel(str(item['id']))
                li.setLabel("Photo " +  str(i).zfill(2))
                i += 1
                if not "url" in item:
                    li.setArt({'icon': item['urlThumbMicro']})
                    url = sys.argv[0] + '?showpicture=' + item['urlThumbMicro']
                else:
                    li.setArt({'icon': item['urlThumb'], 'thumb': item['urlThumb']})
                    url = sys.argv[0] + '?showpicture=' + item['url']
                    urls.append(sys.argv[0] + '?showpicture=' + item['url'])
                    li.setArt({'fanart' : str(item['urlThumb'])})
                items.append((url, li, False))
            xbmcplugin.setContent(int(sys.argv[1]), 'files')
            xbmcplugin.addDirectoryItems(PLUGIN_ID, items, i)
            xbmc.executebuiltin('SlideShow('+ "" + ', pause)')
    except:
        xbmcgui.Dialog().ok("Error", "Error getting album.")    

def slideshow(actor, id):
    xbmc.executebuiltin('Dialog.Close(busydialog)')
    xbmc.executebuiltin("ActivateWindow(Pictures,"+ sys.argv[0] + '?getalbum=' + actor + "&id=" + id +")")

def get_picture(url):
    data = get_site_page_full(url)
    return data

def play_actor(actor, genre="Stripchat"):
    """Get playlist for actor/username and add m3u8 to kodi's playlist"""
    
    # Try to play actor
    try:
        # Fetch and store HTML
        url = API_ENDPOINT_MODEL.format(actor)       
        #xbmc.log("URL to play: " + url, 1)
        data = get_site_page_full(url)
        data = json.loads(data)
        
        # Check for deactivated account
        if not data["cam"]:
            xbmcgui.Dialog().ok("Info", STRINGS['deactivated'])
            return
        
        bio = ""
        
        img = data["user"]["user"]["avatarUrl"]
        if not data["cam"]["topic"] == "":
            bio = "Topic: " + data["cam"]["topic"] + "\n"
        
        # variants hls_source = "https://edge-hls.doppiocdn.com/hls/{0}/master/{0}_auto.m3u8".format(data["cam"]["streamName"])
        # best only hls_source = "https://edge-hls.doppiocdn.com/hls/{0}/master/{0}.m3u8".format(data["cam"]["streamName"])
        hls_source = "https://edge-hls.doppiocdn.com/hls/{0}/master/{0}.m3u8".format(data["cam"]["streamName"])
        
        status = data["user"]["user"]["status"]
        isLive = data["user"]["user"]["isLive"]
            
        # Not live (public)
        if isLive == False:
            statusts = data["user"]["user"]["statusChangedAt"]
            xbmcgui.Dialog().ok(STRINGS['not_live'], "Status: " + USER_STATES_NICE["off"] + "\nLast broadcast: " + format_timestamp_relative(statusts))
            return
        # All other states
        if not status == "public":
            if status in USER_STATES_NICE:
                xbmcgui.Dialog().ok(STRINGS['na'], STRINGS['last_status'] + USER_STATES_NICE[status])  
                return
            # Unknown state
            else:
                xbmcgui.Dialog().ok(STRINGS['na'], STRINGS['unknown_status'] + status)  
                return
            
            
        # Extract playlist
        pl = hls_source
    
        # Bio stats
        if not data["cam"]["goal"] == None:
            bio += "Goal: " + data["cam"]["goal"]["description"] + " [" + str(data["cam"]["goal"]["spent"]) + "/" + str(data["cam"]["goal"]["goal"]) + "]\n"
            
        if not data["user"]["user"]["name"] == "":
            bio += "Name: " + data["user"]["user"]["name"] + "\n"
        viewers = get_viewers_count(actor)
        bio += "Viewers: " + str(viewers) + "\n"
        bio += get_prices_string_for_plot(data["user"]["user"]) + "\n"
        if not data["user"]["user"]["description"] == "":
            bio += "Description: " + data["user"]["user"]["description"] + "\n"
        #bio += "Birthday: " + data["user"]["user"]["birthDate"]
    
        # Build kodi listem for playlist
        li = xbmcgui.ListItem(actor)
        vit = li.getVideoInfoTag()
        vit.setGenres([genre])
        vit.setPlot(bio)
        li.setArt({'icon': img, 'thumb': img})
   
        li.setMimeType('application/vnd.apple.mpegstream_url')
        # Get stream player setting
        stream_player = xbmcaddon.Addon().getSetting('stream_player')
        # Set inputstream addon based on setting
        if stream_player == "0":
            xbmc.log(ADDON_SHORTNAME + ": " + "Using default stream player", 1)
        if stream_player == "1":
            li.setProperty('inputstream', 'inputstream.ffmpegdirect')
            xbmc.log(ADDON_SHORTNAME + ": " + "Using InputStream FFmpegDirect", 1)
        # Play stream
        xbmc.Player().play(pl, li)
    
    except:
        xbmcgui.Dialog().notification("Error", "Something went wrong.", "", 1000, False)  


def get_site_page(page):
    """Fetch HTML data from site (old variant)"""

    url = "%s/%s" % (SITE_URL, page)
    xbmc.log("URL: " + url, 1)
    req = urllib.request.Request(url)
    req.add_header('Referer', SITE_REFFERER)
    req.add_header('Origin', SITE_ORIGIN)
    req.add_header('User-Agent', USER_AGENT)
    req.add_header('Accept', SITE_ACCEPT)
    
    return urllib.request.urlopen(req).read()

def get_site_page_full(page):
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

def search_actor():
    """Search for actor/username and list item if username exists"""

    s = xbmcgui.Dialog().input("Search for exact username")
    if s == '':
        xbmcplugin.endOfDirectory(int(sys.argv[1]), succeeded=False)
    else:
        data = {}
        # Prepare request
        url = API_ENDPOINT_MODEL.format(s) 
        try:
            data = get_site_page_full(url)
            data = json.loads(data)
            
        except urllib.error.HTTPError as e:
            xbmcgui.Dialog().ok("Nothing found", "Username does not exist. Please try again.")
            return

        status = "off"

        # Grab search result
        try:
            # At this point we can be sure the username exists, otherwise: execept part
            try:
                # Try to extract the playlist. Only exists if user is online and not in private
                status = data["user"]["user"]["status"]
                
                #pl = re.findall(PAT_PLAYLIST, data)[0]
                #pl = pl.replace(b'\\u002D', b'-')
            except:
                # User is offline
                pass

            # Build kodi listem for virtual directory
            li = xbmcgui.ListItem(s)
            vit = li.getVideoInfoTag()

            # Context menu
            commands = []
            commands.append(('[COLOR orange]' + ADDON_SHORTNAME + ' - Add as favourite [/COLOR]','RunScript(' + ADDON_NAME + ', ' + str(sys.argv[1]) + ', add_favourite, ' + s + ')'))
            commands.append(('Show profile albums',"Container.Update(%s?%s)" % ( sys.argv[0],  "getalbums=" + s)))
            commands.append(('Show profile videos',"Container.Update(%s?%s)" % ( sys.argv[0],  "getvideos=" + s)))
            li.addContextMenuItems(commands, True)

            # Regex bio stats
            # Bio stats
            bio = ""
            if "goal" in data["cam"] and not data["cam"]["goal"] == None:
                bio += "Goal: " + data["cam"]["goal"]["description"] + " [" + str(data["cam"]["goal"]["spent"]) + "/" + str(data["cam"]["goal"]["goal"]) + "]\n"
            
            if not data["user"]["user"]["name"] == "":
                bio += "Name: " + data["user"]["user"]["name"] + "\n"
            viewers = get_viewers_count(s)
            bio += "Viewers: " + str(viewers) + "\n"
            if not data["user"]["user"]["description"] == "":
                bio += "Description: " + data["user"]["user"]["description"] + "\n"
            #bio += "Birthday: " + data["user"]["user"]["birthDate"]

            if status=="public":
                # Regex thumbnail
                img = data["user"]["user"]["avatarUrl"]
                
                # Regex topic
                topic = data["cam"]["topic"]
                
                vit.setPlot(topic + "\n\n" + bio)
                vit.setGenres(["Stripchat"])
                
                li.setLabel(s)
            else:
                # Prepare default thumbnail
                img = data["user"]["user"]["avatarUrl"]
                
                vit.setPlot(bio)
                if status=="private":    
                    li.setLabel(s + " (pvt)")
                if status=="p2p":    
                    li.setLabel(s + " (p2p)")
                if status=="virtualPrivate":    
                    li.setLabel(s + " (vPvt)")
                if status=="groupShow":
                    li.setLabel(s + " (group)")
                if status=="p2pVoice":    
                    li.setLabel(s + " (p2pV)")
                if status=="off":
                    li.setLabel(s + " (off)")
                if status=="idle":
                    li.setLabel(s + " (idle)")

            # Set thumbnail and fanart
            li.setArt({'icon': img, 'thumb': img, 'fanart' : data["user"]["user"]["previewUrl"]})

            # Put items to virtual directory listing
            url = sys.argv[0] + '?playactor=' + s
            xbmcplugin.setContent(int(sys.argv[1]), 'videos')
            xbmcplugin.addDirectoryItems(PLUGIN_ID, [(url, li, True)])
            xbmcplugin.endOfDirectory(PLUGIN_ID)

        # Actor does not exist, we got an HTTP 404 error
        except urllib.error.HTTPError as e:
            xbmcgui.Dialog().ok(str(e), "Username does not exist. Please try again.")



def search_actor2(primaryTag=None):
    """Fuzzy search for cams and list items if username exists"""
    
    s = xbmcgui.Dialog().input("Search for username")
    if s == '':
        xbmcplugin.endOfDirectory(int(sys.argv[1]), succeeded=False)
        return

    url = API_ENDPOINT_SEARCH.format(s, primaryTag if primaryTag else "girls")
    xbmc.log(f"Search URL: {url}", 1)
    
    try:
        data = get_site_page_full(url)
        cams = json.loads(data)
        xbmc.log("CAMS: " + str(len(cams['models'])),1)
        
        if len(cams['models']) == 0:
            xbmcgui.Dialog().ok("Nothing found", "No cams for this search term.")
            return
        
        # Build kodi list items for virtual directory
        items = get_cam_infos_as_items(cams)
        # Put items to virtual directory listing and set sortings
        put_virtual_directoy_listing(items)
        return
    except:
        xbmcgui.Dialog().ok("Error", "Error filtering cams.")
        return
    
def get_cam_infos_from_favourites(usernames):
    return    

def get_username_string_from_status(username, status):
    if status in USER_STATES:
        if status == "public":
            return username
        else:
            return username + " (" + USER_STATES[status] + ")"
    else:
        return username + " (???)"

def get_tag_string_for_plot(item):
    tags = []
    s = "Tags: "
    if item['isNew']:
        tags.append("NEW")
    if item['isHd'] == True:
        tags.append("HD")
    if item['isVr'] == True:
        tags.append("VR")
    if len(tags) == 0:
        return ""
    else:
        tags = str(tags).replace("'", "") + "\n"
        s += tags
        return s

def get_prices_string_for_plot(item):
    s = "Token price: "
    s2 = "not set"
    if "doPrivate" in item and "privateRate" in item:
        if item['doPrivate'] == True:
            s += str(item['privateRate']) + " (Pvt) "
            s2 = ""
    if "doP2p" in item and "p2pRate" in item:
        if item['doP2p'] == True:
            s += str(item['p2pRate']) + " (P2P) "
            s2 = ""
    if "doSpy" in item and "spyRate" in item:
        if item['doSpy'] == True:
            s += str(item['spyRate']) + " (Spy)"
            s2 = ""
    return s + s2

def get_cam_infos_as_items(cams):
    # Clean Thumbnails before opening the list
    if DEL_THUMBS_ON_STARTUP:
        tool_thumbnails_delete2()
        
    # Build kodi list items for virtual directory
    items = []
    id = 0
    
    for item in cams['models']:
        if not item['status'] == "offfff":
            username = item['username']
            
            icon = "https://img.strpst.com/thumbs/{0}/{1}_webp".format(item['snapshotTimestamp'],item['id'])
            #xbmc.log("ICON for " + username + ": " + icon, 1)
            url = sys.argv[0] + '?playactor=' + username
            #xbmc.log("SC19: " + url,1)
            li = xbmcgui.ListItem(username)
            vit = li.getVideoInfoTag()
            #log username and status
            #xbmc.log("Username: " + username + " Status: " + item['status'], 1)
            li.setLabel(get_username_string_from_status(username, item['status']))
            # previewUrlThumbBig is not available in JSON anymore, use previewUrlThumbSmall instead
            # avaiable: thumb-small, thumb-big, full
            fanart_url = item['previewUrlThumbSmall'].replace('-thumb-small', '-full')
            li.setArt({'icon': icon, 'thumb': icon, 'fanart': fanart_url})
            vit.setSortTitle(str(id).zfill(2) + " - " + username)
            id = id + 1
            # Tag info
            plot = get_tag_string_for_plot(item)
            # Status
            plot += "Status: " + USER_STATES_NICE[item['status']] + "\n"
            # Prices
            plot += get_prices_string_for_plot(item)
            # Set plot
            vit.setPlot(plot)
            
            # Context menu
            li.addContextMenuItems(get_ctx_for_cam_item(username), True)
            
            items.append((url, li, True))
    return items

def get_ctx_for_cam_item(username, remove=False):
    # Context menu
    commands = []
    # Favourites
    if remove:
        commands.append(('[COLOR orange]' + ADDON_SHORTNAME + ' - Remove favourite [/COLOR]','RunScript(' + ADDON_NAME + ', ' + str(sys.argv[1]) + ', remove_favourite, ' + username + ')'))
    else:
        commands.append(('[COLOR orange]' + ADDON_SHORTNAME + ' - Add as favourite [/COLOR]','RunScript(' + ADDON_NAME + ', ' + str(sys.argv[1]) + ', add_favourite, ' + username + ')'))
    commands.append(('[COLOR orange]' + ADDON_SHORTNAME + ' - Refresh thumbnails [/COLOR]','RunScript(' + ADDON_NAME + ', ' + str(sys.argv[1]) + ', ctx_thumbnails_delete)'))
    # Profile info
    commands.append(('Show profile albums',"Container.Update(%s?%s)" % ( sys.argv[0],  "getalbums=" + username)))
    commands.append(('Show profile videos',"Container.Update(%s?%s)" % ( sys.argv[0],  "getvideos=" + username)))
    # Settings
    #commands.append(('Settings',xbmc.executebuiltin('ADDON.openSettings()')))
    #commands.append(('Settings',ADDON.openSettings()))
    #ShowPicture(picture)
    return commands

def get_icon_from_status(status):
    icon = "DefaultVideo.png"
    if status == "private":
        icon = ART_FOLDER + 'icon-pvt.png'
    elif status == "p2p":
        icon = ART_FOLDER + 'icon-p2p.png'
    elif status == "virtualPrivate":
        icon = ART_FOLDER + 'icon-pvt.png'
    elif status == "groupShow":
        icon = ART_FOLDER + 'icon-grp.png'
    elif status == "p2pVoice":
        icon = ART_FOLDER + 'icon-p2p.png'
    elif status == "idle":
         icon = ART_FOLDER + 'icon-idle.png'
    elif status == "off":
        icon = ART_FOLDER + 'icon-off.png' 
    return icon

def tool_thumbnails_delete():
    rc = tool_thumbnails_delete2()
    # Summary dialog
    xbmcgui.Dialog().ok("Delete Thumbnails", "Deleted %s thumbnail files and database entries" % (str(rc)))

def tool_thumbnails_delete2():   
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
        #xbmc.log("Thumb: " + PATH_THUMBS + str(row[1]),1)
        if os.path.exists(PATH_THUMBS + str(row[1])):
            os.remove(PATH_THUMBS + str(row[1]))
            #xbmc.log("The file has been successfully deleted.",1)
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

if __name__ == "__main__":
    evaluate_request()
