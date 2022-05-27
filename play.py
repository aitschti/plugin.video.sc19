import os
import sys
import json
import re
import urllib.request
import urllib.parse
import urllib.error


unicodeData= u"{\u0022viewer_uid\u0022: null, \u0022broadcaster_enable_asp\u0022: false, \u0022is_age_verified\u0022: true, \u0022age\u0022: 26, \u0022room_status\u0022: \u0022public\u0022, \u0022num_viewers\u0022: 56, \u0022wschat_host\u0022: \u0022https://chatw\u002D38.stream.highwebmedia.com/ws\u0022, \u0022viewer_username\u0022: \u0022AnonymousUser\u0022, \u0022viewer_gender\u0022: \u0022m\u0022, \u0022allow_anonymous_tipping\u0022: false, \u0022chat_username\u0022: \u0022__anonymous__DTFcrEvl\u0022, \u0022chat_password\u0022: \u0022{\u005C\u0022username\u005C\u0022:\u005C\u0022__anonymous__DTFcrEvl\u005C\u0022,\u005C\u0022room\u005C\u0022:\u005C\u0022simone_gray\u005C\u0022,\u005C\u0022expire\u005C\u0022:1649620170,\u005C\u0022org\u005C\u0022:\u005C\u0022A\u005C\u0022,\u005C\u0022sig\u005C\u0022:\u005C\u002255fc38da40c1bc7eb428fc678c1b2ca11006d339b9259e639ca12507ca3d7399\u005C\u0022}\u0022, \u0022broadcaster_username\u0022: \u0022simone_gray\u0022, \u0022room_pass\u0022: \u00221800e001e379b7d30abb1421ea7ef94f367d44b1128bf8864af5d9223a43191b\u0022, \u0022chat_rules\u0022: \u0022\u0022, \u0022room_title\u0022: \u0022Ride a Dildo #skinny #young #natural #anal #feet [666 tokens left]\u0022, \u0022room_uid\u0022: \u0022TEBW2XV\u0022, \u0022broadcaster_uid\u0022: \u0022TEBW2XV\u0022, \u0022broadcaster_gender\u0022: \u0022female\u0022, \u0022apps_running\u0022: \u0022[[\u005C\u0022Tip Multi\u002DGoal\u005C\u0022,\u005C\u0022\u005C\u005C/apps\u005C\u005C/app_details\u005C\u005C/tip\u002Dmulti\u002Dgoal\u005C\u005C/?slot\u003D0\u005C\u0022],[\u005C\u0022Tip Menu 50\u005C\u0022,\u005C\u0022\u005C\u005C/apps\u005C\u005C/app_details\u005C\u005C/tip\u002Dmenu\u002D50\u005C\u005C/?slot\u003D2\u005C\u0022],[\u005C\u0022My Secret Show\u005C\u0022,\u005C\u0022\u005C\u005C/apps\u005C\u005C/app_details\u005C\u005C/my\u002Dsecret\u002Dshow\u005C\u005C/?slot\u003D3\u005C\u0022],[\u005C\u0022Roll The Dice\u005C\u0022,\u005C\u0022\u005C\u005C/apps\u005C\u005C/app_details\u005C\u005C/roll\u002Dthe\u002Ddice\u002D5\u005C\u005C/?slot\u003D4\u005C\u0022],[\u005C\u0022STAT BOT\u005C\u0022,\u005C\u0022\u005C\u005C/apps\u005C\u005C/app_details\u005C\u005C/stat\u002Dbot\u005C\u005C/?slot\u003D5\u005C\u0022]]\u0022, \u0022hls_source\u0022: \u0022https://edge9\u002Dhel.live.mmcdn.com/live\u002Dhls/amlst:simone_gray\u002Dsd\u002D8f59e79986e75f60e811773a0ac651c64de0187a575f64a4290b61c66a6caa30_trns_h264/playlist.m3u8\u0022, \u0022dismissible_messages\u0022: [], \u0022edge_auth\u0022: \u0022{\u005C\u0022username\u005C\u0022:\u005C\u0022__anonymous__DTFcrEvl\u005C\u0022,\u005C\u0022room\u005C\u0022:\u005C\u0022simone_gray\u005C\u0022,\u005C\u0022expire\u005C\u0022:1649620170,\u005C\u0022org\u005C\u0022:\u005C\u0022A\u005C\u0022,\u005C\u0022sig\u005C\u0022:\u005C\u002255fc38da40c1bc7eb428fc678c1b2ca11006d339b9259e639ca12507ca3d7399\u005C\u0022}\u0022, \u0022is_widescreen\u0022: true, \u0022allow_private_shows\u0022: true, \u0022private_show_price\u0022: 42, \u0022private_min_minutes\u0022: 10, \u0022allow_show_recordings\u0022: true, \u0022spy_private_show_price\u0022: 12, \u0022private_show_id\u0022: \u0022\u0022, \u0022low_satisfaction_score\u0022: false, \u0022hidden_message\u0022: \u0022\u0022, \u0022following\u0022: false, \u0022follow_notification_frequency\u0022: \u0022\u0022, \u0022is_moderator\u0022: false, \u0022recommender_hmac\u0022: \u00223897e54c3d7ef4e26ff2ba8189048fbfa617cbedb18d45ce2a7c1a2cbcedfc7a\u0022, \u0022chat_settings\u0022: {\u0022font_size\u0022: \u00229pt\u0022, \u0022show_emoticons\u0022: true, \u0022emoticon_autocomplete_delay\u0022: \u00220\u0022, \u0022sort_users_key\u0022: \u0022a\u0022, \u0022room_entry_for\u0022: \u0022org\u0022, \u0022room_leave_for\u0022: \u0022org\u0022, \u0022silence_broadcasters\u0022: \u0022false\u0022, \u0022ignored_users\u0022: \u0022\u0022, \u0022allowed_chat\u0022: \u0022all\u0022, \u0022v_tip_vol\u0022: \u002250\u0022, \u0022b_tip_vol\u0022: \u002210\u0022, \u0022max_pm_age\u0022: 720, \u0022font_color\u0022: \u0022\u0022, \u0022font_family\u0022: \u0022default\u0022, \u0022highest_token_color\u0022: \u0022darkpurple\u0022, \u0022mod_expire\u0022: 1}, \u0022broadcaster_on_new_chat\u0022: false, \u0022token_balance\u0022: 0, \u0022is_supporter\u0022: false, \u0022needs_supporter_to_pm\u0022: true, \u0022server_name\u0022: \u0022www3\u002Dext\u002Dnxvw\u0022, \u0022num_followed\u0022: 0, \u0022num_followed_online\u0022: 0, \u0022has_studio\u0022: false, \u0022is_mobile\u0022: false, \u0022ignored_emoticons\u0022: [], \u0022tfa_enabled\u0022: false, \u0022satisfaction_score\u0022: {\u0022percent\u0022: 100, \u0022up_votes\u0022: 29, \u0022down_votes\u0022: 0, \u0022max\u0022: 49563533}, \u0022hide_satisfaction_score\u0022: false, \u0022tips_in_past_24_hours\u0022: 0, \u0022last_vote_in_past_24_hours\u0022: null, \u0022last_vote_in_past_90_days_down\u0022: false, \u0022show_mobile_site_banner_link\u0022: false, \u0022exploring_hashtag\u0022: \u0022\u0022, \u0022source_name\u0022: \u0022un\u0022, \u0022performer_has_fanclub\u0022: false, \u0022opt_out\u0022: false, \u0022fan_club_is_member\u0022: false, \u0022is_testbed\u0022: false, \u0022asp_auth_url\u0022: \u0022/asp/devportal/\u0022, \u0022browser_id\u0022: \u0022ceaa67f1\u002D1eae\u002D46fc\u002Db3d1\u002D690e713f6a4b\u0022, \u0022offline_room_chat_pm_enabled\u0022: false, \u0022fan_club_paid_with_tokens\u0022: false, \u0022quality\u0022: {\u0022quality\u0022: \u0022\u0022, \u0022rate\u0022: 0, \u0022stopped\u0022: false}}"
s2         = u"{\u0022viewer_uid\u0022: null, \u0022broadcaster_enable_asp\u0022: false, \u0022is_age_verified\u0022: true, \u0022age\u0022: null, \u0022room_status\u0022: \u0022public\u0022, \u0022num_viewers\u0022: 9031, \u0022wschat_host\u0022: \u0022https://chatw\u002D64.stream.highwebmedia.com/ws\u0022, \u0022viewer_username\u0022: \u0022AnonymousUser\u0022, \u0022viewer_gender\u0022: \u0022m\u0022, \u0022allow_anonymous_tipping\u0022: false, \u0022chat_username\u0022: \u0022__anonymous__gtrEM4\u0022, \u0022chat_password\u0022: \u0022{\u005C\u0022username\u005C\u0022:\u005C\u0022__anonymous__gtrEM4\u005C\u0022,\u005C\u0022room\u005C\u0022:\u005C\u0022ms_seductive\u005C\u0022,\u005C\u0022expire\u005C\u0022:1649623688,\u005C\u0022org\u005C\u0022:\u005C\u0022A\u005C\u0022,\u005C\u0022sig\u005C\u0022:\u005C\u002215f9098a220d228ba625cb1a7928f2aa81464d30af119ffa10c3ea58e49c240c\u005C\u0022}\u0022, \u0022broadcaster_username\u0022: \u0022ms_seductive\u0022, \u0022room_pass\u0022: \u0022e4ba1a8e08a85f5feb96c00f2ccaf0ecd04d89576af2d13b23426dcc6106e5d5\u0022, \u0022chat_rules\u0022: \u0022\u0022, \u0022room_title\u0022: \u002280 tkns win prize | huge vibe 50, 70, 310, 710 | tipmenu availaible\u0022, \u0022room_uid\u0022: \u0022LHVYBV5\u0022, \u0022broadcaster_uid\u0022: \u0022LHVYBV5\u0022, \u0022broadcaster_gender\u0022: \u0022female\u0022, \u0022apps_running\u0022: \u0022[[\u005C\u0022All In One Bot \u002D 2048 edition\u005C\u0022,\u005C\u0022\u005C\u005C/apps\u005C\u005C/app_details\u005C\u005C/all\u002Din\u002Done\u002Dbot\u002D2048\u002Dedition\u005C\u005C/?slot\u003D1\u005C\u0022],[\u005C\u0022lalabot\u005C\u0022,\u005C\u0022\u005C\u005C/apps\u005C\u005C/app_details\u005C\u005C/lalabot\u005C\u005C/?slot\u003D2\u005C\u0022],[\u005C\u0022milanasgamebot\u005C\u0022,\u005C\u0022\u005C\u005C/apps\u005C\u005C/app_details\u005C\u005C/milanasgamebot\u005C\u005C/?slot\u003D3\u005C\u0022],[\u005C\u0022Make it Rain Magic\u005C\u0022,\u005C\u0022\u005C\u005C/apps\u005C\u005C/app_details\u005C\u005C/make\u002Dit\u002Drain\u002Dmagic\u005C\u005C/?slot\u003D4\u005C\u0022]]\u0022, \u0022hls_source\u0022: \u0022https://edge16\u002Dalb.stream.highwebmedia.com/live\u002Dhls/amlst:ms_seductive\u002Dsd\u002D105b1115ce916bbf38c34c39986a21d0c0ec51fecebd94da2c0a207af140fd00_trns_h264/playlist.m3u8\u0022, \u0022dismissible_messages\u0022: [], \u0022edge_auth\u0022: \u0022{\u005C\u0022username\u005C\u0022:\u005C\u0022__anonymous__gtrEM4\u005C\u0022,\u005C\u0022room\u005C\u0022:\u005C\u0022ms_seductive\u005C\u0022,\u005C\u0022expire\u005C\u0022:1649623688,\u005C\u0022org\u005C\u0022:\u005C\u0022A\u005C\u0022,\u005C\u0022sig\u005C\u0022:\u005C\u002215f9098a220d228ba625cb1a7928f2aa81464d30af119ffa10c3ea58e49c240c\u005C\u0022}\u0022, \u0022is_widescreen\u0022: true, \u0022allow_private_shows\u0022: false, \u0022private_show_price\u0022: 240, \u0022private_min_minutes\u0022: 10, \u0022allow_show_recordings\u0022: false, \u0022spy_private_show_price\u0022: 0, \u0022private_show_id\u0022: \u0022\u0022, \u0022low_satisfaction_score\u0022: false, \u0022hidden_message\u0022: \u0022\u0022, \u0022following\u0022: false, \u0022follow_notification_frequency\u0022: \u0022\u0022, \u0022is_moderator\u0022: false, \u0022recommender_hmac\u0022: \u0022b6620de95b4224fc3ab72655eb795591d49890ac72d2d9ce6ad3c071de8719c8\u0022, \u0022chat_settings\u0022: {\u0022font_size\u0022: \u00229pt\u0022, \u0022show_emoticons\u0022: true, \u0022emoticon_autocomplete_delay\u0022: \u00220\u0022, \u0022sort_users_key\u0022: \u0022a\u0022, \u0022room_entry_for\u0022: \u0022org\u0022, \u0022room_leave_for\u0022: \u0022org\u0022, \u0022silence_broadcasters\u0022: \u0022false\u0022, \u0022ignored_users\u0022: \u0022\u0022, \u0022allowed_chat\u0022: \u0022all\u0022, \u0022v_tip_vol\u0022: \u002250\u0022, \u0022b_tip_vol\u0022: \u002210\u0022, \u0022max_pm_age\u0022: 720, \u0022font_color\u0022: \u0022\u0022, \u0022font_family\u0022: \u0022default\u0022, \u0022highest_token_color\u0022: \u0022darkpurple\u0022, \u0022mod_expire\u0022: 1}, \u0022broadcaster_on_new_chat\u0022: false, \u0022token_balance\u0022: 0, \u0022is_supporter\u0022: false, \u0022needs_supporter_to_pm\u0022: true, \u0022server_name\u0022: \u0022www3\u002Dext\u002D70b3\u0022, \u0022num_followed\u0022: 0, \u0022num_followed_online\u0022: 0, \u0022has_studio\u0022: false, \u0022is_mobile\u0022: false, \u0022ignored_emoticons\u0022: [], \u0022tfa_enabled\u0022: false, \u0022satisfaction_score\u0022: {}, \u0022hide_satisfaction_score\u0022: true, \u0022tips_in_past_24_hours\u0022: 0, \u0022last_vote_in_past_24_hours\u0022: null, \u0022last_vote_in_past_90_days_down\u0022: false, \u0022show_mobile_site_banner_link\u0022: false, \u0022exploring_hashtag\u0022: \u0022\u0022, \u0022source_name\u0022: \u0022un\u0022, \u0022performer_has_fanclub\u0022: true, \u0022opt_out\u0022: false, \u0022fan_club_is_member\u0022: false, \u0022is_testbed\u0022: false, \u0022asp_auth_url\u0022: \u0022/asp/devportal/\u0022, \u0022browser_id\u0022: \u002209aec8e5\u002D58cf\u002D458e\u002Dad20\u002D7c1d4778aeea\u0022, \u0022offline_room_chat_pm_enabled\u0022: false, \u0022fan_club_paid_with_tokens\u0022: false, \u0022quality\u0022: {\u0022quality\u0022: \u0022\u0022, \u0022rate\u0022: 0, \u0022stopped\u0022: false}}"
#print("unicode Data is ", unicodeData)

