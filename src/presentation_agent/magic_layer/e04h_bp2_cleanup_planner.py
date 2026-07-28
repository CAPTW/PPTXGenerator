"""Plan E04H-BP2 backplate de-duplication cleanup."""

from __future__ import annotations

from typing import Any


def build_bp2_cleanup_plan(
    classification_report: dict[str, Any],
    scaffold_report: dict[str, Any],
    duplicate_chrome_report: dict[str, Any],
) -> dict[str, Any]:
    actions = []
    for row in classification_report.get("classifications", []):
        actions.append(
            {
                "slide_id": row["slide_id"],
                "slide_number": row["slide_number"],
                "selected_reference_id": row["selected_reference_id"],
                "source_clone_layer": row["clone_layer_name"],
                "action": "replace_with_cleaned_nonsemantic_backplate",
                "cleaned_role": row["cleaned_role"],
                "remove_placeholder_boxes": True,
                "remove_duplicate_component_border": True,
                "remove_footer_scaffold": True,
                "preserve_as_bounded_media": True,
                "full_slide_reference_background": False,
                "semantic_raster_allowed": False,
            }
        )
    return {
        "schema_name": "backplate_cleanup_plan",
        "status": "passed" if actions else "failed",
        "replacement_backplate_count": len(actions),
        "remove_scaffold_count": scaffold_report.get("original_scaffold_backplate_count", 0),
        "remove_duplicate_chrome_count": duplicate_chrome_report.get("original_duplicate_chrome_count", 0),
        "preserve_media_backplate_count": len({row["selected_reference_id"] for row in actions}),
        "cleanup_actions": actions,
        "canva_parity_claimed": False,
    }


def build_chrome_ownership_plan() -> dict[str, Any]:
    return {
        "schema_name": "semantic_component_chrome_ownership_plan",
        "status": "passed",
        "rules": [
            "semantic component owns its border, fill, and readable geometry",
            "visual backplate may provide mood, texture, glow, or depth only",
            "native table/chart/card frames are not duplicated by cloned backplates",
            "source/footer rule remains native and editable",
        ],
        "semantic_component_chrome_owner": "semantic_native_component",
        "visual_backplate_allowed_roles": ["atmosphere_texture", "technical_ornament", "subtle_background_depth", "nonsemantic_photo_or_visual_field"],
        "canva_parity_claimed": False,
    }
