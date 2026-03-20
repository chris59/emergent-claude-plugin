---
name: check-story
description: Analyze and refine an ADO story — validate readiness, assess quality, identify issues, and make improvements. Use before starting work on a story.
user-invocable: true
argument-hint: <story-id> [--fix]
---

# Check Story

Comprehensive story refinement and quality assessment tool for developers. Answers the fundamental question: **"Is this a meaningful, coherent batch of work that makes sense to build?"**

Analyzes a story's readiness for development: validates hierarchy (Story → Feature → Epic chain must exist), examines the **parent Feature in detail** to understand where this story fits among its active/new siblings, assesses whether the story is properly scoped as a cohesive unit of work, checks for common anti-patterns, validates acceptance criteria quality, suggests story points, and offers guided fixes.

## Core Philosophy

**A story should be the smallest unit of work that delivers complete, end-to-end value.** This means:

- A widget story includes BOTH its backend API and frontend UI — splitting them creates fractured ownership, integration risk, and incomplete deliverables
- A data pipeline story includes the schema, the proc, AND the C# handler — splitting by layer means no single story produces a working feature
- If a story can't be demo'd or verified on its own, it's not a real story — it's a task masquerading as one

**Common anti-patterns this skill detects:**

| Anti-Pattern | What Happens | What We Flag |
|-------------|-------------|-------------|
| **AC-per-story** | Manager splits each acceptance criterion into its own story | Sibling stories that are really just ACs of one larger story |
| **Layer splitting** | "Backend for X" and "Frontend for X" as separate stories | Stories in the same Feature that split one capability by architecture layer |
| **Estimate-driven splitting** | Story split to fit a sprint velocity target rather than logical boundaries | Multiple small stories (1-2 pts each) under the same Feature that share the same domain concept |
| **Over-decomposition** | 10 stories where 2-3 would deliver the same outcome with less overhead | High story count relative to Feature complexity |
| **Under-decomposition** | One massive story trying to do everything | Story with 8+ ACs spanning 3+ system areas |

**The bias is toward cohesion over fragmentation.** When in doubt, fewer well-scoped stories are better than many fractured ones. Splitting should only happen when a story genuinely covers independent capabilities that could ship separately.

## Arguments

- `1280` or `#1280` — the ADO work item ID (required)
- `--fix` — automatically fix issues found (update ADO fields, rewrite ACs, link to features, etc.)

## Instructions

Follow these steps in order. Use Bash for all `az` and `git` commands.

### Step 0: Load Project Configuration

Read the convention files and extract configuration values before doing any other work.

**Required**: Read `.claude/project.env.md` and extract:
- **ADO_ORG**: Organization URL (e.g., `https://dev.azure.com/MyOrg`)
- **ADO_PROJECT**: Project name (e.g., `My Project` — may contain spaces)
- **ADO_PROJECT_ENCODED**: URL-encoded project name (e.g., `My%20Project`)
- **ADO_REPO_ID**: Repository GUID
- **BRANCH_USERNAME**: Username for branch naming

If `project.env.md` does not exist, **STOP** and tell the user:
```
Project configuration not found. Run /emergent-dev:init-project to set up
.claude/project.env.md with your ADO, database, and Azure configuration.
```

**Optional**: Read `.claude/project.team.md` if it exists and extract:
- **POINT_SCALE**: Story point scale (default: `1, 2, 3, 5, 8, 10`)
- **SPLIT_THRESHOLD**: Story point splitting threshold (default: `13`)

Configure az defaults immediately:
```bash
az devops configure --defaults organization={ADO_ORG} project="{ADO_PROJECT}"
```

### Step 1: Fetch Story & Context

1. Fetch the story:
   ```bash
   az boards work-item show --id {id} --output json
   ```

2. Extract all fields:
   - **Title** (`fields.System.Title`)
   - **Work Item Type** (`fields.System.WorkItemType`) — User Story, Bug, Task
   - **State** (`fields.System.State`)
   - **Assigned To** (`fields.System.AssignedTo`)
   - **Story Points** (`fields.Microsoft.VSTS.Scheduling.StoryPoints`)
   - **Description** (`fields.System.Description`) — strip HTML for display
   - **Acceptance Criteria** (`fields.Microsoft.VSTS.Common.AcceptanceCriteria`) — strip HTML
   - **Tags** (`fields.System.Tags`)
   - **Parent** (`fields.System.Parent`)
   - **All relations** (`relations[]`) — predecessors, successors, children, related

