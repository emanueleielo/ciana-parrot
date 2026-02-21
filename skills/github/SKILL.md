---
name: github
description: "GitHub operations: list/create issues, PRs, check CI, manage repos. Requires GH_TOKEN."
requires_env:
  - GH_TOKEN
---

# GitHub

Manage repositories, issues, pull requests, and CI workflows on GitHub.

## When to Use

- "Check my GitHub issues"
- "Create an issue for [bug]"
- "What's the status of PR #42?"
- "List open PRs on [repo]"

## Auth

All requests require:
```
Authorization: Bearer $GH_TOKEN
Accept: application/vnd.github+json
```

## Key Endpoints

Base URL: `https://api.github.com`

### List Issues

```bash
curl -s "https://api.github.com/repos/OWNER/REPO/issues?state=open&per_page=10" \
  -H "Authorization: Bearer $GH_TOKEN" \
  -H "Accept: application/vnd.github+json"
```

### Create an Issue

```bash
curl -s -X POST "https://api.github.com/repos/OWNER/REPO/issues" \
  -H "Authorization: Bearer $GH_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  -H "Content-Type: application/json" \
  -d '{"title": "Bug: ...", "body": "Description...", "labels": ["bug"]}'
```

### List Pull Requests

```bash
curl -s "https://api.github.com/repos/OWNER/REPO/pulls?state=open&per_page=10" \
  -H "Authorization: Bearer $GH_TOKEN" \
  -H "Accept: application/vnd.github+json"
```

### Comment on Issue/PR

```bash
curl -s -X POST "https://api.github.com/repos/OWNER/REPO/issues/NUMBER/comments" \
  -H "Authorization: Bearer $GH_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  -H "Content-Type: application/json" \
  -d '{"body": "Comment text..."}'
```

### Check CI Status

```bash
curl -s "https://api.github.com/repos/OWNER/REPO/commits/REF/check-runs" \
  -H "Authorization: Bearer $GH_TOKEN" \
  -H "Accept: application/vnd.github+json"
```

### Search Issues/PRs

```bash
curl -s "https://api.github.com/search/issues?q=repo:OWNER/REPO+is:open+label:bug" \
  -H "Authorization: Bearer $GH_TOKEN" \
  -H "Accept: application/vnd.github+json"
```

### List User's Repos

```bash
curl -s "https://api.github.com/user/repos?sort=updated&per_page=10" \
  -H "Authorization: Bearer $GH_TOKEN" \
  -H "Accept: application/vnd.github+json"
```

## Notes

- Rate limit: 5000 requests/hour with token
- Use `per_page` and `page` for pagination
- For private repos, the token needs `repo` scope
- Get a token: https://github.com/settings/tokens
