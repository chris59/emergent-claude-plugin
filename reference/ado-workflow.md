# Azure DevOps (ADO) Story Workflow Reference

Generic ADO story lifecycle and quality standards for Agile .NET teams.

---

## Work Item Hierarchy

```
Epic
  └── Feature
        └── User Story  (or Bug)
                └── Task  (optional — used for sub-work within a story)
```

Rules:
- Every **User Story** must have a parent **Feature**.
- Every **Feature** should have a parent **Epic**.
- Orphaned stories (no parent Feature) indicate planning debt — resolve during grooming.
- Work item type for user-visible stories is **User Story** (not "Product Backlog Item" or "Task").

---

## Story States

| State | Meaning |
|-------|---------|
| **New** | Created but not yet groomed or estimated |
| **Active** | Being worked on in the current sprint |
| **Dev Complete** | Development done; awaiting QA or stakeholder review |
| **Closed** | Accepted and done |

Bug states follow the same lifecycle. Bugs should be closed (not just resolved) once the fix is deployed and verified.

Do not leave stories in "Active" across multiple sprints without a comment explaining the delay.

---

## Estimation

Use **Fibonacci story points** only:

`1 — 2 — 3 — 5 — 8 — 10`

| Points | Meaning |
|--------|---------|
| 1 | Trivial — one file, fully understood |
| 2 | Small — a few files, low risk |
| 3 | Medium — multiple layers, some discovery |
| 5 | Large — cross-layer, some unknowns |
| 8 | Very large — significant scope or risk |
| 10 | At the split threshold — consider splitting |
| 13+ | Too big — **must be split before sprint commitment** |

### Splitting threshold
Any story estimated at **13 or more points** must be split before it enters a sprint. Split
by **capability** (end-to-end slice of user value), never by layer (e.g., "do the DB layer"
and "do the UI layer" are not valid splits — they deliver no value independently).

---

## Acceptance Criteria Quality

Every AC must be:
- **Testable**: a clear pass/fail condition that any team member can verify.
- **Specific**: references actual fields, endpoints, screens, or behaviors.
- **Completable**: has a definitive done state — not ongoing.

### Vague terms — never use in AC

The following words signal an untestable acceptance criterion. Replace them with measurable specifics.

| Banned term | Replace with |
|-------------|-------------|
| improve | "increases X from N to M" or "reduces latency below Nms" |
| optimize | specific metric: "query executes in < 100ms on N rows" |
| clean up | name the specific thing being removed or reorganised |
| as needed | define the exact trigger condition |
| etc. | list every item; "etc." is never acceptable in AC |
| appropriate | define the exact rule |
| better | measurable comparison |
| handle errors | name each error case and its expected outcome |
| flexible | define what variability is required |
| robust | name the failure modes it must survive |
| performant | specify the target metric |
| user-friendly | name the UX requirement explicitly |

### AC template

```
Given [context / precondition]
When [action]
Then [observable, testable outcome]
```

Example:
```
Given a dealer with no submitted forecast for the current cycle
When they navigate to the Forecast page
Then a zero-state message "No forecast submitted" is displayed
  and the Submit button is disabled
```

---

## Story Cohesion Philosophy

The right size for a story is **the smallest unit of work that delivers end-to-end user value**.

- Touching multiple layers (database, API, UI) in one story is **normal and expected** for
  feature work. Splitting by layer destroys value delivery and makes integration harder.
- Split when the story is too big to complete in one sprint, not because it touches multiple layers.
- Each split piece must independently deliver observable value to a user or system.

---

## Linking Stories to Code

Every PR to a production branch (`develop`, `main`) must reference a story:

- Include the story ID in the branch name: `feature/janedoe/{storyId}-description`.
- The PR description must reference the story: `ADO Story: #{storyId}`.
- The CI stamp-review gate enforces this — PRs without a story ID are blocked.

---

## Bug Lifecycle

1. **New** — filed with repro steps, expected vs actual behavior, and environment.
2. **Active** — assigned to a developer; fix in progress.
3. **Dev Complete** — fix deployed to dev/test; awaiting verification.
4. **Closed** — verified fixed in production (or UAT for UAT-only bugs).

Required fields on every bug:
- **Repro Steps** — numbered, specific, reproducible.
- **Expected Behavior** — what should happen.
- **Actual Behavior** — what does happen.
- **Environment** — Dev / UAT / Production.
- **Severity** — Critical / High / Medium / Low.

---

## Sprint Ceremonies

| Ceremony | Cadence | Purpose |
|----------|---------|---------|
| Grooming | Weekly | Size, clarify AC, split large stories |
| Planning | Sprint start | Commit to sprint backlog |
| Review | Sprint end | Demo to stakeholders |
| Retro | Sprint end | Inspect and adapt process |

Stories must be **groomed and estimated before sprint planning** — unestimated stories
cannot be committed to a sprint.

---

## ADO API Access (for Automation)

- WIQL `SELECT` does not return `System.Parent` — use the REST API bulk endpoint for
  parent-child rollups.
- Work item types are case-sensitive in WIQL queries.
- Use `az devops` CLI or direct REST calls for automation; avoid screen-scraping.

```bash
# Configure defaults once
az devops configure --defaults organization=https://dev.azure.com/{org} project="{project}"

# List active stories
az boards query --wiql "SELECT [System.Id], [System.Title] FROM WorkItems WHERE [System.WorkItemType] = 'User Story' AND [System.State] = 'Active'"
```
