---
name: init-project
description: Scaffold .claude/ convention files for a new project. Creates project.env.md, project.architecture.md, and other config files that the start-story/check-story/close-story skills read at runtime.
disable-model-invocation: true
argument-hint: [--minimal]
---

# Init Project

Scaffold `.claude/` convention files for this project so the Emergent Dev plugin skills can read project-specific configuration at runtime.

## Arguments

- `--minimal` — only create `project.env.md` (skip architecture, domains, testing, team files)

## Instructions

### Step 1: Detect Project

1. Find the git root:
   ```bash
   git rev-parse --show-toplevel
   ```

2. Auto-detect the solution file:
   ```bash
   ls *.slnf *.sln 2>/dev/null | head -1
   ```

3. Check if `.claude/` exists:
   ```bash
   ls -d .claude/ 2>/dev/null
   ```
   Create it if missing: `mkdir -p .claude`

4. Check which convention files already exist — do NOT overwrite existing files.

### Step 2: Gather Project Info

Use **AskUserQuestion** to collect required values:

1. **ADO Organization URL** — e.g., `https://dev.azure.com/MyOrg`
2. **ADO Project Name** — e.g., `My Project` (note: may contain spaces)
3. **ADO Repository ID** — the repo **GUID**, not its name. Ask for the repo *name*, then RESOLVE the
   GUID yourself via `mcp__azure-devops__repo_get_repo_by_name_or_id` (or
   `az repos show --repository "{repoName}" --query id -o tsv`) and store the resolved GUID. Storing the
   name instead of the GUID is a known footgun — a name that doesn't exactly match (spaces, dots) makes
   every later `repo_*` call silently no-op. Always write the GUID.
4. **Branch username** — their prefix for feature branches (e.g., `chrisa`)
5. **Database server** — e.g., `localhost\SQL2022` or `myserver.database.windows.net`
6. **Database name** — e.g., `MyAppDb`

### Step 3: Auto-Detect Architecture

Scan the project structure to infer architecture:

1. **Solution file**: Already detected in Step 1
2. **Project structure**: Look for Clean Architecture patterns:
   ```bash
   ls -d src/*Domain* src/*Application* src/*Infrastructure* src/*Web* src/*Api* 2>/dev/null
   ```
3. **Framework**: Check `.csproj` files for target framework, Blazor, MediatR, EF Core
4. **Test projects**: `ls -d test/* tests/* 2>/dev/null`

### Step 4: Generate Convention Files

For each file, check if it already exists. If it does, skip it and note "already exists."

#### 4a. `project.env.md` (always created)

Read the template from the plugin's `templates/project.env.md` and fill in values from Step 2.

#### 4b. `project.architecture.md` (unless --minimal)

Read the template and fill in detected values from Step 3. For values that couldn't be auto-detected, leave the placeholder with a TODO comment.

#### 4c. `project.team.md` (unless --minimal)

Read the template and fill with sensible defaults:
- PR merge strategy: rebase (linear history; "Rebase and fast-forward")
- Story points: Fibonacci (1, 2, 3, 5, 8, 10)
- Splitting threshold: 13+

#### 4d. `project.testing.md` (unless --minimal)

Read the template and fill with detected test project paths and build commands.

#### 4e. `project.domains.md` (unless --minimal)

Create an empty template with instructions — domain rules are always project-specific and must be filled in manually.

#### 4f. `project.cicd.md` (unless --minimal)

Read `templates/project.cicd.md` and create the file with placeholders. Cannot reasonably auto-detect topology or pipeline names — these must be filled in by the user. Display a hint:

```
✅ .claude/project.cicd.md — CI/CD topology and pipeline names (NEEDS MANUAL FILL-IN)
   Read it and fill in {TOPOLOGY}, {ENV}_CI_PIPELINE_NAME, {ENV}_DEPLOY_PIPELINE_NAME,
   etc. The /release skill needs this to know which pipelines to monitor.
```

### Step 4.5: Validate Configuration (do NOT skip)

Before declaring success, RESOLVE and VERIFY every external value — don't just trust what was written.
This converts the most common failure class (a plausible-but-wrong id/name that silently no-ops at
runtime) into a loud setup-time error. Run the same checks as `/emergent-dev:config-doctor` (which shares
this logic):

1. **ADO project** — round-trip `ADO_ORG` + `ADO_PROJECT` via `mcp__azure-devops__core_list_projects`;
   the project name must appear exactly (watch spaces, e.g. `Honda AIM` not `Honda.AIM`).
2. **Repo GUID** — confirm `ADO_REPO_ID` matches the GUID regex
   `^[0-9a-fA-F]{8}-([0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}$` AND resolves via
   `mcp__azure-devops__repo_get_repo_by_name_or_id`. If it's a *name* not a GUID, resolve and rewrite it.
3. **Pipelines** (only if `project.cicd.md` was filled in) — each `{ENV}_CI_PIPELINE_NAME` /
   `{ENV}_DEPLOY_PIPELINE_NAME` must exist via `mcp__azure-devops__pipelines_get_build_definitions`.
4. **Merge strategy** — `MERGE_STRATEGY` must be one of `rebase` (Rebase and fast-forward), `squash`,
   `noFastForward`, `rebaseMerge`. Anything else is rejected by the ADO REST API at auto-complete time.
5. **Solution / build** — `SOLUTION` file exists on disk; `BUILD_CMD` references it.

Emit a verification table:
```
Configuration Validation:
  ✅ ADO project      "Honda AIM" found in org DKYInc
  ✅ Repo GUID        8fafb937-... resolves to "Honda AIM"
  ✅ CI pipelines     aim-ci, aim-deploy both exist
  ✅ Merge strategy   rebase (valid)
  ✅ Solution         Honda.AIM.slnf exists
```
**Any ❌ blocks completion** — print the exact value found, what was expected, and the one-line fix.
Do not report "initialized" with a failing check.

### Step 5: Summary

Display what was created:

```
Project initialized for Emergent Dev plugin:

  Created:
    ✅ .claude/project.env.md — ADO, database, Azure config
    ✅ .claude/project.architecture.md — stack, layers, build commands
    ✅ .claude/project.team.md — PR conventions, story points
    ✅ .claude/project.testing.md — test strategy, build tools
    ✅ .claude/project.domains.md — domain rules (needs manual entry)
    ✅ .claude/project.cicd.md — CI/CD topology and pipeline names (needs manual entry)

  Skipped (already exist):
    ⏭️  .claude/project.env.md

  Next steps:
    1. Review each file and fill in any TODO placeholders
    2. Add domain-specific safety rules to project.domains.md
    3. Fill in pipeline names + topology in project.cicd.md (required by /release)
    4. Try /emergent-dev:check-story {storyId} to verify configuration
```

## Notes

- Never overwrite existing convention files — they may contain user customizations
- Auto-detection is best-effort — always let the user review and correct
- The `project.env.md` file may contain sensitive values (connection strings) — add to `.gitignore` if needed
