"""Resolve icon-like regions into SVG roles or explicit non-icon dispositions."""

from __future__ import annotations

from typing import Any

from .svg_icon_matcher import match_svg_for_role


ICON_REGION_TYPES = {
    "semantic_icon",
    "decorative_icon_or_mark",
    "technical_ornament",
    "text_like_false_positive",
    "chart_marker",
    "table_marker",
    "unresolved_icon_like_region",
}

ICON_DISPOSITIONS = {
    "svg_mapped",
    "ppt_shape_primitive",
    "decorative_nonsemantic_allowed",
    "chart_table_marker_handoff_D04",
    "text_false_positive_handoff_D02",
    "unresolved_blocking",
    "unresolved_nonblocking_decorative",
}


def resolve_icon_regions(
    manifest: dict[str, Any],
    text_slot_map: dict[str, Any],
    taxonomy: dict[str, Any],
    inventory: dict[str, Any],
) -> dict[str, Any]:
    reference_id = manifest.get("reference_id") or "reference"
    width = int((manifest.get("reference_metadata") or {}).get("width") or 1)
    height = int((manifest.get("reference_metadata") or {}).get("height") or 1)
    candidates: list[dict[str, Any]] = []
    mappings: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    slot_counts = text_slot_map.get("slot_counts") or {}
    for layer in manifest.get("layers") or []:
        if not _is_icon_like(layer, width, height):
            continue
        candidate = _icon_candidate(layer, reference_id, width, height, slot_counts)
        candidates.append(candidate)
        mapping = _mapping_for_candidate(candidate, taxonomy, inventory)
        mappings.append(mapping)
        if mapping["final_disposition"].startswith("unresolved"):
            unresolved.append(mapping)
    return {
        "schema_name": "icon_region_resolution",
        "reference_id": reference_id,
        "icon_region_candidates": candidates,
        "svg_icon_mapping_candidates": mappings,
        "resolved_svg_icon_map": [item for item in mappings if item["final_disposition"] == "svg_mapped"],
        "unresolved_icon_regions": unresolved,
        "unresolved_blocking_count": sum(1 for item in unresolved if item["final_disposition"] == "unresolved_blocking"),
    }


