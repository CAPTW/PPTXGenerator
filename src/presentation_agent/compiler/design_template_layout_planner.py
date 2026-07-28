"""Plan slide-to-layout bindings for GPT-Image-2-derived editable templates."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any

from ..generator_contracts import validateDeckAssemblyPlan, validateDesignBrief, validateEditableTemplateSpec, validatePresentationPlan
from .blueprint_adapter import DEFAULT_ADAPTED_SLIDE_BLUEPRINT_PATH, DEFAULT_SLIDE_BLUEPRINT_PATH, load_valid_slide_blueprints


DEFAULT_PRESENTATION_PLAN = Path("outputs/presentation_plan.json")
DEFAULT_DESIGN_BRIEF = Path("outputs/design_brief.json")
DEFAULT_TEMPLATE_SPEC = Path("outputs/editable_template_spec.final.json")
DEFAULT_LAYOUT_FAMILY_PLAN = Path("outputs/design_planning/layout_family_plan.json")
DEFAULT_DECK_SCALE_USAGE_PLAN = Path("outputs/design_planning/deck_scale_usage_plan.json")
DEFAULT_VISUAL_FIDELITY_TARGETS = Path("outputs/design_planning/visual_fidelity_targets.json")
DEFAULT_OUTPUT = Path("outputs/deck_assembly_plan.json")
DEFAULT_RENDER_PRIORITY = 3

SLIDE_CHARACTER_TO_PROMPT_TYPE = {
    "cover": "creative_cover",
    "visual_toc": "visual_table_of_contents",
    "section_divider": "section_divider",
    "research_overview": "research_overview",
    "problem_statement": "problem_statement",
    "research_gap": "research_gap",
    "literature_map": "literature_map",
    "methodology_framework": "methodology_framework",
    "technical_flow_chart": "technical_flow_chart",
    "sequence": "work_support_sequence",
    "photo_caption_grid": "photo_caption_grid",
    "comparison_matrix": "comparison_matrix",
    "concept_relationship": "concept_relationship_venn",
    "three_level_explanation": "three_level_explanation",
    "circular_process": "circular_process",
    "kpi_dashboard": "kpi_donut_chart",
    "timeline_roadmap": "timeline_roadmap",
    "data_table_appendix": "data_table_appendix",
    "case_study": "case_study",
    "closing": "closing",
}

FALLBACK_LAYOUT_BY_CHARACTER = {
    "cover": "cover_hero",
    "visual_toc": "standard_content",
    "section_divider": "section_divider",
    "research_overview": "standard_content",
    "problem_statement": "standard_content",
    "research_gap": "standard_content",
    "literature_map": "standard_content",
    "methodology_framework": "standard_content",
    "technical_flow_chart": "standard_content",
    "sequence": "standard_content",
    "photo_caption_grid": "case_study",
    "comparison_matrix": "comparison_matrix",
    "concept_relationship": "card_grid",
    "three_level_explanation": "card_grid",
    "circular_process": "card_grid",
    "kpi_dashboard": "data_dashboard",
    "timeline_roadmap": "standard_content",
    "data_table_appendix": "table_heavy",
    "case_study": "case_study",
    "closing": "closing",
}


def plan_design_template_layouts(
    *,
    slide_blueprints: dict[str, Any] | list[dict[str, Any]],
    presentation_plan: dict[str, Any],
    editable_template_spec: dict[str, Any],
    design_brief: dict[str, Any],
    template_spec_path: str = "outputs/editable_template_spec.final.json",
    layout_family_plan: dict[str, Any] | None = None,
    deck_scale_usage_plan: dict[str, Any] | None = None,
    visual_fidelity_targets: dict[str, Any] | None = None,
    production_plan_paths: dict[str, str] | None = None,
) -> dict[str, Any]:
    validatePresentationPlan(presentation_plan)
    validateDesignBrief(design_brief)
    validateEditableTemplateSpec(editable_template_spec)
    slides = _normalize_slides(slide_blueprints)
    if not slides:
        raise ValueError("slide_blueprint must contain at least one slide")
    layouts = editable_template_spec.get("layouts") or []
    deck_scale = _deck_scale(len(slides))
    production_context = _production_plan_context(
        editable_template_spec=editable_template_spec,
        layout_family_plan=layout_family_plan,
        deck_scale_usage_plan=deck_scale_usage_plan,
        visual_fidelity_targets=visual_fidelity_targets,
        production_plan_paths=production_plan_paths,
        deck_scale=deck_scale,
    )
    layout_families = production_context["layout_families"]
    family_by_id = {str(family.get("family_id") or ""): family for family in layout_families if isinstance(family, dict)}
    scale_rules = production_context["scale_rules"]
    fidelity_target_ids = production_context["fidelity_target_ids"]
    default_tone = _deck_tone_variant(presentation_plan, design_brief)
    section_positions = _section_positions(slides)
    recent_layouts: deque[str] = deque(maxlen=3)
    recent_families: deque[str] = deque(maxlen=_rotation_window(scale_rules, deck_scale))
    layout_use_count: Counter[str] = Counter()
    family_use_count: Counter[str] = Counter()

    bindings: list[dict[str, Any]] = []
    missing_slot_warnings: list[dict[str, Any]] = []
    overflow_warnings: list[dict[str, Any]] = []
    render_warnings: list[dict[str, Any]] = []

    for index, slide in enumerate(slides, start=1):
        character = _slide_character(slide, index, len(slides))
        unsupported_slide_type = _unsupported_slide_type(slide, index, len(slides))
        section_rhythm_role = _section_rhythm_role(character, section_positions.get(_slide_id(slide), 1), deck_scale)
        character = _apply_section_rhythm(character, slide, section_positions.get(_slide_id(slide), 1), deck_scale)
        needs = _content_needs(slide, character)
        density = _content_density(slide, needs)
        selected_tone = _tone_for_slide(character, default_tone)
        family_scores = _score_layout_families(
            families=layout_families,
            character=character,
            needs=needs,
            density=density,
            deck_scale=deck_scale,
            section_rhythm_role=section_rhythm_role,
            recent_families=recent_families,
            family_use_count=family_use_count,
            scale_rules=scale_rules,
        )
        preferred_family_id = family_scores[0]["family_id"] if family_scores else None
        scored = sorted(
            (
                _score_layout(
                    layout=layout,
                    slide=slide,
                    character=character,
                    needs=needs,
                    density=density,
                    deck_scale=deck_scale,
                    recent_layouts=recent_layouts,
                    layout_use_count=layout_use_count,
                    recent_families=recent_families,
                    family_use_count=family_use_count,
                    preferred_family_id=preferred_family_id,
                    scale_rules=scale_rules,
                    order=order,
                    unsupported_slide_type=unsupported_slide_type,
                )
                for order, layout in enumerate(layouts)
            ),
            key=lambda item: (-item["score"], item["order"]),
        )
        selected = scored[0]["layout"] if scored else None
        if selected is None:
            binding = _failed_binding(slide, character, deck_scale, selected_tone, needs)
        else:
            binding = _binding_for_slide(
                slide=slide,
                layout=selected,
                character=character,
                needs=needs,
                density=density,
                deck_scale=deck_scale,
                section_rhythm_role=section_rhythm_role,
                selected_tone=selected_tone,
                score=scored[0],
                family=family_by_id.get(str(selected.get("layout_family_id") or "")),
                fidelity_target_ids=fidelity_target_ids,
                layout_use_count=layout_use_count,
                family_use_count=family_use_count,
                scale_rules=scale_rules,
                unsupported_slide_type=unsupported_slide_type,
                production_plan_used=production_context["production_plan_used"],
            )
            recent_layouts.append(selected["layout_id"])
            layout_use_count[selected["layout_id"]] += 1
            family_id = str(selected.get("layout_family_id") or "unassigned_board_family")
            recent_families.append(family_id)
            family_use_count[family_id] += 1
        bindings.append(binding)
        for warning in binding.get("warnings") or []:
            code = str(warning.get("code") or "")
            if code.startswith("MISSING_SLOT"):
                missing_slot_warnings.append(warning)
            elif code.startswith("OVERFLOW"):
                overflow_warnings.append(warning)
            else:
                render_warnings.append(warning)
        overflow_warnings.extend(binding.get("content_overflow_warnings") or [])

    plan = {
        "schema_name": "deck_assembly_plan",
        "schema_version": "1.0",
        "deck_id": _deck_id(slides, editable_template_spec),
        "selected_template_pack": editable_template_spec["design_id"],
        "deck_scale": deck_scale,
        "selected_tone_variant": default_tone,
        "template_spec_source": {
            "path": template_spec_path,
            "selection": _template_spec_selection(template_spec_path),
            "fallback_reason": None,
            "warnings": [],
        },
        "production_plan_used": production_context["production_plan_used"],
        "production_plan_source": production_context["source"],
        "layout_family_counts": dict(sorted(family_use_count.items())),
        "layout_repetition_counts": dict(sorted(layout_use_count.items())),
        "visual_fidelity_target_compliance": _visual_fidelity_compliance(bindings, production_context),
        "slide_layout_bindings": bindings,
        "missing_slot_warnings": _dedupe_warnings(missing_slot_warnings),
        "overflow_warnings": _dedupe_warnings(overflow_warnings),
        "render_warnings": _dedupe_warnings(render_warnings),
    }
    validateDeckAssemblyPlan(plan)
    return plan


def plan_design_template_layouts_from_files(
    *,
    slide_blueprint_path: str | Path = DEFAULT_SLIDE_BLUEPRINT_PATH,
    adapted_slide_blueprint_path: str | Path = DEFAULT_ADAPTED_SLIDE_BLUEPRINT_PATH,
    presentation_plan_path: str | Path = DEFAULT_PRESENTATION_PLAN,
    template_spec_path: str | Path = DEFAULT_TEMPLATE_SPEC,
    design_brief_path: str | Path = DEFAULT_DESIGN_BRIEF,
    layout_family_plan_path: str | Path = DEFAULT_LAYOUT_FAMILY_PLAN,
    deck_scale_usage_plan_path: str | Path = DEFAULT_DECK_SCALE_USAGE_PLAN,
    visual_fidelity_targets_path: str | Path = DEFAULT_VISUAL_FIDELITY_TARGETS,
    output_path: str | Path = DEFAULT_OUTPUT,
) -> Path:
    slide_blueprints, selected_blueprint_path = load_valid_slide_blueprints(slide_blueprint_path, adapted_slide_blueprint_path)
    presentation_plan = _load_json(presentation_plan_path)
    editable_template_spec = _load_json(template_spec_path)
    design_brief = _load_json(design_brief_path)
    layout_family_plan = _load_json(layout_family_plan_path)
    deck_scale_usage_plan = _load_json(deck_scale_usage_plan_path)
    visual_fidelity_targets = _load_json(visual_fidelity_targets_path)
    plan = plan_design_template_layouts(
        slide_blueprints=slide_blueprints,
        presentation_plan=presentation_plan,
        editable_template_spec=editable_template_spec,
        design_brief=design_brief,
        template_spec_path=_display_path(Path(template_spec_path)),
        layout_family_plan=layout_family_plan,
        deck_scale_usage_plan=deck_scale_usage_plan,
        visual_fidelity_targets=visual_fidelity_targets,
        production_plan_paths={
            "layout_family_plan_path": _display_path(Path(layout_family_plan_path)),
            "deck_scale_usage_plan_path": _display_path(Path(deck_scale_usage_plan_path)),
            "visual_fidelity_targets_path": _display_path(Path(visual_fidelity_targets_path)),
        },
    )
    plan["source_slide_blueprint_path"] = _display_path(selected_blueprint_path)
    validateDeckAssemblyPlan(plan)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(plan, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")
    return output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Plan slide bindings for design-board-derived editable template layouts.")
    parser.add_argument("--slide-blueprint", type=Path, default=DEFAULT_SLIDE_BLUEPRINT_PATH)
    parser.add_argument("--adapted-slide-blueprint", type=Path, default=DEFAULT_ADAPTED_SLIDE_BLUEPRINT_PATH)
    parser.add_argument("--presentation-plan", type=Path, default=DEFAULT_PRESENTATION_PLAN)
    parser.add_argument("--template-spec", type=Path, default=DEFAULT_TEMPLATE_SPEC)
    parser.add_argument("--design-brief", type=Path, default=DEFAULT_DESIGN_BRIEF)
    parser.add_argument("--layout-family-plan", type=Path, default=DEFAULT_LAYOUT_FAMILY_PLAN)
    parser.add_argument("--deck-scale-usage-plan", type=Path, default=DEFAULT_DECK_SCALE_USAGE_PLAN)
    parser.add_argument("--visual-fidelity-targets", type=Path, default=DEFAULT_VISUAL_FIDELITY_TARGETS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        output = plan_design_template_layouts_from_files(
            slide_blueprint_path=args.slide_blueprint,
            adapted_slide_blueprint_path=args.adapted_slide_blueprint,
            presentation_plan_path=args.presentation_plan,
            template_spec_path=args.template_spec,
            design_brief_path=args.design_brief,
            layout_family_plan_path=args.layout_family_plan,
            deck_scale_usage_plan_path=args.deck_scale_usage_plan,
            visual_fidelity_targets_path=args.visual_fidelity_targets,
            output_path=args.output,
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"PLAN_DESIGN_TEMPLATE_LAYOUTS_FAILED {exc}")
        return 1
    print(f"WROTE {output}")
    return 0


def _production_plan_context(
    *,
    editable_template_spec: dict[str, Any],
    layout_family_plan: dict[str, Any] | None,
    deck_scale_usage_plan: dict[str, Any] | None,
    visual_fidelity_targets: dict[str, Any] | None,
    production_plan_paths: dict[str, str] | None,
    deck_scale: str,
) -> dict[str, Any]:
    provenance = editable_template_spec.get("provenance") or {}
    embedded_families = editable_template_spec.get("layout_families") or []
    embedded_targets = editable_template_spec.get("visual_fidelity_targets") or {}
    families = (layout_family_plan or {}).get("families") or embedded_families
    scales = (deck_scale_usage_plan or {}).get("scales") or {}
    scale_rules = scales.get(deck_scale) if isinstance(scales, dict) else None
    if not isinstance(scale_rules, dict):
        scale_rules = _scale_rules_from_spec(editable_template_spec, deck_scale)
    targets = (visual_fidelity_targets or {}).get("targets") or embedded_targets
    production_plan_used = bool(
        layout_family_plan
        and deck_scale_usage_plan
        and visual_fidelity_targets
        and families
        and targets
    ) or bool(provenance.get("production_plan_used") is True and families and targets)
    source = {"warnings": []}
    candidate_paths = {
        "layout_family_plan_path": (production_plan_paths or {}).get("layout_family_plan_path")
        or provenance.get("layout_family_plan_path"),
        "deck_scale_usage_plan_path": (production_plan_paths or {}).get("deck_scale_usage_plan_path")
        or provenance.get("deck_scale_usage_plan_path"),
        "visual_fidelity_targets_path": (production_plan_paths or {}).get("visual_fidelity_targets_path")
        or provenance.get("visual_fidelity_targets_path"),
    }
    source.update({key: str(value) for key, value in candidate_paths.items() if value})
    if not production_plan_used:
        source["warnings"].append(
            _warning(
                "PRODUCTION_PLAN_NOT_USED",
                "deck",
                "Layout planning used embedded template metadata only; design production plan artifacts were not available.",
                severity="warning",
            )
        )
    return {
        "production_plan_used": production_plan_used,
        "layout_families": [family for family in families if isinstance(family, dict)],
        "scale_rules": scale_rules,
        "visual_fidelity_targets": targets if isinstance(targets, dict) else {},
        "fidelity_target_ids": sorted((targets or {}).keys()) if isinstance(targets, dict) else [],
        "source": source,
    }


def _scale_rules_from_spec(editable_template_spec: dict[str, Any], deck_scale: str) -> dict[str, Any]:
    text = str((editable_template_spec.get("deck_scale_rules") or {}).get(deck_scale) or "")
    match = re.search(r"at least\s+(\d+)\s+layout families", text, re.IGNORECASE)
    return {
        "scale_id": deck_scale,
        "layout_rotation_rules": text,
        "maximum_repetition": int(match.group(1)) if match else (4 if deck_scale == "large" else 5 if deck_scale == "very_large" else 3),
        "ornament_density": "medium-low" if deck_scale == "large" else "low" if deck_scale == "very_large" else "medium",
        "section_rhythm": "section divider -> overview -> evidence -> analysis -> implication" if deck_scale in {"large", "very_large"} else "opener -> context -> method/data -> insight -> close",
        "footer_citation_density": "compact persistent footer" if deck_scale == "very_large" else "dense but compact footer",
    }


def _template_spec_selection(template_spec_path: str) -> str:
    name = Path(template_spec_path).name
    if name == "editable_template_spec.final.json":
        return "final"
    if name == "editable_template_spec.json":
        return "base"
    return "explicit"


def _score_layout_families(
    *,
    families: list[dict[str, Any]],
    character: str,
    needs: list[str],
    density: str,
    deck_scale: str,
    section_rhythm_role: str,
    recent_families: deque[str],
    family_use_count: Counter[str],
    scale_rules: dict[str, Any],
) -> list[dict[str, Any]]:
    target_prompt_type = _normalize_key(SLIDE_CHARACTER_TO_PROMPT_TYPE.get(character, character))
    scored: list[dict[str, Any]] = []
    for order, family in enumerate(families):
        family_id = str(family.get("family_id") or "")
        compatible = {_normalize_key(item) for item in family.get("compatible_slide_types") or []}
        member_archetypes = {_normalize_key(item) for item in family.get("member_archetype_ids") or []}
        components = {_normalize_key(item) for item in family.get("component_bindings") or []}
        required_slots = {_normalize_key(item) for item in family.get("required_slots") or []}
        optional_slots = {_normalize_key(item) for item in family.get("optional_slots") or []}
        family_text = json.dumps(family, sort_keys=True, ensure_ascii=True).lower()
        score = 0
        reasons: list[str] = []
        if target_prompt_type in compatible or target_prompt_type in member_archetypes:
            score += 160
            reasons.append(f"production family compatible with {target_prompt_type}")
        score += _family_role_score(family_id, character, section_rhythm_role)
        dominant_density = _normalize_key((family.get("geometry_strategy") or {}).get("dominant_density"))
        if density == dominant_density:
            score += 22
        elif density == "evidence_heavy" and dominant_density in {"high", "medium"}:
            score += 14
        for need in needs:
            score += _family_need_score(need, components, required_slots | optional_slots, family_text)
        if deck_scale in {"large", "very_large"}:
            if family_id in recent_families:
                score -= 35
                reasons.append("recent family repetition penalty")
            maximum_repetition = int(scale_rules.get("maximum_repetition") or 4)
            if family_use_count[family_id] >= maximum_repetition:
                score -= 45
                reasons.append("scale repetition cap penalty")
        scored.append({"family_id": family_id, "score": score, "order": order, "reason": "; ".join(reasons)})
    return sorted(scored, key=lambda item: (-item["score"], item["order"]))


def _family_role_score(family_id: str, character: str, section_rhythm_role: str) -> int:
    family_id = _normalize_key(family_id)
    if section_rhythm_role == "divider" and family_id == "expressive_cover_divider":
        return 60
    if section_rhythm_role == "overview" and family_id in {"evidence_overview", "visual_toc_navigation"}:
        return 45
    if section_rhythm_role == "evidence" and family_id in {"evidence_overview", "comparison_matrix", "table_appendix", "kpi_dashboard"}:
        return 45
    if section_rhythm_role == "analysis" and family_id in {"problem_research_gap", "methodology_framework", "technical_flow_process", "comparison_matrix"}:
        return 45
    if section_rhythm_role == "implication" and family_id in {"closing_recommendation", "problem_research_gap", "technical_flow_process"}:
        return 35
    if character == "cover" and family_id == "expressive_cover_divider":
        return 75
    if character == "closing" and family_id in {"expressive_cover_divider", "closing_recommendation"}:
        return 55
    return 0


def _family_need_score(need: str, components: set[str], slots: set[str], family_text: str) -> int:
    aliases = {
        "chart": {"chart_module", "primary_chart", "secondary_charts", "metric_panels"},
        "table": {"thin_grid_table", "comparison_matrix", "table"},
        "cards": {"layered_card", "cards", "caption_cards", "section_cards"},
        "process": {"radial_process", "curved_timeline", "diagram", "process_visual"},
        "comparison": {"comparison_matrix", "matrix"},
        "timeline": {"curved_timeline", "timeline_steps"},
        "photo": {"diagonal_image_frame", "photo_grid", "hero_image"},
        "citation": {"citation_strip", "dense_footer", "footer"},
        "appendix": {"thin_grid_table", "table", "source_notes"},
    }
    targets = {_normalize_key(item) for item in aliases.get(need, {need})}
    if targets & components or targets & slots:
        return 42
    if need in family_text:
        return 14
    return -20 if need in {"chart", "table", "photo"} else -4


def _binding_for_slide(
    *,
    slide: dict[str, Any],
    layout: dict[str, Any],
    character: str,
    needs: list[str],
    density: str,
    deck_scale: str,
    section_rhythm_role: str,
    selected_tone: str,
    score: dict[str, Any],
    family: dict[str, Any] | None,
    fidelity_target_ids: list[str],
    layout_use_count: Counter[str],
    family_use_count: Counter[str],
    scale_rules: dict[str, Any],
    unsupported_slide_type: str | None = None,
    production_plan_used: bool = False,
) -> dict[str, Any]:
    slide_id = _slide_id(slide)
    slot_bindings, component_bindings, warnings = _bind_slots(slide, layout)
    missing_slots = _missing_required_slots(slide, layout)
    for slot_id in missing_slots:
        warnings.append(_warning("MISSING_SLOT_REQUIRED", slide_id, f"Required slot {slot_id} is not present in selected layout.", layout["layout_id"], slot_id=slot_id))
    overflow = _overflow_warnings(slide, layout, density)
    layout_family_id = str(layout.get("layout_family_id") or (family or {}).get("family_id") or "unassigned_board_family")
    repeated_layout_warning = _repeated_layout_warning(
        slide_id=slide_id,
        layout_id=layout["layout_id"],
        layout_family_id=layout_family_id,
        layout_use_count=layout_use_count,
        family_use_count=family_use_count,
        scale_rules=scale_rules,
    )
    if repeated_layout_warning:
        warnings.append(repeated_layout_warning)
    fallback_reasons: list[str] = []
    if not score["direct_match"]:
        reason = f"selected {layout.get('slide_type')} for slide character {character}"
        fallback_reasons.append(reason)
        warnings.append(_warning("FALLBACK_LAYOUT_USED", slide_id, reason, layout["layout_id"]))
    if missing_slots:
        fallback_reasons.append("selected layout is usable but missing required blueprint slots: " + ", ".join(missing_slots))
    if "unsupported" in score:
        fallback_reasons.append(score["unsupported"])
        warnings.append(_warning("UNSUPPORTED_SLIDE_TYPE_FALLBACK", slide_id, score["unsupported"], layout["layout_id"]))
    if unsupported_slide_type:
        reason = f"unsupported slide_type {unsupported_slide_type}; mapped to slide character {character}"
        fallback_reasons.append(reason)
        warnings.append(_warning("UNSUPPORTED_SLIDE_TYPE_FALLBACK", slide_id, reason, layout["layout_id"]))
    fallback_used = bool(fallback_reasons)
    fallback_reason = "; ".join(_dedupe(fallback_reasons)) if fallback_reasons else None
    return {
        "slide_id": slide_id,
        "slide_type": _normalize_key(slide.get("slide_type")),
        "slide_character": character,
        "layout_family_id": layout_family_id,
        "layout_id": layout["layout_id"],
        "selected_layout_id": layout["layout_id"],
        "selection_reason": score["reason"],
        "selected_tone_variant": selected_tone,
        "deck_scale": deck_scale,
        "section_rhythm_role": section_rhythm_role,
        "component_density": _component_density(density, needs),
        "ornament_density": _ornament_density(deck_scale, density, needs, family),
        "fidelity_targets_applied": fidelity_target_ids,
        "slot_bindings": slot_bindings,
        "component_bindings": component_bindings,
        "fallback_used": fallback_used,
        "fallback_reason": fallback_reason,
        "repeated_layout_warning": repeated_layout_warning,
        "production_plan_used": production_plan_used,
        "content_overflow_warnings": overflow,
        "image_policy": str(layout.get("image_policy") or _default_image_policy(layout)),
        "render_priority": _render_priority(character, needs),
        "content_needs": needs,
        "warnings": _dedupe_warnings(warnings),
        "failure_reason": None,
    }


def _failed_binding(slide: dict[str, Any], character: str, deck_scale: str, selected_tone: str, needs: list[str]) -> dict[str, Any]:
    slide_id = _slide_id(slide)
    warning = _warning("NO_LAYOUT_AVAILABLE", slide_id, "No editable template layout was available.", severity="error")
    return {
        "slide_id": slide_id,
        "slide_type": _normalize_key(slide.get("slide_type")),
        "slide_character": character,
        "layout_family_id": "NO_FAMILY",
        "layout_id": "NO_LAYOUT",
        "selected_layout_id": "NO_LAYOUT",
        "selection_reason": "no layout available",
        "selected_tone_variant": selected_tone,
        "deck_scale": deck_scale,
        "section_rhythm_role": "unplanned",
        "component_density": "none",
        "ornament_density": "none",
        "fidelity_targets_applied": [],
        "slot_bindings": {},
        "component_bindings": {},
        "fallback_used": True,
        "fallback_reason": "NO_LAYOUT_AVAILABLE",
        "repeated_layout_warning": None,
        "production_plan_used": False,
        "content_overflow_warnings": [],
        "image_policy": "No image placement allowed because no layout was selected.",
        "render_priority": DEFAULT_RENDER_PRIORITY,
        "content_needs": needs,
        "warnings": [warning],
        "failure_reason": "NO_LAYOUT_AVAILABLE",
    }


def _score_layout(
    *,
    layout: dict[str, Any],
    slide: dict[str, Any],
    character: str,
    needs: list[str],
    density: str,
    deck_scale: str,
    recent_layouts: deque[str],
    layout_use_count: Counter[str],
    recent_families: deque[str],
    family_use_count: Counter[str],
    preferred_family_id: str | None,
    scale_rules: dict[str, Any],
    order: int,
    unsupported_slide_type: str | None = None,
) -> dict[str, Any]:
    target_prompt_type = SLIDE_CHARACTER_TO_PROMPT_TYPE.get(character, "research_overview")
    fallback_archetype = FALLBACK_LAYOUT_BY_CHARACTER.get(character, "standard_content")
    layout_id = str(layout.get("layout_id") or "")
    layout_type = _normalize_key(layout.get("slide_type"))
    archetype_id = _normalize_key(layout.get("archetype_id"))
    layout_family_id = str(layout.get("layout_family_id") or "")
    compatible = {_normalize_key(item) for item in layout.get("compatible_slide_types") or []}
    slot_types = _slot_types(layout)
    slot_ids = _slot_ids(layout)
    score = 0
    direct_match = False
    reasons: list[str] = []
    if layout_id.startswith("layout-board-"):
        score += 55
        reasons.append("design-board-derived layout preference")
    elif layout_id.endswith("-mvp"):
        score -= 35
        reasons.append("generic MVP layout penalty")
    exact_layout_match = layout_type == _normalize_key(target_prompt_type) or archetype_id == _normalize_key(target_prompt_type)
    compatible_layout_match = _normalize_key(target_prompt_type) in compatible
    if exact_layout_match:
        score += 180
        direct_match = True
        reasons.append(f"direct character match {target_prompt_type}")
    elif compatible_layout_match:
        score += 95
        reasons.append(f"production family-compatible character {target_prompt_type}")
    elif archetype_id == _normalize_key(fallback_archetype) or layout_type == _normalize_key(fallback_archetype):
        score += 80
        reasons.append(f"deterministic fallback archetype {fallback_archetype}")
    elif character in {"problem_statement", "research_gap", "research_overview", "literature_map"} and ("body" in slot_ids or "insight" in slot_ids):
        score += 45
        reasons.append("academic evidence-compatible content slots")
    if density == _normalize_key(layout.get("density")):
        score += 20
    elif density == "evidence_heavy" and _normalize_key(layout.get("density")) == "high":
        score += 15
    for need in needs:
        score += _need_score(need, slot_ids, slot_types, layout)
    if preferred_family_id and layout_family_id == preferred_family_id:
        score += 85
        reasons.append(f"production plan layout family {preferred_family_id}")
    elif preferred_family_id and layout_family_id:
        score -= 10
    if layout_family_id and layout_family_id in recent_families and deck_scale in {"large", "very_large"}:
        score -= 20
        reasons.append("recent layout family repetition penalty")
    maximum_repetition = int(scale_rules.get("maximum_repetition") or (4 if deck_scale == "large" else 5 if deck_scale == "very_large" else 3))
    if layout_family_id and family_use_count[layout_family_id] >= maximum_repetition and deck_scale in {"large", "very_large"}:
        score -= 35
        reasons.append("production plan family repetition limit penalty")
    if deck_scale in {"large", "very_large"}:
        if layout_id in recent_layouts:
            score -= 45 if deck_scale == "large" else 70
            reasons.append("recent layout repetition penalty")
        score -= min(layout_use_count[layout_id] * (8 if deck_scale == "large" else 14), 60)
        if deck_scale == "very_large" and _ornament_heavy(layout):
            score -= 18
            reasons.append("very-large ornament reduction")
    unsupported = None
    if character not in SLIDE_CHARACTER_TO_PROMPT_TYPE:
        unsupported = f"unsupported slide character {character}; deterministic fallback used"
    elif unsupported_slide_type:
        unsupported = f"unsupported slide_type {unsupported_slide_type}; deterministic fallback used"
    return {
        "layout": layout,
        "score": score,
        "order": order,
        "direct_match": direct_match,
        "reason": "; ".join(reasons) or f"highest deterministic score for {character}",
        **({"unsupported": unsupported} if unsupported else {}),
    }


def _need_score(need: str, slot_ids: set[str], slot_types: set[str], layout: dict[str, Any]) -> int:
    aliases = {
        "chart": {"chart", "primary_chart", "secondary_chart"},
        "table": {"table", "matrix"},
        "cards": {"cards", "caption_cards"},
        "process": {"process_visual", "diagram", "timeline_steps"},
        "comparison": {"matrix"},
        "timeline": {"timeline_steps"},
        "photo": {"photo_frame", "hero_image"},
        "citation": {"footer"},
        "appendix": {"table", "footer"},
    }
    targets = aliases.get(need, {need})
    if targets & slot_ids or need in slot_types:
        return 35
    policy = f"{layout.get('chart_table_policy', '')} {layout.get('image_policy', '')}".lower()
    if need in policy:
        return 12
    return -18 if need in {"chart", "table", "photo"} else -4


def _bind_slots(slide: dict[str, Any], layout: dict[str, Any]) -> tuple[dict[str, str], dict[str, str], list[dict[str, Any]]]:
    bindings: dict[str, str] = {}
    components: dict[str, str] = {}
    warnings: list[dict[str, Any]] = []
    for slot in layout.get("slots") or []:
        slot_id = str(slot["slot_id"])
        components[slot_id] = str(slot.get("component_id") or "")
        source = _source_for_slot(slide, slot)
        if source:
            bindings[slot_id] = source
    if "title" not in bindings and any(slot.get("slot_id") == "title" for slot in layout.get("slots") or []):
        bindings["title"] = "title"
    if "footer" not in bindings and any(slot.get("slot_id") == "footer" for slot in layout.get("slots") or []):
        bindings["footer"] = "citations"
    return bindings, components, warnings


def _source_for_slot(slide: dict[str, Any], slot: dict[str, Any]) -> str | None:
    slot_id = str(slot["slot_id"])
    slot_type = str(slot["slot_type"])
    if slot_id in {"title", "section_title"}:
        return "title"
    if slot_id == "subtitle":
        return "subtitle"
    if slot_id == "footer":
        return "citations"
    if slot_type == "chart":
        return "chart_data"
    if slot_type == "table":
        return "table_data"
    if slot_type == "image":
        return "image_needs"
    if slot_id in {"cards", "caption_cards", "metric_panels", "timeline_steps", "diagram", "process_visual", "section_tabs", "index_navigation", "case_context", "case_evidence", "next_steps"}:
        return "content_blocks"
    for block in slide.get("content_blocks") or []:
        if isinstance(block, dict) and _normalize_key(block.get("slot")) == _normalize_key(slot_id):
            return f"content_blocks.{block.get('block_id') or slot_id}"
    if slot_type in {"content", "text"} and slot_id not in {"title", "subtitle", "footer"}:
        return "content_blocks"
    return None


def _missing_required_slots(slide: dict[str, Any], layout: dict[str, Any]) -> list[str]:
    slot_ids = _slot_ids(layout)
    slot_types = _slot_types(layout)
    missing = []
    for required_slot in _string_list(slide.get("required_slots")):
        normalized = _normalize_key(required_slot)
        aliases = {
            "section_title": {"title"},
            "body": {"body", "content", "cards", "insight", "diagram", "index_navigation", "timeline_steps", "case_context", "case_evidence"},
            "claim": {"body", "insight", "content"},
            "chart": {"primary_chart", "secondary_chart"},
            "table": {"table", "matrix"},
            "image": {"photo_frame", "hero_image"},
            "photo": {"photo_frame", "hero_image"},
            "cards": {"cards", "caption_cards"},
        }
        if normalized in slot_ids or normalized in slot_types or aliases.get(normalized, set()) & slot_ids:
            continue
        missing.append(required_slot)
    return missing


def _overflow_warnings(slide: dict[str, Any], layout: dict[str, Any], density: str) -> list[dict[str, Any]]:
    slide_id = _slide_id(slide)
    warnings: list[dict[str, Any]] = []
    text_size = len(json.dumps(slide.get("content_blocks") or [], sort_keys=True, ensure_ascii=True))
    block_count = len(slide.get("content_blocks") or [])
    if density in {"high", "evidence_heavy"} and _normalize_key(layout.get("density")) in {"low", "medium"}:
        warnings.append(_warning("OVERFLOW_DENSITY_RISK", slide_id, "High/evidence-heavy slide assigned to a lower-density layout.", layout["layout_id"]))
    if text_size > 1000 or block_count > 5:
        warnings.append(_warning("OVERFLOW_CONTENT_VOLUME_RISK", slide_id, "Content volume may exceed selected layout capacity.", layout["layout_id"]))
    table_data = slide.get("table_data")
    if isinstance(table_data, dict) and len(table_data.get("rows") or []) > 7:
        warnings.append(_warning("OVERFLOW_TABLE_ROW_RISK", slide_id, "Table rows exceed deterministic table rendering cap.", layout["layout_id"]))
    return warnings


def _slide_character(slide: dict[str, Any], index: int, total: int) -> str:
    raw = _normalize_key(slide.get("slide_type"))
    text = _slide_text(slide)
    if index == 1 or raw in {"cover", "title", "hero", "opening"}:
        return "cover"
    if index == total or raw in {"closing", "close", "takeaways", "summary"}:
        return "closing"
    mapping = {
        "visual_toc": "visual_toc",
        "agenda": "visual_toc",
        "roadmap": "visual_toc",
        "section": "section_divider",
        "section_divider": "section_divider",
        "section-divider": "section_divider",
        "research_overview": "research_overview",
        "overview": "research_overview",
        "problem": "problem_statement",
        "problem_statement": "problem_statement",
        "research_gap": "research_gap",
        "literature_map": "literature_map",
        "methodology": "methodology_framework",
        "methodology_framework": "methodology_framework",
        "technical_flow_chart": "technical_flow_chart",
        "sequence": "sequence",
        "process": "sequence",
        "photo_caption_grid": "photo_caption_grid",
        "comparison": "comparison_matrix",
        "comparison_matrix": "comparison_matrix",
        "concept_relationship": "concept_relationship",
        "three_level_explanation": "three_level_explanation",
        "circular_process": "circular_process",
        "kpi": "kpi_dashboard",
        "dashboard": "kpi_dashboard",
        "data_dashboard": "kpi_dashboard",
        "timeline": "timeline_roadmap",
        "timeline_roadmap": "timeline_roadmap",
        "table": "data_table_appendix",
        "table_heavy": "data_table_appendix",
        "data_table_appendix": "data_table_appendix",
        "case": "case_study",
        "case_study": "case_study",
    }
    if raw in mapping:
        return mapping[raw]
    if _has_any(text, ("literature", "prior work")):
        return "literature_map"
    if _has_any(text, ("method", "framework")):
        return "methodology_framework"
    if _has_any(text, ("flow", "architecture", "pipeline")):
        return "technical_flow_chart"
    if _has_any(text, ("timeline", "roadmap")):
        return "timeline_roadmap"
    if _has_any(text, ("comparison", "matrix", "versus")):
        return "comparison_matrix"
    if _has_any(text, ("kpi", "dashboard", "metric")) or _has_payload(slide.get("chart_data")):
        return "kpi_dashboard"
    if _has_payload(slide.get("table_data")):
        return "data_table_appendix"
    if _has_payload(slide.get("image_needs")):
        return "photo_caption_grid"
    return "research_overview"


def _unsupported_slide_type(slide: dict[str, Any], index: int, total: int) -> str | None:
    raw = _normalize_key(slide.get("slide_type"))
    if not raw or index == 1 or index == total:
        return None
    supported = {
        "cover",
        "title",
        "hero",
        "opening",
        "closing",
        "close",
        "takeaways",
        "summary",
        "visual_toc",
        "agenda",
        "roadmap",
        "section",
        "section_divider",
        "section-divider",
        "research_overview",
        "overview",
        "problem",
        "problem_statement",
        "research_gap",
        "literature_map",
        "methodology",
        "methodology_framework",
        "technical_flow_chart",
        "sequence",
        "process",
        "photo_caption_grid",
        "comparison",
        "comparison_matrix",
        "concept_relationship",
        "three_level_explanation",
        "circular_process",
        "kpi",
        "dashboard",
        "data_dashboard",
        "timeline",
        "timeline_roadmap",
        "table",
        "table_heavy",
        "data_table_appendix",
        "case",
        "case_study",
        "standard_content",
        "two_column_analysis",
        "card_grid",
        "process_timeline",
    }
    return None if raw in supported else raw


def _apply_section_rhythm(character: str, slide: dict[str, Any], section_position: int, deck_scale: str) -> str:
    if deck_scale not in {"large", "very_large"} or character not in {"research_overview"}:
        return character
    raw = _normalize_key(slide.get("slide_type"))
    if raw in {"research_overview", "overview", "literature_map", "problem_statement", "research_gap"}:
        return character
    rhythm_position = ((section_position - 1) % 5) + 1
    if rhythm_position == 1:
        return "research_overview"
    if rhythm_position == 2:
        return "literature_map" if _has_payload(slide.get("citations")) else "problem_statement"
    if rhythm_position == 3:
        return "three_level_explanation"
    if rhythm_position == 4:
        return "problem_statement"
    return "methodology_framework"


def _section_rhythm_role(character: str, section_position: int, deck_scale: str) -> str:
    if character == "section_divider":
        return "divider"
    if deck_scale in {"large", "very_large"}:
        return ["overview", "evidence", "analysis", "implication", "evidence"][(section_position - 1) % 5]
    if character in {"cover", "visual_toc"}:
        return "opener"
    if character in {"methodology_framework", "technical_flow_chart", "kpi_dashboard", "data_table_appendix"}:
        return "method_data"
    if character == "closing":
        return "close"
    return "context"


def _content_needs(slide: dict[str, Any], character: str) -> list[str]:
    text = _slide_text(slide)
    needs: list[str] = []
    if _has_payload(slide.get("chart_data")) or _has_any(text, ("chart", "kpi", "metric", "dashboard")) or character == "kpi_dashboard":
        needs.append("chart")
    if _has_payload(slide.get("table_data")) or _has_any(text, ("table", "matrix")) or character in {"comparison_matrix", "data_table_appendix"}:
        needs.append("table")
    if _has_any(text, ("card", "cards")) or character in {"three_level_explanation"}:
        needs.append("cards")
    if character in {"methodology_framework", "technical_flow_chart", "sequence", "circular_process", "concept_relationship"}:
        needs.append("process")
    if character == "comparison_matrix":
        needs.append("comparison")
    if character == "timeline_roadmap":
        needs.append("timeline")
    if _has_payload(slide.get("image_needs")) or character == "photo_caption_grid":
        needs.append("photo")
    if _has_payload(slide.get("citations")):
        needs.append("citation")
    if character == "data_table_appendix" or _has_any(text, ("appendix", "reference")):
        needs.append("appendix")
    return _dedupe(needs)


def _content_density(slide: dict[str, Any], needs: list[str]) -> str:
    raw = _normalize_key(slide.get("content_density"))
    if _has_payload(slide.get("citations")) and ("table" in needs or "chart" in needs or len(slide.get("content_blocks") or []) > 2):
        return "evidence_heavy"
    if raw in {"low", "medium", "high"}:
        return raw
    text_size = len(json.dumps(slide.get("content_blocks") or [], sort_keys=True, ensure_ascii=True))
    if text_size > 800 or "table" in needs or "chart" in needs:
        return "high"
    if text_size > 250 or needs:
        return "medium"
    return "low"


def _component_density(density: str, needs: list[str]) -> str:
    if density == "evidence_heavy":
        return "evidence_dense"
    if "table" in needs or "chart" in needs:
        return "data_dense"
    if "cards" in needs or "process" in needs:
        return "modular"
    return density


def _ornament_density(deck_scale: str, density: str, needs: list[str], family: dict[str, Any] | None) -> str:
    if deck_scale == "very_large":
        return "low"
    if deck_scale == "large" and (density in {"high", "evidence_heavy"} or any(need in needs for need in {"table", "appendix"})):
        return "medium-low"
    dominant = _normalize_key(((family or {}).get("geometry_strategy") or {}).get("dominant_density"))
    if dominant == "low":
        return "high" if deck_scale == "small" else "medium"
    if any(need in needs for need in {"photo", "process", "timeline"}):
        return "medium"
    return "medium-low" if density == "high" else "medium"


def _deck_scale(slide_count: int) -> str:
    if slide_count <= 12:
        return "small"
    if slide_count <= 30:
        return "medium"
    if slide_count <= 80:
        return "large"
    return "very_large"


def _rotation_window(scale_rules: dict[str, Any], deck_scale: str) -> int:
    maximum = int(scale_rules.get("maximum_repetition") or 0)
    if maximum > 0:
        return min(maximum, 5)
    return 5 if deck_scale == "very_large" else 4 if deck_scale == "large" else 3


def _deck_tone_variant(presentation_plan: dict[str, Any], design_brief: dict[str, Any]) -> str:
    text = f"{presentation_plan.get('tone', '')} {design_brief.get('tone', '')}".lower()
    if "creative" in text:
        return "creative"
    if "professional" in text:
        return "professional"
    return "academic"


def _tone_for_slide(character: str, default_tone: str) -> str:
    if character in {"research_overview", "research_gap", "literature_map", "methodology_framework", "data_table_appendix"}:
        return "academic"
    if character in {"kpi_dashboard", "comparison_matrix", "technical_flow_chart", "timeline_roadmap"}:
        return "professional"
    if character in {"cover", "section_divider", "visual_toc", "photo_caption_grid", "circular_process"}:
        return "creative"
    return default_tone


def _render_priority(character: str, needs: list[str]) -> int:
    if character in {"cover", "section_divider"}:
        return 1
    if any(need in needs for need in ("chart", "table", "comparison")):
        return 2
    if "appendix" in needs:
        return 4
    return DEFAULT_RENDER_PRIORITY


def _repeated_layout_warning(
    *,
    slide_id: str,
    layout_id: str,
    layout_family_id: str,
    layout_use_count: Counter[str],
    family_use_count: Counter[str],
    scale_rules: dict[str, Any],
) -> dict[str, Any] | None:
    maximum_repetition = int(scale_rules.get("maximum_repetition") or 4)
    next_layout_count = layout_use_count[layout_id] + 1
    next_family_count = family_use_count[layout_family_id] + 1
    if next_layout_count <= maximum_repetition and next_family_count <= maximum_repetition:
        return None
    return {
        "code": "REPEATED_LAYOUT_RISK",
        "slide_id": slide_id,
        "layout_id": layout_id,
        "message": "Selected layout or layout family exceeds production-plan repetition guidance.",
        "severity": "warning",
        "layout_use_count": next_layout_count,
        "family_use_count": next_family_count,
    }


def _visual_fidelity_compliance(bindings: list[dict[str, Any]], production_context: dict[str, Any]) -> dict[str, Any]:
    targets = production_context.get("visual_fidelity_targets") or {}
    selected_layouts = [str(binding.get("selected_layout_id") or "") for binding in bindings]
    selected_families = [str(binding.get("layout_family_id") or "") for binding in bindings]
    fallback_count = sum(1 for binding in bindings if binding.get("fallback_used"))
    slide_count = max(1, len(bindings))
    board_layout_count = sum(1 for layout_id in selected_layouts if layout_id.startswith("layout-board-"))
    generic_layout_count = sum(1 for layout_id in selected_layouts if layout_id.endswith("-mvp") or "standard-content-mvp" in layout_id)
    max_fallback_ratio = float(targets.get("maximum_fallback_ratio") or 0.08)
    max_generic_layout_ratio = float(targets.get("maximum_generic_layout_ratio") or 0.0)
    minimum_families = int(targets.get("minimum_distinct_layout_families_used") or 1)
    return {
        "production_plan_used": bool(production_context.get("production_plan_used")),
        "target_ids_applied": production_context.get("fidelity_target_ids") or [],
        "board_layout_ratio": round(board_layout_count / slide_count, 4),
        "fallback_ratio": round(fallback_count / slide_count, 4),
        "generic_layout_ratio": round(generic_layout_count / slide_count, 4),
        "distinct_layout_family_count": len({family for family in selected_families if family and family != "NO_FAMILY"}),
        "maximum_fallback_ratio_met": (fallback_count / slide_count) <= max_fallback_ratio,
        "maximum_generic_layout_ratio_met": (generic_layout_count / slide_count) <= max_generic_layout_ratio,
        "minimum_distinct_layout_families_met": len({family for family in selected_families if family and family != "NO_FAMILY"}) >= min(minimum_families, slide_count),
        "footer_citation_target": targets.get("footer_citation_presence_ratio"),
        "section_navigation_target": targets.get("section_navigation_presence_ratio"),
    }


def _section_positions(slides: list[dict[str, Any]]) -> dict[str, int]:
    counts: defaultdict[str, int] = defaultdict(int)
    positions: dict[str, int] = {}
    for slide in slides:
        section_id = str(slide.get("section_id") or "default")
        counts[section_id] += 1
        positions[_slide_id(slide)] = counts[section_id]
    return positions


def _slot_ids(layout: dict[str, Any]) -> set[str]:
    return {_normalize_key(slot.get("slot_id")) for slot in layout.get("slots") or []}


def _slot_types(layout: dict[str, Any]) -> set[str]:
    return {_normalize_key(slot.get("slot_type")) for slot in layout.get("slots") or []}


def _default_image_policy(layout: dict[str, Any]) -> str:
    if "image" in _slot_types(layout):
        return "Photos allowed only inside declared image/photo frame slots."
    return "No raster image placement required by selected layout."


def _ornament_heavy(layout: dict[str, Any]) -> bool:
    text = json.dumps(layout, sort_keys=True).lower()
    return any(token in text for token in ("ornament", "diagonal", "oversized", "radial"))


def _normalize_slides(payload: dict[str, Any] | list[dict[str, Any]]) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [slide for slide in payload if isinstance(slide, dict)]
    if isinstance(payload, dict) and isinstance(payload.get("slides"), list):
        return [slide for slide in payload["slides"] if isinstance(slide, dict)]
    if isinstance(payload, dict) and isinstance(payload.get("slide_blueprints"), list):
        return [slide for slide in payload["slide_blueprints"] if isinstance(slide, dict)]
    if isinstance(payload, dict):
        return [payload]
    raise ValueError("slide_blueprint must be an object or array")


def _deck_id(slides: list[dict[str, Any]], template_spec: dict[str, Any]) -> str:
    seed = json.dumps({"design_id": template_spec.get("design_id"), "slides": [_slide_id(slide) for slide in slides]}, sort_keys=True, ensure_ascii=True)
    return f"deck-assembly-{hashlib.sha256(seed.encode('utf-8')).hexdigest()[:12]}"


def _slide_id(slide: dict[str, Any]) -> str:
    return str(slide.get("slide_id") or slide.get("id") or "slide")


def _slide_text(slide: dict[str, Any]) -> str:
    return json.dumps(
        [slide.get("slide_type"), slide.get("title"), slide.get("subtitle"), slide.get("content_blocks"), slide.get("design_intent"), slide.get("required_slots")],
        sort_keys=True,
        ensure_ascii=True,
    ).lower()


def _has_payload(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, (str, list, dict)):
        return bool(value)
    return True


def _has_any(text: str, words: tuple[str, ...]) -> bool:
    return any(re.search(rf"\b{re.escape(word)}\b", text) for word in words)


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return [str(value)]


def _normalize_key(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _warning(code: str, slide_id: str, message: str, layout_id: str | None = None, *, slot_id: str | None = None, severity: str = "warning") -> dict[str, Any]:
    payload = {"code": code, "slide_id": slide_id, "message": message, "severity": severity}
    if layout_id is not None:
        payload["layout_id"] = layout_id
    if slot_id is not None:
        payload["slot_id"] = slot_id
    return payload


def _dedupe(items: list[str]) -> list[str]:
    result: list[str] = []
    for item in items:
        if item not in result:
            result.append(item)
    return result


def _dedupe_warnings(warnings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str, str]] = set()
    result: list[dict[str, Any]] = []
    for warning in warnings:
        key = (str(warning.get("code")), str(warning.get("slide_id")), str(warning.get("layout_id")), str(warning.get("slot_id")))
        if key in seen:
            continue
        seen.add(key)
        result.append(warning)
    return result


def _load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _display_path(path: Path) -> str:
    return path.as_posix()


if __name__ == "__main__":
    raise SystemExit(main())
