# Project CI/CD Configuration

<!--
  TEMPLATE INSTRUCTIONS
  ---------------------
  Copy this file to .claude/project.cicd.md in your project root and fill in
  every placeholder marked {LIKE_THIS}. The /release skill reads this file to
  know which ADO pipelines to monitor for each environment, which release
  branch each environment maps to, and whether to expect a two-stage
  build-then-deploy flow.

  This file lets the /release skill stay generic across projects with very
  different CI/CD topologies — single-pipeline-per-env, build-once/deploy-many,
  monorepo with per-component pipelines, etc.
-->

## CI/CD Topology

<!--
  TOPOLOGY: Which CI/CD shape this project uses.
  Options:
    "single-per-env"   — one pipeline per environment that builds + deploys
                         in the same run. Push to develop triggers a pipeline
                         that builds AND deploys to dev. Push to release/uat
                         triggers a separate pipeline that builds AND deploys
                         to UAT. Same for prod. Each environment is independent.
                         The /release skill monitors a single pipeline per env.
    "build-once-promote" — one CI pipeline builds artifacts on every protected
                         branch. Thin deploy pipelines consume those artifacts
                         via ADO pipeline resource triggers. Push to release/uat
                         runs CI first, then the deploy pipeline auto-fires.
                         The /release skill watches CI first, then switches to
                         watching the deploy pipeline.
    "manual-deploy"    — CI builds on every push, but deploys are triggered
                         manually from the ADO UI. The /release skill stops
                         after CI succeeds and tells the user to trigger the
                         deploy themselves.
-->

- Topology: {TOPOLOGY}

## Environment Configuration

<!--
  For each environment, document:
  - The release branch (which branch you push to in order to deploy)
  - The source branch you typically merge from
  - The CI pipeline name (the build pipeline triggered by the push)
  - The deploy pipeline name (only if topology is "build-once-promote";
    leave blank for "single-per-env" because the CI pipeline IS the deploy)
  - Whether the deploy requires manual approval

  Names must match the exact display name configured in ADO Pipelines.
-->

### dev

- Release branch: {DEV_RELEASE_BRANCH}
- Default source: {DEV_SOURCE_DEFAULT}
- CI pipeline name: {DEV_CI_PIPELINE_NAME}
- Deploy pipeline name: {DEV_DEPLOY_PIPELINE_NAME}
- Requires approval: {DEV_REQUIRES_APPROVAL}

### uat

- Release branch: {UAT_RELEASE_BRANCH}
- Default source: {UAT_SOURCE_DEFAULT}
- CI pipeline name: {UAT_CI_PIPELINE_NAME}
- Deploy pipeline name: {UAT_DEPLOY_PIPELINE_NAME}
- Requires approval: {UAT_REQUIRES_APPROVAL}

### prod

- Release branch: {PROD_RELEASE_BRANCH}
- Default source: {PROD_SOURCE_DEFAULT}
- CI pipeline name: {PROD_CI_PIPELINE_NAME}
- Deploy pipeline name: {PROD_DEPLOY_PIPELINE_NAME}
- Requires approval: {PROD_REQUIRES_APPROVAL}

## Polling Configuration

<!--
  CI_BUILD_TIMEOUT_MIN: How long to wait for the CI build to complete before
  giving up and reporting "still running" to the user.
  Recommended: 30 (most builds finish well under this)

  DEPLOY_TIMEOUT_MIN: How long to wait for the deploy pipeline to complete.
  Recommended: 60 (deploys can include slot swaps, dacpac apply, etc.)

  TRIGGER_REGISTRATION_DELAY_SEC: How long to wait after pushing before the
  first poll, to give ADO time to register the new run.
  Recommended: 10
-->

- CI build timeout (minutes): {CI_BUILD_TIMEOUT_MIN}
- Deploy timeout (minutes): {DEPLOY_TIMEOUT_MIN}
- Trigger registration delay (seconds): {TRIGGER_REGISTRATION_DELAY_SEC}

## Release Tagging

<!--
  Configuration for the prod release tagging step. The /release prod skill
  computes the next version, creates an annotated git tag on the merged
  prod commit, and pushes it to origin.

  TAG_FORMAT: The version scheme. Currently only "semver" is supported.
  Options: "semver"

  TAG_PREFIX: String prepended to every version (e.g., "v" for "v1.0.0",
  "release-" for "release-1.0.0", "" for "1.0.0").
  Recommendation: "v"

  DEFAULT_BUMP: Which semver component to increment by default when no
  flag is passed. Override per-release with --major or --minor.
  Options: "patch" | "minor" | "major"
  Recommendation: "patch" (most releases are bug fixes)

  INITIAL_VERSION: The version assigned when no prior tag exists.
  Used only on the first /release prod call. Format: bare semver, no prefix.
  Recommendation: "1.0.0"

  TAG_ANNOTATED: Whether tags include annotation metadata (release notes
  embedded in the tag message). Always true for production tags.
  Options: "true" | "false"
