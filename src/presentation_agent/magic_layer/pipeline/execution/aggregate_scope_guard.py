from __future__ import annotations

from pathlib import Path
from typing import Any


ARCHETYPES = ["cover_hero", "standard_content", "data_dashboard", "table_heavy"]
PACK_NAME = "p06_four_core_noncanonical_review_pack.pptx"
RENDER_FOLDER = "p06_renders"
PROTECTED_NAMES = {
    "outputs/editable_template_spec.final.json",
    "outputs/golden_template_masters.pptx",
    "outputs/final_deck_large_premium.pptx",
}


def validate_aggregate_scope(
    *,
    p05_run: str | Path,
    out_dir: str | Path,
    source_pptx_inputs: list[str | Path] | None = None,
    aggregate_outputs: list[str | Path] | None = None,
    render_outputs: list[str | Path] | None = None,
    contact_sheet_outputs: list[str | Path] | None = None,
) -> dict[str, Any]:
    p05 = Path(p05_run).resolve()
    out = Path(out_dir).resolve()
    sources = [Path(path).resolve() for path in (source_pptx_inputs or [p05 / "archetypes" / item / "controlled_candidate.pptx" for item in ARCHETYPES])]
    aggregate = [Path(path).resolve() for path in (aggregate_outputs or [out / PACK_NAME])]
    renders = [Path(path).resolve() for path in (render_outputs or [out / RENDER_FOLDER / f"slide_{index:02d}_{archetype}.png" for index, archetype in enumerate(ARCHETYPES, start=1)])]
    contacts = [Path(path).resolve() for path in (contact_sheet_outputs or [out / RENDER_FOLDER / "p06_four_core_contact_sheet.png"])]
    blockers: list[str] = []
    decision = "P06_SCOPE_ALLOWED"

    source_arches = _source_archetypes(sources)
    if len(sources) != 4 or sorted(source_arches) != sorted(ARCHETYPES):
        decision = "P06_SCOPE_BLOCKED_MISSING_ARCHETYPE"
        blockers.append("P06 requires exactly four P05 source PPTX inputs, one per archetype.")
    elif len(aggregate) != 1:
        decision = "P06_SCOPE_BLOCKED_TOO_MANY_PPTX"
        blockers.append("P06 may create exactly one aggregate PPTX.")
    elif len(renders) > 4 or len(contacts) > 1:
        decision = "P06_SCOPE_BLOCKED_TOO_MANY_RENDERS"
        blockers.append("P06 may render at most four slides and one contact sheet.")

    for path in [*aggregate, *renders, *contacts]:
        norm = _norm(path)
        if any(name.lower() in norm.lower() for name in PROTECTED_NAMES):
            decision = "P06_SCOPE_BLOCKED_PROTECTED_ARTIFACT"
            blockers.append("Protected artifact output is forbidden.")
        elif _has_forbidden_stage_token(path, {"e03"}) and "p06_rx" not in norm.lower():
            decision = "P06_SCOPE_BLOCKED_E03"
            blockers.append("E03 output is forbidden.")
        elif "source_bound" in norm.lower() or "source-bound" in norm.lower():
            decision = "P06_SCOPE_BLOCKED_SOURCE_BOUND"
            blockers.append("Source-bound output is forbidden.")
        elif _has_forbidden_stage_token(path, {"e04", "d08", "c11", "bulk", "template_pack"}):
            if "p06_rx" not in norm.lower():
                decision = "P06_SCOPE_BLOCKED_SCALEOUT"
                blockers.append("Scaleout or template-pack output is forbidden.")
        elif "_local_quarantine" in norm.lower() or "__quarantine" in norm.lower():
            decision = "P06_SCOPE_BLOCKED_QUARANTINE"
            blockers.append("Quarantine read/write is forbidden.")
        elif not _is_relative_to(path, out):
            decision = "P06_SCOPE_BLOCKED_OUTPUT_OUTSIDE_FOLDER"
            blockers.append("All P06 outputs must stay under the P06 output folder.")

    if decision == "P06_SCOPE_ALLOWED" and aggregate[0].name != PACK_NAME:
        decision = "P06_SCOPE_BLOCKED_OUTPUT_OUTSIDE_FOLDER"
        blockers.append("Aggregate PPTX filename is not allowed.")

    return {
        "schema": "p06_scope_guard_report.v1",
        "decision": decision,
        "allowed": decision == "P06_SCOPE_ALLOWED",
        "allowed_archetypes": ARCHETYPES,
        "source_pptx_input_count": len(sources),
        "aggregate_pptx_output_count": len(aggregate),
        "aggregate_render_output_count": len(renders),
        "contact_sheet_output_count": len(contacts),
        "allowed_pack_path": str(out / PACK_NAME),
        "allowed_render_folder": str(out / RENDER_FOLDER),
        "blockers": blockers,
        "product_pass": False,
    }


def _source_archetypes(paths: list[Path]) -> list[str]:
    found = []
    for path in paths:
        parts = {part.lower() for part in path.parts}
        for archetype in ARCHETYPES:
            if archetype.lower() in parts:
                found.append(archetype)
    return found


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _norm(path: Path) -> str:
    return str(path).replace("\\", "/")


def _has_forbidden_stage_token(path: Path, tokens: set[str]) -> bool:
    parts = [part.lower() for part in path.parts]
    for part in parts:
        normalized = part.replace("-", "_")
        if normalized in tokens:
            return True
        if any(normalized.startswith(token + "_") or normalized.endswith("_" + token) for token in tokens):
            return True
    return False
