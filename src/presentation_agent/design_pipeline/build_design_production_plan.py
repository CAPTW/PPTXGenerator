"""Build production planning artifacts from a manual Codex design board."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from ..generator_contracts import (
    validateDesignBrief,
    validateExtractedComponentLibrary,
    validateExtractedDesignBoardCodex,
    validateExtractedSlideArchetypes,
    validateExtractedStyleTokens,
    validatePresentationPlan,
)


DEFAULT_PROMPT = Path("design_prompts/creative_academic_template_board.prompt.txt")
DEFAULT_PROMPT_MANIFEST = Path("design_prompts/prompt_manifest.json")
DEFAULT_BOARD_MANIFEST = Path("outputs/template_design_board/template_design_board_manifest.json")
DEFAULT_CROP_MANIFEST = Path("outputs/template_design_board/design_board_crop_manifest.json")
DEFAULT_DESIGN_BOARD = Path("outputs/design_extraction/extracted_design_board.codex.json")
DEFAULT_ARCHETYPES = Path("outputs/design_extraction/extracted_slide_archetypes.json")
DEFAULT_COMPONENTS = Path("outputs/design_extraction/extracted_component_library.json")
DEFAULT_STYLE_TOKENS = Path("outputs/design_extraction/extracted_style_tokens.json")
DEFAULT_DESIGN_BRIEF = Path("outputs/design_brief.json")
DEFAULT_PRESENTATION_PLAN = Path("outputs/presentation_plan.json")
DEFAULT_OUTPUT_DIR = Path("outputs/design_planning")


LAYOUT_FAMILY_SPECS: list[dict[str, Any]] = [
    {
        "family_id": "expressive_cover_divider",
        "label": "expressive cover / divider",
        "source_prompt_slide_types": ["creative_cover", "section_divider"],
        "fallback_layout": "layout-board-creative_cover",
        "variation_rules": ["Alternate hero marker scale and section-number prominence.", "Use stronger ornament only on opening and section breaks."],
    },
    {
        "family_id": "visual_toc_navigation",
        "label": "visual TOC / navigation",
        "source_prompt_slide_types": ["visual_table_of_contents"],
        "fallback_layout": "layout-board-visual_table_of_contents",
        "variation_rules": ["Rotate index tab emphasis by section.", "Keep navigation compact in large decks."],
    },
    {
        "family_id": "evidence_overview",
        "label": "evidence overview",
        "source_prompt_slide_types": ["research_overview", "literature_map"],
        "fallback_layout": "layout-board-research_overview",
        "variation_rules": ["Alternate evidence cards with relationship maps.", "Preserve citation footer on evidence-heavy slides."],
    },
    {
        "family_id": "problem_research_gap",
        "label": "problem / research gap",
        "source_prompt_slide_types": ["problem_statement", "research_gap"],
        "fallback_layout": "layout-board-problem_statement",
        "variation_rules": ["Use contrast bands for problem framing.", "Use insight callouts for gap language."],
    },
    {
        "family_id": "methodology_framework",
        "label": "methodology / framework",
        "source_prompt_slide_types": ["methodology_framework"],
        "fallback_layout": "layout-board-methodology_framework",
        "variation_rules": ["Use layered diagrams for methods.", "Reduce decorative connectors on dense slides."],
    },
    {
        "family_id": "technical_flow_process",
        "label": "technical flow / process",
        "source_prompt_slide_types": ["technical_flow_chart", "work_support_sequence", "circular_process", "timeline_roadmap"],
        "fallback_layout": "layout-board-technical_flow_chart",
        "variation_rules": ["Rotate flow, sequence, radial, and timeline forms.", "Keep connectors editable as lines or SVG ornaments."],
    },
    {
        "family_id": "comparison_matrix",
        "label": "comparison / matrix",
        "source_prompt_slide_types": ["comparison_matrix", "concept_relationship_venn", "three_level_explanation"],
        "fallback_layout": "layout-board-comparison_matrix",
        "variation_rules": ["Alternate matrix, Venn, and card-stack explanation patterns.", "Use table modules for high-density comparisons."],
    },
    {
        "family_id": "kpi_dashboard",
        "label": "KPI / dashboard",
        "source_prompt_slide_types": ["kpi_donut_chart"],
        "fallback_layout": "layout-board-kpi_donut_chart",
        "variation_rules": ["Use KPI cards plus chart frames.", "Avoid rasterized charts; rebuild as PPT chart or editable shape chart."],
    },
    {
        "family_id": "table_appendix",
        "label": "table / appendix",
        "source_prompt_slide_types": ["data_table_appendix"],
        "fallback_layout": "layout-board-data_table_appendix",
        "variation_rules": ["Use thin grid tables.", "Cap rows and move overflow to appendix rhythm."],
    },
    {
        "family_id": "closing_recommendation",
        "label": "closing / recommendation",
        "source_prompt_slide_types": ["photo_caption_grid"],
        "fallback_layout": "layout-board-photo_caption_grid",
        "variation_rules": ["Use photo/caption layouts only with declared image frames.", "Use recommendation cards when no approved photo exists."],
    },
]


COMPONENT_PRIMITIVES = {
    "footer_system": "PPT shape + PPT text",
    "index_navigation": "PPT shape + PPT text",
    "section_tabs": "PPT shape + PPT text",
    "cards": "PPT shape + PPT text",
    "kpi_cards": "PPT shape + PPT text + editable shape chart",
    "quote_blocks": "PPT shape + PPT text",
    "insight_blocks": "PPT shape + PPT text",
    "diagram_nodes": "PPT shape + PPT text",
    "process_arrows": "PPT line/connector or SVG ornament",
    "radial_maps": "PPT shape group",
    "timeline_blocks": "PPT shape + PPT text + connector",
    "table_modules": "PPT table",
    "chart_modules": "PPT chart or editable shape chart",
    "photo_masks": "photo-frame image",
    "diagonal_panels": "PPT shape + photo-frame image",
    "background_ornaments": "SVG ornament or PPT line/shape group",
    "icon_style": "SVG ornament",
    "connector_style": "PPT line/connector",
}


def build_design_production_plan(
    *,
    prompt_text: str,
    prompt_manifest: dict[str, Any],
    board_manifest: dict[str, Any],
    crop_manifest: dict[str, Any],
    extracted_design_board: dict[str, Any],
    extracted_slide_archetypes: dict[str, Any],
    extracted_component_library: dict[str, Any],
    extracted_style_tokens: dict[str, Any],
    design_brief: dict[str, Any] | None = None,
    presentation_plan: dict[str, Any] | None = None,
    paths: dict[str, str] | None = None,
) -> dict[str, dict[str, Any]]:
    validateExtractedDesignBoardCodex(extracted_design_board)
    validateExtractedSlideArchetypes(extracted_slide_archetypes)
    validateExtractedComponentLibrary(extracted_component_library)
    validateExtractedStyleTokens(extracted_style_tokens)
    if design_brief is not None:
        validateDesignBrief(design_brief)
    if presentation_plan is not None:
        validatePresentationPlan(presentation_plan)

    prompt = _prompt_entry(prompt_manifest, board_manifest.get("prompt_id") or extracted_design_board["prompt_id"])
    archetypes = extracted_slide_archetypes.get("archetypes") or []
    crops_by_role = {str(crop.get("crop_role")): crop for crop in crop_manifest.get("crops") or [] if isinstance(crop, dict)}
    component_translation_plan = _component_translation_plan(
        prompt=prompt,
        board_manifest=board_manifest,
        crop_manifest=crop_manifest,
        component_library=extracted_component_library,
        style_tokens=extracted_style_tokens,
        crops_by_role=crops_by_role,
        paths=paths or {},
    )
    layout_family_plan = _layout_family_plan(archetypes, crops_by_role, component_translation_plan)
    deck_scale_usage_plan = _deck_scale_usage_plan(extracted_style_tokens, design_brief, presentation_plan)
    visual_fidelity_targets = _visual_fidelity_targets(archetypes, component_translation_plan, layout_family_plan, extracted_style_tokens)
    for plan in (layout_family_plan, deck_scale_usage_plan, visual_fidelity_targets):
        plan["prompt_id"] = prompt["prompt_id"]
    reading_report = _design_board_reading_report(
        prompt_text=prompt_text,
        prompt=prompt,
        board_manifest=board_manifest,
        crop_manifest=crop_manifest,
        design_board=extracted_design_board,
        style_tokens=extracted_style_tokens,
        layout_family_plan=layout_family_plan,
        visual_fidelity_targets=visual_fidelity_targets,
        paths=paths or {},
    )
    template_production_plan = _template_production_plan(
        prompt=prompt,
        board_manifest=board_manifest,
        design_board=extracted_design_board,
        component_translation_plan=component_translation_plan,
        layout_family_plan=layout_family_plan,
        deck_scale_usage_plan=deck_scale_usage_plan,
        visual_fidelity_targets=visual_fidelity_targets,
        design_brief=design_brief,
        presentation_plan=presentation_plan,
        paths=paths or {},
    )
    return {
        "design_board_reading_report": reading_report,
        "template_production_plan": template_production_plan,
        "component_translation_plan": component_translation_plan,
        "layout_family_plan": layout_family_plan,
        "deck_scale_usage_plan": deck_scale_usage_plan,
        "visual_fidelity_targets": visual_fidelity_targets,
    }


def build_design_production_plan_from_files(
    *,
    prompt_path: str | Path = DEFAULT_PROMPT,
    prompt_manifest_path: str | Path = DEFAULT_PROMPT_MANIFEST,
    board_manifest_path: str | Path = DEFAULT_BOARD_MANIFEST,
    crop_manifest_path: str | Path = DEFAULT_CROP_MANIFEST,
    extracted_design_board_path: str | Path = DEFAULT_DESIGN_BOARD,
    extracted_slide_archetypes_path: str | Path = DEFAULT_ARCHETYPES,
    extracted_component_library_path: str | Path = DEFAULT_COMPONENTS,
    extracted_style_tokens_path: str | Path = DEFAULT_STYLE_TOKENS,
    design_brief_path: str | Path = DEFAULT_DESIGN_BRIEF,
    presentation_plan_path: str | Path = DEFAULT_PRESENTATION_PLAN,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Path]:
    prompt_file = Path(prompt_path)
    prompt_manifest_file = Path(prompt_manifest_path)
    board_manifest_file = Path(board_manifest_path)
    crop_manifest_file = Path(crop_manifest_path)
    design_board_file = Path(extracted_design_board_path)
    archetypes_file = Path(extracted_slide_archetypes_path)
    component_file = Path(extracted_component_library_path)
    style_file = Path(extracted_style_tokens_path)
    output = Path(output_dir)

    prompt_text = prompt_file.read_text(encoding="utf-8")
    paths = {
        "canonical_prompt": prompt_file.as_posix(),
        "prompt_manifest": prompt_manifest_file.as_posix(),
        "board_manifest": board_manifest_file.as_posix(),
        "crop_manifest": crop_manifest_file.as_posix(),
        "extracted_design_board": design_board_file.as_posix(),
        "extracted_slide_archetypes": archetypes_file.as_posix(),
        "extracted_component_library": component_file.as_posix(),
        "extracted_style_tokens": style_file.as_posix(),
    }
    plans = build_design_production_plan(
        prompt_text=prompt_text,
        prompt_manifest=_load_json(prompt_manifest_file),
        board_manifest=_load_json(board_manifest_file),
        crop_manifest=_load_json(crop_manifest_file),
        extracted_design_board=_load_json(design_board_file),
        extracted_slide_archetypes=_load_json(archetypes_file),
        extracted_component_library=_load_json(component_file),
        extracted_style_tokens=_load_json(style_file),
        design_brief=_load_optional_valid_json(design_brief_path, validateDesignBrief),
        presentation_plan=_load_optional_valid_json(presentation_plan_path, validatePresentationPlan),
        paths=paths,
    )

    output.mkdir(parents=True, exist_ok=True)
    written = {
        "design_board_reading_report_json": output / "design_board_reading_report.json",
        "design_board_reading_report_md": output / "design_board_reading_report.md",
        "template_production_plan_json": output / "template_production_plan.json",
        "template_production_plan_md": output / "template_production_plan.md",
        "component_translation_plan_json": output / "component_translation_plan.json",
        "layout_family_plan_json": output / "layout_family_plan.json",
        "deck_scale_usage_plan_json": output / "deck_scale_usage_plan.json",
        "visual_fidelity_targets_json": output / "visual_fidelity_targets.json",
    }
    _write_json(written["design_board_reading_report_json"], plans["design_board_reading_report"])
    written["design_board_reading_report_md"].write_text(_reading_report_md(plans["design_board_reading_report"]), encoding="utf-8")
    _write_json(written["template_production_plan_json"], plans["template_production_plan"])
    written["template_production_plan_md"].write_text(_template_plan_md(plans["template_production_plan"]), encoding="utf-8")
    _write_json(written["component_translation_plan_json"], plans["component_translation_plan"])
    _write_json(written["layout_family_plan_json"], plans["layout_family_plan"])
    _write_json(written["deck_scale_usage_plan_json"], plans["deck_scale_usage_plan"])
    _write_json(written["visual_fidelity_targets_json"], plans["visual_fidelity_targets"])
    return written


def _design_board_reading_report(
    *,
    prompt_text: str,
    prompt: dict[str, Any],
    board_manifest: dict[str, Any],
    crop_manifest: dict[str, Any],
    design_board: dict[str, Any],
    style_tokens: dict[str, Any],
    layout_family_plan: dict[str, Any],
    visual_fidelity_targets: dict[str, Any],
    paths: dict[str, str],
) -> dict[str, Any]:
    motifs = design_board.get("motif_system") or {}
    layout_principles = design_board.get("layout_principles") or {}
    return {
        "schema_name": "design_board_reading_report",
        "schema_version": "1.0",
        "prompt_id": prompt["prompt_id"],
        "canonical_prompt_path": paths.get("canonical_prompt"),
        "prompt_manifest_path": paths.get("prompt_manifest"),
        "board_manifest_path": paths.get("board_manifest"),
        "crop_manifest_path": paths.get("crop_manifest"),
        "board_image_path": board_manifest.get("board_image_path"),
        "generation_mode": board_manifest.get("generation_mode"),
        "reference_only": True,
        "prompt_character_count": len(prompt_text),
        "board_crop_count": crop_manifest.get("crop_count", len(crop_manifest.get("crops") or [])),
        "design_thesis": _sentence(
            design_board.get("global_visual_language"),
            "A premium creative-academic template board that combines editorial navigation, evidence cards, diagram modules, and structured data frames.",
        ),
        "global_visual_identity": design_board.get("global_visual_language"),
        "creative_academic_balance": {
            "design_balance": board_manifest.get("design_balance") or design_board.get("design_balance") or prompt.get("design_balance"),
            "dominant_tone": "creative",
            "supporting_tones": ["academic", "professional", "informative"],
        },
        "main_motif_system": motifs,
        "grid_logic": {
            "source": "master_layout_system crop and extracted layout_principles",
            "principles": layout_principles,
            "safe_margins_required": True,
            "internal_slide_ratio": board_manifest.get("expected_internal_slide_ratio"),
        },
        "editorial_rhythm": {
            "section_flow": ["expressive opener", "navigation", "evidence overview", "analysis modules", "data/table module", "recommendation/close"],
            "family_count": len(layout_family_plan.get("families") or []),
            "large_deck_rotation_required": True,
        },
        "technical_diagram_language": {
            "editable_primitives": ["PPT connectors", "PPT shapes", "SVG ornaments", "editable labels"],
            "motifs": _as_list(motifs.get("technical") if isinstance(motifs, dict) else motifs),
        },
        "information_hierarchy_strategy": {
            "title_zone_priority": "strong title and section marker hierarchy",
            "body_strategy": "chunk source content into slots, cards, tables, charts, and diagrams",
            "footer_strategy": "persistent citation/source strip and section metadata",
            "density_strategy": design_board.get("density_profile"),
        },
        "must_preserve": [
            "creative-academic visual balance",
            "design-board-derived layout families",
            "footer/citation system",
            "editable topology/grid ornaments",
            "distinct tone variants",
            "chart/table/card systems as editable components",
        ],
        "can_simplify_for_editable_ppt": [
            "micro texture and tiny thumbnail details",
            "complex shadows",
            "decorative topology line density",
            "photo masks when no approved photo asset is present",
        ],
        "must_not_copy_literally": [
            "design board image pixels",
            "thumbnail screenshots as slide backgrounds",
            "rasterized paragraphs, charts, or tables",
            "illegible decorative text from the reference board",
        ],
        "visual_fidelity_target_summary": visual_fidelity_targets["summary"],
    }


def _template_production_plan(
    *,
    prompt: dict[str, Any],
    board_manifest: dict[str, Any],
    design_board: dict[str, Any],
    component_translation_plan: dict[str, Any],
    layout_family_plan: dict[str, Any],
    deck_scale_usage_plan: dict[str, Any],
    visual_fidelity_targets: dict[str, Any],
    design_brief: dict[str, Any] | None,
    presentation_plan: dict[str, Any] | None,
    paths: dict[str, str],
) -> dict[str, Any]:
    return {
        "schema_name": "template_production_plan",
        "schema_version": "1.0",
        "prompt_id": prompt["prompt_id"],
        "board_manifest_path": paths.get("board_manifest"),
        "board_image_path": board_manifest.get("board_image_path"),
        "production_mode": "manual_codex_design_reference_to_editable_ppt",
        "reference_only_policy": {
            "do_not_insert_design_board_image": True,
            "do_not_use_full_slide_raster_background": True,
            "editable_text_required": True,
            "editable_tables_required": True,
            "editable_charts_required": True,
            "photo_images_only_inside_declared_frames": True,
        },
        "deck_context": {
            "topic": (design_brief or {}).get("topic") or (presentation_plan or {}).get("deck_title"),
            "audience": (design_brief or {}).get("audience") or (presentation_plan or {}).get("audience"),
            "tone": (design_brief or {}).get("tone") or (presentation_plan or {}).get("tone"),
            "target_slide_count": ((design_brief or {}).get("deck_size") or {}).get("slide_count_target") or (presentation_plan or {}).get("slide_count_target"),
        },
        "master_layout_families": [family["family_id"] for family in layout_family_plan["families"]],
        "slide_type_families": {
            family["family_id"]: family["compatible_slide_types"]
            for family in layout_family_plan["families"]
        },
        "reusable_component_families": [component["component_family"] for component in component_translation_plan["components"]],
        "ornament_layers": {
            "background": "background topology grid, dot grid, contour or ring ornaments as editable SVG/PPT primitives",
            "section": "oversized section number, academic seal, index tabs",
            "data": "thin chart/table rules and modular frames",
        },
        "navigation_footer_system": {
            "required": True,
            "components": ["dense_footer", "citation_strip", "index_navigation", "section_tabs"],
            "source_policy": "Footer text remains editable and carries source/citation metadata.",
        },
        "chart_table_system": {
            "components": ["chart_modules", "table_modules", "kpi_cards"],
            "chart_policy": "Use PPT charts or editable shape charts; no raster chart screenshots.",
            "table_policy": "Use PPT tables or shape-grid tables; no raster tables.",
        },
        "card_system": {
            "components": ["cards", "kpi_cards", "insight_blocks", "quote_blocks"],
            "density_variants": ["compact", "standard", "evidence_heavy"],
        },
        "photo_image_mask_system": {
            "components": ["photo_masks", "diagonal_panels"],
            "allowed_usage": "Only source photos, document crops, or approved photo assets inside declared image-frame slots.",
            "forbidden_usage": "No design board crop or reference image as final slide background.",
        },
        "citation_source_system": {
            "footer_presence_required": True,
            "source_anchor_binding": "slide_blueprint.citations -> footer/citation strip slot",
        },
        "deck_rhythm_rules": deck_scale_usage_plan["scales"],
        "implementation_order": [
            "compile tokens",
            "compile reusable components",
            "compile board-derived layout families",
            "bind slide_blueprint slots",
            "render editable PPTX",
            "run image policy, premium QA, and visual diff",
        ],
        "visual_fidelity_targets": visual_fidelity_targets["targets"],
        "provenance": {
            "source": "design_board_production_planning",
            "prompt_id": prompt["prompt_id"],
            "board_image_path": board_manifest.get("board_image_path"),
            "extraction_source": "actual",
            "codex_extraction_used": True,
        },
    }


def _component_translation_plan(
    *,
    prompt: dict[str, Any],
    board_manifest: dict[str, Any],
    crop_manifest: dict[str, Any],
    component_library: dict[str, Any],
    style_tokens: dict[str, Any],
    crops_by_role: dict[str, dict[str, Any]],
    paths: dict[str, str],
) -> dict[str, Any]:
    components: list[dict[str, Any]] = []
    for component_family in sorted(key for key in component_library.keys() if key not in {"schema_name", "schema_version", "prompt_id"}):
        source = component_library.get(component_family) or {}
        primitive = COMPONENT_PRIMITIVES.get(component_family, "PPT shape + PPT text")
        evidence_roles = _component_evidence_roles(component_family, crops_by_role)
        components.append(
            {
                "component_family": component_family,
                "source_evidence": {
                    "board_image_path": board_manifest.get("board_image_path"),
                    "crop_roles": evidence_roles,
                    "crop_paths": [crops_by_role[role]["path"] for role in evidence_roles if role in crops_by_role],
                    "extraction_component_key": component_family,
                },
                "editable_ppt_translation": source.get("editable_ppt_translation") or _default_translation(component_family, primitive),
                "implementation_primitive": primitive,
                "forbidden": ["full-slide raster image", "rasterized text", "rasterized chart/table"],
                "style_tokens_used": source.get("style_tokens_used") or _tokens_for_component(component_family, style_tokens),
                "density_variants": _premium_component_variants(component_family, source),
                "tone_variants": sorted((style_tokens.get("tone_variants") or {}).keys()),
                "component_geometry_rules": source.get("component_geometry_rules") or {},
                "allowed_variants": _premium_component_variants(component_family, source),
                "forbidden_rasterization": source.get("forbidden_rasterization", True),
                "premium_gap_upgrade": _premium_gap_upgrade(component_family),
            }
        )
    return {
        "schema_name": "component_translation_plan",
        "schema_version": "1.0",
        "prompt_id": prompt["prompt_id"],
        "board_manifest_path": paths.get("board_manifest"),
        "crop_manifest_path": paths.get("crop_manifest"),
        "component_count": len(components),
        "components": components,
        "global_forbidden_behaviors": ["full-slide raster image", "template reference PNG inserted into final deck", "rasterized editable text/tables/charts"],
    }


def _layout_family_plan(
    archetypes: list[dict[str, Any]],
    crops_by_role: dict[str, dict[str, Any]],
    component_plan: dict[str, Any],
) -> dict[str, Any]:
    archetype_by_prompt_type = {str(item.get("source_prompt_slide_type")): item for item in archetypes}
    families: list[dict[str, Any]] = []
    for spec in LAYOUT_FAMILY_SPECS:
        members = [archetype_by_prompt_type[item] for item in spec["source_prompt_slide_types"] if item in archetype_by_prompt_type]
        compatible = sorted({value for item in members for value in item.get("compatible_slide_types") or []})
        required = sorted({value for item in members for value in item.get("required_slots") or []})
        optional = sorted({value for item in members for value in item.get("optional_slots") or []})
        component_bindings = sorted({value for item in members for value in item.get("component_variants") or []})
        visual_primitives = _merge_visual_primitives(members)
        families.append(
            {
                "family_id": spec["family_id"],
                "label": spec["label"],
                "source_prompt_slide_types": spec["source_prompt_slide_types"],
                "member_archetype_ids": [item.get("archetype_id") for item in members],
                "compatible_slide_types": compatible,
                "required_slots": required,
                "optional_slots": optional,
                "geometry_strategy": _geometry_strategy(members),
                "component_bindings": component_bindings,
                "visual_motif_to_preserve": visual_primitives,
                "source_crop_roles": _family_crop_roles(spec["source_prompt_slide_types"], crops_by_role),
                "fallback_layout": spec["fallback_layout"],
                "variation_rules_for_large_decks": spec["variation_rules"],
                "machine_constraints": {
                    "slot_geometry_required": True,
                    "normalized_geometry_required": True,
                    "use_board_derived_layout_before_mvp": True,
                },
            }
        )
    return {
        "schema_name": "layout_family_plan",
        "schema_version": "1.0",
        "family_count": len(families),
        "archetype_count": len(archetypes),
        "families": families,
        "component_plan_component_count": component_plan.get("component_count"),
    }


def _deck_scale_usage_plan(
    style_tokens: dict[str, Any],
    design_brief: dict[str, Any] | None,
    presentation_plan: dict[str, Any] | None,
) -> dict[str, Any]:
    requested_count = ((design_brief or {}).get("deck_size") or {}).get("slide_count_target") or (presentation_plan or {}).get("slide_count_target")
    return {
        "schema_name": "deck_scale_usage_plan",
        "schema_version": "1.0",
        "requested_slide_count": requested_count,
        "scales": {
            "small": _scale_rule("small", "5-12", 2, "high", "expressive", "medium", "full citation footer"),
            "medium": _scale_rule("medium", "13-30", 3, "medium", "balanced", "medium-high", "standard citation footer"),
            "large": _scale_rule("large", "31-80", 4, "medium-low", "section rhythm", "high with caps", "dense but compact footer"),
            "very_large": _scale_rule("very_large", "81+", 5, "low", "performance-first", "controlled high", "compact persistent footer"),
        },
        "style_token_dependencies": {
            "ornament_density": style_tokens.get("ornament_density"),
            "footer_height": style_tokens.get("footer_height"),
            "chart_table_density": style_tokens.get("chart_table_density"),
        },
    }


def _visual_fidelity_targets(
    archetypes: list[dict[str, Any]],
    component_plan: dict[str, Any],
    layout_family_plan: dict[str, Any],
    style_tokens: dict[str, Any],
) -> dict[str, Any]:
    tone_variants = sorted((style_tokens.get("tone_variants") or {}).keys())
    target_count = len(archetypes)
    targets = {
        "minimum_non_white_background_ornament_occupancy": 0.08,
        "footer_citation_presence_ratio": 0.95,
        "section_navigation_presence_ratio": 0.85,
        "card_density_range": {"min_cards_per_card_slide": 3, "max_cards_per_card_slide": 8},
        "chart_table_density_range": {"min_data_module_area_ratio": 0.22, "max_data_module_area_ratio": 0.72},
        "minimum_distinct_layout_families_used": min(8, layout_family_plan.get("family_count", 0)),
        "maximum_generic_layout_ratio": 0.0,
        "maximum_fallback_ratio": 0.08,
        "required_design_board_derived_component_ratio": 0.85,
        "tone_divergence_requirements": {
            "minimum_unique_token_signatures": min(3, len(tone_variants)),
            "required_tone_variants": tone_variants,
            "rendered_visual_divergence_required": True,
        },
        "minimum_board_layout_count": min(18, target_count),
        "minimum_component_family_count": min(12, component_plan.get("component_count", 0)),
        "minimum_dark_hero_navy_area_ratio": 0.18,
        "minimum_accent_occupancy": 0.025,
        "minimum_topology_connector_count_per_hero": 10,
        "oversized_section_number_required": True,
        "index_rail_required_on_section_slides": True,
        "no_photo_frame_placeholder_cross_allowed": True,
        "minimum_chart_module_framing_shapes": 4,
        "minimum_layered_card_surface_count": 2,
    }
    return {
        "schema_name": "visual_fidelity_targets",
        "schema_version": "1.0",
        "summary": {
            "max_generic_layout_ratio": targets["maximum_generic_layout_ratio"],
            "max_fallback_ratio": targets["maximum_fallback_ratio"],
            "required_design_board_component_ratio": targets["required_design_board_derived_component_ratio"],
            "tone_variants": tone_variants,
        },
        "targets": targets,
        "qa_uses": ["premium_design_quality", "template_visual_diff", "final_deck_image_policy"],
        "severe_violation_examples": [
            "generic MVP layout selected for premium run",
            "design board image embedded directly",
            "full-slide raster background",
            "missing footer on non-cover layouts",
            "tone variants collapse to identical rendered appearance",
            "premium cover renders without a dark navy hero treatment",
            "declared photo frames render as empty X placeholders in premium mode",
        ],
    }


def _prompt_entry(prompt_manifest: dict[str, Any], prompt_id: Any) -> dict[str, Any]:
    for prompt in prompt_manifest.get("prompts") or []:
        if prompt.get("prompt_id") == prompt_id:
            return prompt
    raise ValueError(f"prompt manifest does not contain prompt_id {prompt_id!r}")


def _component_evidence_roles(component_family: str, crops_by_role: dict[str, dict[str, Any]]) -> list[str]:
    roles = []
    if component_family in {"footer_system", "index_navigation", "section_tabs"}:
        roles.extend(["master_layout_system", "slide_thumbnail_02_visual_table_of_contents", "slide_thumbnail_03_section_divider"])
    elif component_family in {"cards", "kpi_cards", "quote_blocks", "insight_blocks"}:
        roles.extend(["component_library", "slide_thumbnail_14_three_level_explanation", "slide_thumbnail_16_kpi_donut_chart"])
    elif component_family in {"diagram_nodes", "process_arrows", "radial_maps", "timeline_blocks", "connector_style"}:
        roles.extend(["component_library", "slide_thumbnail_09_technical_flow_chart", "slide_thumbnail_15_circular_process", "slide_thumbnail_17_timeline_roadmap"])
    elif component_family in {"table_modules", "chart_modules"}:
        roles.extend(["component_library", "slide_thumbnail_12_comparison_matrix", "slide_thumbnail_18_data_table_appendix"])
    elif component_family in {"photo_masks", "diagonal_panels"}:
        roles.extend(["hero_cover", "hero_main_content", "slide_thumbnail_11_photo_caption_grid"])
    elif component_family in {"background_ornaments", "icon_style"}:
        roles.extend(["style_tokens", "component_library", "hero_cover"])
    else:
        roles.append("component_library")
    return [role for role in roles if role in crops_by_role]


def _tokens_for_component(component_family: str, style_tokens: dict[str, Any]) -> list[str]:
    token_groups = {
        "footer_system": ["colors", "footer_style", "footer_height", "typography"],
        "cards": ["colors", "card_style", "card_radius", "spacing"],
        "kpi_cards": ["colors", "card_style", "chart_style", "typography"],
        "table_modules": ["table_style", "line_weights", "typography"],
        "chart_modules": ["chart_style", "colors", "typography"],
        "background_ornaments": ["background_layers", "ornament_density", "colors"],
    }
    return [token for token in token_groups.get(component_family, ["colors", "spacing", "typography"]) if token in style_tokens]


def _premium_component_variants(component_family: str, source: dict[str, Any]) -> list[str]:
    variants = [str(item) for item in (source.get("allowed_variants") or ["compact", "standard", "dense"])]
    additions = {
        "footer_system": ["dense_citation_micro_system", "navy_source_rail", "citation_micro_footer"],
        "index_navigation": ["persistent_index_rail", "section_tab_stack", "vertical_index_rail", "creative_section_tab"],
        "section_tabs": ["oversized_section_number", "academic_seal_marker", "creative_section_tab", "dark_header_band"],
        "cards": ["layered_floating_card", "editorial_evidence_card", "glass_overlay_card"],
        "kpi_cards": ["premium_kpi_card", "donut_kpi_chip"],
        "table_modules": ["thin_grid_table", "navy_header_table"],
        "chart_modules": ["framed_chart_module", "kpi_dashboard_combo"],
        "diagram_nodes": ["radial_node_map", "methodology_hex_node"],
        "process_arrows": ["curved_process_connector", "phase_arrow_chain"],
        "radial_maps": ["circular_process_ring", "relationship_orbit"],
        "timeline_blocks": ["curved_timeline", "indexed_roadmap"],
        "photo_masks": ["no_photo_medallion_fallback", "declared_photo_frame_only"],
        "diagonal_panels": ["fractured_diagonal_panel", "diagonal_image_frame", "diagonal_hero_panel", "fractured_geometry_panel"],
        "background_ornaments": ["topology_network", "contour_field", "ring_cluster", "hex_grid", "topology_grid_layer", "expressive_cover_identity"],
        "connector_style": ["curved_connector", "dotted_topology_connector"],
    }.get(component_family, [])
    for item in additions:
        if item not in variants:
            variants.append(item)
    return variants


def _premium_gap_upgrade(component_family: str) -> dict[str, Any]:
    upgrades = {
        "footer_system": {
            "intent": "Preserve the board's citation/source strip as an editable micro-system.",
            "required_primitives": ["PPT text", "PPT rule", "PPT accent tick", "citation_micro_footer"],
        },
        "index_navigation": {
            "intent": "Promote INDEX rail and section tabs from decorative board detail to recurring editable navigation.",
            "required_primitives": ["PPT line", "PPT dot markers", "PPT text", "vertical_index_rail", "creative_section_tab"],
        },
        "section_tabs": {
            "intent": "Render oversized section numbers and academic seal markers as editable text/shapes.",
            "required_primitives": ["PPT text", "PPT oval", "PPT rule", "oversized_section_number", "dark_header_band"],
        },
        "cards": {
            "intent": "Use layered floating card surfaces with accent rails, seals, and nested metadata rules.",
            "required_primitives": ["PPT rounded rectangle", "PPT text", "PPT line", "glass_overlay_card"],
        },
        "chart_modules": {
            "intent": "Wrap editable charts in premium board-derived frames and KPI chips.",
            "required_primitives": ["PPT chart", "PPT shape", "PPT text"],
        },
        "table_modules": {
            "intent": "Use thin-grid editable tables with navy header and citation/caption strip.",
            "required_primitives": ["PPT table", "PPT shape", "PPT text"],
        },
        "background_ornaments": {
            "intent": "Recreate topology, contour, ring, and hex ornaments with editable lines/shapes or SVG ornaments.",
            "required_primitives": ["PPT connector", "PPT dot", "SVG ornament", "topology_grid_layer", "expressive_cover_identity"],
        },
        "connector_style": {
            "intent": "Use curved/radial connectors for process and relationship modules.",
            "required_primitives": ["PPT connector", "PPT node shape", "PPT text"],
        },
        "photo_masks": {
            "intent": "Use declared photo frames only; if no photo is approved, render editable medallion fallback instead of X placeholders.",
            "required_primitives": ["PPT oval", "PPT connector", "PPT line", "diagonal_hero_panel", "fractured_geometry_panel"],
        },
    }
    return upgrades.get(
        component_family,
        {
            "intent": "Preserve design-board component language using editable PowerPoint primitives.",
            "required_primitives": ["PPT shape", "PPT text"],
        },
    )


def _default_translation(component_family: str, primitive: str) -> dict[str, Any]:
    return {
        "primitive": primitive,
        "editable": True,
        "notes": f"Recreate {component_family} with slide-native editable PowerPoint objects.",
    }


def _family_crop_roles(prompt_types: list[str], crops_by_role: dict[str, dict[str, Any]]) -> list[str]:
    roles = []
    for prompt_type in prompt_types:
        suffix = prompt_type.replace("-", "_")
        roles.extend(role for role in crops_by_role if role.endswith(suffix))
    if not roles:
        roles = [role for role in ("master_layout_system", "component_library") if role in crops_by_role]
    return sorted(set(roles))


def _merge_visual_primitives(members: list[dict[str, Any]]) -> dict[str, list[str]]:
    merged: dict[str, list[str]] = {}
    for member in members:
        primitives = member.get("visual_primitives") or {}
        if not isinstance(primitives, dict):
            continue
        for key, values in primitives.items():
            merged.setdefault(key, [])
            for value in _as_list(values):
                if value not in merged[key]:
                    merged[key].append(value)
    return merged


def _geometry_strategy(members: list[dict[str, Any]]) -> dict[str, Any]:
    slot_counts = [len(item.get("slot_geometry") or []) for item in members]
    density = Counter(str(item.get("recommended_density") or "medium") for item in members)
    return {
        "coordinate_system": "normalized_0_1 converted to 13.333 x 7.5 inch canvas",
        "slot_geometry_required": True,
        "normalized_geometry_required": True,
        "member_slot_count_min": min(slot_counts) if slot_counts else 0,
        "member_slot_count_max": max(slot_counts) if slot_counts else 0,
        "dominant_density": density.most_common(1)[0][0] if density else "medium",
    }


def _scale_rule(scale_id: str, slide_range: str, max_repetition: int, ornament_density: str, rhythm: str, table_chart_density: str, footer_density: str) -> dict[str, Any]:
    return {
        "scale_id": scale_id,
        "slide_range": slide_range,
        "layout_rotation_rules": f"Use at least {max(2, max_repetition)} layout families before repeating a family when possible.",
        "section_rhythm": "section divider -> overview -> evidence -> analysis -> implication" if scale_id in {"large", "very_large"} else "opener -> context -> method/data -> insight -> close",
        "ornament_density": ornament_density,
        "maximum_repetition": max_repetition,
        "table_chart_density": table_chart_density,
        "footer_citation_density": footer_density,
        "performance_constraints": "Reduce decorative shape count and preserve table/footer consistency." if scale_id in {"large", "very_large"} else "Full expressive component set allowed.",
        "simplify_creative_elements_when": ["high table density", "many repeated slides", "very large deck performance risk"],
    }


def _reading_report_md(report: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Design Board Reading Report",
            "",
            f"Prompt: `{report['prompt_id']}`",
            f"Board image: `{report['board_image_path']}`",
            f"Generation mode: `{report['generation_mode']}`",
            f"Design thesis: {report['design_thesis']}",
            "",
            "## Must Preserve",
            *[f"- {item}" for item in report["must_preserve"]],
            "",
            "## Can Simplify",
            *[f"- {item}" for item in report["can_simplify_for_editable_ppt"]],
            "",
            "## Must Not Copy Literally",
            *[f"- {item}" for item in report["must_not_copy_literally"]],
            "",
        ]
    )


def _template_plan_md(plan: dict[str, Any]) -> str:
    lines = [
        "# Template Production Plan",
        "",
        f"Prompt: `{plan['prompt_id']}`",
        f"Production mode: `{plan['production_mode']}`",
        f"Board image: `{plan['board_image_path']}`",
        "",
        "## Layout Families",
        "",
    ]
    for family_id in plan["master_layout_families"]:
        lines.append(f"- `{family_id}`")
    lines.extend(["", "## Reusable Components", ""])
    for component in plan["reusable_component_families"]:
        lines.append(f"- `{component}`")
    lines.extend(["", "## Reference Policy", ""])
    for key, value in plan["reference_only_policy"].items():
        lines.append(f"- `{key}`: `{value}`")
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build design-board production planning artifacts.")
    parser.add_argument("--prompt", type=Path, default=DEFAULT_PROMPT)
    parser.add_argument("--prompt-manifest", type=Path, default=DEFAULT_PROMPT_MANIFEST)
    parser.add_argument("--board-manifest", type=Path, default=DEFAULT_BOARD_MANIFEST)
    parser.add_argument("--crop-manifest", type=Path, default=DEFAULT_CROP_MANIFEST)
    parser.add_argument("--extracted-design-board", type=Path, default=DEFAULT_DESIGN_BOARD)
    parser.add_argument("--extracted-slide-archetypes", type=Path, default=DEFAULT_ARCHETYPES)
    parser.add_argument("--extracted-component-library", type=Path, default=DEFAULT_COMPONENTS)
    parser.add_argument("--extracted-style-tokens", type=Path, default=DEFAULT_STYLE_TOKENS)
    parser.add_argument("--design-brief", type=Path, default=DEFAULT_DESIGN_BRIEF)
    parser.add_argument("--presentation-plan", type=Path, default=DEFAULT_PRESENTATION_PLAN)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        written = build_design_production_plan_from_files(
            prompt_path=args.prompt,
            prompt_manifest_path=args.prompt_manifest,
            board_manifest_path=args.board_manifest,
            crop_manifest_path=args.crop_manifest,
            extracted_design_board_path=args.extracted_design_board,
            extracted_slide_archetypes_path=args.extracted_slide_archetypes,
            extracted_component_library_path=args.extracted_component_library,
            extracted_style_tokens_path=args.extracted_style_tokens,
            design_brief_path=args.design_brief,
            presentation_plan_path=args.presentation_plan,
            output_dir=args.output_dir,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"BUILD_DESIGN_PRODUCTION_PLAN_FAILED {exc}")
        return 1
    for path in written.values():
        print(f"WROTE {path}")
    return 0


def _load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _load_optional_valid_json(path: str | Path, validator: Any) -> dict[str, Any] | None:
    candidate = Path(path)
    if not candidate.exists():
        return None
    payload = _load_json(candidate)
    validator(payload)
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def _sentence(value: Any, fallback: str) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, dict) and value:
        return "; ".join(f"{key}: {val}" for key, val in list(value.items())[:4])
    return fallback


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, dict):
        return [f"{key}: {val}" for key, val in value.items()]
    return [str(value)]


if __name__ == "__main__":
    raise SystemExit(main())
