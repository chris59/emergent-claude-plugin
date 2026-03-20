---
name: weekly-status
description: Generate a branded weekly status report (.docx) — stories completed, PRs merged, epic progress, developer velocity. Business-friendly for managers and stakeholders.
user-invocable: true
argument-hint: "1 week | 2 weeks | 3 weeks | --date-range 2026-03-10:2026-03-20"
---

# Status Report

Generates a branded Word document (.docx) summarizing recent work — stories completed, PRs merged, epic progress, developer velocity, and upcoming work. Written in **business-friendly language** suitable for sharing with managers, product owners, and stakeholders.

## Arguments

- `1 week` or `1w` — today minus 7 days through today (default)
- `2 weeks` or `2w` — today minus 14 days through today
- `3 weeks` or `3w` — today minus 21 days through today
- Any `N weeks` or `Nw` pattern — today minus N*7 days through today
- `--date-range 2026-03-10:2026-03-20` — custom date range
- No arguments — defaults to 1 week

**Important**: The date range always ends at today. "2 weeks" means today minus 14 days through today.

## Instructions

Follow these steps in order. Use Bash for all `az`, `git`, and `python` commands.

### Step 0: Load Project Configuration

Read `.claude/project.env.md` and extract:
- **PROJECT_NAME** — Short display name used in the report header
- **ADO_ORG** — Azure DevOps organization URL
- **ADO_PROJECT** — ADO project name
- **ADO_PROJECT_ENCODED** — URL-encoded form of ADO_PROJECT (replace spaces with `%20`)
- **ADO_REPO_ID** — Repository GUID
- **BRANCH_USERNAME** — Username for git author filtering
- **STATUS_REPORT_OUTPUT_DIR** — Output directory for the .docx file (optional; defaults to current working directory)

If `project.env.md` does not exist, **STOP** and tell the user:
```
Project configuration not found. Run /emergent-dev:init-project to set up
.claude/project.env.md with your ADO, database, and Azure configuration.
```

Configure az defaults:
```bash
az devops configure --defaults organization="{ADO_ORG}" project="{ADO_PROJECT}"
```

Also check `.claude/project.env.md` for a `BRANDING` block. If defined, extract:
- **BRANDING_PRIMARY_COLOR**, **BRANDING_ACCENT_COLOR**, **BRANDING_LIGHT_COLOR**, **BRANDING_FOOTER_TEXT**

If not defined, omit the branding object from JSON — the script uses Emergent defaults (coral/red `EE3342`, navy `333F4F`).

### Step 1: Determine Date Range

Parse arguments. The end date is always **today**. Calculate the start date by going backwards.

- Default (no args or `1 week`): today minus 7 days
- `N weeks` or `Nw`: today minus N*7 days
- `--date-range START:END`: use those dates directly

Calculate `PERIOD_WEEKS` = number of weeks in the range (for velocity calculations).

Also calculate `PROJECT_START_DATE` from the first git commit: `git log --reverse --format="%ad" --date=short | head -1`

Calculate `PROJECT_WEEKS` = (today - PROJECT_START_DATE) / 7.

### Step 2: Establish the Active Epic Scope

**CRITICAL**: ALL data in this report must be scoped to stories under the active Epics only. ADO projects often contain legacy/closed Epics from earlier phases — including their stories would inflate every metric.

First, get the active Epic list. Query Epics in active states:
```bash
az boards query --wiql "SELECT [System.Id], [System.Title], [System.State] FROM WorkItems WHERE [System.WorkItemType] = 'Epic' AND [System.State] NOT IN ('Closed', 'Removed', 'Unapproved / Future') ORDER BY [Microsoft.VSTS.Common.BacklogPriority]" --output json
```

If `.claude/project.team.md` contains an "Active Epics" list, use that instead — it's the user's curated view.

Save the list of active Epic IDs. Then build the full story-to-epic mapping:
1. For each active Epic, fetch child Features via `$expand=relations`
2. For each Feature, fetch child Stories via `$expand=relations`
3. Build a set of **in-scope story IDs** — only stories that roll up to an active Epic

