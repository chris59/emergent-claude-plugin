---
name: estimate
description: Generate professional effort estimates from requirements — work breakdown, phase-level costing, agentic development adjustments, and deliverable output. Use after requirements-analysis.
user-invocable: true
argument-hint: "<requirements path or topic>"
---

# Estimate

Professional effort estimation tool. Accepts a requirements document (from `/requirements-analysis`) or a plain description, and produces a structured, client-presentable estimate with phase-level breakdown, agentic development adjustments, PERT-based confidence ranges, and risk-adjusted totals.

The goal is to give every number a defensible explanation. A client or executive should be able to challenge any line item and receive a clear answer grounded in cost drivers — not gut feel or story points pulled from the air.

## Arguments

- Path to a requirements document (`.claude/requirements/{slug}/requirements.md`), a feature slug, or a plain description of what needs to be estimated (optional — will ask interactively if not provided)

## Instructions

Follow these steps in order. This skill is **interactive** — pause and wait for user input where indicated.

### Step 0: Load Project Configuration

Read the convention files and extract configuration values before doing any other work.

**Required**: Read `.claude/project.env.md` and extract:
- **ADO_ORG**: Organization URL (e.g., `https://dev.azure.com/MyOrg`)
- **ADO_PROJECT**: Project name (e.g., `My Project` — may contain spaces)
- **ADO_PROJECT_ENCODED**: URL-encoded project name (e.g., `My%20Project`)
- **BRANCH_USERNAME**: Username for branch naming

If `project.env.md` does not exist, **STOP** and tell the user:
```
Project configuration not found. Run /emergent-dev:init-project to set up
.claude/project.env.md with your ADO, database, and Azure configuration.
```

**Required**: Read `.claude/project.architecture.md` if it exists — extract layer structure, project constraints, and any platform complexity that affects estimation (e.g., multi-tenant architecture, real-time requirements, complex deployment targets).

**Required**: Read `.claude/project.team.md` if it exists and extract:
- **POINT_SCALE**: Story point scale (default: `1, 2, 3, 5, 8, 10`)
- **SPLIT_THRESHOLD**: Story splitting threshold (default: `13`)
- **HOURS_PER_POINT_AGENTIC**: Hours per point in agentic model (default: `4`)
- **HOURS_PER_POINT_TRADITIONAL**: Hours per point in traditional model (default: `12`)
- **VELOCITY_POINTS_PER_WEEK**: Team velocity in points/week (default: use historical calibration or note as unknown)

**Optional**: Read `.claude/project.domains.md` if it exists — extract domain terminology for expressing estimates in domain language rather than technical jargon.

**Optional**: Read `.claude/estimate-epics-features.csv` if it exists — this is the project's historical estimate-to-actual data. Use it in Step 5 for calibration.

Configure az defaults immediately:
```bash
az devops configure --defaults organization={ADO_ORG} project="{ADO_PROJECT}"
```

### Step 1: Load Requirements

#### 1a. Find the Requirements Source

If the user provided a path to a requirements document, read it. If they provided a topic or slug, check for an existing requirements document:

```bash
ls .claude/requirements/ 2>/dev/null || echo "no-requirements-dir"
```

Look for a matching directory and read the `requirements.md` inside it. If found, read the full document and extract:
- All functional requirements (FR-1, FR-2, ...)
- All non-functional requirements (NFR-1, NFR-2, ...)
- Constraints and dependencies
- Suggested story decomposition (if present)
- Any unresolved questions that affect scope

**If no requirements document exists**, present this message to the user:

> No requirements document found for this topic. You have two options:
> 1. Run `/requirements-analysis` first — this produces a structured requirements doc that feeds directly into estimation with proper traceability.
> 2. Describe the scope here in plain language — I'll estimate from your description, but the estimate will carry lower confidence since requirements haven't been formally analyzed.
>
> Which would you prefer?

If the user chooses option 2, capture their description and proceed with it as the input. Mark the overall estimate confidence as **Low** due to unanalyzed requirements.

#### 1b. Confirm Scope with the User

Summarize what you've read:

> Based on the requirements document, the scope includes:
> - **{N} functional requirements** (FR-1 through FR-{N})
> - **{N} non-functional requirements**
> - **{N} unresolved questions** (these may affect estimates)
> - **Suggested decomposition**: {N} stories
>
> Does this match what you want estimated? Any scope to add or exclude before I build the work breakdown?

Wait for the user to confirm or redirect scope before proceeding.

### Step 2: Work Breakdown Structure

Organize the requirements into an Epic → Feature → Story hierarchy.