#encodedUnicode = json.dumps(unicodeData, ensure_ascii=False) # use dump() method to write it in file
#print("JSON character encoding by setting ensure_ascii=False", encodedUnicode)

#print("Decoding JSON", json.loads(unicodeData))


BASE_DIR = os.path.dirname(__file__)
SITE_URL = "https://stripchat.com"
SITE_REFFERER = "https://stripchat.com"
SITE_ORIGIN = "https://stripchat.com"
SITE_ACCEPT = "text/html"

API_ENDPOINT_MODELS = "https://stripchat.com/api/front/models"
API_ENDPOINT_MODELS_FILTER = "https://stripchat.com/api/front/models?&limit={0}&offset={1}&primaryTag={2}&filterGroupTags=[[\"{3}\"]]&sortBy={4}"
API_ENDPOINT_MODEL  = "https://stripchat.com/api/front/v2/models/username/{0}/cam"
LIST_LIMIT = 60

# Tags Api
# https://stripchat.com/api/front/models/liveTags?primaryTag=girls

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36'
USER_AGENT2 = 'Mozilla/5.0 (iPad; CPU OS 8_1 like Mac OS X) AppleWebKit/600.1.4 (KHTML, like Gecko) Version/8.0 Mobile/12B410 Safari/600.1.4'
USER_AGENT3 = 'User-Agent=Mozilla/5.0 (iPad; CPU OS 8_1 like Mac OS X) AppleWebKit/600.1.4 (KHTML, like Gecko) Version/8.0 Mobile/12B410 Safari/600.1.4'


