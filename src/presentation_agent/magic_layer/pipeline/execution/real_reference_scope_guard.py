from __future__ import annotations

from pathlib import Path
from typing import Any


ALLOWED_FIXTURE_ID = "e01b_single_reference_pass"
PPTX_NAME = "p04_controlled_real_reference_candidate.pptx"
RENDER_NAME = "p04_rendered_slide.png"
PROTECTED_NAMES = {
    "outputs/editable_template_spec.final.json",
    "outputs/golden_template_masters.pptx",
    "outputs/final_deck_large_premium.pptx",
}


def validate_real_reference_scope(
    *,
    fixture_id: str,
    out_dir: str | Path,
    reference_image: str | Path | None = None,
    pptx_outputs: list[str | Path] | None = None,
    render_outputs: list[str | Path] | None = None,
    protocol_ready: bool = True,
    semantic_invention_risk: bool = False,
) -> dict[str, Any]:
    out = Path(out_dir).resolve()
    pptx_outputs = [Path(path).resolve() for path in (pptx_outputs or [out / PPTX_NAME])]
    render_outputs = [Path(path).resolve() for path in (render_outputs or [out / RENDER_NAME])]
    blockers: list[str] = []
    decision = "P04_SCOPE_ALLOWED"

    if fixture_id != ALLOWED_FIXTURE_ID:
        decision = "P04_SCOPE_BLOCKED_WRONG_FIXTURE"
        blockers.append("Only e01b_single_reference_pass is allowed for P04.")
    elif not protocol_ready:
        decision = "P04_SCOPE_BLOCKED_MISSING_PROTOCOL_INPUT"
        blockers.append("Protocol/planning input evidence is insufficient.")
    elif semantic_invention_risk:
        decision = "P04_SCOPE_BLOCKED_SEMANTIC_INVENTION_RISK"
        blockers.append("P04 cannot invent missing semantic mappings from the image.")
    elif len(pptx_outputs) > 1:
        decision = "P04_SCOPE_BLOCKED_TOO_MANY_PPTX"
        blockers.append("P04 may create at most one PPTX.")
    elif len(render_outputs) > 1:
        decision = "P04_SCOPE_BLOCKED_TOO_MANY_RENDERS"
        blockers.append("P04 may create at most one render.")

    for path in [*pptx_outputs, *render_outputs]:
        norm = _norm(path)
        if any(name.lower() in norm.lower() for name in PROTECTED_NAMES):
            decision = "P04_SCOPE_BLOCKED_PROTECTED_ARTIFACT"
            blockers.append("Protected artifact output is forbidden.")
        elif "source_bound" in norm.lower() or "source-bound" in norm.lower():
            decision = "P04_SCOPE_BLOCKED_SOURCE_BOUND"
            blockers.append("Source-bound output is forbidden.")
        elif any(token in norm.lower() for token in ["e03", "e04", "d08", "c11", "bulk", "template_pack"]):
            if "p04_rx" not in norm.lower():
                decision = "P04_SCOPE_BLOCKED_SCALEOUT"
                blockers.append("Scaleout/template pack output is forbidden.")
        elif "_local_quarantine" in norm.lower() or "__quarantine" in norm.lower():
            decision = "P04_SCOPE_BLOCKED_QUARANTINE"
            blockers.append("Quarantine read/write is forbidden.")
        elif not _is_relative_to(path, out):
            decision = "P04_SCOPE_BLOCKED_OUTPUT_OUTSIDE_FOLDER"
            blockers.append("All P04 outputs must stay under the P04 output folder.")

    if decision == "P04_SCOPE_ALLOWED" and pptx_outputs and pptx_outputs[0].name != PPTX_NAME:
        decision = "P04_SCOPE_BLOCKED_OUTPUT_OUTSIDE_FOLDER"
        blockers.append("PPTX output filename is not allowed.")
    if decision == "P04_SCOPE_ALLOWED" and render_outputs and render_outputs[0].name != RENDER_NAME:
        decision = "P04_SCOPE_BLOCKED_OUTPUT_OUTSIDE_FOLDER"
        blockers.append("Render output filename is not allowed.")

    return {
        "schema": "p04_scope_guard_report.v1",
        "decision": decision,
        "allowed": decision == "P04_SCOPE_ALLOWED",
        "fixture_id": fixture_id,
        "reference_image": str(reference_image) if reference_image else None,
        "allowed_pptx_path": str(out / PPTX_NAME),
        "allowed_render_path": str(out / RENDER_NAME),
        "pptx_output_count": len(pptx_outputs),
        "render_output_count": len(render_outputs),
        "protocol_ready": protocol_ready,
        "semantic_invention_risk": semantic_invention_risk,
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
