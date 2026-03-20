# Project Team Conventions

<!--
  TEMPLATE INSTRUCTIONS
  ---------------------
  Copy this file to .claude/project.team.md in your project root and fill in
  every placeholder marked {LIKE_THIS}. Skills read this file for PR creation
  conventions, merge strategy, work item state transitions, story point calibration,
  and AI code review policy.

  This file captures the human agreements your team has made about how code ships.
  Get these right once and the skills will follow them consistently.
-->

## PR Merge Strategy

<!--
  PR_MERGE_STRATEGY: How PRs are merged into the base branch.
  Options: "squash" | "merge" | "rebase"

  Squash: All commits in the PR become one commit on the base branch.
    The source branch is deleted after merge. This is the most common choice
    for ADO projects — it produces a clean linear history.
  Merge: A merge commit is created. Preserves all PR commits in history.
  Rebase: Commits are replayed onto the base branch tip. No merge commit.

  This value is used in the auto-complete API call:
    "completionOptions": { "mergeStrategy": "{PR_MERGE_STRATEGY}" }

  DELETE_SOURCE_BRANCH: Whether the source branch is deleted after merge.
  Options: true | false
  Recommendation: true for squash merges (branch is no longer needed).
-->

- Merge strategy: {PR_MERGE_STRATEGY}
- Delete source branch on merge: {DELETE_SOURCE_BRANCH}
- Base branch for PRs: {BASE_BRANCH}

## Work Item State Machine

<!--
  Document the valid states for User Stories and Bugs, and which state
  means "implementation done but not yet QA-tested". Skills use the
  STORY_DONE_STATE and BUG_DONE_STATE when closing work items.

  STORY_DONE_STATE: The state a User Story is moved to after implementation
  is complete and the PR is created. This is NOT the fully-closed state —
  it signals "ready for QA / demo review".
  Example: "Dev Complete" | "Closed" (if your team skips the QA gate)

  BUG_DONE_STATE: The state a Bug is moved to when the fix is verified.
  Example: "Closed" | "Resolved"

  STORY_STATES_AVAILABLE: Comma-separated list of valid states.
  Example: "New, Active, Dev Complete, In QA, QA Testing, Ready to Demo,
            Awaiting Stage Deploy, Closed, Resolved, Blocked,
            Unapproved / Future, Future Phase, Removed"

  DONE_STATES: States that count as "finished" for completion metrics.
  Example: "Closed, Dev Complete, Ready to Demo, Awaiting Stage Deploy, In QA, Resolved"
-->

- Story done state (after PR): {STORY_DONE_STATE}
- Bug done state: {BUG_DONE_STATE}
- All valid states: {STORY_STATES_AVAILABLE}
- "Done" states (for metrics): {DONE_STATES}

## Story Point Scale

<!--
  POINT_SCALE: The Fibonacci sequence values your team uses.
  Example: "1, 2, 3, 5, 8, 10, 13"
  Note: Most teams cap at 13 and require splitting above that threshold.

  SPLIT_THRESHOLD: The point value at or above which a story should be
  considered for splitting. Skills warn when stories meet or exceed this.
  Example: "13"

  SPLIT_GUIDANCE: How to split — by capability (correct) or by layer (wrong).
  Keep this concise — it is displayed verbatim in the check-story output.
  Example:
    "Split by independently deliverable capability, never by architecture layer.
     A story touching UI + API + DB is healthy — split only when two genuinely
     independent features are bundled together. Stories up to 10 pts are fine
     if cohesive."
-->

- Point scale: {POINT_SCALE}
- Split threshold: {SPLIT_THRESHOLD}
- Split guidance: {SPLIT_GUIDANCE}

## AI Code Review Policy