# Pattern matchings for HTML scraping
PAT_PLAYLIST = rb"(http.*?://.*?.stream.highwebmedia.com.*?m3u8)"
PAT_PLAYLIST2 = rb"\"hls_source\": \"(http.*?://.*?.stream.highwebmedia.com.*?m3u8)"
PAT_ACTOR_TOPIC = rb'og:description" content="(.*?)" />'
PAT_ACTOR_THUMB = rb'og:image\" content=\"(.*)\?[0-9]'
PAT_ACTOR_LIST = rb'<li class=\"room_list_room\"[\s\S]*?<a href=\"\/(.*?)\/\"[\s\S]*?<img src=\"(.*?)\S\d{10}\"'
PAT_ACTOR_LIST2 = rb'<li class=\"room_list_room\"[\s\S]*?<a href=\"\/(.*?)\/\"[\s\S]*?<img src=\"(.*?)\S\d{10}\"[\s\S]*?<li title=\"(.*?)">[\s\S]*?\"cams\">(.*)<'
PAT_ACTOR_LIST3 = rb'<li class=\"room_list_room\"[\s\S]*?data-room=\"(.*?)\"[\s\S]*?<img src=\"(.*?)\S\d{10}\"[\s\S]*?thumbnail_label[\s\S]*?\">(.*)<\/[\s\S]*?class=\"age[\s\S]*?\">(.*)<\/span[\s\S]*?<li title=\"(.*?)\">[\s\S]*?class=\"location[\s\S]*?\">(.*)<\/li>[\s\S]*?\"cams\">(.*)<'
PAT_ACTOR_BIO = rb'<div class="attribute">\n[\s\S]*?<div class="label">(.*?)<[\s\S]*?data">(.*?)<'
PAT_TAG_LIST = rb'<div class="tag_row">[\s\S]*?href=\"(.*?)\" title=\"(.*?)\"[\s\S]*?\"viewers\">(.*?)<[\s\S]*?\"rooms\">(.*?)<'
PAT_PAGINATION = rb'endless_page_link[\s\S]*?data-floating[\s\S]*?>([\d*][^a-z]?)<\/a'
PAT_ACTOR_LIST_CAT = r'<div class=\"model-list-item\"[\s\S]*?><a[\s\S]*?href=\"/(.*?)\">[\s\S]*?</div>'
PAT_ACTOR_LIST_CAT2 = r'\"modelsOnline\":\s*\{\s*\"models\":?(.*),\s*\"filteredCount\"'
PAT_ACTOR_LIST_CAT3 = r'\"modelsOnline\":\s*\{\s*\"models\":?(.*),\s*\"filteredCount\":(\d*),?\"'

