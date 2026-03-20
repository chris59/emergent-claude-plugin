---
name: start-story
description: Start work on an ADO story — governance gates, assign, estimate, activate, branch, and plan
user-invocable: true
argument-hint: "<story-id> [--spec <path>]"
---

# Start Story

Prepare an ADO story for development with full governance: validate readiness, assign, estimate, activate, create a branch, research, plan, implement, and verify acceptance criteria.

## Arguments

The user provides a story ID after `/start-story`, with optional flags:
- `910` or `#910` — the ADO work item ID (required)
- `--spec <path>` — path to a specification/reference doc to load during planning (optional)

Examples:
- `/start-story 1051`
- `/start-story 1051 --spec .claude/data-ingestion/sap-extracts-specification.md`

## Instructions

Follow these steps in order. Use Bash for all `az` and `git` commands.

### Step 0: Load Project Configuration

Before any other step, read the convention files from `.claude/` and extract configuration values.
See `tools/emergent-claude-plugin/skills/shared-preamble.md` for the full instructions.

**Required** — read `.claude/project.env.md` and extract:
- **ADO_ORG**: Organization URL (e.g., `https://dev.azure.com/MyOrg`)
- **ADO_PROJECT**: Project name (e.g., `My Project`)
- **ADO_PROJECT_ENCODED**: URL-encoded project name (replace spaces with `%20`)
- **ADO_REPO_ID**: Repository GUID
- **BRANCH_USERNAME**: Username for branch naming (e.g., `chrisa`)

Configure az defaults immediately:
```bash
az devops configure --defaults organization={ADO_ORG} project="{ADO_PROJECT}"
```

If `project.env.md` does not exist, **STOP** and tell the user:
```
Project configuration not found. Run /emergent-dev:init-project to set up
.claude/project.env.md with your ADO, database, and Azure configuration.
```

**Recommended** — read `.claude/project.architecture.md` if it exists and extract:
- **SOLUTION**: Solution file path (e.g., `MyApp.slnf`)
- **BUILD_CMD**: Build command (default: `dotnet build {SOLUTION} -c Release`)
- **TEST_CMD**: Test command (default: `dotnet test {SOLUTION} -c Release --no-build`)
- **FORMAT_CMD**: Format command (default: `dotnet format whitespace {SOLUTION}`)

If not found, auto-detect solution: `ls *.slnf *.sln 2>/dev/null | head -1`

**Optional** — read `.claude/project.testing.md` if it exists and extract:
- **SCSS_CMD**: SCSS compilation command (skip the SCSS step if not defined)
- **DB_BUILD_CMD**: Database build command (skip the DB build step if not defined)

**Optional** — read `.claude/project.team.md` if it exists and extract:
- **MERGE_STRATEGY**: PR merge strategy (default: `squash`)
- **SPLIT_THRESHOLD**: Story point splitting threshold (default: `13`)
- **POINT_SCALE**: Fibonacci point scale (default: `1, 2, 3, 5, 8, 10`)

### Step 1: Parse & Fetch Story

1. Parse the argument string:
   - Strip any leading `#` from the story ID to get the numeric ID
   - If `--spec <path>` is present, save the path for use in Step 5
2. Fetch the story:
   ```bash
   az boards work-item show --id {id} --output json
   ```
3. Extract and display to the user:
   - **Title** (`fields.System.Title`)
   - **State** (`fields.System.State`)
   - **Assigned To** (`fields.System.AssignedTo.displayName` / `.uniqueName`)
   - **Story Points** (`fields.Microsoft.VSTS.Scheduling.StoryPoints`)
   - **Description** (`fields.System.Description`) — strip HTML tags for display
   - **Acceptance Criteria** (`fields.Microsoft.VSTS.Common.AcceptanceCriteria`) — strip HTML
   - **Parent** (`fields.System.Parent`) — if present, fetch parent title too

### Step 2: Story Readiness Gate (Gate 1)

Run a structured readiness assessment before any work begins. Display results as a checklist to the user.

#### 2a. Hierarchy Validation

Verify the story is connected to a business goal:

1. The story MUST have a **Parent** (Feature). Extract `fields.System.Parent` from Step 1.
2. If parent exists, fetch the parent work item and check that IT has a parent (Epic):
   ```bash
   az boards work-item show --id {parentId} --output json
   ```
   Extract the Feature title and its parent Epic ID/title.
3. Display the hierarchy chain: `Story #{id} → Feature #{parentId} ({parentTitle}) → Epic #{epicId} ({epicTitle})`

