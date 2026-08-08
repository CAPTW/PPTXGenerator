---
name: pptx-generator-workflow
description: "Run the live Codex prompt/PDF-to-editable-PPTX workflow after mandatory pptx-workflow-architect Gates 1 and 2. Use for any new deck production in this repository. Its fast-quality-20 profile dispatches platform Image Generation in concurrent waves of 20, reconstructs all accepted PNGs in one full-deck CAPTW/pngtopptx compile, runs source-mapped visual QA, repairs only blockers, and seals truthful execution and timing evidence."
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
the smallest count that serves the communication goal. Each slide needs a
coherent purpose, actual on-slide copy, a named or justified custom layout, a
visual direction, evidence/asset requirements, and presenter-note intent. Do
not impose a one-message or fixed element-count rule that the user did not ask
for.

The approval record must identify Gate 1 and Gate 2 as explicitly approved. Do
not infer approval from silence.

Use the compact runtime contract required by the deterministic request adapter:

- `blueprint.json`: `deck_title`, `audience`,
  `approved_visual_route_id`, and ordered `slides`;
- each slide: `slide_number`, stable `slide_id`, `purpose`, `title`, exact
  `on_slide_copy`, `layout_id`, `visual_direction`, `evidence_refs`, and
  `presenter_notes`;
- `design_system.json`: concise `global_prompt_cues`, `visual_routes` keyed by
  `route_id`, and `layouts` keyed by `layout_id`, with short `prompt_cues` on
  each selected route/layout.

Keep the full planning intelligence in the approved Architect package, but keep
the prompt cues concise. Do not paste source PDFs or the entire Design System
into every slide request.

### 3. Build per-slide image requests

Run this exactly once after the approved files exist:

```powershell
deckcompiler prepare-image-requests --runtime <runtime>
```

This deterministic adapter creates every
`<runtime>/image_requests/slide-NNN.prompt.json`, matching Semantic Sidecar, and
`image_requests/image_request_manifest.json` from the approved Blueprint and
Design System. It performs no model call. Do not ask Codex or another model to
rewrite, summarize, or independently recreate the prompts after this step.

The default design direction is **Academic, Informative, Professional & Creative
Design**. Treat it as four broad qualities, not a rigid prompt checklist. Every
request should concisely include:

- the slide purpose, content, audience, and any evidence-bound facts that must
  be represented accurately;
- the approved visual route and only the design tokens materially useful to
  this image;
- a 16:9 presentation-slide composition and useful continuity cues;
- the four default qualities above unless the approved user route overrides
  them.

Preserve user direction and let ImageGen choose a natural composition. Do not
inject blanket bans on body copy, dense tables, small meaningful labels,
dashboards, card walls, or poster-style infographics. Do not impose a hard
three-element maximum or mandatory three-second test. Reject invented facts and
watermarks, but avoid long negative-prompt lists that crowd out the creative
brief.

Default base prompt (append the approved slide-specific content and route):

```text
Create a 16:9 presentation-slide design reference for the supplied purpose,
audience, and content. The design should be Academic, Informative, Professional
and Creative. Follow the approved deck visual system, represent supplied facts
faithfully, and choose the composition, hierarchy, density, and visual devices
that best fit this slide. Keep the result coherent with the rest of the deck.
```

This base is intentionally short. Add only constraints required by the user,
evidence, brand, accessibility, or the approved route.

Semantic Sidecars remain the authority for exact editable text. Generated text
is visual reference evidence and must never silently become canonical through
OCR.

### 4. Execute platform Image Generation

Use the built-in `image_gen.imagegen` tool, not a repository placeholder, CLI
fallback, or mock. The platform contract still requires one independent call
per slide or selected variant; concurrency does not turn 20 slides into one
multi-image API call.

Use the `fast-quality-20` dispatch profile:

1. Validate the prepared request manifest, then load every Prompt and Semantic
   Sidecar in the wave before calling the image tool.
2. Dispatch up to 20 independent initial `image_gen.imagegen` calls as one
   concurrent wave. A 20-slide deck is one 20-call wave with no serial canary.
3. Inspect every result for content/evidence integrity, composition,
   continuity, and usability as an editable-reconstruction reference.
4. Retry only a slide that fails inspection, at most once. Never restart
   already accepted calls. If the retry still fails, stop that slide as a real
   blocker instead of lowering the acceptance standard.
5. Save each accepted image as
   `<runtime>/pngtopptx-project/src/slideN.png` and its per-slide PASS report.
6. Write `<runtime>/image_batches/image_generation_batch_manifest.json` with
   deterministic wave membership, one call record per slide, attempt counts,
   accepted coverage, request ID, prepared Prompt SHA-256, and selected PNG
   SHA-256.

All selected source images must share a consistent 16:9 canvas. Normalize by
aspect-preserving crop or pad only when necessary; never stretch.

Do not compile until every planned slide has a selected, inspected PNG, a
matching Semantic Sidecar, and a complete batch-manifest record.

### 5. Execute editable reconstruction

Use the installed `slide-editable-deck-orchestrator` Skill against
`<runtime>/pngtopptx-project`.

Do not treat the meta Skill name as the renderer. Follow the exact companion
sequence and commands in `skillset_execution_plan.json`:

1. record whether `slide-text-layer-inpaint` is executed or skipped with a
   concrete reason;
2. install project-local Node dependencies once with npm's verified local cache
   preferred and audit/fund network chatter disabled, then install hardlock
   templates;
3. after all selected PNGs and the batch manifest exist, run
   `deckcompiler prepare-reconstruction-jobs --runtime <runtime>`. This creates
   one hash-bound job and compact worker prompt per slide under
   `work/slideXX/`;
