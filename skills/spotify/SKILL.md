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
TERM=dumb spotify play
TERM=dumb spotify pause
TERM=dumb spotify next
TERM=dumb spotify prev
TERM=dumb spotify replay
TERM=dumb spotify stop

# Volume
TERM=dumb spotify vol up
TERM=dumb spotify vol down
TERM=dumb spotify vol <0-100>
TERM=dumb spotify vol show

# Status
TERM=dumb spotify status
TERM=dumb spotify status track
TERM=dumb spotify status artist
TERM=dumb spotify status album

# Share
TERM=dumb spotify share
TERM=dumb spotify share url
TERM=dumb spotify share uri

# Toggles
TERM=dumb spotify toggle shuffle
TERM=dumb spotify toggle repeat

# Search/play by name (requires API creds)
TERM=dumb spotify play "<song>"
TERM=dumb spotify play album "<album>"
TERM=dumb spotify play artist "<artist>"
TERM=dumb spotify play list "<playlist>"
TERM=dumb spotify play uri "spotify:track:<id>"
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
