# Architect-First Prompt and PDF Workflow

The general workflow is a live Codex workflow. Repository Python owns immutable
input capture and evidence validation; Codex owns the platform-managed Skill and
tool calls.

The mandatory order is:

```text
pptx-workflow-architect
  -> approved Gate 1 and Gate 2
  -> imagegen / 20-call concurrent waves
  -> accept each inspected PNG immediately into streaming ready queue
  -> slide-editable-deck-orchestrator
  -> slide-text-layer-inpaint decision (execute or skip with reason)
  -> one fresh slide-image-dual-render context per source PNG (max 6 concurrent)
     while unfinished ImageGen calls continue
  -> official worker validation and integrator-only fragment merge
  -> one shared all-slide preview for source-mapped per-slide QA
  -> one final all-slide slide-image-dual-render reconstruction compile/gate
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

The default `terra-max` profile targets GPT-5.6 Terra with max reasoning and is
the quality-first route promoted from the accepted one-slide reconstruction.
The explicit `sol-medium` and `luna-max` alternatives remain available. All
profiles consume the same architect blueprint, image prompts, Semantic
Sidecars, renderer inputs, deterministic `raw-measured-bounded-vector-v1`
policy, compiler,
and QA thresholds. Luna may fall back to Sol only for a failed slide after an
explicit blocking gate; silent whole-deck fallback is forbidden.

The base visual direction is **Academic, Informative, Professional & Creative
Design**, adapted to the approved user route and slide content. It deliberately
does not inject one-message, three-element, mandatory three-second, or
layout-category bans into every image prompt.

Use the default or select `generate --execution-profile terra-max`,
`sol-medium`, or `luna-max`. The ImageGen submission cap is 20
slides for either profile; provider-side queuing may still serialize completion,
so reconstruction starts as each image arrives instead of waiting for the full
wave.

Reconstruction workers use the execution profile's `minimal_locked` Codex
arguments. They receive only one source PNG, one Semantic Sidecar, one sealed
job, and the explicit `slide-image-dual-render` Skill path; global plugins,
apps, memories, multi-agent, and ImageGen are disabled in those workers. The
Architect and ImageGen controller retain their normal context.

The default base prompt is intentionally short: create a 16:9 slide reference
for the supplied purpose, audience, and content; make it Academic, Informative,
Professional and Creative; follow the approved deck system; represent supplied
facts faithfully; and choose the composition, hierarchy, density, and visual
devices that best fit the slide. Only user, evidence, brand, accessibility, or
approved-route constraints are appended.

Codex first runs `deckcompiler prepare-streaming-execution --runtime <runtime>`,
prepares the whole wave, then dispatches up to 20 independent built-in
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
`streaming_execution.json`. As soon as one inspected PNG is saved, Codex runs
the external `PPTXlocal/raw` native-canvas measurement and bounded PNG-to-SVG
preflight, then `deckcompiler accept-streaming-image`; that slide's hash-bound
reconstruction job becomes ready while the other calls continue. Passed SVGs
are limited to measured non-text flat regions and are inputs to the official
SkillSet renderer, never a replacement renderer or full-slide surface. After
the last result,
`finalize-streaming-images` seals
`image_batches/image_generation_batch_manifest.json`. The PNG is a visual
reconstruction reference, not the final slide background or canonical text
source. Shared full-deck compilation waits for complete coverage, but one-slide
reconstruction authoring does not.

Concurrent dispatch is a request-side contract, not an unsupported claim about
provider-side capacity. The batch receipt records actual start/end intervals and
observed parallelism. If the platform queues a requested wave, the ready queue
still begins reconstruction on the first completed slide instead of waiting for
the twentieth. The conservative 30-minute budget therefore also covers a
roughly one-image-per-minute completion cadence: six five-minute reconstruction
workers keep pace, the twentieth authoring job closes near minute 25, and the two
shared render/QA passes use the remaining five minutes. The budget is reported
as missed rather than weakening a quality gate when calls, repairs, or QA take
longer.

### Verified one-slide fast lane

For a one-slide rerun, run `probe-one-slide-fast` before authoring. A hit is
valid only when the source, Semantic Sidecar, measured-vector receipt, editable
authoring files, crop plan, renderer/QA profiles, and prior accepted evidence
all match their sealed hashes. The workflow may then reuse those authoring
inputs, but it still performs final PPTX/HTML rendering, hardlocks,
source-mapped Visual QA, openability, and single-process acceptance validation.
The measured target is under 120 seconds: 42.224 seconds with a cold HTML
capture and 11.762 seconds with exact-input capture reuse, with zero change in
the accepted comparison metrics. See
`analysis_runs/20260821-one-slide-fast-benchmark.md`.

This is not an under-two-minute claim for first-time arbitrary-image authoring.
Any cache miss, input change, or rejected metric returns to the full
`terra-max` quality lane.

Live production uses canonical `CAPTW/pngtopptx` commit `d414d45`. Its four
Skill tree OIDs and combined content aggregate are fixed in
`.agents/skills/pptx-generator-workflow/dependencies.json`; the generated plan
then binds the exact installed entrypoint hashes for that run. This live pin is
separate from the immutable older DevPost demo pin.

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
4. measure each inspected image as it arrives with `PPTXlocal/raw`, accept only
   bounded non-text SVG candidates that pass security and fidelity gates, and
   create its compact hash-bound job immediately without waiting for the final
   batch manifest;
5. execute ready jobs in fresh contexts, no more than six concurrently. Each
   context sees one source slide and writes only the authoring artifacts in its
   `work/slideXX/` folder. Record STARTED and AUTHORING_COMPLETED timestamps;
6. after the last ImageGen result, run `finalize-streaming-images` and
   `validate-streaming-execution --require-complete
   --require-authoring-complete --require-overlap`, then validate jobs with
   `deckcompiler validate-reconstruction-jobs --require-authoring-outputs` and
    run the official `validate_agent_work.js` and
    `integrate_subagent_work.js`. Only the integrator may write `lib/slides.js`,
    the shared crop plan, and the merged `work/font_usage.json`;
7. run the official `font_preflight.js`. It collects original font families,
   scans system and per-user font locations, resolves exact installed fonts
   first, and writes both the Original -> Resolved mapping and installation
   request evidence. It never installs automatically. Exit code `3` pauses the
   run so the user can choose `installed`, `declined`, or `unavailable`; after
   that decision, rerun and continue with exact fonts or documented fallbacks;
8. keep `work/crop_plan.json` explicit, including for a zero-crop deck, and run
   crop preparation so `assets/manifest.json` exists;
9. run one official all-slide shared preview. Rasterize its PPTX and capture its
   HTML once, then reuse the mapped slide pages for every per-slide comparison;
10. execute the complete Visual QA chain on the preview: PPTX rasterization,
   HTML capture, comparison, JSON/Markdown summary, and enforcement, all with
   source-slide mapping;
11. apply `deckcompiler validate-visual-quality`. The accepted one-slide canary
    permits only `palette_drift` and `pptx_html_edge_mismatch` as noticeable
    renderer diagnostics; spacing, hierarchy, typography, clipping, content,
    and detail-loss issues require repair;
12. run `deckcompiler finalize-shared-render-qa --runtime <runtime> --summary
   <preview-summary>` to finalize reconstruction QA receipts from the
   source-mapped preview and validate `--require-worker-outputs`, then run one
   final all-slide renderer
   build with `--quality reconstruction --require-qa
   --require-reconstruction --allow-large-batch`, writing the final PPTX/HTML;
13. run `final_gate.js`, openability, and the final source-mapped Visual QA
   chain against the delivered files;
14. only when defects exist, reconstruct and QA targeted repair waves of at
   most five slides, for at most two iterations;
15. after repairs, run one conditional all-slide compile and one final full-deck
    QA chain, binding raster/capture metadata to the repaired PPTX/HTML hashes;
16. record actual call intervals, observed parallelism, overlap, zero isolated
    builds, and the shared full-deck render count in `execution_timing.json`.

The default quality level is `polish`; `blocking-zero` is the minimum accepted
production level. The workflow runs:

1. 20-call concurrent ImageGen waves with one inspected reference per slide;
2. one fresh reconstruction context per slide with six-worker bounded
   ready-queue parallelism and no duplicated full-deck prompt context;
3. official validation plus integrator-owned shared outputs;
4. zero isolated per-slide builds, one shared preview render, and one final
   editable PPTX/HTML reconstruction render on the normal path;
5. route and reconstruction hardlocks;
6. PPTX openability validation;
7. full-deck visual QA and high-fidelity issue acceptance against the generated
   source slides;
8. defect-only repair planning and rebuilding when needed;
9. one conditional post-repair full-deck build and evidence-hash validation.

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
- its streaming state proves accepted-image lineage, at most six concurrent
  reconstruction workers, and reconstruction/ImageGen overlap;
- every selected reference is a real, consistently sized 16:9 PNG with a
  passing inspection record;
- every selected reference has one hash-bound fresh-context reconstruction job,
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
- a zero-repair run records zero isolated per-slide builds and exactly two
  shared full-deck renders in the timing report;
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
