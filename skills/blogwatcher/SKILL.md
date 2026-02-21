---
name: blogwatcher
description: "Monitor RSS/Atom feeds for new articles. Use when user asks to track blogs, news sources, or content updates. No API key needed."
---

# Blog Watcher

Monitor blogs and news sources via RSS/Atom feeds.

## When to Use

- "Check if there's anything new on [blog]"
- "Monitor this RSS feed for updates"
- "What's the latest on [tech blog]?"
- Setting up scheduled blog monitoring

## Commands

### Fetch an RSS Feed

```bash
curl -s "https://example.com/feed" | head -100
```

### Common Feed URL Patterns

Most blogs have feeds at predictable URLs:
- `/feed` or `/rss` or `/atom.xml`
- `/feed.xml` or `/index.xml`
- WordPress: `/feed/`
- Medium: `/feed`
- Substack: `/feed`

### Extract Titles and Links

```bash
# Titles
curl -s "https://example.com/feed" | grep -oP '(?<=<title>).*?(?=</title>)'

# Links
curl -s "https://example.com/feed" | grep -oP '(?<=<link>).*?(?=</link>)'
```

### JSON Feed (if available)

```bash
curl -s "https://example.com/feed/json" | jq '.items[:5] | .[] | {title, url, date_published}'
```

## Workflow: Periodic Monitoring

1. Find the blog's RSS feed URL
2. Verify it works: `curl -s "URL" | head -20`
3. Set up a scheduled task with `schedule_task` to check periodically
4. Save last-seen entries to compare on next check

## Notes

- No API key needed
- Works with any standard RSS 2.0 or Atom feed
- Some sites block curl — add a User-Agent: `curl -s -H "User-Agent: CianaParrot/1.0" "URL"`
- Use `schedule_task` for periodic monitoring
