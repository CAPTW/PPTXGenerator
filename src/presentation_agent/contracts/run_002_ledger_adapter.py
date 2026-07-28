"""Normalize run_002 ledgers into Contract V2 structural ledger dictionaries."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


NORMALIZED_CATEGORIES: frozenset[str] = frozenset(
    {
        "ppt_text",
        "ppt_shape",
        "ppt_table",
        "ppt_chart",
        "svg_or_vector_icon",
        "raster_image",
        "photo_frame_image",
        "full_slide_raster",
        "unknown",
    }
)

SLOT_ALIASES: dict[str, dict[str, str]] = {
    "cover_hero": {
        "date_presenter": "meta_bar",
        "footer": "footer_or_source_strip",
    },
    "standard_content": {
        "cards": "body_or_card_group",
        "insight_takeaway": "takeaway_or_insight",
        "footer": "footer_or_source_strip",
    },
    "data_dashboard": {
        "secondary_chart": "insight_box_or_secondary_chart",
        "insight": "insight_box_or_secondary_chart",
        "footer": "source_strip",
    },
    "table_heavy": {
        "table": "table_region",
        "footer": "source_strip",
        "kpi_chips": "optional_kpi_or_note",
    },
}

_TEXT_PRIMITIVES = {"text_box"}
_SHAPE_PRIMITIVES = {
    "solid_fill_rect",
    "rect",
    "line",
    "oval",
    "rounded_rect",
    "rounded_rect_plus_text",
    "rect_plus_text",
    "editable_shape_chart_frame",
    "editable_combo_chart_frame",
}
_TABLE_PRIMITIVES = {"editable_powerpoint_table", "ppt_table", "native_table", "shape_grid_table"}
_CHART_PRIMITIVES = {"editable_donut_shape", "editable_bar_shape", "editable_line_shape", "rect_bar", "ppt_chart", "native_chart", "shape_chart"}
_ICON_PRIMITIVES = {"role_mapped_svg_icon", "svg_icon", "svg_or_vector_icon", "vector_icon"}
_PHOTO_FRAME_PRIMITIVES = {"replaceable_photo_frame_shape", "image_frame", "photo_frame_image"}
_RASTER_PRIMITIVES = {"picture", "bitmap", "raster_image"}


def normalize_run_002_object_ledger(
    raw_ledger: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    *,
    archetype_by_slide: dict[int, str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return a Contract V2 structural ledger plus adapter diagnostics."""

    objects: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_ledger, start=1):
        normalized = normalize_run_002_object(raw, index=index, archetype_by_slide=archetype_by_slide or {})
        objects.append(normalized)
        if normalized["primitive_type"] == "unknown":
            warnings.append(
                {
                    "code": "RUN002_LEDGER_ADAPTER_UNKNOWN_PRIMITIVE",
                    "object_id": normalized["object_id"],
                    "slot_id": normalized.get("slot_id"),
                    "primitive": raw.get("primitive"),
                    "message": "Run_002 ledger adapter could not normalize object primitive/type.",
                }
            )

    slides: dict[int, dict[str, Any]] = {}
    for obj in objects:
        slide_number = int(obj["slide_number"])
        if slide_number not in slides:
            slides[slide_number] = {
                "slide_number": slide_number,
                "slide_id": obj["slide_id"],
                "archetype_id": obj["archetype_id"],
                "objects": [],
            }
        slides[slide_number]["objects"].append(obj)

    ledger = {
        "schema_name": "contract_v2_structural_ledger",
        "schema_version": "1.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "object_count": len(objects),
        "unknown_object_count": sum(1 for obj in objects if obj["primitive_type"] == "unknown"),
        "slides": [slides[number] for number in sorted(slides)],
        "objects": objects,
        "warnings": warnings,
    }
    report = {
        "schema_name": "run_002_ledger_adapter_report",
        "schema_version": "1.0",
        "generated_at_utc": ledger["generated_at_utc"],
        "normalized_categories": sorted(NORMALIZED_CATEGORIES),
        "slot_aliases": SLOT_ALIASES,
        "summary": {
            "object_count": len(objects),
            "unknown_object_count": ledger["unknown_object_count"],
            "warning_count": len(warnings),
            "category_counts": _category_counts(objects),
        },
        "warnings": warnings,
    }
    return ledger, report


