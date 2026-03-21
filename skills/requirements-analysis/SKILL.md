---
name: requirements-analysis
description: Analyze meeting notes, documents, and descriptions to extract structured requirements. Use before creating stories to ensure thorough analysis.
user-invocable: true
argument-hint: "<topic or paste notes>"
---

# Requirements Analysis

Pre-story analysis tool. Accepts raw inputs — meeting notes, documents, screenshots, emails, or plain descriptions — and produces structured requirements that feed directly into `/create-story` and `/check-story`.

The goal is to surface ambiguities, map scope to the project's domain model, and decompose the work into well-bounded stories **before** any ADO work items are created. Rushing to stories without this step is the single biggest source of poorly scoped work.

## Arguments

- Free-text topic description, pasted notes, or a file path — anything that describes what needs to be analyzed (optional — will ask interactively if not provided)

## Instructions

Follow these steps in order. This skill is **interactive** — pause and wait for user input where indicated.

### Step 0: Load Project Configuration

Read the convention files and extract configuration values before doing any other work.

**Required**: Read `.claude/project.env.md` and extract:
- **ADO_ORG**: Organization URL (e.g., `https://dev.azure.com/MyOrg`)
- **ADO_PROJECT**: Project name (e.g., `My Project` — may contain spaces)
- **ADO_PROJECT_ENCODED**: URL-encoded project name (e.g., `My%20Project`)
- **ADO_REPO_ID**: Repository GUID
- **BRANCH_USERNAME**: Username for branch naming

If `project.env.md` does not exist, **STOP** and tell the user:
```
Project configuration not found. Run /emergent-dev:init-project to set up
.claude/project.env.md with your ADO, database, and Azure configuration.
```

**Recommended**: Read `.claude/project.architecture.md` if it exists — extract the project name, layer structure, and any architectural constraints relevant to scoping requirements.

**Optional**: Read `.claude/project.domains.md` if it exists — this file contains the project's domain model and terminology. Use it throughout to express requirements in domain language rather than technical jargon.

**Optional**: Read `.claude/project.team.md` if it exists and extract:
- **POINT_SCALE**: Story point scale (default: `1, 2, 3, 5, 8, 10`)

Configure az defaults immediately:
```bash
az devops configure --defaults organization={ADO_ORG} project="{ADO_PROJECT}"
```

### Step 1: Gather Inputs

#### 1a. Capture the Topic

If the user provided a description in the arguments, use it as the starting topic. Otherwise ask:

> What do you need to analyze? You can:
> - Paste meeting notes or an email directly into the chat
> - Describe a feature or capability in plain language
> - Provide a file path to an existing document
> - Describe multiple related things at once — I'll help scope them

Capture the topic. Don't proceed until you have enough to start.

#### 1b. Ask About Additional Sources

Present this question to the user (do not skip — additional sources often reveal critical context):

> What other sources do you have for this topic? Check all that apply:
> - Meeting notes or action items (paste them in)
> - Requirement documents or specs (provide file path)
> - Screenshots or mockups (provide file path — I can read images)
> - Figma designs (provide the Figma share link)
> - Emails or Slack threads (paste them in)
> - Existing requirement files in `.claude/requirements/`
> - None — just what you've described

Read every source the user identifies:
- For file paths: use the **Read** tool
- For screenshots/images: use the **Read** tool (handles PNG, JPG, etc.)
- For Figma links: use the Figma REST API to extract component structure:
  ```bash
  # Extract fileKey from URL: https://www.figma.com/file/{fileKey}/...
  curl -s -H "X-Figma-Token: {FIGMA_TOKEN}" \
    "https://api.figma.com/v1/files/{fileKey}" \
    | python -c "import sys,json; f=json.load(sys.stdin); print(json.dumps(f.get('document',{}), indent=2))" 2>/dev/null | head -200
  ```
  If no Figma token is configured, note it and ask the user to describe the key screens instead.

#### 1c. Check for Existing Requirements (Update Mode)

Check `.claude/requirements/` for existing analysis on this topic:

```bash
ls .claude/requirements/ 2>/dev/null || echo "no-requirements-dir"
```

**If an existing `requirements.md` is found for this topic** (matching directory name or topic keywords):

