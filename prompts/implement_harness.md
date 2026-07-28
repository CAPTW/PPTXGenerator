Implement the stage-gated presentation-generation harness in this repository.

Read `AGENTS.md` and the relevant skill docs in `.agents/skills/` before making changes.

## Objective
Replace any placeholder-first, generic-template-first, or export-dependent workflow with an evidence-first local-render workflow.

## Required deliverables
1. Add a pipeline stage enum and state machine enforcing:
   `INGEST -> DESIGN_REFERENCE_CHECK -> MASTER_TEMPLATE -> CONTENT_PLAN -> GENERATE -> QA -> RENDER_LOCAL_PPTX`
2. Add persistent state artifacts under `state/`.
3. Add stage-based tool ACLs so forbidden tools cannot run in earlier stages.
4. Add invalidation logic so changed user materials roll back downstream state.
5. Add approval gates for design reference, master template, and QA.
6. Add tests for:
   - no slide generation before template approval
   - no generic design fallback when user design references exist
   - no final success without a local `.pptx`
   - rollback when inputs change
7. Keep the implementation modular and readable.

## Constraints
- Do not implement a UI-export-based completion path.
- Do not silently assume uploaded materials are unreadable.
- Do not allow section generation before template freeze.
- Prefer small, typed modules over one large orchestrator file.

## Suggested file targets
- `src/presentation_agent/pipeline/stages.py`
- `src/presentation_agent/pipeline/state_store.py`
- `src/presentation_agent/pipeline/tool_acl.py`
- `src/presentation_agent/pipeline/invalidation.py`
- `src/presentation_agent/pipeline/orchestrator.py`
- `tests/test_stage_gating.py`
- `tests/test_local_render_required.py`

## Return format
Return exactly:
1. `CHANGED_FILES`
2. `STAGE_GRAPH`
3. `TESTS_ADDED`
4. `RISKS_OR_FOLLOWUPS`