**If no parent Feature**: **WARN** — display: `"⚠️ Hierarchy: Story has no parent Feature — this work has no documented business justification. Link to a Feature or explain why this is standalone."`
Use **AskUserQuestion** to ask the user to either provide the Feature ID to link, or confirm this is intentional orphaned work.

**If Feature has no parent Epic**: **WARN** (less severe) — display: `"⚠️ Feature #{parentId} has no parent Epic — acceptable for infrastructure work, flag for product stories."`

#### 2b. Acceptance Criteria Validation

1. **AC must exist**: If acceptance criteria is empty, **BLOCK** — use **AskUserQuestion**: `"This story has no acceptance criteria. What does 'done' look like? Please provide testable pass/fail criteria."`
   - If user provides AC, update the story in ADO:
     ```bash
     az boards work-item update --id {id} --fields "Microsoft.VSTS.Common.AcceptanceCriteria={userResponse}"
     ```

2. **AC quality check**: Scan the acceptance criteria text for vague/ambiguous terms:

   | Vague Term | Flag |
   |-----------|------|
   | "improve" | ⚠️ Vague — improve how? What metric? |
   | "optimize" | ⚠️ Vague — optimize what? Target value? |
   | "clean up" | ⚠️ Vague — what specific changes? |
   | "as needed" | ⚠️ Ambiguous — specify exact conditions |
   | "etc." | ⚠️ Ambiguous — enumerate all cases |
   | "appropriate" | ⚠️ Ambiguous — define the criteria |
   | "better" | ⚠️ Vague — better by what measure? |
   | "handle errors" | ⚠️ Vague — what errors? What response? |
   | "flexible" | ⚠️ Vague — what extension points? |
   | "robust" | ⚠️ Vague — what failure modes? |

   If any vague terms found: **WARN** — list them and ask user to clarify or confirm intent. Do NOT block.

3. **AC testability check**: Each AC should be a pass/fail statement. Flag ACs that are purely descriptive (no measurable outcome). Example:
   - Good: "Files are processed in chronological order based on YYYYMMDD-HHMMSS timestamp"
   - Bad: "The system should handle files appropriately"

#### 2c. Scope Validation

1. If story points are already set and **≥ {SPLIT_THRESHOLD}**: **WARN** — `"⚠️ Scope: {points} points is very large. Consider whether this covers genuinely independent capabilities that could be split. Stories up to 10 points are fine if cohesive."`
2. If story points are not yet set, this will be addressed in Step 3.

#### 2d. Dependency Check

Check for linked predecessor work items that might block this story:
```bash
# Fetch work item relations
az boards work-item show --id {id} --output json --query "relations[?contains(attributes.name, 'Predecessor') || contains(rel, 'Predecessor')]"
```
If predecessors exist, check each one's state. If any predecessor is NOT in `Dev Complete`, `Closed`, or `Resolved`:
**WARN** — `"⚠️ Dependencies: Predecessor #{predId} ({predTitle}) is in state '{predState}' — may block this work."`

#### 2e. Business Context Check

Scan the description for a "why" statement. The description should explain the business need, not just the technical change.

**Heuristic**: If the description contains ONLY technical terms (file names, class names, SQL, code patterns) with no mention of users, stakeholders, business process, or client request — **WARN**:
`"⚠️ Business Context: Description appears purely technical with no stated business reason. Who benefits from this and why?"`

#### 2f. Readiness Summary

Display the full assessment:
```
Story #{id} Readiness Assessment:
  {✅|⚠️|❌} Hierarchy: {chain or warning}
  {✅|⚠️|❌} Acceptance Criteria: {count} ACs defined {+ any vague term warnings}
  {✅|⚠️} Scope: {points} points
  {✅|⚠️} Dependencies: {status}
  {✅|⚠️} Business Context: {status}
```

If any items are ❌ (BLOCK), resolve them before proceeding.
If items are ⚠️ (WARN), the user may acknowledge and continue — use **AskUserQuestion** with options: "Acknowledged — proceed" / "Let me fix these first".

### Step 3: ADO Updates

Only update fields that need changing:

1. **Assign to me** (if not already assigned to me):
   ```bash
   # Get my identity
   az ad signed-in-user show --query userPrincipalName -o tsv
   # Assign
   az boards work-item update --id {id} --assigned-to "{email}"
   ```

2. **Story points** (if missing/null):
   - Analyze the story scope (description + acceptance criteria + parent context)
   - Suggest a point value from the {POINT_SCALE} scale with brief reasoning
   - Use **AskUserQuestion** to let the user confirm or override
   - Apply:
     ```bash
     az boards work-item update --id {id} --fields "Microsoft.VSTS.Scheduling.StoryPoints={points}"
     ```

