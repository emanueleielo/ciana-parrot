---
name: openhue
description: "Control Philips Hue lights and scenes: on/off, brightness, color, color temperature, rooms, and scene activation via openhue CLI."
requires_bridge: "openhue"
---

# Philips Hue

Use the `openhue` bridge to control Philips Hue lights via the `openhue` CLI on the host.

## When to Use

- "Turn on/off the lights"
- "Dim the living room lights"
- "Set a scene" or "movie mode"
- Adjusting brightness, color, or color temperature

## When NOT to Use

- Non-Hue smart devices -> not supported
- HomeKit scenes -> not supported via this bridge
- Sonos/audio -> use sonos bridge

## Commands

All commands run via `host_execute(bridge="openhue", command="...")`.

### List Resources

```
openhue get light                              # List all lights
openhue get room                               # List all rooms
openhue get scene                              # List all scenes
```

### Control Lights

```
openhue set light "Bedroom Lamp" --on
openhue set light "Bedroom Lamp" --off
openhue set light "Bedroom Lamp" --on --brightness 50
openhue set light "Bedroom Lamp" --on --temperature 300     # Warm to cool: 153-500 mirek
openhue set light "Bedroom Lamp" --on --color red
openhue set light "Bedroom Lamp" --on --rgb "#FF5500"
```

### Control Rooms

```
openhue set room "Bedroom" --off
openhue set room "Bedroom" --on --brightness 30
```

### Scenes

```
openhue set scene "Relax" --room "Bedroom"
openhue set scene "Concentrate" --room "Office"
```

### Quick Presets

```
openhue set room "Bedroom" --on --brightness 20 --temperature 450    # Bedtime
openhue set room "Office" --on --brightness 100 --temperature 250    # Work mode
openhue set room "Living Room" --on --brightness 10                  # Movie mode
```

## Setup (on host)

- Install: `brew install openhue/cli/openhue-cli`
- Hue Bridge must be on local network
- First run: press button on Hue Bridge to pair
- Uncomment `openhue` bridge in `config.yaml`, restart gateway
