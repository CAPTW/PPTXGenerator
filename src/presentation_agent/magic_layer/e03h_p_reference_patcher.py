"""Patch weak E03H references into richer hybrid conversion fixtures."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from src.presentation_agent.magic_layer.e01h_hybrid_orchestrator import build_ps_layer_protocol_hybrid
from src.presentation_agent.magic_layer.e02h_hybrid_object_graph_builder import SLIDE_H_PX, SLIDE_W_PX
from src.presentation_agent.magic_layer.e03h_hybrid_object_graph_builder import (
    build_e03h_hybrid_object_graph,
    build_e03h_layer_manifest_v5,
    build_e03h_reference_definition,
    build_e03h_region_ledgers,
    build_e03h_semantic_slot_graph,
    build_e03h_visual_layer_graph,
)
from src.presentation_agent.magic_layer.e03h_reference_generator import (
    build_asset_recipe_manifest,
    build_design_intent_trace,
    build_image_prompt,
    build_reference_analysis_report,
    build_reference_visual_richness_report,
)
from src.presentation_agent.magic_layer.e03h_reference_pack_orchestrator import build_e03h_reference_payload
from src.presentation_agent.magic_layer.e03h_semantic_native_planner import build_e03h_semantic_native_plan
from src.presentation_agent.magic_layer.e03h_text_first_lock import build_e03h_text_first_lock_report
from src.presentation_agent.magic_layer.e03h_visual_backplate_planner import build_e03h_visual_backplate_policy


REGRESSION_IDS = {"maritime_checklist_hero", "process_workflow_infographic", "data_dashboard_hybrid", "table_matrix_hybrid"}
COLORS = {"navy": "041826", "teal": "092D37", "cyan": "39D4E7", "gold": "F3A51A", "white": "F3F7FA", "muted": "B8CBD2", "panel": "061D2A"}


def build_patched_reference_payload(reference_id: str, output_dir: str | Path) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    if reference_id in REGRESSION_IDS:
        payload = build_e03h_reference_payload(reference_id, output)
        payload["patch_action"] = "KEEP_REGRESSION_REFERENCE"
        return payload
    definition = build_patched_reference_definition(reference_id)
    reference_path = output / "reference_image.png"
    generate_premium_reference_image(definition, reference_path)
    analysis = build_reference_analysis_report(definition, reference_path)
    text_lock = build_e03h_text_first_lock_report(definition)
    object_graph = build_e03h_hybrid_object_graph(definition, text_lock)
    backplates = build_e03h_visual_backplate_policy(object_graph)
    semantic_plan = build_e03h_semantic_native_plan(object_graph, reference_id)
    ledgers = build_e03h_region_ledgers(object_graph)
    payload = {
        "schema_name": "e03h_p_reference_payload",
        "status": "passed",
        "reference_id": reference_id,
        "patch_action": "PATCH_REFERENCE",
        "definition": definition,
        "image_prompt": build_image_prompt(definition) + "\n\nE03H-P: strengthen archetype identity, focal object, and bounded visual backplates.",
        "design_intent_trace": build_design_intent_trace(definition),
        "asset_recipe_manifest": build_asset_recipe_manifest(definition),
        "reference_analysis_report": analysis,
        "reference_visual_richness_report": build_reference_visual_richness_report(definition, analysis),
        "text_first_lock_report": text_lock,
        "object_graph_v2": object_graph,
        "layer_manifest_v5": build_e03h_layer_manifest_v5(object_graph),
        "semantic_slot_graph": build_e03h_semantic_slot_graph(object_graph),
        "visual_layer_graph": build_e03h_visual_layer_graph(object_graph),
        **backplates,
        **semantic_plan,
        **ledgers,
        "hybrid_candidate_compile_plan": _compile_plan(reference_id),
        "canva_parity_claimed": False,
    }
    payload["ps_layer_intent_hybrid"] = build_ps_layer_protocol_hybrid(object_graph, analysis, protocol_id=f"e03h_p_{reference_id}_intent")
    payload["ps_layer_as_built_hybrid"] = build_ps_layer_protocol_hybrid(object_graph, analysis, protocol_id=f"e03h_p_{reference_id}_as_built")
    return payload


def build_patched_reference_definition(reference_id: str) -> dict[str, Any]:
    original = build_e03h_reference_definition(reference_id)
    base = {
        **original,
        "reference_source": "e03h_p_local_patched",
        "style_tokens": {"palette": ["#041826", "#092D37", "#39D4E7", "#F3A51A", "#F3F7FA"], "tone": "e03h_p_premium_hybrid_reference"},
    }
    if reference_id == "cover_hero_photo_editorial":
        base["archetype_identity_markers"] = ["editorial_hero", "protected_title_area", "premium_meta_system"]
        base["regions"] = _common(reference_id, "Editorial conversion system") + [
            _region("hero_photo_field", "hero_visual_field", [0.06, 0.18, 0.54, 0.56], "replaceable_visual_field", "smart_object_like_image", 10, richness="editorial_hero_field", premium=True),
            _region("hero_mask_chrome", "decorative_texture", [0.04, 0.15, 0.59, 0.62], "bounded_decorative_raster", "decorative_texture", 11, richness="hero_chrome", premium=True),
            _region("editorial_side_panel", "subtitle_panel", [0.66, 0.20, 0.25, 0.44], "semantic_editable", "panel", 40, content=True),
            _region("subtitle_text", "subtitle_text", [0.69, 0.27, 0.18, 0.10], "semantic_editable", "text", 80, text="Protected text zones over a strong visual anchor", content=True),
            _region("meta_text", "meta_text", [0.69, 0.54, 0.18, 0.04], "semantic_editable", "text", 81, text="Hybrid reference v2", content=True),
            _region("hero_icon", "semantic_icon", [0.69, 0.42, 0.045, 0.08], "semantic_vector", "semantic_icon", 82, glyph="shield", content=True),
        ]
    elif reference_id == "standard_content_card_cluster":
        base["archetype_identity_markers"] = ["rich_card_cluster", "card_chrome", "icon_rhythm"]
        rows = _common(reference_id, "Premium card cluster")
        rows.append(_region("bp_card_stage", "decorative_texture", [0.05, 0.21, 0.78, 0.47], "nonsemantic_visual_backplate", "decorative_texture", 8, richness="card_stage_backplate", premium=True))
        for idx, label in enumerate(["Signal", "Decision", "Action"], start=1):
            x = 0.09 + (idx - 1) * 0.245
            rows.extend([
                _region(f"card_backplate_{idx}", "card_chrome_backplate", [x - 0.015, 0.305, 0.205, 0.30], "bounded_decorative_raster", "decorative_texture", 20 + idx, richness="premium_card_chrome", premium=True),
                _region(f"card_{idx}", "card_panel", [x, 0.32, 0.18, 0.26], "semantic_editable", "card", 40 + idx, content=True),
                _region(f"card_icon_{idx}", "semantic_icon", [x + 0.02, 0.36, 0.04, 0.07], "semantic_vector", "semantic_icon", 60 + idx, glyph=["gauge", "shield", "clipboard"][idx - 1], content=True),
                _region(f"card_text_{idx}", "body_text", [x + 0.075, 0.36, 0.085, 0.09], "semantic_editable", "text", 80 + idx, text=label, content=True),
            ])
        base["regions"] = rows
    elif reference_id == "evidence_stack_visual":
        base["archetype_identity_markers"] = ["claim_focal_region", "evidence_ladder", "source_hierarchy"]
        rows = _common(reference_id, "Evidence-backed conversion claim")
        rows.extend([
            _region("claim_backplate", "claim_focal_backplate", [0.06, 0.20, 0.35, 0.38], "bounded_decorative_raster", "decorative_texture", 10, richness="claim_focal_glow", premium=True),
            _region("claim_panel", "claim_focal_region", [0.08, 0.25, 0.30, 0.23], "semantic_editable", "panel", 40, content=True),
            _region("claim_text", "body_text", [0.105, 0.30, 0.23, 0.09], "semantic_editable", "text", 60, text="Claim: references need layered evidence", content=True),
            _region("evidence_backplate", "evidence_ladder_backplate", [0.46, 0.20, 0.36, 0.44], "nonsemantic_visual_backplate", "decorative_texture", 12, richness="evidence_ladder", premium=True),
            _region("source_hierarchy_backplate", "source_hierarchy_backplate", [0.08, 0.58, 0.74, 0.08], "bounded_decorative_raster", "decorative_texture", 13, richness="source_hierarchy", premium=True),
        ])
        for idx in range(1, 4):
            y = 0.27 + (idx - 1) * 0.115
            rows.extend([
                _region(f"evidence_card_{idx}", "evidence_card", [0.49, y, 0.29, 0.08], "semantic_editable", "card", 70 + idx, content=True),
                _region(f"evidence_icon_{idx}", "semantic_icon", [0.505, y + 0.018, 0.025, 0.045], "semantic_vector", "semantic_icon", 80 + idx, glyph="document", content=True),
                _region(f"evidence_text_{idx}", "body_text", [0.545, y + 0.02, 0.18, 0.035], "semantic_editable", "text", 90 + idx, text=f"Evidence layer {idx}", content=True),
            ])
        base["regions"] = rows
    elif reference_id == "comparison_matrix_hybrid":
        base["archetype_identity_markers"] = ["matrix_identity", "header_hierarchy", "native_table"]
        rows = _common(reference_id, "Comparison matrix")
        rows.extend([
            _region("matrix_backplate", "matrix_backplate", [0.055, 0.18, 0.70, 0.58], "nonsemantic_visual_backplate", "decorative_texture", 10, richness="premium_matrix_backplate", premium=True),
            _region("table_header_band", "table_header_band", [0.08, 0.22, 0.64, 0.075], "semantic_editable", "panel", 40, content=True),
            _region("table_matrix", "table_matrix", [0.08, 0.295, 0.64, 0.43], "semantic_native_component", "table", 70, content=True, target="native_table", data={"headers": ["Option", "Fit", "Risk", "Next"], "rows": [["A", "High", "Low", "Use"], ["B", "Med", "Med", "Watch"], ["C", "Low", "High", "Hold"]]}),
            _region("matrix_insight", "insight_text", [0.78, 0.32, 0.14, 0.14], "semantic_editable", "text", 100, text="Editable matrix with header hierarchy.", content=True),
        ])
        base["regions"] = rows
    elif reference_id == "methodology_framework_layered":
        base["archetype_identity_markers"] = ["layered_stack", "connector_logic", "framework_brackets"]
        rows = _common(reference_id, "Layered methodology framework")
        rows.append(_region("framework_backplate", "framework_stack_backplate", [0.08, 0.19, 0.75, 0.50], "nonsemantic_visual_backplate", "decorative_texture", 10, richness="layered_stack_backplate", premium=True))
        for idx, label in enumerate(["Input", "Model", "Compile", "Validate"], start=1):
            y = 0.235 + (idx - 1) * 0.105
            rows.extend([
                _region(f"method_layer_backplate_{idx}", "layer_chrome", [0.15 + idx * 0.04, y - 0.012, 0.48, 0.09], "bounded_decorative_raster", "decorative_texture", 20 + idx, richness="framework_layer_chrome", premium=True),
                _region(f"method_layer_{idx}", "process_node_panel", [0.17 + idx * 0.04, y, 0.44, 0.065], "semantic_editable", "card", 50 + idx, content=True),
                _region(f"method_text_{idx}", "process_node_text", [0.23 + idx * 0.04, y + 0.02, 0.20, 0.03], "semantic_editable", "text", 70 + idx, text=label, content=True),
            ])
            if idx < 4:
                rows.append(_region(f"method_connector_{idx}", "process_connector", [0.64, y + 0.055, 0.08, 0.04], "semantic_vector", "connector", 90 + idx, content=True, target="ppt_connector"))
        base["regions"] = rows
    elif reference_id == "timeline_roadmap_hybrid":
        base["archetype_identity_markers"] = ["timeline_rail", "phase_hierarchy", "milestone_sequence"]
        rows = _common(reference_id, "Roadmap with phase hierarchy")
        rows.extend([
            _region("timeline_backplate", "timeline_backplate", [0.06, 0.25, 0.84, 0.36], "nonsemantic_visual_backplate", "decorative_texture", 10, richness="timeline_phase_backplate", premium=True),
            _region("timeline_phase_band", "timeline_phase_band", [0.09, 0.34, 0.76, 0.06], "bounded_decorative_raster", "decorative_texture", 11, richness="phase_hierarchy_band", premium=True),
        ])
        for idx, label in enumerate(["Q1", "Q2", "Q3", "Q4", "Q5"], start=1):
            x = 0.11 + (idx - 1) * 0.155
            rows.extend([
                _region(f"milestone_{idx}", "timeline_milestone", [x, 0.43, 0.07, 0.11], "semantic_editable", "card", 40 + idx, content=True),
                _region(f"milestone_text_{idx}", "milestone_text", [x + 0.014, 0.46, 0.04, 0.035], "semantic_editable", "text", 60 + idx, text=label, content=True),
            ])
            if idx < 5:
                rows.append(_region(f"timeline_connector_{idx}", "timeline_connector", [x + 0.07, 0.475, 0.085, 0.018], "semantic_vector", "connector", 80 + idx, content=True, target="ppt_connector"))
        base["regions"] = rows
    elif reference_id == "visual_toc_navigation":
        base["archetype_identity_markers"] = ["navigation_system", "active_marker", "section_rhythm"]
        rows = _common(reference_id, "Navigation map")
        rows.append(_region("toc_backplate", "navigation_backplate", [0.12, 0.19, 0.68, 0.54], "nonsemantic_visual_backplate", "decorative_texture", 10, richness="navigation_system_backplate", premium=True))
        for idx, label in enumerate(["Context", "Evidence", "System", "Decision", "Roadmap"], start=1):
            y = 0.225 + (idx - 1) * 0.09
            rows.extend([
                _region(f"toc_item_{idx}", "navigation_item", [0.18, y, 0.50, 0.062], "semantic_editable", "card", 30 + idx, content=True),
                _region(f"toc_icon_{idx}", "semantic_icon", [0.195, y + 0.011, 0.025, 0.045], "semantic_vector", "semantic_icon", 50 + idx, glyph="gauge" if idx == 1 else "shield", content=True),
                _region(f"toc_text_{idx}", "body_text", [0.24, y + 0.018, 0.18, 0.03], "semantic_editable", "text", 70 + idx, text=label, content=True),
            ])
        rows.append(_region("toc_active_marker", "active_current_marker", [0.15, 0.225, 0.018, 0.062], "bounded_decorative_raster", "decorative_texture", 95, richness="active_marker", premium=True))
        base["regions"] = rows
    elif reference_id == "photo_caption_grid_hybrid":
        base["archetype_identity_markers"] = ["photo_grid", "editable_captions", "bounded_image_frames"]
        rows = _common(reference_id, "Photo caption grid")
        rows.append(_region("photo_grid_backplate", "photo_grid_backplate", [0.06, 0.18, 0.72, 0.58], "nonsemantic_visual_backplate", "decorative_texture", 10, richness="photo_grid_stage", premium=True))
        for idx, label in enumerate(["Field", "Detail", "Team", "Evidence"], start=1):
            x = 0.10 + ((idx - 1) % 2) * 0.33
            y = 0.23 + ((idx - 1) // 2) * 0.25
            rows.extend([
                _region(f"photo_frame_{idx}", "thumbnail_visual_field", [x, y, 0.25, 0.15], "replaceable_visual_field", "smart_object_like_image", 30 + idx, richness="rich_photo_placeholder", premium=True),
                _region(f"photo_frame_chrome_{idx}", "image_frame_chrome", [x - 0.01, y - 0.01, 0.27, 0.17], "bounded_decorative_raster", "decorative_texture", 40 + idx, richness="rich_image_frame", premium=True),
                _region(f"caption_{idx}", "thumbnail_caption_text", [x, y + 0.17, 0.22, 0.035], "semantic_editable", "text", 70 + idx, text=label, content=True),
            ])
        base["regions"] = rows
    else:
        return original
    return base


def generate_premium_reference_image(definition: dict[str, Any], output_path: str | Path) -> dict[str, Any]:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (SLIDE_W_PX, SLIDE_H_PX), f"#{COLORS['navy']}")
    draw = ImageDraw.Draw(image, "RGBA")
    _draw_global_texture(draw)
    for region in sorted(definition["regions"], key=lambda row: row["z_order"]):
        bbox = _px(region["bbox_norm"])
        if region["object_type"] == "background_base":
            continue
        if region["layer_class"] == "replaceable_visual_field":
            _draw_visual_field(draw, bbox, region.get("visual_richness"))
        elif region["layer_class"] in {"nonsemantic_visual_backplate", "bounded_decorative_raster"}:
            _draw_backplate(draw, bbox, region.get("visual_richness"))
        elif region["object_type"] in {"card", "panel"}:
            draw.rounded_rectangle(bbox, radius=16, fill=(*_rgb(COLORS["panel"]), 220), outline=(*_rgb(COLORS["cyan"]), 180), width=2)
        elif region["object_type"] == "connector":
            x1, y1, x2, y2 = bbox
            ymid = (y1 + y2) // 2
            draw.line((x1, ymid, x2, ymid), fill=(*_rgb(COLORS["cyan"]), 235), width=4)
            draw.polygon([(x2, ymid), (x2 - 12, ymid - 7), (x2 - 12, ymid + 7)], fill=(*_rgb(COLORS["cyan"]), 235))
        elif region["object_type"] == "semantic_icon":
            _draw_icon(draw, bbox)
        elif region["object_type"] == "table":
            _draw_table(draw, bbox)
        elif region["object_type"] == "chart":
            _draw_chart(draw, bbox)
        elif region["object_type"] == "text":
            _draw_text(draw, bbox[0], bbox[1], region.get("text") or region["semantic_role"], 18 if region["semantic_role"] == "title_text" else 9, COLORS["white"], bold=region["semantic_role"] == "title_text")
    draw.line((0, 790, 1600, 790), fill=(*_rgb(COLORS["gold"]), 230), width=3)
    image.save(output)
    return {"schema_name": "reference_generation_report", "status": "passed", "reference_image": output.as_posix(), "local_generation": "deterministic_pil_e03h_p", "image_api_used": False, "canva_parity_claimed": False}


def _common(reference_id: str, title: str) -> list[dict[str, Any]]:
    return [
        _region("bg_base", "background_base", [0, 0, 1, 1], "decorative_vector", "background_base", 0),
        _region("title_text", "title_text", [0.055, 0.055, 0.68, 0.07], "semantic_editable", "text", 50, text=title, content=True),
        _region("footer_source_text", "footer_source_text", [0.055, 0.86, 0.80, 0.04], "semantic_editable", "text", 180, text=f"Source: {reference_id.replace('_', ' ')} reference fixture", content=True),
    ]


def _region(object_id: str, role: str, bbox: list[float], layer_class: str, object_type: str, z: int, *, text: str | None = None, content: bool = False, glyph: str | None = None, data: dict[str, Any] | None = None, target: str | None = None, richness: str | None = None, premium: bool = False) -> dict[str, Any]:
    return {
        "object_id": object_id,
        "semantic_role": role,
        "bbox_norm": {"x": bbox[0], "y": bbox[1], "w": bbox[2], "h": bbox[3]},
        "layer_class": layer_class,
        "object_type": object_type,
        "z_order": z,
        "text": text,
        "content_bearing": content,
        "glyph_kind": glyph,
        "data": data,
        "editability_target": target,
        "visual_richness": richness,
        "premium_visual": premium,
        "confidence": 0.94,
    }


def _compile_plan(reference_id: str) -> dict[str, Any]:
    return {"schema_name": "hybrid_candidate_compile_plan", "status": "passed", "reference_id": reference_id, "rules": ["semantic layers native", "bounded richer visual backplates", "full reference background forbidden"], "canva_parity_claimed": False}


def _draw_global_texture(draw: ImageDraw.ImageDraw) -> None:
    for x in range(0, SLIDE_W_PX, 72):
        draw.line((x, 0, x, SLIDE_H_PX), fill=(*_rgb(COLORS["teal"]), 38), width=1)
    for y in range(0, SLIDE_H_PX, 72):
        draw.line((0, y, SLIDE_W_PX, y), fill=(*_rgb(COLORS["teal"]), 38), width=1)


def _draw_visual_field(draw: ImageDraw.ImageDraw, bbox: tuple[int, int, int, int], richness: str | None) -> None:
    x1, y1, x2, y2 = bbox
    draw.rounded_rectangle(bbox, radius=24, fill=(*_rgb(COLORS["teal"]), 210), outline=(*_rgb(COLORS["gold"]), 180), width=3)
    for idx in range(7):
        offset = idx * 34
        draw.arc((x1 - 60 + offset, y1 + 20, x2 + 80 + offset, y2 + 160), start=190, end=330, fill=(*_rgb(COLORS["cyan"]), 90), width=3)
    for idx in range(10):
        cx = x1 + 35 + idx * max(22, (x2 - x1) // 12)
        cy = y1 + 28 + (idx % 3) * 24
        draw.ellipse((cx, cy, cx + 8, cy + 8), fill=(*_rgb(COLORS["gold"]), 150))
    if richness == "editorial_hero_field":
        draw.polygon([(x1 + 40, y2 - 40), (x1 + 180, y1 + 80), (x2 - 80, y2 - 70)], outline=(*_rgb(COLORS["cyan"]), 140), fill=(*_rgb(COLORS["cyan"]), 35))


def _draw_backplate(draw: ImageDraw.ImageDraw, bbox: tuple[int, int, int, int], richness: str | None) -> None:
    draw.rounded_rectangle(bbox, radius=22, fill=(*_rgb(COLORS["teal"]), 130), outline=(*_rgb(COLORS["cyan"]), 85), width=2)
    x1, y1, x2, y2 = bbox
    for idx in range(5):
        x = x1 + 22 + idx * 44
        draw.ellipse((x, y2 - 42, x + 9, y2 - 33), outline=(*_rgb(COLORS["gold"]), 120), width=2)
    if richness:
        draw.line((x1 + 18, y1 + 18, x2 - 18, y1 + 18), fill=(*_rgb(COLORS["gold"]), 140), width=2)


def _draw_icon(draw: ImageDraw.ImageDraw, bbox: tuple[int, int, int, int]) -> None:
    x1, y1, x2, y2 = bbox
    s = min(x2 - x1, y2 - y1)
    draw.ellipse((x1, y1, x1 + s, y1 + s), outline=(*_rgb(COLORS["cyan"]), 230), width=max(2, s // 14))
    draw.line((x1 + s * 0.28, y1 + s * 0.55, x1 + s * 0.46, y1 + s * 0.70, x1 + s * 0.72, y1 + s * 0.32), fill=(*_rgb(COLORS["cyan"]), 230), width=max(2, s // 18))


def _draw_table(draw: ImageDraw.ImageDraw, bbox: tuple[int, int, int, int]) -> None:
    draw.rounded_rectangle(bbox, radius=10, fill=(*_rgb(COLORS["panel"]), 235), outline=(*_rgb(COLORS["cyan"]), 210), width=2)
    x1, y1, x2, y2 = bbox
    for col in range(1, 4):
        x = x1 + round((x2 - x1) * col / 4)
        draw.line((x, y1, x, y2), fill=(*_rgb(COLORS["cyan"]), 115), width=2)
    for row in range(1, 5):
        y = y1 + round((y2 - y1) * row / 5)
        draw.line((x1, y, x2, y), fill=(*_rgb(COLORS["gold"] if row == 1 else COLORS["cyan"]), 140), width=3 if row == 1 else 2)


def _draw_chart(draw: ImageDraw.ImageDraw, bbox: tuple[int, int, int, int]) -> None:
    draw.rounded_rectangle(bbox, radius=16, fill=(*_rgb(COLORS["panel"]), 235), outline=(*_rgb(COLORS["cyan"]), 210), width=2)


def _draw_text(draw: ImageDraw.ImageDraw, x: int, y: int, text: str, size: int, color: str, *, bold: bool) -> None:
    try:
        font = ImageFont.truetype("arialbd.ttf" if bold else "arial.ttf", max(8, size * 2))
    except OSError:
        font = ImageFont.load_default()
    draw.multiline_text((x, y), text, fill=(*_rgb(color), 255), font=font, spacing=4)


def _px(bbox: dict[str, float]) -> tuple[int, int, int, int]:
    return (round(bbox["x"] * SLIDE_W_PX), round(bbox["y"] * SLIDE_H_PX), round((bbox["x"] + bbox["w"]) * SLIDE_W_PX), round((bbox["y"] + bbox["h"]) * SLIDE_H_PX))


def _rgb(hex_color: str) -> tuple[int, int, int]:
    return tuple(int(hex_color[index : index + 2], 16) for index in (0, 2, 4))