4. execute each job in a fresh context that can see only one source slide, its
   job, Semantic Sidecar, and the canonical renderer Skill. Combine profile
   mapping and reconstruction in that one context to avoid duplicate model
   passes. Use no more than four workers concurrently. Each worker writes only
   its assigned `work/slideXX/` artifacts and performs isolated PPTX/HTML QA.
   Keep those images under `work/slideXX/worker_qa/` so the later full-deck
   source-mapped `visual_qa/` capture cannot invalidate their evidence hashes;
5. run `deckcompiler validate-reconstruction-jobs --require-worker-outputs`,
   then the official `validate_agent_work.js`. Reject stale source hashes,
   incomplete measurements, generic or backend-branched fragments, missing QA
   evidence, and receipts that edited shared files;
6. run the official `integrate_subagent_work.js` with `WORK_DIR`, `SLIDES_OUT`,
   `CROP_PLAN_OUT`, and `INTEGRATION_REPORT_OUT` from the execution plan. The
   integrator is the only writer of `lib/slides.js` and the integrated crop
   plan; parallel workers must never edit shared renderer files;
7. keep `work/crop_plan.json` explicit even when it contains zero crops, run
   crop preparation so `assets/manifest.json` exists, and do not use
   `--skip-crops` for final delivery;
8. after all ImageGen references and validated integration artifacts are ready,
   run one
   all-slide
   `slide-image-dual-render/scripts/slide_pipeline.js` build with
   `--quality reconstruction --require-qa --require-reconstruction`, an
   explicit `--crop-plan`, an explicit project-local `--node-path`, and
   `--allow-large-batch`, writing directly to `deck-final-editable.pptx` and
   `deck-final-editable.html`;
9. run `slide-image-dual-render/scripts/final_gate.js` with PPTX openability;
10. run all five `slide-visual-polish-qa` steps once against that full-deck
   PPTX/HTML, using `--source-slides`;
11. run `deckcompiler validate-visual-quality` against the official summary.
   Only `palette_drift` and `pptx_html_edge_mismatch` may remain as accepted
   noticeable native-renderer diagnostics. Spacing, hierarchy, typography,
   clipping, missing content, and meaningful-detail loss require repair;
12. when fail/blocking counts are zero and the high-fidelity policy accepts the
   result, take the single-compile fast path and do
   not repeat the all-slide build or QA merely to rename it "final"; run
   `fast_path_acceptance` to enforce the orchestration state;
13. only when blockers exist, create targeted repair-wave plans, rebuild and QA
   waves of at most five slides, for at most two iterations;
14. after any repair, run one conditional all-slide compile, final gate, and
    full-deck QA so delivered capture metadata names and hash-binds the repaired
    PPTX/HTML.

Production defaults:

- quality level: `polish`;
- minimum acceptable level: `blocking-zero`;
- no full-slide screenshot/background fallback;
- native editable semantic text and structured objects;
- route and reconstruction hardlocks enabled;
- PPTX openability required.
- exact official `slide-image-dual-render` render trace required;
- initial ImageGen wave size 20 with concurrent dispatch;
- one source slide per fresh reconstruction context, with at most four workers
  active and no full-deck context duplicated into worker prompts;
- official worker validation and integration scripts required before compile;
- one full-deck `--allow-large-batch` compile on the normal path;
- repair wave size at most 5, with a single conditional post-repair full-deck
  recompile;
- maximum repair iterations 2;
- project-local Node dependencies and explicit crop plan required.

Run the full-deck reconstruction and source-mapped QA once. Continue into the
repair path only when the report contains a fail or blocking slide; an
intermediate repair-wave render is not a deliverable. The time optimization
must never weaken hardlocks, openability, native editability, evidence binding,
or the zero fail/blocking completion gate.

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
- the deterministic Image Request Manifest matches the current Blueprint,
  Design System, approval record, every Prompt, and every Semantic Sidecar;
- `image_gen.imagegen` has one accepted result per blueprint slide;
- the Image Generation batch manifest proves deterministic waves of at most 20,
  concurrent-wave dispatch, exactly one initial built-in call per slide, and no
  more than one targeted regeneration per slide;
- selected slide references are real, consistently sized 16:9 PNGs rather than
  placeholder bytes;
- every selected image is bound to exactly one isolated reconstruction job,
  worker receipt, official integration report, and generated shared
  `lib/slides.js` output;
- reconstruction hardlocks and PPTX openability pass;
- `skillset_execution_plan.json`, orchestration state, the official
  `slide-image-dual-render` render trace, crop plan/manifest, crop coverage, and
  objective QA evidence are all hash-bound to the run;
- the PPTX package slide count and actual-render native-object manifest match
  the approved blueprint, with editable text on every slide;
- the external visual-QA summary agrees with the sealed fail, blocking, and
  needs-polish counts;
- visual QA has zero fail/blocking slides and the high-fidelity issue policy
  rejects any content, layout, hierarchy, typography, clipping, or detail-loss
  drift;
- `execution_timing.json` truthfully records the fast-quality-20 timings and
  full-deck compile count; a zero-repair run must record exactly one full-deck
  compile;
- the delivered PPTX exists and its hash matches the reconstruction output.

## Final delivery

Deliver at least:

- final editable PPTX;
- final standalone HTML from the dual renderer;
- native-object/editability inventory;
- final visual QA JSON and Markdown summaries;
- contact sheet;
- Image Generation batch manifest;
- reconstruction job manifest and official integration report;
- execution timing report;
- sealed `codex_run.json`.

State the actual quality level and remaining `needs_polish` count. Never describe
an intake-only, mocked, canary, or `NEEDS_REPAIR` run as a completed deck.
