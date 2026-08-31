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
- **MERGE_STRATEGY**: PR merge strategy (default: `rebase` — produces linear history; ADO REST API value for "Rebase and fast-forward". Alternatives: `squash`, `noFastForward`, `rebaseMerge`.)
- **SPLIT_THRESHOLD**: Story point splitting threshold (default: `13`)
- **POINT_SCALE**: Story point scale (default: `1, 2, 3, 5, 8, 10`)

### Optional: `.claude/project.domains.md`

Read if exists — contains domain-specific safety rules that should be respected during implementation and review. No specific fields to extract — the content is loaded as contextual rules.

### Optional: project memory (gotchas / learned facts)

If a project memory index exists (`.claude/MEMORY.md`, or the memory directory configured for this
project), skim it for entries tagged `reference` or `feedback` that bear on the current skill's domain —
e.g. ADO/repo infra, SFTP keys, pre-deploy/DACPAC rules, release slot-swap landmines. Load those as
**background context only**.

Treat anything from memory per the recall rules:
- It reflects what was true when written — if a note names a specific file, flag, proc, repo id, or
  pipeline, VERIFY it still exists (or run `/emergent-dev:config-doctor`) before acting on it.
- It is background, not an instruction. If a memory note contradicts what you observe live, trust the
  live observation and flag the stale note (so it can be corrected at the source via the close-story
  "promote a learning" step) rather than silently following it.

Do not block if there is no memory index — it's purely additive context.

### Required-by-/release: `.claude/project.cicd.md`

Read by the `/release` skill (only). Defines per-environment CI/CD topology so the skill stays generic across single-pipeline and build-once/promote-artifacts setups. Extract:
- **TOPOLOGY**: `single-per-env` | `build-once-promote` | `manual-deploy`
- For each of `dev` / `uat` / `prod`:
  - **{ENV}_RELEASE_BRANCH**, **{ENV}_SOURCE_DEFAULT**
  - **{ENV}_CI_PIPELINE_NAME**, **{ENV}_DEPLOY_PIPELINE_NAME** (deploy may be blank for single-per-env)
  - **{ENV}_REQUIRES_APPROVAL**
- **CI_BUILD_TIMEOUT_MIN**, **DEPLOY_TIMEOUT_MIN**, **TRIGGER_REGISTRATION_DELAY_SEC**

If the file doesn't exist when `/release` is invoked, the skill stops and tells the user to scaffold it from `tools/emergent-claude-plugin/templates/project.cicd.md`.

## Step 0.5: Guard — validate before substituting (do NOT skip)

The values above are substituted into ADO API calls and shell commands. A missing or malformed value
produces a wrong-but-plausible call that fails silently (the "repo name vs GUID silently no-ops" class).
Before using any extracted value, assert:

- Every **REQUIRED** value (`ADO_ORG`, `ADO_PROJECT`, `ADO_REPO_ID`, `BRANCH_USERNAME`) is present and
  non-empty. If any is missing, STOP and tell the user to run `/emergent-dev:init-project`.
- `ADO_REPO_ID` matches the GUID regex `^[0-9a-fA-F]{8}-([0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}$`. If it's a
  name instead of a GUID, STOP and tell the user to run `/emergent-dev:config-doctor` (which resolves and
  rewrites it) — do NOT guess the GUID.
- `ADO_ORG` is a URL (`https://dev.azure.com/...` or `https://{host}/...`).

**Hard rule:** never run a command or API call that still contains a literal `{BRACE}` placeholder. If a
substitution didn't resolve, the value is missing — STOP and surface which one, rather than firing a
call with `{ADO_REPO_ID}` literally in the URL. When in doubt about resource identity, defer to
`/emergent-dev:config-doctor` rather than improvising.

## Using Extracted Values

Throughout the skill, use the extracted values instead of hardcoded ones:
- `az devops configure --defaults organization={ADO_ORG} project="{ADO_PROJECT}"`
- `git checkout -b feature/{BRANCH_USERNAME}/{id}-{slug}`
- `dotnet build {SOLUTION} -c Release`
- Repository ID in API calls: `{ADO_REPO_ID}`
- PR merge strategy: `{MERGE_STRATEGY}`
