---
name: things
description: "Manage Things 3 on macOS: add/update todos and projects via URL scheme, read inbox/today/upcoming, search tasks. Syncs to iOS."
requires_bridge: "things"
---

# Things 3

Use the `things` bridge to manage Things 3 via the `things` CLI on the host.

## When to Use

- User asks to add a task or todo to Things
- Listing inbox, today, upcoming tasks
- Searching tasks or projects
- Managing Things areas and tags

## When NOT to Use

- Apple Reminders -> use apple-reminders bridge
- Notion/Trello tasks -> use those skills instead
- Ciana scheduled tasks -> use schedule_task tool

## Commands

All commands run via `host_execute(bridge="things", command="...")`.

### Read (from DB)

```
things inbox --limit 50
things today
things upcoming
things search "query"
things projects
things areas
things tags
```

### Add Todos

```
things add "Buy milk"
things add "Call mom" --notes "about dinner" --when today
things add "Meeting prep" --deadline 2026-02-15
things add "Book flights" --list "Travel"
things add "Trip prep" --checklist-item "Passport" --checklist-item "Tickets"
```

### Update Todos (needs auth token)

```
things search "milk" --limit 5           # Get UUID
things update --id <UUID> "New title"
things update --id <UUID> --completed
things update --id <UUID> --notes "New notes"
```

## Setup (on host)

- Install: `GOBIN=/opt/homebrew/bin go install github.com/ossianhempel/things3-cli/cmd/things@latest`
- Grant Full Disk Access to Terminal/gateway process
- Optional: set `THINGS_AUTH_TOKEN` env var for update operations
- Uncomment `things` bridge in `config.yaml`, restart gateway
