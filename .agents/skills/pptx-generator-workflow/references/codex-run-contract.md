# Codex Run Contract

The final run manifest is the evidence that a live Codex workflow actually
executed. It is not a request plan.

## Required identity

```json
{
  "schema_name": "codex_pptx_generation_run",
  "schema_version": "2.3.0",
  "workflow_id": "generate_...",
  "status": "COMPLETED"
}
```

`workflow_id` must match `generate_workflow_manifest.json`.

## Architect record

Record `pptx-workflow-architect` as `invocation_order: 1`, both Gate statuses as
`APPROVED`, and artifact references for:

- workflow design;
- blueprint;
- design system;
- explicit approval record.

The intake execution plan must bind the tracked repository Architect package:
`SKILL.md`, `references/design-system.md`, `references/large-deck.md`, and
`references/production-qa.md`. An external Architect path is not accepted as a
substitute for the Repo-owned first Skill.

Every artifact reference is:

```json
{"path": "relative/or/absolute/path", "sha256": "64 hex characters"}
```

The sealer replaces supplied hashes with hashes of the referenced files.

## Image Generation record

Record:

- `skill_name: imagegen`;
- `platform_tool_id: image_gen.imagegen`;
- planned and completed slide counts;
- the `fast-quality-20` dispatch profile;
- a hash-bound `image_request_manifest.json` produced by the one-pass
  deterministic Blueprint/Design-System adapter;
- a hash-bound `image_generation_batch_manifest.json` proving deterministic
  concurrent waves of at most 20 independent built-in calls;
- one ordered slide record per blueprint slide.

Each slide record contains the slide number, stable slide/request IDs, Blueprint
entry hash, visual-route/layout IDs and hashes, evidence references, Prompt,
source PNG, Semantic Sidecar, inspection report, `inspection_status: PASS`, and
regeneration count. The sealer rebuilds the expected Prompt and Sidecar from the
current approved Architect package; independently authored or generic Prompts
are rejected even when their files and SHA-256 values are internally valid.
The batch manifest records one initial call per slide, at most one targeted
regeneration for a failed slide, accepted coverage, request ID, Prompt SHA-256,
and selected PNG SHA-256. For exactly 20 slides, the initial generation is one
concurrent 20-call wave.

## Reconstruction record

Record:

- `skill_name: slide-editable-deck-orchestrator`;
- `renderer_skill: slide-image-dual-render` and the exact three-companion
  Skill list;
- the explicit execute/skip decision for `slide-text-layer-inpaint`;
- `execution_mode: single_compile_fast_path` when no repairs were needed, or
  `post_repair_recompile` after targeted repairs;
- quality level;
- route hardlock, reconstruction hardlock, and PPTX openability results;
- final editable PPTX and standalone HTML;
- native-object manifest and openability report.

Also hash-bind the intake-created `skillset_execution_plan.json`,
`work/orchestration_state.json`, official `out/render_trace.json`, explicit crop
plan and generated asset manifest, crop-coverage summary, and objective QA
evidence summary. HTML is required because the approved renderer is the dual
PPTX/HTML path.

The normal path compiles all approved slide artifacts in one full-deck
`--allow-large-batch` invocation and runs one source-mapped full-deck QA chain.
It does not unconditionally repeat that compile. A second full-deck compile is
valid only after recorded repair iterations.

## Visual QA record

Record:

- `skill_name: slide-visual-polish-qa`;
- final JSON summary, Markdown summary, and contact sheet;
- fail, blocking, and needs-polish counts;
- repair iteration count;
- per-slide raster/capture metadata whose input paths and hashes match the final
  delivered PPTX/HTML, plus metrics hashes matching the selected source PNG and
  final render images;
- `status: PASS` only when fail and blocking counts are zero.

## Performance record

Record the `fast-quality-20` target model (`gpt-5.6-sol`), reasoning effort
(`medium`), 120-minute observed baseline, 30-minute target, approximate 4x
target, and a hash-bound `execution_timing.json`. The timing report includes
actual total/ImageGen/reconstruction/QA seconds and the full-deck compile count.
It also records timezone-qualified start/completion timestamps whose span must
match the reported total duration.
For a zero-repair run that count must be one. The time target is measured and
reported; it never overrides quality, hardlock, editability, or openability
gates.

## Draft example

Use repository schema
`schemas/deckcompiler/codex-pptx-generation-run.schema.json` as the complete
field reference. Draft hashes may be 64 zeroes; `deckcompiler seal-codex-run`
recomputes them before validation.

The sealer also rejects placeholder evidence. It checks selected PNG structure,
consistent 16:9 dimensions, PPTX package structure and slide count, exact source
PNG embedding, the actual-render native-object manifest, the official
dual-render trace and hardlocks, crop/QA objective evidence, PPTX openability,
and the external visual-QA summary. A self-declared `PASS` with inconsistent
files cannot be registered as completion.
