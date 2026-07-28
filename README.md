# PPTX Generator

PPTX Generator is an agentic presentation compiler that turns a prompt and
local source documents into an evidence-linked, creatively planned, editable
PowerPoint and HTML deck with deterministic QA and bounded upstream repair.
`DeckCompiler` is the internal architecture and Python namespace.

## Release candidate

The canonical DevPost P0 accepts one prompt plus exactly two text-searchable
PDFs. It creates a three-source corpus, 29 Evidence Units, a six-slide
Presentation Architecture, six Semantic Sidecars, and six Visual Targets before
reconstructing editable PPTX and HTML outputs.

The verified six-slide deck contains 131 editable text objects, one native
table, zero picture objects, and zero full-slide raster violations. PowerPoint
rendering, Chromium capture, Composite QA, deterministic packaging, controlled
fault detection, one-wave upstream repair evidence, and physical fresh-clone
reproduction are included in the release evidence.

Technical status is `ELIGIBLE_FOR_DEVPOST_SUBMISSION`. This repository is a
release-minimal, single-commit public snapshot; it is not the full development
history. No tag, GitHub Release, or DevPost submission is included.

See [`PUBLICATION_BOUNDARY.md`](PUBLICATION_BOUNDARY.md) for the exact inclusion,
omission, external-dependency, and license boundaries of this snapshot.

## Image Generation boundary

The original platform-managed Phase 4 workflow executed Image Generation and
recorded provenance plus hashes for the selected design-reference artifacts.
The exact image-model identity was not exposed and is not claimed.

The reproducible release demo validates and consumes that frozen visual bundle.
It does not call live Image Generation, needs no API key, and does not use
generated images as full-slide final output. Real slide copy, tables, cards,
captions, and layout remain editable PowerPoint or HTML content.

## Run the canonical demo

Use the prepared Windows x64 environment described in
[`docs/devpost/PHASE_07_DEPENDENCY_AND_RUNTIME_GUIDE.md`](docs/devpost/PHASE_07_DEPENDENCY_AND_RUNTIME_GUIDE.md).
Create the virtual environment and output directory outside the clone.

```powershell
python -m venv <venv-outside-clone>
<venv-outside-clone>\Scripts\python.exe -m pip install --require-hashes -r requirements/devpost-release.lock.txt
<venv-outside-clone>\Scripts\python.exe -B -m presentation_agent.deckcompiler demo `
  --config examples/deckcompiler_demo/demo.yaml `
  --output-dir <new-empty-output-directory-outside-repo>
```

The certified fresh-clone environment used CPython 3.11.9 AMD64, Node.js
24.13.1, npm 11.11.0, PowerPoint 16.0 build 20131 x64, Playwright 1.61.0,
Chromium revision 1228, and Chrome for Testing 149.0.7827.55. A later
prerequisite recheck observed Node.js 24.14.0 and PowerPoint build 20228; those
later values are not the certified canonical-run environment.

See the
[`demo runbook`](docs/devpost/PHASE_07_DEMO_RUNBOOK.md),
[`submission documents`](docs/devpost/submission/),
[`known limitations`](docs/devpost/submission/KNOWN_LIMITATIONS.md), and
[`final release gate`](docs/devpost/evidence/phase7_final/final_release_gate.json).

## Existing, adapted, and new

Build Week work includes the Source Corpus and Evidence Unit contracts,
Presentation Architecture integration, Semantic Sidecars, visual-bundle
orchestration, external handoff contracts, Composite QA, bounded repair,
dependency closure, the one-command demo, packaging, and fresh-clone release
evidence. Existing ingestion, planning, creative-planning, editable-template,
QA, and local-runtime surfaces were used only through documented adaptations.

The external CAPTW/pngtopptx four-SkillSet was not created during Build Week.
PPTX Generator pins and orchestrates it through a verified handoff and release
contract. Its source is not vendored or redistributed.

## Scope limits

- The canonical proof covers one source-controlled six-slide demo, not
  arbitrary-volume ingestion or every document and template.
- Scanned or image-only PDF OCR is unsupported.
- Microsoft PowerPoint, Chromium, and the pinned external Skills are
  prepared-machine prerequisites.
- Windows x64 is the certified profile. No arbitrary cross-platform PowerPoint
  fidelity or Google Slides fidelity claim is made.
- The project does not claim arbitrary PNG-to-perfect-PPTX conversion.
- DevPost submission is manual and remains unperformed.

Third-party dependency and redistribution boundaries are documented in
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md). Files in this published
snapshot are provided under the
[`Apache License 2.0`](LICENSE) unless a file or third-party notice states
otherwise.
