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
3. **ADO Repository ID** — GUID from the repo URL. Help the user find it:
   ```bash
   az repos show --repository "{repoName}" --query id -o tsv
   ```
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
- PR merge strategy: squash
- Story points: Fibonacci (1, 2, 3, 5, 8, 10)
- Splitting threshold: 13+

#### 4d. `project.testing.md` (unless --minimal)

Read the template and fill with detected test project paths and build commands.

#### 4e. `project.domains.md` (unless --minimal)

Create an empty template with instructions — domain rules are always project-specific and must be filled in manually.

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

  Skipped (already exist):
    ⏭️  .claude/project.env.md

  Next steps:
    1. Review each file and fill in any TODO placeholders
    2. Add domain-specific safety rules to project.domains.md
    3. Try /emergent-dev:check-story {storyId} to verify configuration
```

## Notes

- Never overwrite existing convention files — they may contain user customizations
- Auto-detection is best-effort — always let the user review and correct
- The `project.env.md` file may contain sensitive values (connection strings) — add to `.gitignore` if needed