**Rules for decomposition:**
- Each story must be **independently deliverable** — it produces something a stakeholder can see or verify on its own
- Never split by architecture layer — no "backend for X" / "frontend for X" splits
- Group stories under Features by functional domain, not technical layer
- Group Features under Epics by high-level business capability
- If the requirements document already has a suggested decomposition, use it as the starting point and refine it
- Each story must reference which FRs and NFRs it covers (for traceability)

**Story sizing guidance before estimation:**
- A story that would exceed `{SPLIT_THRESHOLD}` points after phase estimation should be split
- A story covering a single external integration usually merits its own story
- A story requiring a new data model (tables, migrations) adds meaningful complexity even if the feature logic is simple

For each story, note the **cost drivers** that will determine its estimate:

| Cost Driver | Impact |
|-------------|--------|
| External system integrations | Each integration adds analysis, contract mapping, error handling, and retry logic |
| New data model (tables, migrations) | Schema design, migration scripts, temporal table complexity if applicable |
| UI complexity | New pages, dynamic components, responsive design, empty states, loading states |
| Security / auth requirements | Permission model, row-level security, audit logging |
| Accessibility requirements | WCAG compliance, screen reader testing, keyboard nav |
| Testing complexity | Number of happy paths, edge cases, integration test surface |
| Deployment complexity | Multi-environment config, data migration, feature flags |
| Domain complexity | Business rules, validation logic, branching calculations |
| Uncertainty level | Well-understood vs novel — novel work nearly always runs longer |

Present the work breakdown as a draft and ask the user to confirm before estimating:

> Here is my proposed work breakdown. Does this look right before I apply estimates?
>
> {list epics → features → stories}
>
> Anything to split, merge, or reorder?

Wait for user confirmation.

### Step 3: Phase-Level Estimation

For each story, estimate effort across the seven phases below. Apply the agentic multiplier to arrive at agentic hours, then convert to story points using the project's `{HOURS_PER_POINT_AGENTIC}` ratio.

#### Phase Multiplier Reference

| Phase | % of Story Effort (typical) | Agentic Multiplier | What the multiplier reflects |
|-------|----------------------------|--------------------|------------------------------|
| Analysis | 15% | 0.8–1.0x | Requires human judgment and domain expertise. AI assists with research but decisions are human-paced. |
| Design | 15% | 0.7–0.9x | AI can propose schemas and API contracts, but architecture decisions and UX review require human judgment. Complex or novel integrations stay near 0.9x. |
| Development | 30% | 0.3–0.5x | Highest AI acceleration. The agent writes code, creates files, runs builds, and iterates on feedback. Human reviews and approves. |
| Testing / QA | 20% | 0.4–0.6x | AI writes test scaffolding and basic unit tests quickly. Edge case coverage, UX verification, and exploratory testing remain human-paced. |
| Debugging | 10% | 0.5–0.8x | AI effective for pattern-matching bugs and compiler errors. Novel integration issues, environment-specific failures, and data-dependent bugs require human investigation. |
| DevOps / Deploy | 5% | 0.4–0.6x | AI generates scripts and config quickly. Environment-specific issues and access provisioning are human-paced. |
| Code Review | 5% | 0.6–0.8x | AI review catches patterns and style issues quickly. Human review required for architecture correctness, security, and domain logic. |

**Adjust multipliers up or down** based on story characteristics:
- Move Development toward 0.5x for novel integrations where the agent may need many iterations
- Move Debugging toward 0.8x for stories with complex data dependencies or external system interactions
- Move Testing toward 0.6x for stories requiring manual UX verification or accessibility testing

#### PERT Estimation

For each story, produce three estimates in **traditional hours** (before applying the agentic multiplier):

- **Optimistic (O)**: Everything goes smoothly. Dependencies are available, requirements are clear, no surprises.
- **Most Likely (M)**: Realistic estimate with normal friction — one or two small surprises, one round of review feedback, typical integration gotchas.
- **Pessimistic (P)**: Worst case — a dependency is delayed, a key requirement turns out to be ambiguous, the integration behaves unexpectedly.

**PERT Expected** = `(O + 4M + P) / 6`

Apply the blended agentic multiplier (weighted average across phases) to the PERT expected value to get **agentic hours**.

Convert to points: `points = agentic_hours / {HOURS_PER_POINT_AGENTIC}` — round to the nearest value on the project's `{POINT_SCALE}`.

**Show your work for each story:**

