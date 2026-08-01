# Codex Run Contract

The final run manifest is the evidence that a live Codex workflow actually
executed. It is not a request plan.

## Required identity

```json
{
  "schema_name": "codex_pptx_generation_run",
  "schema_version": "2.0.0",
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
- one ordered slide record per blueprint slide.

Each slide record contains the slide number, prompt, source PNG, Semantic
Sidecar, inspection report, `inspection_status: PASS`, and regeneration count.

## Reconstruction record

Record:

- `skill_name: slide-editable-deck-orchestrator`;
- `renderer_skill: slide-image-dual-render` and the exact three-companion
  Skill list;
- the explicit execute/skip decision for `slide-text-layer-inpaint`;
- quality level;
- route hardlock, reconstruction hardlock, and PPTX openability results;
- final editable PPTX and standalone HTML;
- native-object manifest and openability report.

Also hash-bind the intake-created `skillset_execution_plan.json`,
`work/orchestration_state.json`, official `out/render_trace.json`, explicit crop
plan and generated asset manifest, crop-coverage summary, and objective QA
evidence summary. HTML is required because the approved renderer is the dual
PPTX/HTML path.

## Visual QA record

Record:

- `skill_name: slide-visual-polish-qa`;
- final summary and contact sheet;
- fail, blocking, and needs-polish counts;
- repair iteration count;
- `status: PASS` only when fail and blocking counts are zero.

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