**Every subsequent query in this report must filter to in-scope stories only.** This applies to:
- Epic progress table
- Period work items (Key Achievements)
- Developer stats (period AND project totals)
- Velocity calculations
- PR list (only PRs linked to in-scope stories)

### Step 3: Query Work Items (Scoped to Active Epics)

Get ALL stories under active Epics (for project totals and epic progress):
```bash
az boards query --wiql "SELECT [System.Id], [System.Title], [System.WorkItemType], [System.State], [Microsoft.VSTS.Scheduling.StoryPoints], [System.AssignedTo], [System.ChangedDate] FROM WorkItems WHERE [System.WorkItemType] IN ('User Story', 'Bug') AND [System.State] <> 'Removed' ORDER BY [System.AssignedTo]" --output json
```

Then filter results to only in-scope story IDs (from Step 2).

From this filtered set, calculate:
- **Epic progress**: done/total/% per Epic (all-time, not period-scoped)
- **Period work items**: stories where ChangedDate falls in the period AND state is done
- **All-time developer stats**: total points per developer across the project
- **Period developer stats**: points per developer in this period only

States that count as "done": Closed, Resolved, Dev Complete.

**Developer filtering**: The developer list is dynamic — include anyone with activity. Read `.claude/project.team.md` for a "Developer Report Exclusions" list and remove excluded names. New developers appear automatically when they first contribute.

### Step 4: Query Pull Requests (Scoped)

Get completed PRs:
```bash
curl -s -u ":{ADO_TOKEN}" "{ADO_ORG}/{ADO_PROJECT_ENCODED}/_apis/git/repositories/{ADO_REPO_ID}/pullRequests?searchCriteria.status=completed&$top=1000&api-version=7.0"
```

Filter to PRs that reference in-scope stories (check PR title for story IDs like `#1279` or `Story #1279`). PRs without a story reference should still be included if they were created by an active developer during the period — they're likely deployment fixes or infrastructure work.

Calculate per-developer PR totals (all-time and period).

### Step 5: Locate the Script

Look for `generate_status_report.py` in this order:
1. Project-local: `.claude/skills/status-report/scripts/generate_status_report.py`
2. Plugin: `tools/emergent-claude-plugin/skills/status-report/scripts/generate_status_report.py`
3. Relative to this skill: `../status-report/scripts/generate_status_report.py`

### Step 6: Install Dependencies

```bash
pip install python-docx --quiet
```

### Step 7: Draft the Report Content

**CRITICAL**: Every number in this report must be verified against ADO. Do not estimate or round — query and count. If you say an epic has 18 remaining stories, there must actually be 18 non-done, non-removed stories under that epic.

Write a JSON file with this structure:

```json
{
    "date_range": "March 9 – March 20, 2026",
    "output_path": "{OUTPUT_PATH}",
    "branding": {
        "project_name": "{PROJECT_NAME}"
    },
    "executive_summary": "2-3 sentence summary. Lead with the primary delivery theme, mention total points and stories delivered by the team, and note key milestones.",
    "sections": [
        {
            "heading": "Epic: {Epic Name}",
            "items": [
                "#{story_id}: {Title} ({N} pts) — Business-friendly description of what was delivered"
            ]
        }
    ],
    "callout": {
        "text": "MILESTONE — Brief description of a key milestone reached"
    },
    "epic_summary": [
        {"epic": "Epic Name", "done": 70, "total": 74, "pct": 94}
    ],
    "remaining_work": [
        "Epic Name (N stories remaining) — Business-friendly description of what's left, mentioning specific blocked items, stories in QA, and new work."
    ],
    "velocity": {
        "rows": [
            {"metric": "Points / Week", "period": "75.0", "overall": "55.6", "trend": "▲ 35% above avg"},
            {"metric": "Stories / Week", "period": "27.0", "overall": "26.1", "trend": "▲ On pace"},
            {"metric": "PRs / Week", "period": "38.0", "overall": "19.9", "trend": "▲ 91% above avg"},
            {"metric": "Total Points Delivered", "period": "75", "overall": "1,088", "trend": ""},
            {"metric": "Total Stories Completed", "period": "27", "overall": "510", "trend": ""}
        ],
        "totals": {"metric": "Project Duration", "period": "{PERIOD_WEEKS} week(s)", "overall": "{PROJECT_WEEKS} weeks", "trend": ""},
        "summary": "2-4 sentence narrative explaining velocity trends. If above average, explain why (e.g., production push). If below, explain context (e.g., shifting to integration work with external dependencies). Anticipate whether velocity will increase, decrease, or hold steady and why."
    },
    "developer_stats": [
        {"name": "Developer Name", "period_pts": 41, "project_pts": 604, "period_prs": 30, "project_prs": 301}
    ],
    "developer_totals": {
        "period_pts": 75,
        "project_pts": 1088,
        "period_prs": 38,
        "project_prs": 391,
        "project_weeks": 20,
        "period_weeks": 1
    },
    "developer_summary": "2-4 sentence narrative explaining the developer metrics. Call out who drove the period's output, explain velocity spikes or dips per developer, note developers who contribute via code review or QA rather than story points.",
    "blockers": ["Blocker description — or 'No active blockers' if none"],
    "next_steps": ["Next period's planned focus areas with story IDs"],
    "pull_requests": {
        "date_range_label": "M/D – M/D",
        "items": ["PR #NNN: Title (M/D)"]
    }
}
```

**Writing guidelines:**
- Every bullet must include the story ID (e.g., `#1128: Forecast Submission Tab`)
- Group sections by Epic name
- Executive summary: 2-3 sentences, lead with primary delivery, mention total team output
- Use en-dashes (–) for ranges
- Remaining work: explain what's left per epic, call out blocked items and QA items
- Velocity summary: explain the trend, anticipate future direction
- Developer summary: explain workload distribution, note role differences
- All numbers must be verified against ADO — never guess

### Step 8: Generate the Document

```bash
python "{SCRIPT_PATH}" /tmp/weekly_status_content.json
```

### Step 9: Confirm Output

Tell the user:
- The full path to the generated .docx file
- Stories completed, points delivered, PRs merged
- Any data gaps

## Report Sections (in order)

1. **Header** — Project name, "Weekly Status Update", date range, thin accent line
2. **Executive Summary** — 2-3 sentence overview
3. **Key Achievements** — Grouped by Epic, each bullet has story ID + business description
4. **Callout** — Yellow box highlighting a milestone or key metric
5. **Epic Progress** — Table: Epic / Done / Total / % Complete + Project Total row
6. **Remaining Work** — Bullet discussion of what's left per epic
7. **Velocity** — Table: Metric / This Period / Project Avg / Trend + summary narrative
8. **Developer Metrics** — Table: Developer / Period Pts / Pts/Wk / Proj Pts / Avg Pts/Wk / Period PRs / Proj PRs + summary narrative
9. **Blockers / Risks**
10. **Next Steps**
11. **Appendix: Pull Requests** — Full PR list for the period
12. **Footer** — Project name • Emergent Software • Confidential

## Table Styling

All tables use a slim, clean style:
- **Headers**: No solid fill — thin colored bottom border, bold colored text
- **Totals rows**: No solid fill — thin colored top border, bold colored text
- **Alternating rows**: Light tint background on odd rows
- **Numeric columns**: Right-aligned
- **Font**: Calibri Light 10pt in tables, 11pt body

## Notes

- This skill reuses `generate_status_report.py` from the `status-report` skill.
- Emergent branding (coral `EE3342`, navy `333F4F`) is the default. Override via `branding` in JSON.
- The date range always anchors on today going backwards — not calendar weeks.
- Keep the report concise — aim for 2-3 pages when printed.
