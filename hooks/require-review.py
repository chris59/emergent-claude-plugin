#!/usr/bin/env python3
"""
Claude Code Hook: Require code review before git push / PR creation.

Reads tool input from stdin (JSON). If the Bash command is a git push
or az repos pr create, checks for a review stamp file that matches
the current diff hash. If no stamp exists, blocks the action and
instructs Claude to run a review first.

The stamp is created by: bash .claude/hooks/stamp-review.sh
"""

import json
import hashlib
import os
import subprocess
import sys
import re


def main():
    raw = sys.stdin.read()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        sys.exit(0)  # Can't parse, allow

    command = (data.get("tool_input") or {}).get("command", "")

    # Only gate git push (not --delete). PR creation doesn't need a separate gate
    # because the push itself is already gated — code is reviewed before it reaches remote.
    if re.search(r'git push.*--delete', command):
        sys.exit(0)  # Branch deletion, no review needed
    if not re.search(r'git push', command):
        sys.exit(0)

    project_dir = data.get("cwd") or os.getcwd()
    stamp_dir = os.path.join(project_dir, ".claude", "reviews")

    # Get current branch
    try:
        branch = subprocess.check_output(
            ["git", "-C", project_dir, "branch", "--show-current"],
            text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        sys.exit(0)  # Not in git, allow

    if not branch:
        sys.exit(0)

    # Release/integration branches don't need a story-level review stamp —
    # all code merged into them was already reviewed via individual PRs.
    EXEMPT_BRANCHES = {"main", "develop", "release/uat", "release/2026-02-10"}
    if branch in EXEMPT_BRANCHES or branch.startswith("release/"):
        sys.exit(0)

    # Get upstream ref to diff against
    upstream = None
    try:
        upstream = subprocess.check_output(
            ["git", "-C", project_dir, "rev-parse", "@{upstream}"],
            text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        pass

    if not upstream:
        try:
            upstream = subprocess.check_output(
                ["git", "-C", project_dir, "rev-parse", "origin/develop"],
                text=True, stderr=subprocess.DEVNULL
            ).strip()
        except Exception:
            sys.exit(0)  # Can't determine upstream, allow

    # Compute diff hash (use raw bytes to match md5sum in stamp-review.sh)
    try:
        diff_bytes = subprocess.check_output(
            ["git", "-C", project_dir, "diff", f"{upstream}...HEAD"],
            stderr=subprocess.DEVNULL
        )
        diff_hash = hashlib.md5(diff_bytes).hexdigest()
    except Exception:
        sys.exit(0)  # Can't compute diff, allow

    # Check for stamp file
    safe_branch = branch.replace("/", "_")
    stamp_file = os.path.join(stamp_dir, f"{safe_branch}_{diff_hash}.reviewed")

    if os.path.exists(stamp_file):
        sys.exit(0)  # Review exists, allow push

    # No review stamp — block the push
    result = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                f"Code review required before push. Review the diff for branch '{branch}' "
                f"against project review criteria (security, architecture, correctness, "
                f"code quality). After reviewing, run: "
                f"bash .claude/hooks/stamp-review.sh to mark as reviewed, then retry the push."
            )
        }
    }
    print(json.dumps(result))
    sys.exit(0)


if __name__ == "__main__":
    main()