def get_site_page(page):
    """Fetch HTML data from site"""

    url = "%s/%s" % (SITE_URL, page)
    req = urllib.request.Request(url)
    req.add_header('Referer', SITE_REFFERER)
    req.add_header('Origin', SITE_ORIGIN)
    req.add_header('User-Agent', USER_AGENT)
    
    return urllib.request.urlopen(req).read()

def get_site_page_full(page):
    """Fetch HTML data from site"""

    req = urllib.request.Request(page)
    #req.add_header('Referer', SITE_REFFERER)
    #req.add_header('Origin', SITE_ORIGIN)
    req.add_header('User-Agent', USER_AGENT)
    req.add_header('Accept', SITE_ACCEPT)
    
    return urllib.request.urlopen(req).read()

def get_site_page_file(page):
    """Fetch HTML data from site"""

    url = "%s/%s" % (SITE_URL, page)
    req = urllib.request.Request(url)
    req.add_header('Referer', SITE_REFFERER)
    req.add_header('Origin', SITE_ORIGIN)
    req.add_header('User-Agent', USER_AGENT)
    
    return urllib.request.urlopen(req)


# GET model info: https://stripchat.com/api/front/v2/models/username/{1}/cam
# server = "https://b-{0}.strpst.com/hls/{1}/master_{1}.m3u8".format(data["cam"]["viewServers"]["flashphoner-hls"],data["cam"]["streamName"])
# server0 = "https://b-{0}.strpst.com/hls/{1}/{1}.m3u8".format(data["cam"]["viewServers"]["flashphoner-hls"],data["cam"]["streamName"])

