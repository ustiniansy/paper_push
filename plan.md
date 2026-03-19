# Paper Push Plan

## Goal

Build `paper_push` from a personal Feishu workflow into a reusable paper-intelligence product that can realistically grow toward 1000 GitHub stars.

The project should move through three outcome levels:

1. Usable
   New users can generate their first daily report within 10 minutes.
2. Shareable
   The README, screenshots, and output quality make the value obvious at a glance.
3. Trustworthy
   The pipeline is stable, testable, and safe to run continuously.

## Product Positioning

Recommended positioning:

`A paper intelligence system for researchers and labs, with incremental collection, relevance scoring, conference monitoring, and multi-channel delivery.`

Target users:

- Individual researchers
- Research labs and study groups
- AI product and application teams
- Technical intelligence / trend tracking teams

Primary selling points:

1. Incremental collection with lower miss risk
2. Conference paper monitoring
3. Personalized relevance scoring
4. Multi-channel delivery and knowledge-base export

## Principles

- Prefer the shortest path to a working demo.
- Reduce platform lock-in.
- Keep the current Feishu workflow working while introducing abstractions.
- Ship in slices that are easy to verify.
- Optimize for user onboarding, not just feature count.

## Roadmap

### Phase 0: Product Definition

Objective:
Align the product story before deeper refactors.

Tasks:

- Finalize one-line positioning and repo subtitle
- Define the top 2-3 selling points for the README first screen
- Define the primary target user groups
- Define what is explicitly out of scope for v1

Done when:

- README first screen can explain the product in 3 short statements
- The repo can answer why it is different from generic arXiv summarizers

### Phase 1: First-Run Experience

Objective:
Make the project usable without Feishu.

Tasks:

- Add a local output path for daily reports
- Support a simple local demo mode
- Make missing Feishu config degrade gracefully
- Add clearer startup/config validation
- Keep environment variable overrides for secrets

Done when:

- A new user can run a local daily report without Feishu
- Failure cases are understandable without reading source code

### Phase 2: Publisher Abstraction

Objective:
Remove the Feishu-only bottleneck.

Tasks:

- Introduce a generic output/publisher layer
- Add Markdown output
- Add HTML output
- Keep Feishu support as one publisher among several
- Make outputs configurable

Done when:

- One run can emit both local files and Feishu output
- Adding a new publisher does not require rewriting the main pipeline

### Phase 3: Sharper Output Quality

Objective:
Make report quality and recommendation logic easier to trust.

Tasks:

- Surface score reason consistently
- Show matched keywords / reason tags where possible
- Make report structure easier to skim
- Improve explanation of why a paper was selected

Done when:

- Users can understand recommendation logic from the report itself

### Phase 4: Conference Monitoring as a Headline Feature

Objective:
Turn conference monitoring into a visible differentiator.

Tasks:

- Document source stability by venue
- Improve conference-only execution path
- Improve status output: published / not released / failed
- Add dedicated README section and screenshots

Done when:

- Conference monitoring can stand on its own as a product feature

### Phase 5: Research Profile Templates

Objective:
Make the system feel general-purpose rather than tied to one author profile.

Tasks:

- Add built-in profile presets
- Support profile selection from CLI
- Support custom profile files

Done when:

- New users can start from a preset instead of writing keywords from scratch

### Phase 6: Reliability and Trust

Objective:
Make long-term operation safe.

Tasks:

- Add parser fixture tests
- Add config validation tests
- Add dry-run and idempotency tests
- Improve logging and run summaries
- Add CI for the critical test suite

Done when:

- Core flows are covered by automated checks
- Re-runs are safe and diagnosable

### Phase 7: README and Launch Assets

Objective:
Convert functionality into adoption.

Tasks:

- Rewrite README first screen
- Add screenshots and animated demo assets
- Add example outputs for local file mode and Feishu mode
- Add a comparison table and quickstart path

Done when:

- Users can understand the project before reading deep documentation

### Phase 8: Launch and Community

Objective:
Drive adoption and contributions.

Tasks:

- Publish a polished release
- Prepare release notes and showcase examples
- Add issue templates and contributing guidance
- Gather feedback from public communities

Done when:

- External users can install, run, and open useful issues without hand-holding

## Execution Order

Recommended order:

1. Phase 1
2. Phase 2
3. Phase 7
4. Phase 6
5. Phase 4
6. Phase 5
7. Phase 8

Rationale:
Usability and presentation should improve before deeper expansion.

## Sprint Plan

### Sprint 1

Theme:
Create the first non-Feishu user path.

Tasks:

- Write this execution plan into the repo
- Add local Markdown output
- Introduce runtime output selection
- Keep Feishu write path intact
- Add targeted tests for local output

Done when:

- `--dry-run --output markdown` produces a local report file

### Sprint 2

Theme:
Generalize output and improve onboarding.

Tasks:

- Add HTML output
- Add config validation helpers
- Improve startup errors
- Update README quickstart for local mode

### Sprint 3

Theme:
Sharpen product presentation.

Tasks:

- Rewrite README first screen
- Add screenshots / GIF plan
- Improve report readability and explanation fields

### Sprint 4

Theme:
Stability and release.

Tasks:

- Expand tests around state, output, and parser behavior
- Add CI
- Prepare a first polished public release

## Immediate Implementation Slice

The first code slice should stay intentionally small:

1. Add `plan.md`
2. Add a local Markdown publisher
3. Add CLI support for output selection
4. Wire local output into the existing write flow
5. Add tests for the new local output path

This keeps momentum high without forcing a large refactor too early.
