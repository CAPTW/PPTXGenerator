# PPTXGenerator Agent Instructions

## Presentation-generation dispatch invariant

For every request whose intended output is a new presentation, slide deck, or
editable PPTX, the first presentation Skill must be the repository-owned
`pptx-workflow-architect` Skill. This applies regardless of:

- whether the user supplies an inline prompt, prompt file, PDF, multiple PDFs,
  notes, an outline, or only a topic;
- whether the user says "presentation", "deck", "slides", "PPT", or describes
  the deliverable indirectly;
- whether the request enters through chat or `deckcompiler generate`.

Before planning, generating images, running repository production code, or
invoking PNGtoPPTX:

1. Read and follow
   `.agents/skills/pptx-workflow-architect/SKILL.md` and any reference files it
   requires for the active Gate.
2. Complete its mandatory Gate 1 workflow design.
3. Complete its Gate 2 blueprint and visual-system design.
4. Obtain the approval required by that Skill. A user request such as "just do
   it" may compress Gates 1 and 2, but must not silently bypass approval.
5. Only then read and follow
   `.agents/skills/pptx-generator-workflow/SKILL.md` for production.

If `pptx-workflow-architect` is unavailable, stop with a missing-dependency
status because the checkout is incomplete. Do not substitute an external copy,
a fixed six-slide template, or a heuristic planner.

Within this repository, the production handoff after Architect approval is
`.agents/skills/pptx-generator-workflow/SKILL.md`; it replaces the Architect
Skill's generic standard-PPTX handoff while preserving all three approval gates.

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
  `slide-text-layer-inpaint` decision; prepare one hash-bound reconstruction job
  per accepted source PNG; execute each slide in a fresh context; validate and
  merge only through the official `validate_agent_work.js` and
  `integrate_subagent_work.js`; render only through
  `slide-image-dual-render/scripts/slide_pipeline.js`; gate with its
  `final_gate.js`; and run `slide-visual-polish-qa` with source-slide mapping.
- Follow the hash-bound `skillset_execution_plan.json`. Its default
  `fast-quality-20` profile targets GPT-5.6 Sol at medium reasoning, prepares a
  full image wave before dispatch, launches up to 20 independent built-in
  ImageGen calls concurrently, then launches at most four one-slide
  reconstruction workers concurrently without duplicating the full-deck
  context. The integrator is the only writer of shared renderer inputs. Compile
  all accepted slides in one `--allow-large-batch` renderer invocation. Use project-local Node
  dependencies, an explicit crop plan and generated asset manifest, renderer
  quality `reconstruction`, and QA mode `qa-polish`.
- After Architect approval, run `deckcompiler prepare-image-requests` once. It
  must deterministically derive every Prompt and Semantic Sidecar from the
  approved Blueprint and Design System, with no additional model call. Do not
  hand-author a second prompt set or dispatch an unbound generic prompt.
- Do not add unrequested hard prompt rules such as one-message-per-slide, three
  body elements, a mandatory three-second test, or category bans on body copy,
  tables, labels, dashboards, card grids, and infographic/poster compositions.
  The default visual direction is Academic, Informative, Professional &
  Creative Design, adapted to the approved content and user direction.
- Do not run an unconditional second full-deck compile. If the first full-deck
  gate and source-mapped QA pass with zero fail/blocking slides, seal that
  output. Only blocker repairs may trigger a second full-deck compile; targeted
  repair waves remain at most five slides and at most two iterations.
- Do not use `--skip-crops` for final delivery. A zero-crop deck still carries
  `work/crop_plan.json` and `assets/manifest.json`.
- Production acceptance requires route hardlock, reconstruction hardlock, PPTX
  openability, zero fail/blocking slides in visual QA, and repository
  high-fidelity acceptance. Only `palette_drift` and
  `pptx_html_edge_mismatch` may remain as known noticeable native-renderer
  diagnostics; content, layout, spacing, hierarchy, typography, clipping, and
  meaningful-detail issues require repair.
- Preserve editable native text, tables, charts, diagrams, and shapes. A
  generated full-slide PNG is a reconstruction reference, never the final slide
  background or final semantic surface.
- Do not force a fixed slide count or a fixed decision-brief narrative onto
  arbitrary prompts. Slide count and story architecture come from the approved
  Architect blueprint.
- Do not mock Image Generation, PNGtoPPTX reconstruction, or visual QA and call
  the result an end-to-end quality test.
