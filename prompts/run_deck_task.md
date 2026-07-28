Run the deck-generation harness for the current task.

Read `AGENTS.md` and the relevant skill docs in `.agents/skills/` first.

## Rules for this run
- Use only approved stage transitions.
- Use user-provided materials as the primary source of truth.
- Stop at each approval gate if the gate artifact is not approved.
- Generate slides only after `MASTER_TEMPLATE` is approved.
- Finish only when a local `.pptx` file exists.

## Return format
Return exactly:
1. `CURRENT_STAGE`
2. `ARTIFACT_CREATED`
3. `GATE_RESULT`
4. `NEXT_LEGAL_STAGE`
5. `BLOCKERS_IF_ANY`
