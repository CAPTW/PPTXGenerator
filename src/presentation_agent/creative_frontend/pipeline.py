"""Deterministic creative front-end for editable template deck compilation.

This layer turns the existing section-oriented plan and slide blueprints into
explicit Module -> Batch -> Slide architecture, applies the existing editable
template layout planner, records a bounded content/template fit decision, and
emits source-backed semantic sidecars.  It deliberately does not generate
content-filled slide images.  Image generation remains limited to template
references; the canonical editable-template compiler remains the primary
backend.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from ..compiler.design_template_layout_planner import plan_design_template_layouts
from ..generator_contracts import (
    validateCreativeTemplateArchitecture,
    validateDeckAssemblyPlan,
    validateDesignBrief,
    validateEditableTemplateSpec,
    validatePresentationArchitecture,
    validatePresentationPlan,
    validateSlideBlueprint,
    validateSlideSemanticSidecar,
)
from .template_spec_adapter import adapt_image_template_spec
from .semantic_validation import (
    validate_creative_template_architecture_semantics,
    validate_presentation_architecture_semantics,
    validate_sidecar_semantics,
)


TEMPLATE_REFERENCE_INPUT_FORMAT = "template-reference-contract"


SCHEMA_VERSION = "1.0"
FIT_WEIGHTS = {"semantic": 0.4, "capacity": 0.25, "editability": 0.25, "differentiation": 0.1}
FIT_PASS_THRESHOLD = 0.82
MAX_CONSECUTIVE_LAYOUT = 2
MAX_CONSECUTIVE_FAMILY = 5
NATIVE_OBJECT_TYPES = {
    "title": "text_box",
    "subtitle": "text_box",
    "body": "text_box",
    "content": "text_box",
    "claim": "text_box",
    "callout": "shape",
    "insight": "shape",
    "cards": "shape",
    "card_group": "shape",
    "kpi": "shape",
    "metric_panels": "shape",
    "table": "table",
    "matrix": "table",
    "chart": "chart",
    "primary_chart": "chart",
    "icon": "svg_icon",
    "connector": "connector",
    "diagram": "shape",
    "process": "shape",
    "process_visual": "shape",
    "timeline": "shape",
    "timeline_steps": "shape",
    "milestone_notes": "text_box",
    "footer": "footer",
    "citations": "footer",
    "speaker_notes": "speaker_notes",
}


def build_presentation_architecture(
    *,
    presentation_plan: dict[str, Any],
    slide_blueprints: dict[str, Any] | list[dict[str, Any]],
    source_plan_path: str | None = None,
    source_blueprint_path: str | None = None,
    max_batch_size: int = 5,
) -> dict[str, Any]:
    """Build an explicit, validated Module -> Batch -> Slide overlay."""

    validatePresentationPlan(presentation_plan)
    slides = _normalize_slides(slide_blueprints)
    if not slides:
        raise ValueError("slide_blueprints must contain at least one slide")
    if not 1 <= max_batch_size <= 5:
        raise ValueError("max_batch_size must be between 1 and 5")
    for slide in slides:
        validateSlideBlueprint(slide)
    slide_ids = [str(slide["slide_id"]) for slide in slides]
    duplicate_slide_ids = sorted(slide_id for slide_id, count in Counter(slide_ids).items() if count > 1)
    if duplicate_slide_ids:
        raise ValueError(f"slide_blueprints contain duplicate slide_id values: {', '.join(duplicate_slide_ids)}")

    sections = {
        str(section["section_id"]): section
        for section in presentation_plan.get("sections") or []
        if isinstance(section, dict) and section.get("section_id")
    }
    module_runs: list[tuple[str, list[dict[str, Any]]]] = []
    for slide in slides:
        section_id = str(slide.get("section_id") or "section-unassigned")
        if not module_runs or module_runs[-1][0] != section_id:
            module_runs.append((section_id, [slide]))
        else:
            module_runs[-1][1].append(slide)

    evidence_by_id: dict[str, dict[str, Any]] = {}
    architecture_slides: list[dict[str, Any]] = []
    modules: list[dict[str, Any]] = []
    batch_for_slide: dict[str, str] = {}
    module_for_slide: dict[str, str] = {}
    source_bindings_by_slide: dict[str, list[dict[str, Any]]] = {}

    for module_index, (section_id, module_slides) in enumerate(module_runs, start=1):
        section = sections.get(section_id) or {
            "title": section_id.replace("_", " ").replace("-", " ").title(),
            "purpose": "Preserve the source section as a bounded narrative module.",
        }
        module_id = f"module-{module_index:02d}-{_key(section_id)}"
        batches: list[dict[str, Any]] = []
        for batch_index, start in enumerate(range(0, len(module_slides), max_batch_size), start=1):
            batch_slides = module_slides[start : start + max_batch_size]
            batch_id = f"batch-{module_index:02d}-{batch_index:02d}"
            batch_slide_ids = [str(slide["slide_id"]) for slide in batch_slides]
            batches.append(
                {
                    "batch_id": batch_id,
                    "order": batch_index,
                    "slide_ids": batch_slide_ids,
                    "continuity_anchor": (
                        f"{section.get('title')}: preserve the module claim, evidence terminology, "
                        "numbering, and citation treatment across this batch."
                    ),
                }
            )
            for slide_id in batch_slide_ids:
                batch_for_slide[slide_id] = batch_id
                module_for_slide[slide_id] = module_id

        module_evidence_ids: set[str] = set()
        for slide in module_slides:
            slide_id = str(slide["slide_id"])
            source_bindings = _evidence_for_slide(slide, evidence_by_id)
            source_bindings_by_slide[slide_id] = source_bindings
            evidence_ids = sorted({binding["evidence_id"] for binding in source_bindings})
            module_evidence_ids.update(evidence_ids)

        modules.append(
            {
                "module_id": module_id,
                "section_id": section_id,
                "title": str(section.get("title") or section_id),
                "objective": str(section.get("purpose") or presentation_plan.get("objective") or "Preserve the narrative module."),
                "narrative_role": _module_narrative_role(module_slides, module_index, len(module_runs)),
                "slide_ids": [str(slide["slide_id"]) for slide in module_slides],
                "evidence_ids": sorted(module_evidence_ids),
                "batches": batches,
            }
        )

    for slide_order, slide in enumerate(slides, start=1):
        slide_id = str(slide["slide_id"])
        source_bindings = source_bindings_by_slide[slide_id]
        architecture_slides.append(
            {
                "slide_id": slide_id,
                "order": slide_order,
                "module_id": module_for_slide[slide_id],
                "batch_id": batch_for_slide[slide_id],
                "section_id": str(slide.get("section_id") or "section-unassigned"),
                "slide_type": str(slide.get("slide_type") or "standard_content"),
                "title": str(slide.get("title") or slide_id),
                "content_density": str(slide.get("content_density") or "medium"),
                "required_slots": _unique_strings(slide.get("required_slots") or ["title", "body"]),
                "semantic_intent": _semantic_intent(slide),
                "evidence_ids": sorted({binding["evidence_id"] for binding in source_bindings}),
                "source_bindings": source_bindings,
            }
        )

    deck_id = _stable_id("deck", presentation_plan.get("deck_title"), slide_ids)
    evidence_registry = sorted(evidence_by_id.values(), key=lambda item: item["evidence_id"])
    policies = {
        "preserve_editability": True,
        "image_generation_scope": "template_references_only",
        "allow_full_slide_raster": False,
        "slot_binding_required": True,
        "batching_is_overlay": True,
    }
    architecture_payload = {
        "schema_name": "presentation_architecture",
        "schema_version": SCHEMA_VERSION,
        "deck_id": deck_id,
        "deck_title": str(presentation_plan["deck_title"]),
        "objective": str(presentation_plan["objective"]),
        "source_plan_path": source_plan_path,
        "source_blueprint_path": source_blueprint_path,
        "modules": modules,
        "slides": architecture_slides,
        "evidence_registry": evidence_registry,
        "policies": policies,
    }
    architecture = {
        **architecture_payload,
        "architecture_id": _stable_id("pa", architecture_payload),
    }
    validatePresentationArchitecture(architecture)
    validate_presentation_architecture_semantics(architecture)
    return architecture


def build_creative_template_architecture(
    *,
    presentation_architecture: dict[str, Any],
    slide_blueprints: dict[str, Any] | list[dict[str, Any]],
    editable_template_spec: dict[str, Any],
    deck_assembly_plan: dict[str, Any],
) -> dict[str, Any]:
    """Build module art direction and deterministic content/template fit decisions."""

    validatePresentationArchitecture(presentation_architecture)
    validateEditableTemplateSpec(editable_template_spec)
    validateDeckAssemblyPlan(deck_assembly_plan)
    slides = _normalize_slides(slide_blueprints)
    slide_by_id = {str(slide["slide_id"]): slide for slide in slides}
    binding_by_id = {
        str(binding["slide_id"]): binding
        for binding in deck_assembly_plan.get("slide_layout_bindings") or []
    }
    layout_by_id = {
        str(layout["layout_id"]): layout
        for layout in editable_template_spec.get("layouts") or []
    }
    all_family_ids = _template_family_ids(editable_template_spec)
    fit_decisions: list[dict[str, Any]] = []
    previous_layout_id: str | None = None
    previous_family_id: str | None = None
    layout_run_length = 0
    family_run_length = 0

    for architecture_slide in presentation_architecture["slides"]:
        slide_id = str(architecture_slide["slide_id"])
        slide = slide_by_id[slide_id]
        binding = binding_by_id.get(slide_id) or {}
        layout_id = str(binding.get("selected_layout_id") or binding.get("layout_id") or "NO_LAYOUT")
        family_id = str(binding.get("layout_family_id") or "NO_FAMILY")
        layout_run_length = layout_run_length + 1 if previous_layout_id == layout_id else 1
        family_run_length = family_run_length + 1 if previous_family_id == family_id else 1
        layout = layout_by_id.get(layout_id)
        decision = _fit_decision(
            slide=slide,
            architecture_slide=architecture_slide,
            binding=binding,
            layout=layout,
            editable_template_spec=editable_template_spec,
            previous_layout_id=previous_layout_id,
            previous_family_id=previous_family_id,
            layout_run_length=layout_run_length,
            family_run_length=family_run_length,
        )
        fit_decisions.append(decision)
        previous_layout_id = layout_id
        previous_family_id = family_id

    module_directions: list[dict[str, Any]] = []
    for module_index, module in enumerate(presentation_architecture["modules"], start=1):
        module_bindings = [binding_by_id.get(slide_id) or {} for slide_id in module["slide_ids"]]
        module_slides = [slide_by_id[slide_id] for slide_id in module["slide_ids"]]
        batch_families: list[dict[str, Any]] = []
        for batch in module["batches"]:
            batch_slides = [slide_by_id[slide_id] for slide_id in batch["slide_ids"]]
            selected = _unique_strings(
                (binding_by_id.get(slide_id) or {}).get("layout_family_id")
                for slide_id in batch["slide_ids"]
                if (binding_by_id.get(slide_id) or {}).get("layout_family_id")
            )
            candidates = _candidate_families(selected, all_family_ids, batch_slides)
            batch_families.append(
                {
                    "batch_id": batch["batch_id"],
                    "candidate_family_ids": candidates,
                    "selected_family_ids": selected or candidates[:1],
                    "reference_brief": _reference_brief(module, batch, batch_slides, candidates),
                }
            )
        module_directions.append(
            {
                "module_id": module["module_id"],
                "art_direction": _module_art_direction(module, module_slides, module_bindings),
                "differentiation_signature": _differentiation_signature(module_index, module_slides, module_bindings),
                "batch_template_families": batch_families,
            }
        )

    global_visual_dna = _global_visual_dna(editable_template_spec)
    fit_policy = {
        "pass_threshold": FIT_PASS_THRESHOLD,
        "weights": FIT_WEIGHTS,
        "max_repair_waves": 2,
        "max_consecutive_layout": MAX_CONSECUTIVE_LAYOUT,
        "max_consecutive_family": MAX_CONSECUTIVE_FAMILY,
    }
    template_reference_policy = {
        "image_generation_scope": "template_references_only",
        "content_rendering_allowed": False,
        "preferred_reference_unit": "batch_family",
    }
    architecture_payload = {
        "schema_name": "creative_template_architecture",
        "schema_version": SCHEMA_VERSION,
        "deck_id": presentation_architecture["deck_id"],
        "presentation_architecture_id": presentation_architecture["architecture_id"],
        "template_pack_id": editable_template_spec["design_id"],
        "global_visual_dna": global_visual_dna,
        "modules": module_directions,
        "fit_policy": fit_policy,
        "slide_fit_decisions": fit_decisions,
        "template_reference_policy": template_reference_policy,
    }
    architecture = {
        **architecture_payload,
        "architecture_id": _stable_id("cta", architecture_payload),
    }
    validateCreativeTemplateArchitecture(architecture)
    validate_creative_template_architecture_semantics(
        architecture,
        presentation_architecture,
        editable_template_spec,
    )
    return architecture


def build_slide_semantic_sidecars(
    *,
    presentation_architecture: dict[str, Any],
    creative_template_architecture: dict[str, Any],
    slide_blueprints: dict[str, Any] | list[dict[str, Any]],
    deck_assembly_plan: dict[str, Any],
    editable_template_spec: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build one source-backed semantic truth artifact per slide."""

    validatePresentationArchitecture(presentation_architecture)
    validateCreativeTemplateArchitecture(creative_template_architecture)
    validateDeckAssemblyPlan(deck_assembly_plan)
    validateEditableTemplateSpec(editable_template_spec)
    slides = _normalize_slides(slide_blueprints)
    arch_by_id = {slide["slide_id"]: slide for slide in presentation_architecture["slides"]}
    fit_by_id = {decision["slide_id"]: decision for decision in creative_template_architecture["slide_fit_decisions"]}
    binding_by_id = {binding["slide_id"]: binding for binding in deck_assembly_plan["slide_layout_bindings"]}
    layout_by_id = {layout["layout_id"]: layout for layout in editable_template_spec["layouts"]}
    sidecars: list[dict[str, Any]] = []

    for slide in slides:
        slide_id = str(slide["slide_id"])
        architecture_slide = arch_by_id[slide_id]
        fit = fit_by_id[slide_id]
        binding = binding_by_id[slide_id]
        canonical_content = _canonical_content(slide)
        layout = layout_by_id.get(fit["layout_id"])
        native_required = _native_requirements(slide, canonical_content, layout)
        raster_allowed = _raster_allowances(slide)
        source_bindings = _sidecar_source_bindings(architecture_slide)
        sidecar = {
            "schema_name": "slide_semantic_sidecar",
            "schema_version": SCHEMA_VERSION,
            "slide_id": slide_id,
            "module_id": architecture_slide["module_id"],
            "batch_id": architecture_slide["batch_id"],
            "template_family_id": fit["template_family_id"],
            "layout_id": fit["layout_id"],
            "canonical_content": canonical_content,
            "native_required": native_required,
            "raster_allowed": raster_allowed,
            "source_bindings": source_bindings,
            "editability_policy": {
                "full_slide_raster": "forbidden",
                "text": "native_required",
                "tables": "native_required",
                "charts": "native_required",
                "cards": "native_required",
                "image_frames": "replaceable",
                "speaker_notes": "native_required",
            },
            "content_hash": _content_hash(canonical_content, source_bindings),
        }
        _validate_sidecar_policy(sidecar, binding)
        validateSlideSemanticSidecar(sidecar)
        sidecars.append(sidecar)
    validate_sidecar_semantics(sidecars, presentation_architecture, creative_template_architecture)
    return sidecars