def validate_icon_mapping(mapping: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if mapping.get("icon_classification") == "semantic_icon":
        if mapping.get("final_disposition") == "decorative_nonsemantic_allowed":
            errors.append("semantic_icon_cannot_be_decorative")
        if mapping.get("final_editability_target") != "svg_vector":
            errors.append("semantic_icon_must_resolve_to_svg_vector")
        if mapping.get("raster_fallback_allowed"):
            errors.append("semantic_icon_raster_fallback_forbidden")
    if mapping.get("final_disposition") == "unresolved_blocking" and not mapping.get("unresolved_reason"):
        errors.append("unresolved_semantic_icon_requires_reason")
    return errors


def _is_icon_like(layer: dict[str, Any], width: int, height: int) -> bool:
    layer_type = layer.get("layer_type")
    x, y, w, h = [int(v) for v in layer.get("bbox_px") or [0, 0, 0, 0]]
    area = (w * h) / (width * height) if width and height else 0
    return layer_type == "icon_region" or (layer_type == "technical_overlay" and area < 0.01)


def _icon_candidate(layer: dict[str, Any], reference_id: str, width: int, height: int, slot_counts: dict[str, Any]) -> dict[str, Any]:
    x, y, w, h = [int(v) for v in layer["bbox_px"]]
    area = (w * h) / (width * height) if width and height else 0
    aspect = w / h if h else 0
    role = _role_hint(layer, reference_id, area, aspect, slot_counts)
    classification = _classification(layer, reference_id, area, aspect)
    disposition = {
        "semantic_icon": "svg_mapped",
        "decorative_icon_or_mark": "ppt_shape_primitive",
        "technical_ornament": "decorative_nonsemantic_allowed",
        "chart_marker": "chart_table_marker_handoff_D04",
        "table_marker": "chart_table_marker_handoff_D04",
        "text_like_false_positive": "text_false_positive_handoff_D02",
    }.get(classification, "unresolved_blocking")
    return {
        "candidate_id": f"{reference_id}_icon_candidate_{layer['layer_id']}",
        "reference_id": reference_id,
        "layer_id": layer["layer_id"],
        "bbox_px": layer["bbox_px"],
        "bbox_norm": layer["bbox_norm"],
        "crop_path": layer.get("crop_path"),
        "source_confidence": layer.get("confidence"),
        "icon_classification": classification,
        "semantic_role_candidates": [role, "generic_icon"] if role != "generic_icon" else ["generic_icon"],
        "selected_role": role,
        "mapping_confidence": _mapping_confidence(classification, role),
        "final_disposition": disposition,
        "content_bearing": bool(layer.get("content_bearing")),
        "notes": "D03 icon-like region resolution uses geometry, archetype hint, layer context, and D02 slot context; OCR text is not used as strong evidence.",
    }


def _mapping_for_candidate(candidate: dict[str, Any], taxonomy: dict[str, Any], inventory: dict[str, Any]) -> dict[str, Any]:
    classification = candidate["icon_classification"]
    role = candidate["selected_role"]
    if classification == "semantic_icon":
        svg = match_svg_for_role(role, taxonomy, inventory)
        if svg["status"] != "mapped":
            return {
                **candidate,
                "selected_svg_candidate_path": None,
                "selected_svg_id": None,
                "final_editability_target": "reject_or_patch",
                "raster_fallback_allowed": False,
                "final_disposition": "unresolved_blocking",
                "unresolved_reason": svg.get("unresolved_reason") or "semantic_icon_svg_unmapped",
            }
        return {
            **candidate,
            "selected_svg_candidate_path": svg["selected_svg_path"],
            "selected_svg_id": svg["selected_svg_id"],
            "svg_match_method": svg["match_method"],
            "final_editability_target": "svg_vector",
            "raster_fallback_allowed": False,
            "unresolved_reason": "",
        }
    target = "ppt_shape" if classification in {"decorative_icon_or_mark", "technical_ornament"} else "reject_or_patch"
    return {
        **candidate,
        "selected_svg_candidate_path": None,
        "selected_svg_id": None,
        "svg_match_method": None,
        "final_editability_target": target,
        "raster_fallback_allowed": False,
        "unresolved_reason": "" if not candidate["final_disposition"].startswith("unresolved") else "icon_like_region_needs_review",
    }


def _classification(layer: dict[str, Any], reference_id: str, area: float, aspect: float) -> str:
    layer_type = layer.get("layer_type")
    if layer_type == "technical_overlay":
        return "technical_ornament"
    if reference_id in {"data_dashboard"} and (area < 0.008 or aspect > 2.0 or aspect < 0.45):
        return "chart_marker"
    if reference_id in {"table_heavy", "canva_benchmark"} and (area < 0.008 or aspect > 2.5):
        return "table_marker"
    if area < 0.002:
        return "decorative_icon_or_mark"
    if area > 0.035 and aspect > 2.5:
        return "text_like_false_positive"
    return "semantic_icon"


def _role_hint(layer: dict[str, Any], reference_id: str, area: float, aspect: float, slot_counts: dict[str, Any]) -> str:
    semantic = str(layer.get("semantic_role") or "").lower()
    if "source" in semantic or "footer" in semantic or "citation" in semantic:
        return "source"
    if reference_id == "data_dashboard":
        return "chart_bar" if area > 0.006 else "database"
    if reference_id == "table_heavy":
        return "table_marker" if False else "database"
    if reference_id == "cover_hero":
        return "globe" if area > 0.01 else "generic_icon"
    if reference_id == "standard_content":
        return "evidence"
    if reference_id == "canva_benchmark":
        return "source" if aspect > 2.0 else "generic_icon"
    return "generic_icon"


def _mapping_confidence(classification: str, role: str) -> float:
    if classification == "semantic_icon" and role != "generic_icon":
        return 0.62
    if classification == "semantic_icon":
        return 0.46
    if classification in {"chart_marker", "table_marker"}:
        return 0.58
    return 0.52
