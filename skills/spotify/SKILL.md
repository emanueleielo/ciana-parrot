---
name: spotify
description: "Control Spotify playback: play, pause, skip, search tracks/albums/playlists, manage devices and queue via spogo CLI."
requires_bridge: "spotify"
---

# Spotify

Use the `spotify` bridge to control Spotify playback via `spogo` on the host.

## When to Use

- User asks to play, pause, skip music
- Searching for songs, albums, artists, playlists
- Managing playback devices or queue
- Checking what's currently playing

## When NOT to Use

- Apple Music -> not supported
- Sonos playback -> use sonos bridge
- Local audio files -> not supported

## Critical Rules

1. **Only run `spogo` commands** through `host_execute`. Never run `sleep`, `echo`, or any non-spogo command through the spotify bridge — they will be blocked by the gateway allowlist.
2. **Always verify playback after `spogo play`** — run `spogo status --json` and check that `is_playing` is `true` and the correct track is loaded. Never tell the user "it's playing" without verifying.
3. **Use `--device` flag** when targeting a specific device, especially if `spogo play` fails with "missing device id".

## Commands

All commands run via `host_execute(bridge="spotify", command="...")`.

### Play by Name (most common workflow)

**IMPORTANT:** `spogo play` requires a Spotify URI, not a name. Follow this exact sequence:

1. Search: `spogo search track "song name" --json` (or artist/album/playlist)
2. Extract the `uri` field from the first result
3. Play: `spogo play <uri>`
4. **Verify:** `spogo status --json` — check `is_playing: true` and correct track name
5. If `is_playing: false`, see "Known Issues" below

### Playback

```
spogo status                                   # What's playing (text)
spogo status --json                            # What's playing (JSON, use for verification)
spogo play <uri>                               # Play a specific URI
spogo play <uri> --device "MacBook Air"        # Play on a specific device
spogo pause                                    # Pause
spogo next                                     # Next track
spogo prev                                     # Previous track
```

### Search

Always use `--json` to get URIs for playback.

```
spogo search track "bohemian rhapsody" --json
spogo search album "dark side of the moon" --json
spogo search artist "radiohead" --json
spogo search playlist "chill vibes" --json
```

### Devices

```
spogo device list --json                       # List devices (use JSON to check is_active)
spogo device set "Living Room"                 # Switch device
```

### Auth & Diagnostics

```
spogo auth status                              # Check if authenticated
spogo auth import --browser chrome             # Import cookies from Chrome
spogo auth import --browser safari             # Import cookies from Safari
```

## Known Issues & Workarounds

### Device not active after Spotify restart

After Spotify restarts, all devices show `is_active: false`. In this state:
- `spogo play <uri>` returns "Playback started" but **does nothing** (false success)
- Playback only works after the user manually interacts with Spotify at least once

**Detection:** After `spogo play <uri>`, run `spogo status --json`. If `is_playing` is still `false` or the track didn't change, the device is not active.

**Workaround:** Tell the user: "Spotify needs to be activated first — press play once in the Spotify app, then I can take over."

### Resume (spogo play without args) returns 403

`spogo play` (resume) often fails with `403 Forbidden`. This is a spogo/Spotify API bug.

**Workaround:** Never use `spogo play` without arguments. Instead:
1. Get current track: `spogo status --json`
2. Replay with URI: `spogo play <item.uri>`

### "missing device id" error

Happens when no device is active and spogo can't auto-select one.

**Workaround:**
1. Run `spogo device list --json` to find available devices
2. Use `--device` flag: `spogo play <uri> --device "Emanuele's MacBook Air"`
3. If all devices are `is_active: false`, tell the user to open Spotify and press play once

### Rate limit (429)

Spotify API has rate limits. If you get a 429 error, wait a moment before retrying. Do NOT try to run `sleep` via host_execute — just tell the user you'll retry in a moment and try the command again on the next message.

## Troubleshooting

If a Spotify command fails, follow this sequence:

1. Run `spogo auth status` to check authentication
2. If `sp_dc` cookie is missing/expired, run `spogo auth import --browser chrome`
3. If import fails, tell the user to log out/in on `open.spotify.com` in Chrome, then retry
4. If Keychain popup blocks on host, tell user to click "Always Allow", then retry
5. If playback returns success but nothing happens, run `spogo device list --json` — if all `is_active: false`, tell user to activate Spotify manually once
6. If rate limited (429), wait and retry on the next message

**Always try via host_execute first.** Only suggest manual steps if host_execute itself fails.

## Setup (first time, on host)

- Requires Spotify Premium account
- Install: `brew install steipete/tap/spogo`
- Initial auth: `spogo auth import --browser chrome` (or let Ciana do it)
- If Keychain popup appears, enter password and click "Always Allow"
