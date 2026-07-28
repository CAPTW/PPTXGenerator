"""Helpers for loading Gate 2 inputs, including optional reference_dna guidance."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field

from ..compat.legacy_non_pptx import ContractModel, ReferenceDNA, WorkflowPlan, load_state_file
from ..reference_confidence import build_reference_guidance_payload, reference_dna_for_design_guidance, summarize_reference_scan_confidence


class Gate2ReferenceGuidance(ContractModel):
    available: bool = False
    confidence_tier: str | None = None
    accepted_for_design_guidance: bool = False
    policy_action: str | None = None
    confidence_reason_codes: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    source_family: str | None = None
    patterns_worth_borrowing: list[str] = Field(default_factory=list)
    patterns_to_avoid: list[str] = Field(default_factory=list)
    layout_logic: list[str] = Field(default_factory=list)
    hierarchy_behavior: list[str] = Field(default_factory=list)
    whitespace_behavior: list[str] = Field(default_factory=list)
    section_divider_style: str | None = None
    fit_assessment: str | None = None


class Gate2Context(ContractModel):
    workflow_plan: WorkflowPlan
    reference_dna: ReferenceDNA | None = None
    reference_guidance: Gate2ReferenceGuidance


def _expect_workflow_plan(path: str | Path) -> WorkflowPlan:
    model = load_state_file(path)
    if not isinstance(model, WorkflowPlan):
        raise TypeError(f"expected workflow_plan at {path}, found {model.schema_name}")
    return model


def _load_reference_dna(path: str | Path | None) -> ReferenceDNA | None:
    if path is None:
        return None
    candidate = Path(path)
    if not candidate.exists():
        return None
    model = load_state_file(candidate)
    if not isinstance(model, ReferenceDNA):
        raise TypeError(f"expected reference_dna at {path}, found {model.schema_name}")
    return model


def load_gate2_context(
    workflow_plan_path: str | Path,
    reference_dna_path: str | Path | None = None,
) -> Gate2Context:
    workflow_plan = _expect_workflow_plan(workflow_plan_path)
    scanned_reference_dna = _load_reference_dna(reference_dna_path)
    reference_confidence = summarize_reference_scan_confidence(scanned_reference_dna)
    reference_dna = reference_dna_for_design_guidance(scanned_reference_dna, reference_confidence)

    if scanned_reference_dna is None:
        guidance = Gate2ReferenceGuidance()
    else:
        guidance = Gate2ReferenceGuidance(**build_reference_guidance_payload(scanned_reference_dna, reference_confidence))

    return Gate2Context(
        workflow_plan=workflow_plan,
        reference_dna=reference_dna,
        reference_guidance=guidance,
    )

