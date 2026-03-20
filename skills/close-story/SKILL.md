---
name: close-story
description: Close out a story — verify ACs, format/build/test, commit, push, create PR, monitor AI review, set auto-complete, and close the ADO work item. Use when implementation is done and you're ready to ship.
user-invocable: true
argument-hint: <story-id>
---

# Close Story

Ship a completed story: verify every AC was met, detect scope creep, get user approval, commit, push, create PR, handle AI review, and close the ADO work item with full documentation.

## Arguments

- `1279` or `#1279` — the ADO work item ID (required)

## Instructions

Follow these steps in order. Use Bash for all `az` and `git` commands.

### Step 0: Load Project Configuration

Read the shared preamble at `tools/emergent-claude-plugin/skills/shared-preamble.md` and follow it exactly. Extract and store:

From `.claude/project.env.md` (required):
- `{ADO_ORG}` — organization URL (e.g., `https://dev.azure.com/MyOrg`)
- `{ADO_PROJECT}` — project name, may contain spaces (e.g., `My Project`)
- `{ADO_PROJECT_ENCODED}` — URL-encoded project name (e.g., `My%20Project`)
- `{ADO_REPO_ID}` — repository GUID
- `{BRANCH_USERNAME}` — username for branch naming

From `.claude/project.architecture.md` (recommended, fall back to auto-detect):
- `{FORMAT_CMD}` — format command (default: `dotnet format whitespace {SOLUTION}`)
- `{BUILD_CMD}` — build command (default: `dotnet build {SOLUTION} -c Release`)
- `{TEST_CMD}` — test command (default: `dotnet test {SOLUTION} -c Release --no-build`)

From `.claude/project.testing.md` (optional):
- `{SCSS_CMD}` — SCSS compilation command (skip Step 4 SCSS sub-step if not defined)
- `{DB_BUILD_CMD}` — database build command (skip Step 4 DB sub-step if not defined)

From `.claude/project.team.md` (optional):
- `{MERGE_STRATEGY}` — PR merge strategy (default: `squash`)

Configure az defaults:
```bash
az devops configure --defaults organization={ADO_ORG} project="{ADO_PROJECT}"
```

### Step 1: Fetch Story Context

1. Fetch the story and its parent Feature:
   ```bash
   az boards work-item show --id {id} --output json
   ```
   Extract: Title, State, Story Points, Description, Acceptance Criteria, Parent (Feature ID + title).

2. Fetch the parent Feature (for PR description business context):
   ```bash
   az boards work-item show --id {parentId} --output json
   ```

3. Get the current branch name and verify we're on a feature branch:
   ```bash
   git branch --show-current
   ```
   If on `develop` or `main`, **STOP** — cannot close a story without a feature branch.

### Step 2: AC Verification Checklist

Map every acceptance criterion to what was implemented. Read the changed files to understand what was done.

```bash
git diff develop --name-only
```

Present a checklist to the user:

```
Acceptance Criteria Verification:
  ✅ AC1: {AC text} — {what was implemented and where}
  ✅ AC2: {AC text} — {what was implemented and where}
  ⚠️  AC3: {AC text} — {implemented but lacks test coverage}
  ❌ AC4: {AC text} — {not yet implemented}
```

- If ANY AC is ❌, flag it. Use **AskUserQuestion**: "AC4 is not implemented. Skip it (defer to follow-up story) or implement now?"
- If any AC is ⚠️, note it but don't block.

### Step 3: Scope Creep Detection

Map every changed file to an AC:

```
Files Modified → AC Mapping:
  ProductForecastRow.cs → AC1, AC2, AC3, AC9, AC11, AC13
  DealerForecast.razor → AC1-14
  InventoryAvailableModal.razor (NEW) → AC8
  dealer-forecast.scss → AC1-3, AC5-7, AC11
  ⚠️ check-story/SKILL.md → No AC (tooling change)
```

Files that don't map to any AC are scope creep candidates. Use **AskUserQuestion**: "These files were modified but don't map to any AC. Include in this PR or revert?"

Options:
- "Include — they're related improvements"
- "Split — create a separate commit/PR for non-AC changes"
- "Revert — remove them from this branch"

### Step 4: Format, Build, Test

Run in sequence — each must pass before proceeding:

