---
name: obsidian
description: "Work with Obsidian vaults: create, search, move, delete notes. Plain Markdown files with wikilink-aware operations via obsidian-cli."
requires_bridge: "obsidian"
---

# Obsidian

Use the `obsidian` bridge to manage Obsidian vault notes via `obsidian-cli` on the host.

## When to Use

- User asks about Obsidian notes or vault
- Creating, searching, or editing Markdown notes in a vault
- Moving/renaming notes (preserves wikilinks)

## When NOT to Use

- Apple Notes -> use apple-notes bridge
- Bear notes -> use bear-notes bridge
- Generic file editing -> use filesystem tools

## Commands

All commands run via `host_execute(bridge="obsidian", command="...")`.

### Find Vault

```
obsidian-cli print-default --path-only
```

### Search

```
obsidian-cli search "query"                  # Search note names
obsidian-cli search-content "query"          # Search inside notes
```

### Create

```
obsidian-cli create "Folder/New note" --content "..." --open
```

### Move/Rename (updates wikilinks)

```
obsidian-cli move "old/path/note" "new/path/note"
```

### Delete

```
obsidian-cli delete "path/note"
```

## Notes

- Obsidian vault = normal folder of `.md` files
- Multiple vaults are common; check config before guessing paths
- Vault config: `~/Library/Application Support/obsidian/obsidian.json`

## Setup (on host)

- Install: `brew install yakitrak/yakitrak/obsidian-cli`
- Set default vault: `obsidian-cli set-default "vault-name"`
- Uncomment `obsidian` bridge in `config.yaml`, restart gateway
