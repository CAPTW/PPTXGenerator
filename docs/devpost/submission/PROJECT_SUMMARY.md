# 🌐 PPTX Generator — Project Summary

> [Submission hub](README.md) · [Documentation hub](../../README.md) · [Project README](../../../README.md) · [Final evidence](../evidence/phase7_final/)

> **PPTX Generator turns a prompt and local source documents into a polished, evidence-linked, editable PowerPoint deck and companion HTML presentation.**

---

## At a glance

| Input | Structured knowledge | Output | Release proof |
|---|---:|---:|---:|
| 1 prompt + 2 searchable PDFs | 3 sources + 29 Evidence Units | 6-slide PPTX + HTML | 4 full runs · 0 unexplained divergence |

## What makes it different

<table>
<tr>
<td width="33%"><b>📚 Evidence-linked</b><br/>Claims remain connected to source records and locators.</td>
<td width="33%"><b>✏️ Editable</b><br/>131 text objects and one table remain native; picture objects remain zero.</td>
<td width="33%"><b>🧪 Reproducible</b><br/>Historical Phase 7 passed 274/733 tests; the public snapshot passes its bounded 490-test suite.</td>
</tr>
</table>

## How the release works

```text
prompt + two PDFs
  → Source Corpus + Evidence Units
  → Presentation Architecture
  → frozen design-reference bundle
  → Semantic Sidecars + Visual Targets
  → editable PPTX + HTML
  → PowerPoint + Chromium QA
  → deterministic delivery package
```

## Image Generation boundary

The original platform-managed Phase 4 workflow executed Image Generation and recorded provenance and selected-image hashes. The release CLI validates and uses that frozen visual bundle; it does not invoke live Image Generation, require an API key, or claim an unexposed image-model identity.

## Dependency and fresh-clone proof

DeckCompiler owns the exact interpreter used by the external reconstruction scripts. The release lock contains 38 exact hash-bearing distributions, and six external Python entrypoints are pinned by source hash and exercised by preflight canaries.

Four independent runs completed 36/36 stages. Canonical-repeat, fresh-repeat, and canonical-fresh comparisons found zero unexplained semantic divergence.

The 274 focused and 733 full-suite results are immutable historical Phase 7
full-workspace evidence. The current release-minimal public snapshot carries a
separately verified 490-test suite.

## Current status

| Item | State |
|---|---|
| Technical gate | `ELIGIBLE_FOR_DEVPOST_SUBMISSION` |
| GitHub publication | Complete |
| Tag / GitHub Release | Not created |
| DevPost submission | Not yet submitted |
