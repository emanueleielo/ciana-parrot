---
name: session-logs
description: "Search and analyze your own past session logs with jq. Useful for recalling previous conversations, finding decisions, or reviewing what happened."
---

# Session Logs

Search and analyze past conversation sessions stored as JSONL files.

## When to Use

- "What did we talk about yesterday?"
- "Find where I decided about [topic]"
- "Show recent sessions"
- "What happened in our last conversation?"
- Self-review and continuity across sessions

## Session File Location

Sessions are stored in `sessions/` as JSONL files named by thread ID:
```
sessions/telegram_12345.jsonl
sessions/telegram_12345_s2.jsonl
```

Each line is a JSON object with message data (role, content, timestamp, etc.).

## List Recent Sessions

```bash
ls -lt sessions/*.jsonl | head -20
```

## Search Across All Sessions

```bash
jq -r 'select(.content | test("keyword"; "i")) | "\(.timestamp // "?") [\(.role // "?")]: \(.content[:200])"' sessions/*.jsonl
```

## Show Last N Messages from a Session

```bash
tail -20 sessions/telegram_12345.jsonl | jq -r '"\(.role // "?"): \(.content[:300])"'
```

## Count Messages per Session

```bash
for f in sessions/*.jsonl; do echo "$(wc -l < "$f") $f"; done | sort -rn | head -20
```

## Find Sessions by Date

```bash
jq -r 'select(.timestamp >= "2025-01-15") | .content[:100]' sessions/*.jsonl
```

## Notes

- Use `jq` for JSON processing (already available)
- JSONL = one JSON object per line
- Always use case-insensitive search with `"i"` flag in jq regex
- Truncate output with `[:200]` to avoid flooding