def run_creative_frontend(
    *,
    presentation_plan: dict[str, Any],
    slide_blueprints: dict[str, Any] | list[dict[str, Any]],
    design_brief: dict[str, Any],
    editable_template_spec: dict[str, Any],
    output_dir: str | Path,
    source_plan_path: str | None = None,
    source_blueprint_path: str | None = None,
    template_spec_path: str = "in_memory",
    max_batch_size: int = 5,
    adapter_used: bool = False,
) -> dict[str, Any]:
    """Run the full deterministic front-end and write validated handoff artifacts."""

    validatePresentationPlan(presentation_plan)
    validateDesignBrief(design_brief)
    validateEditableTemplateSpec(editable_template_spec)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    presentation_architecture = build_presentation_architecture(
        presentation_plan=presentation_plan,
        slide_blueprints=slide_blueprints,
        source_plan_path=source_plan_path,
        source_blueprint_path=source_blueprint_path,
        max_batch_size=max_batch_size,
    )
    deck_assembly_plan = plan_design_template_layouts(
        slide_blueprints=slide_blueprints,
        presentation_plan=presentation_plan,
        editable_template_spec=editable_template_spec,
        design_brief=design_brief,
        template_spec_path=template_spec_path,
    )
    creative_template_architecture = build_creative_template_architecture(
        presentation_architecture=presentation_architecture,
        slide_blueprints=slide_blueprints,
        editable_template_spec=editable_template_spec,
        deck_assembly_plan=deck_assembly_plan,
    )
    sidecars = build_slide_semantic_sidecars(
        presentation_architecture=presentation_architecture,
        creative_template_architecture=creative_template_architecture,
        slide_blueprints=slide_blueprints,
        deck_assembly_plan=deck_assembly_plan,
        editable_template_spec=editable_template_spec,
    )

    paths = {
        "presentation_architecture": output / "presentation_architecture.json",
        "creative_template_architecture": output / "creative_template_architecture.json",
        "deck_assembly_plan": output / "deck_assembly_plan.json",
        "semantic_sidecar_dir": output / "semantic_sidecars",
        "manifest": output / "creative_frontend_manifest.json",
    }
    _write_json(paths["presentation_architecture"], presentation_architecture)
    _write_json(paths["creative_template_architecture"], creative_template_architecture)
    _write_json(paths["deck_assembly_plan"], deck_assembly_plan)
    paths["semantic_sidecar_dir"].mkdir(parents=True, exist_ok=True)
    sidecar_paths: list[str] = []
    for sidecar in sidecars:
        sidecar_path = paths["semantic_sidecar_dir"] / f"{sidecar['slide_id']}.semantic.json"
        _write_json(sidecar_path, sidecar)
        sidecar_paths.append(_display_path(sidecar_path))

    status_counts = Counter(decision["status"] for decision in creative_template_architecture["slide_fit_decisions"])
    non_pass_count = sum(count for status, count in status_counts.items() if status != "pass")
    manifest_status = "blocked" if status_counts.get("blocked") else "needs_revision" if non_pass_count else "ready"
    manifest = {
        "schema_name": "creative_frontend_manifest",
        "schema_version": SCHEMA_VERSION,
        "status": manifest_status,
        "deck_id": presentation_architecture["deck_id"],
        "primary_compile_route": "editable_template",
        "raw_png_backend_role": "optional_external_or_legacy_png_reconstruction_only",
        "template_reference_generation_scope": "template_references_only",
        "adapter_used": adapter_used,
        "artifacts": {
            "presentation_architecture": _display_path(paths["presentation_architecture"]),
            "creative_template_architecture": _display_path(paths["creative_template_architecture"]),
            "deck_assembly_plan": _display_path(paths["deck_assembly_plan"]),
            "semantic_sidecars": sidecar_paths,
        },
        "summary": {
            "module_count": len(presentation_architecture["modules"]),
            "batch_count": sum(len(module["batches"]) for module in presentation_architecture["modules"]),
            "slide_count": len(presentation_architecture["slides"]),
            "semantic_sidecar_count": len(sidecars),
            "fit_status_counts": dict(sorted(status_counts.items())),
        },
        "validation": {
            "presentation_architecture": "pass",
            "creative_template_architecture": "pass",
            "deck_assembly_plan": "pass",
            "semantic_sidecars": "pass",
            "template_policy_no_full_slide_raster": "pass",
        },
    }
    _write_json(paths["manifest"], manifest)
    return {"paths": paths, "manifest": manifest, "sidecars": sidecars}


