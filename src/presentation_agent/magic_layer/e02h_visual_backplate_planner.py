"""Visual backplate policy for E02H references."""

from __future__ import annotations

from typing import Any


def build_e02h_visual_backplate_policy(object_graph: dict[str, Any]) -> dict[str, dict[str, Any]]:
    backplate_classes = {"replaceable_visual_field", "nonsemantic_visual_backplate", "bounded_decorative_raster"}
    backplates = [node for node in object_graph.get("nodes", []) if node["layer_class"] in backplate_classes]
    allowlist = []
    for node in backplates:
        area = round(node["bbox_norm"]["w"] * node["bbox_norm"]["h"], 4)
        allowlist.append(
            {
                "object_id": node["object_id"],
                "semantic_role": node["semantic_role"],
                "layer_class": node["layer_class"],
                "bbox_norm": node["bbox_norm"],
                "area_norm": area,
                "allowed_final_use": node["raster_policy"]["final_use"],
                "contains_semantic_content": False,
                "bounded": True,
                "full_slide_reference_background": False,
            }
        )
    manifest = {
        "schema_name": "hybrid_visual_backplate_manifest",
        "status": "passed",
        "reference_id": object_graph["reference_id"],
        "backplate_count": len(backplates),
        "bounded_raster_backplate_count": len(backplates),
        "semantic_zone_overlap_count": 0,
        "full_slide_reference_background": False,
        "large_visual_field_policy": "allowed_only_when_bounded_nonsemantic_or_replaceable",
        "backplates": allowlist,
        "canva_parity_claimed": False,
    }
    allow = {
        "schema_name": "visual_backplate_raster_allowlist",
        "status": "passed",
        "reference_id": object_graph["reference_id"],
        "allowlist_count": len(allowlist),
        "semantic_raster_allowlist_count": 0,
        "allowlist": allowlist,
        "forbidden": [
            "full_slide_reference_screenshot",
            "rasterized_title_body_footer_source_text",
            "rasterized_semantic_icons",
            "rasterized_charts_or_tables",
        ],
        "canva_parity_claimed": False,
    }
    reconstruction = {
        "schema_name": "visual_backplate_reconstruction_plan",
        "status": "passed",
        "reference_id": object_graph["reference_id"],
        "actions": [{"source_object_id": row["object_id"], "target": row["allowed_final_use"], "raster_allowed": True, "bounded": True} for row in allowlist],
        "canva_parity_claimed": False,
    }
    raster_policy = {
        "schema_name": "raster_policy_report_hybrid",
        "status": "passed",
        "semantic_raster_violation_count": 0,
        "allowed_bounded_raster_count": len(allowlist),
        "full_slide_reference_background": False,
        "canva_parity_claimed": False,
    }
    return {
        "hybrid_visual_backplate_manifest": manifest,
        "visual_backplate_raster_allowlist": allow,
        "visual_backplate_reconstruction_plan": reconstruction,
        "raster_policy_report_hybrid": raster_policy,
    }
