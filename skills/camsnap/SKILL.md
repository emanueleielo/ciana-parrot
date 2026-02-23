---
name: camsnap
description: "Capture snapshots, clips, or motion events from RTSP/ONVIF IP cameras via camsnap CLI."
requires_bridge: "camsnap"
---

# IP Cameras (camsnap)

Use the `camsnap` bridge to capture from IP cameras via the `camsnap` CLI on the host.

## When to Use

- User asks to check a camera or take a snapshot
- Capturing video clips from security cameras
- Discovering cameras on the network

## Commands

All commands run via `host_execute(bridge="camsnap", command="...")`.

```
camsnap discover --info                        # Find cameras on network
camsnap snap kitchen --out /tmp/shot.jpg       # Take snapshot
camsnap clip kitchen --dur 5s --out /tmp/clip.mp4  # Record clip
camsnap doctor --probe                         # Diagnostics
```

## Setup (on host)

- Install: `brew install steipete/tap/camsnap`
- Requires `ffmpeg` on PATH
- Configure cameras: `camsnap add --name kitchen --host 192.168.0.10 --user user --pass pass`
- Config file: `~/.config/camsnap/config.yaml`
- Uncomment `camsnap` bridge in `config.yaml`, restart gateway