def run_creative_frontend_from_files(
    *,
    presentation_plan_path: str | Path,
    slide_blueprint_path: str | Path,
    design_brief_path: str | Path,
    template_spec_path: str | Path,
    output_dir: str | Path,
    template_spec_format: str = "canonical",
    reference_design_system_path: str | Path | None = None,
    max_batch_size: int = 5,
) -> dict[str, Any]:
    presentation_plan = _load_json(presentation_plan_path)
    slide_blueprints = _load_json(slide_blueprint_path)
    design_brief = _load_json(design_brief_path)
    raw_template_spec = _load_json(template_spec_path)
    adapter_used = template_spec_format == TEMPLATE_REFERENCE_INPUT_FORMAT
    if adapter_used:
        if reference_design_system_path is None:
            raise ValueError(
                "--reference-design-system is required for "
                f"--template-spec-format {TEMPLATE_REFERENCE_INPUT_FORMAT}"
            )
        editable_template_spec = adapt_image_template_spec(raw_template_spec, _load_json(reference_design_system_path))
        canonical_spec_path = Path(output_dir) / "canonical_template_spec.json"
        _write_json(canonical_spec_path, editable_template_spec)
        effective_template_path = _display_path(canonical_spec_path)
    elif template_spec_format == "canonical":
        editable_template_spec = raw_template_spec
        effective_template_path = _display_path(Path(template_spec_path))
    else:
        raise ValueError(f"template_spec_format must be canonical or {TEMPLATE_REFERENCE_INPUT_FORMAT}")
    return run_creative_frontend(
        presentation_plan=presentation_plan,
        slide_blueprints=slide_blueprints,
        design_brief=design_brief,
        editable_template_spec=editable_template_spec,
        output_dir=output_dir,
        source_plan_path=_display_path(Path(presentation_plan_path)),
        source_blueprint_path=_display_path(Path(slide_blueprint_path)),
        template_spec_path=effective_template_path,
        max_batch_size=max_batch_size,
        adapter_used=adapter_used,
    )


