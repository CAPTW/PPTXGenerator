"""Icon retrieval policy v2 for E03.2.1."""

from __future__ import annotations

from typing import Any


def build_icon_retrieval_policy_v2() -> dict[str, Any]:
    return {
        "schema_name": "icon_retrieval_policy_v2",
        "status": "passed",
        "retrieval_order": [
            "exact_observed_crop_hash_match_in_generated_library",
            "exact_curated_role_and_shape_descriptor_match",
            "curated_role_alias_with_acceptable_shape_match",
            "generated_observed_svg_from_crop_trace",
            "deterministic_manual_svg_for_simple_missing_glyph",
            "blocker_not_generic_fallback",
        ],
        "hard_rules": [
            "no_semantic_raster_fallback",
            "no_generic_p0_fallback",
            "no_silent_role_only_substitution",
            "no_blank_placeholder",
            "every_icon_decision_logged",
        ],
        "generic_p0_fallback_allowed": False,
        "semantic_raster_fallback_allowed": False,
    }
