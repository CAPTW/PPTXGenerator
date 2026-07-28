"""Cross-artifact validation for Phase 3 planning and architecture outputs."""

from __future__ import annotations

from typing import Any

from ...generator_contracts import validateCreativeTemplateArchitecture, validatePresentationArchitecture
from ..intake.multi_source import IntakeArtifacts
from ..planning.strict_adapter import StrictPlanningArtifacts


def validate_phase3_architecture_graph(
    intake: IntakeArtifacts,
    planning: StrictPlanningArtifacts,
    architecture: Any,
) -> None:
    presentation = architecture.presentation_architecture
    creative = architecture.creative_template_architecture
    validatePresentationArchitecture(presentation)
    validateCreativeTemplateArchitecture(creative)
    expected_slide_ids = planning.evidence_allocation_report["ordered_slide_ids"]
    actual_slide_ids = [slide["slide_id"] for slide in presentation["slides"]]
    creative_slide_ids = [item["slide_id"] for item in creative["slide_fit_decisions"]]
    if actual_slide_ids != expected_slide_ids or creative_slide_ids != expected_slide_ids:
        raise ValueError("DC_SLIDE_ORDER_MISMATCH: blueprint, presentation, and creative slide order must match")
    known_evidence = {item["evidence_id"] for item in intake.evidence_unit_registry["evidence_units"]}
    for slide in presentation["slides"]:
        unknown = set(slide["evidence_ids"]) - known_evidence
        if unknown:
            raise ValueError(f"DC_UNKNOWN_EVIDENCE_REFERENCE: {', '.join(sorted(unknown))}")
    module_ids = {module["module_id"] for module in presentation["modules"]}
    batch_ids = {batch["batch_id"] for module in presentation["modules"] for batch in module["batches"]}
    if len(module_ids) != len(presentation["modules"]):
        raise ValueError("DC_ARCHITECTURE_GROUPING_INVALID: duplicate module ID")
    if len(batch_ids) != sum(len(module["batches"]) for module in presentation["modules"]):
        raise ValueError("DC_ARCHITECTURE_GROUPING_INVALID: duplicate batch ID")
    assignments = [slide_id for module in presentation["modules"] for slide_id in module["slide_ids"]]
    if assignments != expected_slide_ids:
        raise ValueError("DC_ORPHAN_SLIDE: modules must cover every slide exactly once and in order")
    art_module_ids = {item["module_id"] for item in architecture.module_art_directions["modules"]}
    creative_module_ids = {item["module_id"] for item in creative["modules"]}
    if art_module_ids != module_ids or creative_module_ids != module_ids:
        raise ValueError("DC_MISSING_MODULE_ART_DIRECTION: module directions must cover every module")
    if architecture.architecture_validation_report["orphan_slide_ids"]:
        raise ValueError("DC_ORPHAN_SLIDE: architecture validation report contains orphan slides")
    if not architecture.architecture_validation_report["module_ranges_contiguous"]:
        raise ValueError("DC_NONCONTIGUOUS_MODULE: module ranges must be contiguous")
    if not architecture.architecture_validation_report["batch_ranges_contiguous"]:
        raise ValueError("DC_NONCONTIGUOUS_BATCH: batch ranges must be contiguous")


__all__ = ["validate_phase3_architecture_graph"]
