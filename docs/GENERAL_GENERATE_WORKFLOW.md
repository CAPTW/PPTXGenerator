# Architect-First Prompt and PDF Workflow

The general workflow is a live Codex workflow. Repository Python owns immutable
input capture and evidence validation; Codex owns the platform-managed Skill and
tool calls.

The mandatory order is:

```text
pptx-workflow-architect
  -> approved Gate 1 and Gate 2
  -> imagegen / 20-call concurrent waves
  -> slide-editable-deck-orchestrator
  -> slide-text-layer-inpaint decision (execute or skip with reason)
  -> one fresh slide-image-dual-render context per source PNG (max 4 concurrent)
  -> official worker validation and integrator-only fragment merge
  -> one all-slide slide-image-dual-render hardlocked compile
  -> one full-deck slide-visual-polish-qa pass with source-slide mapping
  -> repository high-fidelity issue acceptance
  -> blocker-only repair waves and conditional recompile
  -> sealed editable-PPTX delivery
```

This order applies regardless of how the presentation request is phrased or
whether the input is an inline prompt, prompt file, PDF, multiple PDFs, notes,
outline, or topic.

## 1. Capture the request

Choose a new empty runtime directory outside the repository:

```powershell
deckcompiler generate `
  --output-dir C:\runs\quarterly-risk-deck `
  --prompt "Create the best presentation for this material." `
  --pdf C:\sources\operations.pdf `
  --pdf C:\sources\risk-review.pdf `
  --audience "executive leadership" `
  --purpose "investment decision" `
  --language English `
  --tone concise `
  --workflow auto
