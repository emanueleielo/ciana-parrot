---
name: apple-reminders
description: "Manage Apple Reminders via remindctl CLI: list, add, edit, complete, delete. Supports lists, date filters, and JSON output. Syncs to iOS devices."
requires_bridge: "apple-reminders"
---

# Apple Reminders

Use the `apple-reminders` bridge to manage Apple Reminders via `remindctl` on the host.

## When to Use

- User explicitly mentions "reminder" or "Reminders app"
- Creating personal to-dos with due dates that sync to iOS
- Managing Apple Reminders lists

## When NOT to Use

- Scheduling Ciana tasks or alerts -> use the schedule_task tool instead
- Calendar events -> not supported by this skill
- Project/work task management -> use Notion, Trello, or Things
- User says "remind me" but means a Ciana alert -> clarify first

## Commands

All commands run via `host_execute(bridge="apple-reminders", command="...")`.

### View Reminders

```
remindctl                         # Today's reminders
remindctl today                   # Today
remindctl tomorrow                # Tomorrow
remindctl week                    # This week
remindctl overdue                 # Past due
remindctl all                     # Everything
remindctl 2026-01-04              # Specific date
```

### Manage Lists

```
remindctl list                    # List all lists
remindctl list Work               # Show specific list
remindctl list Projects --create  # Create list
remindctl list Work --delete      # Delete list
```

### Create Reminders

```
remindctl add "Buy milk"
remindctl add --title "Call mom" --list Personal --due tomorrow
remindctl add --title "Meeting prep" --due "2026-02-15 09:00"
```

### Complete/Delete

```
remindctl complete 1 2 3          # Complete by ID
remindctl delete 4A83 --force     # Delete by ID
```

### Output Formats

```
remindctl today --json            # JSON for parsing
remindctl today --plain           # TSV format
remindctl today --quiet           # Counts only
```

## Date Formats

Accepted by `--due` and date filters: `today`, `tomorrow`, `yesterday`, `YYYY-MM-DD`, `YYYY-MM-DD HH:mm`, ISO 8601.

## Setup (on host)

- Install: `brew install steipete/tap/remindctl`
- Grant Reminders permission when prompted
- Uncomment `apple-reminders` bridge in `config.yaml`, restart gateway
