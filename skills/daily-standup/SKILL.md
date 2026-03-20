---
name: daily-standup
description: Generate a daily standup summary — what you worked on yesterday, what's planned today, and any blockers. Pulls from ADO work items and PRs. Written in business-friendly language.
user-invocable: true
argument-hint: [--yesterday | --date 2026-03-19]
---

# Daily Standup

Generates a ready-to-share daily standup update by querying ADO for recent work items and pull requests. Output is written in **business-friendly language** — technical details are translated into impact-oriented summaries that a manager or product owner can understand.

## Arguments

- `--yesterday` — report on yesterday's work (default)
- `--date 2026-03-19` — report on a specific date
- No arguments — defaults to yesterday

## Instructions

Follow these steps in order. Use Bash for all `az` and `git` commands.

### Step 0: Load Project Configuration

Read the convention files and extract configuration values before doing any other work.

**Required**: Read `.claude/project.env.md` and extract:
- **ADO_ORG**: Organization URL
- **ADO_PROJECT**: Project name
- **ADO_PROJECT_ENCODED**: URL-encoded project name
- **ADO_REPO_ID**: Repository GUID
- **BRANCH_USERNAME**: Username for branch naming

If `project.env.md` does not exist, **STOP** and tell the user:
```
Project configuration not found. Run /emergent-dev:init-project to set up
.claude/project.env.md with your ADO, database, and Azure configuration.
```

Configure az defaults:
```bash
az devops configure --defaults organization={ADO_ORG} project="{ADO_PROJECT}"
```

### Step 1: Determine Date Range

Parse arguments to determine the target date. Default to yesterday.

```bash
# Yesterday's date
TARGET_DATE=$(date -d "yesterday" +%Y-%m-%d 2>/dev/null || date -v-1d +%Y-%m-%d)
NEXT_DATE=$(date -d "$TARGET_DATE + 1 day" +%Y-%m-%d 2>/dev/null || date -v+1d -j -f "%Y-%m-%d" "$TARGET_DATE" +%Y-%m-%d)
```

### Step 2: Query Work Items Changed

Find work items that were changed on the target date by the current user:

```bash
az boards query --wiql "SELECT [System.Id], [System.Title], [System.WorkItemType], [System.State], [Microsoft.VSTS.Scheduling.StoryPoints], [System.ChangedDate] FROM WorkItems WHERE [System.WorkItemType] IN ('User Story', 'Bug') AND [System.AssignedTo] = @Me AND [System.ChangedDate] >= '$TARGET_DATE' AND [System.ChangedDate] < '$NEXT_DATE' ORDER BY [System.ChangedDate] DESC" --output json
```

For each work item, fetch the parent Feature for context:
```bash
curl -s -u ":$(az account get-access-token --resource 499b84ac-1321-427f-aa17-267ca6975798 --query accessToken -o tsv)" \
  "{ADO_ORG}/{ADO_PROJECT_ENCODED}/_apis/wit/workitems/{id}?\$expand=relations&api-version=7.0"
```

### Step 3: Query Pull Requests

Find PRs created or updated on the target date:

```bash
curl -s -u ":$(az account get-access-token --resource 499b84ac-1321-427f-aa17-267ca6975798 --query accessToken -o tsv)" \
  "{ADO_ORG}/{ADO_PROJECT_ENCODED}/_apis/git/repositories/{ADO_REPO_ID}/pullRequests?searchCriteria.creatorId=$(curl -s -u \":$(az account get-access-token --resource 499b84ac-1321-427f-aa17-267ca6975798 --query accessToken -o tsv)\" \"{ADO_ORG}/_apis/connectionData\" | python -c \"import json,sys; print(json.load(sys.stdin)['authenticatedUser']['id'])\")&searchCriteria.status=all&api-version=7.0"
```

Filter to PRs whose creation date or close date falls on the target date.

### Step 4: Query Git Activity

Check commit activity for additional context:

```bash
git log --oneline --after="$TARGET_DATE" --before="$NEXT_DATE" --author="{BRANCH_USERNAME}" 2>/dev/null
```

### Step 5: Generate Standup Report

Combine all data into a standup report. **Write in business-friendly language** — translate technical work into business impact.

#### Translation Rules

| Technical | Business-Friendly |
|-----------|-------------------|
| "Refactored the allocation pipeline SQL proc" | "Improved the allocation calculation engine for better accuracy and reliability" |
| "Fixed null reference in dealer forecast grid" | "Resolved an issue where the dealer forecast page could fail to load for certain dealers" |
| "Added retry logic to SFTP ingestion" | "Improved reliability of automated file imports — the system now recovers from temporary connection issues" |
| "Created unit tests for supply distribution" | "Added automated quality checks to the supply distribution calculations" |
| "Deployed SQL schema changes to UAT" | "Released database updates to the testing environment for stakeholder review" |
| "Merged PR with SCSS/CSS changes" | "Updated the visual styling of the dealer-facing interface" |

**General principles:**
- Lead with **what it means for the user/business**, not what changed technically
- Use domain terms the team uses (dealers, allocations, forecasts, submissions) not code terms (procs, DTOs, handlers)
- Mention the **story or feature name** to tie work to roadmap items
- Keep each item to 1-2 sentences
- Group by story/feature, not by file or technology

#### Output Format

```markdown
## Standup — {date}

### What I worked on

**{Feature Name}** (Story #{id}: {title})
- {Business-friendly summary of what was accomplished}
- {Second item if applicable}

**{Another Feature}** (Story #{id}: {title})
- {Summary}

### Pull Requests
- **PR #{id}** — {title} ({status: merged/active/approved})

### Today's Plan
- Continue work on {story title} — next up: {next AC or logical next step}

### Blockers
- {Any blockers, or "None"}
```

Present the report to the user. They can copy/paste it directly into their standup channel or meeting.

## Notes

- If no work items or PRs are found for the date, check if the date was a weekend and mention that.
- The "Today's Plan" section should look at stories currently assigned and in Active state to suggest what's next.
- Keep the report concise — standups should be 30 seconds to read, not 5 minutes.
- If the user provides `--today` instead of `--yesterday`, adjust accordingly and skip the "Today's Plan" section (they're reporting live).
