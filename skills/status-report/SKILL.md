---
name: status-report
description: Generate a branded weekly status report (.docx) from recent git history and ADO work items
user-invocable: true
argument-hint: ["since 2026-03-04" | "last 2 weeks" | "last week"]
---

# Status Report Generator

Generate a branded weekly status report based on recent git history, merged pull requests, and completed ADO work items.

## Arguments

- `$ARGUMENTS` — optional date range override, e.g. `"since 2026-03-04"` or `"last 2 weeks"`. Defaults to the last 2 weeks from today.

## Instructions

Follow these steps in order. Use Bash for all `az`, `git`, and `python` commands.

### Step 0: Load Project Configuration

Read `.claude/project.env.md` and extract:
- **PROJECT_NAME** — Short display name used in the report header (e.g., `Honda AIM`)
- **ADO_ORG** — Azure DevOps organization URL (e.g., `https://dev.azure.com/DKYInc`)
- **ADO_PROJECT** — ADO project name (e.g., `Honda AIM`)
- **ADO_PROJECT_ENCODED** — URL-encoded form of ADO_PROJECT (replace spaces with `%20`)
- **ADO_REPO_ID** — Repository GUID
- **BRANCH_USERNAME** — Username for git author filtering
- **STATUS_REPORT_OUTPUT_DIR** — Output directory for the .docx file (optional; defaults to current working directory if not set)

If `project.env.md` does not exist, **STOP** and tell the user:
```
Project configuration not found. Run /emergent-dev:init-project to set up
.claude/project.env.md with your ADO, database, and Azure configuration.
```

Configure az defaults:
```bash
az devops configure --defaults organization="{ADO_ORG}" project="{ADO_PROJECT}"
```

Also check `.claude/project.env.md` for a `BRANDING` block. If the file defines any of the following, extract them for use in the JSON content:
- **BRANDING_PRIMARY_COLOR** — 6-digit hex color (no `#`), e.g. `004E97`
- **BRANDING_ACCENT_COLOR** — 6-digit hex color, e.g. `BD2426`
- **BRANDING_LIGHT_COLOR** — 6-digit hex color, e.g. `E5EEF7`
- **BRANDING_FOOTER_TEXT** — Footer line, e.g. `Honda AIM • Emergent Software • Confidential`

If not defined, use Emergent defaults:
- Primary: `2E7D32`
- Accent: `1565C0`
- Light: `E8F5E9`
- Footer: `{PROJECT_NAME} • Emergent Software • Confidential`

### Step 1: Determine Date Range

Parse the date range from `$ARGUMENTS`. If not specified, use the last 2 weeks from today's date. Calculate `START_DATE` (YYYY-MM-DD) and `END_DATE` (YYYY-MM-DD). The report filename uses the end date in `MMDDYYYY` format.

```bash
# Example: last 2 weeks
END_DATE=$(date +%Y-%m-%d)
START_DATE=$(date -d "14 days ago" +%Y-%m-%d 2>/dev/null || date -v-14d +%Y-%m-%d)
```

### Step 2: Find the Previous Status Report

Look in `{STATUS_REPORT_OUTPUT_DIR}` (or current directory if not set) for the most recent `*-StatusUpdate-*.docx` file. If found, note its filename for context about previous reporting periods. Do not attempt to read its contents — just note the date range covered.

### Step 3: Gather Data

Run all three data sources in parallel where possible.

#### 3a. Git commit history

```bash
git log --since="{START_DATE}" --until="{END_DATE}" \
  --pretty=format:"%H %ad %s%n%b" --date=short
```

#### 3b. Merged pull requests via ADO REST API

```bash
ADO_TOKEN=$(az account get-access-token \
  --resource 499b84ac-1321-427f-aa17-267ca6975798 \
  --query accessToken -o tsv)

curl -s -u ":${ADO_TOKEN}" \
  "{ADO_ORG}/{ADO_PROJECT_ENCODED}/_apis/git/repositories/{ADO_REPO_ID}/pullRequests?searchCriteria.status=completed&searchCriteria.minTime={START_DATE}T00:00:00Z&api-version=7.0" \
  | python -c "
import json, sys
prs = json.load(sys.stdin).get('value', [])
for pr in prs:
    closed = pr.get('closedDate', '')[:10]
    if closed >= '{START_DATE}' and closed <= '{END_DATE}':
        print(f\"PR #{pr['pullRequestId']}: {pr['title']} (merged {closed})\")
"
```

#### 3c. Completed ADO work items

