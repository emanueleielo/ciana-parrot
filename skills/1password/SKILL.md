---
name: 1password
description: "Access 1Password secrets via the op CLI: read passwords, inject secrets into commands, manage vaults. Requires desktop app integration."
requires_bridge: "1password"
---

# 1Password CLI

Use the `1password` bridge to access secrets via the `op` CLI on the host.

## When to Use

- User asks to look up a password or secret
- Injecting credentials into a command
- Listing vault items

## When NOT to Use

- Storing new passwords -> direct the user to 1Password app
- Managing 1Password settings -> direct the user to the app

## Commands

All commands run via `host_execute(bridge="1password", command="...")`.

### Basic Operations

```
op --version                                    # Check CLI
op whoami                                       # Current account
op vault list                                   # List vaults
op item list --vault Personal                   # List items
op item get "Item Name" --fields password       # Get a field
```

### Inject Secrets

```
op run -- env                                   # Run with secrets injected
op inject --in-file template.env --out-file .env  # Template injection
```

## Guardrails

- **Never paste secrets into chat, logs, or code**
- Prefer `op run` / `op inject` over writing secrets to disk
- If sign-in fails, user must authorize in the 1Password desktop app

## Setup (on host)

- Install: `brew install 1password-cli`
- Enable CLI integration in 1Password desktop app (Settings > Developer > CLI)
- Sign in: `op signin`
- Uncomment `1password` bridge in `config.yaml`, restart gateway
