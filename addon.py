import os
import sys
import json
from time import time
import xbmc
import xbmcgui
import xbmcaddon
import xbmcplugin
import re
import urllib.parse
import urllib.error
import socket
from resources.lib import proxy_module
from resources.lib import utils as sc19


# Common config constants (avilable in all modules)
ADDON_NAME = "plugin.video.sc19"
ADDON_SHORTNAME = "SC19"
ADDON = xbmcaddon.Addon(id=ADDON_NAME)

# Module specific constants
SNAPSHOT_IMAGE = "https://img.strpst.com/{0}/thumbs/{1}/{2}_webp"

# Global proxy instance
_proxy_instance = None

# Addon init
PLUGIN_ID = int(sys.argv[1])

# Paths
ART_FOLDER = ADDON.getAddonInfo('path') + '/resources/media/'

# API endpoints
API_ENDPOINT_MODELS = "https://stripchat.com/api/front/models"
API_ENDPOINT_MODELS_FILTER = "https://stripchat.com/api/front/models?&limit={0}&offset={1}&primaryTag={2}&filterGroupTags=[[\"{3}\"]]&sortBy={4}"
API_ENDPOINT_MODEL  = "https://stripchat.com/api/front/v2/models/username/{0}/cam"
API_ENDPOINT_MEMBERS = "https://stripchat.com/api/front/models/username/{0}/members"
API_ENDPOINT_ALBUMS = "https://stripchat.com/api/front/v2/users/username/{0}/albums"
API_ENDPOINT_ALBUM = "https://stripchat.com/api/front/users/username/{0}/albums/{1}/photos"
API_ENDPOINT_VIDEOS = "https://stripchat.com/api/front/v2/users/username/{0}/videos"
API_ENDPOINT_SEARCH = "https://stripchat.com/api/front/v4/models/search/group/username?query={0}&primaryTag={1}&limit=99"

# Site specific constants
LIST_LIMITS = [10, 25, 50, 75, 99]
LIST_LIMIT = LIST_LIMITS[ADDON.getSettingInt('list_limit')]
SORT_BY_OPTIONS = ["stripRanking", "trending"]
SORT_BY_STD = SORT_BY_OPTIONS[ADDON.getSettingInt('sort_by')]
PRIMARY_TAG = "girls"
DEL_THUMBS_ON_STARTUP = ADDON.getSettingBool('del_thumbs_on_startup')

# Threading
MAX_WORKERS = ADDON.getSettingInt('max_workers')

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
SITE_TOOLS = (("Backup Favourites", "tool=fav-backup", "Backup favourites (Set backup location in settings first)."),
              ("Restore Favourites", "tool=fav-restore", "Restore your favourites from backup location."),
              ("Delete Thumbnails", "tool=thumbnails-delete", "Delete cached stripchat related thumbnail files and database entries."),
              ("Update Model IDs", "tool=fav-update", "Update favourites DB (model IDs)."),
              ("Import Keys from File", "tool=import-keys", "Import pkey and pdkey from a text file (format: pkey:pdkey)."))