```

Use `--prompt-file` instead of `--prompt` for UTF-8 text. `--workflow` is only a
user hint; it does not select a fixed narrative template.

The command first verifies the tracked repository Architect package, installed
ImageGen/PNGtoPPTX Skills, and their official entrypoints. It then copies and
fingerprints inputs, creates
the isolated `pngtopptx-project` layout with an explicit empty crop plan, writes
`codex_dispatch.json`, `CODEX_WORKFLOW.md`, and the hash-bound
`skillset_execution_plan.json`, and exits with code `2`:

```text
status=AWAITING_WORKFLOW_ARCHITECT
action=INVOKE_PPTX_WORKFLOW_ARCHITECT
```

It does not run the legacy fixed six-slide planner, generate images, or produce
a PPTX. Missing tracked Architect files, missing external companions, or changed
hashes fail closed. Pass `--skill-root` only to name a verified non-default
ImageGen/PNGtoPPTX installation root; it cannot replace the Repo Architect.

## 2. Run the mandatory Architect gates in Codex

Codex must first read:

```text
.agents/skills/pptx-workflow-architect/SKILL.md
```

The complete tracked package also contains `references/design-system.md`,
`references/large-deck.md`, and `references/production-qa.md`. Codex loads each
reference when the Architect Skill marks it required for the active Gate. After
Gate 2 approval, this repository hands off to
`.agents/skills/pptx-generator-workflow/SKILL.md` instead of the Architect's
generic standard-PPTX production handoff.

Gate 1 diagnoses the presentation and offers workflow options. Gate 2 produces
the communication blueprint and visual system. Production starts only after the
approval required by that Skill.

If the user says "just do it," Gates 1 and 2 may be compressed into a concise
proposal, but approval is still required.

The Architect blueprint chooses a right-sized slide count from 1–400. The
general workflow does not force six slides or a decision-brief story.

After approval, persist the compact Architect runtime package and run:

```powershell
deckcompiler prepare-image-requests --runtime <runtime>
```

This is a single deterministic transformation, not another LLM pass. It creates
all slide Prompts and Semantic Sidecars together, binds each one to the current
Blueprint entry, Design System, visual route, layout, and evidence references,
and writes `image_requests/image_request_manifest.json`. Any later Architect or
Prompt change invalidates the bundle before an expensive ImageGen wave starts.

## 3. Generate and inspect the slide images

After approval, Codex reads:

```text
.agents/skills/pptx-generator-workflow/SKILL.md
${CODEX_HOME}/skills/.system/imagegen/SKILL.md
```

The default `fast-quality-20` profile targets GPT-5.6 Sol with medium reasoning.
Its base visual direction is **Academic, Informative, Professional & Creative
Design**, adapted to the approved user route and slide content. It deliberately
does not inject one-message, three-element, mandatory three-second, or
layout-category bans into every image prompt.

The default base prompt is intentionally short: create a 16:9 slide reference
for the supplied purpose, audience, and content; make it Academic, Informative,
Professional and Creative; follow the approved deck system; represent supplied
facts faithfully; and choose the composition, hierarchy, density, and visual
devices that best fit the slide. Only user, evidence, brand, accessibility, or
approved-route constraints are appended.

Codex prepares the whole wave, then dispatches up to 20 independent built-in
`image_gen.imagegen` calls concurrently. This is one platform call per slide,
not one multi-image call or a repository fallback. A 20-slide deck uses one
20-call initial wave. Each selected output is inspected; only a failed slide may
receive one targeted retry. Selected references are stored as:

```text
<runtime>\pngtopptx-project\src\slide1.png
<runtime>\pngtopptx-project\src\slide2.png
...
```

The workflow also preserves the Architect-bound request manifest, per-slide
prompts, exact-text Semantic Sidecars, inspection reports, and
`image_batches/image_generation_batch_manifest.json`. The PNG is a visual
reconstruction reference, not the final slide background or canonical text
source. Compilation waits until the manifest covers every approved slide.

## 4. Reconstruct, compare, and repair

Codex uses the installed external Skill:

```text
${CODEX_HOME}/skills/slide-editable-deck-orchestrator/SKILL.md
```

The meta Skill coordinates, but does not replace, these companions:

```text
slide-text-layer-inpaint     conditional preprocessing
slide-image-dual-render     only approved PPTX/HTML renderer and final gate
slide-visual-polish-qa      source/PPTX/HTML comparison and fix plans
```

Codex must execute the paths and command templates recorded in
`skillset_execution_plan.json`. That plan matches the verified live workflow:

1. install project-local `pptxgenjs`, `sharp`, `react`, `react-dom`, and
   `react-icons` once, using `--prefer-offline --no-audit --no-fund` to reuse the
   npm cache without changing the package set;
2. install project hardlocks;
3. run the orchestrator planner at quality level `polish`, with at most two
   blocker-repair iterations;
4. run `deckcompiler prepare-vector-preflight --runtime <runtime>` and
   `deckcompiler validate-vector-preflight --runtime <runtime>` after the
   accepted image batch exists. The external `PPTXlocal/raw/pipeline` detector
   measures native-canvas geometry with deep text/region scanning and at most
   two batch workers and one shared OCR reader per worker, while the repository
   gate traces only bounded, non-text flat regions. It adds no model call,
   avoids per-slide OCR-model reloads, and is not a PPTX renderer;
   use `--python-executable` or `PPTXLOCAL_RAW_PYTHON` for the prepared raw
   environment. Deep mode fails fast unless pytesseract, Tesseract, and the
   `eng`/`kor` language packs are available;
5. run `deckcompiler prepare-reconstruction-jobs --runtime <runtime>`. It writes
   one compact, hash-bound job per slide and binds the measurement inventory,
   safe SVG assets, and preflight manifest;
6. execute those jobs in fresh contexts, no more than four concurrently. Each
   context sees one source slide and writes only its `work/slideXX/` folder,
   including measurements, profile decision, editable fragment, crop decision,
   dual-render QA evidence under `worker_qa/`, reconstruction score, and
   hash-bound receipt. The final full-deck gate owns the separate `visual_qa/`
   directory;
7. validate all jobs with `deckcompiler validate-reconstruction-jobs
   --require-worker-outputs`, then run the official `validate_agent_work.js` and
   `integrate_subagent_work.js`. Only the integrator may write `lib/slides.js`
   and the shared crop plan;
8. keep `work/crop_plan.json` explicit, including for a zero-crop deck, and run
   crop preparation so `assets/manifest.json` exists;
9. after every approved source image and integrated per-slide artifact is ready,
   run one
   all-slide reconstruction with renderer quality
   `reconstruction`, `--require-qa`, `--require-reconstruction`, explicit crop
   and Node paths, and `--allow-large-batch`, writing directly to the final
   PPTX/HTML names, then run `final_gate.js`;
10. execute one complete full-deck Visual QA chain: PPTX rasterization,
   HTML capture, comparison, JSON/Markdown summary, and enforcement, all with
   source-slide mapping;
11. apply `deckcompiler validate-visual-quality`. The accepted one-slide canary
    permits only `palette_drift` and `pptx_html_edge_mismatch` as noticeable
    renderer diagnostics; spacing, hierarchy, typography, clipping, content,
    and detail-loss issues require repair;
12. if fail/blocking counts are zero and high-fidelity acceptance passes, use
   that output directly and skip the old
   unconditional second full-deck compile/QA pass, then enforce the orchestration
   state through `fast_path_acceptance`;
13. only when defects exist, reconstruct and QA targeted repair waves of at
   most five slides, for at most two iterations;
14. after repairs, run one conditional all-slide compile and one final full-deck
    QA chain, binding raster/capture metadata to the repaired PPTX/HTML hashes;
15. record actual stage timing and the full-deck compile count in
    `execution_timing.json`.

The default quality level is `polish`; `blocking-zero` is the minimum accepted
production level. The workflow runs:

1. 20-call concurrent ImageGen waves with one inspected reference per slide;
2. one native-canvas `PPTXlocal/raw` measurement/SVG-preflight pass with no
   model call, two-worker bounded parallelism, a 35% region ceiling, and strict
   text/continuous-tone/full-slide exclusions;
3. one fresh reconstruction context per slide with four-worker bounded
   parallelism and no duplicated full-deck prompt context;
4. official validation plus integrator-owned shared outputs;
5. one editable PPTX/HTML full-deck reconstruction on the normal path;
6. route and reconstruction hardlocks;
7. PPTX openability validation;
8. full-deck visual QA and high-fidelity issue acceptance against the generated
   source slides;
9. defect-only repair planning and rebuilding when needed;
10. one conditional post-repair full-deck build and evidence-hash validation.

Completion still requires zero fail/blocking slides. A run that reaches the
two-iteration cap remains `NEEDS_REPAIR`. For a 20-slide run, the timing report
compares the measured duration with the 120-minute baseline and 30-minute
(approximately 4x) target. Missing the time target is reported truthfully and
never causes the workflow to weaken quality gates.

## 5. Seal and register truthful completion

The Codex Skill writes a draft run manifest containing Architect approvals,
Image Generation receipts, selected PNGs, reconstruction evidence, and visual
QA results. Seal it:

```powershell
deckcompiler seal-codex-run `
  --draft C:\runs\quarterly-risk-deck\codex_run.draft.json `
  --output C:\runs\quarterly-risk-deck\codex_run.json
