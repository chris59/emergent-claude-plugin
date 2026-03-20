# Shared Preamble — Load Project Configuration

Every skill in the Emergent Dev plugin starts by reading project convention files from `.claude/`.
These files provide project-specific values so skills remain generic and reusable.

## Step 0: Load Project Configuration

Before any other step, read the convention files and extract configuration values.

### Required: `.claude/project.env.md`

Read this file and extract:
- **ADO_ORG**: Organization URL (e.g., `https://dev.azure.com/MyOrg`)
- **ADO_PROJECT**: Project name (e.g., `My Project` — may contain spaces)
- **ADO_REPO_ID**: Repository GUID
- **BRANCH_USERNAME**: Username for branch naming (e.g., `jdoe`)

Configure az defaults immediately:
```bash
az devops configure --defaults organization={ADO_ORG} project="{ADO_PROJECT}"
```

If `project.env.md` does not exist, **STOP** and tell the user:
```
Project configuration not found. Run /emergent-dev:init-project to set up
.claude/project.env.md with your ADO, database, and Azure configuration.
```

### Recommended: `.claude/project.architecture.md`

Read if exists — extract:
- **SOLUTION**: Solution file path (e.g., `MyApp.slnf`)
- **BUILD_CMD**: Build command (default: `dotnet build {SOLUTION} -c Release`)
- **TEST_CMD**: Test command (default: `dotnet test {SOLUTION} -c Release --no-build`)
- **FORMAT_CMD**: Format command (default: `dotnet format whitespace {SOLUTION}`)

If not found, auto-detect: `ls *.slnf *.sln 2>/dev/null | head -1`

### Optional: `.claude/project.testing.md`

Read if exists — extract:
- **SCSS_CMD**: SCSS compilation command (skip step if not defined)
- **DB_BUILD_CMD**: Database build command (skip step if not defined)
- **REGRESSION_CMD**: Regression test command (skip step if not defined)

### Optional: `.claude/project.team.md`

Read if exists — extract:
- **MERGE_STRATEGY**: PR merge strategy (default: `squash`)
- **SPLIT_THRESHOLD**: Story point splitting threshold (default: `13`)
- **POINT_SCALE**: Story point scale (default: `1, 2, 3, 5, 8, 10`)

### Optional: `.claude/project.domains.md`

Read if exists — contains domain-specific safety rules that should be respected during implementation and review. No specific fields to extract — the content is loaded as contextual rules.

## Using Extracted Values

Throughout the skill, use the extracted values instead of hardcoded ones:
- `az devops configure --defaults organization={ADO_ORG} project="{ADO_PROJECT}"`
- `git checkout -b feature/{BRANCH_USERNAME}/{id}-{slug}`
- `dotnet build {SOLUTION} -c Release`
- Repository ID in API calls: `{ADO_REPO_ID}`
- PR merge strategy: `{MERGE_STRATEGY}`
