"""Narrow Phase 3 adapter over the existing deterministic Creative Front-End."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ...creative_frontend.pipeline import (
    FIT_PASS_THRESHOLD,
    FIT_WEIGHTS,
    MAX_CONSECUTIVE_LAYOUT,
    build_presentation_architecture,
)
from ...generator_contracts import validateCreativeTemplateArchitecture, validatePresentationArchitecture
from ..identity import stable_id
from ..intake.config import Phase3Config
from ..intake.multi_source import IntakeArtifacts
from ..planning.strict_adapter import StrictPlanningArtifacts
from ..provenance import seal_artifact, semantic_content_sha256, verify_artifact_content_hash


ADAPTER_VERSION = "deckcompiler-creative-frontend-adapter-v1"
FORBIDDEN_ACTIONS = {
    "reduce_font_until_fit",
    "rasterize_text",
    "use_full_slide_screenshot",
    "drop_evidence_binding",
    "invent_missing_content",
}


@dataclass(frozen=True, slots=True)
class ArchitectureArtifacts:
    presentation_architecture: dict[str, Any]
    design_invariants: dict[str, Any]
    module_art_directions: dict[str, Any]
    creative_template_architecture: dict[str, Any]
    creative_fit_report: dict[str, Any]
    architecture_validation_report: dict[str, Any]


FAMILY_CATALOG: dict[str, dict[str, Any]] = {
    "family-editorial-hero": {
        "composition_archetype": "asymmetric editorial hero with decision frame",
        "supported_slide_roles": ["decision_framing", "recommendation"],
        "capacity_intent": "one thesis, one supporting proof cluster, and a visible source footer",
        "expected_visual_regions": ["title_band", "hero_field", "proof_panel", "citation_footer"],
    },
    "family-process-flow": {
        "composition_archetype": "directional process flow with bounded stages",
        "supported_slide_roles": ["system_process", "implementation_sources"],
        "capacity_intent": "three to five ordered stages with editable labels and connectors",
        "expected_visual_regions": ["title_band", "process_lane", "annotation_panel", "citation_footer"],
    },
    "family-evidence-grid": {
        "composition_archetype": "analytical evidence grid with metric hierarchy",
        "supported_slide_roles": ["risk_findings", "options_comparison"],
        "capacity_intent": "four evidence units or metrics with explicit provenance",
        "expected_visual_regions": ["title_band", "evidence_grid", "metric_callout", "citation_footer"],
    },
    "family-comparison-matrix": {
        "composition_archetype": "editable option matrix with decision-criteria axis",
        "supported_slide_roles": ["options_comparison", "recommendation"],
        "capacity_intent": "two to four options and up to four criteria without microtext",
        "expected_visual_regions": ["title_band", "comparison_matrix", "decision_callout", "citation_footer"],
    },
    "family-recommendation-focus": {
        "composition_archetype": "recommendation focus with rationale ladder",
        "supported_slide_roles": ["recommendation", "decision_framing"],
        "capacity_intent": "one recommendation with three evidence-backed rationale points",
        "expected_visual_regions": ["title_band", "recommendation_focus", "rationale_ladder", "citation_footer"],
    },
    "family-roadmap-sources": {
        "composition_archetype": "phased roadmap with limitation and source-notes rail",
        "supported_slide_roles": ["implementation_sources", "system_process"],
        "capacity_intent": "three implementation phases plus limitations and source notes",
        "expected_visual_regions": ["title_band", "roadmap_lane", "limitation_rail", "citation_footer"],
    },
}

ROLE_SELECTION = {
    "decision_framing": ("family-editorial-hero", "layout-decision-hero"),
    "system_process": ("family-process-flow", "layout-process-flow"),
    "risk_findings": ("family-evidence-grid", "layout-risk-evidence-grid"),
    "options_comparison": ("family-comparison-matrix", "layout-options-matrix"),
    "recommendation": ("family-recommendation-focus", "layout-recommendation-focus"),
    "implementation_sources": ("family-roadmap-sources", "layout-roadmap-sources"),
}


def build_architecture_artifacts(
    config: Phase3Config,
    intake: IntakeArtifacts,
    planning: StrictPlanningArtifacts,
) -> ArchitectureArtifacts:
    presentation = build_presentation_architecture(
        presentation_plan=planning.presentation_plan,
        slide_blueprints=planning.slide_blueprint_collection,
        source_plan_path="presentation_plan.json",
        source_blueprint_path="slide_blueprint_collection.json",
        max_batch_size=2,
    )
    validatePresentationArchitecture(presentation)
    design_invariants = _build_design_invariants(presentation, planning)
    module_art_directions = _build_module_art_directions(presentation, planning, design_invariants)
    creative, fit_report = _build_planning_creative_architecture(
        presentation,
        planning,
        design_invariants,
        module_art_directions,
    )
    validation_report = _build_architecture_validation_report(
        intake,
        planning,
        presentation,
        creative,
        design_invariants,
        module_art_directions,
        fit_report,
    )
    artifacts = ArchitectureArtifacts(
        presentation,
        design_invariants,
        module_art_directions,
        creative,
        fit_report,
        validation_report,
    )
    from .validation import validate_phase3_architecture_graph

    validate_phase3_architecture_graph(intake, planning, artifacts)
    for payload in (design_invariants, module_art_directions, fit_report, validation_report):
        verify_artifact_content_hash(payload)
    return artifacts


def _build_design_invariants(
    presentation: dict[str, Any],
    planning: StrictPlanningArtifacts,
) -> dict[str, Any]:
    invariants = [
        "professional",
        "academic",
        "authoritative",
        "contemporary",
        "high readability",
        "clear hierarchy",
        "citation visibility",
        "numerical fidelity",
        "source traceability",
        "native slot binding required",
        "full-slide raster forbidden",
        "screenshot slide forbidden",
        "semantic text rasterization forbidden",
        "microtext-dependent design forbidden",
        "maximum two consecutive slides with same layout family",
        "title footer citation safe-area required",
        "one primary message per slide",
        "body paragraph overload prohibited",
        "data and table accuracy strict",
        "Visual Target is future visual truth",
        "Sidecar is future semantic truth",
        "final emitter deterministic",
    ]
    payload = {
        "schema_name": "design_invariants",
        "schema_version": "1.0.0",
        "invariant_set_id": stable_id("invariants", invariants),
        "presentation_architecture_id": presentation["architecture_id"],
        "invariants": invariants,
        "editability_policy": {
            "real_text": "native_required",
            "tables": "native_required",
            "charts": "native_required",
            "cards": "native_required",
            "replaceable_images": "framed_raster_allowed",
            "full_slide_raster": "forbidden",
        },
        "phase_boundary": {
            "visual_target_status": "not_created",
            "semantic_sidecar_status": "not_finalized",
            "reconstruction_status": "not_executed",
        },
    }
    return seal_artifact(
        payload,
        artifact_type="design_invariants",
        input_artifact_ids=(planning.evidence_allocation_report["artifact"]["artifact_id"],),
    )


def _build_module_art_directions(
    presentation: dict[str, Any],
    planning: StrictPlanningArtifacts,
    design_invariants: dict[str, Any],
) -> dict[str, Any]:
    role_by_slide = {
        item["slide_id"]: item["role"] for item in planning.evidence_allocation_report["slides"]
    }
    records: list[dict[str, Any]] = []
    previous_module_id: str | None = None
    for index, module in enumerate(presentation["modules"], start=1):
        roles = [role_by_slide[slide_id] for slide_id in module["slide_ids"]]
        profile = _direction_profile(roles, index)
        records.append(
            {
                "module_id": module["module_id"],
                "narrative_objective": module["objective"],
                "visual_metaphor": profile["visual_metaphor"],
                "composition_energy": profile["composition_energy"],
                "spatial_direction": profile["spatial_direction"],
                "focal_behavior": profile["focal_behavior"],
                "illustration_language": profile["illustration_language"],
                "diagram_language": profile["diagram_language"],
                "density_range": profile["density_range"],
                "contrast_strategy": profile["contrast_strategy"],
                "continuity_with_previous_module": (
                    "Establish the opening visual grammar and citation treatment."
                    if previous_module_id is None
                    else f"Retain type hierarchy and citation treatment from {previous_module_id} while changing focal structure."
                ),
                "differentiation_from_other_modules": profile["differentiation"],
                "forbidden_visual_patterns": [
                    "full-slide raster",
                    "rasterized text",
                    "microtext used to force capacity",
                    "unbound decorative evidence",
                ],
                "batch_visual_grammar": [
                    {
                        "batch_id": batch["batch_id"],
                        "visual_grammar_intent": profile["batch_grammar"],
                        "transition_from": previous_module_id or "deck opening",
                        "transition_to": (
                            presentation["modules"][index]["module_id"]
                            if index < len(presentation["modules"])
                            else "decision close"
                        ),
                    }
                    for batch in module["batches"]
                ],
            }
        )
        previous_module_id = module["module_id"]
    payload = {
        "schema_name": "module_art_directions",
        "schema_version": "1.0.0",
        "direction_set_id": stable_id("directions", records),
        "presentation_architecture_id": presentation["architecture_id"],
        "design_invariant_set_id": design_invariants["invariant_set_id"],
        "modules": records,
    }
    return seal_artifact(
        payload,
        artifact_type="module_art_directions",
        input_artifact_ids=(design_invariants["artifact"]["artifact_id"],),
    )


def _build_planning_creative_architecture(
    presentation: dict[str, Any],
    planning: StrictPlanningArtifacts,
    design_invariants: dict[str, Any],
    module_art_directions: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    role_by_slide = {
        item["slide_id"]: item["role"] for item in planning.evidence_allocation_report["slides"]
    }
    density_by_slide = {
        slide["slide_id"]: slide["content_density"] for slide in planning.slide_blueprint_collection["slides"]
    }
    direction_by_module = {item["module_id"]: item for item in module_art_directions["modules"]}
    module_rows: list[dict[str, Any]] = []
    selected_by_slide: dict[str, tuple[str, str]] = {}
    used_family_ids: set[str] = set()
    for module in presentation["modules"]:
        batch_rows: list[dict[str, Any]] = []
        for batch in module["batches"]:
            selected = []
            for slide_id in batch["slide_ids"]:
                selection = ROLE_SELECTION[role_by_slide[slide_id]]
                selected_by_slide[slide_id] = selection
                selected.append(selection[0])
                used_family_ids.add(selection[0])
            candidates = list(dict.fromkeys(selected))
            for family_id in FAMILY_CATALOG:
                if family_id not in candidates:
                    candidates.append(family_id)
                if len(candidates) >= 2:
                    break
            batch_rows.append(
                {
                    "batch_id": batch["batch_id"],
                    "candidate_family_ids": candidates,
                    "selected_family_ids": list(dict.fromkeys(selected)),
                    "reference_brief": (
                        f"Plan separate editable template-reference archetypes for {module['title']} / {batch['batch_id']}; "
                        "preserve native semantic slots and citations; do not render final copy or a full-slide raster."
                    ),
                }
            )
        direction = direction_by_module[module["module_id"]]
        module_rows.append(
            {
                "module_id": module["module_id"],
                "art_direction": (
                    f"{direction['visual_metaphor']}; {direction['composition_energy']}; "
                    f"{direction['contrast_strategy']}"
                ),
                "differentiation_signature": [
                    direction["visual_metaphor"],
                    direction["spatial_direction"],
                    direction["focal_behavior"],
                ],
                "batch_template_families": batch_rows,
            }
        )

    decisions: list[dict[str, Any]] = []
    fit_rows: list[dict[str, Any]] = []
    previous_layout: str | None = None
    layout_run = 0
    for slide in presentation["slides"]:
        slide_id = slide["slide_id"]
        family_id, layout_id = selected_by_slide[slide_id]
        layout_run = layout_run + 1 if layout_id == previous_layout else 1
        capacity = {"low": 1.0, "medium": 0.95, "high": 0.88}[density_by_slide[slide_id]]
        scores = {
            "semantic": 1.0,
            "capacity": capacity,
            "editability": 1.0,
            "differentiation": 1.0 if layout_run == 1 else 0.72,
        }
        overall = round(sum(scores[key] * FIT_WEIGHTS[key] for key in FIT_WEIGHTS), 4)
        status = "pass" if capacity >= 0.8 and layout_run <= MAX_CONSECUTIVE_LAYOUT else "recompose_content"
        reasons = [
            "Planning archetype covers every declared semantic slot and preserves native editability."
            if status == "pass"
            else "Planning capacity or layout repetition requires an upstream recomposition action."
        ]
        next_actions = [] if status == "pass" else ["recompose_content"]
        decisions.append(
            {
                "slide_id": slide_id,
                "module_id": slide["module_id"],
                "batch_id": slide["batch_id"],
                "layout_id": layout_id,
                "template_family_id": family_id,
                "scores": scores,
                "overall_score": overall,
                "status": status,
                "reasons": reasons,
                "next_actions": next_actions,
            }
        )
        action_type = next_actions[0] if next_actions else None
        fit_rows.append(
            {
                "slide_id": slide_id,
                "selected_family_id": family_id,
                "selected_layout_archetype": layout_id,
                "status": status,
                "scores": scores,
                "reason": reasons[0],
                "action_type": action_type,
                "action_owner_artifact": "slide_blueprint_collection" if action_type else None,
                "action_target_artifact": "creative_template_architecture" if action_type else None,
                "forbidden_action_detected": bool(action_type in FORBIDDEN_ACTIONS),
            }
        )
        previous_layout = layout_id

    creative_payload = {
        "schema_name": "creative_template_architecture",
        "schema_version": "1.0",
        "deck_id": presentation["deck_id"],
        "presentation_architecture_id": presentation["architecture_id"],
        "template_pack_id": "unmaterialized-planning-vocabulary-v1",
        "global_visual_dna": {
            "invariants": [
                "Use editable native objects for semantic content.",
                "Preserve source traceability and visible citations.",
                "Forbid full-slide raster backgrounds and rasterized text.",
                "Treat this artifact as planning input, not materialized template proof.",
            ],
            "color_roles": ["background", "foreground", "accent", "evidence", "risk", "action"],
            "typography_roles": ["display", "title", "body", "data", "caption", "citation"],
            "allowed_raster_roles": ["photo", "source_figure", "replaceable_image_frame"],
            "forbidden_raster_roles": ["full_slide_background", "text", "table", "chart", "card", "footer"],
        },
        "modules": module_rows,
        "fit_policy": {
            "pass_threshold": FIT_PASS_THRESHOLD,
            "weights": FIT_WEIGHTS,
            "max_repair_waves": 0,
            "max_consecutive_layout": MAX_CONSECUTIVE_LAYOUT,
            "max_consecutive_family": 5,
        },
        "slide_fit_decisions": decisions,
        "template_reference_policy": {
            "image_generation_scope": "template_references_only",
            "content_rendering_allowed": False,
            "preferred_reference_unit": "batch_family",
        },
    }
    creative = {
        **creative_payload,
        "architecture_id": stable_id("cta", creative_payload),
    }
    validateCreativeTemplateArchitecture(creative)
    candidate_catalog = []
    for family_id in sorted(used_family_ids | {family for module in module_rows for batch in module["batch_template_families"] for family in batch["candidate_family_ids"]}):
        base = FAMILY_CATALOG[family_id]
        candidate_catalog.append(
            {
                "family_id": family_id,
                "semantic_compatibility": "role and required-slot compatible at planning level",
                "supported_slide_roles": base["supported_slide_roles"],
                "composition_archetype": base["composition_archetype"],
                "capacity_intent": base["capacity_intent"],
                "editability_intent": "all real text, tables, charts, cards, connectors, and citations remain native",
                "differentiation_intent": "change focal structure without changing evidence meaning",
                "expected_visual_regions": base["expected_visual_regions"],
                "prohibited_uses": ["full-slide screenshot", "rasterized text", "microtext overflow workaround"],
            }
        )
    fit_payload = {
        "schema_name": "creative_fit_report",
        "schema_version": "1.0.0",
        "report_id": stable_id("fit", creative["architecture_id"], fit_rows),
        "creative_architecture_id": creative["architecture_id"],
        "planning_level_only": True,
        "geometry_aware_fit_deferred_to_phase4": True,
        "candidate_families": candidate_catalog,
        "decisions": fit_rows,
        "forbidden_actions": sorted(FORBIDDEN_ACTIONS),
        "repair_executed": False,
    }
    fit_report = seal_artifact(
        fit_payload,
        artifact_type="creative_fit_report",
        input_artifact_ids=(module_art_directions["artifact"]["artifact_id"],),
    )
    _validate_creative_planning(creative, fit_report)
    return creative, fit_report


def _build_architecture_validation_report(
    intake: IntakeArtifacts,
    planning: StrictPlanningArtifacts,
    presentation: dict[str, Any],
    creative: dict[str, Any],
    design_invariants: dict[str, Any],
    module_art_directions: dict[str, Any],
    fit_report: dict[str, Any],
) -> dict[str, Any]:
    global_slide_ids = [slide["slide_id"] for slide in presentation["slides"]]
    assignments = [slide_id for module in presentation["modules"] for slide_id in module["slide_ids"]]
    positions = {slide_id: index for index, slide_id in enumerate(global_slide_ids)}
    module_contiguous = all(_is_contiguous([positions[slide_id] for slide_id in module["slide_ids"]]) for module in presentation["modules"])
    batch_contiguous = all(
        _is_contiguous([positions[slide_id] for slide_id in batch["slide_ids"]])
        for module in presentation["modules"]
        for batch in module["batches"]
    )
    evidence_source = {
        item["evidence_id"]: item["source_id"] for item in intake.evidence_unit_registry["evidence_units"]
    }
    documentary_ids = {
        item["source_id"] for item in intake.source_corpus["sources"] if item["source_type"] == "pdf"
    }
    source_slide_sets = {source_id: set() for source_id in documentary_ids}
    for slide in presentation["slides"]:
        for evidence_id in slide["evidence_ids"]:
            source_id = evidence_source.get(evidence_id)
            if source_id in source_slide_sets:
                source_slide_sets[source_id].add(slide["slide_id"])
    report_payload = {
        "schema_name": "architecture_validation_report",
        "schema_version": "1.0.0",
        "report_id": stable_id("archvalidation", presentation["architecture_id"], creative["architecture_id"]),
        "presentation_architecture_id": presentation["architecture_id"],
        "creative_architecture_id": creative["architecture_id"],
        "adapter_version": ADAPTER_VERSION,
        "existing_creative_frontend_builder_used": "build_presentation_architecture",
        "planning_creative_reason": "Materialized template specs and deck assembly plans are Phase 4 inputs, so Phase 3 emits schema-valid planning archetypes only.",
        "slide_assignment_count": len(assignments),
        "orphan_slide_ids": sorted(set(global_slide_ids) - set(assignments)),
        "duplicate_slide_assignments": sorted({slide_id for slide_id in assignments if assignments.count(slide_id) > 1}),
        "module_ranges_contiguous": module_contiguous,
        "batch_ranges_contiguous": batch_contiguous,
        "slide_order_preserved": global_slide_ids == planning.evidence_allocation_report["ordered_slide_ids"],
        "documentary_source_slide_counts": {
            source_id: len(slides) for source_id, slides in sorted(source_slide_sets.items())
        },
        "design_invariant_set_id": design_invariants["invariant_set_id"],
        "module_art_direction_set_id": module_art_directions["direction_set_id"],
        "creative_fit_report_id": fit_report["report_id"],
        "presentation_architecture_content_sha256": semantic_content_sha256(presentation),
        "creative_template_architecture_content_sha256": semantic_content_sha256(creative),
        "validation_status": "valid",
    }
    return seal_artifact(
        report_payload,
        artifact_type="architecture_validation_report",
        input_artifact_ids=(
            design_invariants["artifact"]["artifact_id"],
            module_art_directions["artifact"]["artifact_id"],
            fit_report["artifact"]["artifact_id"],
        ),
    )


def _direction_profile(roles: list[str], index: int) -> dict[str, str]:
    if "system_process" in roles:
        return {
            "visual_metaphor": f"system map and guided flow {index}",
            "composition_energy": "measured, explanatory, and progressively directional",
            "spatial_direction": "left-to-right flow with a stable source rail",
            "focal_behavior": "move from system boundary to operating sequence",
            "illustration_language": "technical editorial primitives with replaceable source-figure frames",
            "diagram_language": "native nodes, connectors, and labelled stages",
            "density_range": "low to medium",
            "contrast_strategy": "calm field with one high-contrast operational path",
            "differentiation": "uses explanatory flow instead of comparison or action framing",
            "batch_grammar": "orient, explain, then hand off to analytical evidence",
        }
    if "risk_findings" in roles or "options_comparison" in roles:
        return {
            "visual_metaphor": f"evidence field and comparative lens {index}",
            "composition_energy": "analytical, evidence-led, and tension-aware",
            "spatial_direction": "ranked grid moving from risk signal to option trade-off",
            "focal_behavior": "anchor on the highest-consequence evidence and explicit criteria",
            "illustration_language": "restrained analytical marks and evidence emphasis",
            "diagram_language": "editable matrices, metric callouts, and causal links",
            "density_range": "medium to high",
            "contrast_strategy": "neutral evidence field with risk and option accents",
            "differentiation": "uses comparison density and proof hierarchy rather than process flow",
            "batch_grammar": "surface risks, compare options, preserve numerical and citation fidelity",
        }
    return {
        "visual_metaphor": f"decision beacon and directional roadmap {index}",
        "composition_energy": "decisive, operational, and cautiously optimistic",
        "spatial_direction": "central recommendation moving into phased forward motion",
        "focal_behavior": "hold the decision as the anchor, then reveal implementation gates",
        "illustration_language": "directional editorial primitives with bounded phase markers",
        "diagram_language": "native roadmap stages, decision gates, and source-note rail",
        "density_range": "low to medium",
        "contrast_strategy": "strong action focal point with subdued limitation context",
        "differentiation": "uses action orientation and closure rather than explanation or comparison",
        "batch_grammar": "decide, justify, sequence action, and close with limitations and sources",
    }


def _validate_creative_planning(creative: dict[str, Any], fit_report: dict[str, Any]) -> None:
    validateCreativeTemplateArchitecture(creative)
    layout_ids = [item["layout_id"] for item in creative["slide_fit_decisions"]]
    for index in range(len(layout_ids) - MAX_CONSECUTIVE_LAYOUT):
        run = layout_ids[index : index + MAX_CONSECUTIVE_LAYOUT + 1]
        if len(set(run)) == 1:
            raise ValueError("DC_EXCESSIVE_LAYOUT_REPETITION: more than two consecutive identical layouts")
    for decision in creative["slide_fit_decisions"]:
        if decision["status"] == "pass":
            if decision["scores"]["semantic"] != 1.0 or decision["scores"]["editability"] != 1.0:
                raise ValueError("DC_CREATIVE_FIT_INVALID: pass requires semantic and editability scores of 1.0")
            if decision["scores"]["capacity"] < 0.8:
                raise ValueError("DC_CREATIVE_FIT_INVALID: insufficient capacity cannot pass")
    for item in fit_report["decisions"]:
        if item["action_type"] in FORBIDDEN_ACTIONS or item["forbidden_action_detected"]:
            raise ValueError("DC_FORBIDDEN_FIT_ACTION: forbidden repair action in planning report")
        if item["status"] != "pass" and (
            not item["action_type"] or not item["action_owner_artifact"] or not item["action_target_artifact"]
        ):
            raise ValueError("DC_CREATIVE_FIT_INVALID: non-pass decision lacks executable action ownership")
    if fit_report["repair_executed"]:
        raise ValueError("DC_STAGE_OUTSIDE_PHASE: repair execution is forbidden in Phase 3")


def _is_contiguous(positions: list[int]) -> bool:
    return positions == list(range(min(positions), max(positions) + 1)) if positions else False


__all__ = ["ADAPTER_VERSION", "ArchitectureArtifacts", "build_architecture_artifacts"]
