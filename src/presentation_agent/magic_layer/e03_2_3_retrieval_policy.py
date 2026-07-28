"""Retrieval policy v5 for complex icon-ready library."""

from __future__ import annotations

from typing import Any


def build_icon_retrieval_policy_v5() -> dict[str, Any]:
    return {
        "schema_name": "icon_retrieval_policy_v5",
        "status": "passed",
        "retrieval_order": [
            "curated_v5_exact_role_and_shape_match",
            "cleaned_glyph_crop_hash_match",
            "generated_observed_svg_v2_v3_approved",
            "library_shape_equivalent_match",
            "human_approved_manual_svg",
            "blocker",
        ],
        "forbidden": ["contaminated_crop", "role_only_generic", "raster_fallback", "placeholder_svg"],
        "semantic_raster_fallback_allowed": False,
        "generic_p0_fallback_allowed": False,
    }