```
Story: {title}
  Covers: FR-2, FR-3, NFR-1
  Cost drivers: 1 external API integration, new data table + migration, standard CRUD UI
  Traditional hours: O=8, M=16, P=28 → PERT Expected = 17.3h
  Blended agentic multiplier: 0.55x
  Agentic hours: 9.5h
  Story points: 8 (nearest on scale: 1, 2, 3, 5, 8, 10)
  Confidence: Medium (external API behavior not fully documented)
```

Do this for every story. Group by Feature and accumulate totals at the Feature and Epic levels.

#### Confidence Classification

| Confidence | Criteria |
|------------|----------|
| **High** | Well-understood domain, similar work done before on this project, clear requirements, no external unknowns |
| **Medium** | Some unknowns — new integration, partially defined requirements, moderate domain complexity |
| **Low** | Novel technology or domain, external system with unknown behavior, requirements have unresolved questions |

### Step 4: Risk Assessment

For each Epic or Feature, assess the four risk dimensions below. Be specific — generic risks like "scope creep" are not actionable.

#### Risk Dimensions

**Technical Risk**: How novel is the technology or integration? Has this been done before on this project?
- Low: Same patterns as existing code, well-understood APIs
- Medium: New integration pattern, new technology but well-documented
- High: First use of this platform/API, undocumented behavior, complex state management

**Requirements Risk**: How stable are the requirements?
- Low: Fully defined, stakeholder-approved, requirements doc complete
- Medium: Core defined, some details TBD, minor open questions
- High: Significant unresolved questions, stakeholder alignment incomplete, scope likely to shift

**Dependency Risk**: External teams, APIs, or data sources not under our control?
- Low: Self-contained, all dependencies internal and available
- Medium: One external dependency with an established contact
- High: Multiple external dependencies, SLA not confirmed, coordination required

**Estimation Confidence**: How closely does this work resemble past work we've delivered?
- High: Direct precedent on this project — similar feature, similar complexity
- Medium: Partial precedent — similar domain, new implementation
- Low: Novel work with no direct precedent

#### Risk Buffer

Apply a risk buffer to the raw point total based on the dominant confidence level:

| Dominant Confidence | Buffer | Rationale |
|--------------------|--------|-----------|
| High | +10% | Normal variance — implementation surprises are minor |
| Medium | +25% | Meaningful unknowns that are likely to add work |
| Low | +40–50% | Substantial unknowns — scope and effort may shift significantly |

State the buffer clearly: `Risk buffer: +25% = +{N} points (Medium confidence: {specific reason})`

### Step 5: Historical Calibration

If `.claude/estimate-epics-features.csv` exists, use it to calibrate the estimate:

1. Calculate **actual velocity** from completed Epics/Features: `actual_points_delivered / weeks_elapsed`
2. Compare the new estimate against that velocity to project a timeline
3. Note how point estimates on similar past features compared to actuals
4. Call out any features where estimates were significantly off and why (this helps calibrate the risk buffer)

Example calibration note:
> "Historical data shows the team delivered at approximately 12 pts/week over the last 3 features (estimated 80 pts, delivered 76 pts actual). At that velocity, this estimate of {N} points represents approximately {N/12} weeks."

If no historical data is available, note it explicitly:
> "No historical velocity data is available. Future estimates will benefit from tracking actuals against these baseline estimates."

Also query ADO for any related completed work items to cross-reference point estimates:

```bash
az boards query --wiql "SELECT [System.Id], [System.Title], [Microsoft.VSTS.Scheduling.StoryPoints], [System.State] FROM WorkItems WHERE [System.WorkItemType] = 'User Story' AND [System.State] = 'Closed' AND [System.Title] CONTAINS '{keyword}' ORDER BY [System.ChangedDate] DESC" --output json
```

### Step 6: Generate Estimate Document

Write the estimate to `.claude/requirements/{slug}/estimate.md` if a requirements document exists, or to `.claude/estimates/{slug}.md` for standalone estimates.

Create the output directory if needed:
```bash
mkdir -p ".claude/requirements/{slug}"
# or
mkdir -p ".claude/estimates"
```

The document must follow this structure exactly:

---

