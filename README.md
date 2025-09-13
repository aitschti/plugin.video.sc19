# plugin.video.sc19

A kodi addon for streaming cams from Stripchat. Works with all kodi releases 19 and up.
Integrates a proxy for decoding newly scrambled playlist segment URLs by Stripchat (see notes below).

Tested on Android (Fire TV), Windows and MacOS, should work fine with other Linux systems as well. Not available in a kodi repository, so use "Install from ZIP" in kodi and point to the zip file to install.

## Features

- Listing of cams for all main categories
- Pagination for listings (set cams per page and type of listing in settings)
- Search for cam (exact name and normal fuzzy search)
- Favourites list (with backup/restore function. **Set path in settings first!**)
- Check online state of favourite cams before listing them (with progress bar, takes some time, can be disabled in settings)
- View profile details of performer (Use context menu > videos and albums)
- Shows cam states of performer (idle, private etc.)
- When streaming a cam use info button for additional info about the room like topic, goal, viewers etc. (if available)
- Option to use my external standalone proxy solution for decoding (<https://github.com/aitschti/scp-standalone>)
- Enable timeshift for playback in settings (Stream options). Check free space on your device! You can look at Inputstream FFmpegDirect settings to set path and max duration.
- Option to use variants playlist (if you have issues with best quality only)
- Option to change CDN (default doppiocdn.net, if you have connection issues / are ip blocked)
- Automatic decode key fetching for scrambled segment filenames (v2.1.0+). If you have issues, set key manually in settings.

## Usage

**First use**:

- Install the addon from the ZIP file in Kodi.
- **Proxy Setup (using internal proxy)**: The addon uses a proxy for streaming. Ensure the proxy port (default 8099) is available and not in use by other applications. You can configure the port in the addon settings.
- **Favourites**: Set a path for a backup location of the favourites database for easy backup and restore and sharing with other clients in your network.
- **Decode Key**: On first playback or on key changes on Stripchat's side, the addon will attempt to fetch the decode key automatically. This key is essential for decrypting stream URLs (using internal proxy). You can also set the key manually in the settings if needed.

## Recommended settings / tips

- Tested with Estuary skin only
- "Info wall" is the recommended view for listings as you get a little more details about the cam
- Use variants (instead of best only quality) playlist, if you have issues. May be slower, though
- Change CDN in settings ("Other"), if you have connection issues / are ip blocked (default doppiocdn.net)

## Notes regarding Stripchat's streaming changes

As of late August 2025 Stripchat started implementing measures to prevent easy streaming of their content outside of their site by scrambling the stream URLs in the m3u8 playlist files and the need to pass additional URL parameters to even get the initial m3u8 playlist. They do that by using custom playlist tags in the playlist files containing the scrambled segment filenames which need to be decoded first and then some string replacement is done to get the actual stream URLs.

By doing that, no normal HLS capable player can simply use the m3u8 URL to stream the content without first decrypting the segment filenames.

To solve this, we can use a proxy that takes the requested m3u8 file, decrypts the segment filenames and serves a modified m3u8 file to the player with the correct stream URLs.

The decryption needs a key, which is also served by Stripchat in an kind of obfuscated way. The addon can fetch this key automatically (if not set manually in settings). This may break at any time if Stripchat changes their obfuscation method.

Outlook: They already serve a "v1" attribute in the m3u8 files, which may suggest upcoming changes to their streaming protocol or additional security measures, maybe even encrypting the stream data. So stay tuned.

## License

For educational purposes only. Do not use for any commercial activities. Feel free to modify.
