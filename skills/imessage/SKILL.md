---
name: imessage
description: "Send and read iMessage/SMS via Messages.app using the imsg CLI. List chats, view history, send messages to phone numbers or Apple IDs."
requires_bridge: "imessage"
---

# iMessage

Use the `imessage` bridge to read and send iMessage/SMS via macOS Messages.app.

## When to Use

- User asks to send an iMessage or SMS
- Reading iMessage conversation history
- Checking recent chats

## When NOT to Use

- Telegram messages -> reply normally (Ciana routes automatically)
- Any other messaging platform

## Commands

All commands run via `host_execute(bridge="imessage", command="...")`.

### List Chats

```
imsg chats --limit 10 --json
```

### View History

```
imsg history --chat-id 1 --limit 20 --json
imsg history --chat-id 1 --limit 20 --attachments --json
```

### Send Messages

```
imsg send --to "+14155551212" --text "Hello!"
imsg send --to "+14155551212" --text "Check this" --file /path/to/image.jpg
imsg send --to "+14155551212" --text "Hi" --service imessage
imsg send --to "+14155551212" --text "Hi" --service sms
```

## Safety Rules

1. **Always confirm recipient and message content** before sending
2. **Never send to unknown numbers** without explicit user approval
3. **Rate limit** - don't spam

## Setup (on host)

- Install: `brew install steipete/tap/imsg`
- macOS with Messages.app signed in
- Grant Full Disk Access and Automation permission for Messages.app
- Uncomment `imessage` bridge in `config.yaml`, restart gateway
