---
name: gifgrep
description: "Search for GIFs and animated images. Use when user asks for a GIF, reaction image, or animated content. No API key needed."
---

# GIF Search

Find GIFs and animated images for any topic or reaction.

## When to Use

- "Send me a funny GIF"
- "Find a GIF of [topic]"
- "Reaction GIF for [emotion]"
- User asks for animated content

## How to Search

Use `web_search` to find GIFs on popular platforms:

```
web_search("site:giphy.com [topic] gif")
web_search("site:tenor.com [topic] gif")
```

## Direct URL Patterns

### Giphy

- Page: `https://giphy.com/gifs/SLUG-ID`
- Direct GIF: `https://media.giphy.com/media/ID/giphy.gif`
- Smaller: `https://media.giphy.com/media/ID/200.gif`

### Tenor

- Page: `https://tenor.com/view/SLUG-ID`
- Fetch the page with `web_fetch` to extract the direct media URL

## Response Format

When sharing a GIF, provide:
1. The direct GIF URL (renders inline in most chat apps)
2. A brief description of what the GIF shows

## Notes

- No API key needed — uses web search
- Prefer Giphy and Tenor for reliable hosting
- Direct GIF URLs render inline in Telegram
