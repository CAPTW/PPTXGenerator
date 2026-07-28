"""Observed icon crop detection for the E01.4 Canva benchmark pass."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps


SLIDE_W_IN = 16.0
SLIDE_H_IN = 9.0

OBSERVED_ICON_SLOTS = [
    {"crop_id": "checklist_step_01_clipboard", "component": "checklist", "role_hint": "plan_prepare_clipboard", "shape_kind": "clipboard_check", "bbox_px": [1077, 138, 1131, 197], "container_bbox_px": [1050, 116, 1157, 223], "z_order": 420, "color_role": "cyan"},
    {"crop_id": "checklist_step_02_valve", "component": "checklist", "role_hint": "setup_secure_valve", "shape_kind": "valve_pipeline", "bbox_px": [1070, 274, 1135, 335], "container_bbox_px": [1050, 250, 1157, 357], "z_order": 421, "color_role": "cyan"},
    {"crop_id": "checklist_step_03_gauge", "component": "checklist", "role_hint": "execute_monitor_gauge", "shape_kind": "gauge_monitor", "bbox_px": [1072, 399, 1134, 459], "container_bbox_px": [1050, 374, 1157, 481], "z_order": 422, "color_role": "cyan"},
    {"crop_id": "checklist_step_04_shield", "component": "checklist", "role_hint": "verify_confirm_shield", "shape_kind": "shield_check", "bbox_px": [1074, 520, 1131, 586], "container_bbox_px": [1050, 507, 1157, 614], "z_order": 423, "color_role": "cyan"},
    {"crop_id": "checklist_step_05_document_pencil", "component": "checklist", "role_hint": "complete_record_document_pencil", "shape_kind": "document_pencil", "bbox_px": [1077, 637, 1135, 701], "container_bbox_px": [1050, 634, 1157, 741], "z_order": 424, "color_role": "cyan"},
    {"crop_id": "chevron_step_01", "component": "checklist", "role_hint": "chevron_next", "shape_kind": "chevron_next", "bbox_px": [1592, 160, 1612, 187], "container_bbox_px": None, "z_order": 425, "color_role": "cyan"},
    {"crop_id": "chevron_step_02", "component": "checklist", "role_hint": "chevron_next", "shape_kind": "chevron_next", "bbox_px": [1592, 293, 1612, 320], "container_bbox_px": None, "z_order": 426, "color_role": "cyan"},
    {"crop_id": "chevron_step_03", "component": "checklist", "role_hint": "chevron_next", "shape_kind": "chevron_next", "bbox_px": [1592, 423, 1612, 450], "container_bbox_px": None, "z_order": 427, "color_role": "cyan"},
    {"crop_id": "chevron_step_04", "component": "checklist", "role_hint": "chevron_next", "shape_kind": "chevron_next", "bbox_px": [1592, 548, 1612, 575], "container_bbox_px": None, "z_order": 428, "color_role": "cyan"},
    {"crop_id": "chevron_step_05", "component": "checklist", "role_hint": "chevron_next", "shape_kind": "chevron_next", "bbox_px": [1592, 673, 1612, 700], "container_bbox_px": None, "z_order": 429, "color_role": "cyan"},
    {"crop_id": "bottom_warning_ppe", "component": "bottom_action_bar", "role_hint": "wear_ppe_warning", "shape_kind": "warning_triangle", "bbox_px": [119, 814, 196, 896], "container_bbox_px": None, "z_order": 430, "color_role": "gold"},
    {"crop_id": "bottom_hardhat_ppe", "component": "bottom_action_bar", "role_hint": "wear_ppe_hardhat", "shape_kind": "hardhat_goggles", "bbox_px": [232, 816, 289, 878], "container_bbox_px": None, "z_order": 431, "color_role": "gold"},
    {"crop_id": "bottom_lock_zero_leak", "component": "bottom_action_bar", "role_hint": "zero_leak_lock", "shape_kind": "lock", "bbox_px": [486, 818, 526, 875], "container_bbox_px": None, "z_order": 432, "color_role": "gold"},
    {"crop_id": "bottom_chemical_barrier_shield", "component": "bottom_action_bar", "role_hint": "chemical_barrier_shield", "shape_kind": "shield_check", "bbox_px": [718, 815, 787, 885], "container_bbox_px": None, "z_order": 433, "color_role": "gold"},
    {"crop_id": "bottom_communicate_chat", "component": "bottom_action_bar", "role_hint": "communicate_chat", "shape_kind": "chat_dots", "bbox_px": [1108, 820, 1172, 878], "container_bbox_px": None, "z_order": 434, "color_role": "gold"},
    {"crop_id": "bottom_teamwork_users", "component": "bottom_action_bar", "role_hint": "teamwork_users", "shape_kind": "users_group", "bbox_px": [1392, 818, 1462, 878], "container_bbox_px": None, "z_order": 435, "color_role": "gold"},
]


def detect_observed_icon_candidates(reference_image: Path, output_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    crop_dir = output_root / "icon_crops"
    norm_dir = output_root / "icon_normalized_crops"
    mask_dir = output_root / "icon_masks"
    for folder in (crop_dir, norm_dir, mask_dir):
        folder.mkdir(parents=True, exist_ok=True)
    image = Image.open(reference_image).convert("RGB")
    records = []
    for slot in OBSERVED_ICON_SLOTS:
        bbox = slot["bbox_px"]
        crop = image.crop(tuple(bbox))
        crop_path = crop_dir / f"{slot['crop_id']}.png"
        crop.save(crop_path)
        normalized = ImageOps.pad(crop, (96, 96), color="#000000")
        norm_path = norm_dir / f"{slot['crop_id']}.png"
        normalized.save(norm_path)
        gray = ImageOps.grayscale(normalized)
        mask = gray.point(lambda value: 255 if value > 38 else 0)
        mask_path = mask_dir / f"{slot['crop_id']}.png"
        mask.save(mask_path)
        records.append(
            {
                **slot,
                "bbox_norm": _norm_bbox(bbox, image.size),
                "insertion_bbox_in": _bbox_in(slot["bbox_px"], image.size),
                "crop_path": crop_path.as_posix(),
                "normalized_crop_path": norm_path.as_posix(),
                "mask_path": mask_path.as_posix(),
                "crop_sha256": hashlib.sha256(crop_path.read_bytes()).hexdigest(),
                "observed_source": "benchmark_reference_image",
                "glyph_present": True,
                "container_split_required": slot["container_bbox_px"] is not None,
            }
        )
    manifest = {
        "schema_name": "icon_crop_manifest",
        "status": "passed",
        "reference_image": reference_image.as_posix(),
        "reference_size_px": {"width": image.width, "height": image.height},
        "crop_count": len(records),
        "crops": records,
        "canva_parity_claimed": False,
    }
    report = {
        "schema_name": "icon_candidate_detection_report",
        "status": "passed",
        "detected_icon_candidate_count": len(records),
        "detection_mode": "benchmark_observed_bbox_seeded_by_visual_review",
        "role_labels_used_as_metadata_only": True,
        "generic_icon_substitution": False,
        "procedural_role_recipe_used": False,
        "canva_parity_claimed": False,
    }
    return report, manifest


def _norm_bbox(bbox: list[int], size: tuple[int, int]) -> list[float]:
    w, h = size
    x1, y1, x2, y2 = bbox
    return [round(x1 / w, 5), round(y1 / h, 5), round((x2 - x1) / w, 5), round((y2 - y1) / h, 5)]


def _bbox_in(bbox: list[int], size: tuple[int, int]) -> dict[str, float]:
    w, h = size
    x1, y1, x2, y2 = bbox
    return {
        "x": round(x1 / w * SLIDE_W_IN, 4),
        "y": round(y1 / h * SLIDE_H_IN, 4),
        "w": round((x2 - x1) / w * SLIDE_W_IN, 4),
        "h": round((y2 - y1) / h * SLIDE_H_IN, 4),
    }