3. If parent exists, fetch the **parent Feature**:
   ```bash
   az boards work-item show --id {parentId} --output json
   ```
   Extract Feature title, description, state, and ITS parent (Epic).

4. If the Feature has a parent, fetch the **Epic**:
   ```bash
   az boards work-item show --id {epicId} --output json
   ```

### Step 2: Fetch Sibling Stories

Fetch all child stories of the parent Feature to understand where this story fits:

```bash
token=$(az account get-access-token --resource 499b84ac-1321-427f-aa17-267ca6975798 --query accessToken -o tsv 2>/dev/null)
# Get all children of the parent Feature
curl -s -H "Authorization: Bearer $token" \
  "https://dev.azure.com/{ADO_ORG_HOSTNAME}/{ADO_PROJECT_ENCODED}/_apis/wit/workitems/{parentId}?\$expand=relations&api-version=7.0" \
  | python -c "
import sys, json
wi = json.load(sys.stdin)
children = [r for r in wi.get('relations', []) if '/Child' in r.get('rel', '')]
ids = [r['url'].split('/')[-1] for r in children]
print(','.join(ids))
"
```

Note: `{ADO_ORG_HOSTNAME}` is the hostname portion of `{ADO_ORG}` — e.g., if `ADO_ORG` is `https://dev.azure.com/MyOrg` then use `dev.azure.com/MyOrg`. Construct the full URL as `{ADO_ORG}/{ADO_PROJECT_ENCODED}/_apis/wit/workitems/...`.

Then bulk-fetch all sibling stories using the repository's API endpoint pattern derived from `{ADO_ORG}` and `{ADO_PROJECT_ENCODED}`:
```bash
curl -s -H "Authorization: Bearer $token" \
  "{ADO_ORG}/{ADO_PROJECT_ENCODED}/_apis/wit/workitems?ids={comma_separated_ids}&fields=System.Id,System.Title,System.State,Microsoft.VSTS.Scheduling.StoryPoints,Microsoft.VSTS.Common.AcceptanceCriteria,System.Description&api-version=7.0"
```

### Step 3: Comprehensive Analysis

Present a detailed analysis report with the following sections:

#### 3a. Story Overview
Display a formatted summary:
```
═══════════════════════════════════════════════════
  STORY #{id}: {title}
═══════════════════════════════════════════════════
  Type: {workItemType}    State: {state}    Points: {points}
  Assigned: {assignedTo}
  Tags: {tags}
───────────────────────────────────────────────────
  Description:
  {description text}
───────────────────────────────────────────────────
  Acceptance Criteria:
  {each AC numbered}
═══════════════════════════════════════════════════
```

#### 3b. Hierarchy & Feature Assessment

Display the full hierarchy chain and assess:

```
Hierarchy:
  Epic #{epicId}: {epicTitle} ({epicState})
    └─ Feature #{featureId}: {featureTitle} ({featureState})
       └─ Story #{id}: {title} ({state}) <- YOU ARE HERE
```

| Check | Status | Detail |
|-------|--------|--------|
| Has parent Feature | ✅/❌ | {detail} |
| Feature has parent Epic | ✅/❌ | {detail} |
| Feature state is Active | ✅/⚠️ | {detail — warn if Feature is Closed/Future} |
| Epic state is Active | ✅/⚠️ | {detail} |

**The Feature is the primary context for analysis.** The Feature's title, description, and goal define what "good" looks like for the stories beneath it. Read the Feature description in detail — it tells you what this batch of work is trying to accomplish, which informs whether THIS story is well-scoped, properly bounded, and coherent.

**The Epic just needs to exist.** It provides top-level business justification but the detailed analysis focuses on the Feature level. If the Epic is missing, flag it as a structural issue but don't block on it.

**The Feature is REQUIRED.** Without a parent Feature, the story has no context — we cannot assess scope, sibling relationships, or coherence. If missing, flag as ❌ **BLOCKING** and identify candidate Features it could belong under:
```bash
az boards query --wiql "SELECT [System.Id], [System.Title], [System.State] FROM WorkItems WHERE [System.WorkItemType] = 'Feature' AND [System.State] <> 'Closed' ORDER BY [System.Title]" --output json
```
Suggest the most likely parent based on title/description similarity.

