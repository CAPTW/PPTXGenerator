"""Semantic icon vectorization planning for E01H-P."""

from __future__ import annotations

from typing import Any


def build_icon_vectorization_plan(icon_inventory: dict[str, Any]) -> dict[str, Any]:
    plans = []
    for row in icon_inventory["required_icons"]:
        plans.append(
            {
                "plan_id": f"vectorize_{row['object_id']}",
                "object_id": row["object_id"],
                "icon_class": row["icon_class"],
                "glyph_kind": row["required_glyph_kind"],
                "source_bbox_norm": row.get("bbox_norm"),
                "target_kind": "native_vector",
                "implementation": "ppt_native_line_freeform",
                "raster_allowed": False,
                "empty_circle_allowed": False,
                "not_applicable_allowed": False,
                "status": "planned",
            }
        )
    raster_plans = [row for row in plans if row["raster_allowed"]]
    empty_circle_plans = [row for row in plans if row["empty_circle_allowed"]]
    return {
        "schema_name": "icon_vectorization_plan",
        "status": "passed" if not raster_plans and not empty_circle_plans and len(plans) == icon_inventory["required_semantic_icon_count"] else "failed",
        "required_icon_plan_count": len(plans),
        "native_vector_plan_count": len([row for row in plans if row["target_kind"] == "native_vector"]),
        "raster_icon_plan_count": len(raster_plans),
        "empty_circle_plan_count": len(empty_circle_plans),
        "plans": plans,
        "icons": plans,
        "canva_parity_claimed": False,
    }


def build_semantic_icon_svg_manifest(vectorization_plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "semantic_icon_svg_manifest",
        "status": vectorization_plan["status"],
        "required_semantic_icon_count": vectorization_plan["required_icon_plan_count"],
        "svg_icon_count": 0,
        "native_vector_icon_count": vectorization_plan["native_vector_plan_count"],
        "semantic_icon_raster_count": vectorization_plan["raster_icon_plan_count"],
        "all_semantic_icons_vector_or_native": vectorization_plan["raster_icon_plan_count"] == 0,
        "icons": [
            {
                "object_id": row["object_id"],
                "glyph_kind": row["glyph_kind"],
                "target_kind": row["target_kind"],
                "implementation": row["implementation"],
            }
            for row in vectorization_plan["plans"]
        ],
        "canva_parity_claimed": False,
    }


def icon_vectorization_plan_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Icon Vectorization Plan",
        "",
        f"- Status: `{report['status']}`",
        f"- Required icon plans: `{report['required_icon_plan_count']}`",
        f"- Native vector plans: `{report['native_vector_plan_count']}`",
        f"- Raster icon plans: `{report['raster_icon_plan_count']}`",
        f"- Empty-circle plans: `{report['empty_circle_plan_count']}`",
        "- Broad Canva parity claimed: `False`",
        "",
        "## Glyph Targets",
    ]
    for row in report["plans"]:
        lines.append(f"- `{row['object_id']}` -> `{row['glyph_kind']}` via `{row['implementation']}`")
    return "\n".join(lines)


def semantic_icon_svg_manifest_markdown(report: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Semantic Icon SVG Manifest",
            "",
            f"- Status: `{report['status']}`",
            f"- Native vector icon count: `{report['native_vector_icon_count']}`",
            f"- SVG icon count: `{report['svg_icon_count']}`",
            f"- Semantic icon raster count: `{report['semantic_icon_raster_count']}`",
            f"- All semantic icons vector/native: `{report['all_semantic_icons_vector_or_native']}`",
            "- Broad Canva parity claimed: `False`",
        ]
    )
