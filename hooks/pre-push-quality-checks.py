#!/usr/bin/env python3
"""
Claude Code Hook: Quality gate before git commit and git push.

On git commit:
  - Runs 'dotnet format whitespace {solution}' to auto-fix whitespace/spacing violations
  - Stages any formatting changes via 'git add -u' so they're included in the commit

On git push (non-delete):
  - Runs 'dotnet build {solution} -c Release' — blocks on compile errors
  - Runs 'dotnet test {solution} -c Release --no-build' — blocks on test failures

The solution file is auto-detected: looks for *.slnf first, then *.sln.
"""

import glob
import json
import os
import re
import subprocess
import sys


def find_solution(project_dir):
    """Auto-detect the solution file (prefer .slnf over .sln)."""
    slnf_files = glob.glob(os.path.join(project_dir, "*.slnf"))
    if slnf_files:
        return slnf_files[0]
    sln_files = glob.glob(os.path.join(project_dir, "*.sln"))
    if sln_files:
        return sln_files[0]
    return None


def run(args, cwd, timeout=300):
    """Run a subprocess and return (returncode, stdout, stderr)."""
    result = subprocess.run(
        args,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result.returncode, result.stdout, result.stderr


def block(reason):
    """Block the tool call with a denial message."""
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))
    sys.exit(0)


def main():
    raw = sys.stdin.read()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        sys.exit(0)

    command = (data.get("tool_input") or {}).get("command", "")
    project_dir = data.get("cwd") or os.getcwd()

    solution = find_solution(project_dir)
    if not solution:
        sys.exit(0)  # No .NET solution found, skip

    is_commit = bool(re.search(r'\bgit commit\b', command))
    is_push = bool(re.search(r'\bgit push\b', command)) and not bool(re.search(r'--delete', command))

    if not is_commit and not is_push:
        sys.exit(0)

    # ── On commit: auto-fix whitespace formatting and stage changes ──────────
    if is_commit:
        rc, stdout, stderr = run(
            ["dotnet", "format", "whitespace", solution],
            project_dir,
            timeout=120,
        )
        if rc != 0:
            block(
                f"dotnet format whitespace failed (exit {rc}). Fix formatting errors before committing.\n"
                f"{stderr[-1500:]}"
            )

        # Stage any files that were auto-formatted
        run(["git", "-C", project_dir, "add", "-u"], project_dir)

        # Report what was auto-fixed (non-blocking — commit proceeds)
        formatted_files = [
            line for line in stdout.splitlines()
            if "Formatted code file" in line or "Formatted " in line
        ]
        if formatted_files:
            print(
                f"[pre-commit] Auto-fixed formatting in {len(formatted_files)} file(s) and staged:\n"
                + "\n".join(f"  {f}" for f in formatted_files),
                file=sys.stderr,
            )

        sys.exit(0)

    # ── On push: build + test ─────────────────────────────────────────────────
    if is_push:
        sln_name = os.path.basename(solution)

        print(f"[pre-push] Building {sln_name} (Release)...", file=sys.stderr)
        rc, stdout, stderr = run(
            ["dotnet", "build", solution, "-c", "Release"],
            project_dir,
            timeout=180,
        )
        if rc != 0:
            errors = [l for l in (stdout + stderr).splitlines() if ": error " in l]
            block(
                "Build failed — fix compile errors before pushing:\n\n"
                + "\n".join(errors[:20])
                + ("\n..." if len(errors) > 20 else "")
            )

        print(f"[pre-push] Running tests (Release)...", file=sys.stderr)
        rc, stdout, stderr = run(
            ["dotnet", "test", solution, "-c", "Release", "--no-build"],
            project_dir,
            timeout=300,
        )
        if rc != 0:
            failed = [l for l in stdout.splitlines() if "Failed" in l and "::" in l]
            summary = [l for l in stdout.splitlines() if "Failed:" in l and "Passed:" in l]
            block(
                "Tests failed — fix failing tests before pushing:\n\n"
                + "\n".join(summary[:5])
                + ("\n\nFailing tests:\n" + "\n".join(failed[:20]) if failed else "")
                + f"\n\nFull output (last 2000 chars):\n{stdout[-2000:]}"
            )

        print("[pre-push] Build and tests passed.", file=sys.stderr)
        sys.exit(0)


if __name__ == "__main__":
    main()
