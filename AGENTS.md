# PPTXGenerator Agent Instructions

## Presentation-generation dispatch invariant

For every request whose intended output is a new presentation, slide deck, or
editable PPTX, the first presentation Skill must be the installed
`pptx-workflow-architect` Skill. This applies regardless of:

- whether the user supplies an inline prompt, prompt file, PDF, multiple PDFs,
  notes, an outline, or only a topic;
- whether the user says "presentation", "deck", "slides", "PPT", or describes
  the deliverable indirectly;
- whether the request enters through chat or `deckcompiler generate`.

Before planning, generating images, running repository production code, or
invoking PNGtoPPTX:

1. Read and follow
   `${CODEX_HOME}/skills/pptx-workflow-architect/SKILL.md`.
2. Complete its mandatory Gate 1 workflow design.
3. Complete its Gate 2 blueprint and visual-system design.
4. Obtain the approval required by that Skill. A user request such as "just do
   it" may compress Gates 1 and 2, but must not silently bypass approval.
5. Only then read and follow
   `.agents/skills/pptx-generator-workflow/SKILL.md` for production.

If `pptx-workflow-architect` is unavailable, stop with a missing-dependency
status. Do not substitute a fixed six-slide template or heuristic planner.

Reading, extracting, or reviewing an existing PPTX without producing a new deck
is outside this dispatch rule.

## Production invariants

- `deckcompiler generate` is an intake and Codex-dispatch control plane. It must
  not claim that repository Python invoked a platform-managed Image Generation
  tool.
- The live Codex production path must call `image_gen.imagegen` for the selected
  slide visual for every planned slide.
- The live reconstruction path must use the installed
  `slide-editable-deck-orchestrator` and its companion Skills.
- The companion path is explicit: record the conditional
  `slide-text-layer-inpaint` decision, render only through
  `slide-image-dual-render/scripts/slide_pipeline.js`, gate with its
  `final_gate.js`, and run `slide-visual-polish-qa` with source-slide mapping.
- Follow the hash-bound `skillset_execution_plan.json`; use project-local Node
  dependencies, an explicit crop plan and generated asset manifest, waves of at
  most five slides, renderer quality `reconstruction`, and QA mode `qa-polish`.
- Do not use `--skip-crops` for final delivery. A zero-crop deck still carries
  `work/crop_plan.json` and `assets/manifest.json`.
- Production acceptance requires route hardlock, reconstruction hardlock, PPTX
  openability, and zero fail/blocking slides in visual QA.
- Preserve editable native text, tables, charts, diagrams, and shapes. A
  generated full-slide PNG is a reconstruction reference, never the final slide
  background or final semantic surface.
- Do not force a fixed slide count or a fixed decision-brief narrative onto
  arbitrary prompts. Slide count and story architecture come from the approved
  Architect blueprint.
- Do not mock Image Generation, PNGtoPPTX reconstruction, or visual QA and call
  the result an end-to-end quality test.