def _fit_decision(
    *,
    slide: dict[str, Any],
    architecture_slide: dict[str, Any],
    binding: dict[str, Any],
    layout: dict[str, Any] | None,
    editable_template_spec: dict[str, Any],
    previous_layout_id: str | None,
    previous_family_id: str | None,
    layout_run_length: int,
    family_run_length: int,
) -> dict[str, Any]:
    layout_id = str(binding.get("selected_layout_id") or binding.get("layout_id") or "NO_LAYOUT")
    family_id = str(binding.get("layout_family_id") or "NO_FAMILY")
    reasons: list[str] = []
    next_actions: list[str] = []
    blocked = layout is None or bool(binding.get("failure_reason"))
    if blocked:
        scores = {"semantic": 0.0, "capacity": 0.0, "editability": 0.0, "differentiation": 0.0}
        overall = 0.0
        status = "blocked"
        reasons.append("No compiler-ready editable layout was selected.")
        next_actions.append("Add or repair an editable template family before compilation.")
    else:
        required_slots = _unique_strings(slide.get("required_slots") or [])
        covered = sum(1 for slot_id in required_slots if _layout_covers(layout, slot_id))
        semantic = covered / max(1, len(required_slots))
        overflow_count = len(binding.get("content_overflow_warnings") or [])
        capacity = max(0.2, 1.0 - 0.22 * overflow_count)
        editability = _editability_score(layout, required_slots, editable_template_spec)
        if previous_layout_id == layout_id:
            differentiation = 0.45
        elif previous_family_id == family_id:
            differentiation = 0.72
        else:
            differentiation = 1.0
        scores = {
            "semantic": round(semantic, 4),
            "capacity": round(capacity, 4),
            "editability": round(editability, 4),
            "differentiation": round(differentiation, 4),
        }
        overall = round(sum(scores[key] * FIT_WEIGHTS[key] for key in FIT_WEIGHTS), 4)
        missing_slots = [slot_id for slot_id in required_slots if not _layout_covers(layout, slot_id)]
        if missing_slots or editability < 1.0:
            status = "expand_template_family"
            reasons.append("Selected family does not cover every required editable semantic slot.")
            if missing_slots:
                reasons.append("Missing slots: " + ", ".join(missing_slots))
            next_actions.append("Generate or select another template reference archetype, then adapt it to the canonical spec.")
        elif overflow_count or capacity < 0.8:
            status = "recompose_content"
            reasons.append("Content volume exceeds the selected layout capacity signal.")
            next_actions.append("Shorten secondary copy or move lookup-heavy detail to an appendix slide.")
        elif layout_run_length > MAX_CONSECUTIVE_LAYOUT or family_run_length > MAX_CONSECUTIVE_FAMILY:
            status = "recompose_content"
            reasons.append(
                "Layout/family repetition exceeds the hard creative-rhythm limit "
                f"(layout run {layout_run_length}, family run {family_run_length})."
            )
            next_actions.append("Rotate to another approved layout or family before compilation.")
        elif overall < FIT_PASS_THRESHOLD:
            status = "recompose_content"
            reasons.append("Overall fit is below the deterministic pass threshold, primarily due to repetition.")
            next_actions.append("Rotate to another approved family or vary the focal composition within this batch.")
        else:
            status = "pass"
            reasons.append("Semantic slots, capacity, editability, and module differentiation meet the fit policy.")
    return {
        "slide_id": str(slide["slide_id"]),
        "module_id": architecture_slide["module_id"],
        "batch_id": architecture_slide["batch_id"],
        "layout_id": layout_id,
        "template_family_id": family_id,
        "scores": scores,
        "overall_score": overall,
        "status": status,
        "reasons": reasons,
        "next_actions": next_actions,
    }