```markdown
# Estimate: {Feature / Project Name}

**Date**: {today's date}
**Based on**: {path to requirements doc, or "description provided by user"}
**Prepared by**: {BRANCH_USERNAME}

---

## Executive Summary

{2–3 paragraphs. Cover: total effort in points and approximate calendar time, confidence level and what drives it, key cost drivers (the 3–4 things that most explain the estimate), and what is explicitly included vs. excluded. A manager should read this and understand the scope and cost without reading the rest of the document.}

**Total estimate**: {N} points risk-adjusted ({N} points base + {N} points risk buffer)
**Agentic timeline**: approximately {N} weeks at {VELOCITY_POINTS_PER_WEEK} pts/week
**Traditional timeline**: approximately {N} weeks (for reference — not the delivery model)
**Agentic savings vs. traditional**: ~{pct}%
**Overall confidence**: High / Medium / Low

---

## Agentic Development Model

This estimate assumes **agentic (AI-assisted) development** — a delivery model where an AI agent writes code, creates files, runs builds, proposes designs, and iterates on review feedback. The human developer directs the work, reviews outputs, makes architectural decisions, and approves changes.

### What this means for each phase

| Phase | Traditional Effort | Agentic Multiplier | Agentic Effort | Why |
|-------|-------------------|-------------------|----------------|-----|
| Analysis | {N}h | 0.8–1.0x | {N}h | Human judgment required for domain research and decision-making |
| Design | {N}h | 0.7–0.9x | {N}h | AI proposes designs; human reviews and decides on architecture |
| Development | {N}h | 0.3–0.5x | {N}h | Agent writes code and iterates quickly; human reviews and approves |
| Testing / QA | {N}h | 0.4–0.6x | {N}h | Agent scaffolds tests; edge cases and UX testing remain human |
| Debugging | {N}h | 0.5–0.8x | {N}h | Pattern bugs resolved by AI; novel integration issues require human investigation |
| DevOps / Deploy | {N}h | 0.4–0.6x | {N}h | Agent generates scripts; environment-specific issues are human |
| Code Review | {N}h | 0.6–0.8x | {N}h | AI review catches patterns; architecture and domain review is human |

**Traditional estimate**: {N} points / {N} hours
**Agentic estimate**: {N} points / {N} hours
**Savings from agentic model**: {pct}% reduction in effort

### Agentic Assumptions

- The AI agent used is capable of reading and writing code across all project layers (Domain, Application, Infrastructure, API, Web)
- The agent can run builds, deploy database changes, and interpret compiler errors autonomously
- Human review time is not eliminated — it is reduced to directed oversight (reading diffs, answering questions, making judgment calls)
- Development phases that involve novel integrations or ambiguous behavior may not realize the full 0.3–0.5x multiplier — these are noted per-story
- Debugging time for data-dependent or environment-specific issues is estimated conservatively (0.7–0.8x) because these require human investigation regardless of tooling

---

## Work Breakdown Structure

### Epic: {name}

**Description**: {1–2 sentences of business context}

#### Feature: {name}

**Description**: {1–2 sentences of what this feature delivers}
**Requirements covered**: {FR-list, NFR-list}

| Story | Points | O / M / P (trad. hrs) | Confidence | Key Cost Drivers |
|-------|--------|----------------------|------------|-----------------|
| {title} | 5 | 6 / 12 / 20 | High | Standard CRUD, existing patterns, 2 API endpoints |
| {title} | 8 | 10 / 18 / 32 | Medium | External SAP integration, new data table + migration, custom validation |
| {title} | 3 | 2 / 6 / 10 | High | UI-only change, no new data model, existing component patterns |

**Feature total (base)**: {N} points (~{N} agentic days / ~{N} traditional days)

#### Feature: {name}

...

**Epic total (base)**: {N} points

---

### Epic: {name}

...

---

## Phase Breakdown Summary

Aggregate hours across all stories, broken down by phase. This is the view to use when planning team capacity — it shows where the effort actually lives.

| Phase | % of Effort | Traditional Hours | Agentic Hours | Savings |
|-------|-------------|------------------|---------------|---------|
| Analysis | 15% | {N}h | {N}h | {pct}% |
| Design | 15% | {N}h | {N}h | {pct}% |
| Development | 30% | {N}h | {N}h | {pct}% |
| Testing / QA | 20% | {N}h | {N}h | {pct}% |
| Debugging | 10% | {N}h | {N}h | {pct}% |
| DevOps / Deploy | 5% | {N}h | {N}h | {pct}% |
| Code Review | 5% | {N}h | {N}h | {pct}% |
| **Total** | 100% | **{N}h** | **{N}h** | **{pct}%** |

---

## Risk Assessment

| Risk | Dimension | Level | Affected Stories | Impact | Mitigation |
|------|-----------|-------|-----------------|--------|------------|
| {specific risk} | Technical | High | Story 3, Story 4 | Integration may behave differently than documented | Spike story in Sprint 1 to validate API contract |
| {specific risk} | Requirements | Medium | Story 2 | Q3 (unresolved) may add a new data model | Resolve Q3 before starting Story 2 |
| {specific risk} | Dependency | Low | Story 5 | Deployment window must be coordinated with ops | Schedule 2 weeks ahead |

**Risk buffer applied**: +{pct}% = +{N} points
**Reason**: {specific explanation — e.g., "Medium confidence overall: external API behavior partially documented, one unresolved question on data retention scope"}

**Base estimate**: {N} points
**Risk-adjusted estimate**: {N} points

---

## Assumptions & Exclusions

### Assumptions

These are the conditions this estimate relies on. If any assumption is wrong, the estimate should be revisited.

- {assumption} — if violated, impact is approximately {+N points / +N weeks}
- {assumption}
- {assumption}

### Exclusions (Out of Scope)

These items are explicitly NOT included in this estimate. Documenting them prevents scope creep.

- {item explicitly excluded}
- {item explicitly excluded}
- {item explicitly excluded}

---

## Historical Calibration

{If historical data exists: "Historical velocity on this project is approximately {N} pts/week based on {N} completed features ({N} pts estimated, {N} pts actual — {pct}% accuracy). At that velocity, this {N}-point estimate represents approximately {N} weeks of work."}

{If no historical data: "No historical velocity data is available for this project. This estimate uses the default ratio of {HOURS_PER_POINT_AGENTIC} hours/point for agentic development. Tracking actuals against these estimates will calibrate future work."}

{If ADO completed stories were found: note any similar past stories with their estimated vs. actual points.}

---

## Confidence Summary

| Metric | Value |
|--------|-------|
| Base estimate (points) | {N} |
| Risk buffer | +{N} ({pct}%) |
| **Risk-adjusted estimate** | **{N} points** |
| Agentic hours (risk-adjusted) | {N}h |
| Traditional hours (risk-adjusted) | {N}h |
| Agentic timeline | ~{N} weeks at {N} pts/week |
| Traditional timeline | ~{N} weeks at {N} pts/week |
| Agentic savings | ~{pct}% |
| Unresolved questions affecting scope | {N} |
| **Overall confidence** | **High / Medium / Low** |
```