# Strings
STRINGS = {
    'na' : 'User is not available',
    'last_status' : 'Last status: ',
    'unknown_status' : 'Unkown status: ',
    'not_live' : 'User is not live at the moment',
    'not_found' : 'Account not found. It may have been deleted.',
    'deactivated' : 'This account is deactivated',
    'disabled' : 'This account is disabled',
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
        "fav-backup": sc19.tool_fav_backup,
        "fav-restore": sc19.tool_fav_restore,
        "thumbnails-delete": sc19.tool_thumbnails_delete,
        "fav-update": sc19.tool_fav_update,
        "import-keys": sc19.tool_import_keys
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

def get_profile_data(item):
    data = sc19.get_data_from_page(API_ENDPOINT_MODEL.format(item))
    data = json.loads(data)
    xbmc.log("AVATAR URL: " + data["user"]["user"]["avatarUrl"], 1)
    return data["user"]["user"]["avatarUrl"]

def get_favourites():
    """Get list of favourites from addon's db"""    
    
    # Clean Thumbnails before opening the list
    if DEL_THUMBS_ON_STARTUP:
        sc19.tool_thumbnails_delete_from_db()

    # Connect to favourites db
    db_con = sc19.connect_favourites_db()
    conn = db_con.cursor()
    # Explicitly select both columns so we keep user_id for later use
    conn.execute("SELECT user, user_id FROM favourites")
    res = []
    for row in conn.fetchall():
        username = row[0]
        user_id = row[1] if len(row) > 1 else None
        res.append((username, user_id))
    # Sort by username case-insensitive
    res.sort(key=lambda x: x[0].lower())

    # If no favourites found, notify the user and exit
    if not res:
        xbmcgui.Dialog().ok("Favourites", "No favourites available. Please add some first.")
        xbmcplugin.endOfDirectory(PLUGIN_ID, succeeded=False)
        xbmc.executebuiltin("Container.Update(%s)" % (sys.argv[0],))
        return

    # Settings
    fav_default_icon = ADDON.getSettingBool('fav_default_icon')
    fav_check_online_status = ADDON.getSettingBool('fav_check_online_status')

    # Progress bar
    prg = xbmcgui.DialogProgress()
    prg.create("Scanning favourites", "0 from " + str(len(res)) ) 
    
    # Build kodi listitems for virtual directory
    items = []
    
    # Pre-fetch all user data in parallel
    user_data_dict = {}
    image_availability = {}
    
    if fav_check_online_status:
        # Fetch all user data in parallel
        prg.update(0, "Fetching user data...")
        usernames = [username for username, user_id in res]
        user_data_dict = sc19.fetch_user_data_parallel(usernames, API_ENDPOINT_MODEL, MAX_WORKERS)
    else:
        # Check snapshot availability in parallel (existing behavior)
        timestamp = int(time())
        urls_to_check = []
        
        for username, user_id in res:
            if user_id:
                snap = "https://img.strpst.com/thumbs/{0}/{1}_webp".format(timestamp, user_id)
                urls_to_check.append((username, snap))
        
        if urls_to_check:
            prg.update(0, "Checking snapshot availability...")
            image_availability = sc19.check_images_parallel(urls_to_check, MAX_WORKERS)
    
    # Now build the list items with pre-fetched data
    n = 0
    chunk = 100/len(res)
    i = 0
    
    for item in res:
        username, user_id = item
        
        # Cancel scanning
        if prg.iscanceled():
            break
            
        n += 1
        i += chunk
        prg.update(int(i), "Processing " + str(n) + " from " + str(len(res)) + " ( " + username + " )")
        
        url = sys.argv[0] + '?playactor=' + username
        li = xbmcgui.ListItem(username)
        
        # expose user_id on the item for future use (if available)
        if user_id:
           li.setProperty('sc_user_id', str(user_id))
        vit = li.getVideoInfoTag()

        # Get JSON for model to load avatar, fanart and status
        try:
            if fav_check_online_status:
                # Use pre-fetched data
                data = user_data_dict.get(username)
                
                if data and "user" in data:
                    status = data["user"]["user"]['status']
                    username_display = get_username_string_from_status(username, status)
                    
                    # Show avatar if not live
                    if not status == "public":
                        if fav_default_icon:
                            li.setArt({'icon': get_icon_from_status(status), 'fanart': data["user"]["user"]['previewUrl']})
                        else:
                            li.setArt({'icon': data["user"]["user"]["avatarUrl"], 'fanart': data["user"]["user"]['previewUrl']})
                    else:
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
                else:
                    # Data fetch failed
                    username_display = username + " (n/a)"
                    vit.setPlot('Userdata cannot be retrieved at this point! This may be temporary. Check profile on website, if it still exists.')
            else:
                # Just list names (existing behavior)
                username_display = username
                timestamp = int(time())
                
                if user_id:
                    snap = "https://img.strpst.com/thumbs/{0}/{1}_webp".format(timestamp, user_id)
                    # Use pre-checked result
                    if image_availability.get(username, False):
                        li.setArt({'icon': snap, 'thumb': snap, 'fanart': 'DefaultVideo.png'})
                    else:
                        # Use offline icon if snapshot doesn't exist
                        li.setArt({'icon': get_icon_from_status('off'), 'thumb': get_icon_from_status('off'), 'fanart': 'DefaultVideo.png'})
                else:
                    # No user_id available -> use default icon/thumb and fanart
                    li.setArt({'icon': 'DefaultVideo.png', 'thumb': 'DefaultVideo.png', 'fanart': 'DefaultVideo.png'})
                
        except Exception as e:
            # User data cannot be retrieved
            username_display = username + " (n/a)"
            vit.setPlot('Userdata cannot be retrieved at this point! This may be temporary. Check profile on website, if it still exists.')
            
        li.setLabel(username_display)
        # Set title
        vit.setTitle(username_display)
        # Clear playcount for directory items
        vit.setPlaycount(0)
        # Context menu        
        li.addContextMenuItems(get_ctx_for_cam_item(username, True), True)
        # Append to list
        items.append((url, li, False))

    # Put items to virtual directory listing and set sortings
    xbmcplugin.setContent(int(sys.argv[1]), 'videos')
    xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_LABEL)
    xbmcplugin.addDirectoryItems(PLUGIN_ID, items)
    xbmcplugin.endOfDirectory(PLUGIN_ID)
    # Close DB connection
    try:
        db_con.close()
    except Exception:
        pass

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
        data = sc19.get_data_from_page(url)
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
            vit.setSortTitle(str(999).zfill(2) + " - " + "Next Page")
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
        data = sc19.get_data_from_page(url)
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
        data = sc19.get_data_from_page(API_ENDPOINT_ALBUMS.format(actor))
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
            vit = li.getVideoInfoTag()
            vit.setPlot("Photos: " + str(item['photosCount']))

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
        data = sc19.get_data_from_page(API_ENDPOINT_ALBUM.format(actor,id))
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
        data = sc19.get_data_from_page(API_ENDPOINT_VIDEOS.format(actor))
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
                    url = sys.argv[0] + '?playurl=' + item['videoUrl']  + "&title=" + actor + " - " + item['title']
                    items.append((url, li, False))
                
            else:
                if item['accessMode'] == 'free':
                    li.setLabel(item['title'])
                    vit.setPlot("Duration in seconds: " + str(item['duration']))                    
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
        data = sc19.get_data_from_page(API_ENDPOINT_ALBUM.format(actor,id))
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
    data = sc19.get_data_from_page(url)
    return data

