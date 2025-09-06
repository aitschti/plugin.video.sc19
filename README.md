# plugin.video.sc19

A kodi plugin with integrated proxy for streaming cams from stripchat.com. Works with all kodi releases 19, 20 and 21.

Tested on Android (Fire TV), Windows and MacOS, should work fine with other Linux systems as well. Not available in a kodi repository, so use "Install from ZIP" in kodi and point to the zip file to install.

**You will need to set a decode key in the addon's settings at first use. Otherwise, no streams can be played. Read below why.**

## Important note

As of late August 2025 Stripchat started implementing measures to prevent easy streaming of their content outside of their site by encrypting the stream URLs in the m3u8 playlist files and the need to pass additional URL parameters to even get the initial m3u8 playlist. They do that by using custom playlist tags in the playlist files containing the encrypted segment filenames which need to be decoded first and then some string replacement is done to get the actual stream URLs.

By doing that, no normal HLS capable player can simply use the m3u8 URL to stream the content without first decrypting the segment filenames.

To solve this, we can use a proxy that takes the requested m3u8 file, decrypts the segment filenames and serves a modified m3u8 file to the player with the correct stream URLs.

All the needed info for decrypting is already available in the m3u8 files themselves, except the function to decrypt the segment filenames with the needed key. The javascript handling all of this gets dynamically loaded from the site as a blob when using a browser, so we do not have simple url to load it from. One can quite easily extract the key from the blob with a browser's development tools.

For possible legal reason, I will not provide the key with this addon, not even obfuscated. You will need to extract it yourself. Stripchat did not implement theses measures for fun.

I am sorry this is making it more difficult to use this addon.

Outlook: They already serve a "v1" attribute in the m3u8 files, which may suggest upcoming changes to their streaming protocol or additional security measures, maybe even encrypting the stream data. So stay tuned.

## Features

- Listing of cams for all main categories
- Pagination for listings (set cams per page and type of listing in settings)
- Search for cam (exact name and normal fuzzy search)
- Favourites list (with backup/restore function. **Set path in settings first!**)
- Check online state of favourite cams before listing them (with progress bar, takes some time, can be disabled in settings)
- View profile details of performer (Use context menu > videos and albums)
- Shows cam states of performer (idle, private etc.)
- When streaming a cam use info button for additional info about the room like topic, goal, viewers etc. (if available)
- Option to use external proxy for decoding (e.g. <https://github.com/aitschti/scp-standalone>)
- Enable timeshift for playback in settings (Stream options). Check free space on your device! You can look at Inputstream FFmpegDirect settings to set path and max duration.

## Usage

**First use**:

- Install the addon from the ZIP file in Kodi.
- **Proxy Setup (if using internal proxy)**: The addon uses a proxy for streaming. Ensure the proxy port (default 8099) is available and not in use by other applications. You can configure the port in the addon settings.
- **Decode Key**: You must set a decode key in the addon's settings. This key is essential for decrypting stream URLs.
- **Favourites**: Set a path for a backup location of the favourites database for easy backup and restore and sharing with other clients in your network.

## Recommended settings

- Tested with Estuary skin only
- "Info wall" is the recommended view for listings as you get a little more details about the cam

## License

For educational purposes only. Do not use for any commercial activities. Feel free to modify.
