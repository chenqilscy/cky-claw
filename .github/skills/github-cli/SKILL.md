---
name: github-cli
description: Use when needing to interact with GitHub repositories, issues, pull requests, releases, actions CI/CD, labels, milestones, tags, or file content via the gh CLI tool. Triggers on GitHub API operations, repository management, CI/CD pipeline management, issue tracking, PR management, or any task requiring gh commands.
---

# github-cli

GitHub official CLI (`gh`) for GitHub REST/GraphQL API. Every call is an independent request, safe for concurrent use.

## Binary Location

```bash
# Default install path on Windows
GH="/c/Program Files/GitHub CLI/gh.exe"

# If in PATH (Linux/macOS or after Windows PATH update)
GH="gh"
```

Always use the full path `$GH` in bash sessions unless `gh` is in PATH.

## Agent Rules

1. **Always use full path** — Use `"/c/Program Files/GitHub CLI/gh.exe"` when `gh` not in PATH
2. **Verify before destructive ops** — Run `list`/`view` first before closing/deleting
3. **Use `--repo` flag** — Specify repo explicitly: `--repo owner/repo`
4. **JSON output for parsing** — Use `--json` flag when processing results programmatically

## Common Commands

### Issues

```bash
# List issues
$GH issue list --repo owner/repo [--state open|closed|all] [--label label] [--assignee user] [--limit N]

# View issue detail
$GH issue view <number> --repo owner/repo

# Create issue
$GH issue create --repo owner/repo --title "Title" --body "Description" [--label bug] [--assignee user]

# Close issue
$GH issue close <number> --repo owner/repo

# Reopen issue
$GH issue reopen <number> --repo owner/repo

# Add comment
$GH issue comment <number> --repo owner/repo --body "Comment text"

# Edit issue
$GH issue edit <number> --repo owner/repo --title "New title" --body "New body"

# List issue comments
$GH issue view <number> --repo owner/repo --comments
```

### Pull Requests

```bash
# List PRs
$GH pr list --repo owner/repo [--state open|closed|merged|all] [--author user] [--label label]

# View PR detail
$GH pr view <number> --repo owner/repo

# Create PR
$GH pr create --repo owner/repo --title "Title" --body "Description" [--base main] [--head branch]

# Merge PR
$GH pr merge <number> --repo owner/repo [--merge|--squash|--rebase]

# Close PR
$GH pr close <number> --repo owner/repo

# Checkout PR locally
$GH pr checkout <number> --repo owner/repo

# Review PR
$GH pr review <number> --repo owner/repo --approve|--request-changes|--comment --body "Review text"

# View PR checks
$GH pr checks <number> --repo owner/repo
```

### Repositories

```bash
# View repo info
$GH repo view owner/repo

# Clone repo
$GH repo clone owner/repo [directory]

# List repo issues/PRs (shorthand, no --repo needed inside a repo)
$GH issue list
$GH pr list

# Create repo
$GH repo create name [--public|--private] [--description "desc"]
```

### Actions / CI-CD

```bash
# List workflow runs
$GH run list --repo owner/repo [--workflow name] [--limit N]

# View run detail
$GH run view <run-id> --repo owner/repo

# View run logs
$GH run view <run-id> --repo owner/repo --log

# Re-run failed jobs
$GH run rerun <run-id> --repo owner/repo [--failed]

# List workflows
$GH workflow list --repo owner/repo

# Trigger workflow
$GH workflow run <workflow-name> --repo owner/repo [--ref branch] [-f key=value]
```

### Releases & Tags

```bash
# List releases
$GH release list --repo owner/repo [--limit N]

# Create release
$GH release create <tag> --repo owner/repo --title "Title" --notes "Notes" [--draft] [--prerelease]

# Upload assets
$GH release upload <tag> <file> --repo owner/repo

# Delete release
$GH release delete <tag> --repo owner/repo --yes

# List tags
$GH api repos/owner/repo/tags --jq '.[].name'
```

### Labels & Milestones

```bash
# Labels
$GH label list --repo owner/repo
$GH label create "name" --repo owner/repo --color "RRGGBB" --description "desc"
$GH label delete "name" --repo owner/repo --yes

# Milestones
$GH api repos/owner/repo/milestones --jq '.[].title'
```

### API (raw access)

```bash
# GET
$GH api repos/owner/repo/issues --jq '.[].title'

# POST
$GH api repos/owner/repo/issues -f title="Title" -f body="Body"

# With pagination
$GH api repos/owner/repo/issues --paginate --jq '.[].title'
```

## Common Workflows

**Issue lifecycle** — `issue list` → `issue view <n>` → `issue comment <n>` → `issue close <n>`
**PR lifecycle** — `pr create` → `pr checks <n>` → `pr review <n>` → `pr merge <n>`
**Release** — `release create <tag>` → `release upload <tag> <file>`
**CI debugging** — `run list` → `run view <id>` → `run view <id> --log`

## Error Handling

| Error | Fix |
|-------|-----|
| `command not found` | Use full path `"/c/Program Files/GitHub CLI/gh.exe"` |
| `401 Unauthorized` | Run `gh auth login` |
| `404 Not Found` | Verify owner/repo name |
| `422 Validation Failed` | Check required fields |
| `rate limit exceeded` | Wait or use `--jq` to reduce data |

Destructive ops (close, delete, merge): always `view`/`list` first. Deleted resources cannot be recovered.
