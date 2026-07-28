"""Planning helpers for the run_002 12-archetype expansion gate."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Iterable

from presentation_agent.contracts.warning_policy import DEFAULT_FATAL_WARNING_CODES
from presentation_agent.qa.visual_product_gate import find_placeholder_leakage


CORE_ARCHETYPES: tuple[str, ...] = (
    "cover_hero",
    "standard_content",
    "data_dashboard",
    "table_heavy",
)

NEW_ARCHETYPES: tuple[str, ...] = (
    "section_divider",
    "visual_toc",
    "evidence_overview",
    "card_grid",
    "methodology_framework",
    "process_flow",
    "comparison_matrix",
    "timeline_roadmap",
)

ALL_ARCHETYPES: tuple[str, ...] = (*CORE_ARCHETYPES, *NEW_ARCHETYPES)

VISUAL_SYSTEM_TOKENS: dict[str, Any] = {
    "palette": {
        "primary_navy": "#06131D",
        "dark_teal": "#113C3E",
        "panel_teal": "#0F4652",
        "off_white": "#F7F1E4",
        "gold": "#DDB45B",
        "cyan": "#56C7D9",
        "coral": "#EF6B5A",
        "sage": "#A7C4A0",
    },
    "shape_language": [
        "editorial diagonal fields",
        "thin technical dividers",
        "source strip with citation-ready metadata",
        "bounded off-white content panels on dark ink grounds",
        "SVG/vector icon slots for semantic marks",
    ],
    "typography_policy": {
        "real_text": "ppt_text",
        "placeholder_labels": "semantic only during template stage",
        "source_filled_demo": "no visible TITLE/BODY/VALUE/TABLE placeholders",
    },
}

CORE_VISUAL_MATRIX: dict[str, dict[str, Any]] = {
    "cover_hero": {
        "composition_family": "editorial_hero",
        "primary_information_structure": "title-led hero with diagonal replaceable image frame",
        "density_level": "low",
        "visual_motif": "masthead plus diagonal hero frame",
        "protected_text_zones": ["title", "subtitle", "meta_bar"],
        "semantic_components": ["replaceable hero image frame", "editable meta bar", "editable source strip"],
        "source_strip_policy": "editable footer/source strip; binding required in source-bound stage",
        "chart_table_policy": "not applicable",
        "icon_policy": "decorative ornaments only; semantic icons must be SVG/vector if used",
        "allowed_raster_policy": "photo_frame_only",
        "visual_distinction_from_other_archetypes": "Only archetype with dominant hero image frame and cover masthead.",
        "source_bound_use_cases": ["opening slide", "executive narrative setup"],
        "orientation_tags": ["narrative_navigation"],
    },
    "standard_content": {
        "composition_family": "editorial_cards",
        "primary_information_structure": "evidence cards with insight strip",
        "density_level": "medium",
        "visual_motif": "stacked editorial evidence modules",
        "protected_text_zones": ["title", "body_or_card_group", "takeaway_or_insight"],
        "semantic_components": ["editable cards", "editable dividers", "editable insight strip"],
        "source_strip_policy": "editable source strip required for source-bound content slides",
        "chart_table_policy": "not applicable",
        "icon_policy": "SVG/vector icons only where semantic",
        "allowed_raster_policy": "no content-bearing raster",
        "visual_distinction_from_other_archetypes": "Card narrative slide with one executive insight band.",
        "source_bound_use_cases": ["argument development", "evidence-backed recommendations"],
        "orientation_tags": ["card_grid_dominant"],
    },
    "data_dashboard": {
        "composition_family": "dashboard_data",
        "primary_information_structure": "KPI rail plus editable shape charts and insight panel",
        "density_level": "dense",
        "visual_motif": "portfolio signal board",
        "protected_text_zones": ["title", "kpi_cards", "primary_chart", "source_strip"],
        "semantic_components": ["editable KPI cards", "editable shape charts", "SVG/vector icons"],
        "source_strip_policy": "editable source strip required for source-bound data slides",
        "chart_table_policy": "native chart or editable shape chart only",
        "icon_policy": "semantic icons must resolve to SVG/vector",
        "allowed_raster_policy": "no semantic raster",
        "visual_distinction_from_other_archetypes": "Only archetype combining KPI rail with multi-chart evidence.",
        "source_bound_use_cases": ["metrics review", "portfolio readiness"],
        "orientation_tags": ["data_evidence", "dense_information"],
    },
    "table_heavy": {
        "composition_family": "dense_table",
        "primary_information_structure": "editable native table with side metrics",
        "density_level": "dense",
        "visual_motif": "review matrix with grouped rows",
        "protected_text_zones": ["title", "table_region", "source_strip"],
        "semantic_components": ["native PPT table", "editable row emphasis", "editable source strip"],
        "source_strip_policy": "editable source strip required for source-bound table slides",
        "chart_table_policy": "native PPT table or editable shape-grid only",
        "icon_policy": "SVG/vector icons only if used as row markers",
        "allowed_raster_policy": "no table raster",
        "visual_distinction_from_other_archetypes": "Highest row/column density and native table emphasis.",
        "source_bound_use_cases": ["artifact register", "criteria table", "control review"],
        "orientation_tags": ["data_evidence", "dense_information"],
    },
}


def all_archetype_ids() -> tuple[str, ...]:
    return ALL_ARCHETYPES


def new_archetype_ids() -> tuple[str, ...]:
    return NEW_ARCHETYPES


def build_new_archetype_plan(archetype_id: str) -> dict[str, Any]:
    if archetype_id not in NEW_ARCHETYPE_DEFINITIONS:
        raise ValueError(f"unsupported B04 archetype: {archetype_id}")
    return copy.deepcopy(NEW_ARCHETYPE_DEFINITIONS[archetype_id])


def build_contract_v2_for_plan(plan: dict[str, Any]) -> dict[str, Any]:
    slot_contracts = [_slot_contract(slot) for slot in plan["slots"]]
    required_slots = [slot["slot_id"] for slot in slot_contracts if slot["required"]]
    return {
        "$schema": "../../../../../../schemas/template_contract_v2.schema.json",
        "contract_version": "2",
        "archetype_id": plan["archetype_id"],
        "layout_id": f"run_002_{plan['archetype_id']}_contract_v2_plan",
        "required_slots": required_slots,
        "slot_contracts": slot_contracts,
        "editable_object_assertions": {
            "all_real_text_is_ppt_text": True,
            "cards_are_ppt_shapes": True,
            "panels_are_ppt_shapes": True,
            "dividers_are_ppt_shapes": True,
            "footer_is_ppt_shapes_or_text": True,
            "source_strip_is_editable": True,
            "semantic_icons_are_svg_or_vector": True,
            "semantic_tables_are_native_or_editable_shape_grid": True,
            "semantic_charts_are_native_or_editable_shape_chart": True,
            "hero_photo_is_replaceable_frame": True,
            "reference_image_not_embedded_as_background": True,
        },
        "semantic_component_assertions": {
            "text": "ppt_text",
            "cards": "ppt_shape_groups",
            "panels": "ppt_shapes",
            "connectors": "ppt_shapes",
            "icons": "svg_or_vector",
            "tables": plan["chart_table_policy"],
            "charts": plan["chart_table_policy"],
        },
        "asset_policy": {
            "reference_images_allowed_as_design_inputs_only": True,
            "reference_images_may_be_embedded": False,
            "semantic_svg_icons_required": True,
        },
        "raster_policy": {
            "full_slide_raster_allowed": False,
            "content_bearing_raster_allowed": False,
            "photo_frame_raster_allowed": True,
            "texture_raster_allowed": "allowlisted_only",
            "semantic_component_raster_allowed": False,
        },
        "fallback_policy": {
            "fallback_allowed": False,
            "semantic_component_fallback_allowed": False,
            "all_fallbacks_must_be_recorded": True,
            "unrecorded_fallback_is_fatal": True,
            "raster_fallback_requires_allowlist": True,
        },
        "overflow_policy": {
            "text_overflow_allowed": False,
            "unbounded_placeholder_content_allowed": False,
            "source_bound_stage_overflow_must_fail": True,
        },
        "protected_zones": [
            {
                "zone_id": f"{slot['slot_id']}_safe",
                "bbox": slot["bbox"],
                "intrusion_allowed": False,
            }
            for slot in plan["slots"]
            if slot["required"]
        ],
        "source_binding_requirements": {
            "required_for_content_slides": bool(plan["source_binding_required_for_content"]),
            "required_slot_types": plan["source_required_slot_types"],
            "template_stage_placeholder_allowed": True,
            "source_bound_stage_requirement_declared_for": "B05",
        },
        "citation_binding_requirements": {
            "required_for_content_slides": bool(plan["citation_binding_required_for_content"]),
            "required_slot_types": plan["citation_required_slot_types"],
            "template_stage_placeholder_allowed": True,
            "source_bound_stage_requirement_declared_for": "B05",
        },
        "render_policy": {
            "render_required": False,
            "renderer_skip_allowed": True,
            "structural_ledger_required_if_render_skipped": True,
        },
        "structural_ledger_requirements": {
            "required": True,
            "min_slide_count": 1,
            "require_object_ledger": True,
            "required_ledgers": [
                "ooxml",
                "object",
                "text",
                "media",
                "slot_coverage",
                "protected_zone",
            ],
        },
        "warning_policy": {
            "fatal_codes": sorted(DEFAULT_FATAL_WARNING_CODES),
            "allowlist": [],
        },
        "qa_policy": {
            "qa_report_required": True,
            "zero_unallowlisted_warnings": True,
            "selected_route_required": "editable_template",
        },
        "template_stage_policy": {
            "semantic_placeholders_allowed": True,
            "placeholder_text_must_not_be_final_content": True,
            "source_citation_binding_deferred_to_source_bound_stage": True,
        },
        "b04_plan_evidence": {
            "visual_system_tokens": "B03.5 accepted tokens",
            "reference_image_status": "not_required_for_plan_precompile",
            "source_bound_stage": "deferred_to_B05",
        },
    }


def build_template_stage_blueprint(contract: dict[str, Any], fixture: dict[str, Any]) -> dict[str, Any]:
    return {
        "slide_id": f"{contract['archetype_id']}-b04-template-stage",
        "template_stage": True,
        "slots": [
            {
                "slot_id": slot["slot_id"],
                "primitive": _blueprint_primitive(slot),
                "editable": True,
                "placeholder_status": "semantic_template_placeholder",
                "text": _fixture_text_for_slot(slot, fixture),
                "object_id": f"{slot['slot_id']}_b04_plan_object",
            }
            for slot in contract["slot_contracts"]
            if slot["required"]
        ],
    }


def build_visual_diversity_matrix() -> dict[str, Any]:
    archetypes = []
    for archetype_id in ALL_ARCHETYPES:
        if archetype_id in CORE_VISUAL_MATRIX:
            entry = {"archetype_id": archetype_id, **copy.deepcopy(CORE_VISUAL_MATRIX[archetype_id])}
        else:
            plan = build_new_archetype_plan(archetype_id)
            entry = {
                "archetype_id": archetype_id,
                "composition_family": plan["composition_family"],
                "primary_information_structure": plan["primary_information_structure"],
                "density_level": plan["density_level"],
                "visual_motif": plan["visual_motif"],
                "protected_text_zones": plan["protected_text_zones"],
                "semantic_components": plan["semantic_components"],
                "source_strip_policy": plan["source_strip_policy"],
                "chart_table_policy": plan["chart_table_policy"],
                "icon_policy": plan["icon_policy"],
                "allowed_raster_policy": plan["allowed_raster_policy"],
                "visual_distinction_from_other_archetypes": plan["visual_distinction_from_other_archetypes"],
                "source_bound_use_cases": plan["source_bound_use_cases"],
                "orientation_tags": plan["orientation_tags"],
            }
        archetypes.append(entry)
    validation = validate_visual_diversity_matrix({"archetypes": archetypes})
    return {
        "schema_name": "run_002_12_archetype_visual_diversity_matrix",
        "schema_version": "1.0",
        "archetypes": archetypes,
        "validation": validation,
    }


def validate_visual_diversity_matrix(matrix: dict[str, Any]) -> dict[str, Any]:
    archetypes = matrix.get("archetypes") or []
    families = [str(item.get("composition_family")) for item in archetypes]
    tags_by_id = {
        str(item.get("archetype_id")): {str(tag) for tag in item.get("orientation_tags") or []}
        for item in archetypes
    }
    card_grid_count = sum(1 for tags in tags_by_id.values() if "card_grid_dominant" in tags)
    data_count = sum(1 for tags in tags_by_id.values() if "data_evidence" in tags)
    narrative_count = sum(1 for tags in tags_by_id.values() if "narrative_navigation" in tags)
    dense_count = sum(1 for tags in tags_by_id.values() if "dense_information" in tags)
    diagram_count = sum(1 for tags in tags_by_id.values() if "diagram_process" in tags)
    checks = {
        "archetype_count_is_12": len(archetypes) == 12,
        "distinct_composition_families_at_least_5": len(set(families)) >= 5,
        "card_grid_dominant_no_more_than_3": card_grid_count <= 3,
        "data_evidence_at_least_3": data_count >= 3,
        "narrative_navigation_at_least_2": narrative_count >= 2,
        "dense_information_at_least_2": dense_count >= 2,
        "diagram_process_at_least_2": diagram_count >= 2,
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "counts": {
            "distinct_composition_families": len(set(families)),
            "card_grid_dominant": card_grid_count,
            "data_evidence": data_count,
            "narrative_navigation": narrative_count,
            "dense_information": dense_count,
            "diagram_process": diagram_count,
        },
    }


def build_canva_benchmark_registry(search_roots: Iterable[Path]) -> dict[str, Any]:
    candidates: list[str] = []
    excluded_self_references: list[str] = []
    for root in search_roots:
        root_path = Path(root)
        if not root_path.exists():
            continue
        for path in root_path.rglob("*"):
            if not path.is_file():
                continue
            name = path.name.lower()
            if not any(token in name for token in ("canva", "magic", "benchmark")):
                continue
            if _is_self_referential_benchmark_path(path):
                excluded_self_references.append(_display_path(path))
                continue
            if path.suffix.lower() in {".pptx", ".ppt", ".png", ".jpg", ".jpeg", ".pdf", ".json", ".md"}:
                candidates.append(_display_path(path))
    status = "found_local_benchmark_artifacts" if candidates else "benchmark_not_available"
    return {
        "schema_name": "canva_benchmark_registry",
        "schema_version": "1.0",
        "status": status,
        "exact_paths": sorted(dict.fromkeys(candidates)),
        "excluded_self_references": sorted(dict.fromkeys(excluded_self_references)),
        "action_required": None if candidates else "import_canva_benchmark_artifacts",
        "canva_parity_claim_allowed": bool(candidates),
        "policy": "Self-referential B03.5/B04 reports are excluded from benchmark evidence.",
    }


def build_visual_gate_precheck(plan: dict[str, Any], canva_registry: dict[str, Any]) -> dict[str, Any]:
    leakage = find_placeholder_leakage(flatten_fixture_texts(plan["content_fixture"]))
    scores = {
        "visual_ambition": plan["visual_scores"]["visual_ambition"],
        "archetype_identity": plan["visual_scores"]["archetype_identity"],
        "content_capacity": plan["visual_scores"]["content_capacity"],
        "source_filled_fixture_realism": 10 if not leakage else 0,
        "visual_clutter_risk": plan["visual_scores"]["visual_clutter"],
        "protected_zone_integrity_plan": 10,
        "editability_preservation_plan": "pass",
        "canva_benchmark_status": canva_registry["status"],
    }
    failures: list[str] = []
    if leakage:
        failures.append("placeholder_leakage")
    if scores["visual_ambition"] < 7:
        failures.append("visual_ambition_below_threshold")
    if scores["archetype_identity"] < 8:
        failures.append("archetype_identity_below_threshold")
    if plan["visual_distinction_from_other_archetypes"].strip() == "":
        failures.append("missing_visual_distinction")
    classification = "READY_FOR_MASTER_COMPILE" if not failures else "NEEDS_SPEC_PATCH"
    return {
        "schema_name": "b04_visual_gate_precheck",
        "schema_version": "1.0",
        "archetype_id": plan["archetype_id"],
        "classification": classification,
        "passed": classification == "READY_FOR_MASTER_COMPILE",
        "scores": scores,
        "placeholder_leakage": leakage,
        "canva_benchmark_status": canva_registry["status"],
        "findings": failures,
    }


def build_source_bound_readiness(archetype_plans: dict[str, dict[str, Any]]) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for archetype_id in ALL_ARCHETYPES:
        if archetype_id in archetype_plans:
            plan = archetype_plans[archetype_id]
            entries.append(
                {
                    "archetype_id": archetype_id,
                    "served_slide_blueprint_types": plan["served_slide_blueprint_types"],
                    "required_source_fields": plan["required_source_fields"],
                    "required_citation_fields": plan["required_citation_fields"],
                    "supported_content_density": plan["density_level"],
                    "max_capacity": plan["max_capacity"],
                    "fallback_layout_recommendations": plan["fallback_layout_recommendations"],
                    "b05_binding_risks": plan["b05_binding_risks"],
                }
            )
            continue
        core = CORE_VISUAL_MATRIX[archetype_id]
        entries.append(
            {
                "archetype_id": archetype_id,
                "served_slide_blueprint_types": core["source_bound_use_cases"],
                "required_source_fields": ["source_id", "source_excerpt_or_metric", "owner"],
                "required_citation_fields": ["citation_id", "source_label"],
                "supported_content_density": core["density_level"],
                "max_capacity": _core_capacity(archetype_id),
                "fallback_layout_recommendations": "Use accepted B03.5 premium master slot grammar; overflow must fail before compile.",
                "b05_binding_risks": "Low after B03.5; verify real slide_blueprint field mapping before source-bound deck generation.",
            }
        )
    return {
        "schema_name": "run_002_12_archetype_source_bound_readiness",
        "schema_version": "1.0",
        "stage": "B04_precompile_plan",
        "source_bound_deck_generated": False,
        "entries": entries,
        "blocking_policy_for_B05": {
            "source_binding_missing_is_fatal": True,
            "citation_binding_missing_is_fatal": True,
            "placeholder_labels_as_final_content_allowed": False,
            "text_overflow_allowed": False,
        },
    }


def flatten_fixture_texts(value: Any) -> list[str]:
    texts: list[str] = []
    if isinstance(value, str):
        texts.append(value)
    elif isinstance(value, dict):
        for item in value.values():
            texts.extend(flatten_fixture_texts(item))
    elif isinstance(value, list | tuple):
        for item in value:
            texts.extend(flatten_fixture_texts(item))
    return texts


def _slot_contract(slot: dict[str, Any]) -> dict[str, Any]:
    return {
        "slot_id": slot["slot_id"],
        "slot_type": slot["slot_type"],
        "required": bool(slot.get("required", True)),
        "editable_required": True,
        "min_capacity_chars": int(slot["min_capacity_chars"]),
        "max_capacity_chars": int(slot["max_capacity_chars"]),
        "overflow_allowed": False,
        "allowed_primitives": list(slot["allowed_primitives"]),
        "forbidden_primitives": ["raster_image", "full_slide_raster"],
        "source_binding_required": False,
        "citation_binding_required": False,
        "protected_zone_id": f"{slot['slot_id']}_safe",
        "fallback_allowed": False,
        "fallback_allowlist": [],
        "template_stage_placeholder_allowed": True,
        "source_bound_binding_required_later": bool(slot.get("source_bound_binding_required_later", False)),
    }


def _blueprint_primitive(slot: dict[str, Any]) -> str:
    allowed = [str(item) for item in slot.get("allowed_primitives") or []]
    if "ppt_table" in allowed:
        return "ppt_table"
    if "ppt_chart" in allowed:
        return "ppt_chart"
    if "image_frame" in allowed:
        return "image_frame"
    if "svg_or_vector_icon" in allowed and "ppt_text" not in allowed:
        return "svg_or_vector_icon"
    return "ppt_text"


def _fixture_text_for_slot(slot: dict[str, Any], fixture: dict[str, Any]) -> str:
    max_chars = int(slot.get("max_capacity_chars") or 0)
    if max_chars == 0:
        return ""
    text = str(fixture.get("slot_texts", {}).get(slot["slot_id"]) or slot["slot_id"].replace("_", " "))
    return text[:max_chars]


def _is_self_referential_benchmark_path(path: Path) -> bool:
    name = path.name.lower()
    parent_text = path.as_posix().lower()
    return (
        name in {"visual_delta_vs_canva_benchmark.md", "canva_benchmark_registry.json", "canva_benchmark_registry.md"}
        or "12_archetype_expansion/canva_benchmark_registry" in parent_text
        or name.startswith("visual_delta_vs_canva_benchmark")
    )


def _display_path(path: Path) -> str:
    try:
        root = Path(__file__).resolve().parents[3]
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _core_capacity(archetype_id: str) -> dict[str, Any]:
    return {
        "cover_hero": {"title_chars": 54, "subtitle_chars": 96, "cards": 0, "rows": 0},
        "standard_content": {"title_chars": 72, "body_chars": 520, "cards": 4, "rows": 0},
        "data_dashboard": {"title_chars": 72, "kpi_cards": 5, "chart_series": 2, "rows": 0},
        "table_heavy": {"title_chars": 72, "table_rows": 6, "table_columns": 6},
    }[archetype_id]


def _slot(
    slot_id: str,
    slot_type: str,
    min_capacity_chars: int,
    max_capacity_chars: int,
    allowed_primitives: list[str],
    bbox: dict[str, float],
) -> dict[str, Any]:
    return {
        "slot_id": slot_id,
        "slot_type": slot_type,
        "required": True,
        "min_capacity_chars": min_capacity_chars,
        "max_capacity_chars": max_capacity_chars,
        "allowed_primitives": allowed_primitives,
        "bbox": bbox,
    }


NEW_ARCHETYPE_DEFINITIONS: dict[str, dict[str, Any]] = {
    "section_divider": {
        "archetype_id": "section_divider",
        "composition_family": "chapter_marker",
        "primary_information_structure": "large section number with title/subtitle and footer",
        "density_level": "low",
        "visual_motif": "oversized numeric system with editorial diagonal field",
        "protected_text_zones": ["section_number", "title", "subtitle"],
        "semantic_components": ["editable section number", "editable title", "editable subtitle", "editable footer"],
        "source_strip_policy": "source strip optional; editable footer required",
        "chart_table_policy": "not_applicable",
        "icon_policy": "ornamental marks only; semantic icons must be SVG/vector",
        "allowed_raster_policy": "no content-bearing raster",
        "visual_distinction_from_other_archetypes": "Section number dominates the composition; it is not a cover clone and has no hero image frame.",
        "source_bound_use_cases": ["section break", "chapter transition", "narrative reset"],
        "orientation_tags": ["narrative_navigation"],
        "source_binding_required_for_content": False,
        "citation_binding_required_for_content": False,
        "source_required_slot_types": [],
        "citation_required_slot_types": [],
        "served_slide_blueprint_types": ["section", "chapter_divider", "transition"],
        "required_source_fields": ["section_id", "section_title"],
        "required_citation_fields": ["optional_citation_id"],
        "max_capacity": {"title_chars": 58, "subtitle_chars": 110, "section_number_chars": 6},
        "fallback_layout_recommendations": "Shorten subtitle before changing composition; do not reuse cover hero image frame.",
        "b05_binding_risks": "Low; source/citation binding is optional unless section has evidence claims.",
        "slots": [
            _slot("section_number", "callout", 1, 6, ["ppt_text", "ppt_shape"], {"x": 0.04, "y": 0.10, "w": 0.22, "h": 0.42}),
            _slot("title", "title", 12, 58, ["ppt_text", "ppt_shape"], {"x": 0.24, "y": 0.20, "w": 0.62, "h": 0.20}),
            _slot("subtitle", "subtitle", 12, 110, ["ppt_text", "ppt_shape"], {"x": 0.24, "y": 0.43, "w": 0.58, "h": 0.18}),
            _slot("footer", "footer", 8, 120, ["ppt_text", "ppt_shape"], {"x": 0.04, "y": 0.88, "w": 0.90, "h": 0.08}),
        ],
        "content_fixture": {
            "title": "Operating Model",
            "subtitle": "How reusable evidence, owner memory, and risk routing work together",
            "section_number": "03",
            "footer": "Governance playbook section 3 | Citation: gp-s03",
            "slot_texts": {
                "section_number": "03",
                "title": "Operating Model",
                "subtitle": "Reusable evidence, owner memory, and risk routing",
                "footer": "Governance playbook section 3 | Citation: gp-s03",
            },
        },
        "visual_scores": {"visual_ambition": 8, "archetype_identity": 9, "content_capacity": 8, "visual_clutter": 9},
    },
    "visual_toc": {
        "archetype_id": "visual_toc",
        "composition_family": "navigation_index",
        "primary_information_structure": "modular agenda index with active section highlight",
        "density_level": "medium",
        "visual_motif": "numbered navigation modules on a clear reading path",
        "protected_text_zones": ["title", "agenda_modules", "active_section_marker"],
        "semantic_components": ["editable agenda modules", "editable active marker", "editable footer"],
        "source_strip_policy": "editable footer; source strip optional in template stage",
        "chart_table_policy": "not_applicable",
        "icon_policy": "SVG/vector icons for module markers only",
        "allowed_raster_policy": "no raster navigation blocks",
        "visual_distinction_from_other_archetypes": "Only archetype with agenda navigation and active section progression.",
        "source_bound_use_cases": ["agenda", "navigation overview", "module index"],
        "orientation_tags": ["narrative_navigation"],
        "source_binding_required_for_content": False,
        "citation_binding_required_for_content": False,
        "source_required_slot_types": [],
        "citation_required_slot_types": [],
        "served_slide_blueprint_types": ["toc", "agenda", "navigation"],
        "required_source_fields": ["section_titles", "active_section"],
        "required_citation_fields": ["optional_citation_id"],
        "max_capacity": {"agenda_modules": 7, "module_label_chars": 48},
        "fallback_layout_recommendations": "Reduce to 5 modules before shrinking type; never rasterize navigation blocks.",
        "b05_binding_risks": "Medium if source plan has more than seven sections; split into two navigation slides.",
        "slots": [
            _slot("title", "title", 12, 64, ["ppt_text", "ppt_shape"], {"x": 0.06, "y": 0.08, "w": 0.72, "h": 0.14}),
            _slot("agenda_modules", "card", 120, 430, ["ppt_text", "ppt_shape", "svg_or_vector_icon"], {"x": 0.06, "y": 0.26, "w": 0.82, "h": 0.52}),
            _slot("active_section_marker", "callout", 8, 70, ["ppt_text", "ppt_shape"], {"x": 0.70, "y": 0.10, "w": 0.22, "h": 0.12}),
            _slot("footer", "footer", 8, 120, ["ppt_text", "ppt_shape"], {"x": 0.06, "y": 0.88, "w": 0.86, "h": 0.08}),
        ],
        "content_fixture": {
            "title": "Governance Roadmap",
            "modules": ["Intake", "Evidence", "Risk route", "Control fit", "Decision", "Monitoring"],
            "active_section": "Active module: Evidence",
            "footer": "Planning registry | Citation: gp-toc",
            "slot_texts": {
                "title": "Governance Roadmap",
                "agenda_modules": "Intake, evidence, risk route, control fit, decision, and monitoring",
                "active_section_marker": "Active module: Evidence",
                "footer": "Planning registry | Citation: gp-toc",
            },
        },
        "visual_scores": {"visual_ambition": 8, "archetype_identity": 9, "content_capacity": 8, "visual_clutter": 8},
    },
    "evidence_overview": {
        "archetype_id": "evidence_overview",
        "composition_family": "evidence_trail",
        "primary_information_structure": "source-backed evidence cards with confidence indicators",
        "density_level": "medium",
        "visual_motif": "traceable evidence trail",
        "protected_text_zones": ["title", "evidence_cards", "source_strip"],
        "semantic_components": ["editable evidence cards", "editable confidence indicators", "editable source strip"],
        "source_strip_policy": "editable source strip required for source-bound evidence slides",
        "chart_table_policy": "not_applicable",
        "icon_policy": "confidence icons must be SVG/vector",
        "allowed_raster_policy": "no content-bearing raster",
        "visual_distinction_from_other_archetypes": "Evidence cards emphasize provenance and confidence rather than generic recommendations.",
        "source_bound_use_cases": ["evidence summary", "source trail", "claim support"],
        "orientation_tags": ["data_evidence", "card_grid_dominant"],
        "source_binding_required_for_content": True,
        "citation_binding_required_for_content": True,
        "source_required_slot_types": ["card", "source_strip"],
        "citation_required_slot_types": ["card", "source_strip"],
        "served_slide_blueprint_types": ["evidence_overview", "source_summary", "claim_support"],
        "required_source_fields": ["claim", "source_id", "evidence_excerpt", "confidence"],
        "required_citation_fields": ["citation_id", "source_label", "retrieval_note"],
        "max_capacity": {"evidence_cards": 5, "card_body_chars": 120},
        "fallback_layout_recommendations": "Use 3-card or 5-card variant; overflow should become an evidence appendix slide.",
        "b05_binding_risks": "High if source plan lacks citation IDs for each card; fail source-bound gate rather than merging citations.",
        "slots": [
            _slot("title", "title", 12, 72, ["ppt_text", "ppt_shape"], {"x": 0.06, "y": 0.08, "w": 0.78, "h": 0.14}),
            _slot("evidence_cards", "card", 160, 620, ["ppt_text", "ppt_shape", "svg_or_vector_icon"], {"x": 0.06, "y": 0.25, "w": 0.76, "h": 0.52}),
            _slot("confidence_indicators", "icon", 0, 80, ["svg_or_vector_icon", "ppt_shape"], {"x": 0.82, "y": 0.25, "w": 0.12, "h": 0.52}),
            _slot("source_strip", "source_strip", 8, 150, ["ppt_text", "ppt_shape"], {"x": 0.06, "y": 0.88, "w": 0.88, "h": 0.08}),
        ],
        "content_fixture": {
            "title": "Evidence Trail For Portfolio Review",
            "cards": [
                {"claim": "Reusable decisions reduced duplicate review.", "confidence": "High", "citation": "gp-e01"},
                {"claim": "Controls are mapped before model approval.", "confidence": "Medium", "citation": "gp-e02"},
                {"claim": "Exception handling now has named owners.", "confidence": "High", "citation": "gp-e03"},
                {"claim": "Monitoring cadence varies by risk tier.", "confidence": "Medium", "citation": "gp-e04"},
            ],
            "source_strip": "Sources: governance registry and review notes | Citations: gp-e01 to gp-e04",
            "slot_texts": {
                "title": "Evidence Trail For Portfolio Review",
                "evidence_cards": "Four source-backed claims with confidence and citation markers",
                "confidence_indicators": "High, medium, high, medium",
                "source_strip": "Sources: governance registry and review notes | Citations: gp-e01 to gp-e04",
            },
        },
        "visual_scores": {"visual_ambition": 8, "archetype_identity": 8, "content_capacity": 8, "visual_clutter": 8},
    },
    "card_grid": {
        "archetype_id": "card_grid",
        "composition_family": "modular_card_grid",
        "primary_information_structure": "6-8 grouped cards with hierarchy and SVG/vector icon slots",
        "density_level": "medium",
        "visual_motif": "modular capability grid",
        "protected_text_zones": ["title", "card_grid", "source_strip"],
        "semantic_components": ["editable cards", "SVG/vector icon slots", "editable group labels"],
        "source_strip_policy": "editable source strip required for content slides",
        "chart_table_policy": "not_applicable",
        "icon_policy": "semantic card icons must be SVG/vector",
        "allowed_raster_policy": "no semantic raster",
        "visual_distinction_from_other_archetypes": "Only archetype optimized for six to eight parallel capabilities.",
        "source_bound_use_cases": ["capability map", "workstream overview", "feature set"],
        "orientation_tags": ["card_grid_dominant"],
        "source_binding_required_for_content": True,
        "citation_binding_required_for_content": True,
        "source_required_slot_types": ["card", "source_strip"],
        "citation_required_slot_types": ["card", "source_strip"],
        "served_slide_blueprint_types": ["card_grid", "capability_grid", "workstream_overview"],
        "required_source_fields": ["card_title", "card_body", "source_id"],
        "required_citation_fields": ["citation_id", "source_label"],
        "max_capacity": {"cards": 8, "card_body_chars": 92},
        "fallback_layout_recommendations": "Use 6-card variant for verbose content; split beyond 8 cards.",
        "b05_binding_risks": "Medium if blueprint has uneven card lengths; use capacity preflight before compile.",
        "slots": [
            _slot("title", "title", 12, 72, ["ppt_text", "ppt_shape"], {"x": 0.06, "y": 0.08, "w": 0.74, "h": 0.14}),
            _slot("card_grid", "card", 240, 720, ["ppt_text", "ppt_shape", "svg_or_vector_icon"], {"x": 0.06, "y": 0.24, "w": 0.86, "h": 0.56}),
            _slot("group_labels", "callout", 12, 110, ["ppt_text", "ppt_shape"], {"x": 0.06, "y": 0.18, "w": 0.70, "h": 0.08}),
            _slot("source_strip", "source_strip", 8, 150, ["ppt_text", "ppt_shape"], {"x": 0.06, "y": 0.88, "w": 0.88, "h": 0.08}),
        ],
        "content_fixture": {
            "title": "Reusable Governance Capabilities",
            "groups": ["Intake", "Review", "Decision"],
            "cards": [
                "Use-case intake",
                "Evidence memory",
                "Risk routing",
                "Control mapping",
                "Approval record",
                "Monitoring cadence",
            ],
            "source_strip": "Source: governance operating map | Citation: gp-g01",
            "slot_texts": {
                "title": "Reusable Governance Capabilities",
                "card_grid": "Six capability cards covering intake, evidence memory, risk routing, controls, approval, and monitoring",
                "group_labels": "Intake | Review | Decision",
                "source_strip": "Source: governance operating map | Citation: gp-g01",
            },
        },
        "visual_scores": {"visual_ambition": 8, "archetype_identity": 8, "content_capacity": 9, "visual_clutter": 8},
    },
    "methodology_framework": {
        "archetype_id": "methodology_framework",
        "composition_family": "framework_diagram",
        "primary_information_structure": "3-5 layer conceptual framework with editable connectors",
        "density_level": "medium",
        "visual_motif": "layered operating framework",
        "protected_text_zones": ["title", "framework_layers", "method_note"],
        "semantic_components": ["editable framework layers", "editable connectors", "editable method note"],
        "source_strip_policy": "editable source strip required when framework is source-backed",
        "chart_table_policy": "not_applicable",
        "icon_policy": "SVG/vector stage icons only",
        "allowed_raster_policy": "no diagram raster",
        "visual_distinction_from_other_archetypes": "Conceptual layers and connectors, not cards or a linear process.",
        "source_bound_use_cases": ["methodology", "operating model", "framework"],
        "orientation_tags": ["diagram_process"],
        "source_binding_required_for_content": True,
        "citation_binding_required_for_content": True,
        "source_required_slot_types": ["body", "callout", "source_strip"],
        "citation_required_slot_types": ["body", "callout", "source_strip"],
        "served_slide_blueprint_types": ["methodology", "framework", "operating_model"],
        "required_source_fields": ["stage_name", "stage_description", "source_id"],
        "required_citation_fields": ["citation_id", "method_source"],
        "max_capacity": {"layers": 5, "layer_body_chars": 120},
        "fallback_layout_recommendations": "Use 3-layer compact framework before shrinking labels.",
        "b05_binding_risks": "Medium if blueprint represents a process rather than conceptual layers; route process content to process_flow.",
        "slots": [
            _slot("title", "title", 12, 72, ["ppt_text", "ppt_shape"], {"x": 0.06, "y": 0.08, "w": 0.76, "h": 0.14}),
            _slot("framework_layers", "body", 140, 560, ["ppt_text", "ppt_shape"], {"x": 0.08, "y": 0.24, "w": 0.74, "h": 0.46}),
            _slot("connector_labels", "callout", 20, 140, ["ppt_text", "ppt_shape"], {"x": 0.16, "y": 0.32, "w": 0.68, "h": 0.22}),
            _slot("method_note", "callout", 16, 130, ["ppt_text", "ppt_shape"], {"x": 0.62, "y": 0.68, "w": 0.30, "h": 0.12}),
            _slot("source_strip", "source_strip", 8, 150, ["ppt_text", "ppt_shape"], {"x": 0.06, "y": 0.88, "w": 0.88, "h": 0.08}),
        ],
        "content_fixture": {
            "title": "Evidence-To-Decision Framework",
            "layers": ["Intake context", "Evidence memory", "Risk interpretation", "Decision record"],
            "method_note": "Each layer preserves owner, source, and next action.",
            "source_strip": "Source: governance method note | Citation: gp-m01",
            "slot_texts": {
                "title": "Evidence-To-Decision Framework",
                "framework_layers": "Intake context, evidence memory, risk interpretation, and decision record",
                "connector_labels": "Source context flows into review memory and accountable decision records",
                "method_note": "Each layer preserves owner, source, and next action.",
                "source_strip": "Source: governance method note | Citation: gp-m01",
            },
        },
        "visual_scores": {"visual_ambition": 9, "archetype_identity": 9, "content_capacity": 8, "visual_clutter": 8},
    },
    "process_flow": {
        "archetype_id": "process_flow",
        "composition_family": "process_diagram",
        "primary_information_structure": "5-7 step horizontal or diagonal flow with decision points",
        "density_level": "medium",
        "visual_motif": "diagonal operating flow",
        "protected_text_zones": ["title", "process_steps", "decision_points"],
        "semantic_components": ["editable step markers", "editable connectors", "editable decision points"],
        "source_strip_policy": "editable source strip required for process slides",
        "chart_table_policy": "not_applicable",
        "icon_policy": "SVG/vector status markers only",
        "allowed_raster_policy": "no process raster",
        "visual_distinction_from_other_archetypes": "Linear sequence with explicit connectors and decisions, distinct from timeline dates.",
        "source_bound_use_cases": ["workflow", "review process", "decision path"],
        "orientation_tags": ["diagram_process"],
        "source_binding_required_for_content": True,
        "citation_binding_required_for_content": True,
        "source_required_slot_types": ["card", "callout", "source_strip"],
        "citation_required_slot_types": ["card", "callout", "source_strip"],
        "served_slide_blueprint_types": ["process", "workflow", "decision_path"],
        "required_source_fields": ["step_name", "step_owner", "step_evidence", "source_id"],
        "required_citation_fields": ["citation_id", "process_source"],
        "max_capacity": {"steps": 7, "step_body_chars": 80},
        "fallback_layout_recommendations": "Use 5-step variant or split into two flows before reducing text below readability.",
        "b05_binding_risks": "Medium if source data mixes phases and tasks; choose timeline_roadmap for dated milestones.",
        "slots": [
            _slot("title", "title", 12, 72, ["ppt_text", "ppt_shape"], {"x": 0.06, "y": 0.08, "w": 0.76, "h": 0.14}),
            _slot("process_steps", "card", 180, 560, ["ppt_text", "ppt_shape", "svg_or_vector_icon"], {"x": 0.06, "y": 0.28, "w": 0.82, "h": 0.36}),
            _slot("decision_points", "callout", 18, 150, ["ppt_text", "ppt_shape"], {"x": 0.16, "y": 0.66, "w": 0.62, "h": 0.12}),
            _slot("source_strip", "source_strip", 8, 150, ["ppt_text", "ppt_shape"], {"x": 0.06, "y": 0.88, "w": 0.88, "h": 0.08}),
        ],
        "content_fixture": {
            "title": "Review-To-Decision Flow",
            "steps": ["Intake", "Evidence check", "Risk route", "Control match", "Council decision", "Monitor"],
            "decision_points": "Escalate only when source confidence or control fit is unresolved.",
            "source_strip": "Source: operating process map | Citation: gp-p01",
            "slot_texts": {
                "title": "Review-To-Decision Flow",
                "process_steps": "Intake, evidence check, risk route, control match, council decision, and monitoring",
                "decision_points": "Escalate only when source confidence or control fit is unresolved.",
                "source_strip": "Source: operating process map | Citation: gp-p01",
            },
        },
        "visual_scores": {"visual_ambition": 9, "archetype_identity": 9, "content_capacity": 8, "visual_clutter": 8},
    },
    "comparison_matrix": {
        "archetype_id": "comparison_matrix",
        "composition_family": "criteria_matrix",
        "primary_information_structure": "criteria-vs-options matrix with editable emphasis cells",
        "density_level": "dense",
        "visual_motif": "decision matrix",
        "protected_text_zones": ["title", "matrix_region", "source_strip"],
        "semantic_components": ["native PPT table or editable shape-grid", "editable row headers", "editable emphasis cells"],
        "source_strip_policy": "editable source strip required for matrix slides",
        "chart_table_policy": "native_or_editable_shape_grid",
        "icon_policy": "SVG/vector status icons only if used",
        "allowed_raster_policy": "no raster matrix",
        "visual_distinction_from_other_archetypes": "Criteria matrix with options and emphasis cells, not a long artifact table.",
        "source_bound_use_cases": ["option comparison", "criteria scoring", "tradeoff matrix"],
        "orientation_tags": ["data_evidence", "dense_information"],
        "source_binding_required_for_content": True,
        "citation_binding_required_for_content": True,
        "source_required_slot_types": ["table", "source_strip"],
        "citation_required_slot_types": ["table", "source_strip"],
        "served_slide_blueprint_types": ["comparison", "matrix", "criteria_options"],
        "required_source_fields": ["criteria", "options", "cell_evidence", "source_id"],
        "required_citation_fields": ["citation_id", "criterion_source"],
        "max_capacity": {"rows": 5, "columns": 4, "cell_chars": 70},
        "fallback_layout_recommendations": "Use 2x3 or 3x3 variant; split criteria when cells exceed capacity.",
        "b05_binding_risks": "High if source blueprint has mixed scoring scales; normalize before compile.",
        "slots": [
            _slot("title", "title", 12, 72, ["ppt_text", "ppt_shape"], {"x": 0.06, "y": 0.08, "w": 0.74, "h": 0.14}),
            _slot("matrix_region", "table", 0, 0, ["ppt_table", "ppt_shape"], {"x": 0.06, "y": 0.24, "w": 0.84, "h": 0.56}),
            _slot("emphasis_cells", "callout", 20, 120, ["ppt_text", "ppt_shape"], {"x": 0.66, "y": 0.24, "w": 0.24, "h": 0.18}),
            _slot("source_strip", "source_strip", 8, 150, ["ppt_text", "ppt_shape"], {"x": 0.06, "y": 0.88, "w": 0.88, "h": 0.08}),
        ],
        "content_fixture": {
            "title": "Governance Options Compared",
            "columns": ["Criteria", "Central review", "Federated review", "Hybrid council"],
            "rows": [
                ["Speed", "Moderate", "Fast", "Balanced"],
                ["Control depth", "Strong", "Variable", "Strong"],
                ["Reuse memory", "High", "Medium", "High"],
            ],
            "source_strip": "Source: operating model comparison | Citation: gp-c01",
            "slot_texts": {
                "title": "Governance Options Compared",
                "matrix_region": "",
                "emphasis_cells": "Hybrid council balances speed and control depth.",
                "source_strip": "Source: operating model comparison | Citation: gp-c01",
            },
        },
        "visual_scores": {"visual_ambition": 8, "archetype_identity": 9, "content_capacity": 9, "visual_clutter": 8},
    },
    "timeline_roadmap": {
        "archetype_id": "timeline_roadmap",
        "composition_family": "timeline_roadmap",
        "primary_information_structure": "phased roadmap with milestones and risk markers",
        "density_level": "medium",
        "visual_motif": "chronological phase lane",
        "protected_text_zones": ["title", "phase_lane", "milestones", "source_strip"],
        "semantic_components": ["editable phase lane", "editable milestone markers", "editable risk markers"],
        "source_strip_policy": "editable source strip required for roadmap slides",
        "chart_table_policy": "not_applicable",
        "icon_policy": "SVG/vector risk and milestone markers only",
        "allowed_raster_policy": "no timeline raster",
        "visual_distinction_from_other_archetypes": "Chronological phases and milestones, distinct from step-by-step process_flow.",
        "source_bound_use_cases": ["roadmap", "timeline", "implementation phases"],
        "orientation_tags": ["narrative_navigation", "diagram_process"],
        "source_binding_required_for_content": True,
        "citation_binding_required_for_content": True,
        "source_required_slot_types": ["body", "callout", "source_strip"],
        "citation_required_slot_types": ["body", "callout", "source_strip"],
        "served_slide_blueprint_types": ["timeline", "roadmap", "milestones"],
        "required_source_fields": ["phase_name", "date_or_period", "milestone", "source_id"],
        "required_citation_fields": ["citation_id", "roadmap_source"],
        "max_capacity": {"phases": 5, "milestones": 8, "milestone_chars": 74},
        "fallback_layout_recommendations": "Use quarterly lane for dated milestones; route non-dated task sequences to process_flow.",
        "b05_binding_risks": "Medium if source plan lacks dates or phase ordering; require deterministic ordering before compile.",
        "slots": [
            _slot("title", "title", 12, 72, ["ppt_text", "ppt_shape"], {"x": 0.06, "y": 0.08, "w": 0.74, "h": 0.14}),
            _slot("phase_lane", "body", 80, 320, ["ppt_text", "ppt_shape"], {"x": 0.06, "y": 0.30, "w": 0.84, "h": 0.24}),
            _slot("milestones", "callout", 80, 360, ["ppt_text", "ppt_shape", "svg_or_vector_icon"], {"x": 0.08, "y": 0.56, "w": 0.80, "h": 0.22}),
            _slot("risk_markers", "icon", 0, 80, ["svg_or_vector_icon", "ppt_shape"], {"x": 0.08, "y": 0.48, "w": 0.76, "h": 0.10}),
            _slot("source_strip", "source_strip", 8, 150, ["ppt_text", "ppt_shape"], {"x": 0.06, "y": 0.88, "w": 0.88, "h": 0.08}),
        ],
        "content_fixture": {
            "title": "Governance Scale-Out Roadmap",
            "phases": ["Pilot", "Policy alignment", "Reusable controls", "Portfolio cadence"],
            "milestones": ["Pilot gate", "Control map", "Council launch", "Quarterly review"],
            "source_strip": "Source: implementation roadmap | Citation: gp-r01",
            "slot_texts": {
                "title": "Governance Scale-Out Roadmap",
                "phase_lane": "Pilot, policy alignment, reusable controls, and portfolio cadence",
                "milestones": "Pilot gate, control map, council launch, and quarterly review",
                "risk_markers": "Dependency markers for control and owner readiness",
                "source_strip": "Source: implementation roadmap | Citation: gp-r01",
            },
        },
        "visual_scores": {"visual_ambition": 9, "archetype_identity": 9, "content_capacity": 8, "visual_clutter": 8},
    },
}