```

Then register the result:

```powershell
deckcompiler generate `
  --resume C:\runs\quarterly-risk-deck `
  --codex-run-manifest C:\runs\quarterly-risk-deck\codex_run.json
```

The command returns `COMPLETED` only when:

- `pptx-workflow-architect` is invocation order 1;
- Gate 1 and Gate 2 have explicit user approval;
- `image_gen.imagegen` covers every approved slide;
- its batch manifest records deterministic concurrent waves of at most 20,
  exactly one initial built-in call per slide, and no more than one targeted
  retry per slide;
- every selected reference is a real, consistently sized 16:9 PNG with a
  passing inspection record;
- every selected reference has one hash-bound fresh-context reconstruction job,
  a validated raw-measurement inventory, hash-bound bounded-SVG decisions,
  complete worker receipt, official integration report, and exactly one merged
  `sN(s)` function in `lib/slides.js`;
- the PPTX is a valid package whose slide count matches the approved blueprint;
- the native-object manifest comes from actual render-surface calls and records
  editable text on every slide;
- PNGtoPPTX hardlocks and PPTX openability pass, with the openability report
  hash-bound to that PPTX;
- the exact execution plan, orchestrator state, official dual-render trace,
  explicit crop plan/manifest, crop coverage, and objective per-slide QA
  evidence are hash-bound and internally consistent;
- the exact generated source PNG bytes are not embedded in the PPTX as a
  full-slide raster shortcut;
- the external visual-QA summary agrees with the sealed counts and has zero
  fail/blocking slides, and the high-fidelity policy finds no content, layout,
  hierarchy, typography, clipping, or meaningful-detail defect;
- a zero-repair run records exactly one full-deck compile in the timing report;
- the delivered editable PPTX exists and matches its recorded hash.

Placeholder bytes, a self-declared `PASS`, or a hash-only mock cannot satisfy
this completion gate.

Validate state at any time:

```powershell
deckcompiler validate-generate C:\runs\quarterly-risk-deck
deckcompiler validate-codex-run C:\runs\quarterly-risk-deck\codex_run.json
```

## Release-demo boundary

The historical DeckCompiler release demo remains a separate source-controlled
six-slide reproducibility fixture. Its Phase 3–6 schemas and frozen visual
bundle are not the general live Codex workflow and are not used to choose the
story or slide count for arbitrary user requests.
