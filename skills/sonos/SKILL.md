---
name: sonos
description: "Control Sonos speakers: discover, play/pause, volume, grouping, favorites, and queue management via sonos CLI."
requires_bridge: "sonos"
---

# Sonos

Use the `sonos` bridge to control Sonos speakers via the `sonos` CLI on the host.

## When to Use

- User asks to play/pause/skip on Sonos
- Adjusting volume on speakers
- Grouping/ungrouping speakers
- Playing favorites or managing queue

## When NOT to Use

- Spotify direct control -> use spotify bridge
- Bluesound/NAD -> use blucli bridge
- Non-Sonos speakers

## Commands

All commands run via `host_execute(bridge="sonos", command="...")`.

### Discovery & Status

```
sonos discover
sonos status --name "Kitchen"
```

### Playback

```
sonos play --name "Kitchen"
sonos pause --name "Kitchen"
sonos stop --name "Kitchen"
```

### Volume

```
sonos volume set 15 --name "Kitchen"
sonos volume up --name "Kitchen"
sonos volume down --name "Kitchen"
```

### Grouping

```
sonos group status
sonos group join --name "Bedroom" --coordinator "Kitchen"
sonos group unjoin --name "Bedroom"
sonos group party                              # Group all speakers
sonos group solo --name "Kitchen"              # Ungroup one
```

### Favorites & Queue

```
sonos favorites list
sonos favorites open --name "Kitchen" --favorite "My Playlist"
sonos queue list --name "Kitchen"
sonos queue clear --name "Kitchen"
```

## Setup (on host)

- Install: `go install github.com/steipete/sonoscli/cmd/sonos@latest`
- Sonos speakers must be on local network
- If SSDP fails: `sonos --ip <speaker-ip> status`
- Uncomment `sonos` bridge in `config.yaml`, restart gateway