3. **State → Active** (conditional):

   | Current State | Action |
   |---------------|--------|
   | `New` | Move to `Active` |
   | `Active` | Skip — already active |
   | `Unapproved / Future`, `Future Phase` | Warn user — may need approval first, ask before changing |
   | `Closed`, `Dev Complete`, `Resolved`, `In QA` | Warn user — this re-opens finished work, ask before changing |
   | `Blocked` | Warn user — investigate blocker first |

   ```bash
   az boards work-item update --id {id} --state "Active"
   ```

### Step 4: Git Prep

1. **Stash** uncommitted changes (only if working tree is dirty):
   ```bash
   # Check if dirty
   git status --porcelain
   # If output is non-empty:
   git stash push -m "auto-stash before starting story #{id}"
   ```

2. **Pull latest develop**:
   ```bash
   git checkout develop
   git pull origin develop
   ```

3. **Create feature branch**:
   - Branch name: `feature/{BRANCH_USERNAME}/{id}-{slug}`
   - Slug: lowercase title, spaces → hyphens, strip non-alphanumeric (except hyphens), truncate to ~50 chars
   - Example: story #910 "Add Wish List Balance" → `feature/{BRANCH_USERNAME}/910-add-wish-list-balance`
   ```bash
   git checkout -b feature/{BRANCH_USERNAME}/{id}-{slug}
   ```

### Step 5: Research, Specification & Planning (Gates 2 & 3)

This step has three sub-phases that MUST be executed in order: Load Context → Research/Spec → Plan.
The depth of each phase scales with story complexity (story points).

#### 5a. Load Context

Before planning, load all available context in this priority order:

1. **Explicit spec file** (`--spec` flag): If the user provided `--spec <path>`, read that file with the **Read** tool. This is the primary planning reference and should be treated as authoritative context for this story.

2. **Description-referenced spec**: If the story description contains a reference to a spec file (look for patterns like `Full spec:`, `Reference:`, `See:`, or `.claude/` paths followed by `.md`), read that file too. This catches specs that were linked when the story was created.

3. **Related `.claude/` documentation**: Based on the story title and tags, check for relevant documentation in the `.claude/` directory. Look for subdirectories whose names match keywords from the story title or tags, and read any `README.md`, notes, or specification files found there.

Display a brief summary of loaded context to the user:
```
Loaded context:
- .claude/data-ingestion/sap-extracts-specification.md (SAP extract specs — 550 lines)
```

#### 5b. Research & Specification (Gate 2)

**Purpose**: Understand the problem before designing a solution. Prevent "jump to code" syndrome.

The research depth depends on story size:

| Story Points | Research Depth |
|-------------|---------------|
| 1-2 | Brief: Read the directly-affected files, understand the change. No written spec needed. |
| 3-5 | Standard: Use Explore subagents to investigate the codebase area. Produce a brief spec (see below). |
| 8+ | Deep: Full exploration + architecture impact assessment. Written spec required. |

**For stories > 3 points** (or any story where the approach is unclear), produce a specification:

1. Use **Explore subagents** to investigate the relevant codebase area. Do NOT start planning yet.

2. Write a brief spec covering:
   - **Current behavior**: What exists today in the affected area
   - **Desired behavior**: What should change (map directly to ACs)
   - **Boundaries**: What should NOT change (explicit scope limits)
   - **Edge cases & risks**: What could go wrong
   - **Affected layers**: Which architecture layers are touched (Domain, Application, Infrastructure, Web, Database)

3. Save the spec to `.claude/specs/story-{id}.md` for audit trail.

4. Present the spec to the user for confirmation before proceeding to planning.
   Use **AskUserQuestion**: "I've completed research and produced a spec. Please review the spec above. Is this understanding correct?" with options "Yes, proceed to planning" / "No, let me clarify"

**For stories > 8 points**, additionally assess architecture impact:
- Does this touch authentication or authorization?
- Does this modify database schema?
- Does this change public API contracts?
- Are there cross-cutting concerns (logging, validation, error handling)?
- Should this be reviewed by a second person?

Display the impact assessment and flag high-risk areas.

#### 5c. Create Plan (Gate 3)

**Every story gets a plan.** The depth varies by size:

| Story Points | Plan Depth |
|-------------|------------|
| 1-2 | Inline plan: "I'll modify X file to change Y behavior. 2-3 files affected." Present to user for quick confirmation. |
| 3-5 | Written plan in plan file via **EnterPlanMode**: files to modify, approach, risks, verification steps. |
| 8+ | Full plan mode with architecture review: written plan + user-edited spec + explicit approval. |

**Every plan MUST include** (regardless of size):

