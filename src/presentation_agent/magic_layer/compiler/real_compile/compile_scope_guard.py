from __future__ import annotations

from pathlib import Path
from typing import Any


PROTECTED_OUTPUTS = {
    "outputs/editable_template_spec.final.json",
    "outputs/golden_template_masters.pptx",
    "outputs/final_deck_large_premium.pptx",
}


def validate_compile_scope(
    bundle: dict[str, Any],
    out_dir: str | Path,
    output_path: str | Path,
    *,
    planned_pptx_outputs: list[str | Path] | None = None,
) -> dict[str, Any]:
    out_root = Path(out_dir).resolve()
    output = Path(output_path).resolve()
    planned = [Path(item).resolve() for item in (planned_pptx_outputs or [output])]
    blockers: list[str] = []

    pptx_outputs = [item for item in planned if item.suffix.lower() == ".pptx"]
    if len(pptx_outputs) != 1:
        blockers.append("C02 compile scope allows exactly one PPTX output.")
    if not _is_relative_to(output, out_root):
        blockers.append("PPTX output path must be under the C02 output folder.")
    normalized = str(output).replace("\\", "/").lower()
    if any(protected.lower() in normalized for protected in PROTECTED_OUTPUTS):
        blockers.append("Protected canonical output target is forbidden.")
    if "source_bound" in normalized or "source-bound" in normalized:
        blockers.append("Source-bound output target is forbidden in C02.")
    if _has_forbidden_instruction(bundle):
        blockers.append("Full-slide raster, screenshot, or semantic raster instruction is forbidden.")

    return {
        "schema": "compile_scope_guard.v1",
        "allowed": not blockers,
        "blockers": blockers,
        "planned_pptx_output_count": len(pptx_outputs),
        "output_path": str(output),
        "out_dir": str(out_root),
        "product_pass": False,
    }


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _has_forbidden_instruction(bundle: dict[str, Any]) -> bool:
    spec = bundle.get("editable_candidate_spec") if isinstance(bundle.get("editable_candidate_spec"), dict) else bundle
    for obj in spec.get("objects", []):
        if not isinstance(obj, dict):
            continue
        object_type = str(obj.get("pptx_object_type") or obj.get("native_target") or "").lower()
        role = str(obj.get("semantic_role") or "").lower()
        if object_type in {"full_slide_raster", "screenshot_slide"}:
            return True
        if obj.get("raster_allowed") is True and role:
            return True
        geometry = obj.get("geometry") if isinstance(obj.get("geometry"), dict) else {}
        bbox = geometry.get("bbox_norm")
        if object_type == "replaceable_image_frame" and isinstance(bbox, list) and len(bbox) == 4:
            if float(bbox[2]) >= 0.95 and float(bbox[3]) >= 0.95:
                return True
    return False