def play_actor(actor, genre="Stripchat"):
    """Get playlist for actor/username and add m3u8 to kodi's playlist"""
    
    global _proxy_instance
    
    # Try to play actor
    try:
        # Fetch and store HTML
        url = API_ENDPOINT_MODEL.format(actor)       
        data = sc19.get_data_from_page(url)
        data = json.loads(data)
        
        if not data or "user" not in data:
            xbmcgui.Dialog().ok("Error", "Could not retrieve data for this user. Temporarily not available or may not exist anymore.")
            return
        
        # Check for deactivated account
        if not data["cam"]:
            xbmcgui.Dialog().ok("Info", STRINGS['disabled'])
            return
        
        bio = ""
        
        img = data["user"]["user"]["avatarUrl"]
        if not data["cam"]["topic"] == "":
            bio = "Topic: " + data["cam"]["topic"] + "\n"

        status = data["user"]["user"]["status"]
        isLive = data["user"]["user"]["isLive"]
            
        # Not live (public)
        if isLive == False:
            statusts = data["user"]["user"]["statusChangedAt"]
            xbmcgui.Dialog().ok(STRINGS['not_live'], "Status: " + USER_STATES_NICE["off"] + "\nLast broadcast: " + sc19.format_timestamp_relative(statusts))
            xbmc.executebuiltin('Dialog.Close(busydialog)')
            return
        # All other states
        if not status == "public":
            if status in USER_STATES_NICE:
                xbmcgui.Dialog().ok(STRINGS['na'], STRINGS['last_status'] + USER_STATES_NICE[status])
            else:
                xbmcgui.Dialog().ok(STRINGS['na'], STRINGS['unknown_status'] + status)
            xbmc.executebuiltin('Dialog.Close(busydialog)')
            return
        
        # Check proxy settings
        use_external_proxy = ADDON.getSettingBool('use_external_proxy')
        if use_external_proxy:
            external_ip = ADDON.getSetting('external_proxy_ip')
            external_port = ADDON.getSettingInt('external_proxy_port')
            if not external_ip:
                xbmcgui.Dialog().ok("Proxy Error", "External proxy IP is not set.")
                xbmc.executebuiltin('Dialog.Close(busydialog)')
                return
            pl = f"http://{external_ip}:{external_port}/{actor}"
            xbmc.log(ADDON_SHORTNAME + ": Using external proxy: " + pl, 1)
        else:
            # Always use internal proxy
            proxy_port = ADDON.getSettingInt('proxy_port') or 8099
            xbmc.log(ADDON_SHORTNAME + ": Proxy port: " + str(proxy_port), 1)
            
            # Check if port is already in use (proxy running)
            if not is_port_in_use(proxy_port):
                try:
                    xbmc.log(ADDON_SHORTNAME + ": Starting proxy", 1)
                    _proxy_instance = proxy_module.get_proxy(port=proxy_port)
                    xbmc.log(ADDON_SHORTNAME + ": Proxy started successfully", 1)
                except Exception as e:
                    xbmc.log(ADDON_SHORTNAME + ": Failed to start proxy: " + str(e), xbmc.LOGERROR)
                    xbmcgui.Dialog().ok("Proxy Error", f"Failed to start proxy. Cannot play stream.\nError: {str(e)}")
                    xbmc.executebuiltin('Dialog.Close(busydialog)')
                    return
            else:
                xbmc.log(ADDON_SHORTNAME + ": Proxy already running on port " + str(proxy_port) + ", reusing it", 1)
            
            # Use proxy URL
            pl = f"http://127.0.0.1:{proxy_port}/{actor}"
            xbmc.log(ADDON_SHORTNAME + ": Constructed URL: " + pl, 1)

        # Bio stats
        if not data["cam"]["goal"] == None:
            bio += "Goal: " + data["cam"]["goal"]["description"] + " [" + str(data["cam"]["goal"]["spent"]) + "/" + str(data["cam"]["goal"]["goal"]) + "]\n"

        name_to_use = data["user"]["user"]["name"] if data["user"]["user"]["name"] else data["user"]["user"]["username"]
        bio += "Name: " + name_to_use + "\n"
        viewers = get_viewers_count(actor)
        bio += "Viewers: " + str(viewers) + "\n"
        bio += get_prices_string_for_plot(data["user"]["user"]) + "\n"
        if not data["user"]["user"]["description"] == "":
            bio += "Description: " + data["user"]["user"]["description"] + "\n"

        # Build kodi listitem for playlist
        li = xbmcgui.ListItem(actor)
        vit = li.getVideoInfoTag()
        vit.setGenres([genre])
        vit.setPlot(bio)
        li.setArt({'icon': img, 'thumb': img})

        li.setMimeType('application/vnd.apple.mpegurl')
        
        # Get stream player setting
        stream_player = xbmcaddon.Addon().getSetting('stream_player')
        # Set inputstream addon based on setting
        if stream_player == "0":
            xbmc.log(ADDON_SHORTNAME + ": " + "Using default stream player", 1)
        if stream_player == "1":
            li.setProperty('inputstream', 'inputstream.ffmpegdirect')
            li.setProperty('inputstream.ffmpegdirect.is_realtime_stream', 'true')  # Indicate live stream
            if ADDON.getSettingBool('use_ffmpeg_timeshift'):
                li.setProperty('inputstream.ffmpegdirect.stream_mode', 'timeshift')  # Enable timeshift
            xbmc.log(ADDON_SHORTNAME + ": " + "Using InputStream FFmpegDirect", 1)

        # Play stream
        xbmc.Player().play(pl, li)
        xbmc.executebuiltin('Dialog.Close(busydialog)')
        xbmcplugin.setResolvedUrl(PLUGIN_ID, True, li)
        return
    
    except Exception as e:
        xbmc.log(ADDON_SHORTNAME + ": Exception in play_actor: " + str(e), xbmc.LOGERROR)
        xbmcgui.Dialog().notification("Error", "Something went wrong: " + str(e), "", 3000, False)
        xbmc.executebuiltin('Dialog.Close(busydialog)')
        return 

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
            data = sc19.get_data_from_page(url)
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

            # Clear playcount for directory items
            vit.setPlaycount(0)
            
            url = sys.argv[0] + '?playactor=' + s
            xbmcplugin.setContent(int(sys.argv[1]), 'videos')
            xbmcplugin.addDirectoryItems(PLUGIN_ID, [(url, li, False)])
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
        data = sc19.get_data_from_page(url)
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
    if item.get('isNew', False):
        tags.append("NEW")
    if item.get('isHd', False) == True:
        tags.append("HD")
    if item.get('isVr', False) == True:
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
    if item.get('doPrivate', False) and item.get('privateRate') is not None:
        s += str(item['privateRate']) + " (Pvt) "
        s2 = ""
    if item.get('doP2p', False) and item.get('p2pRate') is not None:
        s += str(item['p2pRate']) + " (P2P) "
        s2 = ""
    if item.get('doSpy', False) and item.get('spyRate') is not None:
        s += str(item['spyRate']) + " (Spy)"
        s2 = ""
    return s + s2