def _global_visual_dna(editable_template_spec: dict[str, Any]) -> dict[str, Any]:
    tokens = editable_template_spec.get("tokens") or {}
    return {
        "invariants": [
            "Use editable text boxes for all real slide copy.",
            "Keep tables and charts native and data-backed.",
            "Use explicit slot binding and stable reading order.",
            "Preserve title hierarchy, safe margins, citations, and slide numbering.",
            "Allow module-specific art direction without changing semantic truth.",
        ],
        "color_roles": sorted(str(key) for key in (tokens.get("colors") or {}).keys()),
        "typography_roles": sorted(str(key) for key in (tokens.get("typography") or {}).keys()),
        "allowed_raster_roles": ["photo", "source_figure", "replaceable_image_frame"],
        "forbidden_raster_roles": ["full_slide_background", "text", "table", "chart", "card", "footer"],
    }


def _candidate_families(selected: list[str], all_family_ids: list[str], slides: list[dict[str, Any]]) -> list[str]:
    candidates = list(selected)
    needs = {_need for slide in slides for _need in _slide_needs(slide)}
    ranked = sorted(
        all_family_ids,
        key=lambda family_id: (
            -sum(1 for need in needs if need in family_id.lower()),
            family_id,
        ),
    )
    for family_id in ranked:
        if family_id not in candidates:
            candidates.append(family_id)
        if len(candidates) >= 4:
            break
    return candidates or ["unassigned_board_family"]


def _template_family_ids(editable_template_spec: dict[str, Any]) -> list[str]:
    family_ids = [
        str(family.get("family_id"))
        for family in editable_template_spec.get("layout_families") or []
        if isinstance(family, dict) and family.get("family_id")
    ]
    family_ids.extend(
        str(layout.get("layout_family_id"))
        for layout in editable_template_spec.get("layouts") or []
        if isinstance(layout, dict) and layout.get("layout_family_id")
    )
    return _unique_strings(family_ids) or ["unassigned_board_family"]


def _module_art_direction(module: dict[str, Any], slides: list[dict[str, Any]], bindings: list[dict[str, Any]]) -> str:
    needs = Counter(need for slide in slides for need in _slide_needs(slide))
    dominant = needs.most_common(1)[0][0] if needs else "text"
    family_count = len({binding.get("layout_family_id") for binding in bindings if binding.get("layout_family_id")})
    direction = {
        "chart": "evidence-forward quantitative composition with direct labels and restrained ornament",
        "table": "academic lookup composition with strong row hierarchy and calm comparison rhythm",
        "process": "systems-oriented composition with directional flow and explicit connectors",
        "timeline": "sequential editorial composition with a visible temporal spine",
        "photo": "source-grounded editorial composition using replaceable image frames",
        "cards": "modular comparison composition with bounded card count and varied focal weight",
    }.get(dominant, "editorial evidence composition with a single dominant claim and generous whitespace")
    return f"{module['title']}: {direction}; rotate across {max(1, family_count)} approved family/families without changing the global visual DNA."


