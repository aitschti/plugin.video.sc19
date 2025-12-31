import sys
import sqlite3
import xbmc
import xbmcaddon
import utils as sc19

# Common config constants (avilable in all modules)
ADDON_NAME = "plugin.video.sc19"
ADDON_SHORTNAME = "SC19"
ADDON = xbmcaddon.Addon(id=ADDON_NAME)

def ctx_add_favourite(user, user_id=None):
    "Adds username to database. Remove first if already exists. user_id is optional."

    db_con = sc19.connect_favourites_db()
    c = db_con.cursor()
    c.execute(sc19.Q_DEL_FAVOURITE, (user,))
    db_con.commit()
    # If user_id not passed, try to resolve it via API (best-effort)
    if not user_id:
        try:
            model_id, err = sc19.get_model_id_for_user(user)
            if model_id:
                user_id = model_id
        except Exception as e:
            xbmc.log(ADDON_NAME + f": Failed to lookup user_id for {user}: {e}", xbmc.LOGDEBUG)
    try:
        # explicit column names: works with old and new schema (user_id may be NULL)
        c.execute(sc19.Q_ADD_FAVOURITE, (user, user_id))
        xbmc.log(ADDON_NAME + f": Added favourite {user} with user_id {user_id}", 1)
        db_con.commit()
    except sqlite3.IntegrityError:
        pass


def ctx_remove_favourite(user):
    "Removes username from database."

    db_con = sc19.connect_favourites_db()
    c = db_con.cursor()
    try:
        c.execute(sc19.Q_DEL_FAVOURITE, (user,))
        db_con.commit()
    except sqlite3.IntegrityError:
        pass

if sys.argv[2]:
    cmd = sys.argv[2]
    if cmd == "ctx_add_favourite":
        ctx_add_favourite(sys.argv[3])
    if cmd == "ctx_remove_favourite":
        ctx_remove_favourite(sys.argv[3])
        xbmc.executebuiltin("Container.Refresh")
    if cmd == "ctx_thumbnails_delete":
        sc19.tool_thumbnails_delete_from_db()
        xbmc.executebuiltin("Container.Refresh")