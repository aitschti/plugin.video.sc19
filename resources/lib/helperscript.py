import sys
import os
import sqlite3
import xbmc
import xbmcvfs
import xbmcgui
import xbmcplugin

ADDON_NAME = "plugin.video.sc19"
DB_FAVOURITES_FILE = "favourites-sc.db"
DB_FAVOURITES = xbmcvfs.translatePath("special://profile/addon_data/%s/%s" % (ADDON_NAME, DB_FAVOURITES_FILE))
DB_TEXTURES = xbmcvfs.translatePath("special://userdata/Database/Textures13.db")
PATH_THUMBS = xbmcvfs.translatePath("special://userdata/Thumbnails/")

# Queries
Q_THUMBNAILS = "SELECT url,cachedurl FROM texture WHERE url LIKE '%.strpst.com%'"
Q_DEL_THUMBNAILS = "DELETE FROM texture WHERE url LIKE '%.strpst.com%'"

xbmc.log(ADDON_NAME + ": " + str(sys.argv), 1)
#xbmcgui.Dialog().ok("OFFLINE", "The user is currently offline. Please try again later.")

def clean_database():
    conn = sqlite3.connect(xbmcvfs.translatePath("special://database/Textures13.db"))
    try:
        with conn:
            list = conn.execute("SELECT id, cachedurl FROM texture WHERE url LIKE '%%%s%%';" % ".strpst.com")
            for row in list:
                conn.execute("DELETE FROM sizes WHERE idtexture LIKE '%s';" % row[0])
                try:
                    os.remove(xbmcvfs.translatePath("special://thumbnails/" + row[1]))
                except:
                    pass
            conn.execute("DELETE FROM texture WHERE url LIKE '%%%s%%';" % ".strpst.com")
            xbmcgui.Dialog().notification('Done', 'Database and thumbnails cleaned up!')
    except:
        pass


def refresh_container():
    """Refresh container and remove cached thumbnails"""
    
    # Clean up thumbnails from database on main menu
    conn = sqlite3.connect(xbmcvfs.translatePath(
        "special://database/Textures13.db"))
    try:
        with conn:
            conn.execute("DELETE FROM texture WHERE url LIKE '%img.strpst.com%';")
            xbmc.log(ADDON_NAME + ": Cleaned up thumnails!", 1)
    except:
        pass

def connect_favourites_db():
    "Connect to favourites database and create one, if it does not exist." 
    
    db_con = sqlite3.connect(DB_FAVOURITES)
    c = db_con.cursor()
    try:
        c.execute("SELECT * FROM favourites;")
    except sqlite3.OperationalError:
        c.executescript("CREATE TABLE favourites (user primary key);")
    return db_con


def add_favourite(user):
    "Adds username to database. Remove first if already exists."

    db_con = connect_favourites_db()
    c = db_con.cursor()
    c.execute("DELETE FROM favourites WHERE user = ?", (user,))
    db_con.commit()
    try:
        c.execute("INSERT INTO favourites VALUES(?)", (user,))
        db_con.commit()
    except sqlite3.IntegrityError:
        pass


def remove_favourite(user):
    "Removes username from database."

    db_con = connect_favourites_db()
    c = db_con.cursor()
    try:
        c.execute("DELETE FROM favourites WHERE user = ?", (user,))
        db_con.commit()
    except sqlite3.IntegrityError:
        pass


def ctx_thumbnails_delete():   
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
    # Delete entries from db
    cur_del.execute(Q_DEL_THUMBNAILS)
    conn.commit()
    # Close connection
    conn.close()
    # Return number of entries found and log
    xbmc.log("Deleted %s thumbnail files and database entries" % (str(rc)),1)
    return rc


if sys.argv[2]:
    cmd = sys.argv[2]
    if cmd == "refresh":
        refresh_container()
    if cmd == "add_favourite":
        add_favourite(sys.argv[3])
    if cmd == "remove_favourite":
        remove_favourite(sys.argv[3])
        xbmc.executebuiltin("Container.Refresh")
    if cmd == "ctx_thumbnails_delete":
        ctx_thumbnails_delete()
        xbmc.executebuiltin("Container.Refresh")