1. **Files to create/modify** (with line references to existing code where applicable)
2. **AC-to-implementation mapping**: A table showing which implementation step satisfies which acceptance criterion:
   ```
   | AC | Implementation | Verification |
   |----|----------------|-------------|
   | AC1: Extension-agnostic discovery | Modify FindDatFile() in SapDatFileImporter.cs | Manual test with extensionless file |
   | AC2: MFT patterns | Add to SapDatasetRegistry.cs | Unit test |
   ```
3. **Scope boundary**: What is explicitly OUT of scope for this story
4. **Verification plan**: How each AC will be verified (test command, manual check, etc.)

Use **EnterPlanMode** for stories ≥ 3 points. For 1-2 point stories, present the inline plan and use **AskUserQuestion** for quick approval.

### Step 6: Post-Implementation — Format, Build, Test, Commit, Push, PR

After the implementation is complete:

1. **Format**: Run `{FORMAT_CMD}` — auto-fixes whitespace/spacing violations.
   Stage any changes it made: `git add -u`.

2. **Build**: Run `{BUILD_CMD}`.
   - If it fails, fix compile errors (missing files, type mismatches, etc.) and re-run.
   - Common cause: a new source file is untracked — add it with `git add <path>`.

3. **Test**: Run `{TEST_CMD}`.
   - If tests fail, fix them before proceeding.

3.5. **⛔ MANDATORY PRE-PR VERIFICATION GATE (Gate 4) — DO NOT SKIP**:

   Before committing, pushing, or creating a PR, you MUST complete ALL of the following:

   **a. AC Verification Checklist**: Map every acceptance criterion to what was implemented. Present as a checklist:
   ```
   Acceptance Criteria Verification:
     ✅ AC1: {AC text} — {what was implemented and where}
     ✅ AC2: {AC text} — {what was implemented and where}
     ⚠️  AC3: {AC text} — {implemented but lacks test coverage}
     ❌ AC4: {AC text} — {not yet implemented}
   ```
   If ANY AC is ❌, it must be implemented before proceeding.
   If any AC is ⚠️, flag it and ask user if partial coverage is acceptable.

   **b. Scope Creep Detection**: List every file modified and map each to an AC:
   ```
   Files Modified → AC Mapping:
     SapDatasetRegistry.cs → AC1, AC2
     MftFileNameParser.cs (NEW) → AC3
     SapLoaderHostedService.cs → AC4, AC5
     ⚠️ README.md → No AC (scope creep candidate)
   ```
   Any file that doesn't map to an AC is a **scope creep candidate**. Ask the user: "These files were modified but don't map to any AC. Keep or revert?"

   **c. Self-Review**: Spawn the **reviewer** subagent to review the diff in a clean context:
   ```
   Use a subagent with the reviewer agent to review all changes on this branch vs develop.
   Focus on: architecture compliance, security, correctness, and whether the changes match the stated ACs.
   ```
   The reviewer has no confirmation bias since it didn't write the code. Address any Critical or Major findings before proceeding.

   **d. User Approval**: After presenting the AC checklist, scope map, and self-review results:
   - Present a specific test plan (what to navigate to, what to click, what to verify)
   - Use **AskUserQuestion** to ask: "Build and tests pass. AC verification and self-review complete. Have you tested locally and approved the changes?" with options "Yes, approved — commit and push" / "No, I found issues"
   - **DO NOT PROCEED** to step 4 until the user selects "Yes, approved". If they report issues, fix them first.
   - **This gate exists to avoid wasting CI cycles.** Get local approval first, then commit/push/PR.

4. **Commit** with a descriptive message explaining the "why", ending with the `Co-Authored-By` trailer.
   (The pre-commit hook re-runs format and stages any remaining changes automatically.)

5. **Stamp review**: `bash .claude/hooks/stamp-review.sh` (must be a separate command BEFORE push).

6. **Push**: `git push -u origin {branch}` (separate command AFTER stamp).
   (The pre-push hook runs build + tests again as a final gate before allowing the push.)

