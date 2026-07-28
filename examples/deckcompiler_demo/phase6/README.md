# DeckCompiler Phase 6 evidence

This directory contains the compact, hash-bound evidence for Phase 6. The active output set remains the immutable Phase 5 baseline; no PPTX, HTML, failed runtime, external Skill source, or protected historical output is duplicated here.

Phase 6A independently recomputes semantic fidelity, source coverage, creative intent, native editability, package/render integrity, deterministic visual geometry, raster/crop policy, and PPTX/HTML parity. The six-slide contact sheet was built from fresh Microsoft PowerPoint COM 16.0 renders at 1920×1080.

The official `slide-visual-polish-qa` comparator is retained as evidence and has no acceptance authority. Its metric-only 4 fail / 2 needs-polish result is adjudicated under rule `P6-VIS-EXT-PIXEL-DELTA-001`: all reviewed raster hashes match the fresh renders, semantic and native coverage remain 100%, deterministic clipping/off-canvas/overlap gates pass, and the model-assisted review finds no material Visual Target intent failure.

Phase 6.1B adds a deterministic off-canvas fixture and an actual Composite
detection report. The compact `detection/` pair is official current-output HTML
screenshot evidence for slide 1, labeled baseline and faulty; it is negative
test evidence, not a canonical product slide. The full faulty PPTX/HTML and the
complete runtime render/screenshot sets remain outside Git.

Phase 6.1C repair and unified-release evidence is added only after the focused
controlled-detection commit leaves a clean worktree. The active product output
continues to be `phase5_baseline`.

Phase 6.1C is now closed. `repair/` contains the hash-bound plan, deterministic
27-class invalidation, one-wave history, three-state manifest, and the only
curated before/faulty/repaired contact sheet. `repaired_qa/` contains compact
current-output bindings; `release/` contains the unified gate and Phase 6
acceptance. `screenshot_evidence/` contains path-sanitized baseline, fault, and
repaired capture summaries plus the contract audit.

The terminal status is `ELIGIBLE_FOR_PACKAGING`, not final or DevPost release.
The repaired PPTX/HTML and full visual evidence sets remain outside Git, the
active product output stays `phase5_baseline`, and Phase 7 is required but was
not started.