1. **Format**: `{FORMAT_CMD}` then `git add -u`
2. **Build**: `{BUILD_CMD}` — must be 0 errors, 0 warnings
3. **Test**: `{TEST_CMD}` — must pass
4. **SCSS compile** (if `{SCSS_CMD}` is defined AND any `.scss` files changed):
   ```bash
   {SCSS_CMD}
   ```
   Verify no errors. Stage the compiled output: `git add {compiled-css-path}`
5. **Database build** (if `{DB_BUILD_CMD}` is defined AND any `.sql` files changed):
   ```bash
   {DB_BUILD_CMD}
   ```

If any step fails, fix the issue and re-run. Do NOT proceed with failures.

### Step 5: User Approval Gate

Present a summary and ask for approval:

```
Ready to ship Story #{id}: {title}

  ACs verified: {count}/{total}
  Files changed: {count}
  Build: ✅ clean
  Tests: ✅ {count} passed

  Test plan:
  1. {specific thing to test}
  2. {specific thing to verify}
```

Use **AskUserQuestion**: "Have you tested locally and approved the changes?"
- "Yes, approved — commit and push"
- "No, I found issues"

**DO NOT PROCEED** until the user approves.

### Step 6: Commit and Push

1. **Stage files**: `git add` specific files (not `git add -A`). Include any compiled output (e.g., minified CSS) if a build step produced it.

2. **Commit** with a descriptive message via HEREDOC:
   ```bash
   git commit -m "$(cat <<'EOF'
   {Descriptive message explaining the "why"}

   Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
   EOF
   )"
   ```

3. **Stamp review**: `bash .claude/hooks/stamp-review.sh` (separate command)

4. **Push**: `git push -u origin {branch}` (separate command after stamp)

### Step 7: Create PR

Create a PR targeting `develop` with structured description:

```bash
az repos pr create --repository "{ADO_PROJECT}" --source-branch {branch} --target-branch develop \
  --title "{short title}" --work-items {id} --description "$(cat <<'EOF'
## Summary
[One-sentence linking to business value]

## Motivation
[Reference parent Feature/Epic and business need]

## Implementation Details
*   [Key technical changes]

## Acceptance Criteria Verification
| AC | Status | Implementation |
|----|--------|---------------|
| AC1: {text} | ✅ | {file and approach} |

## Testing & Verification
1.  [How to test]

## Related Resources
*   [ADO Story #{id}]({ADO_ORG}/{ADO_PROJECT_ENCODED}/_workitems/edit/{id})
*   Parent: [Feature #{parentId}]({ADO_ORG}/{ADO_PROJECT_ENCODED}/_workitems/edit/{parentId})

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Extract the PR ID from the response.

**Check for merge conflicts immediately:**
```bash
token=$(az account get-access-token --resource 499b84ac-1321-427f-aa17-267ca6975798 --query accessToken -o tsv 2>/dev/null)
curl -s -H "Authorization: Bearer $token" \
  "{ADO_ORG}/{ADO_PROJECT_ENCODED}/_apis/git/repositories/{ADO_REPO_ID}/pullrequests/{prId}?api-version=7.0" \
  | python -c "import sys,json; pr=json.load(sys.stdin); print(pr.get('mergeStatus','?'))"