#### 3c. Acceptance Criteria Quality

Analyze each AC individually:

| AC # | Text | Testable? | Issues |
|------|------|-----------|--------|
| AC1 | {text} | ✅/⚠️/❌ | {specific issues} |
| AC2 | {text} | ✅/⚠️/❌ | {specific issues} |

**Quality checks per AC:**
1. **Testability**: Is this a pass/fail statement? Can it be verified objectively?
2. **Specificity**: Does it use measurable terms or vague ones?
3. **Completeness**: Does it define the expected outcome, not just the action?
4. **Independence**: Can it be verified independently of other ACs?

**Vague term detection** — flag these patterns:
- "improve", "optimize", "better", "enhance" → needs measurable target
- "appropriate", "proper", "correct" → needs specific criteria
- "handle errors", "handle edge cases" → needs enumerated cases
- "as needed", "if necessary", "etc." → needs explicit conditions
- "clean up", "refactor" → needs specific structural changes
- "flexible", "robust", "scalable" → needs defined extension/failure scenarios
- "support" without specifying what formats/inputs → needs enumeration
- "user-friendly", "intuitive" → needs specific UX criteria

**Overall AC assessment:**
- **Strong**: All ACs are testable pass/fail statements with measurable outcomes
- **Needs Work**: Some ACs are vague or not independently testable
- **Weak**: Most ACs lack testability or specificity
- **Missing**: No acceptance criteria defined

#### 3d. Scope Assessment & Story Point Suggestion

| Check | Status | Detail |
|-------|--------|--------|
| Story points set | ✅/❌ | {points or "not estimated"} |
| Points reasonable | ✅/⚠️ | {assessment} |
| Single responsibility | ✅/⚠️ | {does it try to do too many things?} |
| Decomposition needed | ✅/⚠️ | {only if {SPLIT_THRESHOLD}+ points AND covers independent capabilities} |

**Story point suggestion** — ALWAYS suggest a point value, whether or not one is already set:

Analyze the story's ACs, description, and likely implementation scope (files touched, layers involved, complexity of logic). Suggest a value from the project's point scale ({POINT_SCALE}) with reasoning:

```
Suggested Story Points: {N}
Reasoning:
  - {count} ACs across {count} capability groups
  - Touches: {layers — e.g., "UI + API endpoint + DB query"}
  - Complexity: {Low/Medium/High — e.g., "Medium — multiple conditional UI states but well-defined specs"}
  - Similar completed stories: #{siblingId} ({title}) was {pts} pts with comparable scope
```

If story points are already set, compare your suggestion against the existing value. If they differ significantly (±3 or more), flag it as a calibration concern.

**Scope analysis:**

The goal is to assess whether this story represents a **cohesive unit of deliverable work** — NOT to enforce arbitrary size limits.

- **Multiple layers is NORMAL**: A story touching UI + API + DB is healthy if they're all serving the same capability. Do NOT flag multi-layer stories as "too big" — that's how real features work.
- **Multiple ACs is NORMAL**: 5-7 ACs for a 5-point story is typical. ACs define what "done" looks like, not separate work items.
- **Flag genuine over-scope**: If a story has 10+ ACs spanning genuinely independent capabilities (e.g., "Add user management AND redesign the dashboard AND migrate the database"), THAT warrants splitting — by capability, NOT by layer.
- **Flag under-estimation**: If story points < 2 but ACs describe significant cross-cutting work, the estimate is probably wrong.
- **Flag over-estimation**: If story points are large but the work is straightforward and confined to a few files, the estimate is inflated.
- **Splitting threshold**: Stories up to **{SPLIT_THRESHOLD} - 3 points are fine**. Only recommend splitting at **{SPLIT_THRESHOLD}+ points**, and only when the story genuinely covers independent capabilities. Do NOT split a cohesive story just because it's large.

**When recommending a split**, split by **independently deliverable capability**, NEVER by architecture layer:

```
✅ GOOD SPLIT (by capability):
  Story A: "Feature discovery and pattern matching" (3 pts) — AC1, AC2, AC3
  Story B: "Archiving and lifecycle management" (3 pts) — AC4, AC5, AC6
  Rationale: Each story delivers a complete, testable capability independently.

❌ BAD SPLIT (by layer):
  Story A: "Backend API for X" (3 pts)
  Story B: "Frontend UI for X" (3 pts)
  Why bad: Neither story is complete alone. Story B can't work without Story A.
  Creates integration risk, split ownership, and two PRs that must merge in sequence.
```

#### 3e. Dependency Analysis

Check all linked work items:
- **Predecessors**: Are they complete? If not, is this story blocked?
- **Related items**: Are there stories doing similar work that should be combined?
- **Children**: Does this story have sub-tasks?

| Relation | Item | State | Impact |
|----------|------|-------|--------|
| Predecessor | #{id}: {title} | {state} | {blocking/not blocking} |
| Related | #{id}: {title} | {state} | {overlap assessment} |

#### 3f. Feature Context & Sibling Analysis

**IMPORTANT: Only analyze sibling stories in `New` or `Active` state.** Ignore stories that are `Closed`, `Dev Complete`, `Resolved`, `Removed`, `In QA`, or any other terminal/completed state. Those are done — they don't affect this story's scope or readiness.