# api_call = "https://stripchat.com/api/front/v2/models/username/{0}/cam".format(username)

# https://go.stripchat.com/api/models Random 10 Models in json format

# status values: off, groupShow, public, virtualPrivate

# cam->isCamAvailable false bei offline

#target = 'api/front/v2/models/username/Harpi_Tai/cam'
#target = 'api/front/v2/models/username/Magic_eyes/cam'
target = 'api/front/v2/models/username/ScarlettHills/cam'

target2 = "https://stripchat.com/girls/new"

target3 = "https://stripchat.com/api/front/models"

filter = API_ENDPOINT_MODELS_FILTER.format(LIST_LIMIT, 0, 'girls', 'autoTagVr', 'trending')

# primaryTag: girls, couples, men, trans
# filterGroupTags specials: "autoTagNew", "pornStar", "autoTagVr", "fetishes", "autoTagRecordablePublic"
# filterGroupTags age: "ageTeen", "tagMenTwinks", "ageYoung", "ageMilf", "ageDaddies", "ageMature", "ageOld", "ageGrandpas"
# filterGroupTags ethnicity: ethnicityMiddleEastern, ethnicityAsian, ethnicityEbony, ethnicityIndian, ethnicityLatino, ethnicityWhite
# filterGroupTags bodyType: "bodyTypePetite", "bodyTypeSkinny", "bodyTypeAthletic", "bodyTypeMuscular", "bodyTypeMedium", "bodyTypeChunky", "bodyTypeCurvy", "bodyTypeBBW", "bodyTypeBig"
# filterGroupTags hairColor: "hairColorBlonde", "hairColorBlack", "hairColorRed", "hairColorColorful"
# filterGroupTags orientation: "orientationBisexual", "orientationGay", "orientationStraight"
# sortBy: trending, stripRanking
# &limit=40
# # &offset=0
# &primaryTag=girls
# &filterGroupTags=[["autoTagNew"]]
# &sortBy=trending

