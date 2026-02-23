---
name: peekaboo
description: "macOS UI automation: capture screenshots, click elements, type text, manage apps/windows/menus. Full desktop control via peekaboo CLI."
requires_bridge: "peekaboo"
---

# Peekaboo (macOS UI Automation)

Use the `peekaboo` bridge for full macOS UI automation: screenshots, clicks, typing, app/window management.

## When to Use

- User asks to interact with a macOS app (click, type, screenshot)
- Capturing what's on screen
- Automating UI workflows
- Managing windows, menus, Dock

## When NOT to Use

- Tasks that can be done via API/CLI -> prefer the specific bridge/skill
- Bulk automation -> consider AppleScript or Shortcuts instead

## Commands

All commands run via `host_execute(bridge="peekaboo", command="...")`.

### See & Capture

```
peekaboo permissions                                          # Check permissions
peekaboo see --annotate --path /tmp/peekaboo-see.png          # Annotated screenshot
peekaboo image --mode screen --path /tmp/screen.png           # Full screenshot
peekaboo image --app Safari --analyze "Summarize the page"    # Screenshot + analysis
peekaboo list apps --json                                     # List running apps
peekaboo list windows --app Safari --json                     # List windows
```

### Interact

```
peekaboo click --on B1                                        # Click element by ID
peekaboo click --coords 500,300                               # Click by coordinates
peekaboo type "Hello" --return                                # Type text + Enter
peekaboo hotkey --keys "cmd,shift,t"                          # Keyboard shortcut
peekaboo scroll --direction down --amount 5                   # Scroll
```

### App Management

```
peekaboo app launch "Safari" --open https://example.com
peekaboo app quit --app Safari
peekaboo window focus --app Safari
peekaboo menu click --app Safari --item "New Window"
```

### Workflow: See -> Click -> Type

```
peekaboo see --app Safari --annotate --path /tmp/see.png      # 1. See what's on screen
peekaboo click --on B3 --app Safari                           # 2. Click target element
peekaboo type "search query" --app Safari --return            # 3. Type and submit
```

## Setup (on host)

- Install: `brew install steipete/tap/peekaboo`
- Grant Screen Recording + Accessibility permissions in System Settings
- Uncomment `peekaboo` bridge in `config.yaml`, restart gateway
