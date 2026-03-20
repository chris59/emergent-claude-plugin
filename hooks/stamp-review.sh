#!/bin/bash
# Stamps the current branch diff as "reviewed" so the require-review hook allows push.
# Run this after completing a code review of the current changes.

PROJECT_DIR="$(git rev-parse --show-toplevel 2>/dev/null)"
if [ -z "$PROJECT_DIR" ]; then
  echo "Not in a git repository."
  exit 1
fi

STAMP_DIR="$PROJECT_DIR/.claude/reviews"
mkdir -p "$STAMP_DIR"

BRANCH=$(git branch --show-current 2>/dev/null)
if [ -z "$BRANCH" ]; then
  echo "Not on a branch."
  exit 1
fi

UPSTREAM=$(git rev-parse "@{upstream}" 2>/dev/null)
if [ -z "$UPSTREAM" ]; then
  UPSTREAM=$(git rev-parse origin/develop 2>/dev/null)
fi

if [ -z "$UPSTREAM" ]; then
  echo "Cannot determine upstream."
  exit 1
fi

# ---- Story ID check ----
# All production code changes must be on a branch with a story ID.
# Branch pattern: feature/<user>/<id>-<description> (e.g., feature/chrisa/1031-vuln-check)
# Exempt: release/integration branches (code was reviewed via individual PRs) and .claude/-only changes
case "$BRANCH" in
  main|develop|release/*)
    # Release/integration branches — skip story ID check, code was reviewed via PRs
    ;;
  *)
STORY_ID=$(echo "$BRANCH" | sed -n 's|^feature/[^/]*/\([0-9]*\).*|\1|p' 2>/dev/null || true)
if [ -z "$STORY_ID" ]; then
  # Check if all changes are .claude/-only (exempt from story requirement)
  CHANGED_FILES=$(git diff --name-only "$UPSTREAM"...HEAD 2>/dev/null)
  NON_CLAUDE_FILES=$(echo "$CHANGED_FILES" | grep -v '^\\.claude/' | grep -v '^$' || true)
  if [ -n "$NON_CLAUDE_FILES" ]; then
    echo ""
    echo "ERROR: Branch '$BRANCH' has no story ID in its name."
    echo ""
    echo "All production code changes must be linked to an ADO story."
    echo "Branch name must match: feature/<user>/<storyId>-<description>"
    echo "  Example: feature/chrisa/1031-vulnerable-nuget-check"
    echo ""
    echo "To fix:"
    echo "  1. Create a story: /start-story (which creates the branch for you)"
    echo "  2. Or rename this branch: git branch -m feature/chrisa/<id>-<description>"
    echo ""
    echo "Changed files outside .claude/:"
    echo "$NON_CLAUDE_FILES" | head -10
    exit 1
  fi
fi
    ;;
esac

DIFF_HASH=$(git diff "$UPSTREAM"...HEAD 2>/dev/null | md5sum | cut -d' ' -f1)
STAMP_FILE="$STAMP_DIR/${BRANCH//\//_}_${DIFF_HASH}.reviewed"

echo "Reviewed at $(date -u +%Y-%m-%dT%H:%M:%SZ) by Claude Code" > "$STAMP_FILE"
echo "Review stamp created: $STAMP_FILE"
echo "Push is now allowed for branch '$BRANCH' with current diff."