7. **Create PR (Gate 5 — Merge Readiness)**: Use `az repos pr create` targeting `develop`, linking the work item with `--work-items {id}`.

   The PR description MUST include business context from the Feature/Epic hierarchy (fetched in Gate 1).
   Use this structured format (via HEREDOC):
   ```
   ## Summary
   [One-sentence description linking to business value]

   ## Motivation
   [The 'why' — reference the parent Feature/Epic and the business need it addresses.
    Example: "Part of Feature #706 (SFTP Setup & Connectivity) under Epic #XXX.
    Client requested standardized naming conventions for nightly extracts."]

   ## Implementation Details
   *   [Bulleted list of key technical changes]
   *   [Mention patterns, libraries, or architectural decisions]

   ## Acceptance Criteria Verification
   | AC | Status | Implementation |
   |----|--------|---------------|
   | AC1: {text} | ✅ | {file and approach} |
   | AC2: {text} | ✅ | {file and approach} |

   ## Testing & Verification
   1.  [How to test — specific steps or commands]
   2.  [Include build/test results]

   ## Related Resources
   *   [ADO Story #NNN]({ADO_ORG}/{ADO_PROJECT_ENCODED}/_workitems/edit/NNN)
   *   Parent: [Feature #NNN]({ADO_ORG}/{ADO_PROJECT_ENCODED}/_workitems/edit/NNN)

   🤖 Generated with [Claude Code](https://claude.com/claude-code)
   ```

   **⚠️ MANDATORY after PR creation — check for merge conflicts immediately:**
   ```bash
   token=$(az account get-access-token --resource 499b84ac-1321-427f-aa17-267ca6975798 --query accessToken -o tsv 2>/dev/null)
   curl -s -H "Authorization: Bearer $token" \
     "{ADO_ORG}/{ADO_PROJECT_ENCODED}/_apis/git/repositories/{ADO_REPO_ID}/pullrequests/{prId}?api-version=7.0" \
     | python -c "import sys,json; pr=json.load(sys.stdin); print(pr.get('mergeStatus','?'))"
   ```
   - If `mergeStatus` is `conflicts`: rebase, stamp, force-push, then re-check until clean:
     ```bash
     git fetch origin develop
     git rebase origin/develop
     bash .claude/hooks/stamp-review.sh
     git push --force-with-lease
     ```
   - If `mergeStatus` is `queued`: wait 5s and re-check (ADO is still computing the merge).
   - Only proceed to auto-complete and build polling when `mergeStatus` is `succeeded`.

8. **Set auto-complete once AI review is clean.** The user already approved the changes locally at step 3.5, so once the AI code review passes (0 Critical, 0 Major), set auto-complete immediately. No additional user gate is needed here.

### Step 6a: AI Code Review Gate

After the PR is created, the CI build will run and include an AI code review. **You must wait for this to pass before proceeding to Step 7.**

**⚠️ CRITICAL — DO NOT set auto-complete until the AI review is clean (0 Critical AND 0 Major).** Setting auto-complete too early causes the PR to merge and delete the branch while you're still fixing issues. This creates orphan branches with no PR and wastes time. The correct flow is: create PR → poll build + review → fix all issues → push fixes → poll again → set auto-complete once review is clean. (User already approved locally at step 3.5, so no additional user gate is needed.)

#### Merge Gate

The AI code review blocks merge when:
- **Any** Critical issues are found, OR
- **More than 5** Major issues are found (i.e., ≤5 Major is OK — but ALL Major issues must still be fixed before setting auto-complete)

#### Polling Loop

**IMPORTANT: Always run polling loops as background tasks** using `run_in_background=true` on the Bash tool call. Then use `TaskOutput` with `block=true` and a generous timeout to wait for them. This avoids locking up the conversation for minutes at a time.

1. **Check for merge conflicts first** — before polling for the build, verify the PR has no merge conflicts:
   ```bash
   token=$(az account get-access-token --resource 499b84ac-1321-427f-aa17-267ca6975798 --query accessToken -o tsv 2>/dev/null)
   curl -s -H "Authorization: Bearer $token" \
     "{ADO_ORG}/{ADO_PROJECT_ENCODED}/_apis/git/repositories/{ADO_REPO_ID}/pullrequests/{prId}?api-version=7.0" \
     | python -c "import sys,json; pr=json.load(sys.stdin); print(pr.get('mergeStatus','?'), pr.get('mergeFailureType','none'))"
   ```
   - If `mergeStatus` is `conflicts`: rebase the branch, force-push, then re-check before polling for the build:
     ```bash
     git fetch origin develop
     git rebase origin/develop
     bash .claude/hooks/stamp-review.sh
     git push --force-with-lease
     ```
   - If `mergeStatus` is `succeeded` or `queued`: proceed to build polling.

