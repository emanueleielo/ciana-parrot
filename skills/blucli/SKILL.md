---
name: blucli
description: "Control Bluesound/NAD players: discovery, playback, volume, grouping, and TuneIn radio via blu CLI."
requires_bridge: "blucli"
---

# Bluesound / NAD (BluOS)

Use the `blucli` bridge to control Bluesound/NAD players via the `blu` CLI on the host.

## When to Use

- User asks to control Bluesound or NAD speakers
- Playing/pausing BluOS devices
- Adjusting volume, grouping speakers
- Searching/playing TuneIn radio

## When NOT to Use

- Sonos speakers -> use sonos bridge
- Spotify -> use spotify bridge

## Commands

All commands run via `host_execute(bridge="blucli", command="...")`.

```
blu devices                                    # Discover devices
blu --device "Living Room" status              # Current status
blu --device "Living Room" play                # Play
blu --device "Living Room" pause               # Pause
blu --device "Living Room" volume set 15       # Set volume
blu group status                               # Group status
blu group add --device "Bedroom"               # Add to group
blu tunein search "BBC Radio"                  # Search TuneIn
blu tunein play "BBC Radio 1"                  # Play radio
```

## Setup (on host)

- Install: `go install github.com/steipete/blucli/cmd/blu@latest`
- BluOS devices must be on local network
- Uncomment `blucli` bridge in `config.yaml`, restart gateway
