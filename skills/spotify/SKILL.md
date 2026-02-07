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

## Commands (common shpotify)

Use `TERM=dumb` to avoid `tput` / `$TERM` issues in non-interactive runs.

```bash
TERM=dumb spotify play           # Resume
TERM=dumb spotify pause          # Pause/toggle
TERM=dumb spotify next           # Next track
TERM=dumb spotify prev           # Previous track
TERM=dumb spotify stop           # Stop

TERM=dumb spotify vol up         # +10%
TERM=dumb spotify vol down       # -10%
TERM=dumb spotify vol 50         # Set to 50%

TERM=dumb spotify status         # Current track info
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
