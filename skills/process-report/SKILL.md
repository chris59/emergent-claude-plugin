---
name: process-report
description: Summarize the emergent-dev process metrics (.claude/process-metrics.jsonl) — plan-revision rate, which gates catch real issues, AC-warning→rework correlation, avg AI-review iterations. Use to decide which lifecycle gates earn their cost.
user-invocable: true
argument-hint: "[--last N]"
---

# Process Report

Read the append-only telemetry the lifecycle skills emit (`start-story`, `close-story`) and summarize
whether the process gates are pulling their weight. Pure read + arithmetic — no agents, no ADO calls.

The point is to answer: *are the gates we pay for (readiness assessment, AC-quality warnings, scope-creep
detection, local-approval gate, AI review) actually catching problems, or just adding ceremony?*

## Arguments

- `--last N` — only consider the most recent N stories (default: all).

## Instructions

### Step 1: Load metrics

Read `.claude/process-metrics.jsonl`. Each line is one JSON object with an `event` of `start` or `close`,
keyed by `storyId`. If the file is missing or empty, tell the user no metrics have been collected yet
(they accrue as stories go through `/start-story` and `/close-story`) and stop.

Pair `start` and `close` records by `storyId`. A story may have a `start` with no `close` yet (in
flight) — count it as in-progress, don't include it in the rework stats.

### Step 2: Compute

Across the paired records (respect `--last N`):

- **Throughput**: stories started, closed, in-progress; points closed.
- **Plan / approval health**:
  - `reworkAfterApproval` rate — % of closed stories where the user found issues *after* first approving
    at the local gate (high = the gate is rubber-stamping).
  - avg `aiReviewIterations` — how many fix-push cycles the AI review forced (high = local review is
    missing things the AI catches).
- **Gate signal — does each gate predict rework?** For the AC-quality gate especially: compare
  `reworkAfterApproval` / `aiReviewIterations` for stories that started with `acWarnings > 0` vs
  `acWarnings == 0`. If warned stories don't rework more, the warning isn't earning its cost.
- **Scope creep**: avg `scopeCreepFiles` and how often it's nonzero.
- **Readiness**: how often `hierarchyOk == false` or `depsBlocking > 0` at start, and whether those
  stories closed cleaner or messier.

### Step 3: Report

Print a compact summary, then ONE actionable takeaway per gate (keep, tune, or drop):

```
Process Report — last {N} stories ({closed} closed, {inProgress} in flight)

  Throughput        {closed} stories / {points} pts
  Rework-after-approval  {x}%  ({n}/{closed})
  Avg AI-review iters    {x.x}
  Scope-creep stories    {x}%  (avg {x.x} files)

  Gate signal:
    AC-quality warning  → reworked {a}% (warned) vs {b}% (clean)   [{KEEP|TUNE|DROP}]
    Readiness hierarchy → {observation}
    Local-approval gate → {observation}

  Takeaway: {1-2 sentences — which gate to keep/tune/drop and why}
```

Be honest when the sample is too small to conclude (< ~8 closed stories) — say the signal isn't
significant yet rather than over-reading noise.

## Notes

- Read-only. Never edits the JSONL.
- `.claude/process-metrics.jsonl` is local, gitignored telemetry — it won't exist in a fresh clone.
- Timestamps are written by the emitting skills (`date -u`), not inferred here.