---

### Step 7: Review with User

After writing the document, present a concise summary:

```
## Estimate Complete

**Saved to**: .claude/requirements/{slug}/estimate.md (or .claude/estimates/{slug}.md)

### Summary
- **Total (risk-adjusted)**: {N} points
- **Agentic timeline**: ~{N} weeks
- **Traditional timeline**: ~{N} weeks (for reference)
- **Agentic savings**: ~{pct}%
- **Overall confidence**: High / Medium / Low

### Largest Stories
| Story | Points | Confidence |
|-------|--------|------------|
| {title} | {N} | {level} |
| {title} | {N} | {level} |

### Key Risks
- {risk}: {brief impact}
- {risk}: {brief impact}

### Open Questions Still Affecting Scope
- {Q if any}: owned by {stakeholder}
```

Then ask the following, one at a time:

1. **Does the scope look right?** Any stories that feel over- or under-scoped?
2. **Are there stories to add or remove?** Anything the analysis missed?
3. **Want to create the Epic/Feature/Story hierarchy in ADO?** I can hand this off to `/create-story` with the estimate data pre-populated.
4. **Want a Word document version?** I can generate a client-presentable estimate doc if needed.

If the user wants ADO items created, hand off to `/create-story` with:
- The story title
- The requirements doc path as context
- The suggested acceptance criteria (from the requirements doc)
- The estimated story points

## Notes

- **Show your work.** Every number must have a traceable explanation. A client should be able to say "why is Story 3 eight points?" and receive a clear answer referencing specific cost drivers.
- **The agentic multipliers are guidelines, not fixed rules.** Adjust them based on what you know about the specific story — a story with a well-documented external API behaves differently from one with an undocumented internal API.
- **Integration complexity is almost always underestimated.** When in doubt, move toward the pessimistic end of the PERT range for stories with external dependencies.
- **This skill works without a formal requirements doc** — the user can describe scope in plain language. But estimates produced without formal requirements should carry Low confidence and include a recommendation to formalize the requirements.
- **Do not include project-specific references in the skill itself.** Use `{VARIABLE}` placeholders — the project values come from `.claude/project.env.md` and `.claude/project.team.md`.
- **Agentic savings compound across stories.** A 12-story estimate that saves 50% on Development and 45% on Testing delivers materially better ROI than a 2-story estimate. The summary should make this visible to the client.
- **The estimate is a living document.** If requirements change, update the estimate. Add a Change Log section at the bottom when revisions are made: `- {date}: Revised based on {reason} — impact: {+/- N points}`.
- When estimating stories that reference an unresolved clarifying question from the requirements doc, flag the dependency explicitly and apply a pessimistic buffer to the affected stories.
