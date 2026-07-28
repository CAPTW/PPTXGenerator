"""Icon retrieval policy v3 after glyph hygiene."""

from __future__ import annotations

from typing import Any


def build_icon_retrieval_policy_v3() -> dict[str, Any]:
    return {
        "schema_name": "icon_retrieval_policy_v3",
        "status": "passed",
        "retrieval_order": [
            "exact_cleaned_glyph_crop_hash_match",
            "curated_v4_exact_role_and_shape_match",
            "curated_v4_shape_equivalent_match",
            "generated_observed_svg_v2_from_cleaned_crop",
            "human_reviewed_deterministic_manual_svg",
            "blocker",
        ],
        "forbidden": [
            "contaminated_crop_match",
            "role_only_substitution",
            "generic_fallback_for_semantic_icons",
            "raster_fallback",
        ],
        "semantic_raster_fallback_allowed": False,
        "generic_p0_fallback_allowed": False,
        "every_icon_decision_logged": True,
    }
