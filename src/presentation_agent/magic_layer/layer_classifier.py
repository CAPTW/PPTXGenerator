"""Rule-based layer classification for D01 region proposals."""

from __future__ import annotations

from typing import Any

from .layer_schema_v4 import make_layer
from .region_detection import RegionProposal


def semantic_role_for(layer_type: str, archetype_hint: str) -> str:
    roles = {
        "background_base": "canvas_base",
        "source_footer_strip": "source_footer",
        "title_text_region": "title",
        "subtitle_text_region": "subtitle",
        "body_text_region": "body",
        "icon_region": "semantic_or_decorative_icon",
        "chart_region": "chart_or_dashboard",
        "table_region": "table_or_register",
        "matrix_region": "comparison_matrix",
        "hero_visual_field": "hero_or_photo_field",
        "image_frame": "replaceable_image",
        "card_panel": "content_panel",
        "connector": "connector_line",
        "accent_line": "accent_rule",
        "technical_overlay": "technical_overlay",
        "unknown": "unknown",
    }
    return roles.get(layer_type, archetype_hint or "visual_layer")


def target_for(layer_type: str) -> str:
    if layer_type in {"title_text_region", "subtitle_text_region", "body_text_region", "source_footer_strip"}:
        return "ppt_text"
    if layer_type == "icon_region":
        return "svg_vector"
    if layer_type == "chart_region":
        return "editable_chart"
    if layer_type in {"table_region", "matrix_region"}:
        return "editable_table"
    if layer_type in {"hero_visual_field", "image_frame"}:
        return "replaceable_image_frame"
    if layer_type in {"decorative_texture", "shadow_or_glow", "technical_overlay"}:
        return "allowed_decorative_raster"
    if layer_type == "unknown":
        return "unknown_pending_review"
    return "ppt_shape"


def component_identity_candidate_for(layer_type: str, reason: str) -> dict[str, Any]:
    candidates_by_type = {
        "chart_region": ["chart", "dashboard_chart", "editable_shape_chart"],
        "table_region": ["table_grid", "evidence_table", "editable_shape_grid_table"],
        "matrix_region": ["comparison_matrix", "editable_shape_grid_table"],
        "card_panel": ["card_panel", "evidence_card_grid"],
        "icon_region": ["icon", "svg_vector_icon"],
        "connector": ["connector", "process_flow", "timeline_roadmap"],
        "hero_visual_field": ["diagonal_image_mask", "replaceable_image_frame"],
        "image_frame": ["photo_caption_grid", "replaceable_image_frame"],
        "source_footer_strip": ["source_footer_strip"],
        "technical_overlay": ["technical_overlay"],
        "accent_line": ["technical_overlay", "accent_line"],
    }
    candidates = candidates_by_type.get(layer_type, [layer_type])
    return {
        "primary": candidates[0],
        "candidates": candidates,
        "confidence": 0.0 if layer_type == "unknown" else 0.5,
        "promotion_stage": "D03_D04_candidate" if layer_type in candidates_by_type else "review_required",
        "signals": [reason],
        "notes": "D01 candidate only; downstream stages must confirm component identity.",
    }