# Get HTML
#o = get_site_page(target)
o = get_site_page_full(filter)
o = o.decode('utf-8')
#cams = re.findall(PAT_ACTOR_LIST_CAT3, o)[0]
#count = cams[1]
#cams = cams[0]
#cams = cams.decode

cams = json.loads(o)

print("totalCount: " + str(cams['totalCount']))
print("filteredCount: " + str(cams['filteredCount']))
print("Models: " + str(len(cams['models'])))

#for c in cams:
#    print(c['snapshotUrl'])

#print(str(len(cams)))
#print(str(cams[0]))

#data = json.loads(o)

#server = "https://b-{0}.strpst.com/hls/{1}/master_{1}.m3u8".format(data["cam"]["viewServers"]["flashphoner-hls"],data["cam"]["streamName"])

#server0 = "https://b-{0}.strpst.com/hls/{1}/{1}.m3u8".format(data["cam"]["viewServers"]["flashphoner-hls"],data["cam"]["streamName"])


#print (server)
#print (server0)
#print (data["user"]["user"]["status"]) # must be public, otherweise show value (virtualPrivate,)
#print (data["user"]["user"]["isLive"]) # must be true also
#print (data["user"]["user"]["avatarUrl"]) # for 'setArt' (WebP works fine)

#print ("https://stripchat.com/api/front/v2/models/username/{0}/cam".format("ScarlettHills"))
# Extract data
#o = re.search(r'initialRoomDossier\s*=\s*"([^"]+)', str(o)) # Get first filtered result (json of room summary)
#if o:
#    temp = o.group(1)
#    temp = temp.replace('\\\\u002D', '-')
#    temp = temp.replace('\\\\u005C', '\\')
#    temp = temp.replace('\\\\u0022', '"')
   
    #temp = json.loads(u""+temp)
    
    #print ("Room Title: \t" + temp['room_title'] + "\nHLS Source: \t" + temp['hls_source'] + "\nStatus: \t" + str(temp['room_status']) + "\nViewers: \t" + str(temp['num_viewers']))
    
#    print (temp)
    
#else:
#    temp = b"Error"
#r = get_site_page_file(target)
#with open("page.html", 'r+b') as f:
#    f.seek(0)
#    f.write(r.read())
#    f.truncate()
#    r = f


#print (o)

#s = json.loads(unicodeData)
#print (s['hls_source'])

#s2 = json.loads(s2)
#print (s2['hls_source'])
