"""D07.2.1 visual-field asset import validation helpers."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from .visual_field_asset_pipeline import ALLOWED_VISUAL_TARGETS, validate_single_visual_asset


ACCEPTED_EXTENSIONS = [".png", ".jpg", ".jpeg"]


def visual_asset_policy_v1_1() -> dict[str, Any]:
    return {
        "schema_name": "visual_asset_policy_v1_1",
        "visual_assets_bounded_to_visual_field_slots_only": True,
        "allowed_visual_asset_targets": sorted(ALLOWED_VISUAL_TARGETS),
        "full_slide_image_background_allowed": False,
        "screenshot_slide_allowed": False,
        "required_readable_text_inside_image_allowed": False,
        "semantic_icon_chart_table_inside_image_allowed": False,
        "semantic_text_icon_chart_table_rasterization_allowed": False,
        "source_citation_footer_text_must_remain_editable_ppt_text": True,
        "image_frame_bbox_and_crop_mask_record_required": True,
        "shape_fill_or_picture_crop_must_respect_slot_bounds": True,
        "missing_assets_create_patched_deck": False,
        "zero_accepted_assets_create_final_visual_asset_contact_sheets": False,
        "canva_parity_claimed": False,
    }


def build_visual_asset_slot_to_file_map(slot_inventory: dict[str, Any], import_dir: Path, prompt_dir: Path | None = None) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for slot in slot_inventory.get("slots") or []:
        slot_id = slot["slot_id"]
        slide_id = slot["slide_id"]
        expected = [f"{slot_id}{suffix}" for suffix in ACCEPTED_EXTENSIONS]
        recommended = [f"{slide_id}__{slot_id}__visual_asset{suffix}" for suffix in ACCEPTED_EXTENSIONS]
        entries.append(
            {
                "slot_id": slot_id,
                "slide_id": slide_id,
                "slide_number": slot.get("slide_number"),
                "archetype_id": slot.get("archetype_id"),
                "role": slot.get("visual_field_type"),
                "bbox_norm": slot.get("bbox_norm"),
                "bbox_area_norm": slot.get("bbox_area_norm"),
                "required_or_optional": "required",
                "expected_import_filenames": expected,
                "recommended_import_filenames": recommended,
                "accepted_extensions": ACCEPTED_EXTENSIONS,
                "import_folder_path": import_dir.as_posix(),
                "prompt_reference": (prompt_dir / f"{slot_id}.md").as_posix() if prompt_dir else None,
            }
        )
    return {
        "schema_name": "visual_asset_slot_to_file_map",
        "status": "passed" if entries else "blocked",
        "slot_count": len(entries),
        "import_folder_path": import_dir.as_posix(),
        "entries": entries,
        "canva_parity_claimed": False,
    }


def validate_imported_visual_assets(slot_file_map: dict[str, Any], import_dir: Path, processed_dir: Path) -> dict[str, Any]:
    accepted: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for entry in slot_file_map.get("entries") or []:
        asset_path = find_import_asset(import_dir, entry)
        if asset_path is None:
            missing.append(
                {
                    "slot_id": entry["slot_id"],
                    "slide_id": entry["slide_id"],
                    "slide_number": entry.get("slide_number"),
                    "archetype_id": entry["archetype_id"],
                    "role": entry["role"],
                    "expected_import_filenames": entry["expected_import_filenames"],
                    "recommended_import_filenames": entry["recommended_import_filenames"],
                    "status": "MISSING_IMPORT",
                }
            )
            continue
        validation = validate_single_visual_asset(
            asset_path,
            {
                "slot_id": entry["slot_id"],
                "slide_id": entry["slide_id"],
                "archetype_id": entry["archetype_id"],
                "visual_field_type": entry["role"],
                "bbox_norm": entry["bbox_norm"],
                "bbox_area_norm": entry["bbox_area_norm"],
            },
        )
        if validation["status"] == "accepted":
            processed_dir.mkdir(parents=True, exist_ok=True)
            processed_path = processed_dir / f"{entry['slot_id']}{asset_path.suffix.lower()}"
            shutil.copy2(asset_path, processed_path)
            accepted.append(
                {
                    **validation,
                    "role": entry["role"],
                    "bbox_norm": entry["bbox_norm"],
                    "bbox_area_norm": entry["bbox_area_norm"],
                    "original_import_path": asset_path.as_posix(),
                    "processed_asset_path": processed_path.as_posix(),
                    "final_use": "bounded_visual_field_asset",
                    "full_slide_background": False,
                    "semantic_raster_target": False,
                }
            )
        else:
            rejected.append({**validation, "role": entry["role"], "bbox_norm": entry["bbox_norm"], "bbox_area_norm": entry["bbox_area_norm"]})
    return {
        "schema_name": "visual_asset_import_validation_report",
        "status": "passed" if accepted and not missing and not rejected else "blocked",
        "slot_count": len(slot_file_map.get("entries") or []),
        "accepted_asset_count": len(accepted),
        "missing_asset_count": len(missing),
        "rejected_asset_count": len(rejected),
        "accepted_assets": accepted,
        "missing_assets": missing,
        "rejected_assets": rejected,
        "all_required_assets_accepted": len(accepted) == len(slot_file_map.get("entries") or []) and not missing and not rejected,
        "canva_parity_claimed": False,
    }


def find_import_asset(import_dir: Path, entry: dict[str, Any]) -> Path | None:
    for name in [*(entry.get("expected_import_filenames") or []), *(entry.get("recommended_import_filenames") or [])]:
        candidate = import_dir / name
        if candidate.exists():
            return candidate
    return None
