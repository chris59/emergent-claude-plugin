# Git Workflow Reference

Generic git branching and PR workflow for ADO-tracked .NET projects.

---

## Branch Strategy

| Branch | Purpose | Direct push? |
|--------|---------|-------------|
| `main` | Production releases | Never |
| `develop` | Integration branch | Never |
| `feature/...` | All development work | Yes (own branch) |
| `hotfix/...` | Emergency production fixes | Yes (own branch) |

**Never commit or push directly to `develop` or `main`.** All changes flow through
a feature branch and a pull request.

---

## Feature Branch Naming

```
feature/{username}/{storyId}-{short-description}
```

Examples:
```
feature/janedoe/1042-add-forecast-endpoint
feature/bobsmith/983-fix-dealer-login-timeout
```

Rules:
- `{username}` — your ADO/Git username (no spaces, all lowercase).
- `{storyId}` — the ADO work item ID linking the branch to a story. **Required** for all
  branches targeting production code. The stamp-review pre-push hook enforces this.
- `{short-description}` — kebab-case, 3–6 words, describes the change.

Hotfix branches follow the same pattern, substituting `hotfix/` for `feature/`:
```
hotfix/janedoe/1101-fix-null-ref-in-export
```

---

## Creating a Feature Branch

```bash
# Start from the latest develop
git checkout develop
git pull origin develop

# Create and switch to the feature branch
git checkout -b feature/janedoe/1042-add-forecast-endpoint

# Push and set tracking
git push -u origin feature/janedoe/1042-add-forecast-endpoint
```

---

## Pre-Push Quality Checks

The pre-push hook at `tools/emergent-claude-plugin/hooks/pre-push-quality-checks.py` runs
automatically on every push. It enforces:

1. **Format check** — `dotnet format <solution>.sln whitespace --verify-no-changes`
2. **Build** — `dotnet build <solution>.slnf`
3. **Tests** — unit and architecture tests

Fix locally before pushing:

```bash
# Fix formatting
dotnet format <solution>.sln

# Verify build
dotnet build <solution>.slnf
```

If the hook rejects the push, fix the issue and push again. Do not bypass hooks with
`--no-verify`.

---

## Pull Request Requirements

### ADO Story link (enforced by stamp-review)
Every PR to `develop` or `main` must link an ADO story. The story ID in the branch name
(`feature/janedoe/{storyId}-...`) is used to auto-stamp the PR. Branches without a
story ID are blocked from merging to production branches.

Exception: `.claude/` documentation changes are exempt from the story requirement.

### PR description format
Use this structure for all PRs:

```markdown
## Summary
- Bullet 1: what changed
- Bullet 2: why

## Motivation
One paragraph explaining the business or technical driver.

## Implementation Details
- Key design decisions
- Non-obvious trade-offs
- Any schema or API changes

## Testing & Verification
- [ ] Unit tests added / updated
- [ ] Tested locally against dev database
- [ ] Regression suite passed (if pipeline change)

## Related Resources
- ADO Story: #{storyId}
- PR: #{relatedPrId} (if related)
```

### Merge strategy
- **Squash merge** — one clean commit per PR on `develop`.
- **Delete source branch** after merge — set auto-complete with "Delete source branch" checked.

---

## Auto-Complete Policy

After creating a PR and verifying the AI code review is clean (0 Critical, 0 Major
real issues), **set auto-complete immediately**. Do not wait for the user to ask.

Workflow:
1. Implement changes locally.
2. Build + run tests.
3. User approves locally.
4. Commit, push, create PR.
5. Poll for AI code review (up to 5 minutes).
6. Fix all real Major/Critical issues. Push fixes.
7. Poll again until review is clean.
8. Set auto-complete.

False positives from AI review (documented in `.claude/ai-review-findings.md`) do not
block auto-complete.

---

## Commit Messages

Use imperative mood, present tense, ≤72 characters on the first line:

```
Add forecast endpoint for dealer portal

- Implements GetForecastQuery handler
- Adds /api/dealer/forecast route
- Wires up typed HTTP client in Web.Dealer
```

Reference the ADO story where relevant:
```
Fix null reference in export handler (#1042)
```

---

## After Merge

1. Delete the remote feature branch (auto-complete handles this if configured).
2. Delete the local branch:
   ```bash
   git checkout develop
   git pull origin develop
   git branch -d feature/janedoe/1042-add-forecast-endpoint
   ```
3. Close or transition the ADO story to the next state.

---

## Emergency Hotfixes

For critical production bugs:

```bash
# Branch from main, not develop
git checkout main
git pull origin main
git checkout -b hotfix/janedoe/1101-fix-null-ref-in-export

# After fix, PR into both main AND develop
gh pr create --base main --title "..."
gh pr create --base develop --title "..."
```

Both PRs must be merged to keep `develop` in sync with `main`.
