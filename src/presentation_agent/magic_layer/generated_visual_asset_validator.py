"""Validate generated visual-field assets before importing into D07.2."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image

from .image_generation_provider import sha256_file


def build_forbidden_asset_hashes(paths: list[Path]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for path in paths:
        if path.exists() and path.is_file():
            try:
                hashes[path.as_posix()] = sha256_file(path)
            except OSError:
                continue
    return hashes


def validate_generated_visual_asset(asset_path: Path, slot: dict[str, Any], *, forbidden_hashes: dict[str, str] | None = None) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    forbidden_hashes = forbidden_hashes or {}
    if not asset_path.exists():
        errors.append("generated_asset_missing")
        return _report(asset_path, slot, errors, warnings)
    try:
        with Image.open(asset_path) as image:
            width, height = image.size
            mode = image.mode
    except Exception as exc:  # noqa: BLE001
        errors.append(f"generated_asset_unreadable:{exc}")
        return _report(asset_path, slot, errors, warnings)
    if width < 640 or height < 360:
        errors.append("resolution_below_minimum")
    ratio = width / height
    target_ratio = float(slot.get("target_aspect_ratio") or 1.7778)
    if not (0.45 <= ratio / target_ratio <= 2.2):
        errors.append("aspect_ratio_not_crop_or_pad_compatible")
    if slot.get("bbox_norm") and len(slot["bbox_norm"]) == 4:
        area = float(slot["bbox_norm"][2]) * float(slot["bbox_norm"][3])
        if area >= 0.85:
            errors.append("full_slide_visual_field_forbidden")
    digest = sha256_file(asset_path)
    if digest in set(forbidden_hashes.values()):
        errors.append("generated_asset_matches_forbidden_reference_or_render_hash")
    warnings.append("text_validation_mode=heuristic_no_ocr")
    warnings.append("text_risk=bounded")
    warnings.append("prompt_no_text_policy=enforced")
    return {
        **_report(asset_path, slot, errors, warnings),
        "width": width,
        "height": height,
        "mode": mode,
        "asset_aspect_ratio": round(ratio, 4),
        "target_aspect_ratio": target_ratio,
        "sha256": digest,
    }


def validate_generated_visual_assets(
    generation_results: dict[str, Any],
    resolved_map: dict[str, Any],
    *,
    forbidden_hashes: dict[str, str] | None = None,
) -> dict[str, Any]:
    slots = {slot["slot_id"]: slot for slot in resolved_map.get("slots") or []}
    reports = []
    for result in generation_results.get("results") or []:
        slot = slots.get(result.get("slot_id"))
        if not slot:
            continue
        path = Path(result.get("output_path") or "")
        reports.append(validate_generated_visual_asset(path, slot, forbidden_hashes=forbidden_hashes))
    accepted = [report for report in reports if report["status"] == "accepted"]
    rejected = [report for report in reports if report["status"] == "rejected"]
    return {
        "schema_name": "generated_asset_validation_report",
        "status": "passed" if reports and not rejected and len(accepted) == len(slots) else "blocked",
        "expected_asset_count": len(slots),
        "accepted_asset_count": len(accepted),
        "rejected_asset_count": len(rejected),
        "reports": reports,
        "accepted_assets": accepted,
        "rejected_assets": rejected,
        "canva_parity_claimed": False,
    }


def _report(asset_path: Path, slot: dict[str, Any], errors: list[str], warnings: list[str]) -> dict[str, Any]:
    return {
        "slot_id": slot.get("slot_id"),
        "slide_id": slot.get("slide_id"),
        "archetype_id": slot.get("archetype_id"),
        "role": slot.get("role"),
        "asset_path": asset_path.as_posix(),
        "status": "accepted" if not errors else "rejected",
        "errors": errors,
        "warnings": warnings,
        "text_validation_mode": "heuristic_no_ocr",
        "text_risk": "bounded",
        "prompt_no_text_policy": "enforced",
    }
