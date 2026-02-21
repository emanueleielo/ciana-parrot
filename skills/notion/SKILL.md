---
name: notion
description: "Manage Notion workspace: create pages, query databases, add content blocks. Requires NOTION_API_KEY."
requires_env:
  - NOTION_API_KEY
---

# Notion

Create pages, query databases, and manage content in Notion.

## When to Use

- "Add this to Notion"
- "Create a Notion page about..."
- "Query my Notion database"
- "Update the [project] page in Notion"

## Auth

All requests require:
```
Authorization: Bearer $NOTION_API_KEY
Notion-Version: 2022-06-28
Content-Type: application/json
```

## Key Endpoints

Base URL: `https://api.notion.com/v1`

### Search

```bash
curl -s -X POST "https://api.notion.com/v1/search" \
  -H "Authorization: Bearer $NOTION_API_KEY" \
  -H "Notion-Version: 2022-06-28" \
  -H "Content-Type: application/json" \
  -d '{"query": "meeting notes", "page_size": 5}'
```

### Create a Page

```bash
curl -s -X POST "https://api.notion.com/v1/pages" \
  -H "Authorization: Bearer $NOTION_API_KEY" \
  -H "Notion-Version: 2022-06-28" \
  -H "Content-Type: application/json" \
  -d '{
    "parent": {"database_id": "DATABASE_ID"},
    "properties": {
      "Name": {"title": [{"text": {"content": "Page Title"}}]}
    },
    "children": [
      {
        "object": "block",
        "type": "paragraph",
        "paragraph": {
          "rich_text": [{"type": "text", "text": {"content": "Content here"}}]
        }
      }
    ]
  }'
```

### Query a Database

```bash
curl -s -X POST "https://api.notion.com/v1/databases/DATABASE_ID/query" \
  -H "Authorization: Bearer $NOTION_API_KEY" \
  -H "Notion-Version: 2022-06-28" \
  -H "Content-Type: application/json" \
  -d '{"page_size": 10}'
```

### Get a Page

```bash
curl -s "https://api.notion.com/v1/pages/PAGE_ID" \
  -H "Authorization: Bearer $NOTION_API_KEY" \
  -H "Notion-Version: 2022-06-28"
```

### Add Blocks to a Page

```bash
curl -s -X PATCH "https://api.notion.com/v1/blocks/BLOCK_ID/children" \
  -H "Authorization: Bearer $NOTION_API_KEY" \
  -H "Notion-Version: 2022-06-28" \
  -H "Content-Type: application/json" \
  -d '{
    "children": [
      {
        "object": "block",
        "type": "to_do",
        "to_do": {
          "rich_text": [{"type": "text", "text": {"content": "Task item"}}],
          "checked": false
        }
      }
    ]
  }'
```

## Block Types

- `paragraph`, `heading_1`, `heading_2`, `heading_3`
- `to_do` (checkbox), `bulleted_list_item`, `numbered_list_item`
- `code` (add `"language": "python"`), `toggle`

## Notes

- API key = Notion internal integration token
- Integration must be connected to pages/databases in Notion UI
- Rate limit: 3 requests/second
- Max 100 blocks per request
