---
name: release
description: Release code to an environment (dev, uat, prod) with full best practices — pre-flight checks, two-stage promote-and-watch for build-once topologies, automatic semver tagging, generated release notes, ADO project wiki publication, and work item annotations. Use when you're ready to deploy.
user-invocable: true
argument-hint: <environment> [--source <branch>] [--dry-run] [--major | --minor | --patch] [--skip-uat]
---

# Release

End-to-end release automation that reads project-specific pipeline names and topology from `.claude/project.cicd.md`. Handles single-pipeline-per-env, build-once/promote-artifacts, and manual-deploy topologies. For prod releases, automatically runs the UAT release first, then promotes to main, tags the commit, generates release notes, **publishes a release subpage to the ADO project wiki**, and annotates linked work items.

## Arguments

- `dev` | `uat` | `prod` — target environment (required)
- `--source <branch>` — source branch to merge from (overrides the default in `project.cicd.md`)
- `--dry-run` — show every step that would happen, but don't push, merge, tag, or post anything
- `--major` | `--minor` | `--patch` — for prod releases, override the default semver bump
- `--skip-uat` — for `release prod`, skip the Phase A (UAT release) step. Use when UAT was already deployed separately and you just want to promote to main.

## Instructions

Follow the steps below in order. Use Bash for `git` commands and single-shot `az` calls.

> **🚨 Wait for pipelines via MCP tools + `ScheduleWakeup` — NEVER `for … sleep 15 … done` bash loops
> or `… | python -c` pipes.** On this box cp1252 mangles piped JSON → the loop's completion check never
> fires → silent infinite wait until a human notices the deploy finished. That defeats the whole point of
> driving the release to done. Use `mcp__azure-devops__pipelines_get_build_status` /
> `pipelines_get_run` to read run state (clean JSON), and re-schedule yourself with `ScheduleWakeup`
> (~150s while a run is active) so each wakeup re-checks. Single-shot `az`/`az devops invoke` calls that
> TRIGGER a run (not poll it) are fine — it's the sleep-loop *waits* and `python -c` parsing that are banned.

### Step 0: Load Project Configuration

Read the shared preamble at `tools/emergent-claude-plugin/skills/shared-preamble.md`. Extract from `.claude/project.env.md`:
- `{ADO_ORG}`, `{ADO_PROJECT}`, `{ADO_PROJECT_ENCODED}`, `{ADO_REPO_ID}`

Configure az defaults:
```bash
az devops configure --defaults organization={ADO_ORG} project="{ADO_PROJECT}"
```

**Required**: read `.claude/project.cicd.md` and extract:

**Topology and environments:**
- `{TOPOLOGY}`: `single-per-env` | `build-once-promote` | `manual-deploy`
- For each env (`dev`, `uat`, `prod`): `{ENV}_RELEASE_BRANCH`, `{ENV}_SOURCE_DEFAULT`, `{ENV}_CI_PIPELINE_NAME`, `{ENV}_DEPLOY_PIPELINE_NAME`, `{ENV}_REQUIRES_APPROVAL`

**Polling:**
- `{CI_BUILD_TIMEOUT_MIN}`, `{DEPLOY_TIMEOUT_MIN}`, `{TRIGGER_REGISTRATION_DELAY_SEC}`

**Tagging:**
- `{TAG_FORMAT}`, `{TAG_PREFIX}`, `{DEFAULT_BUMP}`, `{INITIAL_VERSION}`, `{TAG_ANNOTATED}`

**Release notes:**
- `{RELEASE_NOTES_DIR}`, `{WORK_ITEM_ID_PATTERN}`, `{ENRICH_WITH_ADO_TITLES}`, `{INCLUDE_FILE_DIFF_STAT}`, `{INCLUDE_SCHEMA_CHANGES_SECTION}`, `{INCLUDE_BUILD_ARTIFACT_INFO}`, `{POST_TO_WORK_ITEMS}`

**Production gates:**
- `{REQUIRE_PROD_CONFIRMATION}`, `{SHOW_COMMIT_LIST_BEFORE_PROD}`, `{SHOW_FILE_COUNT_BEFORE_PROD}`, `{PROD_INVOKE_VIA_AZ_PIPELINES_RUN}`

`{PROD_INVOKE_VIA_AZ_PIPELINES_RUN}` controls how `/release prod` invokes Deploy Prod:
- **`true`** (recommended for build-once-promote): Deploy Prod has NO automatic trigger. `/release prod` Phase A pushes to release/uat, watches CI + Deploy UAT, captures the upstream `aim-ci` runId. Phase B then invokes Deploy Prod explicitly via `az pipelines run --pipelines aim-ci=<runId>` — pinning the same artifact UAT validated. After Deploy Prod succeeds, Phase B ff-pushes release/uat → main as audit-trail. **Critical: `/release uat` cannot reach Deploy Prod under this model — there is no auto-trigger anywhere on the prod pipeline.**
- **`false`** (legacy): Deploy Prod fires off CI on main. Phase A watches CI + Deploy UAT only. Phase B merges release/uat → main, pushes, watches CI on main, watches Deploy Prod.