```
If `conflicts`: rebase, stamp, force-push, re-check.

### Step 8: Poll Build & AI Review

**Run polling as background tasks.**

1. **Poll for build completion** (background, up to 10 minutes):
   ```bash
   token=$(az account get-access-token --resource 499b84ac-1321-427f-aa17-267ca6975798 --query accessToken -o tsv 2>/dev/null)
   for i in $(seq 1 40); do
     result=$(curl -s -H "Authorization: Bearer $token" \
       "{ADO_ORG}/{ADO_PROJECT_ENCODED}/_apis/build/builds?\$top=10&api-version=7.0" \
       | python -c "
   import sys,json
   builds=json.load(sys.stdin)['value']
   target=[b for b in builds if b.get('sourceBranch')=='refs/pull/{prId}/merge']
   if target:
       b=target[0]
       print(b['id'], b['status'], b.get('result',''))
   else:
       print('no-build-yet')
   " 2>/dev/null)
     echo "[$i] $result"
     if echo "$result" | grep -q "completed"; then echo "BUILD_DONE: $result"; break; fi
     sleep 15
   done
   ```

2. **Poll for AI review** (background, after build completes):
   ```bash
   for i in $(seq 1 20); do
     result=$(curl -s -H "Authorization: Bearer $token" \
       "{ADO_ORG}/{ADO_PROJECT_ENCODED}/_apis/git/repositories/{ADO_REPO_ID}/pullrequests/{prId}/threads?api-version=7.0" \
       | python -c "
   import sys,json
   threads=json.load(sys.stdin)['value']
   reviews=[]
   for t in threads:
       for c in t.get('comments',[]):
           content=c.get('content','')
           if 'AI Code Review' in content:
               reviews.append((c.get('publishedDate',''), content))
   reviews.sort()
   print(reviews[-1][1][:100] if reviews else 'not-found')
   " 2>/dev/null)
     echo "[$i] ${result:0:60}"
     if [ "$result" != "not-found" ]; then echo "FOUND"; break; fi
     sleep 15
   done
   ```

3. **Parse findings**: Count Critical and Major issues from the review.

### Step 9: Fix AI Review Issues

For each Critical and Major finding, triage:

| Category | Action |
|----------|--------|
| **Real issue** | Fix in code, commit, stamp, push |
| **False positive** | Log in `.claude/ai-review-findings.md` |

**After fixing:**
1. Commit fixes with descriptive message
2. **Update PR description** — append a `## Review Fixes` section:
   ```
   ### Iteration N
   **Issues addressed:**
   - **[Major]** {summary of fix and why}
   ```
3. `bash .claude/hooks/stamp-review.sh`
4. `git fetch origin develop && git rebase origin/develop` (if needed)
5. `bash .claude/hooks/stamp-review.sh` (re-stamp after rebase)
6. `git push` (or `--force-with-lease` after rebase)
7. Loop back to Step 8 polling

**Max iterations**: 5. If still failing, report to user.

### Step 10: Set Auto-Complete

Once the latest AI review shows 0 Critical AND 0 Major (or all remaining are logged false positives):

```bash
token=$(az account get-access-token --resource 499b84ac-1321-427f-aa17-267ca6975798 --query accessToken -o tsv 2>/dev/null)
myId=$(curl -s -H "Authorization: Bearer $token" "{ADO_ORG}/_apis/connectionData" | python -c "import sys,json; print(json.load(sys.stdin)['authenticatedUser']['id'])")
curl -s -X PATCH -H "Authorization: Bearer $token" -H "Content-Type: application/json" \
  "{ADO_ORG}/{ADO_PROJECT_ENCODED}/_apis/git/repositories/{ADO_REPO_ID}/pullrequests/{prId}?api-version=7.0" \
  -d "{\"autoCompleteSetBy\":{\"id\":\"$myId\"},\"completionOptions\":{\"mergeStrategy\":\"{MERGE_STRATEGY}\",\"deleteSourceBranch\":true}}"
```

### Step 11: Close Work Item

**For User Stories** — set state to `Dev Complete`:

```bash
az boards work-item update --id {id} --state "Dev Complete" --discussion "$(cat <<'HTMLEOF'
<h3>Implementation Complete — PR #{prId}</h3>
<p><strong>What was done</strong>: {summary}</p>
<p><strong>Business Context</strong>: Part of Feature #{parentId} ({parentTitle})</p>
<h4>Acceptance Criteria Verification</h4>
<table><tr><th>AC</th><th>Status</th><th>Implementation</th></tr>
{one row per AC}
</table>
<p><strong>Verified</strong>: {what was tested}</p>
<p><strong>Follow-up</strong>: {deferred items or "None"}</p>
HTMLEOF
)"
```

**For Bugs** — set state to `Closed` with root cause + fix details.

### Step 12: Cleanup

1. Verify PR merged (check `status=completed`)
2. `git checkout develop && git pull origin develop`
3. `git branch -d {branch}` (or `-D` for squash-merged branches)
4. Confirm to user: "Story #{id} closed. Switched to develop."

## Notes

- This skill handles everything AFTER implementation is done
- If `{SCSS_CMD}` is defined in `project.testing.md`, always run it when `.scss` files changed and stage the compiled output — projects typically load the minified/compiled version, not the source file
- Always stamp review BEFORE pushing, as a separate command
- PR description must include AC verification table and business context from Feature/Epic
- Update PR description with review fix details after each iteration
- The user already approved locally at Step 5 — no additional gate needed after AI review
