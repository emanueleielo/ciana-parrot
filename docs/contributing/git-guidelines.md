---
title: Git Guidelines
---

# Git Guidelines

This page covers the git workflow, commit conventions, protected files, and pre-commit hooks used in CianaParrot.

---

## Protected Files

Certain files must **never be committed**. These are either runtime-generated or contain personal data.

### Files you must not commit

| File | Reason | Protection |
|------|--------|------------|
| `data/session_counters.json` | Auto-created at runtime | Listed in `.gitignore` |
| `workspace/MEMORY.md` | Contains the user's personal data | Hidden via `git update-index --skip-worktree` |
| Files in `.git/info/exclude` | Local-only ignores (skills with user data, local analysis docs, local project clones) | Git's local exclude mechanism |

!!! danger "workspace/MEMORY.md"
    The agent's memory file is the most important file to protect. It accumulates personal information about the user over time. The template is committed to the repository, but your local changes must never be pushed.

### After a fresh clone

Always run this command after cloning the repository:

```bash
git update-index --skip-worktree workspace/MEMORY.md
```

This tells git to ignore local modifications to `MEMORY.md`, even though the file is tracked.

### Before every commit

Run `git status` and verify that `workspace/MEMORY.md` does **not** appear in the changeset:

```bash
git status
```

!!! warning "If MEMORY.md shows up in git status"
    The skip-worktree flag may have been reset (this can happen after certain git operations like `stash` or `checkout`). Re-apply it immediately:
    ```bash
    git update-index --skip-worktree workspace/MEMORY.md
    ```

---

## `.git/info/exclude` vs `.gitignore`

CianaParrot uses both mechanisms for ignoring files, and they serve different purposes:

| Mechanism | Scope | Use For |
|-----------|-------|---------|
| `.gitignore` | Shared with all contributors (committed) | Standard ignores: `.env`, `__pycache__`, `*.pyc`, build artifacts |
| `.git/info/exclude` | Local to your clone only (never committed) | Personal ignores: skills with user data, local analysis docs, local project clones |

!!! note "Do not move exclude entries to .gitignore"
    Entries in `.git/info/exclude` are intentionally local-only. They reflect your personal development setup and should not be imposed on other contributors.

---

## Commit Messages

Use **conventional commits** style for all commit messages. This keeps the git history readable and enables automated tooling.

### Format

```
type(scope): short description

Optional longer description explaining the "why" behind the change.
```

### Types

| Type | Use For |
|------|---------|
| `feat` | A new feature |
| `fix` | A bug fix |
| `chore` | Maintenance tasks (dependency updates, config changes) |
| `refactor` | Code restructuring without behavior change |
| `test` | Adding or updating tests |
| `docs` | Documentation changes |
| `style` | Formatting, whitespace (no logic changes) |
| `perf` | Performance improvements |

### Examples

```
feat(telegram): add voice message transcription support

fix(scheduler): prevent duplicate execution of one-shot tasks

chore: update langchain to 0.3.x

refactor(gateway): extract bridge validation into separate module

test(router): add coverage for group chat trigger detection

docs: add bridge architecture diagram
```

!!! tip "Scope is optional but helpful"
    The scope (in parentheses) identifies which part of the codebase is affected. Common scopes: `telegram`, `gateway`, `scheduler`, `config`, `tools`, `bridge`.

---

## Pre-Commit Hooks

The repository includes a **gitleaks** pre-commit hook for secret scanning. This runs automatically before each commit and blocks the commit if it detects potential secrets (API keys, tokens, passwords).

```bash
# The hook runs automatically on git commit
git commit -m "feat: add new feature"
# If gitleaks finds a potential secret, the commit is rejected
```

!!! info "What gitleaks checks"
    Gitleaks scans staged changes for patterns that look like API keys, tokens, passwords, and other secrets. If your commit is blocked, review the flagged content and either:

    - Remove the secret and use an environment variable instead
    - If it is a false positive, add an inline `# gitleaks:allow` comment

---

## Branching

When contributing a feature or fix:

1. **Create a feature branch** from `main`:
    ```bash
    git checkout -b feat/my-new-feature
    ```

2. **Make your changes** with focused, atomic commits.

3. **Run the test suite** before pushing:
    ```bash
    make test
    ```

4. **Push and open a pull request** against `main`.

---

## Pre-Commit Checklist

Before every commit, run through this checklist:

- [ ] `git status` -- verify `workspace/MEMORY.md` is **not** in the changeset
- [ ] `make test` -- all tests pass
- [ ] No secrets in staged files (gitleaks will catch most, but double-check)
- [ ] Commit message follows conventional commits format
- [ ] Changes are focused -- one logical change per commit

---

## Summary

| Rule | Details |
|------|---------|
| Never commit `workspace/MEMORY.md` | Protected via `skip-worktree`; re-apply after clone |
| Never commit `data/session_counters.json` | Runtime file, in `.gitignore` |
| Local ignores go in `.git/info/exclude` | Not in `.gitignore` |
| Conventional commits | `type(scope): description` |
| Pre-commit hook | gitleaks scans for secrets automatically |
| Run `git status` before committing | Verify no protected files appear |
| Run `make test` before pushing | All 506 tests should pass |