Default: `false` if absent (preserves legacy behavior for projects that haven't migrated).

**Authorization:**
- `{AUTO_AUTHORIZE_NEW_PIPELINES}`

**Wiki publishing:**
- `{WIKI_PUBLISH_ENABLED}`, `{WIKI_NAME}`, `{WIKI_RELEASE_PARENT_PATH}`, `{WIKI_INDEX_TABLE_HEADER}`, `{WIKI_INDEX_ROW_FORMAT}`

If `project.cicd.md` does not exist, **STOP** and tell the user to run `/emergent-dev:init-project` to scaffold it, or copy from `tools/emergent-claude-plugin/templates/project.cicd.md` and fill in pipeline names.

### Step 1: Parse Arguments and Resolve Environment

1. Parse positional environment (`dev` | `uat` | `prod`)
2. Parse optional flags:
   - `--source <branch>`
   - `--dry-run` (sets `DRY_RUN=true`)
   - `--major` | `--minor` | `--patch` (sets `BUMP_TYPE`, default `{DEFAULT_BUMP}`)
   - `--skip-uat` (sets `SKIP_UAT=true`, only valid with `prod`)
3. Resolve effective config: release branch, source default, CI pipeline name, deploy pipeline name, approval requirement
4. Display the resolved plan to the user as a one-line summary:
```
Release plan:
  env={env}  release_branch={RELEASE_BRANCH}  source={SOURCE}
  ci={CI_PIPELINE_NAME}  deploy={DEPLOY_PIPELINE_NAME or "(same as CI)"}
  topology={TOPOLOGY}  approval={REQUIRES_APPROVAL}
  dry_run={DRY_RUN}  bump={BUMP_TYPE if env==prod}  skip_uat={SKIP_UAT}
```

### Step 2: Pre-Flight Checks

These run for every environment.

1. **Working tree clean**: `git status --porcelain`. If dirty, `git stash push -m "auto-stash before /release"` and remember to pop in the final cleanup step.

2. **On a sane current branch**: capture `ORIGINAL_BRANCH=$(git branch --show-current)` for restore later.

3. **Fetch latest** for source, target, develop, release/uat, main, and prune deleted remote branches:
   ```bash
   git fetch origin develop release/uat main --tags --prune
   ```

4. **Re-invocation reset (CRITICAL — the "stale state" guard)**. The skill is often re-invoked after a mid-session fix has merged. The local checkout is then stale: HEAD may be on a feature branch that no longer exists on origin, file content on disk reflects pre-merge state, and any push attempt confuses the pre-push hook. Detect and recover deterministically — do NOT improvise:
   ```bash
   # If HEAD is detached or on a branch that no longer exists on origin,
   # switch to the release target so the rest of the skill operates on a
   # known-clean ref. The hook keys off the push-target ref now (require-review.py
   # was hardened in #1812) but having local HEAD on the right branch removes
   # an entire class of "wait, why is this branch state weird?" detours.
   if [ -n "$ORIGINAL_BRANCH" ]; then
     if ! git show-ref --verify --quiet "refs/remotes/origin/$ORIGINAL_BRANCH"; then
       echo "Local branch '$ORIGINAL_BRANCH' no longer exists on origin (likely deleted after PR merge)."
       echo "Switching to {release_branch} and resetting to origin/{release_branch}..."
       git checkout {release_branch}
       git reset --hard origin/{release_branch}
       ORIGINAL_BRANCH=  # Don't try to restore a deleted branch in cleanup
     fi
   fi
   ```
   This prevents tonight's failure mode where the user re-invokes `/release uat` after a fix PR merged, the local feature branch is gone-on-origin, and the skill tries to push from that orphan checkout. NEVER skip this step "because the local state looks right" — looks-right has burned us before.

5. **Check for in-flight or recently failed CI runs** on the target branch. If a previous run is still `inProgress`, STOP and tell the user — don't pile on. If the most recent completed run is `failed`, surface that and ask if the user wants to proceed.

6. **For env=prod**: verify `main` is not ahead of `release/uat` in unexpected ways. Classify the
   divergence by content before acting — do NOT blanket-STOP:
   ```bash
   MAIN_AHEAD=$(git log --oneline origin/release/uat..origin/main)
   if [ -n "$MAIN_AHEAD" ]; then
     # What do main-only commits touch?
     NONDOCS=$(git diff --name-only origin/release/uat..origin/main | grep -v "^${RELEASE_NOTES_DIR}/" || true)
     if [ -z "$NONDOCS" ]; then
       # DOCS-ONLY divergence = the legacy release-notes-on-main ratchet (pre the Phase D fix
       # that commits notes to develop). Auto-heal: backflow the notes into develop via a PR
       # (the structural fix below ensures this never re-accumulates). This is safe — release
       # notes are docs, no code/schema. Do it, don't escalate.
       echo "main is ahead of release/uat by DOCS-ONLY release-notes commits (legacy ratchet)."
       echo "Auto-healing: backflow ${RELEASE_NOTES_DIR}/ from main into develop, then continue."
       # (Reconcile: branch off develop, `git checkout origin/main -- ${RELEASE_NOTES_DIR}/`,
       #  commit, PR to develop, merge; then re-fetch. After this, develop≡main on notes.)
     else
       echo "❌ STOP: main has NON-docs commits release/uat doesn't have (real hotfix-on-main):"
       echo "$NONDOCS"
       echo "Don't merge over a direct-to-main code/schema hotfix without the user's input."
       exit 1
     fi
   fi
   ```
   **Root-cause note**: this divergence should no longer occur after the Phase D fix (release notes are
   committed to `develop` and ff-flowed up, so `main` is only ever reached by ff and never accumulates
   direct commits). The docs-only auto-heal above exists to drain the legacy backlog one final time.
   A NON-docs main-ahead state is a genuine direct-to-main hotfix and still hard-STOPs.

7. **Show what will be deployed**:
   ```bash
   git log --oneline origin/{release_branch}..origin/{source_branch}
   COMMIT_COUNT=$(git rev-list --count origin/{release_branch}..origin/{source_branch})
   FILE_COUNT=$(git diff --name-only origin/{release_branch}..origin/{source_branch} | wc -l)
   ```

8. **DIVERGENCE GUARD — STOP if release branch has commits the source doesn't.** This is the structural invariant that ff-only relies on. If a previous release (or a manual hotfix) committed directly to `{release_branch}` instead of going through `{source_branch}`, the next `git merge` would either create a forbidden merge commit or refuse with "Not possible to fast-forward". Skill MUST refuse to proceed:
   ```bash
   ORPHAN_COMMITS=$(git log --oneline origin/{source_branch}..origin/{release_branch})
   if [ -n "$ORPHAN_COMMITS" ]; then
     echo "❌ STOP: origin/{release_branch} has commits that origin/{source_branch} doesn't:"
     echo "$ORPHAN_COMMITS"
     echo ""
     echo "Per the ff-only rule, release branches must never have commits the source branch doesn't."
     echo "This usually means: (a) a hotfix was committed directly to {release_branch} instead of"
     echo "going through {source_branch}, OR (b) a prior /release run cherry-picked instead of"
     echo "ff-merging. Either way, do NOT improvise a fix — escalate to the user. Common recovery:"
     echo "if the orphan commits are safely preserved on main (the audit-trail ref), the right move"
     echo "is to hard-reset origin/{release_branch} to origin/{source_branch} via force-push, but"
     echo "the user must explicitly authorize that."
     exit 1
   fi
   ```

9. **DUPLICATE-SHA GUARD — STOP if release branch contains content-duplicates of source-branch commits.** This catches the silent failure mode where a prior release committed the same change to both branches as different SHAs (same tree hash, same author timestamp, different parent → different SHA). The divergence guard above usually catches this, but if release/uat has already been reset to "match" via cherry-pick instead of ff, the divergence guard passes while history still contains the duplicate. Detect by tree-hash overlap:
   ```bash
   # Compare patch-id of the last N commits on each branch — patch-id is stable
   # across rebases and cherry-picks, so identical content produces identical IDs.
   git log --format="%H" origin/{release_branch} | head -20 | while read sha; do
     pid=$(git show "$sha" | git patch-id --stable | awk '{print $1}')
     match=$(git log --format="%H" origin/{source_branch} | head -50 | while read s2; do
       p2=$(git show "$s2" | git patch-id --stable | awk '{print $1}')
       [ "$pid" = "$p2" ] && [ "$sha" != "$s2" ] && echo "$sha ↔ $s2"
     done)
     if [ -n "$match" ]; then
       echo "⚠️  DUPLICATE-SHA WARNING: $sha on {release_branch} has same content as a different SHA on {source_branch}: $match"
       echo "    This means the same change was committed to both branches separately (cherry-pick or direct commit)."
       echo "    Continuing the release is safe (the duplicate is already shipped) but the underlying skill bug"
       echo "    or operator improvisation must be fixed before the next release."
     fi
   done
   ```
   This is a WARNING, not a STOP — by the time you see this, the bad commits are already on both branches and blocking the release helps nothing. Use it to alert the user and trigger investigation of which previous release introduced the duplicate.

10. **Already-up-to-date handling**. If `COMMIT_COUNT == 0`, do NOT silently STOP — that hides the common re-invocation case where the user already ff-pushed in a prior turn but the deploy never actually shipped. Instead, check whether the most recent successful Deploy {ENV} run's `sourceVersion` matches `origin/{release_branch}`'s tip:
    - Get the most recent **succeeded** Deploy {ENV} run via `mcp__azure-devops__pipelines_list_runs`
      (definition `$deployId`) and read its `sourceVersion` (clean JSON — no `python -c` parse).
    - Compare to `git rev-parse origin/{release_branch}`:
      - **Equal** → `release/{release_branch}` is already deployed for this SHA. Report "Nothing to do" and stop.
      - **Different** → set `SKIP_MERGE=true` (the branch is up to date but this SHA was never deployed).

    With `SKIP_MERGE=true`, jump past Step 4 step 1-2 (update-ref/push) and go straight to Step 4 step 3 (invoke Deploy + watch). This handles the re-invocation case cleanly without the user having to think about it.

11. Display summary:
```
Ready to release to {ENVIRONMENT}:
  Source: {source_branch}
  Target: {release_branch}
  Commits: {COMMIT_COUNT} new commits
  Files: {FILE_COUNT} files changed
```

12. If `--dry-run`, **continue through every subsequent step** but skip any `git push`, `az pipelines run`, `git tag`, or `az boards work-item update` calls. Print what each step WOULD do.

### Step 3: Branch routing — pick the right phase

The release flow depends on the environment:

- **`dev`**: Single phase. Merge source → develop, push, watch CI, watch Deploy_Dev (or skip if topology has same-pipeline dev deploy). Skip tagging entirely. Skip release notes. Skip Phase B.
- **`uat`**: Single phase. Merge source → release/uat, push, watch CI, watch Deploy UAT. Skip tagging unless project config opts in (typically off — UAT releases don't get tagged). Skip Phase B.
- **`prod`**: Multi-phase orchestration. Topology-aware:
  - **Phase A** (unless `--skip-uat`): merge develop → release/uat, push, watch CI on release/uat, watch Deploy UAT. **Gate on Deploy UAT success** before Phase B. Capture the upstream `aim-ci` run ID that Deploy UAT consumed — it's the artifact that will be promoted to prod.
  - **Phase B**: confirm with user (if `{REQUIRE_PROD_CONFIRMATION}=true`). Topology branch:
    - If `{PROD_INVOKE_VIA_AZ_PIPELINES_RUN}=true`: invoke Deploy Prod via `az pipelines run`, pinning the `aim-ci` resource to the runId captured in Phase A. Watch Deploy Prod to completion. Then ff-push release/uat → main as audit-trail bookkeeping (main does NOT trigger any deploy).
    - Otherwise (legacy main-trigger topology): merge release/uat → main, push, watch CI on main, watch Deploy Prod (handle approval gate).
  - **Phase C**: compute next version, create annotated tag, push tag.
  - **Phase D**: generate release notes file, embed in tag annotation.
  - **Phase E**: publish release subpage to ADO project wiki + add row to release index page (if `{WIKI_PUBLISH_ENABLED}=true`).
  - **Phase F**: post to ADO work items (if `{POST_TO_WORK_ITEMS}=true`).
  - **Phase G**: print final report with all URLs.

For `dev` and `uat`, jump to Step 4 (Single Phase). For `prod`, jump to Step 5 (Multi-Phase Prod Release).

### Step 4: Single Phase Release (dev / uat)

Used by `release dev` and `release uat`.

**Topology note for `uat`** (build-once-promote, story #1806): the push to `release/uat` is audit-trail only — it does NOT trigger a CI rebuild. The artifact already exists on develop's CI run from when the source SHA was merged. `/release uat` looks up that develop CI run by SHA, captures its **buildNumber string** (e.g. `20260502.11`), then explicitly invokes Deploy UAT via `az devops invoke` POST to `/pipelines/{id}/runs` with `resources.pipelines.aim-ci.version` = the buildNumber. This pins the exact artifact develop already produced. This mirrors how `/release prod` invokes Deploy Prod (Phase B) — same pattern, same guarantee that no auto-trigger reaches UAT/Prod without an explicit `/release {env}` invocation.

**CRITICAL**: do NOT use `az pipelines run --pipelines aim-ci=<runId>`. The `--pipelines` flag is unrecognized in azure-devops CLI extension v1.0.2 (and ADO's REST API needs the `version` field to be the **buildNumber string**, not the runId integer). See Step 6 (`build-once-promote` routine) for the correct invocation.

**CRITICAL — release branches are ff-only refs from `{source_branch}`.** Never `git checkout {release_branch}` + `git merge`. Never `git cherry-pick` onto `{release_branch}`. Never commit directly to `{release_branch}`. The skill MUST use `git update-ref` + `git push origin {release_branch}` and nothing else. A `git merge` is destructive here for two reasons: (a) if release/uat has any commits develop doesn't, merge either creates a merge commit (forbidden per the linear-history rule) or refuses with "Not possible to fast-forward"; (b) if a previous release wrongly committed something directly to release/uat instead of going through develop, the next `git merge` will silently apply the change a second time, creating a duplicate SHA in history (the v0.9.2/v0.9.3 failure mode — same content, same author timestamp, different parent → different SHA). The ff-only path makes both classes mechanically impossible.

1. **Skip steps 1-2 entirely if `SKIP_MERGE=true`** (set in Step 2.10 when the release branch is already up-to-date but Deploy hasn't shipped that SHA yet — re-invocation case). Jump to step 3 (invoke Deploy + watch).

2. **Fast-forward the release branch via `update-ref` + `push`** — NO checkout, NO merge, NO working tree mutation:
   ```bash
   # Pre-flight divergence guard already ran in Step 2.8 — if release/uat had any
   # commits develop didn't, this skill STOPPED before reaching here. Reaching this
   # step means origin/{release_branch} is strictly behind origin/{source_branch},
   # so the update-ref is unambiguously a fast-forward.
   SOURCE_SHA=$(git rev-parse origin/{source_branch})
   git update-ref refs/heads/{release_branch} "$SOURCE_SHA"
   git push origin {release_branch}
   ```
   This is the same pattern Phase B uses to update main. It mechanically cannot produce a merge commit or a duplicate SHA — the release branch tip is simply pointed at the source branch's SHA. If `--dry-run`, skip the push but still do the local `update-ref` so the diff is real.

   For `uat` under build-once-promote: this push moves the release/uat tip but does NOT trigger any pipeline. CI was already produced when the source SHA was merged to develop.

3. **Watch CI and Deploy** by topology — see Step 6 (Pipeline Polling Routines). Use the routine matching `{TOPOLOGY}` and the env's pipeline names.

4. **Cleanup**: switch back to `ORIGINAL_BRANCH`, `git stash pop` if stashed.

5. **Final report**:
```
Release to {ENVIRONMENT} complete:
  Fast-forwarded {release_branch} -> {source} ({COMMIT_COUNT} commits, {FILE_COUNT} files)
  CI run: #{ciRunNumber}  {ciResult}  {ciUrl}
  Deploy run: #{deployRunNumber}  {deployResult}  {deployUrl}    (omit for single-per-env)
  Commit SHA deployed: {sourceVersion}
  Returned to branch: {ORIGINAL_BRANCH}
```

### Step 5: Multi-Phase Prod Release

Used only by `release prod`.

#### Phase A — UAT release (skip if `--skip-uat`)

1. Fast-forward release/uat to develop via `git update-ref` + `git push` (steps from Step 4 with `release_branch=release/uat`, `source=develop`). NEVER `git checkout release/uat && git merge` — see the CRITICAL note in Step 4. For build-once-promote, the push to release/uat is audit-trail only — no CI rebuild.
2. **Look up the develop CI run** for the SHA being released (the run produced when the source SHA was merged to develop), using the routine in Step 6. Capture the CI run ID into `${RELEASE_CI_RUN_ID}` — this is the artifact that will be promoted to prod in Phase B. (Pre-#1806 this was the release/uat CI run; since story #1806, release/uat no longer produces CI artifacts.)
3. **Invoke Deploy UAT** explicitly via the `az devops invoke` POST documented in Step 6 (`build-once-promote` routine), pinning the `aim-ci` resource to the **buildNumber** for `${RELEASE_CI_RUN_ID}` (NOT the runId itself — see Step 6). Watch it using the same routine. Same pattern Phase B uses for Deploy Prod.
4. **Gate check**: if either CI or Deploy UAT fails, STOP. Do not proceed to Phase B. Do not tag. Print the failure and instruct the user to fix and re-run.
5. If both succeed, immediately proceed to Phase B. **Note: Deploy Prod is NOT triggered or watched in Phase A — `/release uat` runs the same Phase A code path and must not reach prod.**

#### Phase B — Prod deploy + main update

Behavior depends on `{PROD_INVOKE_VIA_AZ_PIPELINES_RUN}`.

**If `{PROD_INVOKE_VIA_AZ_PIPELINES_RUN}=true`** (modern topology — Deploy Prod has no automatic trigger, must be invoked explicitly):

1. **If `{REQUIRE_PROD_CONFIRMATION}=true`**: show the commit list and file count for `release/uat → main` and use **AskUserQuestion** with options "Yes, deploy to production" / "No, abort". If aborted, restore branch and stop.

2. **Invoke Deploy Prod**, pinning the `aim-ci` resource to the same CI run UAT consumed:
   ```bash
   # Resolve Deploy Prod's pipeline definition ID (not a run ID)
   DEPLOY_PROD_PIPELINE_ID=$(az pipelines list \
     --org "${ADO_ORG}" \
     --project "${ADO_PROJECT}" \
     --query "[?name=='${PROD_DEPLOY_PIPELINE_NAME}'].id" -o tsv)

   # Resolve the buildNumber STRING for the CI run captured in Phase A.
   # CRITICAL: the pipelines/runs API's `version` field expects the
   # buildNumber string (e.g. "20260502.11"), NOT the runId integer (3203).
   # Passing the runId silently produces a run with the validation error
   # "Unable to resolve version <runId> for pipeline aim-ci".
   # Empirically verified 2026-05-02 after three failed attempts.
   RELEASE_CI_BUILD_NUMBER=$(az pipelines runs show \
     --org "${ADO_ORG}" \
     --project "${ADO_PROJECT}" \
     --id "${RELEASE_CI_RUN_ID}" \
     --query buildNumber -o tsv)

   # Build the run-pipeline POST body. az pipelines run --pipelines is
   # unrecognized in azure-devops CLI extension v1.0.2 — use az devops
   # invoke against the pipelines/runs REST API directly.
   # Use a Windows-style absolute path because MSYS bash + az CLI mangles
   # /tmp paths when reading --in-file.
   BODY_PATH="$(cygpath -w /tmp/run-deploy-prod.json 2>/dev/null || echo /tmp/run-deploy-prod.json)"
   cat > "$BODY_PATH" <<EOF
   {
     "resources": {
       "pipelines": {
         "aim-ci": {
           "version": "${RELEASE_CI_BUILD_NUMBER}"
         }
       }
     }
   }
   EOF

   # MSYS_NO_PATHCONV=1 prevents Git Bash from mangling the leading /
   DEPLOY_PROD_RUN_ID=$(MSYS_NO_PATHCONV=1 az devops invoke \
     --org "${ADO_ORG}" \
     --area pipelines \
     --resource runs \
     --route-parameters \
         project="${ADO_PROJECT}" \
         pipelineId="${DEPLOY_PROD_PIPELINE_ID}" \
     --http-method POST \
     --in-file "$BODY_PATH" \
     --api-version 7.1 \
     --query id -o tsv)

   echo "Queued Deploy Prod run ${DEPLOY_PROD_RUN_ID} pinned to aim-ci buildNumber ${RELEASE_CI_BUILD_NUMBER} (runId ${RELEASE_CI_RUN_ID})"
   ```
   This pins the `aim-ci` pipeline-resource to the exact CI run captured in Phase A — bit-for-bit identical artifact.

   **Why `az devops invoke` and not `az pipelines run`?** The `--pipelines` flag exists in the azure-devops extension's GitHub source for v1.0.3+ but is **unrecognized in v1.0.2** (the version installed on Honda Windows boxes and CI agents as of May 2026). The REST API has always supported pipeline-resource pinning via the `resources.pipelines.<alias>.version` field, so we go through `az devops invoke` for portability. The `version` field MUST be the buildNumber string (`20260502.11`), not the runId integer (`3203`) — the API accepts the integer but fails validation with `"Unable to resolve version <runId>"`. Empirically confirmed 2026-05-02 after three failed Deploy UAT attempts.

3. Watch the Deploy Prod run using the routine in Step 6. If it fails, STOP. Do not tag. Print the failure with the run URL and tell the user to investigate.

4. After Deploy Prod succeeds, ff-push release/uat → main as audit-trail bookkeeping:
   ```bash
   git fetch origin release/uat main
   git update-ref refs/heads/main origin/release/uat
   git push origin main
   ```
   This is a fast-forward pointer move, NOT a 3-way merge. Per project preference (linear history, no merge commits), use `update-ref` + `push` rather than `git checkout main && git merge`. The main push triggers a CI audit run on main that is not consumed by any deploy pipeline.

**Otherwise** (legacy topology — Deploy Prod fires off main push):

1. **If `{REQUIRE_PROD_CONFIRMATION}=true`**: show the commit list and file count for `release/uat → main` and use **AskUserQuestion** with options "Yes, deploy to production" / "No, abort". If aborted, restore branch and stop.

2. Switch to main, pull, merge release/uat, push.

3. Watch CI on main, then watch the Prod deploy pipeline.

4. **Approval gate**: if `{PROD_REQUIRES_APPROVAL}=true`, the deploy will pause at the env approval check. Tell the user explicitly:
   ```
   {PROD_DEPLOY_PIPELINE_NAME} is waiting for approval at the prod environment gate.
   Approve at: {ADO_ORG}/{ADO_PROJECT_ENCODED}/_build/results?buildId={deployRunId}
   ```
   Continue polling — once approval lands, the deploy resumes automatically.

5. If Deploy Prod fails, STOP. Do not tag. Print the failure with the run URL and tell the user to investigate.

#### Phase C — Tag the release

1. **Compute next version**:
   ```bash
   # Get the latest matching tag
   LATEST_TAG=$(git tag -l "${TAG_PREFIX}*" --sort=-v:refname | head -1)
   if [ -z "$LATEST_TAG" ]; then
     # Bootstrap: no prior tags
     NEW_VERSION="${INITIAL_VERSION}"
   else
     # Strip prefix
     CURRENT_VERSION="${LATEST_TAG#$TAG_PREFIX}"
     # Parse semver
     IFS='.' read -r MAJOR MINOR PATCH <<< "$CURRENT_VERSION"
     case "$BUMP_TYPE" in
       major) MAJOR=$((MAJOR + 1)); MINOR=0; PATCH=0 ;;
       minor) MINOR=$((MINOR + 1)); PATCH=0 ;;
       patch) PATCH=$((PATCH + 1)) ;;
     esac
     NEW_VERSION="${MAJOR}.${MINOR}.${PATCH}"
   fi
   NEW_TAG="${TAG_PREFIX}${NEW_VERSION}"
   ```

2. **Idempotence check**: if a tag with this name already exists, fetch it and compare its commit:
   - Same commit as `main` HEAD: no-op, log "tag already correct"
   - Different commit: STOP and ask the user (someone else may have tagged in the meantime)

3. **Compute the tag commit**: the tag points at `origin/main` HEAD after Phase D's ff-flow — i.e. the
   release-notes commit (`NOTES_SHA`), which is identical content on develop, release/uat, and main.
   This is the prod-deployed code plus its notes.

4. **Generate release notes** (Phase D below) FIRST, because the notes commit becomes the tag target.
   Phase D commits the notes on develop and ff-flows them up to main, so the tag captures code + notes
   while keeping all three branches in lock-step (no main-ahead divergence for the next release).

5. **Create annotated tag**:
   ```bash
   git tag -a "${NEW_TAG}" "${PROD_COMMIT_SHA}" -F "${RELEASE_NOTES_FILE}"
   ```

6. **Push the tag** (skip if `--dry-run`):
   ```bash
   git push origin "${NEW_TAG}"
   ```

#### Phase D — Generate release notes

Phase D actually runs BEFORE Phase C (the notes are needed for the tag annotation). The numbering reflects logical order, not execution order.

1. **Determine the previous prod tag**:
   ```bash
   PREVIOUS_TAG=$(git tag -l "${TAG_PREFIX}*" --sort=-v:refname | sed -n '2p')
   # If no previous tag, use the first commit on main
   if [ -z "$PREVIOUS_TAG" ]; then
     PREVIOUS_TAG=$(git rev-list --max-parents=0 origin/main | head -1)
   fi
   ```

2. **Collect commits** between previous tag and the new prod commit:
   ```bash
   git log "${PREVIOUS_TAG}..${PROD_COMMIT_SHA}" --no-merges --pretty=format:"%h|%an|%s"
   ```

3. **Parse work item IDs** using `{WORK_ITEM_ID_PATTERN}` (Python regex). Group commits by ID. Commits without an ID go to "Other".

4. **If `{ENRICH_WITH_ADO_TITLES}=true`**: for each unique work item ID, call:
   ```bash
   az boards work-item show --id {id} --query "fields.\"System.Title\"" -o tsv
   ```
   Cache the title for use in the notes file and Phase E.

5. **Compute optional sections**:
   - **File diff stat** (if `{INCLUDE_FILE_DIFF_STAT}=true`):
     ```bash
     git diff --shortstat "${PREVIOUS_TAG}..${PROD_COMMIT_SHA}"
     ```
   - **Schema changes** (if `{INCLUDE_SCHEMA_CHANGES_SECTION}=true`): list any `.sqlproj` or `*.sql` files in the diff that touch a directory containing "Database":
     ```bash
     git diff --name-only "${PREVIOUS_TAG}..${PROD_COMMIT_SHA}" | grep -E "\.(sqlproj|sql)$" | grep -i "database"
     ```
   - **Build artifact info** (if `{INCLUDE_BUILD_ARTIFACT_INFO}=true`): the CI build number and URL from the prod CI run captured during Phase B polling.

5b. **Compose `{NON_TECHNICAL_SUMMARY}` (REQUIRED).** Before rendering, write a 3–6 sentence
   plain-language summary aimed at management / stakeholders, following the rules in the
   "Release summary" block of the template below. Base it on the enriched ADO story titles
   (step 4) plus your understanding of what the work does for users — NOT on commit subjects.
   Cover: why the release went out, what changed for users, and who is affected / whether any
   action is needed. This section is non-optional; if the release is pure plumbing, state that
   there are no user-facing changes and explain the business reason in lay terms anyway. Do NOT
   ship a release-notes file whose Release summary is empty, a commit-subject dump, or jargon.

5c. **Compose `{TECHNICAL_NARRATIVE}` (REQUIRED).** Also write a 2–5 sentence narrative for the
   technical team (developers/ops), following the rules in the "Technical summary" block of the
   template. Cover root causes, the approach, migrations/infra/config changes, and prod risks
   to watch. Jargon and identifiers are fine here. Release notes serve two distinct audiences —
   management (Release summary) and engineers (Technical summary) — and BOTH must be filled in.

6. **Render the markdown file** to `{RELEASE_NOTES_DIR}/{NEW_TAG}.md`:

```markdown
# Release {NEW_TAG}

**Released:** {YYYY-MM-DD}
**Commit:** [`{shortSha}`]({ADO_ORG}/{ADO_PROJECT_ENCODED}/_git/{repo}?version=GC{fullSha})
**Previous release:** {PREVIOUS_TAG}

## Release summary

> **MANDATORY — write this in plain, non-technical language for a management / stakeholder
> audience (PMs, account managers, the client liaison), NOT for developers.** This is the
> first thing readers see and is what gets relayed to the client. It must answer, in 3–6
> sentences with NO jargon, NO proc/file/flag names, and NO ticket-speak:
>   1. **Why did this release go out?** — the business reason or request that drove it.
>   2. **What changed for users?** — what someone using the system will now see or be able to
>      do, or what was broken and is now fixed, described in terms of their workflow.
>   3. **Who is affected and is any action needed?** — which roles/users, and whether anyone
>      must do anything (e.g. "no action required" or "dealers should refresh their forecast").
> Lead with the user/business impact. If the release is purely internal plumbing with no
> visible change, say so explicitly ("No user-facing changes; this release fixes the
> infrastructure that keeps nightly data imports running.") and still give the business reason
> in lay terms. A non-technical reader must be able to email the client a 2-line summary from
> this section alone. Compose it from the enriched ADO story titles + your understanding of the
> work — do NOT restate commit subjects.

{NON_TECHNICAL_SUMMARY}

## Technical summary

> **For the technical team (developers, ops).** A short narrative of WHAT changed under the
> hood and WHY, written for engineers — root causes, the approach taken, notable risks,
> migrations, config/infra changes, and anything to watch in prod. This is distinct from the
> Release summary above: jargon, proc/file/flag names, and ticket IDs are welcome here. 2–5
> sentences of narrative, then the stats line. Do NOT just repeat the business summary in
> technical words — say what an engineer reviewing or supporting this release needs to know.

{TECHNICAL_NARRATIVE}

{COMMIT_COUNT} commits, {FILE_COUNT} files changed{, +{insertions} -{deletions} if INCLUDE_FILE_DIFF_STAT}.

## Stories shipped

### #1452 — {story title from ADO}
- {commit hash} {commit subject}
- {commit hash} {commit subject}

### #1450 — {story title}
- {commit hash} {commit subject}

### Other
- {commit hash} {commit subject}

## Schema Changes

{section only present if INCLUDE_SCHEMA_CHANGES_SECTION and any files matched}

The following database files changed in this release:
- src/MyApp.Database/Tables/MyTable.sql
- src/MyApp.Database/Scripts/PreDeploy/Patches/2026-04-10_001_FixSomething.sql

Review these files for schema migrations, breaking changes, and pre-deploy ordering.

## Build artifacts

{section only present if INCLUDE_BUILD_ARTIFACT_INFO}

- CI run: [#{ciBuildNumber}]({ciRunUrl})
- Deploy run: [#{deployBuildNumber}]({deployRunUrl})
- Source SHA: {fullSha}

## How to roll back

To revert this release, redeploy the previous tag's commit via the prod deploy pipeline with the resources picker:
1. ADO -> Pipelines -> {PROD_DEPLOY_PIPELINE_NAME} -> Run pipeline
2. Resources -> {ci_pipeline_resource_alias} -> select the run that produced {PREVIOUS_TAG}
3. Run -> approve
```

7. **Save and commit the file to `develop`, then ff-flow it up to main** — NEVER commit release notes
   directly to main. Committing notes only to main is what created the recurring "main is ahead of
   release/uat" divergence ratchet (main accumulated notes commits that never flowed back, so every
   subsequent release's pre-flight guard stopped on a dirty divergence). The invariant is: **main is
   reached ONLY by fast-forward from release/uat; release/uat ONLY by fast-forward from develop.**
   Release notes are docs that belong on the dev line too, so they ride that same ff chain.
   ```bash
   # Commit the notes on develop (the integration branch), not main.
   git fetch origin develop release/uat main
   git checkout develop
   git pull --ff-only origin develop
   mkdir -p "${RELEASE_NOTES_DIR}"
   # Write the rendered markdown to ${RELEASE_NOTES_DIR}/${NEW_TAG}.md
   git add "${RELEASE_NOTES_DIR}/${NEW_TAG}.md"
   git commit -m "Release notes for ${NEW_TAG}"
   bash .claude/hooks/stamp-review.sh   # if the project uses a stamp hook
   git push origin develop

   # ff-flow the notes commit develop -> release/uat -> main (pointer moves only, no merges).
   NOTES_SHA=$(git rev-parse develop)
   git update-ref refs/heads/release/uat "$NOTES_SHA"
   git push origin release/uat
   git update-ref refs/heads/main "$NOTES_SHA"
   git push origin main
   ```

   **Why this order works and never ratchets**: by the time Phase D runs, Phase B has already pointed
   main at release/uat's tip (the deployed code). develop is at that same code tip plus nothing else
   (release/uat and main were just ff'd from it in Phase A/B). Committing the notes on develop and
   ff-ing the single new commit up to release/uat then main keeps all three branches identical — main
   is NEVER ahead of release/uat, so the next release's divergence guard always passes. `PROD_COMMIT_SHA`
   for the tag (Phase C) is this `NOTES_SHA` (main's new HEAD). The develop and main pushes each trigger
   a CI audit run; with `{PROD_INVOKE_VIA_AZ_PIPELINES_RUN}=true` neither feeds a deploy pipeline. The
   release/uat push triggers nothing (per topology).

   If `--dry-run`, just print the file content to stdout, don't write, commit, or push.

8. Print the release notes file path so the user can review.

#### Phase E — Publish to ADO project wiki (if `{WIKI_PUBLISH_ENABLED}=true`)

Create a new wiki subpage with the release details, and add a row to the release index page on the parent.

**Required config from `project.cicd.md`:**
- `{WIKI_NAME}` — e.g., `Honda-AIM.wiki`
- `{WIKI_RELEASE_PARENT_PATH}` — e.g., `/Release Notes`
- `{WIKI_INDEX_TABLE_HEADER}` — e.g., `| Version | Released | Headline |`
- `{WIKI_INDEX_ROW_FORMAT}` — e.g., `| [[Release Notes/{TAG}|{TAG}]] | {DATE} | {HEADLINE} |`

**Step 1: Build the subpage content.** Render a markdown file with the same structure as the docs/releases/{tag}.md file but adapted for ADO Wiki conventions:
- Add `[[_TOC_]]` near the top for auto-generated table of contents
- For cross-references to other wiki pages, **use absolute URL paths instead of `[[Page Name]]` syntax**. The bracket-link form only resolves when the target page is at the wiki root, which silently breaks for nested pages (e.g., `Architecture & Development/Branching Strategy`). Use this format instead: `[Display Text](/{ADO_PROJECT_ENCODED}/_wiki/wikis/{WIKI_NAME}?pagePath={URL_ENCODED_FULL_PATH})`. For example, to link to `/Release Notes` in Honda AIM: `[Release Notes](/Honda%20AIM/_wiki/wikis/Honda-AIM.wiki?pagePath=%2FRelease%20Notes)`. Note that the `pagePath` value uses `%2F` for path separators inside the wiki, while spaces become `%20` in both the project name and the path.
- Include the same sections: Quick facts table, **Release summary** (the non-technical `{NON_TECHNICAL_SUMMARY}` written in Phase D step 5b — management-facing, appears near the top right after Quick facts), **Technical summary** (the `{TECHNICAL_NARRATIVE}` from step 5c — engineer-facing), Headline, What shipped, Stats, Stories shipped table, Schema changes, Build artifacts, Deploy history (if relevant)
- Save the rendered content to a temp file: `/tmp/wiki-release-{TAG}.md`

**Step 2: Create the subpage:**
```bash
MSYS_NO_PATHCONV=1 az devops wiki page create \
  --wiki "{WIKI_NAME}" \
  --path "{WIKI_RELEASE_PARENT_PATH}/{NEW_TAG}" \
  --file-path /tmp/wiki-release-{NEW_TAG}.md
```
The `MSYS_NO_PATHCONV=1` prefix is required on Windows MSYS bash to prevent path mangling on the leading `/` in the wiki path.

**Idempotence check**: if the page already exists for this tag, skip the create and update instead via `az devops wiki page update --version {existingEtag}`.

**Step 3: Add a row to the parent index page.**
Fetch the current parent page content:
```bash
MSYS_NO_PATHCONV=1 az devops wiki page show \
  --wiki "{WIKI_NAME}" \
  --path "{WIKI_RELEASE_PARENT_PATH}" \
  --include-content -o json > /tmp/wiki-parent-current.json
```
Extract `eTag` and `content` from the JSON response.

Find the line matching `{WIKI_INDEX_TABLE_HEADER}` in the content, find the next line (the markdown separator like `|---|---|---|`), and insert the new row immediately after the separator (so newest releases appear at the top of the table).

Format the new row using `{WIKI_INDEX_ROW_FORMAT}`, substituting:
- `{TAG}` → `{NEW_TAG}` (e.g., `v0.9.1`)
- `{DATE}` → today's date (`YYYY-MM-DD`)
- `{HEADLINE}` → a one-sentence, **plain-language, non-technical** summary of why the release went out and what changed for users — written so a PM or account manager can paste it into a client email. Derive it from the `{NON_TECHNICAL_SUMMARY}` you wrote in Phase D step 5b (NOT from commit subjects, proc names, or ticket IDs). Lead with user/business impact.

Write the updated content to `/tmp/wiki-parent-updated.md`:
```bash
python3 - <<PY
import json
with open('/tmp/wiki-parent-current.json') as f:
    d = json.load(f)
content = d['page']['content']
header = "{WIKI_INDEX_TABLE_HEADER}"
row = "{WIKI_INDEX_ROW_FORMAT}".replace("{TAG}", "{NEW_TAG}").replace("{DATE}", "$(date +%Y-%m-%d)").replace("{HEADLINE}", "{HEADLINE}")
lines = content.split("\n")
new_lines = []
inserted = False
i = 0
while i < len(lines):
    new_lines.append(lines[i])
    if not inserted and lines[i].strip() == header.strip():
        # Append the separator line as-is
        if i + 1 < len(lines):
            new_lines.append(lines[i + 1])
            new_lines.append(row)
            i += 2
            inserted = True
            continue
    i += 1
if not inserted:
    raise SystemExit("ERROR: could not find index table header in wiki parent page")
with open('/tmp/wiki-parent-updated.md', 'w', encoding='utf-8') as f:
    f.write("\n".join(new_lines))
PY
```

Update the parent page with the new content (eTag from the show command):
```bash
MSYS_NO_PATHCONV=1 az devops wiki page update \
  --wiki "{WIKI_NAME}" \
  --path "{WIKI_RELEASE_PARENT_PATH}" \
  --file-path /tmp/wiki-parent-updated.md \
  --version "${parentEtag}"
```

**Skip everything in Phase E if `--dry-run`** — print the rendered subpage content and the new index row to stdout instead.

If `{WIKI_PUBLISH_ENABLED}=false`, skip Phase E entirely.

#### Phase F — Annotate ADO work items (if `{POST_TO_WORK_ITEMS}=true`)

For each unique work item ID extracted in Phase D:
```bash
az boards work-item update --id {id} --discussion "<p>Shipped in <strong>${NEW_TAG}</strong> on $(date +%Y-%m-%d).</p>"
```

Skip if `--dry-run`. Skip if no work item IDs were extracted.

#### Phase G — Final report

```
Production release {NEW_TAG} complete:
  Phase A — UAT:
    CI #{uatCiRun}: succeeded ({uatCiUrl})
    Deploy UAT #{uatDeployRun}: succeeded ({uatDeployUrl})
  Phase B — Prod:
    Merged release/uat -> main ({COMMIT_COUNT} commits, {FILE_COUNT} files)
    CI #{prodCiRun}: succeeded ({prodCiUrl})
    Deploy Prod #{prodDeployRun}: succeeded ({prodDeployUrl})
  Phase C — Tag:
    Created annotated tag {NEW_TAG} on {prodCommitSha}
    Pushed to origin
  Phase D — Release notes:
    {RELEASE_NOTES_DIR}/{NEW_TAG}.md
    {N} stories shipped, {M} other commits
  Phase E — Wiki publish:
    Created subpage {WIKI_RELEASE_PARENT_PATH}/{NEW_TAG} ({wikiSubpageUrl})
    Added row to release index on {WIKI_RELEASE_PARENT_PATH}
  Phase F — Work item annotations:
    Posted "Shipped in {NEW_TAG}" to {N} work items
  Returned to branch: {ORIGINAL_BRANCH}
```

### Step 6: Pipeline Polling Routines

The polling logic depends on `{TOPOLOGY}`. Each routine identifies the run, then **waits via
`ScheduleWakeup` + MCP** (per the banner at the top of Instructions) until the run reaches a terminal
state — NOT bash `sleep` loops or `python -c` parsing. Each routine returns the run id, status, result,
and source URL.

#### Routine: `single-per-env`

The CI pipeline both builds and deploys in the same run. Wait for one pipeline to complete.

1. Give the trigger a moment to register (a single `Bash` `sleep {TRIGGER_REGISTRATION_DELAY_SEC}` is
   fine — it's a one-shot delay, not a poll loop), then resolve the pipeline definition id:
   `az pipelines list --query "[?name=='{CI_PIPELINE_NAME}'].id" -o tsv`.
2. Find the run for our push via `mcp__azure-devops__pipelines_list_runs` (or `pipelines_get_builds`
   with `branchName: "refs/heads/{release_branch}"`); pick the newest run whose source version matches
   `{commit_sha_we_pushed}` (first 8 chars).
3. **Wait** for that run with `mcp__azure-devops__pipelines_get_build_status` (`status: 2` = completed;
   read `result`), re-scheduling via `ScheduleWakeup` (~150s) until terminal. Timeout budget:
   `{CI_BUILD_TIMEOUT_MIN}` minutes.

#### Routine: `build-once-promote`

The CI pipeline builds artifacts on `develop` (the only artifact-producing branch). The deploy pipeline does NOT auto-fire — `/release uat` and `/release prod` invoke it explicitly via `az devops invoke` POST to `/pipelines/{id}/runs`, pinning the develop CI run's **buildNumber** in `resources.pipelines.aim-ci.version`. This guarantees no auto-trigger reaches UAT or Prod without an explicit `/release {env}` invocation (story #1806).

**Two CLI gotchas (empirically verified 2026-05-02):**
1. `az pipelines run --pipelines aim-ci=<runId>` does NOT work — the `--pipelines` flag is unrecognized in azure-devops CLI extension v1.0.2. We go through `az devops invoke` against the REST API instead.
2. The REST API's `version` field expects the **buildNumber STRING** (e.g. `"20260502.11"`), NOT the runId integer (`3203`). Passing the runId fails validation with `"Unable to resolve version <runId> for pipeline aim-ci"`.

Resolve the two pipeline definition ids once (single-shot `az`, fine):
```bash
ciId=$(az pipelines list --query "[?name=='{CI_PIPELINE_NAME}'].id" -o tsv)
deployId=$(az pipelines list --query "[?name=='{DEPLOY_PIPELINE_NAME}'].id" -o tsv)
```

**Phase 1 — find & await the develop CI run for this SHA.** The artifact-producing run was created when
the source SHA was merged to `develop` (usually already complete by the time `/release {env}` runs, but
may still be in progress if invoked right after merge). `release/uat` is no longer artifact-producing, so
look up by SHA on `develop`. Use `mcp__azure-devops__pipelines_list_runs` (definition `$ciId`); pick the
newest run whose `sourceBranch` is `refs/heads/develop` and whose source version starts with
`{commit_sha}` (first 8 chars). **Wait** on it with `mcp__azure-devops__pipelines_get_build_status`,
re-scheduling via `ScheduleWakeup` (~150s) until `status: 2` (completed); timeout `{CI_BUILD_TIMEOUT_MIN}`
min. If `result` ≠ `succeeded`, **abort the release** and report. Capture the CI **run id**.

**Phase 2 — resolve the buildNumber STRING** for that run id (the pipeline-resource `version` field
requires the buildNumber, e.g. `20260502.11`, NOT the runId integer — passing the runId fails with
`Unable to resolve version <runId>`). Read it via `mcp__azure-devops__pipelines_get_run` (or single-shot
`az pipelines runs show --id $ciRunId --query buildNumber -o tsv`).

**Phase 3 — trigger Deploy, pinning `aim-ci` to that buildNumber.** This is a one-shot trigger (not a
poll), so the `az devops invoke` plumbing below is fine to run as-is:
```bash
# CLI gotchas (verified 2026-05-02):
#  • `az pipelines run --pipelines aim-ci=<runId>` is broken in azure-devops CLI v1.0.2 — use
#    `az devops invoke` against /pipelines/{id}/runs instead.
#  • version expects the buildNumber STRING, not the runId integer.
#  • Windows-style --in-file path + MSYS_NO_PATHCONV=1 so Git Bash doesn't mangle the leading /.
BODY_PATH="$(cygpath -w /tmp/run-deploy.json 2>/dev/null || echo /tmp/run-deploy.json)"
cat > "$BODY_PATH" <<EOF
{ "resources": { "pipelines": { "aim-ci": { "version": "${ciBuildNumber}" } } } }
EOF
deployRunId=$(MSYS_NO_PATHCONV=1 az devops invoke \
  --org "{ADO_ORG}" --area pipelines --resource runs \
  --route-parameters project="{ADO_PROJECT}" pipelineId="$deployId" \
  --http-method POST --in-file "$BODY_PATH" --api-version 7.1 --query id -o tsv)
echo "Deploy run queued: $deployRunId (pinned aim-ci buildNumber=$ciBuildNumber)"
```

**Phase 4 — handle the authorization-pending case.** Read the new run's status via
`mcp__azure-devops__pipelines_get_run`. If it's `notStarted`, wait one short interval (`ScheduleWakeup`
~30s) and re-check; if still `notStarted` and `{AUTO_AUTHORIZE_NEW_PIPELINES}` is `true`, run the
authorization helper (Step 7: `authorize_pipeline_for_environment $deployId $envName`).

**Phase 5 — await the deploy.** Wait on `$deployRunId` with
`mcp__azure-devops__pipelines_get_build_status`, re-scheduling via `ScheduleWakeup` (~150s) until
completed; timeout `{DEPLOY_TIMEOUT_MIN}` min.

**Phase 6 — sanity-check that it actually deployed.** A deploy run can report `succeeded` with every
stage *Skipped* if change-detection misfires. Read `startTime`/`finishTime` from
`mcp__azure-devops__pipelines_get_run`: a real deploy runs >60s, so an elapsed time **<30s** is a red
flag — warn the user to verify in the ADO UI that deploy stages actually ran (not skipped).

#### Routine: `manual-deploy`

Run Phase 1 (find & await the develop CI run) exactly as in `build-once-promote`, then stop and tell the
user to trigger the deploy manually from the ADO UI.

### Step 7: Pipeline Authorization Helper

When a new pipeline tries to use a protected environment for the first time, ADO requires explicit authorization. This is a one-time-per-(pipeline,env) gate that manifests as a deploy run stuck in `notStarted` state with no error.

If `{AUTO_AUTHORIZE_NEW_PIPELINES}=true` and the polling routine detects this case:

```bash
# Look up environment id by name.
# Use --query (server-side JMESPath) instead of a `| python -c` pipe — the pipe mangles JSON on cp1252.
envId=$(az devops invoke --area distributedtask --resource environments \
  --route-parameters project="{ADO_PROJECT}" --http-method get --api-version 6.0-preview \
  --query "value[?name=='{env_name}'].id | [0]" -o tsv)

# Build the authorization payload
cat > /tmp/authorize-pipe.json <<EOF
{
  "pipelines": [
    {"id": $pipelineId, "authorized": true}
  ]
}
EOF

# PATCH the pipeline-permissions endpoint
az devops invoke \
  --area pipelinepermissions \
  --resource pipelinepermissions \
  --route-parameters project="{ADO_PROJECT}" resourceType=environment resourceId=$envId \
  --http-method patch \
  --in-file /tmp/authorize-pipe.json \
  --api-version 5.1-preview
```

After authorization, return to Phase 5 (await the deploy via MCP + `ScheduleWakeup`) and continue waiting for the deploy to actually start.

### Step 8: Cleanup and Final State

Always run, regardless of success or failure:

1. `git checkout {ORIGINAL_BRANCH}`
2. `git stash pop` if Step 2 stashed (warn user if pop conflicts)
3. Print the final report

## Error Handling

**Output discipline (NON-NEGOTIABLE).** When the skill hits an obstacle (hook block, validation error, in-flight CI run, etc.), the response MUST be: one sentence describing what blocked, one bash block executing the recovery from the table below, then continue. Do NOT theorize, write paragraphs of analysis, or improvise alternative paths. The whole point of the skill is that releasing to UAT/prod is one command with one of two outcomes — succeeded, or a single specific failure with the ADO run URL. Anything else is a skill bug; STOP and surface the failure verbatim to the user rather than improvising around it.

| Failure | Behavior |
|---|---|
| Merge conflicts | STOP, list files, escalate. Never auto-resolve. |
| Push rejected | Pull, retry once, then STOP. |
| CI fails | STOP. Report URL. Do not proceed to deploy or tag. |
| Deploy fails | STOP. Report URL. Do not proceed to tag. |
| Deploy stuck `notStarted` | Wait 30s. If still stuck, attempt authorization (if enabled), else escalate. |
| Tag already exists for same commit | No-op, log "tag already correct". |
| Tag already exists for different commit | STOP, escalate. Manual intervention required. |
| Approval gate timeout | Wait the full `{DEPLOY_TIMEOUT_MIN}`. If still pending, surface to user with the approval URL and continue polling. |
| Stash conflicts on restore | Warn user that they need to `git stash pop` manually. |
| Phase A fails in `release prod` | STOP. Do not run Phase B. The user fixes UAT first, then re-runs `/release prod` (which will skip Phase A if `--skip-uat`, or rerun it from a clean state). |
| `az devops invoke` returns 404 | Verify `--api-version` is `7.1`, the pipeline name resolves to a definition ID (not a run id), and the route parameters quote the project name. |
| Validation error: `Unable to resolve version <N> for pipeline aim-ci` | The `version` field was set to a runId instead of a buildNumber. Re-resolve via `az pipelines runs show --id <runId> --query buildNumber -o tsv`. |
| Deploy run completes in <30 seconds | Suspiciously fast — usually means deploy stages were Skipped. Open the run in the ADO UI and verify actual deploy jobs ran. Pre-removal of UAT/Prod ReadChanges (this story) was the recurring cause. |

## --dry-run mode

When `--dry-run` is set, the skill executes every step EXCEPT:
- `git push`
- `git tag` and `git push --tags`
- `az pipelines run` (manual queues)
- `az devops wiki page create` and `az devops wiki page update` (print rendered content to stdout instead)
- `az boards work-item update`
- Any file write to the release notes directory (print to stdout instead)

The merge step still runs locally so the diff is real, but it's a local-only commit that the user can `git reset --hard origin/{release_branch}` to discard.

## Examples

```bash
# Deploy current feature branch to dev
/release dev

# Deploy current feature branch to dev (preview only, don't actually push)
/release dev --dry-run

# Promote develop to UAT
/release uat

# Promote develop to UAT and watch the full flow without actually shipping
/release uat --dry-run

# Full prod release: develop -> release/uat -> main, tag, notes, work items
/release prod

# Same but bump minor instead of patch (e.g., for a feature release)
/release prod --minor

# Prod release skipping the UAT step (UAT was already deployed separately)
/release prod --skip-uat

# Prod release from a hotfix branch instead of develop
/release prod --source feature/chrisa/1499-prod-hotfix
```