def _differentiation_signature(module_index: int, slides: list[dict[str, Any]], bindings: list[dict[str, Any]]) -> list[str]:
    needs = _unique_strings(need for slide in slides for need in _slide_needs(slide))
    families = _unique_strings(binding.get("layout_family_id") for binding in bindings if binding.get("layout_family_id"))
    return _unique_strings(
        [
            f"module-accent-rotation-{((module_index - 1) % 4) + 1}",
            f"dominant-needs-{'+'.join(needs[:3]) if needs else 'text'}",
            f"family-set-{'+'.join(families[:3]) if families else 'unassigned'}",
        ]
    )


def _reference_brief(module: dict[str, Any], batch: dict[str, Any], slides: list[dict[str, Any]], candidates: list[str]) -> str:
    needs = _unique_strings(need for slide in slides for need in _slide_needs(slide))
    return (
        f"Create separate editable-template reference archetypes for {module['title']} / {batch['batch_id']}; "
        f"support {', '.join(needs[:4]) or 'text'} using families {', '.join(candidates[:3])}. "
        "Use placeholder labels only as semantic slot indicators; do not render final slide copy or a full-slide raster background."
    )


def _canonical_content(slide: dict[str, Any]) -> list[dict[str, Any]]:
    content: list[dict[str, Any]] = [{"slot_id": "title", "kind": "text", "value": str(slide.get("title") or "")}]
    if str(slide.get("subtitle") or "").strip():
        content.append({"slot_id": "subtitle", "kind": "text", "value": str(slide["subtitle"])})
    for block in slide.get("content_blocks") or []:
        if not isinstance(block, dict):
            continue
        kind = _content_kind(str(block.get("type") or "structured"))
        content.append(
            {
                "slot_id": _key(block.get("slot") or block.get("block_id") or "body"),
                "kind": kind,
                "value": block.get("content"),
            }
        )
    if isinstance(slide.get("chart_data"), dict):
        content.append({"slot_id": "chart", "kind": "chart", "value": slide["chart_data"]})
    if isinstance(slide.get("table_data"), dict):
        content.append({"slot_id": "table", "kind": "table", "value": slide["table_data"]})
    for image_need in slide.get("image_needs") or []:
        if isinstance(image_need, dict):
            content.append({"slot_id": _key(image_need.get("slot") or "image"), "kind": "image_need", "value": image_need})
    if slide.get("citations"):
        content.append({"slot_id": "footer", "kind": "citation", "value": slide["citations"]})
    if str(slide.get("speaker_notes") or "").strip():
        content.append(
            {
                "slot_id": "speaker_notes",
                "kind": "speaker_notes",
                "value": str(slide["speaker_notes"]),
            }
        )
    return content


def _native_requirements(
    slide: dict[str, Any],
    content: list[dict[str, Any]],
    layout: dict[str, Any] | None,
) -> list[dict[str, str]]:
    requirements: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in content:
        if item["kind"] == "image_need":
            continue
        slot_id = _key(item["slot_id"])
        object_type = {
            "chart": "chart",
            "table": "table",
            "citation": "footer",
            "kpi": "shape",
            "speaker_notes": "speaker_notes",
        }.get(item["kind"], _native_object_type_for_slot(slot_id, layout))
        key = (slot_id, object_type)
        if key not in seen:
            seen.add(key)
            requirements.append({"slot_id": slot_id, "object_type": object_type})
    for required_slot in slide.get("required_slots") or []:
        raw_slot_id = _key(required_slot)
        if any(existing_slot == raw_slot_id for existing_slot, _ in seen):
            continue
        slot_id = _canonical_native_slot_id(raw_slot_id)
        if slot_id in {"image", "photo", "hero_image", "photo_frame"}:
            continue
        object_type = _native_object_type_for_slot(slot_id, layout)
        key = (slot_id, object_type)
        if key not in seen:
            seen.add(key)
            requirements.append({"slot_id": slot_id, "object_type": object_type})
    if _key(slide.get("slide_type")) in {"process", "process_timeline", "timeline", "timeline_roadmap", "technical_flow_chart"}:
        key = ("connector", "connector")
        if key not in seen:
            requirements.append({"slot_id": "connector", "object_type": "connector"})
    return requirements


def _canonical_native_slot_id(slot_id: Any) -> str:
    """Collapse semantic aliases that refer to the same editable native object."""

    normalized = _key(slot_id)
    return {
        "section_title": "title",
        "headline": "title",
        "primary_chart": "chart",
        "matrix": "table",
        "citations": "footer",
        "metric_panels": "kpi",
    }.get(normalized, normalized)


def _native_object_type_for_slot(slot_id: str, layout: dict[str, Any] | None) -> str:
    explicit = NATIVE_OBJECT_TYPES.get(slot_id)
    if explicit:
        return explicit
    if layout:
        matching = [slot for slot in layout.get("slots") or [] if _slot_matches(slot, slot_id)]
        if matching:
            slot_type = _key(matching[0].get("slot_type"))
            return {
                "text": "text_box",
                "footer": "footer",
                "table": "table",
                "chart": "chart",
                "icon": "svg_icon",
                "image": "shape",
                "content": "shape",
                "shape": "shape",
            }.get(slot_type, "shape")
    if any(token in slot_id for token in ("diagram", "process", "timeline", "flow", "map", "framework", "visual")):
        return "shape"
    if any(token in slot_id for token in ("card", "panel", "callout", "kpi", "metric")):
        return "shape"
    return "text_box"


def _raster_allowances(slide: dict[str, Any]) -> list[dict[str, str]]:
    allowances: list[dict[str, str]] = []
    for image_need in slide.get("image_needs") or []:
        if not isinstance(image_need, dict):
            continue
        source_policy = str(image_need.get("source_policy") or "").lower()
        usage = "source_figure" if "source" in source_policy or "figure" in source_policy else "replaceable_image_frame"
        allowances.append({"slot_id": _key(image_need.get("slot") or "image"), "usage": usage})
    return allowances