def get_cam_infos_as_items(cams):
    # Clean Thumbnails before opening the list
    if DEL_THUMBS_ON_STARTUP:
        sc19.tool_thumbnails_delete_from_db()
        
    # Build kodi list items for virtual directory
    items = []
    id = 0
    
    for item in cams['models']:
        if not item['status'] == "offfff":
            username = item['username']
            
            icon = "https://img.strpst.com/thumbs/{0}/{1}_webp".format(item['snapshotTimestamp'],item['id'])
            url = sys.argv[0] + '?playactor=' + username
            li = xbmcgui.ListItem(username)
            vit = li.getVideoInfoTag()
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
            # Set title
            vit.setTitle(username)
            # Clear playcount for directory items
            vit.setPlaycount(0)
            # Context menu
            li.addContextMenuItems(get_ctx_for_cam_item(username), True)
            items.append((url, li, False))
    return items

def get_ctx_for_cam_item(username, remove=False):
    # Context menu
    commands = []
    # Favourites
    if remove:
        commands.append(('[COLOR orange]' + ADDON_SHORTNAME + ' - Remove favourite [/COLOR]','RunScript(' + ADDON_NAME + ', ' + str(sys.argv[1]) + ', ctx_remove_favourite, ' + username + ')'))
    else:
        commands.append(('[COLOR orange]' + ADDON_SHORTNAME + ' - Add as favourite [/COLOR]','RunScript(' + ADDON_NAME + ', ' + str(sys.argv[1]) + ', ctx_add_favourite, ' + username + ')'))
    commands.append(('[COLOR orange]' + ADDON_SHORTNAME + ' - Refresh thumbnails [/COLOR]','RunScript(' + ADDON_NAME + ', ' + str(sys.argv[1]) + ', ctx_thumbnails_delete)'))
    # Profile info
    commands.append(('Show profile albums',"Container.Update(%s?%s)" % ( sys.argv[0],  "getalbums=" + username)))
    commands.append(('Show profile videos',"Container.Update(%s?%s)" % ( sys.argv[0],  "getvideos=" + username)))
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

def is_port_in_use(port):
    """Check if a port is in use by attempting to connect to it."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)  # Short timeout to avoid hanging
            result = s.connect_ex(('127.0.0.1', port))
            return result == 0  # 0 means connection successful (port in use)
    except Exception as e:
        xbmc.log(f"{ADDON_SHORTNAME}: Error checking port {port}: {str(e)}", xbmc.LOGERROR)
        return False  # Assume not in use if check fails

if __name__ == "__main__":
    evaluate_request()
