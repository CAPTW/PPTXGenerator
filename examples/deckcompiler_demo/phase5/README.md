# DeckCompiler Phase 5.1 accepted reconstruction bundle

This directory is the curated, repository-local evidence bundle for the accepted
Phase 5.1 reconstruction of the six-slide DeckCompiler demo.

The bundle proves that the pinned external `CAPTW/pngtopptx` SkillSet produced an
editable PPTX and selectable-text HTML from a fresh Phase 5.1 handoff, that the
official final gate passed, and that independent package, render, semantic,
native-object, raster/crop, HTML, and provenance checks passed. It does not make
the deck final-release or DevPost-release eligible. Phase 6 composite visual QA
and release packaging remain required.

## Accepted outputs

- `outputs/pptx_generator_demo.pptx` — six-slide editable PowerPoint output.
- `outputs/html/index.html` — six-slide self-contained HTML output with native
  selectable text and a native table.
- `renders/slide-001.png` through `renders/slide-006.png` — canonical Microsoft
  PowerPoint COM renders used only as QA evidence, never as slide surfaces.

## Evidence map

- `handoff/` preserves the sanitized project-level handoff and observed crop
  artifact contract. The zero-crop plan has six ordered source records and the
  official producer output is the exact two-byte JSON object `{}`.
- `manifests/` binds reconstruction, native objects, crop coverage, PPTX objects,
  and HTML elements to the accepted outputs.
- `validation/` contains the official final-gate result and independent package,
  semantic, parity, render, HTML, and Phase 5 acceptance reports.
- `provenance/` preserves the official invocation record, the complete three-wave
  repair history, and pre/post equality fingerprints for the external SkillSet,
  Phase 4 bundle, and final handoff sources.
- `prior_failed_run_reference.json` records the earlier closed diagnostic run
  without curating or reusing any of its output bytes.

## Authority and restrictions

Phase 4 Semantic Sidecars remain the sole authority for copy, numbers, units,
table data, citations, and native/raster policy. Visual Targets remain design
references only. This bundle contains no full-slide picture, screenshot slide,
semantic raster, external network dependency, machine-specific absolute path,
external Skill source, rejected output, or protected historical output.

The bundle's JSON evidence and canonical HTML are raw-hash-bound. Repository
attributes disable EOL normalization for those exact paths so mixed official
source bytes survive checkout; PPTX and PNG retain the binary policy.

Do not use the rendered PNGs as slide backgrounds. Do not infer Phase 6 or final
release completion from `phase5_accepted=true`; the authoritative terminal state
here is `ELIGIBLE_FOR_COMPOSITE_QA` with `final_release_eligible=false` and
`phase6_required=true`.
