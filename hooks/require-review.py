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

    def is_exempt(b: str) -> bool:
        return b in EXEMPT_BRANCHES or b.startswith("release/")

    # Check the PUSH TARGET REF first, not just the current branch.
    # Pattern matches: `git push origin release/uat`, `git push origin HEAD:release/uat`,
    # `git push origin develop:release/uat`. The destination ref is what gets the
    # commits — that's what the exemption should key off of.
    # /release uat ff-pushes release/uat from whatever branch is checked out
    # (could be a deleted feature branch with stale local HEAD), so the
    # current-branch check below is the wrong gate for that case.
    target_match = re.search(
        r'git push(?:\s+--?\S+)*\s+\S+\s+(?:[^:\s]+:)?(\S+)',
        command,
    )
    if target_match:
        target_ref = target_match.group(1)
        # Strip refs/heads/ prefix if present
        target_ref = re.sub(r'^refs/heads/', '', target_ref)
        if is_exempt(target_ref):
            sys.exit(0)

    if is_exempt(branch):
        sys.exit(0)

    # Diff base = merge-base with origin/develop, NOT @{upstream}. After a rebase, @{upstream}
    # still points at the pre-rebase remote tip, so its diff (and thus the diff-hash) won't match
    # the stamp that stamp-review.sh wrote against the merge-base. Keep both scripts on the same
    # base so a stamp made post-rebase actually satisfies this gate. Fall back to @{upstream}.
    upstream = None
    try:
        upstream = subprocess.check_output(
            ["git", "-C", project_dir, "merge-base", "HEAD", "origin/develop"],
            text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        pass

    if not upstream:
        try:
            upstream = subprocess.check_output(
                ["git", "-C", project_dir, "rev-parse", "@{upstream}"],
                text=True, stderr=subprocess.DEVNULL
            ).strip()
        except Exception:
            sys.exit(0)  # Can't determine diff base, allow

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