```bash
az boards query --wiql "
  SELECT [System.Id], [System.Title], [System.WorkItemType],
         [System.State], [Microsoft.VSTS.Scheduling.StoryPoints],
         [System.ChangedDate]
  FROM WorkItems
  WHERE [System.WorkItemType] IN ('User Story', 'Bug')
    AND [System.State] IN ('Closed', 'Resolved', 'Done')
    AND [System.ChangedDate] >= '{START_DATE}'
    AND [System.ChangedDate] <= '{END_DATE}T23:59:59.999Z'
  ORDER BY [System.ChangedDate] DESC
" --output json
```

For each work item returned, optionally fetch parent Feature/Epic for grouping context:
```bash
curl -s -u ":${ADO_TOKEN}" \
  "{ADO_ORG}/{ADO_PROJECT_ENCODED}/_apis/wit/workitems/{id}?\$expand=relations&api-version=7.0"
```

### Step 4: Locate the Script

Look for the report generator script in this order:
1. Project-local: `.claude/skills/status-report/scripts/generate_status_report.py`
2. Plugin path: `tools/emergent-claude-plugin/skills/status-report/scripts/generate_status_report.py`

Use the first one found. Set `SCRIPT_PATH` to the resolved path.

Also locate the styles template:
```bash
SCRIPT_DIR=$(dirname "{SCRIPT_PATH}")
STYLES_PATH="${SCRIPT_DIR}/EmergentStyles.docx"
```

### Step 5: Install Dependencies

```bash
pip install python-docx --quiet
```

### Step 6: Draft the Report Content

Analyze all git commits, PRs, and ADO work items to create a JSON content file. Reason carefully about groupings — related PRs and stories should appear under the same section heading.

Determine `OUTPUT_PATH`:
- If `STATUS_REPORT_OUTPUT_DIR` is set: `{STATUS_REPORT_OUTPUT_DIR}/{PROJECT_NAME}-StatusUpdate-{MMDDYYYY}.docx`
- Otherwise: `./{PROJECT_NAME}-StatusUpdate-{MMDDYYYY}.docx`

Write the JSON to a temp file with this structure:

```json
{
    "date_range": "March 4 – March 18, 2026",
    "output_path": "{OUTPUT_PATH}",
    "branding": {
        "project_name": "{PROJECT_NAME}",
        "primary_color": "{BRANDING_PRIMARY_COLOR}",
        "accent_color": "{BRANDING_ACCENT_COLOR}",
        "light_color": "{BRANDING_LIGHT_COLOR}",
        "footer_text": "{BRANDING_FOOTER_TEXT}"
    },
    "executive_summary": "2-3 sentence summary of the period's work...",
    "sections": [
        {
            "heading": "Category Name",
            "items": ["Detailed bullet point explaining the what and why"]
        }
    ],
    "callout": {
        "text": "COMING UP — Brief description of the next major focus area"
    },
    "timeline": [
        {"phase": "Phase 1", "focus": "Description", "dates": "Completed", "outcome": "Result"},
        {"phase": "Phase N", "focus": "Current work", "dates": "Date range", "outcome": "Expected result"}
    ],
    "blockers": ["Blocker or risk description"],
    "next_steps": ["Next step description"],
    "pull_requests": {
        "date_range_label": "M/D – M/D",
        "items": ["PR #NNN: Title (merged YYYY-MM-DD)"]
    }
}
```

**Writing guidelines:**
- Executive summary: 2-3 sentences, lead with the primary delivery, mention secondary themes
- Group related PRs and stories into logical achievement categories (e.g., "Dealer Portal UX", "Pipeline Reliability")
- Each bullet should explain the *what* and *why*, not just the code change
- Use en-dashes (–) for ranges, not hyphens
- Keep bullet points substantive but concise (2-3 sentences max)
- Timeline: mark completed phases clearly, show current/upcoming phases
- Blockers: be honest — "No active technical blockers" is fine if true
- Next steps: forward-looking and actionable

### Step 7: Generate the Document

```bash
python "{SCRIPT_PATH}" /tmp/status_content.json
```

### Step 8: Confirm Output

Tell the user:
- The full path to the generated .docx file
- A brief summary of what was included (sections covered, number of PRs and stories)
- Any data gaps (e.g., if ADO returned no work items for the period)

## Notes

- If the date range spans a holiday or known PTO period, note that in the executive summary for context.
- When multiple stories touch the same Feature/Epic, group them under one section heading and write a cohesive summary rather than isolated bullets.
- If a story was started AND completed in the same period, call it out as a quick win.
- The `timeline` section is optional — omit or simplify if there is no formal phase structure for this project.
- `STATUS_REPORT_OUTPUT_DIR` in `project.env.md` should be an absolute path (e.g., `D:/Chris/OneDrive/.../Status`). If it is not set, the file is saved to the working directory.