-->

- Tag format: {TAG_FORMAT}
- Tag prefix: {TAG_PREFIX}
- Default version bump: {DEFAULT_BUMP}
- Initial version: {INITIAL_VERSION}
- Tag annotated: {TAG_ANNOTATED}

## Release Notes

<!--
  Configuration for the auto-generated release notes that ship with each
  prod release. The /release prod skill collects commits since the previous
  prod tag, parses linked work item IDs, and produces a markdown file plus
  the annotated tag message.

  RELEASE_NOTES_DIR: Where {tag}.md files are written. Path is relative
  to the repo root.
  Example: "docs/releases"

  WORK_ITEM_ID_PATTERN: Regex (Python flavor) capturing a work item ID
  from a commit subject line. Used to group commits by linked story.
  Example for "#1452": "#(\\d+)"
  Set to "" to disable story grouping (commits go to "Other").

  ENRICH_WITH_ADO_TITLES: Whether to call az boards to fetch story titles
  for each work item ID. Adds API calls but produces richer notes.
  Options: "true" | "false"

  INCLUDE_FILE_DIFF_STAT: Include the file change count and PR diff stat
  in release notes (e.g., "186 files changed, 12,345+, 6,789-").
  Options: "true" | "false"

  INCLUDE_SCHEMA_CHANGES_SECTION: Auto-detect database schema changes
  (any .sqlproj or .sql files in src/.../Database/) and call them out
  in a dedicated section.
  Options: "true" | "false"

  INCLUDE_BUILD_ARTIFACT_INFO: Include the CI build number and ADO run
  URL for traceability.
  Options: "true" | "false"

  POST_TO_WORK_ITEMS: For each story shipped, post a comment to the
  ADO work item: "Shipped in {tag} on {date}". Posts via az boards
  work-item update --discussion.
  Options: "true" | "false"
-->

- Release notes directory: {RELEASE_NOTES_DIR}
- Work item ID pattern: {WORK_ITEM_ID_PATTERN}
- Enrich with ADO titles: {ENRICH_WITH_ADO_TITLES}
- Include file diff stat: {INCLUDE_FILE_DIFF_STAT}
- Include schema changes section: {INCLUDE_SCHEMA_CHANGES_SECTION}
- Include build artifact info: {INCLUDE_BUILD_ARTIFACT_INFO}
- Post to work items: {POST_TO_WORK_ITEMS}

## Production Confirmation

<!--
  Safety gates for /release prod. The skill stops and asks for explicit
  confirmation before any prod-affecting action.

  REQUIRE_PROD_CONFIRMATION: Show a confirmation prompt before advancing
  main / triggering prod. Set to false if /release prod is itself the
  intentional act (no extra prompt needed).
  Options: "true" | "false"

  SHOW_COMMIT_LIST_BEFORE_PROD: Display the list of commits that will
  ship before asking for confirmation.
  Options: "true" | "false"

  SHOW_FILE_COUNT_BEFORE_PROD: Display the count of files changed before
  asking for confirmation.
  Options: "true" | "false"

  PROD_INVOKE_VIA_AZ_PIPELINES_RUN: Controls how /release prod invokes
  Deploy Prod.
  - "true" (recommended for build-once-promote): Deploy Prod has NO
    automatic trigger anywhere. /release prod Phase A pushes to
    release/uat and watches CI + Deploy UAT, capturing the upstream
    aim-ci buildNumber. Phase B invokes Deploy Prod via `az devops
    invoke` POST to /pipelines/{id}/runs with
    resources.pipelines.aim-ci.version=<buildNumber> (pinning the same
    artifact UAT validated, bit-for-bit identical), watches it, then
    ff-pushes release/uat -> main as audit-trail. Critical:
    /release uat cannot reach Deploy Prod under this model. Note: the
    flag name is historical — we no longer use `az pipelines run
    --pipelines`, which is unrecognized in azure-devops CLI v1.0.2.
  - "false" (legacy main-trigger): Deploy Prod fires off CI on main.
    Phase A watches CI + Deploy UAT only. Phase B merges release/uat ->
    main, pushes, watches CI on main, watches Deploy Prod.
  Default if absent: "false".
  Options: "true" | "false"
-->