2. **Wait for the build to complete** — run this as a background task:
   ```bash
   token=$(az account get-access-token --resource 499b84ac-1321-427f-aa17-267ca6975798 --query accessToken -o tsv 2>/dev/null)
   # NOTE: The ADO builds API ignores sourceBranch as a URL filter — filter in Python instead
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
   Set `run_in_background=true`. Then call `TaskOutput` with `timeout=600000` to wait for `BUILD_DONE`.

   **If `no-build-yet` persists beyond 10 attempts**: the PR policy build may not have auto-triggered (can happen when a branch is re-pushed after a previous PR on the same branch was squash-merged). Queue it manually:
   ```bash
   token=$(az account get-access-token --resource 499b84ac-1321-427f-aa17-267ca6975798 --query accessToken -o tsv 2>/dev/null)
   defId=$(curl -s -H "Authorization: Bearer $token" \
     "{ADO_ORG}/{ADO_PROJECT_ENCODED}/_apis/build/builds?\$top=1&api-version=7.0" \
     | python -c "import sys,json; b=json.load(sys.stdin)['value'][0]; print(b['definition']['id'])")
   curl -s -X POST -H "Authorization: Bearer $token" -H "Content-Type: application/json" \
     "{ADO_ORG}/{ADO_PROJECT_ENCODED}/_apis/build/builds?api-version=7.0" \
     -d "{\"definition\":{\"id\":$defId},\"sourceBranch\":\"refs/heads/{branchName}\"}" \
     | python -c "import sys,json; b=json.load(sys.stdin); print('Queued build', b.get('id','?'), b.get('status','?'))"
   ```
   Then poll build by ID: `curl .../build/builds/{buildId}?api-version=7.0`

2. **Poll for the AI review thread** — also run as a background task after build completes:

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
   Set `run_in_background=true`. Then call `TaskOutput` with `timeout=360000` to wait for `FOUND`.

   Once found, extract the LATEST full review (there may be multiple from fix iterations — always use the newest):
   ```bash
   curl -s -H "Authorization: Bearer $token" \
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
if reviews: print(reviews[-1][1])
"
   ```

   **IMPORTANT — ADO API commentType gotcha**: The ADO REST API returns `commentType` as a **string** (`"text"`, `"system"`) — NOT an integer. Do NOT filter threads by `commentType == 1`. Instead, always search by **content** — look for threads where any comment's `content` field contains `AI Code Review`, `#### Critical`, or `#### Major`. The AI review is posted by the build service as a summary thread (no `threadContext`/`filePath`).

   Only conclude the review was skipped if the full 20-attempt / 5-minute poll completes with no result. Do NOT give up after a single check.

3. **Parse the findings** from the review content:
   - Count findings under `#### Critical Issues` — each `- **[` line is one finding
   - Count findings under `#### Major Issues` — each `- **[` line is one finding
   - Count findings under `#### Minor Issues` — informational only, do not block

4. **Evaluate**:
   - **FAIL** (any Critical OR >5 Major): Enter the fix loop (see below).
   - **PASS** (0 Critical AND ≤5 Major): **Still fix all Major issues before proceeding.** The merge gate allows ≤5 Major, but ALL Major issues must be fixed or logged as false positives — do NOT skip them. Fix real issues in code, log false positives in `.claude/ai-review-findings.md`. After fixing, push and poll for a new clean review. Once the latest review shows 0 Critical AND 0 Major (or all remaining are logged as false positives), **set auto-complete immediately** — the user already approved locally at step 3.5.

#### Fix Loop (when review fails)

For each Critical and Major finding, triage into one of three categories:

| Category | Action |
|----------|--------|
| **Real issue** | Fix it in the code. These are genuine bugs, missing validation, or security concerns. |
| **False positive** | The reviewer misunderstands the architecture, conventions, or design intent. Do NOT change code — instead, log it. |
| **Questionable** | Borderline finding. Could go either way. If fixing is low-effort, fix it. Otherwise, log it. |

**For real issues**: Fix them in the code, commit, stamp review, push.

**For false positives and questionable findings**: Log them in `.claude/ai-review-findings.md` for threshold tuning. Append entries in this format:

```markdown
## {date} — PR #{prId} — Story #{storyId}

### False Positives
- **[File:Line]** {Finding summary} — **Why FP**: {1-2 sentence explanation of why this is not a real issue}

### Questionable
- **[File:Line]** {Finding summary} — **Notes**: {Why this is borderline and what you decided}
```

Create the file if it doesn't exist. This log helps the team tune the AI review thresholds over time.

**After fixing and logging**:
1. `git add` changed files and commit with message describing the fixes
2. **Update the PR description** — append a `## Review Fixes` section (or update existing) summarizing what was fixed and why:
   ```
   ### Iteration N
   **Issues addressed:**
   - **[Major]** {summary of fix and why}
   - **[Minor]** {summary — or "logged as false positive"}
   ```
   Use `az repos pr update --id {prId} --description "..."` to replace the full description with the appended section.
