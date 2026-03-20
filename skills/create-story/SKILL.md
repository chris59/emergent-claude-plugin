---
name: create-story
description: Create a new ADO user story — describe what you need, get suggested placement (Epic/Feature), generated ACs, and a fully created work item. Use when you need a new story.
user-invocable: true
argument-hint: [description or topic]
---

# Create Story

Guided story creation tool. Describe what you need in plain language, and this skill will:

1. Query the ADO backlog to find the right Epic and Feature to parent it under
2. Present the hierarchy so you can confirm or redirect
3. Generate a well-structured title, description, and acceptance criteria
4. Suggest story points
5. Create the work item in ADO with all fields set

## Arguments

- Free-text description of what the story should cover (optional — will ask interactively if not provided)

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

### Step 1: Understand the Request

If the user provided a description in the arguments, use that. Otherwise, ask:

> What do you need this story to cover? A brief description is fine — I'll flesh it out.

Capture the user's intent. Don't proceed until you understand:
- **What** capability or change is needed
- **Why** (if mentioned — business context helps place it correctly)
- **Where** in the system it touches (if mentioned)

### Step 2: Find the Right Parent

Query ADO for the active Epics and their child Features to present the backlog hierarchy.

```bash
# Fetch all active Epics
az boards query --wiql "SELECT [System.Id], [System.Title], [System.State] FROM WorkItems WHERE [System.WorkItemType] = 'Epic' AND [System.State] IN ('New', 'Active') ORDER BY [System.Title]" --output json
```

For each Epic, fetch its child Features:
```bash
# Get children of each Epic via relations API
curl -s -u ":$(az account get-access-token --resource 499b84ac-1321-427f-aa17-267ca6975798 --query accessToken -o tsv)" \
  "{ADO_ORG}/{ADO_PROJECT_ENCODED}/_apis/wit/workitems/{epicId}?\$expand=relations&api-version=7.0"
```

Then bulk-fetch Feature details to get titles and states.

Present the hierarchy as a formatted table:

```
## Backlog Hierarchy

### Epic: #101 — Platform Infrastructure
  Feature: #201 — Authentication & Authorization (Active)
  Feature: #202 — CI/CD Pipeline (Active)
  Feature: #203 — Monitoring & Alerting (New)

### Epic: #102 — Data Pipeline
  Feature: #301 — SAP Integration (Active)
  Feature: #302 — File Processing (Active)

### Epic: #103 — Dealer Portal
  Feature: #401 — Forecast Grid (Active)
  Feature: #402 — Dashboard (New)
```

Then **suggest** the best parent Feature based on the story description:

> Based on your description, I'd suggest placing this under **Feature #301 — SAP Integration** (Epic: Data Pipeline).
>
> Does that look right, or would you prefer a different parent?

If no existing Feature fits, suggest creating a new Feature under the most relevant Epic.

Wait for user confirmation before proceeding.

### Step 3: Check Sibling Stories

Once the parent Feature is confirmed, fetch existing stories under that Feature:

```bash
# Get Feature relations to find child stories
curl -s -u ":$(az account get-access-token --resource 499b84ac-1321-427f-aa17-267ca6975798 --query accessToken -o tsv)" \
  "{ADO_ORG}/{ADO_PROJECT_ENCODED}/_apis/wit/workitems/{featureId}?\$expand=relations&api-version=7.0"
```

Bulk-fetch sibling story details (title, state, story points). Show them:

> **Existing stories under Feature #301 — SAP Integration:**
> | ID | Title | State | Points |
> |----|-------|-------|--------|
> | #1280 | SAP MFT Naming Conventions | Active | 5 |
> | #1275 | SAP File Archiving | Closed | 3 |

Check for overlap:
- If the new story overlaps significantly with an existing sibling, **warn the user** and suggest either extending the existing story or clarifying the boundary
- If the story complements existing siblings well, note that

### Step 4: Generate Story Content

Based on the user's description, the parent Feature context, and sibling analysis, generate:

#### Title
- Short, action-oriented (e.g., "Add retry logic to SAP file ingestion")
- Under 80 characters
- Starts with a verb when possible

#### Description
- 2-3 sentences of context: what and why
- Reference the parent Feature for traceability
- Mention any related siblings if relevant

#### Acceptance Criteria
Follow these AC quality rules:
- Each AC is **independently verifiable** — a tester can confirm it without ambiguity
- Use **Given/When/Then** format OR concise declarative statements
- Cover the **happy path, edge cases, and error handling**
- Include **non-functional** criteria if relevant (performance, accessibility, logging)
- Typically 3-6 ACs per story — fewer than 3 suggests under-specification, more than 8 suggests the story is too large
- No implementation details in ACs — they describe **what**, not **how**

#### Story Points
Suggest a value from the project's point scale ({POINT_SCALE}) based on:
- Complexity of the change
- Number of system layers touched
- Uncertainty/risk
- Comparison to sibling stories' points if available

Present the full draft to the user:

```
## Proposed Story

**Title:** Add retry logic to SAP file ingestion
**Parent:** Feature #301 — SAP Integration
**Points:** 5

### Description
Add configurable retry behavior to the SAP MFT file ingestion pipeline...

### Acceptance Criteria
1. When an SAP file download fails due to a transient SFTP error, the system retries up to 3 times with exponential backoff
2. Failed retries are logged with the error details and retry count
3. After all retries are exhausted, the ingestion run is marked as Failed with a descriptive error message
4. Retry count and backoff interval are configurable via SystemSettings
5. Existing successful ingestion behavior is unchanged (no regression)
```

Ask: **"Does this look good? I can adjust the title, ACs, points, or parent before creating."**

Wait for user approval or modifications.

### Step 5: Create the Work Item

Once approved, create the story in ADO:

```bash
az boards work-item create \
  --type "User Story" \
  --title "{title}" \
  --description "{description}" \
  --fields "Microsoft.VSTS.Scheduling.StoryPoints={points}" \
  --output json
```

Then link it to the parent Feature:

```bash
az boards work-item relation add \
  --id {storyId} \
  --relation-type "System.LinkTypes.Hierarchy-Reverse" \
  --target-id {featureId}
```

Add acceptance criteria. ADO stores ACs in `Microsoft.VSTS.Common.AcceptanceCriteria` as HTML:

```bash
az boards work-item update \
  --id {storyId} \
  --fields "Microsoft.VSTS.Common.AcceptanceCriteria=<ol><li>AC 1...</li><li>AC 2...</li></ol>"
```

### Step 6: Confirm Creation

Present the final result:

> **Story #{id} created successfully**
> - **Title:** {title}
> - **Parent:** Feature #{featureId} — {featureTitle}
> - **Points:** {points}
> - **State:** New
> - **Link:** {ADO_ORG}/{ADO_PROJECT_ENCODED}/_workitems/edit/{id}
>
> Ready to start? Run `/emergent-dev:start-story {id}` to pick it up.

## Notes

- This skill creates stories in **New** state. Use `/emergent-dev:start-story` to activate and begin work.
- If the user wants to create a Feature (not a story), suggest they do it manually in ADO or extend this skill in the future.
- When generating ACs, bias toward the **user's domain language**, not technical jargon — ACs should be readable by product owners.
- If the description is vague, ask clarifying questions rather than guessing. It's better to ask once than to create a poorly scoped story.