- Require prod confirmation: {REQUIRE_PROD_CONFIRMATION}
- Show commit list before prod: {SHOW_COMMIT_LIST_BEFORE_PROD}
- Show file count before prod: {SHOW_FILE_COUNT_BEFORE_PROD}
- Prod invoke via az pipelines run: {PROD_INVOKE_VIA_AZ_PIPELINES_RUN}

## Pipeline Authorization

<!--
  When a new ADO pipeline is created and tries to use a protected environment
  for the first time, ADO blocks it pending explicit authorization. The
  skill can detect this case and authorize the pipeline automatically.

  AUTO_AUTHORIZE_NEW_PIPELINES: If a deploy run is stuck in notStarted
  state and the cause is unauthorized environment access, automatically
  PATCH the pipeline-permissions endpoint to authorize and re-poll.
  Options: "true" | "false"
  Recommendation: "true" — saves a lot of friction during initial pipeline
  setup. Only happens once per (pipeline, environment) pair.
-->

- Auto-authorize new pipelines on environments: {AUTO_AUTHORIZE_NEW_PIPELINES}

## Wiki Publishing

<!--
  After a successful prod release, /release prod can publish the release
  notes to the ADO project wiki as a subpage. The pattern: a parent index
  page lists all releases (one row per version), and each version has its
  own subpage with the full details.

  WIKI_PUBLISH_ENABLED: Whether to publish to the project wiki at all.
  Set false if your team doesn't use the ADO project wiki for release tracking.
  Options: "true" | "false"

  WIKI_NAME: The exact name of the ADO project wiki (the value az devops
  wiki list returns under .name). Usually "{ProjectName}.wiki" for the
  default project wiki.
  Example: "Honda-AIM.wiki"

  WIKI_RELEASE_PARENT_PATH: The path of the parent index page in the wiki.
  Subpages will be created at "{WIKI_RELEASE_PARENT_PATH}/{tag}".
  Example: "/Release Notes"
  Set to "" to skip — release notes will not be published to the wiki.

  WIKI_INDEX_TABLE_HEADER: The exact line that starts the index table on
  the parent page. The skill will append a new row immediately after the
  header row + separator. Must match the existing table header on the
  parent page.
  Example: "| Version | Released | Headline |"

  WIKI_INDEX_ROW_FORMAT: How to render the row added to the index table
  for each new release. Variables: {TAG}, {DATE}, {HEADLINE}.
  Use the ADO absolute-URL link form instead of [[Page Name]] syntax —
  bracket links only resolve at the wiki root, which silently breaks for
  nested pages. The skill substitutes {ADO_PROJECT_ENCODED} and {WIKI_NAME}
  from project.env.md and the wiki section above.
  Example: "| [{TAG}](/{ADO_PROJECT_ENCODED}/_wiki/wikis/{WIKI_NAME}?pagePath=%2FRelease%20Notes%2F{TAG}) | {DATE} | {HEADLINE} |"
-->

- Wiki publish enabled: {WIKI_PUBLISH_ENABLED}
- Wiki name: {WIKI_NAME}
- Wiki release parent path: {WIKI_RELEASE_PARENT_PATH}
- Wiki index table header: {WIKI_INDEX_TABLE_HEADER}
- Wiki index row format: {WIKI_INDEX_ROW_FORMAT}

## Examples

<!--
  Example 1 — single-per-env (legacy three-pipeline model):
  ```
  Topology: single-per-env

  dev:
    Release branch: develop
    Default source: (current branch)
    CI pipeline name: MyApp Dev
    Deploy pipeline name:
    Requires approval: false

  uat:
    Release branch: release/uat
    Default source: develop
    CI pipeline name: MyApp UAT
    Deploy pipeline name:
    Requires approval: false

  prod:
    Release branch: main
    Default source: release/uat
    CI pipeline name: MyApp Prod
    Deploy pipeline name:
    Requires approval: true
  ```

  Example 2 — build-once-promote (Honda AIM as of story #1452):
  ```
  Topology: build-once-promote

  dev:
    Release branch: develop
    Default source: (current branch)
    CI pipeline name: Honda AIM CI
    Deploy pipeline name:           # build + deploy happen in same CI run
    Requires approval: false

  uat:
    Release branch: release/uat
    Default source: develop
    CI pipeline name: Honda AIM CI
    Deploy pipeline name: Honda AIM Deploy UAT
    Requires approval: false

  prod:
    Release branch: main
    Default source: release/uat
    CI pipeline name: Honda AIM CI
    Deploy pipeline name: Honda AIM Deploy Prod
    Requires approval: true
  ```
-->