3. `bash .claude/hooks/stamp-review.sh` (separate command)
4. **Check for merge conflicts BEFORE pushing** — `develop` may have moved while you were working:
   ```bash
   git fetch origin develop && git rebase origin/develop
   bash .claude/hooks/stamp-review.sh   # re-stamp after rebase
   ```
5. `git push` (or `git push --force-with-lease` if a rebase was needed)
6. **Verify the PR has no conflicts** before polling:
   ```bash
   curl -s -H "Authorization: Bearer $token" \
     ".../pullrequests/{prId}?api-version=7.0" \
     | python -c "import sys,json; pr=json.load(sys.stdin); print(pr.get('mergeStatus','?'))"
   ```
   If still `conflicts`, repeat the rebase + force-push loop.
7. **Loop back** to the polling step and wait for the new build

**Max iterations**: 5 fix-push cycles. If still failing after 5 attempts, stop and report to the user:
- List the remaining findings
- Explain which ones keep recurring and why
- Ask the user how to proceed (force merge, adjust approach, or abandon)

#### Build Failure (non-review)

If the build fails for reasons OTHER than AI review, triage the failure type and fix locally before re-pushing:

| Failure type | Local fix |
|---|---|
| **Format violation** | `{FORMAT_CMD}` → `git add -u` |
| **Compile error / missing file** | Fix or add the missing file: `git add <path>` |
| **Test failure** | Run `{TEST_CMD}` locally, read output, fix failing tests |
| **SCSS compilation** | Run `{SCSS_CMD}` (if defined in project.testing.md) |
| **Database build** | Run `{DB_BUILD_CMD}` (if defined in project.testing.md) |

**Fix loop**:
1. Run the failing check locally to get the full error output
2. Fix the issue in the code
3. Re-run `{FORMAT_CMD}` + `git add -u`
4. Re-run `{BUILD_CMD}` — confirm clean
5. Re-run `{TEST_CMD}` — confirm passing
6. If defined: re-run `{SCSS_CMD}` and `{DB_BUILD_CMD}` as applicable
7. `git add` changed files and commit
8. `bash .claude/hooks/stamp-review.sh` (separate command)
9. `git push` (separate command) — pre-push hook verifies build + tests pass again
10. Loop back to the CI polling step

The AI review only runs if the build and tests succeed, so these must be resolved first.

### Step 7: Verification & Close

Determine the verification path based on the story type:

#### Path A: Test-only stories (tag contains `test-gap`)

For stories tagged `test-gap`, the tests themselves ARE the verification. No manual user verification is needed.

**Auto-close criteria** — all must be true before closing:
1. `{BUILD_CMD}` — 0 errors, 0 warnings
2. `{TEST_CMD}` — all tests pass (including the new ones)
3. PR has been created and linked to the story

If all three pass, proceed directly to closing the work item (skip AskUserQuestion):

```bash
az boards work-item update --id {id} --state "Closed" --discussion "$(cat <<'HTMLEOF'
<h3>Implementation Complete — PR #{prId}</h3>
<p><strong>What was done</strong>: {summary — e.g., "Added N unit tests covering X failure modes for Y handler"}</p>
<p><strong>Verification</strong>: All tests pass, build clean.</p>
<p><strong>Test count</strong>: {N} new tests, {total} total suite</p>
HTMLEOF
)"
```

#### Path B: Infrastructure / pipeline / tooling stories (CI-verified)

For stories where the changes are to CI/CD pipelines, build scripts, analyzer config,
architecture tests, `.editorconfig`, build props, tooling scripts, or other developer
infrastructure — the CI pipeline itself verifies the changes. No manual UI verification
is needed.

**Indicators** (any of these):
- Changed files are under `.azure-pipelines/`, `tools/`, or `.claude/`
- Changed files are build props, `.editorconfig`, `*.props`, `*.targets`
- Story is tagged `enterprise-practices` or is a pure infrastructure task
- Story title references "CI", "pipeline", "analyzer", "formatting", "coverage", "build"

**Auto-close criteria** — all must be true before closing:
1. `{BUILD_CMD}` — 0 errors, 0 warnings
2. PR has been created and linked to the story
3. Python/YAML syntax valid (if pipeline scripts were changed)

If all pass, proceed directly to closing the work item (skip AskUserQuestion):

```bash
az boards work-item update --id {id} --state "Dev Complete" --discussion "$(cat <<'HTMLEOF'
<h3>Implementation Complete — PR #{prId}</h3>
<p><strong>What was done</strong>: {summary of infrastructure/pipeline changes}</p>
<p><strong>Verification</strong>: Build clean, pipeline config validated, PR created.</p>
<p><strong>Note</strong>: CI pipeline will validate these changes when the PR build runs.</p>
HTMLEOF
)"
```

