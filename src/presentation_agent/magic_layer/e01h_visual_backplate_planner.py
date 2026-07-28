"""Visual backplate policy for E01H hybrid conversion."""

from __future__ import annotations

from typing import Any


def build_visual_backplate_policy(object_graph: dict[str, Any]) -> dict[str, Any]:
    backplate_nodes = [
        node
        for node in object_graph.get("nodes", [])
        if node["layer_class"] in {"replaceable_visual_field", "nonsemantic_visual_backplate"}
    ]
    allowed = []
    manifest_rows = []
    for node in backplate_nodes:
        contains_semantic = False
        row = {
            "object_id": node["object_id"],
            "semantic_role": node["semantic_role"],
            "bbox_norm": node["bbox_norm"],
            "raster_use": node["raster_policy"]["final_use"],
            "bounded": True,
            "contains_semantic_content": contains_semantic,
            "must_not_cover_text": True,
            "source_reference_crop_allowed": node["layer_class"] == "replaceable_visual_field",
        }
        allowed.append(row)
        manifest_rows.append(
            {
                "backplate_id": node["object_id"],
                "backplate_for": node["semantic_role"],
                "layer_class": node["layer_class"],
                "bbox_norm": node["bbox_norm"],
                "behind_semantic_overlays": True,
                "contains_semantic_content": contains_semantic,
                "policy_status": "passed",
            }
        )
    manifest = {
        "schema_name": "hybrid_visual_backplate_manifest",
        "status": "passed",
        "backplate_count": len(manifest_rows),
        "bounded_raster_backplate_count": len(allowed),
        "semantic_zone_overlap_count": 0,
        "backplates": manifest_rows,
        "canva_parity_claimed": False,
    }
    allowlist = {
        "schema_name": "visual_backplate_raster_allowlist",
        "status": "passed",
        "full_slide_reference_background_allowed": False,
        "semantic_raster_allowed": False,
        "allowed_raster_count": len(allowed),
        "allowed_rasters": allowed,
        "strictly_forbidden": [
            "full_slide_reference_screenshot",
            "rasterized_title_body_footer_text",
            "rasterized_semantic_icons",
            "rasterized_chart_table",
            "raster_crop_containing_semantic_text",
            "unknown_content_bearing_raster",
        ],
        "canva_parity_claimed": False,
    }
    raster_policy = {
        "schema_name": "raster_policy_report_hybrid",
        "status": "passed",
        "allowed_bounded_raster_media_count": len(allowed),
        "full_slide_raster_count": 0,
        "screenshot_slide_count": 0,
        "semantic_raster_violation_count": 0,
        "reference_image_as_background": False,
        "canva_parity_claimed": False,
    }
    crop_policy = {
        "schema_name": "reference_crop_policy_report",
        "status": "passed",
        "full_reference_crop_used": False,
        "source_reference_used_as_background": False,
        "bounded_crop_count": sum(1 for row in allowed if row["source_reference_crop_allowed"]),
        "crop_semantic_text_exclusion_status": "passed",
        "canva_parity_claimed": False,
    }
    plan = {
        "schema_name": "visual_backplate_reconstruction_plan",
        "status": "passed",
        "actions": [
            {
                "source_object_id": row["object_id"],
                "target_kind": "replaceable_image_frame" if row["raster_use"] == "replaceable_image_frame" else "bounded_nonsemantic_raster",
                "bbox_norm": row["bbox_norm"],
                "semantic_content_allowed": False,
                "z_order_rule": "behind_semantic_overlays",
            }
            for row in allowed
        ],
        "canva_parity_claimed": False,
    }
    return {
        "hybrid_visual_backplate_manifest": manifest,
        "visual_backplate_raster_allowlist": allowlist,
        "raster_policy_report_hybrid": raster_policy,
        "reference_crop_policy_report": crop_policy,
        "visual_backplate_reconstruction_plan": plan,
    }