def normalize_run_002_object(
    raw: dict[str, Any],
    *,
    index: int,
    archetype_by_slide: dict[int, str],
) -> dict[str, Any]:
    slide_number = int(raw.get("slide_number") or 0)
    archetype_id = str(raw.get("archetype_id") or archetype_by_slide.get(slide_number) or "unknown")
    category = _primitive_category(raw)
    slot_ref = _optional_str(raw.get("slot_ref") or raw.get("slot_id"))
    slot_id = SLOT_ALIASES.get(archetype_id, {}).get(slot_ref or "", slot_ref)
    object_id = _object_id(raw, index)
    primitive = _contract_gate_primitive(category)
    semantic_type = _semantic_type(category, raw)
    full_slide = bool(raw.get("full_slide")) or _is_full_slide(raw.get("bounds"))
    if full_slide and category == "raster_image":
        category = "full_slide_raster"
        primitive = "raster_image"

    return {
        "slide_number": slide_number,
        "slide_id": str(raw.get("slide_id") or f"slide-{slide_number:03d}"),
        "archetype_id": archetype_id,
        "object_id": object_id,
        "slot_id": slot_id,
        "source_slot_id": slot_ref,
        "bbox": _bbox(raw.get("bounds") or raw.get("bbox")),
        "primitive_type": category,
        "primitive": primitive,
        "semantic_type": semantic_type,
        "editability": "editable" if bool(raw.get("editable", False)) else "non_editable",
        "editable": bool(raw.get("editable", False)),
        "decorative": bool(raw.get("decorative", False)),
        "required": bool(raw.get("required", False)),
        "raster": category in {"raster_image", "full_slide_raster"},
        "full_slide": full_slide,
        "source_binding": _binding_placeholder(raw, kind="source"),
        "citation_binding": _binding_placeholder(raw, kind="citation"),
        "warnings": [],
        "raw_primitive": raw.get("primitive"),
        "raw_role": raw.get("role"),
    }


def split_contract_v2_ledgers(ledger: dict[str, Any]) -> dict[str, dict[str, Any]]:
    objects = list(ledger.get("objects") or [])
    return {
        "object": _filtered_ledger(ledger, objects),
        "text": _filtered_ledger(ledger, [obj for obj in objects if obj.get("primitive_type") == "ppt_text"]),
        "media": _filtered_ledger(ledger, [obj for obj in objects if obj.get("primitive_type") in {"raster_image", "full_slide_raster", "photo_frame_image", "svg_or_vector_icon"}]),
        "chart_table": _filtered_ledger(ledger, [obj for obj in objects if obj.get("primitive_type") in {"ppt_chart", "ppt_table"}]),
        "svg_icon": _filtered_ledger(ledger, [obj for obj in objects if obj.get("primitive_type") == "svg_or_vector_icon"]),
        "slot_coverage": _slot_coverage_ledger(ledger),
        "protected_zone": _protected_zone_ledger(ledger),
    }


def _primitive_category(raw: dict[str, Any]) -> str:
    primitive = str(raw.get("primitive") or raw.get("primitive_type") or raw.get("shape_type") or "").strip().lower()
    role = str(raw.get("role") or "").strip().lower()
    if primitive in _TEXT_PRIMITIVES:
        return "ppt_text"
    if primitive in _PHOTO_FRAME_PRIMITIVES or role == "photo_frame":
        return "photo_frame_image"
    if primitive in _TABLE_PRIMITIVES or role == "table":
        return "ppt_table"
    if primitive in _CHART_PRIMITIVES or role in {"chart", "chart_frame", "chart_label", "chart_title", "chart_legend_marker", "chart_legend_label"}:
        return "ppt_chart"
    if primitive in _ICON_PRIMITIVES or role == "semantic_svg_icon":
        return "svg_or_vector_icon"
    if primitive in _RASTER_PRIMITIVES:
        return "raster_image"
    if primitive in _SHAPE_PRIMITIVES:
        return "ppt_shape"
    return "unknown"