<!--
  Settings for the automated AI code review that runs on every PR build.
  Skills use these values in the fix-loop logic of start-story / close-story.

  AI_REVIEW_MERGE_GATE: The condition that blocks the PR from merging.
  Example: "Any Critical issues OR more than 5 Major issues"

  AI_REVIEW_FINDINGS_LOG: Path to the file where false positives are logged.
  This file accumulates across PRs for threshold tuning over time.
  Example: ".claude/ai-review-findings.md"

  AI_REVIEW_MAX_FIX_ITERATIONS: How many push cycles the skill attempts before
  giving up and escalating to the user.
  Example: "5"

  AI_REVIEW_FALSE_POSITIVE_POLICY: What to do with false positives.
  Options:
    "log-and-skip"  — log in findings file, do not change code
    "always-fix"    — fix everything the reviewer flags, no exceptions
  Recommendation: "log-and-skip" — prevents wasted effort on reviewer hallucinations.
-->

- Merge gate: {AI_REVIEW_MERGE_GATE}
- Findings log: {AI_REVIEW_FINDINGS_LOG}
- Max fix iterations: {AI_REVIEW_MAX_FIX_ITERATIONS}
- False positive policy: {AI_REVIEW_FALSE_POSITIVE_POLICY}

## PR Description Format

<!--
  Document the required sections in PR descriptions so the skill produces
  descriptions that match your team's review culture.

  PR_DESCRIPTION_REQUIRED_SECTIONS: The ordered list of sections every PR
  description must include.
  Example:
    1. ## Summary — one sentence linking to business value
    2. ## Motivation — why this change was needed (reference Feature/Epic)
    3. ## Implementation Details — bulleted technical changes
    4. ## Acceptance Criteria Verification — table mapping ACs to implementation
    5. ## Testing & Verification — steps to verify the change
    6. ## Related Resources — links to ADO story and parent Feature

  PR_DESCRIPTION_REVIEW_FIXES_SECTION: Name of the section appended after each
  AI review fix iteration.
  Example: "## Review Fixes"
-->

- Required sections: {PR_DESCRIPTION_REQUIRED_SECTIONS}
- Review fixes section heading: {PR_DESCRIPTION_REVIEW_FIXES_SECTION}

## Story Hierarchy

<!--
  Document the expected Epic → Feature → Story hierarchy and the work item
  types used in your ADO project.

  WORK_ITEM_TYPES: The types used in this project (exact spelling from ADO).
  Example: "Epic, Feature, User Story"
  Note: ADO's default is "Product Backlog Item" — custom process templates may
  rename this to "User Story".

  HIERARCHY_REQUIRED: Whether every story must have a parent Feature.
  Options: "required" | "recommended" | "optional"
  Recommendation: "required" — orphan stories have no business justification context.

  EPIC_REQUIRED: Whether every Feature must have a parent Epic.
  Options: "required" | "recommended" | "optional"
  Recommendation: "recommended" — acceptable to omit for infrastructure/tooling work.
-->

- Work item types: {WORK_ITEM_TYPES}
- Story parent Feature: {HIERARCHY_REQUIRED}
- Feature parent Epic: {EPIC_REQUIRED}

## Hooks and Pre-Push Gates

<!--
  List any git hooks or scripts that must run in a specific order before pushing.
  Skills call these in the commit → stamp → push sequence.

  STAMP_REVIEW_HOOK: Path to the script that stamps the review identifier into
  the branch before pushing. Run as a separate command BEFORE git push.
  Example: "bash .claude/hooks/stamp-review.sh"
  Set to "(none)" if no stamp hook is used.

  PRE_PUSH_HOOK: Description of what the pre-push hook validates.
  Example: "Runs dotnet build + dotnet test — push is blocked if either fails."
  Set to "(none)" if no pre-push hook is configured.

  COMMIT_FORMAT: The trailer appended to every commit message for AI attribution.
  Example: "Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
  Set to "(none)" if no trailer convention is used.
-->

- Stamp review hook: {STAMP_REVIEW_HOOK}
- Pre-push hook behavior: {PRE_PUSH_HOOK}
- Commit co-author trailer: {COMMIT_FORMAT}
