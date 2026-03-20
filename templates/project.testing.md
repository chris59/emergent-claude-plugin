# Project Testing

<!--
  TEMPLATE INSTRUCTIONS
  ---------------------
  Copy this file to .claude/project.testing.md in your project root and fill in
  every placeholder marked {LIKE_THIS}. Skills read this file to understand what
  test suites exist, how to run them, and what additional verification steps are
  required before pushing code.

  This file also documents mandatory pre-push checks that go beyond a standard
  `dotnet test` — for example, SCSS compilation, database schema build validation,
  regression runners, or linting steps. Every check listed here is enforced by
  the close-story skill's Step 4.
-->

## Test Suite

<!--
  TEST_PROJECT_PATTERN: Glob or path pattern used to discover test projects.
  Example: "**/*.Tests.csproj" | "tests/" | "src/**/*Tests/"

  TEST_FRAMEWORK: The testing framework in use.
  Example: "xUnit" | "NUnit" | "Jest" | "pytest"

  TEST_RUNNER_COMMAND: The full command to run all tests.
  This is what skills run after building. Must exit non-zero on failure.
  Example: "dotnet test {SOLUTION_FILE} -c Release --no-build"
           "npm test -- --ci"
           "pytest tests/ -x"

  TEST_COUNT_APPROX: Approximate number of tests in the suite (for context).
  Example: "~450" | "unknown"
-->

- Test project pattern: {TEST_PROJECT_PATTERN}
- Framework: {TEST_FRAMEWORK}
- Run command: {TEST_RUNNER_COMMAND}
- Approximate test count: {TEST_COUNT_APPROX}

## Test Categories

<!--
  List the types of tests in the project and where they live.
  Skills use this to know what to search for when checking test coverage.

  Example:
    | Category | Location | What They Cover |
    |----------|----------|----------------|
    | Unit | src/*.Tests/ | Domain logic, handlers, validators |
    | Integration | src/*.IntegrationTests/ | EF Core queries, API endpoints |
    | Architecture | src/*.Tests/Architecture/ | Layer dependency rules (NetArchTest) |
-->

{TEST_CATEGORIES}

## Pre-Push Verification Checklist

<!--
  List every check that must pass before code is pushed to remote.
  These are the steps the close-story skill runs in Step 4 (Format, Build, Test).
  Checks run in the order listed — include the exact command for each.

  Mark each as:
    [always]  — run on every PR regardless of what changed
    [if-scss] — run only if .scss files were modified
    [if-sql]  — run only if .sql files were modified
    [if-X]    — run only under the specified condition

  Example:
    1. [always]  Format: dotnet format whitespace {SOLUTION_FILE}
    2. [always]  Build: dotnet build {SOLUTION_FILE} -c Release
    3. [always]  Test: dotnet test {SOLUTION_FILE} -c Release --no-build
    4. [if-scss] SCSS: cd src/MyProject.Web.Shared && sass css/main.scss wwwroot/main.min.css --style=compressed --no-source-map
    5. [if-sql]  DB build: powershell -ExecutionPolicy Bypass -File tools/scripts/database/build-database.ps1
-->

{PRE_PUSH_CHECKLIST}

## Regression Tools

<!--
  If the project has a regression runner or comparison tool, document it here.
  Skills load this during planning for any story that touches the relevant subsystem.

  REGRESSION_RUNNER_PATH: Relative path to the regression runner tool.
  Example: "tools/MyProject.Tools.RegressionRunner/"

  REGRESSION_BASELINE_COMMAND: Command to save a baseline before making changes.
  REGRESSION_COMPARE_COMMAND: Command to compare after making changes.
  REGRESSION_THRESHOLD: What constitutes a regression (for context in planning).
  Example: "Any stage dropping > 0.5% match rate is a regression."

  Set all fields to "(none)" if no regression runner exists.
-->

- Runner path: {REGRESSION_RUNNER_PATH}
- Save baseline: {REGRESSION_BASELINE_COMMAND}
- Compare: {REGRESSION_COMPARE_COMMAND}
- Regression threshold: {REGRESSION_THRESHOLD}

## Database Build Validation

<!--
  If the project has an SSDT (.sqlproj) or other compiled database project,
  document how to validate the schema compiles correctly before pushing.

  DB_BUILD_SCRIPT: The script or command that builds the dacpac / schema artifact.
  DB_BUILD_WARNINGS_OK: List of expected warnings that are safe to ignore.
  DB_BUILD_ERRORS_BLOCK: Confirm that errors (not warnings) block the PR.

  Set to "(none)" if no database build step exists.

  Example:
    - Build script: powershell -ExecutionPolicy Bypass -File tools/scripts/database/build-database.ps1
    - Safe to ignore: SQL71502 warnings about unresolved references to dynamic landing tables
    - Errors block push: yes — any error means the dacpac will fail to deploy
-->

- Build script: {DB_BUILD_SCRIPT}
- Safe warnings: {DB_BUILD_WARNINGS_OK}
- Errors block push: {DB_BUILD_ERRORS_BLOCK}

## Test Gap Stories

<!--
  Stories tagged "test-gap" follow a different close workflow — the tests
  themselves ARE the verification and no manual user approval is needed after
  they pass. Document the tag name used by this project.

  TEST_GAP_TAG: The ADO tag that identifies test-coverage stories.
  Example: "test-gap"
  Set to "(none)" if the project does not use this pattern.
-->

- Test gap tag: {TEST_GAP_TAG}

## Infrastructure / CI-Verified Stories

<!--
  Some stories (CI pipeline changes, build config, analyzer rules) are verified
  by the CI pipeline itself rather than manual user testing. Document the
  indicators that identify these stories so close-story can auto-close them.

  INFRA_STORY_INDICATORS: List of signals that mark a story as infra-only.
  Example:
    - Changed files under .azure-pipelines/, tools/, or .claude/
    - Changed files: Directory.Build.props, .editorconfig, *.props, *.targets
    - Tagged "enterprise-practices"
    - Title contains "CI", "pipeline", "analyzer", "build", "formatting"
-->

- Infra story indicators: {INFRA_STORY_INDICATORS}
