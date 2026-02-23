---
name: whatsapp
description: "Send and read WhatsApp messages via the wacli CLI. Search chats, view history, send text and files to contacts or groups."
requires_bridge: "whatsapp"
---

# WhatsApp

Use the `whatsapp` bridge to read and send WhatsApp messages via the wacli CLI.

## When to Use

- User asks to send a WhatsApp message
- Reading WhatsApp conversation history
- Searching WhatsApp chats or messages

## When NOT to Use

- Telegram messages -> reply normally (Ciana routes automatically)
- iMessage/SMS -> use the `imessage` bridge
- Any other messaging platform

## Commands

All commands run via `host_execute(bridge="whatsapp", command="...")`.

### List Chats

```
wacli chats list --limit 20
wacli chats list --limit 20 --query "John"
```

### Search Messages

```
wacli messages search "query" --limit 20
wacli messages search "query" --limit 20 --chat <jid>
wacli messages search "query" --after 2025-01-01 --before 2025-02-01
```

### Send Text

```
wacli send text --to "+14155551212" --message "Hello!"
```

For groups, use JID format:

```
wacli send text --to "1234567890-123456789@g.us" --message "Hello group!"
```

### Send File

```
wacli send file --to "+14155551212" --file /path/to/image.jpg --caption "Check this"
```

### Auth & Sync

```
wacli auth
wacli sync --follow
wacli doctor
```

## Contact Resolution

When the user asks to message someone by name (e.g. "send a message to Marco"), **never say you don't have the number**. Instead:

1. Search chats first: `wacli chats list --query "Marco"`
2. If found, use the JID or phone number from the result to send
3. If multiple matches, show the list and ask the user to pick
4. Only if no match is found, ask the user for the number

## Safety Rules

1. **Always confirm recipient and message content** before sending
2. **Never send to unknown numbers** without explicit user approval
3. **Rate limit** - don't spam

## Setup (on host)

- Install: `brew install steipete/tap/wacli`
- Authenticate: `wacli auth` (scan QR code with WhatsApp on phone)
- Initial sync: `wacli sync --follow`
- Add `whatsapp` bridge in `config.yaml`, restart gateway
