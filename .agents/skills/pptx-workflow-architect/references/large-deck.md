# Large Deck Architecture Reference

## Table of Contents
1. [Scale Mode Detection](#scale-mode-detection)
2. [Deck Hierarchy](#deck-hierarchy)
3. [Deck Constitution](#deck-constitution)
4. [Slide Ledger](#slide-ledger)
5. [Batch Manifest & Modular Production](#batch-manifest--modular-production)
6. [Context Lock & Handoff](#context-lock--handoff)
7. [Navigation for Long Decks](#navigation-for-long-decks)
8. [Main Story vs Appendix](#main-story-vs-appendix)
9. [Anti-Drift Rules](#anti-drift-rules)
10. [Right-Sized Deck Planning](#right-sized-deck-planning)

---

## Scale Mode Detection

Choose a mode based on scope, complexity, and safe response/context limits — not only raw slide count.

| Mode | When to Use |
|------|------------|
| Compact Deck | Simple topic, <10 slides, low complexity |
| Standard Deck | Moderate scope, 10–25 slides |
| Extended Deck | Multi-section, 25–60 slides |
| Large-Deck | Complex multi-part, 60–150 slides |
| Mega-Deck | Comprehensive reference, 150–400 slides |

**Hard ceiling: 400 slides.** This is never a default target. Always recommend the smallest count that fully serves the user's goal.

---

## Deck Hierarchy

When one-pass generation is risky, use hierarchical architecture:

```
Deck → Part → Section → Slide Cluster → Slide
```

| Level | Definition |
|-------|-----------|
| Deck | The whole presentation |
| Part | Major macro-unit |
| Section | Coherent theme block within a Part |
| Slide Cluster | Small group of slides that work together |
| Slide | Individual page |

Large decks must not be planned as a flat list only. Use narrative boundaries first, numerical batching second. Prefer cuts at section or cluster boundaries.

---

## Deck Constitution

Before producing a medium, large, or multi-batch deck, create a persistent Deck Constitution — the single source of truth.

### Required Fields

| Category | Items |
|----------|-------|
| Strategy | Deck objective, audience definition, delivery mode, message spine, narrative promise |
| Structure | Section logic, appendix boundary, numbering rules, navigation rules |
| Language | Terminology glossary, title-writing rules, tone and voice |
| Visual | Approved visual route, design tokens, layout library, infographic rules, chart/table rules, screenshot treatment, icon style, section-divider logic |
| Evidence | Evidence policy, source handling |
| Motifs | Recurring motifs (if any) |

### Rules
- Later batches **must inherit** the Deck Constitution
- No drift allowed unless explicitly revised
- If a locked decision changes, issue a **Continuity Update Notice**

---

## Slide Ledger

Maintain a Slide Ledger for the full deck when scale is non-trivial. Mandatory for large decks.

### Tracked Fields

| Field | Description |
|-------|-------------|
| Slide number | Current numbering |
| Working title | Draft title |
| Final title status | Locked / Draft |
| Part / Section | Location in hierarchy |
| Slide role | Function of this slide |
| One-line takeaway | Core message |
| Layout pattern | From layout library |
| Visual type | Chart / diagram / infographic / text |
| Dependency | Earlier slides this depends on |
| Required evidence | Data / sources needed |
| Required asset | Images / icons needed |
| Production status | Not started / In progress / Complete |
| QA status | Not checked / Passed / Issues found |

Update whenever slides are inserted, revised, removed, or renumbered.

---

## Batch Manifest & Modular Production

When one-pass production is unsafe or low quality, create a Batch Manifest automatically.

### Per Batch Define

| Field | Content |
|-------|---------|
| Batch name | Descriptive name |
| Deck mode | Scale mode |
| Covered slide range | Slide numbers |
| Covered Part/Section/Cluster | Structural location |
| Batch objective | What this batch accomplishes |
| Continuity inputs needed | What must be inherited |
| Key dependencies | Prior slides/decisions required |
| Assets needed | Images, data, icons |
| Risks | What could go wrong |
| Expected output scope | What will be delivered |

### Rules
- Batch by logic first, page count second
- Prefer section-based or cluster-based batching
- Do not ask the user to manually solve batching unless they explicitly want to
- The system manages modular production proactively

### Fast-quality execution batches

Logical content batches do not require serial Image Generation. Under the
repository `fast-quality-20` profile, prepare the whole wave first and dispatch
up to 20 independent built-in ImageGen calls concurrently. For exactly 20
slides, all initial calls belong to one wave. For larger decks, use deterministic
waves of 20 while preserving the Deck Constitution. After all approved source
images exist, prepare one hash-bound reconstruction job per slide. Execute each
job in a fresh one-slide context with at most four workers active, then use the
official PNGtoPPTX validator and integrator to merge their isolated fragments.
This preserves local visual detail without repeating the full-deck context in
every worker. After all jobs pass, compile all approved slides in one
`--allow-large-batch` renderer invocation. Repair waves remain targeted and may
be smaller.

### Context-Limit Aware Generation
If generating the entire deck in one pass risks truncation or coherence loss:
- Automatically split production into smaller units
- Split first by Part / Section / Slide Cluster
- Split by raw page count only when needed
- Never push beyond a safe quality threshold just to cover more slides
- **Quality and continuity > volume per response**

---

## Context Lock & Handoff

Every production batch must begin with a **Context Lock** and end with a **Handoff Packet** + **State Capsule**.

### Context Lock

| Field | Content |
|-------|---------|
| Approved deck objective | |
| Approved message spine | |
| Approved visual route | |
| Locked design rules | |
| Active section | |
| Numbering range | |
| Terminology rules | |
| Unresolved risks | |

### Handoff Packet

| Field | Content |
|-------|---------|
| What was produced | |
| Slide ranges completed | |
| Unresolved issues | |
| Continuity-sensitive decisions | |
| Numbering updates | |
| Remaining assets needed | |
| Remaining verification items | |
| Next recommended batch | |

### State Capsule

| Field | Content |
|-------|---------|
| Deck title | |
| Approved workflow | |
| Approved visual route | |
| Locked design system | |
| Completed ranges | |
| Total planned range | |
| Open issues | |
| Next recommended range | |
| Continuity warnings | |

Mandatory for multi-batch generation.

---

## Navigation for Long Decks

Long decks must feel navigable. Use these elements when appropriate:

- **Section dividers** — clear visual break between major parts
- **Recurring navigation cues** — consistent position indicators
- **Transition slides** — bridge between sections
- **Recap slides** — summarize what was covered
- **Roadmap refresh slides** — show progress through the deck
- **Synthesis slides** — connect multiple sections
- **Summary checkpoints** — periodic consolidation

Make it obvious: where the audience is, why this section matters, how the next section connects.

---

## Main Story vs Appendix

Do not treat all material as equally important.

**Main story** = the communication thread the audience experiences live

**Separate into appendix/backup:**
- Detailed methodology
- Full reference lists
- Granular evidence tables
- Extra examples
- Technical backup
- Raw data

Keep the main communication thread leaner than the full research archive.

---

## Anti-Drift Rules

The following are **prohibited** in long or multi-batch decks:

- Redesigning style midstream without notice
- Arbitrary changes in title style
- Changing terminology for the same concept
- Changing icon or chart logic without reason
- Losing section hierarchy
- Duplicate slides from batch overlap
- Contradiction between earlier and later slides
- Unexplained shifts in narrative stance

If drift is detected, correct it before considering the deck complete.

### User Communication for Batched Production

Frame modular production positively:
- "This deck is being produced in controlled batches to preserve continuity and design quality."
- "The global blueprint and design system remain locked across all batches."
- "Next recommended unit: [range / section name]."

Do not present modular production as a failure.

---

## Right-Sized Deck Planning

Before production, estimate the optimal slide-count range based on:

| Factor | Consideration |
|--------|--------------|
| Audience | Executive → fewer slides; Reference reader → more depth OK |
| Purpose | Decision → lean; Training → comprehensive |
| Delivery mode | Live → leaner; Self-study → fuller |
| Speaking time | 1 slide per 1–2 min for live delivery |
| Required depth | Shallow overview vs deep analysis |
| Evidence density | How much data must be shown |
| Appendix needs | What can be moved to backup |

Do not create bloated decks for short presentations. Live presentations should stay leaner than deep reference decks.
