---
name: config-doctor
description: Verify .claude/ project configuration against live ADO/Azure — resolve the repo GUID, confirm the project, pipelines, and merge strategy exist, and flag placeholder/typo drift before it silently breaks start-story/close-story/release. Run after any ADO change.
user-invocable: true
argument-hint: ""
---

# Config Doctor

Validate that the `.claude/project.*.md` convention files actually match live ADO/Azure resources.
Every emergent-dev skill substitutes values from these files into ADO API calls; a wrong-but-plausible
value (a repo *name* where a GUID is expected, a project with the wrong spacing, a renamed pipeline)
doesn't error loudly — it silently no-ops or hits the wrong target. This skill turns that latent
runtime failure into an explicit, fixable report.

Run it after `init-project`, after any ADO rename/repo move, or whenever a skill behaves as if its API
calls "did nothing."

## Instructions

### Step 0: Load configuration

Read the convention files per `tools/emergent-claude-plugin/skills/shared-preamble.md` and extract
`ADO_ORG`, `ADO_PROJECT`, `ADO_REPO_ID`, `BRANCH_USERNAME`, `MERGE_STRATEGY`, `SOLUTION`, `BUILD_CMD`,
and (if `project.cicd.md` exists) `TOPOLOGY` + the per-env `{ENV}_CI_PIPELINE_NAME` /
`{ENV}_DEPLOY_PIPELINE_NAME`.

If `project.env.md` is missing, stop and tell the user to run `/emergent-dev:init-project`.

### Step 1: Verify each value against live resources

Use the Azure DevOps MCP tools (clean JSON — never `curl ... | python`, which mangles JSON on cp1252):

| # | Check | How | Pass condition |
|---|-------|-----|----------------|
| 1 | **Org + project** | `mcp__azure-devops__core_list_projects` | `ADO_PROJECT` appears EXACTLY (watch spaces/dots — e.g. `Honda AIM` not `Honda.AIM`) |
| 2 | **Repo GUID format** | regex `^[0-9a-fA-F]{8}-([0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}$` | `ADO_REPO_ID` is a GUID, not a name |
| 3 | **Repo resolves** | `mcp__azure-devops__repo_get_repo_by_name_or_id` (repositoryId = `ADO_REPO_ID`) | returns a repo in `ADO_PROJECT` |
| 4 | **Pipelines exist** | `mcp__azure-devops__pipelines_get_build_definitions` | each configured CI/Deploy pipeline name is found (only if `project.cicd.md` present) |
| 5 | **Merge strategy** | string compare | one of `rebase`, `squash`, `noFastForward`, `rebaseMerge` |
| 6 | **Solution on disk** | `Glob` for `SOLUTION` | file exists; `BUILD_CMD` references it |

For check 3, if `ADO_REPO_ID` turns out to be a name (or a GUID that doesn't resolve), look the repo up
by name via `mcp__azure-devops__repo_list_repos_by_project`, and OFFER to rewrite `project.env.md` with
the correct GUID (AskUserQuestion before editing).

### Step 2: Report

Emit a verification table; show the actual value found and, for any failure, the exact fix:

```
Config Doctor — {ADO_PROJECT}
  ✅ ADO project      "Honda AIM" found in org DKYInc
  ✅ Repo GUID        8fafb937-1bcd-474d-837b-da3daeddfc44 → "Honda AIM"
  ❌ CI pipeline      "aim-ci-old" NOT found. Did you mean "aim-ci"? Fix {DEV}_CI_PIPELINE_NAME in project.cicd.md.
  ✅ Merge strategy   rebase (valid)
  ✅ Solution         Honda.AIM.slnf exists

  1 issue — fix project.cicd.md and re-run /emergent-dev:config-doctor.
```

If everything passes, say so plainly ("All checks passed — config is live-verified") and stop.

## Notes

- This skill is read-only EXCEPT for the optional repo-GUID rewrite in Step 1 (always confirm first).
- It shares its check logic with `init-project` Step 4.5 — keep the two in sync if either changes.
- It does NOT validate secrets/connection strings (those aren't resolvable without a DB round-trip);
  scope is ADO/Azure resource identity only.
