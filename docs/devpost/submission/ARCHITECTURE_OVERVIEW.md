# Architecture Overview

PPTX Generator is the public product. `DeckCompiler` is its internal,
contract-driven Python pipeline. Each layer can be validated independently, so
content, design intent, editable reconstruction, and release evidence do not
collapse into one opaque generation step.

```text
one prompt + exactly two searchable PDFs
  -> Source Corpus (3 sources) + Evidence Unit registry (29 units)
  -> Presentation Architecture (3 modules / 3 batches / 6 slides)
  -> design invariants + Creative Template Architecture
  -> platform-generated, frozen design-reference bundle
  -> 6 Semantic Sidecars + 6 Visual Targets
  -> slot binding + pinned external editable reconstruction
  -> editable PPTX + companion HTML
  -> PowerPoint render + Chromium capture
  -> semantic, source, editability, raster, parity, and visual QA
  -> controlled-fault evidence + bounded upstream repair
  -> deterministic package + final release gate
```

## Key boundaries

- Real slide copy is authored as editable PowerPoint and HTML text, not OCR
  output from a generated reference image.
- The native table, cards, panels, dividers, captions, and frames remain
  editable or vector-based wherever the contract requires it.
- The original platform-managed Phase 4 workflow executed Image Generation and
  recorded provenance and selected-image hashes. The image-model identity was
  not exposed and is not claimed.
- The release CLI validates and consumes the frozen verified visual bundle. It
  performs no live Image Generation, needs no API key, and never treats a
  design reference as a full-slide final screenshot.
- The external CAPTW/pngtopptx four-SkillSet was not created during Build Week.
  PPTX Generator pins and orchestrates it through a verified handoff and
  release contract.
- DeckCompiler owns the `sys.executable` passed to external Python scripts and
  therefore owns the exact 38-distribution package closure for that
  interpreter.
- JSON Schemas, content hashes, structural fingerprints, real renderers, and a
  clean-tree final gate make failure and reproducibility reviewable.

The future Local Model path can make bounded JSON decisions against locked
design assets while deterministic code retains control of compilation and
validation. It is a compatibility direction, not a claim that the current P0
is model-agnostic or generally cross-platform.