1. Read the existing document fully
2. Tell the user what's already captured — summarize the current requirements, open questions, and suggested stories
3. Ask: **"This topic has an existing requirements analysis. What would you like to do?"**
   - **Update** — add new information (meeting transcript, additional notes, answers to open questions) while preserving everything already documented
   - **Revise** — rework specific sections based on new understanding
   - **Continue** — pick up where we left off (answer remaining open questions, refine decomposition)

4. When updating, **merge new inputs into the existing document** — do NOT overwrite. Specifically:
   - Add new sources to the Sources section
   - Append new requirements with the next FR/NFR number (don't renumber existing ones)
   - Move answered questions from "Unresolved" to "Resolved" with the answer
   - Update story decomposition if new requirements change the scope
   - Add a `## Change Log` entry at the bottom: `- {date}: Updated with {source description}`

This is the primary way teams iterate on requirements over time — initial analysis, then updates as meeting transcripts arrive, stakeholder feedback comes in, or designs evolve.

**If no existing analysis is found**, proceed to Step 1d (new analysis).

#### 1d. Check ADO for Related Work

Search ADO for Features and Stories that might overlap with this topic:

```bash
# Search for related features using keywords from the topic
az boards query --wiql "SELECT [System.Id], [System.Title], [System.WorkItemType], [System.State] FROM WorkItems WHERE [System.WorkItemType] IN ('Feature', 'User Story') AND [System.State] NOT IN ('Closed', 'Removed') AND [System.Title] CONTAINS '{keyword}' ORDER BY [System.WorkItemType], [System.Title]" --output json
```

Run 2-3 keyword searches based on the topic. Note any items found — they inform scope decisions and prevent duplication.

### Step 2: Analyze and Extract

Analyze all gathered inputs. Do not present a wall of text — structure the findings clearly.

Work through each source and extract:

#### 2a. Functional Requirements

What must the system DO? These are observable behaviors — things that can be verified.

For each requirement:
- State it as a clear, testable behavior (not an implementation choice)
- Identify which domain entities or processes are involved (use terms from `project.domains.md` if available)
- **Citation (MANDATORY)**: Every requirement MUST cite its origin. Use the format `[Source: {origin}]`. Origins include:
  - `[Source: Client — {person name}, Sprint Planning meeting, 2026-03-20]` — requirement came directly from the client; include WHO said it, WHICH meeting, and WHEN
  - `[Source: Client — {person name}, email re: "{subject line}", 2026-03-15]` — client communication; include sender, subject, and date
  - `[Source: Client — {person name}, "{document title}" p.{N}, 2026-03-10]` — from a client-provided document; include author, document name, and page/section if applicable
  - `[Source: Stakeholder — {person name}, {context}, verbal]` — stakeholder direction; include who and the conversation context
  - `[Source: Design — Figma "{screen/component name}", {designer name}]` — derived from a design artifact; include which screen and who created it
  - `[Source: Dev — {person name}, technical analysis of {area}]` — developer-identified requirement; include who and what they analyzed
  - `[Source: Manager — {person name}, scope decision in {context}]` — management direction; include who and when/where the decision was made
  - `[Source: Inferred — based on {FR-N} and {domain constraint}]` — not explicitly stated; cite WHAT it was inferred from so it can be validated
  - `[Source: Regulation — {standard name and section, e.g., "WCAG 2.1 AA §1.4.3"}]` — compliance or regulatory; cite the specific standard and clause

  **Be as specific as possible.** "Client meeting" is not enough — "John Smith, SAP Integration kickoff meeting, 2026-03-20" lets someone trace the requirement back to the exact conversation. If you don't know who said it, note that: "Unknown attendee, Sprint Review meeting, 2026-03-20 — needs attribution."
- Requirements without client origin should be flagged for validation — they may be valid (security hardening, accessibility) but the team should consciously decide to include them
- Assign a temporary label: FR-1, FR-2, ...

Good functional requirement: "When a user submits a forecast, the system records the submission timestamp and the submitting user's identity."
Bad functional requirement: "Add a timestamp column to the forecast table." (implementation, not behavior)

#### 2b. Non-Functional Requirements

Performance, security, accessibility, reliability, UX behavior that cuts across functional requirements:
- Response time / throughput targets
- Access control (who can see or do what)
- Accessibility standards (WCAG level, screen reader support)
- Data retention or audit requirements
- Concurrent user or load expectations
- Assign labels: NFR-1, NFR-2, ...

#### 2c. Constraints and Dependencies

Things that limit design choices or require coordination with external systems:
- External systems the feature must integrate with
- Data sources or feeds required
- Timing constraints (deadlines, scheduling windows, data availability)
- Platform constraints (browser support, mobile, deployment environment)
- Regulatory or compliance requirements

#### 2d. Edge Cases and Error Handling

Scenarios that aren't the happy path but must be handled:
- What happens when input is missing, malformed, or out of range?
- What if an external dependency is unavailable?
- What if a user takes an unexpected action sequence?
- What are the failure modes, and what should users see/experience?

#### 2e. Domain Mapping

If `project.domains.md` exists, map each functional requirement to the domain:
- Which aggregate roots or bounded contexts are involved?
- Which domain events might be raised?
- Are there domain rules (invariants) that requirements must respect?

#### 2f. Ambiguities and Assumptions

Flag everything that is:
- **Ambiguous**: the source material says something that could mean two different things
- **Assumed**: you've made a design or scope decision that the sources don't explicitly state
- **Unstated**: something the system probably needs to do, but the sources don't mention

Be explicit. Don't silently fill in assumptions — surface them so the user can confirm or correct.

### Step 3: Clarifying Questions

Present a numbered list of questions that must be answered before stories can be written. Group by category.

```
## Clarifying Questions

### Business Logic
1. {question}
   WHY THIS MATTERS: {what decision or scope boundary this answer unlocks}

2. {question}
   WHY THIS MATTERS: {what decision or scope boundary this answer unlocks}

### UX / Design
3. {question}
   WHY THIS MATTERS: {what this affects}

### Technical / Integration
4. {question}
   WHY THIS MATTERS: {what this affects}

### Data
5. {question}
   WHY THIS MATTERS: {what this affects}
```

Only ask questions that genuinely affect what gets built or how it's scoped. Don't ask about things that are already clear from the sources or that can be decided during implementation.

**Wait for user responses before proceeding.** This is a conversation, not a batch process.

When the user responds, update your understanding of the requirements accordingly. If their answers reveal new questions, ask them — but be disciplined. Don't turn this into an endless questionnaire. After one round of Q&A, proceed even if some questions remain unresolved (mark them as unresolved in the output).

### Step 4: Produce Requirements Document

Once you have enough information to proceed (at minimum: Step 1 inputs captured and Step 3 questions answered or acknowledged), write the structured requirements document.

Determine the feature slug: lowercase kebab-case from the topic (e.g., "dealer forecast export" → `dealer-forecast-export`). This becomes the subdirectory name.

Create the output directory and source archive:
```bash
mkdir -p ".claude/requirements/{feature-slug}/sources"
```

**Archive all raw source material** into the `sources/` subdirectory:
- Meeting notes/transcripts → `sources/meeting-{date}.md`
- Emails → `sources/email-{person}-{date}.md`
- Pasted content → `sources/notes-{date}.md`
- Screenshots → copy to `sources/` with descriptive names
- Document summaries → `sources/summary-{doc-name}.md`

This creates a searchable archive. When someone asks "where did FR-3 come from?", the source file is right there.

Write the document to `.claude/requirements/{feature-slug}/requirements.md`:

```markdown
# Requirements: {Feature Name}

## Sources

| ID | Type | Description | Who | Date | Location |
|----|------|-------------|-----|------|----------|
| S1 | Meeting | Sprint Planning — SAP integration discussion | John Smith (client), Chris Adam | 2026-03-20 | `sources/meeting-sprint-planning-2026-03-20.md` |
| S2 | Email | Re: "Dealer forecast requirements" | Jane Doe (client) → Chris Adam | 2026-03-15 | `sources/email-jane-doe-2026-03-15.md` |
| S3 | Design | Figma — Dealer Forecast Card | Sarah (designer) | 2026-03-12 | `sources/figma-dealer-forecast-card.md` |
| S4 | Document | "Honda AIM Allocation Rules v2.pdf" | Mahesh Yadav (client) | 2026-03-01 | `sources/honda-allocation-rules-v2-summary.md` |
| S5 | Transcript | Teams recording — requirements walkthrough | Multiple attendees | 2026-03-18 | `sources/transcript-requirements-walkthrough-2026-03-18.md` |

**Important**: Save all raw source material into `.claude/requirements/{slug}/sources/` so it can be searched and referenced later. Meeting transcripts, emails, and notes should be saved as markdown files. Screenshots and images should be copied as-is.

## Context

{2-4 sentences: what this feature/capability is, who it serves, and why it matters to the business.
Use domain language. Reference any ADO Features or Epics this falls under.}

## Functional Requirements

| ID | Requirement | Priority | Source | Validated |
|----|-------------|----------|--------|-----------|
| FR-1 | {requirement stated as observable system behavior} | Must | [S1] Client — {name} | Yes/No |
| FR-2 | {requirement} | Should | [S2] Dev — technical analysis | Pending |

**Priority levels** (MoSCoW):
- **Must** — non-negotiable for delivery
- **Should** — important but delivery is viable without it
- **Could** — desirable if time permits
- **Won't** — explicitly out of scope (document WHY to prevent scope creep)

**Validated column**: Has the requirement been confirmed by the client or authoritative stakeholder? Requirements sourced from Dev/Manager/Inferred should be validated before story creation.

## Non-Functional Requirements

| ID | Requirement | Category | Source | Validated |
|----|-------------|----------|--------|-----------|
| NFR-1 | {requirement} | Performance | [S1] | Yes |
| NFR-2 | {requirement} | Security | [Dev — inferred] | Pending |

Categories: Performance, Security, Accessibility, Reliability, UX, Data Retention, Compliance

## Constraints & Dependencies

- {constraint or external dependency — be specific about system name, timing, or data source} `[Source: {origin}]`
- ...

## Edge Cases & Error Handling

- **{scenario}**: {expected system behavior} `[Source: {origin}]`
- **{scenario}**: {expected system behavior} `[Source: {origin}]`
- ...

## Clarifying Questions Log

Track ALL questions raised during analysis — both answered and pending. This is the audit trail of how requirements were refined.

### Resolved

| # | Question | Asked | Answered By | Answer | Date | Impact |
|---|----------|-------|-------------|--------|------|--------|
| Q1 | {question} | Step 3 | {person} | {answer} | {date} | Updated FR-2 |
| Q2 | {question} | Meeting | {person} | {answer} | {date} | Added NFR-3 |

### Unresolved

| # | Question | Category | Needed From | Why It Matters | Blocking |
|---|----------|----------|-------------|----------------|----------|
| Q3 | {question} | Business Logic | {stakeholder} | {what decision this unlocks} | Story 2 |
| Q4 | {question} | Integration | {team/vendor} | {what this affects} | No |

## Related ADO Items

- {WorkItemType} #{id}: {title} — {relationship: "overlaps", "depends on", "related to", "parent candidate"}
- ...
(Leave blank if nothing found in Step 1d)

## Suggested Story Decomposition

Based on the requirements above, this feature could be decomposed into the following stories.
Each story is a cohesive end-to-end unit of deliverable work — not a layer or a task.

1. **Story: {title}** (~{N} pts from {POINT_SCALE}) — covers {FR-list}, {NFR-list}
   - AC1: {testable acceptance criterion}
   - AC2: {testable acceptance criterion}
   - AC3: {testable acceptance criterion}

2. **Story: {title}** (~{N} pts) — covers {FR-list}
   - AC1: {testable acceptance criterion}
   - AC2: {testable acceptance criterion}

(If the entire scope fits one story, say so — don't force a split.)

## Traceability Matrix

Maps requirements back to sources and forward to suggested stories. This is the single view that answers "where did this come from?" and "where does it go?"

| Requirement | Source | Priority | Validated | Story |
|-------------|--------|----------|-----------|-------|
| FR-1 | S1 — Client meeting | Must | Yes | Story 1 |
| FR-2 | S2 — Dev analysis | Should | Pending | Story 1 |
| NFR-1 | S1 — Client meeting | Must | Yes | Story 2 |
| FR-3 | Inferred | Could | No | Backlog |

## Change Log

- {date}: Initial analysis from {sources}

```

Guidelines for the decomposition:
- Each suggested story must be independently deliverable — it produces something a stakeholder can see or verify on its own
- Do NOT split by architecture layer (no "backend for X" / "frontend for X" splits)
- Use point estimates from `{POINT_SCALE}` (from `project.team.md`, or default `1, 2, 3, 5, 8, 10`)
- ACs in the decomposition are suggestions — they will be refined when creating the actual stories
- If scope is too uncertain to decompose, say so and explain what needs to be resolved first

### Step 5: Generate Professional Word Document

After writing the markdown requirements doc, generate a branded `.docx` for client distribution and stakeholder sign-off.

1. Locate `generate_status_report.py` (the shared docx engine) — same search order as the status report skill.

2. Build a JSON file with this structure:
```json
{
    "date_range": "{date of last update}",
    "output_path": ".claude/requirements/{feature-slug}/{Feature Name} - Requirements.docx",
    "branding": {
        "project_name": "{PROJECT_NAME}"
    },
    "executive_summary": "Use the Context section from the requirements doc — 2-4 sentences explaining what this feature is, who it serves, and why it matters.",
    "sections": [
        {
            "heading": "Functional Requirements",
            "items": [
                "Summary paragraph describing the category, then the top requirements listed with IDs"
            ]
        },
        {
            "heading": "Non-Functional Requirements",
            "items": ["NFR items"]
        },
        {
            "heading": "Constraints & Dependencies",
            "items": ["Constraint items"]
        },
        {
            "heading": "Assumptions",
            "items": ["Each assumption with risk rating"]
        }
    ],
    "callout": {
        "text": "OPEN QUESTIONS — {N} questions remain unresolved and must be answered before implementation begins. See Section X."
    }
}
```

3. **Additional sections not handled by the shared script** — write directly using python-docx after the script generates the base:
   - **Requirements tables** (FR/NFR) with columns: ID, Requirement, Priority, Source, Validated
   - **Assumptions table** with columns: ID, Assumption, Risk if Wrong, Source
   - **Clarifying Questions** — Resolved and Unresolved tables
   - **Traceability Matrix** — Requirement → Source → Story mapping
   - **Suggested Story Decomposition** — Story title, points, ACs
   - **Sign-off block** at the end: "Reviewed and accepted by: _____________ Date: _____"

4. Use the same table styling as the status report: slim headers with thin colored bottom border, alternating row shading, Calibri 11pt body, 10pt tables, right-aligned numeric columns.

5. Output the Word doc to `.claude/requirements/{feature-slug}/{Feature Name} - Requirements.docx` and also copy to `{STATUS_REPORT_OUTPUT_DIR}` if configured.

Tell the user the path to both the `.md` and `.docx` files.

### Step 6: Review with User

After writing the document, present a summary of findings:

```
## Requirements Analysis Complete

**Documents saved to**:
- `.claude/requirements/{feature-slug}/requirements.md` (version-controlled, feeds into other skills)
- `.claude/requirements/{feature-slug}/{Feature Name} - Requirements.docx` (client-facing, for sign-off and distribution)

### Summary
- **Functional Requirements**: {N} identified (FR-1 through FR-{N})
- **Non-Functional Requirements**: {N} identified
- **Edge Cases**: {N} documented
- **Open Questions**: {N} resolved, {N} still unresolved
- **Related ADO Items**: {N} found

### Suggested Stories
1. **{title}** (~{N} pts)
2. **{title}** (~{N} pts)
{...}

### Unresolved Questions
{List any questions that couldn't be answered — with the stakeholder who owns the answer}
```

Then ask:

> Would you like to create any of these stories now? I can run `/create-story` for any of them with this requirements doc as context — the ACs and description will be pre-populated from the analysis.
>
> Which story should we start with, or would you like to refine the requirements first?

If the user wants to create a story, hand off with:
- The suggested story title
- The relevant FR/NFR references from the requirements doc
- The suggested ACs
- The path to the requirements doc (`.claude/requirements/{feature-slug}/requirements.md`)

These feed directly into `/create-story` as starting content.

## Notes

- This skill is **interactive** — the Q&A in Step 3 is not optional. Requirements written without clarification are guesses.
- Use domain language from `project.domains.md` throughout. Requirements written in technical jargon are harder for stakeholders to validate.
- The requirements document is a **living document**. If new information comes in later, update it — don't create a second file.
- If the user provides a Figma link, use the Figma REST API to extract component structure. If no token is available, ask the user to describe the key screens instead.
- Each analysis gets its own subdirectory in `.claude/requirements/` named with a kebab-case slug. Create the directory if it doesn't exist.
- Cross-reference ADO in Step 1d to avoid duplicating existing stories. If a proposed story clearly duplicates an existing one, flag it and suggest using `/check-story` on the existing item instead.
- Story point estimates in the decomposition use the project's scale from `project.team.md`. Default to `1, 2, 3, 5, 8, 10` if the file is absent.
- The requirements doc path can be passed as context to `/create-story` to pre-populate the story's description and ACs.
