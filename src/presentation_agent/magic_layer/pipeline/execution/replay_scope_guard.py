from __future__ import annotations

from pathlib import Path
from typing import Any


ALLOWED_SAMPLE_ID = "controlled_minimal_cover_hero_v1"
ALLOWED_MODE = "CONTROLLED_REPLAY_MINIMAL"
PPTX_NAME = "p03_controlled_minimal_editable_candidate.pptx"
RENDER_NAME = "p03_controlled_minimal_rendered_slide.png"
PROTECTED_NAMES = {
    "outputs/editable_template_spec.final.json",
    "outputs/golden_template_masters.pptx",
    "outputs/final_deck_large_premium.pptx",
}


def validate_replay_scope(
    *,
    sample_id: str,
    mode: str,
    out_dir: str | Path,
    pptx_outputs: list[str | Path] | None = None,
    render_outputs: list[str | Path] | None = None,
) -> dict[str, Any]:
    out = Path(out_dir).resolve()
    pptx_outputs = [Path(p).resolve() for p in (pptx_outputs or [out / PPTX_NAME])]
    render_outputs = [Path(p).resolve() for p in (render_outputs or [out / RENDER_NAME])]
    blockers: list[str] = []
    decision = "REPLAY_SCOPE_ALLOWED"

    if sample_id != ALLOWED_SAMPLE_ID:
        decision = "REPLAY_SCOPE_BLOCKED_WRONG_SAMPLE"
        blockers.append("Only controlled_minimal_cover_hero_v1 is allowed.")
    elif mode.upper().replace("-", "_") != ALLOWED_MODE:
        decision = "REPLAY_SCOPE_BLOCKED_WRONG_SAMPLE"
        blockers.append("Only CONTROLLED_REPLAY_MINIMAL mode is allowed.")
    elif len(pptx_outputs) > 1:
        decision = "REPLAY_SCOPE_BLOCKED_TOO_MANY_PPTX"
        blockers.append("P03 may create at most one PPTX.")
    elif len(render_outputs) > 1:
        decision = "REPLAY_SCOPE_BLOCKED_TOO_MANY_RENDERS"
        blockers.append("P03 may create at most one primary render.")

    for path in [*pptx_outputs, *render_outputs]:
        norm = _norm(path)
        if any(protected.lower() in norm.lower() for protected in PROTECTED_NAMES):
            decision = "REPLAY_SCOPE_BLOCKED_PROTECTED_ARTIFACT"
            blockers.append("Protected artifact output is forbidden.")
        elif "source_bound" in norm.lower() or "source-bound" in norm.lower():
            decision = "REPLAY_SCOPE_BLOCKED_SOURCE_BOUND"
            blockers.append("Source-bound outputs are forbidden.")
        elif any(token in norm.lower() for token in ["e03", "e04", "d08", "c11", "bulk"]):
            if "p03_rx" not in norm.lower():
                decision = "REPLAY_SCOPE_BLOCKED_SCALEOUT"
                blockers.append("Scaleout output paths are forbidden.")
        elif "_local_quarantine" in norm.lower() or "__quarantine" in norm.lower():
            decision = "REPLAY_SCOPE_BLOCKED_QUARANTINE"
            blockers.append("Quarantine paths are forbidden.")
        elif not _is_relative_to(path, out):
            decision = "REPLAY_SCOPE_BLOCKED_OUTPUT_OUTSIDE_FOLDER"
            blockers.append("All P03 outputs must stay under the P03 output folder.")

    if decision == "REPLAY_SCOPE_ALLOWED" and pptx_outputs and pptx_outputs[0].name != PPTX_NAME:
        decision = "REPLAY_SCOPE_BLOCKED_OUTPUT_OUTSIDE_FOLDER"
        blockers.append("PPTX output filename is not allowed.")
    if decision == "REPLAY_SCOPE_ALLOWED" and render_outputs and render_outputs[0].name != RENDER_NAME:
        decision = "REPLAY_SCOPE_BLOCKED_OUTPUT_OUTSIDE_FOLDER"
        blockers.append("Render output filename is not allowed.")

    return {
        "schema": "controlled_replay_scope_guard_report.v1",
        "decision": decision,
        "allowed": decision == "REPLAY_SCOPE_ALLOWED",
        "sample_id": sample_id,
        "mode": mode,
        "allowed_pptx_path": str(out / PPTX_NAME),
        "allowed_render_path": str(out / RENDER_NAME),
        "pptx_output_count": len(pptx_outputs),
        "render_output_count": len(render_outputs),
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