def _sidecar_source_bindings(architecture_slide: dict[str, Any]) -> list[dict[str, Any]]:
    grouped: dict[str, set[str]] = defaultdict(set)
    for binding in architecture_slide.get("source_bindings") or []:
        grouped[str(binding["slot_id"])].add(str(binding["evidence_id"]))
    return [
        {"element": element, "evidence_ids": sorted(evidence_ids)}
        for element, evidence_ids in sorted(grouped.items())
        if evidence_ids
    ]


def _validate_sidecar_policy(sidecar: dict[str, Any], binding: dict[str, Any]) -> None:
    forbidden = {"background", "full_slide", "full_slide_background", "slide"}
    for allowance in sidecar["raster_allowed"]:
        if _key(allowance["slot_id"]) in forbidden:
            raise ValueError(f"{sidecar['slide_id']}: full-slide/background raster allowance is forbidden")
    native_slots = {item["slot_id"] for item in sidecar["native_required"]}
    raster_slots = {allowance["slot_id"] for allowance in sidecar["raster_allowed"]}
    conflicts = sorted(native_slots & raster_slots)
    if conflicts:
        raise ValueError(
            f"{sidecar['slide_id']}: semantic slots cannot be both native-required and raster-allowed: "
            f"{', '.join(conflicts)}"
        )
    if "title" not in native_slots:
        raise ValueError(f"{sidecar['slide_id']}: title must remain a native text object")
    if binding.get("failure_reason"):
        raise ValueError(f"{sidecar['slide_id']}: cannot bind semantic truth to a failed layout")


def _editability_score(layout: dict[str, Any], required_slots: list[str], spec: dict[str, Any]) -> float:
    components = {component["component_id"]: component for component in spec.get("components") or []}
    if not required_slots:
        return 1.0
    passed = 0
    for required_slot in required_slots:
        matching = [slot for slot in layout.get("slots") or [] if _slot_matches(slot, required_slot)]
        if not matching:
            continue
        if any(bool(components.get(slot.get("component_id"), {}).get("editable", True)) for slot in matching):
            passed += 1
    return passed / len(required_slots)


def _layout_covers(layout: dict[str, Any], required_slot: str) -> bool:
    return any(_slot_matches(slot, required_slot) for slot in layout.get("slots") or [])


def _slot_matches(slot: dict[str, Any], required_slot: str) -> bool:
    required = _key(required_slot)
    slot_id = _key(slot.get("slot_id"))
    slot_type = _key(slot.get("slot_type"))
    aliases = {
        "title": {"title", "section_title", "headline"},
        "section_title": {"title", "section_title", "headline"},
        "body": {"body", "content", "cards", "insight", "case_context", "case_evidence"},
        "claim": {"body", "content", "insight", "claim"},
        "chart": {"chart", "primary_chart", "secondary_chart"},
        "primary_chart": {"chart", "primary_chart"},
        "table": {"table", "matrix"},
        "matrix": {"table", "matrix"},
        "image": {"image", "photo_frame", "hero_image"},
        "photo": {"image", "photo_frame", "hero_image"},
        "kpi": {"kpi", "metric_panels"},
        "metric_panels": {"kpi", "metric_panels"},
        "cards": {"cards", "card_group"},
        "footer": {"footer"},
    }
    structural_types = {slot_type} if slot_type in {"chart", "table", "image", "footer", "icon"} else set()
    candidates = {slot_id, *structural_types}
    return required in candidates or bool(aliases.get(required, set()) & candidates)