**IMPORTANT: Stay focused on THIS story.** The purpose of sibling analysis is to understand the context around the story being checked — NOT to do a full Feature/Epic audit. Only flag sibling issues that **directly affect this story** (e.g., a sibling that overlaps with this story's ACs, or a sibling that should be merged INTO this story). Do NOT recommend combining, splitting, or rewriting unrelated sibling stories.

Show the Feature's active/new stories:

```
Feature #{featureId}: {featureTitle}
  Feature Goal: {1-2 sentence summary from Feature description}

  Active/New Stories:
  ├─ Story #{s3}: {title} (Active, 3 pts)
  ├─ Story #{id}: {title} ({state}, {pts} pts) <- THIS STORY
  ├─ Story #{s4}: {title} (New, 5 pts)
  └─ Story #{s5}: {title} (New, 3 pts)

  Completed: {count} stories already done
  Remaining: {count} stories (this + {count} others)
```

**Sibling analysis — only flag issues that affect THIS story:**

1. **Direct overlap detection**: Does any New/Active sibling have ACs or description text that overlaps with THIS story's ACs? If so, flag it — the developer needs to know which story owns which scope before starting work.
   ```
   ⚠️ OVERLAP WITH THIS STORY: Sibling #{s4} "{title}" has ACs that overlap
   with your AC3 and AC7. Clarify ownership before starting — or merge #{s4}
   into this story if the work is inseparable.
   ```

2. **Dependency detection**: Does any New/Active sibling need to be completed BEFORE this story can start? Or does this story block a sibling?

3. **Coherence check**: Does THIS story fit naturally within the Feature's stated goal? Or does it feel like it was parked here for convenience?

4. **Fragmentation check (this story only)**: Has THIS story been over-split from what should be a single unit of work? Look for signs:
   - A sibling with a nearly identical title (e.g., "X Backend" / "X Frontend")
   - A sibling whose ACs are really just more ACs for this same capability
   - If detected, recommend merging the sibling INTO this story — not the other way around

#### 3g. Business Context Assessment

| Check | Status | Detail |
|-------|--------|--------|
| Description explains "why" | ✅/⚠️ | {does it state the business need?} |
| User/stakeholder identified | ✅/⚠️ | {who benefits?} |
| Value proposition clear | ✅/⚠️ | {what problem does it solve?} |
| Feature alignment | ✅/⚠️ | {does it advance the parent Feature's goal?} |

### Step 4: Issues Summary & Recommendations

Present a prioritized list of all issues found:

```
═══════════════════════════════════════════════════
  ISSUES FOUND: {count}
═══════════════════════════════════════════════════

  BLOCKING (must fix before starting):
    1. {issue description}
    2. {issue description}

  WARNINGS (should fix, but can proceed):
    3. {issue description}
    4. {issue description}

  SUGGESTIONS (nice to have):
    5. {issue description}
═══════════════════════════════════════════════════
```

### Step 5: Guided Refinement Session

Walk the developer through each issue interactively, one at a time. This should feel like a **refinement session with a knowledgeable PM**, not a checklist.

For each issue found (starting with the most critical), present:
1. The specific problem
2. Why it matters (concrete risk if left unfixed)
3. A proposed fix with before/after comparison
4. Let the developer approve, modify, or skip

Use **AskUserQuestion** at each decision point. If the developer wants to modify the proposed fix, use **AskUserQuestion** again to let them provide their own wording or approach. Keep iterating until they're satisfied.

**If `--fix` flag was passed**: Apply all fixes automatically but still show a summary of what was changed.

**Available fix actions** (offer based on what issues were found):

#### 5a. Rewrite Acceptance Criteria
If ACs are vague, propose specific rewrites:
```
Current AC3: "Handle errors appropriately"
Proposed AC3: "When file download fails, log the error with filename and retry up to 3 times before marking as failed"

Current AC5: "Improve performance"
Proposed AC5: "Reduce query execution time from current ~2s to < 500ms by adding an index on MaterialNo"
```
Use **AskUserQuestion** to let user approve/edit each rewrite.
Apply approved rewrites:
```bash
az boards work-item update --id {id} --fields "Microsoft.VSTS.Common.AcceptanceCriteria={updated_html}"
```

#### 5b. Update Description
If description lacks business context, propose an enhanced version that includes:
- Who benefits and why
- What problem it solves
- How it relates to the parent Feature
Apply with:
```bash
az boards work-item update --id {id} --fields "System.Description={updated_html}"
```

#### 5c. Link to Feature
If no parent Feature, let user select from candidates:
```bash
az boards work-item update --id {id} --relations add --relation-type "System.LinkTypes.Hierarchy-Reverse" --target-id {featureId}
```

#### 5d. Set/Update Story Points
If missing or unreasonable, suggest a value with reasoning and let user confirm:
```bash
az boards work-item update --id {id} --fields "Microsoft.VSTS.Scheduling.StoryPoints={points}"
```

#### 5e. Split Story
If decomposition is recommended:
1. Propose the split with AC assignments
2. On approval, create new child stories:
   ```bash
   az boards work-item create --type "User Story" --title "{title}" --fields "System.Description={desc}" "Microsoft.VSTS.Common.AcceptanceCriteria={acs}" "Microsoft.VSTS.Scheduling.StoryPoints={pts}" --output json
   ```
3. Link new stories to the same parent Feature
4. Move original ACs to the appropriate new stories
5. Update original story to reference the split

#### 5f. Merge Overlapping Sibling INTO This Story
If a sibling story directly overlaps with THIS story's scope:
1. Show the overlapping ACs/description text side-by-side
2. Explain why they belong together (same capability, same component, inseparable work)
3. On approval, merge the sibling's ACs into THIS story and close the sibling with a note
4. Only offer this for siblings that genuinely overlap with THIS story — do NOT suggest merging unrelated siblings with each other

#### 5g. Add Missing Links
If dependency analysis reveals unlinked predecessors:
```bash
az boards work-item update --id {id} --relations add --relation-type "System.LinkTypes.Dependency-Reverse" --target-id {predecessorId}
```

### Step 6: Final Assessment

After all fixes are applied (or skipped), present the final readiness score:

```
═══════════════════════════════════════════════════
  STORY #{id} — FINAL READINESS ASSESSMENT
═══════════════════════════════════════════════════

  Readiness Score: {score}/10

  ✅ Hierarchy:            Linked (Story → Feature → Epic)
  ✅ Description:          Clear business context
  ✅ Acceptance Criteria:  7 testable ACs
  ✅ Story Points:         5 (reasonable scope)
  ✅ Dependencies:         None blocking
  ✅ Business Context:     Clear value proposition

  Verdict: READY FOR DEVELOPMENT
  (or: NEEDS ATTENTION — {remaining issues})
═══════════════════════════════════════════════════
```

The readiness score is calculated:
- +2 for parent Feature linked
- +1 for Epic linked
- +2 for all ACs testable (no vague terms)
- +1 for AC count matches scope (not too many, not too few)
- +1 for story points set and reasonable
- +1 for description has business context
- +1 for no blocking dependencies
- +1 for story fits coherently in Feature context

## Notes

- This skill is **read-write** — it can update ADO work items when the user approves changes
- Always show proposed changes and get user confirmation before modifying ADO
- When rewriting ACs, preserve the user's intent — make them more specific, not different
- When suggesting splits, ensure each resulting story is independently deliverable
- The `--fix` flag means "fix automatically without asking for each change" — still show what was changed
