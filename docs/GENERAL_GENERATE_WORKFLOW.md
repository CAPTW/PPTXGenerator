# Architect-First Prompt and PDF Workflow

The general workflow is a live Codex workflow. Repository Python owns immutable
input capture and evidence validation; Codex owns the platform-managed Skill and
tool calls.

The mandatory order is:

```text
pptx-workflow-architect
  -> approved Gate 1 and Gate 2
  -> imagegen / image_gen.imagegen for every slide
  -> slide-editable-deck-orchestrator
  -> slide-text-layer-inpaint decision (execute or skip with reason)
  -> slide-image-dual-render hardlocked reconstruction
  -> slide-visual-polish-qa with source-slide mapping
  -> orchestrated repair waves
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

## 3. Generate and inspect the slide images

After approval, Codex reads:

```text
.agents/skills/pptx-generator-workflow/SKILL.md
${CODEX_HOME}/skills/.system/imagegen/SKILL.md
```

Codex calls the built-in `image_gen.imagegen` tool for every approved slide.
Each selected output is inspected and, when needed, regenerated with a targeted
change. Selected references are stored as:

```text
<runtime>\pngtopptx-project\src\slide1.png
<runtime>\pngtopptx-project\src\slide2.png
...
```

The workflow also preserves per-slide prompts, exact-text Semantic Sidecars,
and inspection reports. The PNG is a visual reconstruction reference, not the
final slide background or canonical text source.

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
   `react-icons`;
2. install project hardlocks;
3. run the orchestrator planner at quality level `polish`;
4. materialize a project-local design profile, `lib/slides.js`, and isolated
   per-slide worker artifacts;
5. keep `work/crop_plan.json` explicit, including for a zero-crop deck, and run
   crop preparation so `assets/manifest.json` exists;
6. reconstruct waves of at most five slides with renderer quality
   `reconstruction`, `--require-qa`, `--require-reconstruction`, an explicit
   `--crop-plan`, and an explicit project-local `--node-path`;
7. run `final_gate.js` with PPTX openability;
8. rasterize PPTX and capture HTML, always using `--source-slides` for wave
   mapping, then compare, summarize, enforce, and plan repairs;
9. run the final all-slide build with explicit `--allow-large-batch` only after
   all waves pass.

The default quality level is `polish`; `blocking-zero` is the minimum accepted
production level. The workflow runs:

1. editable PPTX/HTML reconstruction;
2. route and reconstruction hardlocks;
3. PPTX openability validation;
4. full-deck visual QA against the generated source slides;
5. repair-wave planning and rebuilding;
6. source-mapped QA after every wave;
7. final full-deck build and QA.

Completion requires zero fail/blocking slides. A run that reaches the iteration
cap remains `NEEDS_REPAIR`.

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
- every selected reference is a real, consistently sized 16:9 PNG with a
  passing inspection record;
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
  fail/blocking slides;
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
