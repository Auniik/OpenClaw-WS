---
name: spotify
description: Control Spotify playback on macOS. Play/pause, skip tracks, control volume, play artists/albums/playlists. Use when a user asks to play music, control Spotify, change songs, or adjust Spotify volume.
metadata: {"clawdbot":{"emoji":"🎵","requires":{"bins":["spotify"],"os":"darwin"},"install":[{"id":"brew","kind":"brew","packages":["shpotify"],"bins":["spotify"],"label":"Install spotify CLI (brew)"}]}}
---

# Spotify CLI

Control Spotify on macOS.

- **Basic controls (play/pause/next/prev/volume/status):** no API key needed.
- **Search/play by name:** requires Spotify API creds in `/Users/anik/.shpotify.cfg` (shpotify).

## Priority order

1) Use the `spotify` CLI for everything it supports.
2) If you must play a specific Spotify URI, use AppleScript.
3) Use the browser only as a last resort to discover IDs.

*(Don’t run `spotify --help` every time; only when debugging or the CLI variant is unknown.)*

## Commands (`spotify` / shpotify)

Use `TERM=dumb` to avoid `tput` / `$TERM` issues in non-interactive runs.

```bash
# Playback
TERM=dumb spotify play                  # Resume playback where Spotify last left off
TERM=dumb spotify play "<song name>"     # Find a song by name and play it (requires API creds)
TERM=dumb spotify play album "<album>"   # Find an album by name and play it (requires API creds)
TERM=dumb spotify play artist "<artist>" # Find an artist by name and play it (requires API creds)
TERM=dumb spotify play list "<playlist>" # Find a playlist by name and play it (requires API creds)
TERM=dumb spotify play uri "<uri>"       # Play from a specific Spotify URI (e.g. spotify:track:<id>)

TERM=dumb spotify next                  # Skip to next song
TERM=dumb spotify prev                  # Go to previous song
TERM=dumb spotify replay                # Restart current track from beginning
TERM=dumb spotify pos <seconds>         # Jump to position in seconds
TERM=dumb spotify pause                 # Pause (or resume) playback
TERM=dumb spotify stop                  # Stop playback
TERM=dumb spotify quit                  # Stop playback and quit Spotify

# Volume
TERM=dumb spotify vol up                # +10% volume
TERM=dumb spotify vol down              # -10% volume
TERM=dumb spotify vol <0-100>           # Set volume
TERM=dumb spotify vol show              # Show current volume

# Status
TERM=dumb spotify status                # Show current player status
TERM=dumb spotify status track          # Show currently playing track
TERM=dumb spotify status artist         # Show currently playing artist
TERM=dumb spotify status album          # Show currently playing album

# Share
TERM=dumb spotify share                 # Show current song's Spotify URL + URI
TERM=dumb spotify share url             # Show URL (and copy to clipboard)
TERM=dumb spotify share uri             # Show URI (and copy to clipboard)

# Toggles
TERM=dumb spotify toggle shuffle        # Toggle shuffle
TERM=dumb spotify toggle repeat         # Toggle repeat
```

## Fallback: play a specific Spotify URI (AppleScript)

Use this when:
- search/play-by-name isn’t available (or creds aren’t configured), or
- you already have a Spotify URL/ID.

1) Get the ID from a Spotify URL (prefer `web_search`; use browser only if needed):
- `open.spotify.com/track/<ID>` → `<ID>`
- `open.spotify.com/album/<ID>` → `<ID>`
- `open.spotify.com/artist/<ID>` → `<ID>`

2) Play via AppleScript:

```bash
osascript -e 'tell application "Spotify" to play track "spotify:track:<ID>"'
# or: spotify:album:<ID> / spotify:artist:<ID>
```

## Notes

- **macOS only** - uses AppleScript
- Spotify desktop app must be running
- Works with Sonos via Spotify Connect
