---
name: troubleshooting
description: "Diagnose and resolve errors with Ciana's host bridges, CLI tools, Claude Code mode, macOS permissions, and gateway connectivity."
---

# Troubleshooting

Reference guide for diagnosing errors. Read this when a command fails, a bridge is unreachable, or a user reports something isn't working.

## When to Use

- A `host_execute` call returns an error
- Claude Code mode fails
- User says something "doesn't work" or asks how to set up a feature
- You get connection, auth, or permission errors

## Gateway Errors

### "Cannot connect to host gateway. Is the gateway server running?"

The gateway process is not running on the host machine.

**Tell the user:** Run `make gateway` on the host (outside Docker) to start it.

### "Gateway auth failed. Check GATEWAY_TOKEN."

The token in the Docker container doesn't match the one on the host.

**Tell the user:** Verify that `GATEWAY_TOKEN` in `.env` matches on both sides, then restart both gateway and container.

### "unknown bridge 'X'. Available: ..."

The bridge name doesn't exist in `config.yaml` under `gateway.bridges`.

**Check:** Are you using the correct bridge name? Compare with the available list in the error.

### "command 'X' not allowed for bridge 'Y'"

The CLI command is not in the bridge's `allowed_commands` list. This is a security feature.

**Tell the user:** Add the command to the bridge's `allowed_commands` in `config.yaml` and restart the gateway.

## CLI Not Found

### "Command 'X' not found on host. Install it first."

The CLI binary is not installed on the host. Exit code 127.

**Installation commands (Homebrew):**

| CLI | Install command |
|-----|----------------|
| `remindctl` | `brew install steipete/tap/remindctl` |
| `imsg` | `brew install steipete/tap/imsg` |
| `spogo` | `brew install steipete/tap/spogo` |
| `wacli` | `brew install steipete/tap/wacli` |
| `sonoscli` | `brew install steipete/tap/sonoscli` |
| `bear` | `brew install steipete/tap/bear` |
| `camsnap` | `brew install steipete/tap/camsnap` |
| `peekaboo` | `brew install steipete/tap/peekaboo` |
| `blucli` | `brew install steipete/tap/blucli` |
| `obsidian-cli` | `brew install steipete/tap/obsidian-cli` |
| `openhue` | `brew install openhue/cli/openhue` |
| `things-cli` | `brew install thingsapi/things-cli/things-cli` |
| `op` | `brew install 1password-cli` |

## CLI Authentication

Some CLIs require one-time interactive setup on the host **before** they can work through the gateway. The gateway cannot handle interactive prompts (QR codes, passwords, browser flows).

**Tell the user to run these manually in their terminal:**

| CLI | Setup command | Notes |
|-----|--------------|-------|
| `spogo` | `spogo auth import --browser chrome` | Needs Spotify Premium. Keychain popup: click "Always Allow" |
| `wacli` | `wacli auth` then `wacli sync --follow` | Scan QR code with WhatsApp on phone |
| `imsg` | (automatic) | Grant Full Disk Access + Automation for Messages.app in System Settings |
| `op` | `op signin` | Needs 1Password account |
| `openhue` | `openhue setup` | Press Hue Bridge button when prompted |

## macOS Permissions

Some CLIs need macOS privacy permissions. These are granted once in System Settings > Privacy & Security.

### Keychain Access Popup

If a CLI tries to access Chrome cookies or saved credentials, macOS shows a Keychain dialog. This **blocks the subprocess** until the user responds.

**Tell the user:** Enter password and click "Always Allow" so it won't ask again.

### Full Disk Access

Required by: `imsg` (reads Messages database)

**Tell the user:** System Settings > Privacy & Security > Full Disk Access > enable Terminal (or the app running the gateway).

### Automation

Required by: `imsg` (controls Messages.app)

**Tell the user:** System Settings > Privacy & Security > Automation > allow Terminal to control Messages.

### Reminders / Contacts / Calendar

CLIs that access these trigger a one-time permission prompt. Accept it when it appears.

## Claude Code Mode

### "Bridge returned HTTP 400"

The request to the gateway is missing required fields. Make sure the container is running the latest code.

**Tell the user:** Rebuild and restart: `make build && make restart`

### "Bridge returned HTTP 401"

Auth token mismatch between the CC bridge config (`CC_BRIDGE_TOKEN`) and the gateway (`GATEWAY_TOKEN`).

**Tell the user:** Check that both tokens match in `.env`, restart both.

### "Cannot connect to Claude Code bridge"

Same as gateway connection error. The CC bridge uses the gateway.

**Tell the user:** Run `make gateway` on the host.

### Project list is empty

Claude Code stores projects in `~/.claude/projects/`. If this directory doesn't exist or is empty, there are no projects to show.

**Tell the user:** Use Claude Code from the terminal first to create at least one project, or check that `projects_dir` in `config.yaml` points to the right path.

### Session hangs or times out

Claude Code can take a long time for complex tasks. The default timeout is 0 (unlimited).

If it seems stuck, the user can exit CC mode and re-enter. The session state is persisted and can be resumed.

## Edge Cases

### Interactive commands don't work through the gateway

Any command that requires user input (stdin) will fail or hang. This includes:
- QR code scans (`wacli auth`)
- Password prompts
- Browser-based OAuth flows
- Confirmation dialogs

**Rule:** Always do initial auth/setup directly on the host terminal, not through Ciana.

### Large output gets truncated

`host_execute` truncates output at 15,000 characters. For commands that produce very long output, use `--limit`, `--json`, or pagination flags to reduce output size.

### Gateway runs on the host, not in Docker

The gateway process must run on the macOS host because it needs access to native apps (Messages, Reminders, Spotify, etc.). Docker containers can't access these.

The container reaches the host via `http://host.docker.internal:9842`.