#### Path C: All other stories and bugs (user already approved locally)

The user already verified the feature locally at Step 6, step 3.5 (the mandatory approval gate before commit/push). No additional user gate is needed here — proceed directly to auto-complete and close.

1. **Set auto-complete on the PR and close the work item**:

   **Set auto-complete** ({MERGE_STRATEGY} merge + delete branch):
   ```bash
   token=$(az account get-access-token --resource 499b84ac-1321-427f-aa17-267ca6975798 --query accessToken -o tsv 2>/dev/null)
   myId=$(curl -s -H "Authorization: Bearer $token" "{ADO_ORG}/_apis/connectionData" | python -c "import sys,json; print(json.load(sys.stdin)['authenticatedUser']['id'])")
   curl -s -X PATCH -H "Authorization: Bearer $token" -H "Content-Type: application/json" \
     "{ADO_ORG}/{ADO_PROJECT_ENCODED}/_apis/git/repositories/{ADO_REPO_ID}/pullrequests/{prId}?api-version=7.0" \
     -d "{\"autoCompleteSetBy\":{\"id\":\"$myId\"},\"completionOptions\":{\"mergeStrategy\":\"{MERGE_STRATEGY}\",\"deleteSourceBranch\":true}}"
   ```

   **Close the work item**:
   - **For Bugs**: Set state to `Closed` with a formatted HTML discussion comment:
     ```
     <h3>Fix Verified — PR #{prId}</h3>
     <p><strong>Root Cause</strong>: [1-2 sentence explanation]</p>
     <p><strong>Fix</strong>: [what was changed and why]</p>
     <p><strong>Verified</strong>: [brief confirmation of what was tested]</p>
     ```

   - **For User Stories**: Set state to `Dev Complete` with a formatted HTML discussion comment that includes AC verification:
     ```
     <h3>Implementation Complete — PR #{prId}</h3>
     <p><strong>What was done</strong>: [summary of implementation]</p>
     <p><strong>Business Context</strong>: [reference parent Feature/Epic and why this was needed]</p>
     <h4>Acceptance Criteria Verification</h4>
     <table><tr><th>AC</th><th>Status</th><th>Implementation</th></tr>
     <tr><td>AC1: {text}</td><td>✅</td><td>{how it was implemented}</td></tr>
     <tr><td>AC2: {text}</td><td>✅</td><td>{how it was implemented}</td></tr>
     </table>
     <p><strong>Verified</strong>: [brief confirmation of what was tested]</p>
     <p><strong>Follow-up</strong>: [any stories created for deferred scope, or "None"]</p>
     ```

   ```bash
   az boards work-item update --id {id} --state "Closed" --discussion "{html}"   # Bugs
   az boards work-item update --id {id} --state "Dev Complete" --discussion "{html}"  # Stories
   ```

### Step 8: Cleanup — Return to develop and delete local branch

After the work item is closed (regardless of path A/B/C), clean up the local branch:

1. **Verify the PR merged** — confirm the source branch PR is in `completed` status:
   ```bash
   token=$(az account get-access-token --resource 499b84ac-1321-427f-aa17-267ca6975798 --query accessToken -o tsv 2>/dev/null)
   curl -s -H "Authorization: Bearer $token" \
     "{ADO_ORG}/{ADO_PROJECT_ENCODED}/_apis/git/repositories/{ADO_REPO_ID}/pullrequests?sourceRefName=refs/heads/{branchName}&status=completed&api-version=7.0" \
     | python -c "import sys,json; prs=json.load(sys.stdin)['value']; print('merged' if prs else 'not-merged')"
   ```
   - If `not-merged`: the PR may still be pending auto-complete — skip the branch delete and note it to the user.
   - If `merged`: proceed.

2. **Switch to develop and pull latest**:
   ```bash
   git checkout develop
   git pull origin develop
   ```

3. **Delete the local feature branch** (use `-d` not `-D` — safe delete only):
   ```bash
   git branch -d feature/{BRANCH_USERNAME}/{id}-{slug}
   ```
   - If it warns "not fully merged" but the PR is confirmed completed above, use `-D` instead ({MERGE_STRATEGY} merge means git doesn't know the branch is merged).
   - If there were multiple branches (e.g., a `-review-fixes` branch), delete all of them.

4. Confirm to the user: `"Switched to develop, pulled latest, and deleted local branch feature/{BRANCH_USERNAME}/{id}-{slug}."`

## Requirements

- `az` CLI installed and authenticated (`az login`)
- Git credentials configured for the ADO remote
- `.claude/project.env.md` populated (run `/emergent-dev:init-project` if missing)
