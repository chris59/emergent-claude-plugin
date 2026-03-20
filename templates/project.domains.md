# Project Domains

<!--
  TEMPLATE INSTRUCTIONS
  ---------------------
  Copy this file to .claude/project.domains.md in your project root and fill in
  every placeholder marked {LIKE_THIS}. This file teaches skills the project-specific
  domain rules, safety constraints, and business logic that cannot be inferred from
  the codebase alone.

  This is the most important file for preventing costly mistakes. Use it to document:
    - Tables or data stores that must never be modified directly
    - Pipeline stages or processes with invariants that must be preserved
    - Business rules that look wrong but are intentional
    - Data ownership boundaries (who is allowed to write what)

  These rules are loaded before any planning or implementation begins. Be specific —
  vague rules ("be careful with the database") are ignored. Concrete rules ("never
  INSERT into alloc.RunOptions — use InitializeRunOptions only") are enforced.
-->

## Critical Safety Rules

<!--
  List rules that, if violated, cause data corruption, non-reproducible results,
  or production incidents. Number them so they can be referenced by ID.

  Format each rule as:
    ### Rule N: {Short title}
    {One paragraph explaining what must not happen, why, and what to do instead.}

  Example rules from a data pipeline project:
    ### Rule 1: Never directly modify user-configured option tables
    The RunOptions and GlobalOptions tables store values set through the Admin UI.
    Do NOT run INSERT/UPDATE/DELETE against them unless explicitly instructed with
    specific values. If values look wrong, ask the user — they may be intentional.

    ### Rule 2: Landing tables are the immutable input record per run
    Landing tables are populated once at run creation and never modified during
    pipeline execution. Never truncate them — they accumulate history across all
    runs. Only delete rows when a run is explicitly deleted by the user.
-->

{SAFETY_RULES}

## Domain Model

<!--
  Describe the core domain concepts, their relationships, and their invariants.
  Skills use this during planning to understand what entities exist and how they
  relate, without having to read the entire database schema.

  Example:
    ### AllocationRun
    The central aggregate. Represents one execution of the allocation pipeline for
    a given month and product set. Has many RunOptions (one per material) and one
    set of GlobalOptions.

    States: New → Active → Complete → Published
    Invariant: A Published run's output is immutable — no adjustments allowed.

    ### RunOptions
    Per-material configuration for one AllocationRun. User-owned — written only
    through the Admin UI or InitializeRunOptions. The pipeline reads but never
    writes these values (except during initial seeding).
-->

{DOMAIN_MODEL}

## Critical Tables / Data Stores

<!--
  List the tables, collections, or data stores that require special care.
  For each, state: what it contains, who is allowed to write it, and what
  operations are forbidden.

  Example:
    | Table | Owner | Forbidden Operations |
    |-------|-------|---------------------|
    | alloc.RunOptions | Admin UI / InitializeRunOptions | Direct INSERT/UPDATE from pipeline |
    | landing.* | Ingest process (one-time) | Truncate, re-seed during pipeline runs |
    | data.* | ops.MergeToData only | Direct INSERT, system versioning disabled |
-->

{CRITICAL_TABLES}

## Business Rules

<!--
  Document non-obvious business rules that look like bugs but are intentional.
  These are rules the implementer must preserve when touching related code.

  Example:
    - Retail sales date range is inclusive on both ends. Do NOT change <= to <.
    - Dealer ranking uses DENSE_RANK, not ROW_NUMBER. Ties must share the same rank.
    - Aged inventory penalty applies to units > 180 days old, counted from arrival date
      (not sold date). The header says "Days In Inv Penalty" but the lookup key is
      "AgedInv Days" — this is intentional, not a copy-paste error.
    - The allocation pipeline must never run concurrently for different runs.
      SQL Server deadlocks occur. Always run sequentially.
-->

{BUSINESS_RULES}

## Pipeline / Process Constraints

<!--
  If the project has a multi-step pipeline, data processing workflow, or job
  scheduler, document its constraints here.

  Example:
    ### Allocation Pipeline
    Stages run in strict sequence: BuildOptionTable → BuildAllocationRunOptions →
    AgedInventory → StrictAge → Forecast → ... → Distribute → BuildPass1Output

    Invariants:
    - Stage N must complete before stage N+1 starts (no parallel execution)
    - Each stage proc must be idempotent — re-running stage 3 must produce the
      same result as running it for the first time
    - The pipeline reads alloc.RunOptions at the start of execution and again
      after stage 5 (BuildAllocationRunOptions may have back-filled NULLs)
    - Never call InitializeRunOptions or SeedLandingFromData from pipeline stages

    ### Regression Testing Requirement
    Any change to a pipeline stage proc must be regression-tested before merging:
      dotnet run -- --runs 71 --run-pipeline --baseline   # save baseline
      # deploy changes
      dotnet run -- --runs 71 --run-pipeline --compare    # verify no regression
    A stage dropping > 0.5% match rate is a regression that must be reverted.
-->

{PIPELINE_CONSTRAINTS}

## External Integrations

<!--
  List external systems the project integrates with and any integration-specific
  safety rules.

  Example:
    ### SAP Flat File Integration
    SAP produces .dat files via SFTP nightly. Files follow the naming convention
    YYYYMMDD-HHMMSS_{DATASET}.dat. The loader processes them in chronological order.
    Never process a file that has already been successfully ingested (check by hash).

    ### Azure Service Bus
    Outbox processor publishes events to Service Bus. The processor is idempotent —
    it can safely re-run if interrupted. Do NOT disable the outbox table or bypass
    the processor by publishing events directly.
-->

{EXTERNAL_INTEGRATIONS}