def classify_proposal(
    proposal: RegionProposal,
    *,
    reference_id: str,
    archetype_hint: str,
    image_width: int,
    image_height: int,
    index: int,
) -> dict[str, Any]:
    x, y, w, h = proposal.bbox_px
    nx, ny, nw, nh = x / image_width, y / image_height, w / image_width, h / image_height
    area = nw * nh
    aspect = w / h if h else 0
    reason = proposal.reason
    layer_type = "unknown"
    content_bearing = False
    unknown_disposition = "review_required"
    confidence = proposal.confidence

    if proposal.proposal_id.endswith("_001") or proposal.reason.startswith("canvas background"):
        layer_type = "background_base"
        confidence = 0.99
        unknown_disposition = "not_unknown"
    elif ny > 0.84 and nw > 0.45:
        layer_type = "source_footer_strip"
        content_bearing = True
        unknown_disposition = "not_unknown"
        confidence = max(confidence, 0.72)
    elif ny < 0.22 and nx < 0.58 and nw > 0.12:
        layer_type = "title_text_region"
        content_bearing = True
        unknown_disposition = "not_unknown"
        confidence = max(confidence, 0.62)
    elif "cover" in archetype_hint and nx < 0.42 and 0.42 < ny < 0.78 and nw > 0.16 and nh < 0.18:
        layer_type = "subtitle_text_region"
        content_bearing = True
        unknown_disposition = "not_unknown"
        confidence = max(confidence, 0.58)
    elif area < 0.012 and 0.55 <= aspect <= 1.9:
        layer_type = "icon_region"
        content_bearing = True
        unknown_disposition = "not_unknown"
        confidence = max(confidence, 0.58)
    elif nh < 0.025 and nw > 0.12:
        layer_type = "accent_line"
        unknown_disposition = "not_unknown"
        confidence = max(confidence, 0.54)
    elif "cover" in archetype_hint and area > 0.08 and nx < 0.55:
        layer_type = "hero_visual_field"
        unknown_disposition = "not_unknown"
        confidence = max(confidence, 0.62)
    elif "dashboard" in archetype_hint and area > 0.05:
        layer_type = "chart_region"
        content_bearing = True
        unknown_disposition = "not_unknown"
        confidence = max(confidence, 0.6)
    elif "table" in archetype_hint and area > 0.05:
        layer_type = "table_region"
        content_bearing = True
        unknown_disposition = "not_unknown"
        confidence = max(confidence, 0.6)
    elif "standard" in archetype_hint and area > 0.035:
        layer_type = "card_panel"
        content_bearing = True
        unknown_disposition = "not_unknown"
        confidence = max(confidence, 0.56)
    elif any(token in archetype_hint for token in ("comparison", "matrix")) and area > 0.015:
        layer_type = "matrix_region"
        content_bearing = True
        unknown_disposition = "not_unknown"
        confidence = max(confidence, 0.58)
    elif any(token in archetype_hint for token in ("risk_register", "register")) and area > 0.015:
        layer_type = "table_region"
        content_bearing = True
        unknown_disposition = "not_unknown"
        confidence = max(confidence, 0.58)
    elif "timeline" in archetype_hint and area > 0.015:
        layer_type = "timeline_phase"
        content_bearing = True
        unknown_disposition = "not_unknown"
        confidence = max(confidence, 0.56)
    elif any(token in archetype_hint for token in ("process", "methodology", "framework")) and area > 0.015:
        layer_type = "process_node"
        content_bearing = True
        unknown_disposition = "not_unknown"
        confidence = max(confidence, 0.56)
    elif any(token in archetype_hint for token in ("toc", "card", "evidence", "decision", "case", "closing", "section_divider")) and area > 0.015:
        layer_type = "card_panel"
        content_bearing = True
        unknown_disposition = "not_unknown"
        confidence = max(confidence, 0.55)
    elif area > 0.04 and aspect > 1.2:
        layer_type = "card_panel"
        content_bearing = "content" in archetype_hint or "standard" in archetype_hint
        unknown_disposition = "not_unknown"
        confidence = max(confidence, 0.55)
    elif area < 0.006 and (aspect > 3.5 or aspect < 0.28):
        layer_type = "connector"
        unknown_disposition = "not_unknown"
        confidence = max(confidence, 0.48)
    elif area < 0.02:
        layer_type = "technical_overlay"
        unknown_disposition = "not_unknown"
        confidence = max(confidence, 0.42)
    else:
        content_bearing = bool(area > 0.015 and ny < 0.82)
        unknown_disposition = "blocking_content_bearing_unknown" if content_bearing else "bounded_decorative_unknown"
        confidence = min(confidence, 0.4)

    raster_policy = "analysis_crop_only"
    if layer_type in {"title_text_region", "subtitle_text_region", "body_text_region", "source_footer_strip", "icon_region", "chart_region", "table_region", "matrix_region"}:
        raster_policy = "semantic_raster_forbidden_final_use"
    elif layer_type in {"hero_visual_field", "image_frame", "decorative_texture", "technical_overlay", "shadow_or_glow"}:
        raster_policy = "scoped_raster_allowed_if_non_semantic"
    elif layer_type == "background_base":
        raster_policy = "no_full_slide_crop"
    elif layer_type == "unknown":
        raster_policy = "reject_or_patch_until_reviewed"

    return make_layer(
        layer_id=f"{reference_id}_layer_{index:03d}",
        reference_id=reference_id,
        archetype_hint=archetype_hint,
        bbox_px=proposal.bbox_px,
        image_width=image_width,
        image_height=image_height,
        layer_type=layer_type,
        semantic_role=semantic_role_for(layer_type, archetype_hint),
        source=proposal.source,
        confidence=confidence,
        content_bearing=content_bearing,
        editability_target=target_for(layer_type),
        raster_policy=raster_policy,
        component_identity_candidate=component_identity_candidate_for(layer_type, reason),
        unknown_disposition=unknown_disposition,
        dependencies=[],
        notes=reason,
    )


def classify_regions(
    proposals: list[RegionProposal],
    *,
    reference_id: str,
    archetype_hint: str,
    image_width: int,
    image_height: int,
) -> list[dict[str, Any]]:
    return [
        classify_proposal(
            proposal,
            reference_id=reference_id,
            archetype_hint=archetype_hint,
            image_width=image_width,
            image_height=image_height,
            index=i,
        )
        for i, proposal in enumerate(proposals, start=1)
    ]
