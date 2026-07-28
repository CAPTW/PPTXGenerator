"""Codex Desktop observed-crop vision-to-SVG trace contract for E01.4."""

from __future__ import annotations

from typing import Any


TRACE_PROMPT = """Convert this exact icon glyph crop into SVG. Preserve the observed silhouette/strokes.
Do not invent additional objects. Do not add semantic embellishments. Do not include text, raster images, or external references.
Use transparent background and viewBox=\"0 0 24 24\". Prefer currentColor for stroke/fill.
Return SVG markup only."""


def build_observed_icon_parsing_policy_v1() -> dict[str, Any]:
    return {
        "schema_name": "observed_icon_parsing_policy_v1",
        "status": "active",
        "icon_resolution_basis": "observed_shape_not_semantic_role_alone",
        "library_search_first": True,
        "accepted_library_match_types": ["LIBRARY_EXACT_MATCH", "LIBRARY_SHAPE_EQUIVALENT_MATCH"],
        "near_match_accepted": False,
        "vision_trace_required_when_no_exact_match": True,
        "procedural_role_recipe_allowed_for_target_semantic_icon": False,
        "generic_icon_allowed_for_semantic_icon": False,
        "raster_icon_final_fallback_allowed": False,
        "generated_icon_library_persistence_required": True,
        "canva_parity_claimed": False,
    }


def build_vision_svg_trace_request_manifest(exact_match_report: dict[str, Any]) -> dict[str, Any]:
    requests = []
    for match in exact_match_report["matches"]:
        if match["classification"] != "LIBRARY_NO_MATCH_TRACE_REQUIRED":
            continue
        requests.append(
            {
                "crop_id": match["crop_id"],
                "role_hint": match["role_hint"],
                "shape_kind": match["shape_kind"],
                "prompt": TRACE_PROMPT,
                "trace_source": "observed_icon_crop",
                "api_key_required": False,
                "gpt_image_2_used": False,
                "procedural_recipe_fallback_allowed": False,
            }
        )
    return {
        "schema_name": "vision_svg_trace_request_manifest",
        "status": "passed",
        "vision_svg_trace_route": "codex_desktop_vision_svg_trace",
        "request_count": len(requests),
        "requests": requests,
        "blocked_reason": None,
        "canva_parity_claimed": False,
    }
