---
name: trello
description: "Manage Trello boards: list/create/move cards, checklists, labels. Requires TRELLO_API_KEY and TRELLO_TOKEN."
requires_env:
  - TRELLO_API_KEY
  - TRELLO_TOKEN
---

# Trello

Manage boards, lists, and cards on Trello for project management.

## When to Use

- "What's on my Trello board?"
- "Add a card for [task]"
- "Move [card] to Done"
- "What are my Trello tasks?"

## Auth

All requests append query params:
```
?key=$TRELLO_API_KEY&token=$TRELLO_TOKEN
```

## Key Endpoints

Base URL: `https://api.trello.com/1`

### List My Boards

```bash
curl -s "https://api.trello.com/1/members/me/boards?key=$TRELLO_API_KEY&token=$TRELLO_TOKEN&fields=name,url"
```

### Get Board Lists (columns)

```bash
curl -s "https://api.trello.com/1/boards/BOARD_ID/lists?key=$TRELLO_API_KEY&token=$TRELLO_TOKEN&fields=name"
```

### Get Cards on a List

```bash
curl -s "https://api.trello.com/1/lists/LIST_ID/cards?key=$TRELLO_API_KEY&token=$TRELLO_TOKEN&fields=name,desc,due,labels"
```

### Create a Card

```bash
curl -s -X POST "https://api.trello.com/1/cards?key=$TRELLO_API_KEY&token=$TRELLO_TOKEN" \
  -d "idList=LIST_ID&name=Task+Name&desc=Description"
```

### Move a Card

```bash
curl -s -X PUT "https://api.trello.com/1/cards/CARD_ID?key=$TRELLO_API_KEY&token=$TRELLO_TOKEN" \
  -d "idList=NEW_LIST_ID"
```

### Archive a Card

```bash
curl -s -X PUT "https://api.trello.com/1/cards/CARD_ID?key=$TRELLO_API_KEY&token=$TRELLO_TOKEN" \
  -d "closed=true"
```

## Workflow

1. List boards to find the right one
2. Get board lists (columns) to understand the workflow
3. Get cards for the relevant list
4. Create/move/update cards as needed

## Notes

- Get API key: https://trello.com/app-key
- Generate token: link on the API key page
- Rate limit: 100 requests per 10 seconds
