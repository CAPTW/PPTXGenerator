---
name: pptx-generator-workflow
description: "Run the live Codex prompt/PDF-to-editable-PPTX workflow after mandatory pptx-workflow-architect Gates 1 and 2. Use for any new deck production in this repository. It calls platform Image Generation for every approved slide, reconstructs the selected PNGs with the installed CAPTW/pngtopptx SkillSet, runs visual QA and repair waves, and seals a truthful final run manifest."
---

# PPTXGenerator Live Codex Workflow

## Mandatory first dependency

This Skill is never the first presentation Skill.

Before any action in this Skill:

1. Read `.agents/skills/pptx-workflow-architect/SKILL.md` completely and load
   the reference files it requires for the active Gate.
2. Follow its Gate 1 workflow-design contract.
3. Follow its Gate 2 blueprint and visual-system contract.
4. Confirm that the user approved the blueprint and visual route.

If the repository-owned dependency is missing or Gate 2 is not approved, stop.
Do not use an external Architect substitute, create images, run PNGtoPPTX, or
substitute the legacy fixed six-slide planner.

The repository/external dependency order is machine-readable in
`dependencies.json`. This Skill is the repository-specific production handoff
after Architect approval and replaces the Architect's generic PPTX handoff.

## Required companion Skills

After Architect approval, read these installed Skills completely before using
them:

1. `${CODEX_HOME}/skills/.system/imagegen/SKILL.md`
2. `${CODEX_HOME}/skills/slide-editable-deck-orchestrator/SKILL.md`
3. `${CODEX_HOME}/skills/slide-text-layer-inpaint/SKILL.md`
4. `${CODEX_HOME}/skills/slide-image-dual-render/SKILL.md`
5. `${CODEX_HOME}/skills/slide-visual-polish-qa/SKILL.md`

Follow any references those Skills mark as required for the active action.
Never copy or modify the external PNGtoPPTX Skill implementation in this
repository.

## Workflow

### 1. Create the runtime intake

Run `deckcompiler generate` with the user's prompt and PDFs. The command only
copies and fingerprints inputs and writes:

- `generate_workflow_manifest.json`
- `codex_dispatch.json`
- `CODEX_WORKFLOW.md`
- `skillset_execution_plan.json`
- an isolated `pngtopptx-project/` scaffold with an explicit empty
  `work/crop_plan.json`

The expected status is `AWAITING_WORKFLOW_ARCHITECT`. If the command enters
image generation or produces a PPTX, treat that as a contract violation.
The command must fail before intake when the repository Architect package,
ImageGen/PNGtoPPTX SkillSet, or any official required entrypoint is missing. The
generated execution plan binds all four tracked Architect files plus the exact
installed companion Skill and entrypoint hashes for the lifetime of the run.

### 2. Persist the approved Architect package

Write the approved artifacts under `<runtime>/architect/`:

- `workflow_design.json`
- `blueprint.json`
- `design_system.json`
- `approval_record.json`

The blueprint controls the slide count. It may contain 1–400 slides and must use
the smallest count that serves the communication goal. Each slide needs one
main message, actual on-slide copy, a named layout pattern, a visual direction,
evidence/asset requirements, and presenter-note intent.

The approval record must identify Gate 1 and Gate 2 as explicitly approved. Do
not infer approval from silence.

### 3. Build per-slide image requests

Create `<runtime>/image_requests/slide-NNN.prompt.json` and
`<runtime>/semantic_sidecars/slide-NNN.semantic.json` from the approved
blueprint and design system.

Every request must include:

- the slide's one-line takeaway and actual on-slide copy;
- the approved visual route, color/type/spatial tokens, and named layout;
- exact evidence-bound numbers, units, and labels;
- intended 16:9 composition and safe regions;
- consistency references to previously selected slides where useful;
- prohibitions against invented facts, pseudo-language, watermarks, logos, and
  unreadable microtext.

Semantic Sidecars remain the authority for exact editable text. Generated text
is visual reference evidence and must never silently become canonical through
OCR.

### 4. Execute platform Image Generation

Use the built-in `image_gen.imagegen` tool, not a repository placeholder or a
mock. Issue one call per slide or selected variant as required by the Image
Generation Skill.

For every slide:

1. Generate the 16:9 slide reference.
2. Inspect subject, hierarchy, composition, text accuracy, evidence integrity,
   design-system consistency, and forbidden elements.
3. Make a targeted regeneration when a check fails.
4. Save the selected image as `<runtime>/pngtopptx-project/src/slideN.png`.
5. Save an inspection report with `PASS` plus the regeneration count.

All selected source images must share a consistent 16:9 canvas. Normalize by
aspect-preserving crop or pad only when necessary; never stretch.

Do not proceed until every planned slide has a selected, inspected PNG and a
matching Semantic Sidecar.

### 5. Execute editable reconstruction

Use the installed `slide-editable-deck-orchestrator` Skill against
`<runtime>/pngtopptx-project`.

Do not treat the meta Skill name as the renderer. Follow the exact companion
sequence and commands in `skillset_execution_plan.json`:

1. record whether `slide-text-layer-inpaint` is executed or skipped with a
   concrete reason;
2. install project-local Node dependencies and install hardlock templates;
3. create `styles/active.json`, `lib/slides.js`, and isolated per-slide worker
   artifacts;
4. keep `work/crop_plan.json` explicit even when it contains zero crops, run
   crop preparation so `assets/manifest.json` exists, and do not use
   `--skip-crops` for final delivery;
5. run `slide-image-dual-render/scripts/slide_pipeline.js` with
   `--quality reconstruction --require-qa --require-reconstruction`, an
   explicit `--crop-plan`, and an explicit project-local `--node-path`;
6. run `slide-image-dual-render/scripts/final_gate.js` with PPTX openability;
7. run `slide-visual-polish-qa` against both PPTX rasters and HTML screenshots,
   using `--source-slides` for every selected wave;
8. create backlog and repair-wave plans through the orchestrator and repeat.

Production defaults:

- quality level: `polish`;
- minimum acceptable level: `blocking-zero`;
- no full-slide screenshot/background fallback;
- native editable semantic text and structured objects;
- route and reconstruction hardlocks enabled;
- PPTX openability required.
- exact official `slide-image-dual-render` render trace required;
- wave size at most 5 until the final `--allow-large-batch` assembly;
- project-local Node dependencies and explicit crop plan required.

Run the initial reconstruction, full-deck visual QA, backlog summary, repair
wave planning, repair builds, and source-mapped QA. Repeat until there are zero
fail/blocking slides or the Skill's iteration/failure policy stops the run.
Continue repair waves whenever the report still contains a fail or blocking
slide; an intermediate render is not a deliverable.

If the iteration cap is reached, report `NEEDS_REPAIR`; do not seal the run as
complete.

### 6. Seal and register the run

Create a draft `codex_pptx_generation_run` JSON using
`references/codex-run-contract.md`, then run:

```powershell
deckcompiler seal-codex-run `
  --draft <runtime>\codex_run.draft.json `
  --output <runtime>\codex_run.json

deckcompiler generate `
  --resume <runtime> `
  --codex-run-manifest <runtime>\codex_run.json
```

The sealer recomputes every referenced file hash. The resume command accepts
completion only when:

- `pptx-workflow-architect` is recorded as invocation order 1;
- Gate 1 and Gate 2 are approved;
- `image_gen.imagegen` has one accepted result per blueprint slide;
- selected slide references are real, consistently sized 16:9 PNGs rather than
  placeholder bytes;
- reconstruction hardlocks and PPTX openability pass;
- `skillset_execution_plan.json`, orchestration state, the official
  `slide-image-dual-render` render trace, crop plan/manifest, crop coverage, and
  objective QA evidence are all hash-bound to the run;
- the PPTX package slide count and actual-render native-object manifest match
  the approved blueprint, with editable text on every slide;
- the external visual-QA summary agrees with the sealed fail, blocking, and
  needs-polish counts;
- visual QA has zero fail/blocking slides;
- the delivered PPTX exists and its hash matches the reconstruction output.

## Final delivery

Deliver at least:

- final editable PPTX;
- final standalone HTML from the dual renderer;
- native-object/editability inventory;
- final visual QA summary;
- contact sheet;
- sealed `codex_run.json`.

State the actual quality level and remaining `needs_polish` count. Never describe
an intake-only, mocked, canary, or `NEEDS_REPAIR` run as a completed deck.
