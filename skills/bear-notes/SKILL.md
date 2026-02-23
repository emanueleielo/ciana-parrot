---
name: bear-notes
description: "Create, search, and manage Bear notes via the grizzly CLI. Supports tags, x-callback-url, and JSON output."
requires_bridge: "bear-notes"
---

# Bear Notes

Use the `bear-notes` bridge to manage Bear notes via `grizzly` on the host.

## When to Use

- User asks to create, read, or search Bear notes
- Managing Bear tags
- Appending content to existing notes

## When NOT to Use

- Apple Notes -> use apple-notes bridge
- Obsidian -> use obsidian bridge
- General text files -> use filesystem tools

## Commands

All commands run via `host_execute(bridge="bear-notes", command="...")`.

### Create a Note

```
echo "Note content" | grizzly create --title "My Note" --tag work
grizzly create --title "Quick Note" --tag inbox < /dev/null
```

### Read a Note

```
grizzly open-note --id "NOTE_ID" --enable-callback --json
```

### Append to a Note

```
echo "Additional content" | grizzly add-text --id "NOTE_ID" --mode append
```

### List Tags

```
grizzly tags --enable-callback --json
```

### Search by Tag

```
grizzly open-tag --name "work" --enable-callback --json
```

## Common Flags

- `--enable-callback` - Wait for Bear's response (needed for reading data)
- `--json` - Output as JSON
- `--dry-run` - Preview without executing

## Setup (on host)

- Install: `go install github.com/tylerwince/grizzly/cmd/grizzly@latest`
- Bear app must be installed and running
- Get API token: Bear > Help > API Token > Copy Token
- Save token: `echo "TOKEN" > ~/.config/grizzly/token`
- Uncomment `bear-notes` bridge in `config.yaml`, restart gateway
