"""Build an editable template spec from Codex-extracted design-board artifacts."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

from ..generator_contracts import (
    validateDesignBrief,
    validateEditableTemplateSpec,
    validateExtractedComponentLibrary,
    validateExtractedDesignBoardCodex,
    validateExtractedSlideArchetypes,
    validateExtractedStyleTokens,
)


DEFAULT_DESIGN_BOARD = Path("outputs/design_extraction/extracted_design_board.codex.json")
DEFAULT_ARCHETYPES = Path("outputs/design_extraction/extracted_slide_archetypes.json")
DEFAULT_COMPONENTS = Path("outputs/design_extraction/extracted_component_library.json")
DEFAULT_STYLE_TOKENS = Path("outputs/design_extraction/extracted_style_tokens.json")
DEFAULT_DESIGN_BRIEF = Path("outputs/design_brief.json")
DEFAULT_BASE_SPEC = Path("outputs/editable_template_spec.json")
DEFAULT_OUTPUT = Path("outputs/editable_template_spec.final.json")
DEFAULT_REPORT_JSON = Path("outputs/template_spec_from_design_board_report.json")
DEFAULT_REPORT_MD = Path("outputs/template_spec_from_design_board_report.md")
DEFAULT_BOARD_MANIFEST = Path("outputs/template_design_board/template_design_board_manifest.json")
DEFAULT_TEMPLATE_PRODUCTION_PLAN = Path("outputs/design_planning/template_production_plan.json")
DEFAULT_COMPONENT_TRANSLATION_PLAN = Path("outputs/design_planning/component_translation_plan.json")
DEFAULT_LAYOUT_FAMILY_PLAN = Path("outputs/design_planning/layout_family_plan.json")
DEFAULT_DECK_SCALE_USAGE_PLAN = Path("outputs/design_planning/deck_scale_usage_plan.json")
DEFAULT_VISUAL_FIDELITY_TARGETS = Path("outputs/design_planning/visual_fidelity_targets.json")
SAMPLE_ROOT = Path("outputs/schema_samples/valid")
CANVAS = {"width": 13.333, "height": 7.5, "unit": "in", "ratio": "16:9"}
CANONICAL_COMPONENTS = [
    "dense_footer",
    "index_navigation",
    "oversized_section_number",
    "diagonal_image_frame",
    "layered_card",
    "premium_kpi_card",
    "radial_process",
    "curved_timeline",
    "comparison_matrix",
    "thin_grid_table",
    "chart_module",
    "insight_callout",
    "citation_strip",
    "background_topology_grid",
    "expressive_cover_identity",
    "vertical_index_rail",
    "diagonal_hero_panel",
    "fractured_geometry_panel",
    "topology_grid_layer",
    "dark_header_band",
    "citation_micro_footer",
    "creative_section_tab",
    "glass_overlay_card",
]


def build_template_spec_from_design_board(
    *,
    extracted_design_board: dict[str, Any],
    extracted_slide_archetypes: dict[str, Any],
    extracted_component_library: dict[str, Any],
    extracted_style_tokens: dict[str, Any],
    design_brief: dict[str, Any],
    base_spec: dict[str, Any] | None = None,
    production_plans: dict[str, dict[str, Any]] | None = None,
    warnings: list[dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    validateExtractedDesignBoardCodex(extracted_design_board)
    validateExtractedSlideArchetypes(extracted_slide_archetypes)
    validateExtractedComponentLibrary(extracted_component_library)
    validateExtractedStyleTokens(extracted_style_tokens)
    validateDesignBrief(design_brief)
    report_warnings = list(warnings or [])

    spec = _base_spec_shell(base_spec)
    spec["schema_name"] = "editable_template_spec"
    spec["schema_version"] = "1.0"
    spec["design_id"] = f"design-board-{_safe_id(extracted_design_board['prompt_id'])}"
    production_plan_used = production_plans is not None
    spec["provenance"] = {
        "source": "design_board_production_plan" if production_plan_used else "design_board_extraction",
        "prompt_id": extracted_design_board["prompt_id"],
        "board_image_path": extracted_design_board["board_image_path"],
        "codex_extraction_used": True,
        **(
            {
                "extraction_source": "actual",
                "production_plan_used": True,
                "component_translation_plan_path": str((production_plans.get("_paths") or {}).get("component_translation_plan") or DEFAULT_COMPONENT_TRANSLATION_PLAN.as_posix()),
                "layout_family_plan_path": str((production_plans.get("_paths") or {}).get("layout_family_plan") or DEFAULT_LAYOUT_FAMILY_PLAN.as_posix()),
                "deck_scale_usage_plan_path": str((production_plans.get("_paths") or {}).get("deck_scale_usage_plan") or DEFAULT_DECK_SCALE_USAGE_PLAN.as_posix()),
                "visual_fidelity_targets_path": str((production_plans.get("_paths") or {}).get("visual_fidelity_targets") or DEFAULT_VISUAL_FIDELITY_TARGETS.as_posix()),
            }
            if production_plan_used
            else {}
        ),
    }
    spec["canvas"] = dict(CANVAS)
    spec["tokens"] = _tokens_from_extraction(extracted_style_tokens, base_spec, report_warnings)
    spec["components"] = (
        _components_from_translation_plan(production_plans["component_translation_plan"], base_spec)
        if production_plan_used
        else _components_from_library(extracted_component_library, base_spec)
    )

    board_layouts = [_layout_from_archetype(item) for item in extracted_slide_archetypes["archetypes"]]
    if production_plan_used:
        board_layouts = _apply_layout_family_plan(
            board_layouts,
            extracted_slide_archetypes["archetypes"],
            production_plans["layout_family_plan"],
            production_plans["component_translation_plan"],
            production_plans["visual_fidelity_targets"],
        )
    if len(board_layouts) < 18:
        report_warnings.append(_warning("MISSING_ARCHETYPE", f"Expected 18 extracted archetypes but found {len(board_layouts)}."))
    if any(len(layout["slots"]) <= 2 for layout in board_layouts):
        report_warnings.append(_warning("LAYOUT_TOO_GENERIC", "One or more extracted layouts has only title/footer slots."))

    spec["layouts"] = board_layouts if production_plan_used else _merge_layouts(board_layouts, base_spec)
    spec["slot_definitions"] = _slot_definitions(spec["layouts"])
    spec["primitives"] = _primitives(spec["layouts"])
    spec["asset_policy"] = _asset_policy(base_spec)
    spec["render_policy"] = {
        "editable_text": True,
        "editable_tables": True,
        "editable_charts": True,
        "editable_titles": True,
    }

    spec.setdefault("tokens", {}).setdefault("typography", {})
    spec["tokens"]["typography"]["tone_variants"] = extracted_style_tokens["tone_variants"]
    spec["tokens"]["spacing"]["deck_scale_small_expressiveness"] = 1.0
    spec["tokens"]["spacing"]["deck_scale_medium_rotation"] = 0.75
    spec["tokens"]["spacing"]["deck_scale_large_rhythm"] = 0.5
    spec["tokens"]["spacing"]["deck_scale_very_large_ornament_density"] = 0.25
    spec["deck_scale_rules"] = (
        _deck_scale_rules_from_plan(production_plans["deck_scale_usage_plan"])
        if production_plan_used
        else {
            "small": "Use more expressive layouts and stronger visual motifs.",
            "medium": "Use balanced layout rotation across content, data, and section layouts.",
            "large": "Reuse archetypes with deterministic variation and section rhythm.",
            "very_large": "Reduce ornament density and enforce footer/table consistency.",
        }
    )
    spec["tokens"]["shadows"]["deck_scale_rules"] = spec["deck_scale_rules"]
    if production_plan_used:
        spec["layout_families"] = production_plans["layout_family_plan"].get("families", [])
        spec["visual_fidelity_targets"] = production_plans["visual_fidelity_targets"].get("targets", {})
        spec["production_notes"] = _production_notes(production_plans)

    if not extracted_style_tokens.get("tone_variants"):
        report_warnings.append(_warning("NO_TONE_VARIANT_SELECTED", "No tone variants were extracted."))
    if not extracted_design_board.get("motif_system"):
        report_warnings.append(_warning("NO_VISUAL_MOTIF_EXTRACTED", "No visual motif system was extracted."))

    validateEditableTemplateSpec(spec)
    report = _report(spec, extracted_design_board, extracted_slide_archetypes, report_warnings, production_plans)
    return spec, report


def build_template_spec_from_design_board_files(
    *,
    design_board_path: str | Path = DEFAULT_DESIGN_BOARD,
    slide_archetypes_path: str | Path = DEFAULT_ARCHETYPES,
    component_library_path: str | Path = DEFAULT_COMPONENTS,
    style_tokens_path: str | Path = DEFAULT_STYLE_TOKENS,
    design_brief_path: str | Path = DEFAULT_DESIGN_BRIEF,
    base_spec_path: str | Path = DEFAULT_BASE_SPEC,
    output_path: str | Path = DEFAULT_OUTPUT,
    report_json_path: str | Path = DEFAULT_REPORT_JSON,
    report_md_path: str | Path = DEFAULT_REPORT_MD,
    board_manifest_path: str | Path = DEFAULT_BOARD_MANIFEST,
    template_production_plan_path: str | Path = DEFAULT_TEMPLATE_PRODUCTION_PLAN,
    component_translation_plan_path: str | Path = DEFAULT_COMPONENT_TRANSLATION_PLAN,
    layout_family_plan_path: str | Path = DEFAULT_LAYOUT_FAMILY_PLAN,
    deck_scale_usage_plan_path: str | Path = DEFAULT_DECK_SCALE_USAGE_PLAN,
    visual_fidelity_targets_path: str | Path = DEFAULT_VISUAL_FIDELITY_TARGETS,
    extraction_mode: str = "auto",
) -> Path:
    warnings: list[dict[str, Any]] = []
    board_manifest = _load_optional_json(board_manifest_path)
    premium_mode = _is_premium_mode(board_manifest, extraction_mode)
    allow_schema_sample_fallback = extraction_mode == "sample"
    if extraction_mode == "premium" and not board_manifest:
        raise ValueError(f"premium design-board build requires manifest: {Path(board_manifest_path).as_posix()}")
    production_plans = _load_production_plans(
        premium_mode=premium_mode,
        template_production_plan_path=template_production_plan_path,
        component_translation_plan_path=component_translation_plan_path,
        layout_family_plan_path=layout_family_plan_path,
        deck_scale_usage_plan_path=deck_scale_usage_plan_path,
        visual_fidelity_targets_path=visual_fidelity_targets_path,
    )

    loaded: list[dict[str, Any]] = []
    design_board = _load_contract_or_sample(
        design_board_path,
        SAMPLE_ROOT / "extracted_design_board_codex.json",
        validateExtractedDesignBoardCodex,
        warnings,
        "missing design board extraction",
        allow_schema_sample_fallback=allow_schema_sample_fallback,
        loaded=loaded,
    )
    archetypes = _load_contract_or_sample(
        slide_archetypes_path,
        SAMPLE_ROOT / "extracted_slide_archetypes.json",
        validateExtractedSlideArchetypes,
        warnings,
        "missing archetype extraction",
        allow_schema_sample_fallback=allow_schema_sample_fallback,
        loaded=loaded,
    )
    components = _load_contract_or_sample(
        component_library_path,
        SAMPLE_ROOT / "extracted_component_library.json",
        validateExtractedComponentLibrary,
        warnings,
        "missing component library extraction",
        allow_schema_sample_fallback=allow_schema_sample_fallback,
        loaded=loaded,
    )
    style_tokens = _load_contract_or_sample(
        style_tokens_path,
        SAMPLE_ROOT / "extracted_style_tokens.json",
        validateExtractedStyleTokens,
        warnings,
        "missing style tokens",
        allow_schema_sample_fallback=allow_schema_sample_fallback,
        loaded=loaded,
    )
    extraction_source = "actual" if all(item["source"] == "actual" for item in loaded) else "schema_sample"
    fallback_used = any(item["source"] == "schema_sample" for item in loaded)
    fallback_reason = "; ".join(item["reason"] for item in loaded if item.get("reason")) or ""
    if premium_mode:
        _assert_premium_extraction(
            extraction_source=extraction_source,
            design_board=design_board,
            board_manifest=board_manifest,
            loaded=loaded,
        )
    design_brief = _load_json(design_brief_path)
    base_spec = _load_optional_base_spec(base_spec_path, warnings)
    spec, report = build_template_spec_from_design_board(
        extracted_design_board=design_board,
        extracted_slide_archetypes=archetypes,
        extracted_component_library=components,
        extracted_style_tokens=style_tokens,
        design_brief=design_brief,
        base_spec=base_spec,
        production_plans=production_plans,
        warnings=warnings,
    )
    report.update({
        "extraction_source": extraction_source,
        "premium_mode": premium_mode,
        "fallback_used": fallback_used,
        "fallback_reason": fallback_reason,
        "extraction_files_used": loaded,
        "board_manifest_path": Path(board_manifest_path).as_posix(),
        "production_plan_used": production_plans is not None,
        "production_plan_files_used": _production_plan_file_report(production_plans),
    })
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(spec, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")
    report_json = Path(report_json_path)
    report_json.parent.mkdir(parents=True, exist_ok=True)
    report_json.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")
    Path(report_md_path).write_text(_markdown_report(report), encoding="utf-8")
    return output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build editable_template_spec.final.json from extracted design-board artifacts.")
    parser.add_argument("--design-board", type=Path, default=DEFAULT_DESIGN_BOARD)
    parser.add_argument("--slide-archetypes", type=Path, default=DEFAULT_ARCHETYPES)
    parser.add_argument("--component-library", type=Path, default=DEFAULT_COMPONENTS)
    parser.add_argument("--style-tokens", type=Path, default=DEFAULT_STYLE_TOKENS)
    parser.add_argument("--design-brief", type=Path, default=DEFAULT_DESIGN_BRIEF)
    parser.add_argument("--base-spec", type=Path, default=DEFAULT_BASE_SPEC)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report-json", type=Path, default=DEFAULT_REPORT_JSON)
    parser.add_argument("--report-md", type=Path, default=DEFAULT_REPORT_MD)
    parser.add_argument("--board-manifest", type=Path, default=DEFAULT_BOARD_MANIFEST)
    parser.add_argument("--template-production-plan", type=Path, default=DEFAULT_TEMPLATE_PRODUCTION_PLAN)
    parser.add_argument("--component-translation-plan", type=Path, default=DEFAULT_COMPONENT_TRANSLATION_PLAN)
    parser.add_argument("--layout-family-plan", type=Path, default=DEFAULT_LAYOUT_FAMILY_PLAN)
    parser.add_argument("--deck-scale-usage-plan", type=Path, default=DEFAULT_DECK_SCALE_USAGE_PLAN)
    parser.add_argument("--visual-fidelity-targets", type=Path, default=DEFAULT_VISUAL_FIDELITY_TARGETS)
    parser.add_argument(
        "--extraction-mode",
        choices=("auto", "premium", "sample"),
        default="auto",
        help="auto treats an ingested manual_codex premium board as premium; sample is the only mode that may use schema sample fallback.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        output = build_template_spec_from_design_board_files(
            design_board_path=args.design_board,
            slide_archetypes_path=args.slide_archetypes,
            component_library_path=args.component_library,
            style_tokens_path=args.style_tokens,
            design_brief_path=args.design_brief,
            base_spec_path=args.base_spec,
            output_path=args.output,
            report_json_path=args.report_json,
            report_md_path=args.report_md,
            board_manifest_path=args.board_manifest,
            template_production_plan_path=args.template_production_plan,
            component_translation_plan_path=args.component_translation_plan,
            layout_family_plan_path=args.layout_family_plan,
            deck_scale_usage_plan_path=args.deck_scale_usage_plan,
            visual_fidelity_targets_path=args.visual_fidelity_targets,
            extraction_mode=args.extraction_mode,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"BUILD_TEMPLATE_SPEC_FROM_DESIGN_BOARD_FAILED {exc}")
        return 1
    print(f"WROTE {output}")
    return 0


def _base_spec_shell(base_spec: dict[str, Any] | None) -> dict[str, Any]:
    if base_spec:
        return copy.deepcopy(base_spec)
    return {
        "schema_name": "editable_template_spec",
        "schema_version": "1.0",
        "design_id": "design-board-template",
        "canvas": dict(CANVAS),
        "tokens": {},
        "components": [],
        "layouts": [],
        "slot_definitions": {},
        "primitives": [],
        "asset_policy": {},
        "render_policy": {},
    }


def _tokens_from_extraction(style_tokens: dict[str, Any], base_spec: dict[str, Any] | None, warnings: list[dict[str, Any]]) -> dict[str, Any]:
    base = copy.deepcopy((base_spec or {}).get("tokens") or {})
    colors = dict(base.get("colors") or {})
    for token, value in (style_tokens.get("colors") or {}).items():
        if isinstance(value, str) and value.startswith("#"):
            colors[_color_alias(token)] = value
    colors.setdefault("background", "#F8FAFC")
    colors.setdefault("surface", "#FFFFFF")
    colors.setdefault("surface_alt", "#EEF2F7")
    colors.setdefault("text", colors.get("ink", "#111827"))
    colors.setdefault("muted_text", "#475569")
    colors.setdefault("accent", "#2563EB")
    colors.setdefault("accent_secondary", "#0F766E")
    colors.setdefault("line", "#CBD5E1")
    colors.setdefault("grid", "#E2E8F0")
    colors.setdefault("shadow", "#0F172A")
    typography = dict(base.get("typography") or {})
    extracted_typography = style_tokens.get("typography") or {}
    typography["title"] = _typography_token(extracted_typography.get("title"), "Aptos Display", 34, "semibold")
    typography["subtitle"] = typography.get("subtitle") or {"font_family": "Aptos", "size_pt": 17, "weight": "regular"}
    typography["body"] = _typography_token(extracted_typography.get("body"), "Aptos", 14, "regular")
    typography["label"] = typography.get("label") or {"font_family": "Aptos", "size_pt": 9, "weight": "semibold"}
    typography["footer"] = typography.get("footer") or {"font_family": "Aptos", "size_pt": 7.5, "weight": "regular"}
    typography["kpi"] = typography.get("kpi") or {"font_family": "Aptos Display", "size_pt": 24, "weight": "bold"}
    spacing = _numeric_tokens(base.get("spacing"), style_tokens.get("spacing"), {"xs": 0.08, "sm": 0.14, "md": 0.24, "lg": 0.42, "xl": 0.68})
    radius = _numeric_tokens(base.get("radius"), style_tokens.get("card_style"), {"none": 0, "sm": 0.08, "md": 0.14, "lg": 0.22})
    line_weights = _numeric_tokens(base.get("line_weights"), style_tokens.get("borders"), {"hairline": 0.5, "standard": 1.0, "emphasis": 2.0})
    shadows = dict(base.get("shadows") or {})
    shadows["card"] = {"enabled": True, "source": style_tokens.get("shadows", {}).get("card", "subtle editable shadow")}
    shadows["background_layers"] = style_tokens.get("background_layers", {})
    shadows["chart_style"] = style_tokens.get("chart_style", {})
    shadows["table_style"] = style_tokens.get("table_style", {})
    shadows["card_style"] = style_tokens.get("card_style", {})
    shadows["footer_style"] = style_tokens.get("footer_style", {})
    shadows["section_number_style"] = style_tokens.get("section_number_style", {})
    if not style_tokens.get("colors"):
        warnings.append(_warning("MISSING_STYLE_TOKENS", "Style tokens did not include colors; base/default palette was used."))
    ornament_density = _ornament_density_tokens(base.get("ornament_density"), style_tokens)
    return {
        "colors": colors,
        "typography": typography,
        "spacing": spacing,
        "radius": radius,
        "line_weights": line_weights,
        "shadows": shadows,
        "ornament_density": ornament_density,
    }


def _ornament_density_tokens(base: Any, style_tokens: dict[str, Any]) -> dict[str, dict[str, Any]]:
    extracted_layers = style_tokens.get("background_layers") or {}
    extracted_density = _coerce_float(extracted_layers.get("ornament_density"), default=0.6)
    base_modes = copy.deepcopy(base) if isinstance(base, dict) else {}
    defaults = {
        "low": {
            "mode": "low",
            "grid_columns": 4,
            "guide_line_count": 4,
            "connector_cluster_count": 1,
            "micro_node_count": 8,
            "blueprint_arc_count": 1,
            "max_extra_shapes": 18,
            "line_weight_pt": 0.12,
            "allowed_components": ["ppt_line_grid_clusters", "micro_node_markers"],
        },
        "medium": {
            "mode": "medium",
            "grid_columns": 8,
            "guide_line_count": 10,
            "connector_cluster_count": 2,
            "micro_node_count": 18,
            "blueprint_arc_count": 3,
            "max_extra_shapes": 42,
            "line_weight_pt": 0.18,
            "allowed_components": [
                "ppt_line_grid_clusters",
                "micro_node_markers",
                "diagonal_guide_rails",
                "section_index_ticks",
            ],
        },
        "high": {
            "mode": "high",
            "grid_columns": 12,
            "guide_line_count": 18 if extracted_density < 0.75 else 22,
            "connector_cluster_count": 3,
            "micro_node_count": 30,
            "blueprint_arc_count": 5,
            "max_extra_shapes": 72,
            "line_weight_pt": 0.24,
            "allowed_components": [
                "ppt_line_grid_clusters",
                "micro_node_markers",
                "diagonal_guide_rails",
                "section_index_ticks",
                "subtle_blueprint_arcs",
                "transparent_polygon_bands",
            ],
        },
    }
    for mode, payload in defaults.items():
        configured = base_modes.get(mode)
        if isinstance(configured, dict):
            merged = dict(payload)
            merged.update(configured)
            merged["mode"] = mode
            defaults[mode] = merged
    return defaults


def _components_from_library(component_library: dict[str, Any], base_spec: dict[str, Any] | None) -> list[dict[str, Any]]:
    components = {item["component_id"]: copy.deepcopy(item) for item in (base_spec or {}).get("components") or [] if isinstance(item, dict) and item.get("component_id")}
    mapping = {
        "dense_footer": ("footer_system", "footer"),
        "index_navigation": ("index_navigation", "shape_group"),
        "oversized_section_number": ("section_tabs", "shape"),
        "diagonal_image_frame": ("diagonal_panels", "image_frame"),
        "layered_card": ("cards", "shape_group"),
        "premium_kpi_card": ("kpi_cards", "shape_group"),
        "radial_process": ("radial_maps", "shape_group"),
        "curved_timeline": ("timeline_blocks", "shape_group"),
        "comparison_matrix": ("table_modules", "table_frame"),
        "thin_grid_table": ("table_modules", "table_frame"),
        "chart_module": ("chart_modules", "chart_frame"),
        "insight_callout": ("insight_blocks", "shape_group"),
        "citation_strip": ("footer_system", "footer"),
        "background_topology_grid": ("background_ornaments", "shape"),
        "expressive_cover_identity": ("background_ornaments", "shape_group"),
        "vertical_index_rail": ("index_navigation", "shape_group"),
        "diagonal_hero_panel": ("diagonal_panels", "image_frame"),
        "fractured_geometry_panel": ("diagonal_panels", "shape_group"),
        "topology_grid_layer": ("background_ornaments", "shape_group"),
        "dark_header_band": ("section_tabs", "shape"),
        "citation_micro_footer": ("footer_system", "footer"),
        "creative_section_tab": ("section_tabs", "shape_group"),
        "glass_overlay_card": ("cards", "shape_group"),
    }
    for component_id in CANONICAL_COMPONENTS:
        source_key, component_type = mapping[component_id]
        source = component_library.get(source_key) or {}
        components[component_id] = {
            "component_id": component_id,
            "type": component_type,
            "editable": True,
            "default_tokens": {
                "source_component": source_key,
                "description": source.get("description", component_id),
                "editable_primitives": source.get("editable_primitives", ["shape", "text_box"]),
                "style_notes": source.get("style_notes", ""),
                "usage": source.get("usage", ""),
            },
        }
    return list(components.values())


def _components_from_translation_plan(component_plan: dict[str, Any], base_spec: dict[str, Any] | None) -> list[dict[str, Any]]:
    components = {item["component_id"]: copy.deepcopy(item) for item in (base_spec or {}).get("components") or [] if isinstance(item, dict) and item.get("component_id")}
    type_aliases = {
        "PPT shape + PPT text": "shape_group",
        "PPT shape + PPT text + editable shape chart": "shape_chart",
        "PPT chart or editable shape chart": "chart_frame",
        "PPT table": "table_frame",
        "photo-frame image": "image_frame",
        "PPT shape + photo-frame image": "image_frame",
        "SVG ornament": "svg_icon",
        "SVG ornament or PPT line/shape group": "ornament",
        "PPT line/connector": "connector",
        "PPT line/connector or SVG ornament": "connector",
        "PPT shape group": "shape_group",
        "PPT shape + PPT text + connector": "shape_group",
    }
    canonical_mapping = {
        "dense_footer": ("footer_system", "footer"),
        "index_navigation": ("index_navigation", "shape_group"),
        "oversized_section_number": ("section_tabs", "shape"),
        "diagonal_image_frame": ("diagonal_panels", "image_frame"),
        "layered_card": ("cards", "shape_group"),
        "premium_kpi_card": ("kpi_cards", "shape_group"),
        "radial_process": ("radial_maps", "shape_group"),
        "curved_timeline": ("timeline_blocks", "shape_group"),
        "comparison_matrix": ("table_modules", "table_frame"),
        "thin_grid_table": ("table_modules", "table_frame"),
        "chart_module": ("chart_modules", "chart_frame"),
        "insight_callout": ("insight_blocks", "shape_group"),
        "citation_strip": ("footer_system", "footer"),
        "background_topology_grid": ("background_ornaments", "ornament"),
        "expressive_cover_identity": ("background_ornaments", "shape_group"),
        "vertical_index_rail": ("index_navigation", "shape_group"),
        "diagonal_hero_panel": ("diagonal_panels", "image_frame"),
        "fractured_geometry_panel": ("diagonal_panels", "shape_group"),
        "topology_grid_layer": ("background_ornaments", "shape_group"),
        "dark_header_band": ("section_tabs", "shape"),
        "citation_micro_footer": ("footer_system", "footer"),
        "creative_section_tab": ("section_tabs", "shape_group"),
        "glass_overlay_card": ("cards", "shape_group"),
    }
    plan_by_family: dict[str, dict[str, Any]] = {}
    for item in component_plan.get("components") or []:
        if not isinstance(item, dict):
            continue
        family = str(item.get("component_family") or "").strip()
        if not family:
            continue
        plan_by_family[family] = item
        primitive = str(item.get("implementation_primitive") or "PPT shape + PPT text")
        components[family] = {
            "component_id": family,
            "type": type_aliases.get(primitive, _safe_id(primitive)),
            "editable": True,
            "default_tokens": {
                "source": "component_translation_plan",
                "implementation_primitive": primitive,
                "editable_ppt_translation": item.get("editable_ppt_translation"),
                "style_tokens_used": item.get("style_tokens_used") or [],
                "density_variants": item.get("density_variants") or [],
                "tone_variants": item.get("tone_variants") or [],
                "source_evidence": item.get("source_evidence") or {},
                "forbidden": item.get("forbidden") or [],
                "forbidden_rasterization": item.get("forbidden_rasterization", True),
            },
        }
    for component_id in CANONICAL_COMPONENTS:
        source_family, default_type = canonical_mapping[component_id]
        source = plan_by_family.get(source_family, {})
        primitive = str(source.get("implementation_primitive") or "PPT shape + PPT text")
        components[component_id] = {
            "component_id": component_id,
            "type": type_aliases.get(primitive, default_type),
            "editable": True,
            "default_tokens": {
                "source": "component_translation_plan",
                "source_component_family": source_family,
                "implementation_primitive": primitive,
                "editable_ppt_translation": source.get("editable_ppt_translation") or ["shape", "text_box"],
                "style_tokens_used": source.get("style_tokens_used") or [],
                "density_variants": source.get("density_variants") or source.get("allowed_variants") or [],
                "tone_variants": source.get("tone_variants") or [],
                "source_evidence": source.get("source_evidence") or {},
                "forbidden": source.get("forbidden") or ["full-slide raster image", "rasterized text", "rasterized chart/table"],
                "forbidden_rasterization": source.get("forbidden_rasterization", True),
            },
        }
    return list(components.values())


def _apply_layout_family_plan(
    board_layouts: list[dict[str, Any]],
    archetypes: list[dict[str, Any]],
    layout_family_plan: dict[str, Any],
    component_translation_plan: dict[str, Any],
    visual_fidelity_targets: dict[str, Any],
) -> list[dict[str, Any]]:
    family_by_archetype: dict[str, dict[str, Any]] = {}
    for family in layout_family_plan.get("families") or []:
        if not isinstance(family, dict):
            continue
        for archetype_id in family.get("member_archetype_ids") or []:
            family_by_archetype[_safe_id(archetype_id)] = family
    archetype_by_id = {_safe_id(item.get("archetype_id")): item for item in archetypes if isinstance(item, dict)}
    primitive_mapping = {
        str(item.get("component_family")): str(item.get("implementation_primitive"))
        for item in component_translation_plan.get("components") or []
        if isinstance(item, dict) and item.get("component_family")
    }
    fidelity_refs = sorted((visual_fidelity_targets.get("targets") or {}).keys())
    enriched: list[dict[str, Any]] = []
    for layout in board_layouts:
        layout = copy.deepcopy(layout)
        archetype_key = _safe_id(layout.get("archetype_id"))
        source_archetype = archetype_by_id.get(archetype_key, {})
        family = family_by_archetype.get(archetype_key, {})
        layout["layout_family_id"] = str(family.get("family_id") or "unassigned_board_family")
        layout["source_archetype_ids"] = [str(item) for item in family.get("member_archetype_ids") or [source_archetype.get("archetype_id") or layout.get("archetype_id")]]
        layout["compatible_slide_types"] = list(family.get("compatible_slide_types") or layout.get("compatible_slide_types") or [])
        layout["required_slots"] = list(family.get("required_slots") or layout.get("required_slots") or [])
        layout["optional_slots"] = list(family.get("optional_slots") or layout.get("optional_slots") or [])
        layout["geometry_strategy"] = dict(family.get("geometry_strategy") or {"coordinate_system": "normalized_0_1 converted to inches"})
        layout["component_bindings"] = _component_bindings_from_family(layout, family)
        _apply_expressive_cover_divider_components(layout)
        component_ids = list((layout.get("component_bindings") or {}).values())
        layout["editable_primitive_mapping"] = {
            component_id: primitive_mapping.get(component_id, "PPT shape + PPT text")
            for component_id in sorted(set(component_ids + list(family.get("component_bindings") or [])))
            if component_id
        }
        layout["variation_rules"] = [str(item) for item in family.get("variation_rules_for_large_decks") or []]
        layout["deck_scale_fit"] = dict(source_archetype.get("deck_scale_fit") or {})
        layout["tone_affinity"] = dict(source_archetype.get("tone_affinity") or {})
        layout["fidelity_target_references"] = fidelity_refs
        enriched.append(layout)
    return enriched


def _apply_expressive_cover_divider_components(layout: dict[str, Any]) -> None:
    if layout.get("layout_family_id") != "expressive_cover_divider":
        return
    archetype_id = str(layout.get("archetype_id") or "")
    bindings = dict(layout.get("component_bindings") or {})
    bindings["_family_primary"] = "expressive_cover_identity"
    bindings["_ornament_layer"] = "topology_grid_layer"
    bindings["_index_system"] = "vertical_index_rail"
    bindings["_footer_system"] = "citation_micro_footer"
    bindings["_fracture_system"] = "fractured_geometry_panel"
    if archetype_id == "creative_cover":
        bindings["date_presenter"] = "glass_overlay_card"
        bindings["hero_image"] = "diagonal_hero_panel"
        bindings["footer"] = "citation_micro_footer"
        bindings["section_number"] = "creative_section_tab"
    elif archetype_id == "section_divider":
        bindings["section_number"] = "oversized_section_number"
        bindings["section_icon"] = "creative_section_tab"
        bindings["hero_image"] = "fractured_geometry_panel"
        bindings["footer"] = "citation_micro_footer"
        bindings["_header_band"] = "dark_header_band"
    layout["component_bindings"] = bindings
    for slot in layout.get("slots") or []:
        slot_id = str(slot.get("slot_id") or "")
        if slot_id in bindings and not slot_id.startswith("_"):
            slot["component_id"] = bindings[slot_id]


def _component_bindings_from_family(layout: dict[str, Any], family: dict[str, Any]) -> dict[str, str]:
    existing = dict(layout.get("component_bindings") or {})
    family_components = [str(item) for item in family.get("component_bindings") or []]
    if not family_components:
        return existing
    for slot in layout.get("slots") or []:
        slot_id = str(slot.get("slot_id") or "")
        component_id = str(slot.get("component_id") or "")
        if slot_id and component_id:
            existing[slot_id] = component_id
    existing.setdefault("_family_primary", family_components[0])
    return existing


def _layout_from_archetype(archetype: dict[str, Any]) -> dict[str, Any]:
    archetype_id = _safe_id(archetype["archetype_id"])
    slots = _slots_from_archetype(archetype)
    component_bindings = {slot["slot_id"]: slot.get("component_id", "") for slot in slots}
    return {
        "layout_id": f"layout-board-{archetype_id}",
        "archetype_id": archetype_id,
        "slide_type": archetype["source_prompt_slide_type"],
        "density": archetype["recommended_density"],
        "compatible_slide_types": archetype["compatible_slide_types"],
        "required_slots": archetype["required_slots"],
        "optional_slots": archetype["optional_slots"],
        "density_range": _density_range(archetype["recommended_density"]),
        "component_bindings": component_bindings,
        "image_policy": archetype["image_policy"],
        "chart_table_policy": archetype["chart_table_policy"],
        "fallback_layout": archetype["fallback_layout"],
        "layout_geometry_description": archetype["layout_geometry_description"],
        "extraction_geometry_source": "extracted_slide_archetypes.slot_geometry",
        "normalized_geometry": archetype["normalized_geometry"],
        "slots": slots,
    }


def _slots_from_archetype(archetype: dict[str, Any]) -> list[dict[str, Any]]:
    if archetype.get("slot_geometry"):
        return [_slot_from_geometry(slot, archetype) for slot in archetype["slot_geometry"]]
    slide_type = archetype["source_prompt_slide_type"]
    required = set(archetype.get("required_slots") or [])
    slots = [
        _slot("title", "text", "title" in required or True, "title_block", 0.6, 0.42, 8.8, 0.72),
        _slot("footer", "text", "footer" in required, "dense_footer", 0.6, 6.86, 12.1, 0.3),
    ]
    if slide_type in {"creative_cover"}:
        slots.extend([
            _slot("subtitle", "text", False, "title_block", 0.6, 1.24, 5.8, 0.55),
            _slot("hero_image", "image", False, "diagonal_image_frame", 7.1, 0.55, 5.55, 5.75),
            _slot("section_number", "shape", False, "oversized_section_number", 0.6, 5.85, 2.0, 0.55),
        ])
    elif slide_type in {"visual_table_of_contents"}:
        slots.append(_slot("index_navigation", "content", True, "index_navigation", 0.8, 1.35, 11.75, 4.9))
    elif slide_type in {"section_divider"}:
        slots.extend([
            _slot("section_number", "shape", True, "oversized_section_number", 0.72, 1.35, 2.6, 2.4),
            _slot("section_tabs", "content", False, "index_navigation", 4.0, 2.0, 7.9, 1.25),
        ])
    elif slide_type in {"comparison_matrix", "data_table_appendix"}:
        slots.append(_slot("matrix" if slide_type == "comparison_matrix" else "table", "table", True, "thin_grid_table", 0.6, 1.32, 12.1, 5.18))
    elif slide_type in {"kpi_donut_chart"}:
        slots.extend([
            _slot("metric_panels", "content", False, "premium_kpi_card", 0.6, 1.32, 3.8, 4.95),
            _slot("primary_chart", "chart", True, "chart_module", 4.8, 1.32, 7.9, 4.95),
        ])
    elif slide_type in {"timeline_roadmap", "work_support_sequence"}:
        slots.append(_slot("timeline_steps", "content", True, "curved_timeline", 0.75, 2.05, 11.8, 2.95))
    elif slide_type in {"circular_process", "concept_relationship_venn"}:
        slots.append(_slot("process_visual", "content", True, "radial_process", 2.0, 1.25, 9.35, 5.15))
    elif slide_type in {"technical_flow_chart", "methodology_framework", "literature_map"}:
        slots.append(_slot("diagram", "content", True, "radial_process", 0.8, 1.35, 11.75, 4.95))
    elif slide_type in {"photo_caption_grid"}:
        slots.extend([
            _slot("photo_frame", "image", False, "diagonal_image_frame", 0.75, 1.35, 4.0, 4.85),
            _slot("caption_cards", "content", True, "layered_card", 5.05, 1.35, 7.45, 4.85),
        ])
    elif slide_type in {"three_level_explanation"}:
        slots.append(_slot("cards", "content", True, "layered_card", 0.75, 1.35, 11.8, 4.9))
    else:
        slots.extend([
            _slot("body", "content", True, "layered_card", 0.65, 1.35, 7.7, 4.95),
            _slot("insight", "content", False, "insight_callout", 8.7, 1.35, 3.95, 4.95),
        ])
    return slots


def _slot_from_geometry(slot: dict[str, Any], archetype: dict[str, Any]) -> dict[str, Any]:
    slot_id = str(slot["slot_id"])
    role = str(slot["role"])
    slot_type = _slot_type_from_role(role, slot_id)
    required = slot_id in set(archetype.get("required_slots") or []) or int(slot.get("priority") or 99) <= 2
    component_id = _component_for_role(role, slot_id)
    bounds = _normalized_to_inches(slot)
    return {
        "slot_id": slot_id,
        "slot_type": slot_type,
        "required": required,
        "component_id": component_id,
        "bounds": bounds,
    }


def _normalized_to_inches(slot: dict[str, Any]) -> dict[str, float]:
    return {
        "x": round(float(slot["x"]) * CANVAS["width"], 3),
        "y": round(float(slot["y"]) * CANVAS["height"], 3),
        "w": round(float(slot["w"]) * CANVAS["width"], 3),
        "h": round(float(slot["h"]) * CANVAS["height"], 3),
    }


def _slot_type_from_role(role: str, slot_id: str) -> str:
    text = f"{role} {slot_id}".lower()
    if "title" in text or "subtitle" in text or "footer" in text:
        return "text"
    if "table" in text or "matrix" in text:
        return "table"
    if "chart" in text or "kpi" in text:
        return "chart" if "chart" in text else "content"
    if "image" in text or "photo" in text:
        return "image"
    if "section_marker" in text:
        return "shape"
    return "content"


def _component_for_role(role: str, slot_id: str) -> str:
    text = f"{role} {slot_id}".lower()
    if "footer" in text:
        return "dense_footer"
    if "title" in text or "subtitle" in text:
        return "title_block"
    if "image" in text or "photo" in text:
        return "diagonal_image_frame"
    if "chart" in text:
        return "chart_module"
    if "table" in text or "matrix" in text:
        return "thin_grid_table"
    if "kpi" in text:
        return "premium_kpi_card"
    if "timeline" in text or "sequence" in text:
        return "curved_timeline"
    if "diagram" in text or "process" in text or "relationship" in text:
        return "radial_process"
    if "section" in text:
        return "oversized_section_number"
    if "navigation" in text:
        return "index_navigation"
    if "insight" in text:
        return "insight_callout"
    return "layered_card"


def _merge_layouts(board_layouts: list[dict[str, Any]], base_spec: dict[str, Any] | None) -> list[dict[str, Any]]:
    merged = {layout["layout_id"]: layout for layout in board_layouts}
    for layout in (base_spec or {}).get("layouts") or []:
        if isinstance(layout, dict) and layout.get("layout_id") not in merged:
            merged[layout["layout_id"]] = copy.deepcopy(layout)
    return list(merged.values())


def _slot(slot_id: str, slot_type: str, required: bool, component_id: str, x: float, y: float, w: float, h: float) -> dict[str, Any]:
    return {"slot_id": slot_id, "slot_type": slot_type, "required": required, "component_id": component_id, "bounds": {"x": x, "y": y, "w": w, "h": h}}


def _slot_definitions(layouts: list[dict[str, Any]]) -> dict[str, Any]:
    definitions = {}
    for layout in layouts:
        for slot in layout["slots"]:
            definitions[f"{layout['layout_id']}.{slot['slot_id']}"] = {
                "slot_type": slot["slot_type"],
                "required": slot["required"],
                "bounds": slot["bounds"],
            }
    return definitions


def _primitives(layouts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    primitives = {}
    for layout in layouts:
        for slot in layout["slots"]:
            kind = _primitive_kind(slot["slot_type"])
            primitive_id = f"primitive-{slot.get('component_id') or slot['slot_id']}-{kind}"
            primitives.setdefault(primitive_id, {"primitive_id": primitive_id, "kind": kind, "editable": True, "bounds": slot["bounds"]})
    return list(primitives.values())


def _asset_policy(base_spec: dict[str, Any] | None) -> dict[str, Any]:
    policy = copy.deepcopy((base_spec or {}).get("asset_policy") or {})
    policy.update({
        "allow_full_slide_raster": False,
        "image_usage": "Design board images are references only; final decks may use images only inside declared image/photo frames.",
        "text_editable": True,
        "tables_editable": True,
        "charts_editable": True,
        "icons": "SVG",
        "ornaments": "SVG or PPT lines",
        "photos": "Only inside image frames",
        "no_full_slide_raster_background": True,
    })
    return policy


def _deck_scale_rules_from_plan(deck_scale_plan: dict[str, Any]) -> dict[str, str]:
    rules: dict[str, str] = {}
    for scale_id in ("small", "medium", "large", "very_large"):
        scale = (deck_scale_plan.get("scales") or {}).get(scale_id) or {}
        rules[scale_id] = "; ".join(
            str(scale.get(key) or "")
            for key in ("layout_rotation_rules", "section_rhythm", "performance_constraints")
            if scale.get(key)
        ) or f"Use {scale_id} deck defaults from production plan."
    return rules


def _production_notes(production_plans: dict[str, dict[str, Any]]) -> list[str]:
    template_plan = production_plans["template_production_plan"]
    fidelity = production_plans["visual_fidelity_targets"]
    notes = [
        "Use design production plan as the primary editable template planning source.",
        "Raw Codex extraction artifacts remain source evidence, not the final production decision layer.",
        "Do not insert the design board image or design board crops into final slides.",
    ]
    for item in template_plan.get("implementation_order") or []:
        notes.append(f"Implementation order: {item}")
    targets = fidelity.get("targets") or {}
    if targets:
        notes.append(f"Maximum generic layout ratio: {targets.get('maximum_generic_layout_ratio')}")
        notes.append(f"Maximum fallback ratio: {targets.get('maximum_fallback_ratio')}")
    return notes


def _report(
    spec: dict[str, Any],
    design_board: dict[str, Any],
    archetypes: dict[str, Any],
    warnings: list[dict[str, Any]],
    production_plans: dict[str, dict[str, Any]] | None,
) -> dict[str, Any]:
    board_layout_count = sum(1 for layout in spec["layouts"] if str(layout["layout_id"]).startswith("layout-board-"))
    generic_fallback_layouts = [
        layout["layout_id"]
        for layout in spec["layouts"]
        if str(layout.get("layout_id") or "").endswith("-mvp") or "mvp" in str(layout.get("layout_id") or "")
    ]
    layout_family_count = len((production_plans or {}).get("layout_family_plan", {}).get("families") or [])
    component_family_count = len((production_plans or {}).get("component_translation_plan", {}).get("components") or [])
    visual_fidelity_target_count = len((production_plans or {}).get("visual_fidelity_targets", {}).get("targets") or {})
    return {
        "schema_name": "template_spec_from_design_board_report",
        "schema_version": "1.0",
        "status": "passed",
        "prompt_id": design_board["prompt_id"],
        "output_path": "outputs/editable_template_spec.final.json",
        "design_id": spec["design_id"],
        "layout_count": len(spec["layouts"]),
        "extracted_layout_count": board_layout_count,
        "component_count": len(spec["components"]),
        "production_plan_used": production_plans is not None,
        "layout_family_count": layout_family_count,
        "component_family_count": component_family_count,
        "visual_fidelity_target_count": visual_fidelity_target_count,
        "generic_fallback_layouts": generic_fallback_layouts,
        "tone_variants": sorted((spec["tokens"]["typography"].get("tone_variants") or {}).keys()),
        "asset_policy": spec["asset_policy"],
        "deck_scale_rules": spec["tokens"]["shadows"].get("deck_scale_rules", {}),
        "provenance": spec.get("provenance", {}),
        "layouts_derived_from_extraction_geometry": all(
            str(layout.get("extraction_geometry_source") or "").startswith("extracted_slide_archetypes")
            for layout in spec["layouts"]
            if str(layout.get("layout_id") or "").startswith("layout-board-")
        ),
        "source_archetype_count": len(archetypes.get("archetypes") or []),
        "warnings": warnings,
    }


def _load_production_plans(
    *,
    premium_mode: bool,
    template_production_plan_path: str | Path,
    component_translation_plan_path: str | Path,
    layout_family_plan_path: str | Path,
    deck_scale_usage_plan_path: str | Path,
    visual_fidelity_targets_path: str | Path,
) -> dict[str, dict[str, Any]] | None:
    paths = {
        "template_production_plan": Path(template_production_plan_path),
        "component_translation_plan": Path(component_translation_plan_path),
        "layout_family_plan": Path(layout_family_plan_path),
        "deck_scale_usage_plan": Path(deck_scale_usage_plan_path),
        "visual_fidelity_targets": Path(visual_fidelity_targets_path),
    }
    missing = [path.as_posix() for path in paths.values() if not path.exists()]
    if missing:
        if premium_mode:
            raise ValueError("premium design-board build requires design production plan artifacts: " + ", ".join(missing))
        return None
    plans = {key: _load_json(path) for key, path in paths.items()}
    _validate_production_plans(plans)
    plans["_paths"] = {key: path.as_posix() for key, path in paths.items()}  # type: ignore[assignment]
    return plans


def _validate_production_plans(plans: dict[str, dict[str, Any]]) -> None:
    required = {
        "template_production_plan": "template_production_plan",
        "component_translation_plan": "component_translation_plan",
        "layout_family_plan": "layout_family_plan",
        "deck_scale_usage_plan": "deck_scale_usage_plan",
        "visual_fidelity_targets": "visual_fidelity_targets",
    }
    prompt_ids = set()
    for key, schema_name in required.items():
        payload = plans.get(key)
        if not isinstance(payload, dict) or payload.get("schema_name") != schema_name:
            raise ValueError(f"{key} must be a {schema_name} artifact")
        if payload.get("prompt_id"):
            prompt_ids.add(str(payload["prompt_id"]))
    if prompt_ids and prompt_ids != {"creative_academic_template_board_v1"}:
        raise ValueError(f"design production plan prompt_id mismatch: {sorted(prompt_ids)}")
    if not plans["component_translation_plan"].get("components"):
        raise ValueError("component_translation_plan.components must not be empty")
    if not plans["layout_family_plan"].get("families"):
        raise ValueError("layout_family_plan.families must not be empty")
    if not plans["visual_fidelity_targets"].get("targets"):
        raise ValueError("visual_fidelity_targets.targets must not be empty")


def _production_plan_file_report(production_plans: dict[str, dict[str, Any]] | None) -> list[dict[str, str]]:
    if not production_plans:
        return []
    paths = production_plans.get("_paths") or {}
    return [{"artifact": key, "path": value} for key, value in sorted(paths.items())]


def _load_contract_or_sample(
    path: str | Path,
    sample_path: Path,
    validator: Any,
    warnings: list[dict[str, Any]],
    missing_label: str,
    *,
    allow_schema_sample_fallback: bool,
    loaded: list[dict[str, Any]],
) -> dict[str, Any]:
    candidate = Path(path)
    if candidate.exists():
        payload = _load_json(candidate)
        validator(payload)
        loaded.append({"path": candidate.as_posix(), "source": "actual"})
        return payload
    if not allow_schema_sample_fallback:
        raise ValueError(f"{missing_label}: {candidate.as_posix()}; schema sample fallback is disabled outside explicit sample mode")
    warnings.append(_warning("MISSING_DESIGN_BOARD_EXTRACTION" if "design board" in missing_label else "MISSING_EXTRACTION_ARTIFACT", f"{missing_label}: {candidate.as_posix()}; using schema sample fixture.", {"path": candidate.as_posix(), "sample": sample_path.as_posix()}))
    payload = _load_json(sample_path)
    validator(payload)
    loaded.append({"path": sample_path.as_posix(), "requested_path": candidate.as_posix(), "source": "schema_sample", "reason": missing_label})
    return payload


def _is_premium_mode(board_manifest: dict[str, Any] | None, extraction_mode: str) -> bool:
    if extraction_mode == "premium":
        return True
    if extraction_mode == "sample":
        return False
    return bool(
        board_manifest
        and board_manifest.get("generation_mode") == "manual_codex"
        and board_manifest.get("premium_design_candidate") is True
    )


def _assert_premium_extraction(
    *,
    extraction_source: str,
    design_board: dict[str, Any],
    board_manifest: dict[str, Any] | None,
    loaded: list[dict[str, Any]],
) -> None:
    if extraction_source != "actual":
        raise ValueError("premium design-board build requires actual extraction artifacts; schema sample fallback is forbidden")
    if not board_manifest:
        raise ValueError("premium design-board build requires template_design_board_manifest.json")
    prompt_id = board_manifest.get("prompt_id")
    if prompt_id != "creative_academic_template_board_v1":
        raise ValueError(f"premium design-board build requires prompt_id creative_academic_template_board_v1, got {prompt_id!r}")
    if design_board.get("prompt_id") != prompt_id:
        raise ValueError(f"extracted design board prompt_id {design_board.get('prompt_id')!r} does not match manifest prompt_id {prompt_id!r}")
    manifest_board_path = board_manifest.get("board_image_path")
    if design_board.get("board_image_path") != manifest_board_path:
        raise ValueError(
            f"extracted board_image_path {design_board.get('board_image_path')!r} does not match manifest board_image_path {manifest_board_path!r}"
        )
    missing_actual = [item for item in loaded if item.get("source") != "actual"]
    if missing_actual:
        raise ValueError(f"premium design-board build requires all extraction files to be actual: {missing_actual}")


def _load_optional_base_spec(path: str | Path, warnings: list[dict[str, Any]]) -> dict[str, Any] | None:
    candidate = Path(path)
    if not candidate.exists():
        warnings.append(_warning("FALLBACK_TO_BASE_SPEC_UNAVAILABLE", f"Base editable template spec not found at {candidate.as_posix()}; building from board extraction only."))
        return None
    try:
        payload = _load_json(candidate)
        validateEditableTemplateSpec(payload)
        return payload
    except Exception as exc:
        warnings.append(_warning("FALLBACK_TO_BASE_SPEC_FAILED", f"Base editable template spec could not be used: {exc}"))
        return None


def _markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# Template Spec From Design Board Report",
        "",
        f"Status: `{report['status']}`",
        f"Prompt: `{report['prompt_id']}`",
        f"Output: `{report['output_path']}`",
        f"Design id: `{report['design_id']}`",
        f"Layouts: `{report['layout_count']}`",
        f"Extracted board layouts: `{report['extracted_layout_count']}`",
        f"Components: `{report['component_count']}`",
        f"Production plan used: `{report.get('production_plan_used')}`",
        f"Extraction source: `{report.get('extraction_source')}`",
        f"Fallback used: `{report.get('fallback_used')}`",
        f"Layout families: `{report.get('layout_family_count')}`",
        f"Component families: `{report.get('component_family_count')}`",
        f"Visual fidelity targets: `{report.get('visual_fidelity_target_count')}`",
        f"Tone variants: `{', '.join(report['tone_variants'])}`",
        f"Generic fallback layouts: `{len(report.get('generic_fallback_layouts') or [])}`",
        "",
        "## Warnings",
        "",
    ]
    if report["warnings"]:
        for warning in report["warnings"]:
            lines.append(f"- `{warning['code']}`: {warning['message']}")
    else:
        lines.append("- None")
    return "\n".join(lines) + "\n"


def _typography_token(value: Any, family: str, size: float, weight: str) -> dict[str, Any]:
    payload = value if isinstance(value, dict) else {}
    return {
        "font_family": str(payload.get("font_family") or family),
        "size_pt": float(payload.get("size_pt") or size),
        "weight": str(payload.get("weight") or weight),
    }


def _numeric_tokens(base_value: Any, extracted_value: Any, defaults: dict[str, float]) -> dict[str, float]:
    result = {key: float(value) for key, value in defaults.items()}
    for source in (base_value, extracted_value):
        if not isinstance(source, dict):
            continue
        for key, value in source.items():
            if isinstance(value, (int, float)):
                result[_safe_id(key)] = float(value)
    return result


def _coerce_float(value: Any, *, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _primitive_kind(slot_type: str) -> str:
    return {"text": "text_box", "content": "shape", "shape": "shape", "table": "table", "chart": "chart", "image": "image_frame"}.get(slot_type, "shape")


def _density_range(density: str) -> list[str]:
    if density == "high":
        return ["medium", "high"]
    if density == "low":
        return ["low", "medium"]
    return ["medium"]


def _color_alias(token: str) -> str:
    return {"ink": "text"}.get(str(token), _safe_id(token))


def _safe_id(value: Any) -> str:
    text = str(value or "").strip().lower().replace("-", "_")
    return "_".join("".join(char if char.isalnum() else "_" for char in text).split("_")) or "item"


def _warning(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = {"code": code, "severity": "warning", "message": message}
    if details:
        payload["details"] = details
    return payload


def _load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _load_optional_json(path: str | Path) -> Any:
    candidate = Path(path)
    if not candidate.exists():
        return None
    return _load_json(candidate)


if __name__ == "__main__":
    raise SystemExit(main())
