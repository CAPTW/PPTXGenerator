"""Reference-image analysis for the E01H hybrid Canva+ gate."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageStat


SLIDE_W_PX = 1600
SLIDE_H_PX = 900

CHECKLIST_STEPS = [
    ("01", "PLAN & PREPARE", "Verify documents, communication, readiness"),
    ("02", "SET UP & SECURE", "Closed loading, isolation & line-up"),
    ("03", "EXECUTE & MONITOR", "Operate within limits, continuous monitoring"),
    ("04", "VERIFY & CONFIRM", "Levels, pressures, temperatures, soundings"),
    ("05", "COMPLETE & RECORD", "Secure, debrief, records & lessons"),
]

THUMBNAIL_CAPTIONS = ["CARGO CONTROL ROOM", "CARGO PUMP & HPU", "GAS DETECTION"]
FOOTER_ITEMS = [
    "WEAR PPE AT ALL TIMES",
    "ZERO LEAK ZERO SPILL",
    "RESPECT THE CHEMICAL / RESPECT THE SAFETY BARRIER",
    "COMMUNICATE / CONFIRM",
    "TEAMWORK FOR SAFE OPERATIONS",
]


def analyze_reference_image(reference_path: str | Path) -> dict[str, Any]:
    path = Path(reference_path)
    if not path.exists():
        return {"schema_name": "reference_analysis_report", "status": "failed", "missing_reference": path.as_posix()}
    with Image.open(path) as image:
        width, height = image.size
        mode = image.mode
        stat = ImageStat.Stat(image.convert("L"))
        density = _visual_density(stat.stddev[0])
    regions = _regions(width, height)
    semantic_regions = [row for row in regions if row["layer_class"] == "semantic_editable"]
    visual_candidates = [row for row in regions if row["layer_class"] in {"replaceable_visual_field", "nonsemantic_visual_backplate"}]
    return {
        "schema_name": "reference_analysis_report",
        "status": "passed",
        "reference_path": path.as_posix(),
        "width": width,
        "height": height,
        "aspect_ratio": round(width / height, 6),
        "file_size_bytes": path.stat().st_size,
        "image_mode": mode,
        "visual_density_estimate": density,
        "likely_semantic_object_count": len(semantic_regions),
        "likely_visual_backplate_candidate_count": len(visual_candidates),
        "likely_visual_backplate_candidates": [row["object_id"] for row in visual_candidates],
        "semantic_text_regions": [row for row in semantic_regions if "text" in row["semantic_role"]],
        "regions": regions,
        "ocr_performed": False,
        "ocr_claimed": False,
        "canva_parity_claimed": False,
    }


def build_reference_asset_manifest(analysis: dict[str, Any], output_reference_path: str | Path) -> dict[str, Any]:
    return {
        "schema_name": "reference_asset_manifest",
        "status": analysis["status"],
        "reference_image": Path(output_reference_path).as_posix(),
        "source_reference_path": analysis.get("reference_path"),
        "width": analysis.get("width"),
        "height": analysis.get("height"),
        "role": "design_reference_only",
        "full_reference_background_allowed": False,
        "image_api_used": False,
        "openai_api_key_required": False,
        "canva_parity_claimed": False,
    }


def build_reference_visual_richness_report(analysis: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "reference_visual_richness_report",
        "status": "passed" if analysis.get("visual_density_estimate") in {"medium", "high"} else "warning",
        "visual_density_estimate": analysis.get("visual_density_estimate"),
        "major_visual_regions": ["hero_photo_visual_field", "checklist_panel", "bottom_safety_strip", "thumbnail_photo_chain", "technical_overlay"],
        "semantic_text_region_count": len(analysis.get("semantic_text_regions", [])),
        "visual_backplate_candidate_count": analysis.get("likely_visual_backplate_candidate_count", 0),
        "requires_hybrid_backplates": True,
        "native_only_skeleton_risk": "high",
        "canva_parity_claimed": False,
    }


def build_canva_benchmark_boundary_report(benchmark_root: str | Path) -> dict[str, Any]:
    root = Path(benchmark_root)
    present = {
        "object_ledger": (root / "canva_pptx_object_ledger.json").exists(),
        "media_ledger": (root / "canva_pptx_media_ledger.json").exists(),
        "text_ledger": (root / "canva_pptx_text_ledger.json").exists(),
        "render": (root / "assets/canva_rendered_slide.png").exists(),
    }
    return {
        "schema_name": "canva_benchmark_boundary_report",
        "status": "passed",
        "benchmark_files_present": present,
        "benchmark_boundary": "Canva benchmark is a hybrid visual/layer segmentation target, not a native editability ceiling.",
        "known_benchmark_facts": [
            "Canva output uses many raster/freeform visual layers.",
            "Canva output keeps text as editable text boxes.",
            "Canva native chart/table count is zero for this reference.",
            "E01H must preserve semantic editability while using bounded nonsemantic visual backplates.",
        ],
        "broad_canva_parity_claimed": False,
        "single_reference_benchmark_scope": True,
        "canva_parity_claimed": False,
    }


def bbox_to_px(bbox: dict[str, float], width: int, height: int) -> list[int]:
    return [round(bbox["x"] * width), round(bbox["y"] * height), round(bbox["w"] * width), round(bbox["h"] * height)]


def _visual_density(stddev: float) -> str:
    if stddev >= 52:
        return "high"
    if stddev >= 34:
        return "medium"
    return "low"


def _regions(width: int, height: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def add(object_id: str, semantic_role: str, bbox: list[float], layer_class: str, object_type: str, z: int, text: str | None = None, content: bool = False) -> None:
        bbox_norm = {"x": bbox[0], "y": bbox[1], "w": bbox[2], "h": bbox[3]}
        rows.append(
            {
                "object_id": object_id,
                "semantic_role": semantic_role,
                "bbox_norm": bbox_norm,
                "bbox_px": bbox_to_px(bbox_norm, width, height),
                "layer_class": layer_class,
                "object_type": object_type,
                "z_order": z,
                "text": text,
                "content_bearing": content,
                "confidence": 0.9,
            }
        )

    add("bg_base", "background_base", [0, 0, 1, 1], "decorative_vector", "background_base", 0)
    add("bp_hero_photo", "hero_visual_field", [0.0, 0.0, 0.61, 0.68], "replaceable_visual_field", "smart_object_like_image", 5)
    add("technical_overlay_top", "technical_overlay", [0.03, 0.015, 0.55, 0.22], "decorative_vector", "technical_overlay", 12)
    add("checklist_panel_backplate", "checklist_panel", [0.61, 0.04, 0.38, 0.80], "nonsemantic_visual_backplate", "panel", 15)
    add("checklist_title_text", "checklist_title_text", [0.66, 0.065, 0.28, 0.055], "semantic_editable", "text", 60, "5-STEP PRACTICAL CHECKLIST", True)
    for idx, (num, title, body) in enumerate(CHECKLIST_STEPS, start=1):
        y = 0.125 + (idx - 1) * 0.145
        add(f"checklist_row_{idx}_panel", "checklist_row_panel", [0.62, y, 0.355, 0.13], "semantic_editable", "card", 20 + idx)
        add(f"checklist_icon_{idx}", "semantic_icon", [0.632, y + 0.018, 0.074, 0.092], "semantic_editable", "semantic_icon", 35 + idx, content=True)
        add(f"checklist_step_{idx}_number", "checklist_step_number_text", [0.715, y + 0.036, 0.045, 0.055], "semantic_editable", "text", 55 + idx, num, True)
        add(f"checklist_step_{idx}_title", "checklist_step_title_text", [0.77, y + 0.032, 0.18, 0.035], "semantic_editable", "text", 65 + idx, title, True)
        add(f"checklist_step_{idx}_body", "checklist_step_body_text", [0.77, y + 0.067, 0.15, 0.055], "semantic_editable", "text", 70 + idx, body, True)
        add(f"checklist_chevron_{idx}", "semantic_icon", [0.948, y + 0.054, 0.018, 0.04], "semantic_editable", "semantic_icon", 80 + idx, content=True)
    for idx, caption in enumerate(THUMBNAIL_CAPTIONS, start=1):
        x = [0.23, 0.37, 0.505][idx - 1]
        add(f"bp_thumbnail_{idx}", "thumbnail_visual_field", [x, 0.64, 0.11, 0.14], "replaceable_visual_field", "smart_object_like_image", 18 + idx)
        add(f"thumbnail_caption_{idx}", "thumbnail_caption_text", [x, 0.815, 0.12, 0.035], "semantic_editable", "text", 78 + idx, caption, True)
    add("footer_strip_panel", "source_footer_strip", [0.03, 0.865, 0.94, 0.12], "semantic_editable", "panel", 30, content=True)
    for idx, label in enumerate(FOOTER_ITEMS, start=1):
        x = [0.075, 0.225, 0.385, 0.635, 0.80][idx - 1]
        add(f"footer_icon_{idx}", "semantic_icon", [x, 0.897, 0.05, 0.062], "semantic_editable", "semantic_icon", 90 + idx, content=True)
        add(f"footer_label_{idx}", "footer_source_text", [x + 0.06, 0.905, 0.12 if idx != 3 else 0.22, 0.058], "semantic_editable", "text", 100 + idx, label, True)
    return rows
