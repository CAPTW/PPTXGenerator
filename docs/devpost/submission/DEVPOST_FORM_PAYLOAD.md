<div align="center">

# 📝 DevPost Form Payload

**Evidence-backed, copy-ready fields for the manual DevPost submission**

[Submission hub](README.md) · [Documentation hub](../../README.md) ·
[Project README](../../../README.md) ·
[Final evidence](../evidence/phase7_final/)

</div>

---

This document contains only fields confirmed by repository evidence. It is
copy-paste ready but has not been submitted.

> **Status:** `READY_FOR_MANUAL_SUBMISSION — NOT YET SUBMITTED`

## Project Name

PPTX Generator

## Elevator Pitch

PPTX Generator is an agentic presentation compiler that turns a prompt and local source documents into an evidence-linked, creatively planned, editable PowerPoint and HTML deck with deterministic QA and bounded upstream repair.

## About the Project

### Inspiration and problem

Many document-to-slide workflows optimize for appearance and quietly flatten
the result into screenshots. That makes the final deck difficult to edit and
separates claims from their sources. We wanted creative planning, native
PowerPoint editability, evidence linkage, and repeatable release proof in one
workflow.

### Product approach

PPTX Generator accepts a prompt and local source documents, converts them into
structured evidence and a presentation plan, and emits an editable PowerPoint
deck plus a companion HTML presentation. The canonical P0 is deliberately
bounded: one prompt plus exactly two text-searchable PDFs produces three
sources, 29 Evidence Units, and one six-slide deck.

The verified deck contains 131 editable text objects, one native table, zero
picture objects, and zero full-slide raster violations. Semantic, number/unit,
citation, source-binding, PowerPoint-render, Chromium-capture, parity, and
package checks are retained as machine-readable evidence.

### Architecture and build

`DeckCompiler` is the internal deterministic Python pipeline. Versioned JSON
Schema contracts connect Source Corpus and Evidence Units, Module–Batch–Slide
Presentation Architecture, design invariants, Creative Template Architecture,
Semantic Sidecars, Visual Targets, slot binding, editable reconstruction,
PPTX/HTML compilation, Composite QA, bounded repair, and release packaging.

The original platform-managed Phase 4 workflow executed Image Generation and
recorded provenance plus hashes for the selected design-reference artifacts.
The exact image-model identity was not exposed and is not claimed. The release
CLI validates and consumes that frozen visual bundle, performs no live Image
Generation, needs no API key, and reconstructs fresh editable PPTX and HTML
outputs.

The external CAPTW/pngtopptx four-SkillSet was not created during Build Week.
PPTX Generator pins and orchestrates it through a verified handoff and release
contract. DeckCompiler owns the exact interpreter and hash-locked package
closure used to invoke its external entrypoints; the external source remains
outside the repository and delivery ZIP.

### Challenges and controlled repair

The last fresh-clone dependency blocker was subtle: `pip check` passed, but an
external script imported NumPy directly through DeckCompiler's interpreter
while NumPy was absent from the release lock. Auditing the full execution graph
led to a versioned dependency manifest, 38 exact hash-bearing distributions,
isolated import preflight, and six entrypoint canaries.

A separate comparison exposed an absolute checkout locator inside a legacy
structural hash. Canonicalizing it to a filename made the proof
checkout-independent without changing presentation content.

The reliability evidence also includes a controlled off-canvas fault. The
detector rejected it, a bounded upstream repair restored the canonical owner in
one wave, and the immutable before/faulty/repaired proof confirms that final
PPTX bytes were not patched directly.

### Reproducibility and results

Four independent demo runs completed 36/36 stages. A physical
`--no-local --no-checkout` fresh clone of the historical Phase 7 full workspace
passed 274 focused and 733 full-suite tests. The current release-minimal public
snapshot carries a separately verified, bounded 490-test suite.
Canonical-repeat, fresh-repeat, and canonical-fresh comparisons reported zero
unexplained divergence. PowerPoint rendering and Chromium capture completed
6/6. The final gate passed 81/81 prerequisites and reports
`ELIGIBLE_FOR_DEVPOST_SUBMISSION`.

The certified fresh-clone environment used CPython 3.11.9 AMD64, Node.js
24.13.1, npm 11.11.0, PowerPoint 16.0 build 20131 x64, Playwright 1.61.0,
Chromium revision 1228, and Chrome for Testing 149.0.7827.55. A later
prerequisite recheck observed Node.js 24.14.0 and PowerPoint build 20228; those
later values are not the certified canonical-run environment.

### Existing, adapted, and new

Build Week work includes the Source Corpus and Evidence Unit contracts,
multi-source intake, Presentation Architecture integration, Module–Batch–Slide
planning, design invariants, Creative Template Architecture, Semantic
Sidecars, visual-bundle orchestration, the external handoff contract, Composite
QA, the controlled fault, bounded repair, dependency closure, the one-command
demo, packaging, physical fresh-clone verification, and DevPost release
evidence.

Existing ingestion, workflow planning, Creative Front-End planning,
editable-template concepts, QA concepts, and local runtime utilities were
adapted behind versioned or strict interfaces. The CAPTW/pngtopptx
four-SkillSet and third-party runtime dependencies remain existing external
components.

### What we learned

Dependency ownership follows the interpreter, not only the repository where a
script lives. A passing resolver does not prove direct imports are closed.
Reliable editable-slide generation needs semantic contracts, real renderers,
independent acceptance authority, immutable evidence, and a repair loop that
changes the upstream owner rather than patching final bytes.

### Limitations and status

This release proves one source-controlled six-slide P0, not arbitrary-volume
document ingestion. Scanned or image-only PDF OCR is unsupported. The prepared
machine requires Windows x64, PowerPoint, Chromium, and the pinned external
Skills. No Google Slides fidelity, arbitrary PNG-to-perfect-PPTX conversion,
arbitrary cross-platform PowerPoint fidelity, or unexposed model identity is
claimed. The release CLI does not rerun live Image Generation, and DevPost
submission is manual.

The candidate is technically eligible for DevPost submission. GitHub
publication, push, tag, release creation, and actual DevPost submission remain
unperformed and unauthorized.

## Built With

`python`, `powerpoint`, `html`, `document-automation`, `generative-ai`,
`openai`, `codex`, `image-generation`, `playwright`, `chromium`,
`json-schema`, `pymupdf`, `python-pptx`, `numpy`, `opencv`, `scikit-image`,
`reproducibility`, `design-systems`, `developer-tools`, `accessibility`

Tag count: 20.

OpenAI Codex was used for planning, orchestration, and review. Platform-managed
Image Generation produced the original frozen design references. The release
CLI does not call live Image Generation.

## Repository URL

`PENDING_GITHUB_PUBLICATION`

## Demo Video URL

`PENDING_DEMO_VIDEO`

## Try-It URL or Additional Links

`LOCAL_ONE_COMMAND_DEMO — SEE PUBLIC REPOSITORY RUNBOOK`

## Submission Status

`READY_FOR_MANUAL_SUBMISSION — NOT YET SUBMITTED`

## Fields to confirm in the live DevPost form

Confirm the current form's challenge/category selection, team-member fields,
media count and dimension limits, demo-video requirement, additional-link
fields, disclosure fields, and deadline/time-zone display. Do not populate or
submit those unverified live fields without separate authorization.
