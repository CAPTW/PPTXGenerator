from __future__ import annotations

from pathlib import Path
from typing import Any


ARCHETYPES = ["cover_hero", "standard_content", "data_dashboard", "table_heavy"]
PPTX_NAME = "controlled_candidate.pptx"
RENDER_NAME = "rendered_slide.png"
PROTECTED_NAMES = {
    "outputs/editable_template_spec.final.json",
    "outputs/golden_template_masters.pptx",
    "outputs/final_deck_large_premium.pptx",
}


def validate_four_core_scope(
    *,
    out_dir: str | Path,
    archetypes: list[str] | None = None,
    pptx_outputs: list[str | Path] | None = None,
    render_outputs: list[str | Path] | None = None,
    protocol_ready: bool = True,
    semantic_invention_risk: bool = False,
) -> dict[str, Any]:
    out = Path(out_dir).resolve()
    selected = archetypes or list(ARCHETYPES)
    pptx_outputs = [Path(path).resolve() for path in (pptx_outputs or [out / "archetypes" / item / PPTX_NAME for item in selected])]
    render_outputs = [Path(path).resolve() for path in (render_outputs or [out / "archetypes" / item / RENDER_NAME for item in selected])]
    blockers: list[str] = []
    decision = "P05_SCOPE_ALLOWED"

    if sorted(selected) != sorted(ARCHETYPES):
        decision = "P05_SCOPE_BLOCKED_WRONG_ARCHETYPE"
        blockers.append("P05 allows exactly the four E02 archetypes.")
    elif not protocol_ready:
        decision = "P05_SCOPE_BLOCKED_SEMANTIC_INVENTION_RISK"
        blockers.append("Protocol/planning evidence is not ready for all selected archetypes.")
    elif semantic_invention_risk:
        decision = "P05_SCOPE_BLOCKED_SEMANTIC_INVENTION_RISK"
        blockers.append("P05 cannot invent missing semantic mappings from reference images.")
    elif len(pptx_outputs) > 4:
        decision = "P05_SCOPE_BLOCKED_TOO_MANY_PPTX"
        blockers.append("P05 may create at most four PPTX outputs.")
    elif len(render_outputs) > 4:
        decision = "P05_SCOPE_BLOCKED_TOO_MANY_RENDERS"
        blockers.append("P05 may create at most four render outputs.")

    for path in [*pptx_outputs, *render_outputs]:
        norm = _norm(path)
        if any(name.lower() in norm.lower() for name in PROTECTED_NAMES):
            decision = "P05_SCOPE_BLOCKED_PROTECTED_ARTIFACT"
            blockers.append("Protected artifact output is forbidden.")
        elif "source_bound" in norm.lower() or "source-bound" in norm.lower():
            decision = "P05_SCOPE_BLOCKED_SOURCE_BOUND"
            blockers.append("Source-bound output is forbidden.")
        elif any(token in norm.lower() for token in ["e03", "e04", "d08", "c11", "bulk", "template_pack"]):
            if "p05_rx" not in norm.lower():
                decision = "P05_SCOPE_BLOCKED_SCALEOUT"
                blockers.append("Scaleout or template-pack output is forbidden.")
        elif "_local_quarantine" in norm.lower() or "__quarantine" in norm.lower():
            decision = "P05_SCOPE_BLOCKED_QUARANTINE"
            blockers.append("Quarantine read/write is forbidden.")
        elif not _is_relative_to(path, out):
            decision = "P05_SCOPE_BLOCKED_OUTPUT_OUTSIDE_FOLDER"
            blockers.append("All P05 outputs must stay under the P05 output folder.")

    return {
        "schema": "p05_scope_guard_report.v1",
        "decision": decision,
        "allowed": decision == "P05_SCOPE_ALLOWED",
        "allowed_archetypes": ARCHETYPES,
        "selected_archetypes": selected,
        "pptx_output_count": len(pptx_outputs),
        "render_output_count": len(render_outputs),
        "allowed_pptx_paths": [str(out / "archetypes" / item / PPTX_NAME) for item in ARCHETYPES],
        "allowed_render_paths": [str(out / "archetypes" / item / RENDER_NAME) for item in ARCHETYPES],
        "blockers": blockers,
        "product_pass": False,
    }


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _norm(path: Path) -> str:
    return str(path).replace("\\", "/")
