---
name: spotify
description: Control Spotify playback on macOS. Play/pause, skip tracks, control volume, play artists/albums/playlists. Use when a user asks to play music, control Spotify, change songs, or adjust Spotify volume.
metadata: {"clawdbot":{"emoji":"🎵","requires":{"bins":["spotify"],"os":"darwin"},"install":[{"id":"brew","kind":"brew","packages":["shpotify"],"bins":["spotify"],"label":"Install spotify CLI (brew)"}]}}
---

# Spotify CLI

Control Spotify on macOS. No API key required.

## Priority order (important)

1) **Prefer the `spotify` binary for anything it can do** (play/pause/next/prev/volume/status, and *any* search/play-by-name features if your installed `spotify` supports them).
2) If the binary **does not support** the request (common for “play <song name>”), fall back to **AppleScript** using a Spotify URI (track/album/artist).
3) Only use a **browser** as a last resort to discover a Spotify ID when no reliable non-browser lookup exists.

### Capability check (avoid token burn)

Do **not** run `spotify --help` for every request.

Only run it when:
- this is the first Spotify command of the session **and** you don’t already know the installed CLI’s feature set, or
- a command fails and you suspect the CLI variant changed.

Otherwise, assume the common `shpotify` interface listed below.

```bash
TERM=dumb spotify --help
```

## Commands (your installed `spotify` / shpotify)

Use `TERM=dumb` to avoid `tput` / `$TERM` issues in non-interactive runs.

### Quick cheat-sheet

```bash
TERM=dumb spotify play                 # Resume
TERM=dumb spotify play "<song>"         # Search + play track by name (requires API creds)
TERM=dumb spotify play album "<album>"  # Search + play album (requires API creds)
TERM=dumb spotify play artist "<artist>"# Search + play artist (requires API creds)
TERM=dumb spotify play list "<playlist>"# Search + play playlist (requires API creds)
TERM=dumb spotify play uri "spotify:track:<id>"  # Play a specific URI

TERM=dumb spotify next
TERM=dumb spotify prev
TERM=dumb spotify replay
TERM=dumb spotify pos <seconds>
TERM=dumb spotify pause
TERM=dumb spotify stop
TERM=dumb spotify quit

TERM=dumb spotify vol up
TERM=dumb spotify vol down
TERM=dumb spotify vol <0-100>
TERM=dumb spotify vol show

TERM=dumb spotify status
TERM=dumb spotify status artist
TERM=dumb spotify status album
TERM=dumb spotify status track

TERM=dumb spotify share
TERM=dumb spotify share url
TERM=dumb spotify share uri

TERM=dumb spotify toggle shuffle
TERM=dumb spotify toggle repeat
```

### Full `spotify --help` output (captured)

(Kept here so the agent has the interface at a glance; don’t re-run help unless debugging.)

```text
Usage:

  spotify <command>

Commands:

  play                         # Resumes playback where Spotify last left off.
  play <song name>             # Finds a song by name and plays it.
  play album <album name>      # Finds an album by name and plays it.
  play artist <artist name>    # Finds an artist by name and plays it.
  play list <playlist name>    # Finds a playlist by name and plays it.
  play uri <uri>               # Play songs from specific uri.

  next                         # Skips to the next song in a playlist.
  prev                         # Returns to the previous song in a playlist.
  replay                       # Replays the current track from the beginning.
  pos <time>                   # Jumps to a time (in secs) in the current song.
  pause                        # Pauses (or resumes) Spotify playback.
  stop                         # Stops playback.
  quit                         # Stops playback and quits Spotify.

  vol up                       # Increases the volume by 10%.
  vol down                     # Decreases the volume by 10%.
  vol <amount>                 # Sets the volume to an amount between 0 and 100.
  vol [show]                   # Shows the current Spotify volume.

  status                       # Shows the current player status.
  status artist                # Shows the currently playing artist.
  status album                 # Shows the currently playing album.
  status track                 # Shows the currently playing track.

  share                        # Displays the current song's Spotify URL and URI.
  share url                    # Displays the current song's Spotify URL and copies it to the clipboard.
  share uri                    # Displays the current song's Spotify URI and copies it to the clipboard.

  toggle shuffle               # Toggles shuffle playback mode.
  toggle repeat                # Toggles repeat playback mode.

Connecting to Spotify's API:

  This command line application needs to connect to Spotify's API in order to
  find music by name.

  To get this to work, create an app at:
  https://developer.spotify.com/my-applications/#!/applications/create

  Then set creds in:
  /Users/anik/.shpotify.cfg

  Example:
  CLIENT_ID="abc01de2fghijk345lmnop"
  CLIENT_SECRET="qr6stu789vwxyz"
```

## Play by Name (fallback)

If the `spotify` binary does **not** support search/play-by-name, do this:

1) Find a Spotify URL (prefer non-browser lookups first):
   - Try `web_search` for a direct Spotify URL.
   - If no direct URL is found, **then** use the browser to open Spotify search and copy the track/album/artist link.
2) Extract the ID from the URL:
   - `open.spotify.com/track/<ID>` → `<ID>`
   - `open.spotify.com/album/<ID>` → `<ID>`
   - `open.spotify.com/artist/<ID>` → `<ID>`
3) Play with AppleScript:

```bash
# Artist
osascript -e 'tell application "Spotify" to play track "spotify:artist:4tZwfgrHOc3mvqYlEYSvVi"'

# Album
osascript -e 'tell application "Spotify" to play track "spotify:album:4m2880jivSbbyEGAKfITCa"'

# Track
osascript -e 'tell application "Spotify" to play track "spotify:track:2KHRENHQzTIQ001nlP9Gdc"'
```

## Notes

- **macOS only** - uses AppleScript
- Spotify desktop app must be running
- Works with Sonos via Spotify Connect