def _evidence_for_slide(slide: dict[str, Any], evidence_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    slide_id = str(slide["slide_id"])
    bindings: list[dict[str, Any]] = []
    for index, citation in enumerate(slide.get("citations") or [], start=1):
        if not isinstance(citation, dict):
            continue
        evidence_id = str(citation.get("citation_id") or f"ev-{_key(slide_id)}-citation-{index:02d}")
        _record_evidence(
            evidence_by_id,
            evidence_id=evidence_id,
            kind="citation",
            label=str(citation.get("label") or evidence_id),
            source=citation.get("source"),
            slide_id=slide_id,
        )
        bindings.append({"evidence_id": evidence_id, "slot_id": "footer", "label": str(citation.get("label") or evidence_id), "source": citation.get("source")})
    if isinstance(slide.get("chart_data"), dict):
        evidence_id = f"ev-{_key(slide_id)}-chart"
        source = _data_evidence_source(slide, slide["chart_data"])
        _record_evidence(evidence_by_id, evidence_id=evidence_id, kind="chart_data", label=f"Chart data for {slide_id}", source=source, slide_id=slide_id)
        bindings.append({"evidence_id": evidence_id, "slot_id": "chart", "label": f"Chart data for {slide_id}", "source": source})
    if isinstance(slide.get("table_data"), dict):
        evidence_id = f"ev-{_key(slide_id)}-table"
        source = _data_evidence_source(slide, slide["table_data"])
        _record_evidence(evidence_by_id, evidence_id=evidence_id, kind="table_data", label=f"Table data for {slide_id}", source=source, slide_id=slide_id)
        bindings.append({"evidence_id": evidence_id, "slot_id": "table", "label": f"Table data for {slide_id}", "source": source})
    for index, image_need in enumerate(slide.get("image_needs") or [], start=1):
        if not isinstance(image_need, dict):
            continue
        evidence_id = f"ev-{_key(slide_id)}-asset-{index:02d}"
        label = str(image_need.get("purpose") or f"Source asset {index}")
        _record_evidence(evidence_by_id, evidence_id=evidence_id, kind="source_asset", label=label, source=image_need.get("source_policy"), slide_id=slide_id)
        bindings.append({"evidence_id": evidence_id, "slot_id": _key(image_need.get("slot") or "image"), "label": label, "source": image_need.get("source_policy")})
    return bindings


def _data_evidence_source(slide: dict[str, Any], data_payload: dict[str, Any]) -> Any:
    for key in ("source", "source_path", "source_id", "source_ref"):
        if data_payload.get(key):
            return data_payload[key]
    citation_sources = {
        str(citation.get("source"))
        for citation in slide.get("citations") or []
        if isinstance(citation, dict) and citation.get("source")
    }
    if len(citation_sources) == 1:
        return next(iter(citation_sources))
    return None


def _record_evidence(
    evidence_by_id: dict[str, dict[str, Any]],
    *,
    evidence_id: str,
    kind: str,
    label: str,
    source: Any,
    slide_id: str,
) -> None:
    normalized_source = str(source) if source else None
    record = evidence_by_id.setdefault(
        evidence_id,
        {"evidence_id": evidence_id, "kind": kind, "label": label, "source": normalized_source, "slide_ids": []},
    )
    if (record["kind"], record["label"], record.get("source")) != (kind, label, normalized_source):
        raise ValueError(
            f"evidence id {evidence_id} is reused with incompatible provenance: "
            f"expected ({record['kind']}, {record['label']}, {record.get('source')}), "
            f"got ({kind}, {label}, {normalized_source})"
        )
    if slide_id not in record["slide_ids"]:
        record["slide_ids"].append(slide_id)


def _semantic_intent(slide: dict[str, Any]) -> str:
    design_intent = slide.get("design_intent")
    if isinstance(design_intent, str) and design_intent.strip():
        return design_intent.strip()
    return f"Communicate {slide.get('title') or slide.get('slide_id')} with source-backed editable content."


def _module_narrative_role(slides: list[dict[str, Any]], index: int, total: int) -> str:
    types = {_key(slide.get("slide_type")) for slide in slides}
    if index == 1 or types & {"cover", "title", "agenda", "visual_toc"}:
        return "orientation"
    if index == total or types & {"closing", "recommendation", "summary"}:
        return "synthesis_and_close"
    if types & {"data_dashboard", "table_heavy", "evidence", "comparison_matrix"}:
        return "evidence_and_analysis"
    if types & {"process", "process_timeline", "methodology_framework"}:
        return "method_and_mechanism"
    return "narrative_development"


def _slide_needs(slide: dict[str, Any]) -> list[str]:
    needs: list[str] = []
    required = {_key(item) for item in slide.get("required_slots") or []}
    if slide.get("chart_data") or "chart" in required:
        needs.append("chart")
    if slide.get("table_data") or "table" in required:
        needs.append("table")
    if slide.get("image_needs") or required & {"image", "photo", "hero_image"}:
        needs.append("photo")
    slide_type = _key(slide.get("slide_type"))
    if "timeline" in slide_type:
        needs.append("timeline")
    if "process" in slide_type or "flow" in slide_type:
        needs.append("process")
    if "card" in slide_type or "cards" in required:
        needs.append("cards")
    if not needs:
        needs.append("text")
    return _unique_strings(needs)


def _content_kind(value: str) -> str:
    normalized = _key(value)
    if normalized in {"bullet", "bullets", "list"}:
        return "bullets"
    if normalized in {"kpi", "metric", "metrics"}:
        return "kpi"
    if normalized in {"text", "paragraph", "quote"}:
        return "text"
    return "structured"


def _content_hash(content: list[dict[str, Any]], source_bindings: list[dict[str, Any]]) -> str:
    payload = json.dumps({"canonical_content": content, "source_bindings": source_bindings}, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _stable_id(prefix: str, *parts: Any) -> str:
    payload = json.dumps(parts, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return f"{prefix}-{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:16]}"


def _normalize_slides(payload: dict[str, Any] | list[dict[str, Any]]) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("slides"), list):
        return payload["slides"]
    if isinstance(payload, dict) and payload.get("slide_id"):
        return [payload]
    raise ValueError("slide_blueprints must be a list, a {slides:[...]} object, or one slide_blueprint")


def _unique_strings(values: Any) -> list[str]:
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in result:
            result.append(text)
    return result


def _key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_") or "unnamed"


def _load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_json(path: str | Path, payload: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def _display_path(path: Path) -> str:
    return path.as_posix()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build Module/Batch/Slide creative-template and semantic handoff artifacts.")
    parser.add_argument("--presentation-plan", type=Path, required=True)
    parser.add_argument("--slide-blueprints", type=Path, required=True)
    parser.add_argument("--design-brief", type=Path, required=True)
    parser.add_argument("--template-spec", type=Path, required=True)
    parser.add_argument(
        "--template-spec-format",
        choices=["canonical", TEMPLATE_REFERENCE_INPUT_FORMAT],
        default="canonical",
    )
    parser.add_argument("--reference-design-system", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--max-batch-size", type=int, default=5)
    parser.add_argument(
        "--allow-needs-revision",
        action="store_true",
        help="Diagnostic escape hatch: return success after writing artifacts even when fit actions remain.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = run_creative_frontend_from_files(
            presentation_plan_path=args.presentation_plan,
            slide_blueprint_path=args.slide_blueprints,
            design_brief_path=args.design_brief,
            template_spec_path=args.template_spec,
            output_dir=args.output_dir,
            template_spec_format=args.template_spec_format,
            reference_design_system_path=args.reference_design_system,
            max_batch_size=args.max_batch_size,
        )
    except Exception as exc:
        print(f"CREATIVE_FRONTEND_FAILED {exc}")
        return 1
    print(f"WROTE {result['paths']['manifest']}")
    status = result["manifest"]["status"]
    if status == "blocked":
        print("CREATIVE_FRONTEND_BLOCKED")
        return 1
    if status == "needs_revision" and not args.allow_needs_revision:
        print("CREATIVE_FRONTEND_NEEDS_REVISION")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