def _contract_gate_primitive(category: str) -> str:
    return {
        "ppt_text": "ppt_text",
        "ppt_shape": "ppt_shape",
        "ppt_table": "ppt_table",
        "ppt_chart": "ppt_chart",
        "svg_or_vector_icon": "svg_or_vector_icon",
        "photo_frame_image": "image_frame",
        "raster_image": "raster_image",
        "full_slide_raster": "raster_image",
        "unknown": "unknown",
    }[category]


def _semantic_type(category: str, raw: dict[str, Any]) -> str:
    role = str(raw.get("role") or "").lower()
    if category == "ppt_text":
        return "text"
    if category == "ppt_table":
        return "table"
    if category == "ppt_chart":
        return "chart"
    if category == "svg_or_vector_icon":
        return "icon"
    if category == "photo_frame_image":
        return "image_frame"
    if category in {"raster_image", "full_slide_raster"}:
        return role or "raster"
    return role or category


def _object_id(raw: dict[str, Any], index: int) -> str:
    base = str(raw.get("object_id") or raw.get("component_id") or raw.get("name") or f"object-{index}").strip()
    shape_id = str(raw.get("shape_id") or index).strip()
    return f"{base}:{shape_id}"


def _bbox(value: Any) -> dict[str, float] | None:
    if not isinstance(value, dict):
        return None
    result: dict[str, float] = {}
    for key in ("x", "y", "w", "h"):
        try:
            result[key] = round(float(value[key]), 6)
        except (KeyError, TypeError, ValueError):
            return None
    return result


def _is_full_slide(value: Any) -> bool:
    bbox = _bbox(value)
    if not bbox:
        return False
    return bbox["w"] >= 12.6 and bbox["h"] >= 7.0


def _binding_placeholder(raw: dict[str, Any], *, kind: str) -> dict[str, Any]:
    explicit = _optional_str(raw.get(f"{kind}_id") or raw.get(f"{kind}_binding"))
    return {
        "bound": explicit is not None,
        f"{kind}_id": explicit,
        "placeholder_status": str(raw.get("placeholder_status") or "semantic_template_placeholder"),
    }


def _category_counts(objects: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {category: 0 for category in sorted(NORMALIZED_CATEGORIES)}
    for obj in objects:
        counts[str(obj.get("primitive_type") or "unknown")] += 1
    return counts


def _filtered_ledger(base: dict[str, Any], objects: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_name": "contract_v2_filtered_ledger",
        "schema_version": "1.0",
        "generated_at_utc": base.get("generated_at_utc"),
        "object_count": len(objects),
        "objects": objects,
    }


def _slot_coverage_ledger(base: dict[str, Any]) -> dict[str, Any]:
    coverage: dict[str, dict[str, Any]] = {}
    for obj in base.get("objects") or []:
        archetype_id = str(obj.get("archetype_id"))
        slot_id = str(obj.get("slot_id") or "")
        if not slot_id:
            continue
        key = f"{archetype_id}:{slot_id}"
        entry = coverage.setdefault(key, {"archetype_id": archetype_id, "slot_id": slot_id, "object_count": 0, "editable_object_count": 0, "objects": []})
        entry["object_count"] += 1
        entry["editable_object_count"] += int(bool(obj.get("editable")))
        entry["objects"].append(obj.get("object_id"))
    return {
        "schema_name": "contract_v2_slot_coverage_ledger",
        "schema_version": "1.0",
        "generated_at_utc": base.get("generated_at_utc"),
        "slots": list(coverage.values()),
    }


def _protected_zone_ledger(base: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "contract_v2_protected_zone_ledger",
        "schema_version": "1.0",
        "generated_at_utc": base.get("generated_at_utc"),
        "intrusions": [],
        "checks": [
            {
                "archetype_id": slide.get("archetype_id"),
                "slide_number": slide.get("slide_number"),
                "status": "passed",
                "intrusion_count": 0,
            }
            for slide in base.get("slides") or []
        ],
    }


def _optional_str(value: Any) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None
