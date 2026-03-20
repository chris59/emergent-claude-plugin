---
name: dev-report
description: Generate a developer code review report (Word doc) from ADO pull requests
user-invocable: true
argument-hint: [2w|4w|8w|all]
---

# Developer Code Review Report

Generate a branded Word document that reviews all developer PRs within a timeframe.

## Arguments

The user provides an optional timeframe after `/dev-report`:
- `2w` — last 2 weeks (default)
- `4w` — last 4 weeks
- `8w` — last 8 weeks
- `all` — all completed PRs

## Instructions

### Step 0: Load Project Configuration

Read `.claude/project.env.md` and extract:
- **ADO_ORG** — Azure DevOps organization URL (e.g., `https://dev.azure.com/MyOrg`)
- **ADO_PROJECT** — Project name (e.g., `My Project`)
- **PROJECT_NAME** — Short project name used for the output file name (e.g., `MyApp`)

Configure az defaults:
```bash
az devops configure --defaults organization={ADO_ORG} project="{ADO_PROJECT}"
```

If `project.env.md` does not exist, **STOP** and tell the user:
```
Project configuration not found. Run /emergent-dev:init-project to set up
.claude/project.env.md with your ADO, database, and Azure configuration.
```

### Step 1: Parse Arguments

Parse the timeframe from the user's argument (default: `2w`). Accept `2w`, `4w`, `8w`, or `all`.

### Step 2: Ensure Dependencies

```bash
pip install python-docx anthropic
```

### Step 3: Locate the Script

Look for the report generator script in this order:
1. Project-local: `.claude/skills/dev-report/scripts/generate-dev-report.py`
2. Plugin path: `tools/emergent-claude-plugin/skills/dev-report/scripts/generate-dev-report.py`

Use the first one found. If neither exists, tell the user the script is missing and where to place it.

### Step 4: Run the Report Generator

```bash
python {SCRIPT_PATH} <timeframe>
```

The script fetches completed PRs from Azure DevOps using `{ADO_ORG}` and `{ADO_PROJECT}`, reviews each PR diff using the Claude API (`claude-sonnet-4-6`), and generates a Word document.

Output file location: `{PROJECT_NAME} - Developer Code Review Report.docx` in the current working directory. If `PROJECT_NAME` is not defined in `project.env.md`, fall back to the git repo name (from `git rev-parse --show-toplevel | xargs basename`).

### Step 5: Report Results

After the script completes, summarize:
- Number of PRs reviewed per developer
- Overall ratings per developer
- Number of critical issues found
- Full path to the generated Word document
- If any critical fixes were found, display the Critical Fixes section so the user can copy-paste it into Teams or email

## Requirements

- `ANTHROPIC_API_KEY` environment variable must be set
- Git credentials must be configured for `dev.azure.com` (used for ADO REST API auth)
- `python-docx` and `anthropic` Python packages
- `.claude/project.env.md` must define `ADO_ORG`, `ADO_PROJECT`, and (optionally) `PROJECT_NAME`
