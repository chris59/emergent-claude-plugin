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
- `--deep-review` — before the approval gate, run the multi-agent fan-out + adversarial-verify
  self-review (the `reviewer` agent's Deep Review Mode, §9) instead of relying solely on the ADO AI
  review. Useful when closing a large/high-risk branch directly without having gone through
  `/start-story`'s pre-PR self-review gate.

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
- `{MERGE_STRATEGY}` — PR merge strategy (default: `rebase` — linear history; "Rebase and fast-forward")

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

### Step 2: AC Verification — dispatch the verifier (do NOT self-grade)

**The session that wrote the code does not rule on whether it is finished.** Dispatch the
`ac-verifier` agent, fresh context, and relay its verdict. Mapping the ACs yourself here is the
failure this step exists to prevent — you already believe the work is done, so you will read each
criterion as a description of what you built.

```
Agent(subagent_type: "ac-verifier", model: "opus", prompt: """
WORK ITEM: #{id} — {title}
TYPE: {Bug|Story}
BASE: develop
PLAN: {plan path, if one exists}

ACCEPTANCE CRITERIA (verbatim):
{the ACs, numbered, exactly as written on the work item}

IMPLEMENTER'S REPORT (a claim to test, not a finding to relay):
{what the implementation reported, including anything it tried and abandoned}
""")
```

Relay its table as-is. Its verdict is mechanical and **you never round it up**:

| Verifier verdict | What happens |
|---|---|
| `COMPLETE` (every AC `MET`) | proceed to Step 3 |
| `SHORT` (any `PARTIAL` or `NOT MET`) | **re-plan the remainder — do not ship with a caveat** |

**A shortfall is not a question for the user and not a footnote in the PR.** Writing the gap into
the PR body does not close it; it moves the decision onto the reviewer after the work is merged and
hard to unwind. Take the verifier's `REGROUP BRIEF` back to planning, implement the delta, and
re-verify. Budget two regroup cycles.

When the budget is exhausted, that IS a stop point — and the three options are genuinely the user's:
keep going on a fresh plan, amend the criterion, or park the story. **Amending or descoping an
acceptance criterion is never your call.**

If the verifier cannot run at all, the story **holds here**. An unavailable verifier is not a pass.

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

**If `--deep-review` was passed**: first run the fan-out + adversarial-verify self-review from the
`reviewer` agent's Deep Review Mode (§9) over the branch diff vs develop — ideally as a `Workflow`. Fold
any surviving Critical/Major findings into the summary below (and fix them before approval). This is a
local pre-PR gate; the ADO AI review at Step 8 still runs regardless.

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

**Check for merge conflicts immediately** via `mcp__azure-devops__repo_get_pull_request_by_id`
(`repositoryId: {ADO_REPO_ID}`, `pullRequestId: {prId}`) — read `mergeStatus`. (Clean JSON, no
cp1252/curl encoding issues.)
If `conflicts`: rebase, stamp, force-push, re-check.

### Step 8: Poll Build & AI Review

> **🚨 POLL VIA MCP TOOLS — NOT curl/az-rest/python loops.**
> The `curl ... | python` and `az rest ... | python` poll loops below this note are
> BROKEN on Windows (cp1252 mangles the JSON → python gets empty stdin → the loop's
> completion check NEVER fires → silent infinite wait). If you use them you will hang
> until the human notices the build/review is done — which is a failure of your job to
> shepherd the PR to completion. Use the MCP path instead.
>
> **It is YOUR job to drive the PR to done (auto-complete set, work item closed) without
> the human having to notice "it's done."** Do not stop at "I started polling."

**Reliable polling (use this):**

1. **Build status** — `mcp__azure-devops__pipelines_get_builds` with
   `branchName: "refs/pull/{prId}/merge"` (or `pipelines_get_build_status` once you have the
   build id). Clean JSON, no encoding issues. `status: 1` = in progress, `2` = completed;
   read `result` for success/failure. If no build appears after a few checks, the PR-policy
   build may not have auto-triggered — queue it (`pipelines_run_pipeline`) or check PR policies.

2. **AI review thread** — `mcp__azure-devops__repo_list_pull_request_threads`
   (`repositoryId: {ADO_REPO_ID}`, `project: {ADO_PROJECT}`). Find the thread whose comment
   `content` contains `AI Code Review` (author is the build service). Parse `#### Critical Issues`
   and `#### Major Issues` — each `- **[` line is one finding.

3. **Drive the wait with `ScheduleWakeup`, NOT a bash sleep loop.** After pushing the PR,
   schedule a wakeup (~150s while a build is actively running — CI here takes a few minutes)
   that re-invokes you to re-check via the MCP tools above. Keep re-scheduling until: build
   completed AND review parsed AND (clean → auto-complete set + work item closed) OR
   (findings → fixed, pushed, re-poll). The wakeup re-invokes you automatically, so there is
   no silent hang and no dependence on the human noticing. Only stop scheduling when the work
   is truly done or you genuinely need a human decision.

4. **Parse findings**: Count Critical and Major issues from the review (gate: any Critical OR
   >5 Major blocks; but fix/log ALL Major before auto-complete).

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

Once the latest AI review shows 0 Critical AND 0 Major (or all remaining are logged false positives),
set auto-complete via `mcp__azure-devops__repo_update_pull_request` (`repositoryId: {ADO_REPO_ID}`,
`pullRequestId: {prId}`) — set `autoCompleteSetBy` to your own identity (resolve via
`mcp__azure-devops__core_get_identity_ids` if you don't have it) and `completionOptions` to
`{mergeStrategy: "{MERGE_STRATEGY}", deleteSourceBranch: true}`.

If the MCP tool doesn't expose `autoCompleteSetBy`, fall back to a single (non-loop) `az repos pr update`
— never a curl/python pipe, which mangles JSON on cp1252.

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

### Step 11.5: Record Process Metrics

Append ONE line to `.claude/process-metrics.jsonl` (create the file if missing) capturing how this story
actually went — so `/emergent-dev:process-report` can later show which gates earn their cost. This is
fire-and-forget telemetry; never block the close on it.

Write a single JSON object (one line, no pretty-print) with these fields:
```json
{"event":"close","storyId":{id},"type":"{Story|Bug}","points":{points},
 "acTotal":{n},"acMet":{n},"acWarnings":{n},
 "scopeCreepFiles":{n},"aiReviewIterations":{n},
 "reworkAfterApproval":{true|false},"ts":"{ISO-8601 timestamp}"}
```
- `acWarnings` = count of ⚠️ ACs from Step 2; `scopeCreepFiles` = files flagged in Step 3 with no AC.
- `aiReviewIterations` = number of fix-push cycles in Step 9 (0 if review was clean first pass).
- `reworkAfterApproval` = did the user report issues at the Step 5 gate after first approving? (proxy for
  "local approval was premature").
- Stamp `ts` from `date -u +%Y-%m-%dT%H:%M:%SZ` (Bash) — do not invent a time.

Append safely (don't clobber prior lines):
```bash
echo '{...json...}' >> .claude/process-metrics.jsonl
```
`.claude/process-metrics.jsonl` is local telemetry — add it to `.gitignore` if it isn't already.

### Step 11.6: Promote a Learning (close the knowledge loop)

Knowledge from a story tends to die in session memory or get re-discovered later. Before cleanup, decide
whether anything learned this story is a **durable fact worth persisting** — and route it to where it'll
actually be re-read, not just to session memory.

Consider: a non-obvious gotcha hit during implementation, a correction to a stale assumption, a project
fact not derivable from the code, a recurring failure and its fix.

If there's nothing durable (most small stories), skip silently — do NOT manufacture a "learning."

If there IS something, use **AskUserQuestion** to confirm it's worth keeping and route by type:

| Type of learning | Destination |
|------------------|-------------|
| **Operational gotcha** reusable across stories (CLI flag, API quirk, env trap) | the relevant skill's comment or a `reference/*.md` doc in the plugin |
| **Project fact** (topology, naming, a hard rule) not in the code | the matching `.claude/project.*.md` convention file |
| **Correction** of an existing note/doc that turned out wrong | edit the note AT ITS SOURCE — don't just add a contradicting one (the failure mode this step exists to prevent) |
| **Session/ongoing-work state** only | project memory (`MEMORY.md` + topic file) per the memory rules |

The bias is toward the durable destinations (skill/reference/project file) over session memory, because
those feed the next run automatically via the shared preamble. Always confirm before editing a shared
plugin file or convention file.

### Step 12: Cleanup — tear the worktree down

Capture both values **while still inside the worktree**, before leaving it:

```bash
STORY_BRANCH="$(git branch --show-current)"
MAIN_ROOT="$(git rev-parse --git-common-dir | xargs dirname)"
```

1. **Verify the PR actually merged** (`status=completed`). Do not tear down on an open PR.
2. **Leave the worktree**: `ExitWorktree({ action: "keep" })` — back to the main checkout.
3. **Remove it, by BRANCH name (never the work-item id):**
   ```bash
   bash .claude/skills/start-story/scripts/story-worktree.sh remove "$STORY_BRANCH" --merged
   ```
   `--merged` lets it delete the local branch too. The script tears down the directory, prunes
   git's worktree registry, and — because every story runs a build and MSBuild keeps file handles
   on `bin/*.dll` — runs `dotnet build-server shutdown` and retries automatically if the first
   delete is refused. An empty-but-pinned directory (a shell whose cwd is still inside it) is also
   handled.
4. **Confirm the teardown**, do not assume it:
   ```bash
   git worktree list          # the story worktree must be GONE
   git status --porcelain     # main checkout, must be clean
   ```
   The script's own contract is `REMOVED=yes`. If it prints `REMOVED=partial`, the `REASON` line
   names what still holds a handle — an open editor, a running API/Function host, or an Explorer
   window. Close it and re-run; never leave a half-removed worktree behind.
5. **Tree-clean check**: if `git status --porcelain` lists anything in the main checkout, surface it
   with the file list and a recommendation (commit, stash, revert) BEFORE the final confirmation.
   Do not silently leave a story closed on a dirty tree.
6. Confirm to the user: "Story #{id} closed. Worktree removed, back on develop." plus "Tree clean"
   or "Tree dirty — see above".

**Housekeeping:** `story-worktree.sh list` classifies every worktree and names abandoned ones
(`safe=merged-pr`, `in-develop`, `patch-upstream` are all recoverable elsewhere). It REPORTS; it
never deletes. Never remove a worktree you did not create.

## Notes

- This skill handles everything AFTER implementation is done
- If `{SCSS_CMD}` is defined in `project.testing.md`, always run it when `.scss` files changed and stage the compiled output — projects typically load the minified/compiled version, not the source file
- Always stamp review BEFORE pushing, as a separate command
- PR description must include AC verification table and business context from Feature/Epic
- Update PR description with review fix details after each iteration
- The user already approved locally at Step 5 — no additional gate needed after AI review
