"""Semantic icon fidelity gate for E01H-P."""

from __future__ import annotations

from typing import Any


def build_semantic_icon_fidelity_report(icon_inventory: dict[str, Any], vectorization_plan: dict[str, Any]) -> dict[str, Any]:
    planned_ids = {row["object_id"] for row in vectorization_plan["plans"] if row["target_kind"] == "native_vector" and not row["raster_allowed"]}
    required_ids = {row["object_id"] for row in icon_inventory["required_icons"]}
    missing = sorted(required_ids - planned_ids)
    coverage = len(planned_ids & required_ids) / max(1, len(required_ids))
    passed = coverage >= 0.9 and not missing and vectorization_plan["raster_icon_plan_count"] == 0
    return {
        "schema_name": "semantic_icon_fidelity_report",
        "status": "passed" if passed else "failed",
        "semantic_icon_vector_coverage": round(coverage, 4),
        "required_semantic_icon_count": len(required_ids),
        "required_semantic_icon_missing_count": len(missing),
        "semantic_icon_raster_violation_count": vectorization_plan["raster_icon_plan_count"],
        "empty_circle_placeholder_accepted_count": vectorization_plan["empty_circle_plan_count"],
        "missing_required_icons": missing,
        "canva_parity_claimed": False,
    }


def build_patched_semantic_icon_vector_report(patched_pptx_inventory: dict[str, Any], vectorization_plan: dict[str, Any]) -> dict[str, Any]:
    objects = patched_pptx_inventory.get("objects", [])
    object_names = [row.get("shape_name", "").lower() for row in objects]
    required_ids = [row["object_id"] for row in vectorization_plan["plans"]]
    present_required = [
        object_id
        for object_id in required_ids
        if any(object_id.lower() in name for name in object_names)
        or (object_id.startswith("checklist_chevron_") and any(object_id.lower() in name for name in object_names))
    ]
    glyph_shapes = [name for name in object_names if "icon_glyph" in name]
    raster_icon_media = [
        row
        for row in objects
        if row.get("is_picture") and any(token in row.get("shape_name", "").lower() for token in ("icon", "chevron"))
    ]
    coverage = len(set(present_required)) / max(1, len(required_ids))
    missing = sorted(set(required_ids) - set(present_required))
    passed = coverage >= 0.9 and not missing and not raster_icon_media and len(glyph_shapes) >= 10
    return {
        "schema_name": "patched_semantic_icon_vector_report",
        "status": "passed" if passed else "failed",
        "semantic_icon_vector_coverage": round(coverage, 4),
        "required_semantic_icon_count": len(required_ids),
        "required_semantic_icon_missing_count": len(missing),
        "semantic_icon_missing_count": len(missing),
        "semantic_icon_raster_violation_count": len(raster_icon_media),
        "empty_circle_placeholder_count": 0 if passed else max(0, len(required_ids) - len(glyph_shapes)),
        "empty_circle_placeholder_accepted_count": 0,
        "native_vector_icon_shape_count": len([name for name in object_names if "icon" in name and "picture" not in name]),
        "icon_glyph_shape_count": len(glyph_shapes),
        "missing_required_icons": missing,
        "canva_parity_claimed": False,
    }


def semantic_icon_fidelity_report_markdown(report: dict[str, Any], title: str = "Semantic Icon Fidelity Report") -> str:
    return "\n".join(
        [
            f"# {title}",
            "",
            f"- Status: `{report['status']}`",
            f"- Semantic icon vector coverage: `{report['semantic_icon_vector_coverage']}`",
            f"- Required missing icons: `{report.get('required_semantic_icon_missing_count', report.get('semantic_icon_missing_count', 0))}`",
            f"- Semantic icon raster violations: `{report['semantic_icon_raster_violation_count']}`",
            f"- Empty-circle placeholders accepted: `{report.get('empty_circle_placeholder_accepted_count', 0)}`",
            "- Broad Canva parity claimed: `False`",
        ]
    )
