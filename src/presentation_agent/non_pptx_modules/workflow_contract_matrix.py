"""Central workflow-family contract and conformance rules."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Callable

from pydantic import ValidationError

from .shared_proof_registry import shared_proof_consumer_policy
from ..compat.legacy_non_pptx import (
    Blueprint,
    ContentPlanConformance,
    ContentPlanConformanceStatus,
    DeckMode,
    ProofCoverageClass,
    ProofModuleManifest,
    ProofModuleStatus,
    ProofUnitRegistry,
    SlideRole,
    WorkflowOption,
    WorkflowOptionContractStatus,
    WorkflowOptionProvenance,
    WorkflowOptionResolutionCode,
    WorkflowOptionSelectionMode,
    WorkflowPlan,
    proof_module_manifest_from_proof_unit_registry,
    proof_unit_registry_from_proof_module_manifest,
)


WORKFLOW_CONTRACT_MATRIX_VERSION = "2026-04-02"
WORKFLOW_CONTRACT_MATRIX_POLICY_ID = f"workflow-contract-matrix@{WORKFLOW_CONTRACT_MATRIX_VERSION}"

ConformanceEvaluation = tuple[list[str], list[str], list[str]]
WorkflowConformanceValidator = Callable[[Blueprint, ProofModuleManifest | None, ProofUnitRegistry | None], ConformanceEvaluation]


class WorkflowFamilyContractState(StrEnum):
    CONTRACTABLE = "contractable"
    NOT_CONTRACTABLE = "not-contractable"


class SharedProofArtifactReadiness(StrEnum):
    CURRENT_DIRECT_CONSUMER = "current-direct-consumer"
    LIKELY_FUTURE_CONSUMER = "likely-future-consumer"
    BLOCKED_UNTIL_GATE2_PROOF_STRUCTURE = "blocked-until-gate2-proof-structure"
    UNLIKELY_SHARED_PROOF_CONSUMER = "unlikely-shared-proof-consumer"


@dataclass(frozen=True, slots=True)
class WorkflowFamilyContract:
    option_id: str
    contract_state: WorkflowFamilyContractState
    explanation: str
    shared_proof_artifact_readiness: SharedProofArtifactReadiness
    shared_proof_artifact_notes: tuple[str, ...]
    required_sections: tuple[str, ...] = ()
    required_main_story_roles: tuple[str, ...] = ()
    minimum_appendix_slides: int = 0
    minimum_story_sections: int = 0
    maximum_story_sections: int | None = None
    require_lecture_family: bool = False
    require_clustering_decisions: bool = False
    conformance_rule_ids: tuple[str, ...] = ()
    budget_rule_ids: tuple[str, ...] = ()
    provenance_expectations: tuple[str, ...] = ()
    deterministic_fixture_expectations: tuple[str, ...] = ()
    reason_code: str | None = None
    next_step_requirements: tuple[str, ...] = ()
    custom_validator: WorkflowConformanceValidator | None = None

    @property
    def policy_id(self) -> str:
        return f"{WORKFLOW_CONTRACT_MATRIX_POLICY_ID}:{self.option_id}"

    @property
    def supports_explicit_contract(self) -> bool:
        return self.contract_state == WorkflowFamilyContractState.CONTRACTABLE

    def completeness_errors(self) -> tuple[str, ...]:
        errors: list[str] = []
        if not self.option_id.strip():
            errors.append("option_id must be non-empty")
        if not self.explanation.strip():
            errors.append("explanation must be non-empty")
        if not self.shared_proof_artifact_notes:
            errors.append("shared_proof_artifact_notes must be non-empty")
        if self.minimum_appendix_slides < 0:
            errors.append("minimum_appendix_slides cannot be negative")
        if self.minimum_story_sections < 0:
            errors.append("minimum_story_sections cannot be negative")
        if self.maximum_story_sections is not None and self.maximum_story_sections < 1:
            errors.append("maximum_story_sections must be at least 1 when provided")

        if self.supports_explicit_contract:
            if not self.required_sections:
                errors.append("contractable families require required_sections")
            if not self.required_main_story_roles:
                errors.append("contractable families require required_main_story_roles")
            if not self.conformance_rule_ids:
                errors.append("contractable families require conformance_rule_ids")
            if not self.budget_rule_ids:
                errors.append("contractable families require budget_rule_ids")
            if not self.provenance_expectations:
                errors.append("contractable families require provenance_expectations")
            if not self.deterministic_fixture_expectations:
                errors.append("contractable families require deterministic_fixture_expectations")
            if self.reason_code is not None:
                errors.append("contractable families cannot define reason_code")
            if self.next_step_requirements:
                errors.append("contractable families cannot define next_step_requirements")
        else:
            if self.reason_code is None or not self.reason_code.strip():
                errors.append("not-contractable families require reason_code")
            if not self.next_step_requirements:
                errors.append("not-contractable families require next_step_requirements")
            if self.required_sections:
                errors.append("not-contractable families cannot define required_sections")
            if self.required_main_story_roles:
                errors.append("not-contractable families cannot define required_main_story_roles")
            if self.minimum_appendix_slides:
                errors.append("not-contractable families cannot define minimum_appendix_slides")
            if self.minimum_story_sections:
                errors.append("not-contractable families cannot define minimum_story_sections")
            if self.maximum_story_sections is not None:
                errors.append("not-contractable families cannot define maximum_story_sections")
            if self.require_lecture_family:
                errors.append("not-contractable families cannot require lecture_family")
            if self.require_clustering_decisions:
                errors.append("not-contractable families cannot require clustering_decisions")
            if self.conformance_rule_ids:
                errors.append("not-contractable families cannot define conformance_rule_ids")
            if self.budget_rule_ids:
                errors.append("not-contractable families cannot define budget_rule_ids")
            if self.provenance_expectations:
                errors.append("not-contractable families cannot define provenance_expectations")
            if self.deterministic_fixture_expectations:
                errors.append("not-contractable families cannot define deterministic_fixture_expectations")
            if self.custom_validator is not None:
                errors.append("not-contractable families cannot define custom_validator")

        return tuple(errors)

    def evaluate(
        self,
        blueprint: Blueprint,
        proof_module_manifest: ProofModuleManifest | None = None,
        proof_unit_registry: ProofUnitRegistry | None = None,
    ) -> ConformanceEvaluation:
        accepted_checks: list[str] = []
        failure_reasons: list[str] = []
        failure_codes: list[str] = []

        section_titles = [str(section.title) for section in getattr(blueprint, "story_architecture", [])]
        section_title_set = set(section_titles)
        if self.required_sections:
            missing_sections = sorted(set(self.required_sections) - section_title_set)
            if missing_sections:
                failure_codes.append("missing-required-sections")
                failure_reasons.append(
                    f"`{self.option_id}` requires sections {', '.join(self.required_sections)}. "
                    f"Missing: {', '.join(missing_sections)}."
                )
            else:
                accepted_checks.append(
                    f"`{self.option_id}` kept the required sections {', '.join(self.required_sections)}."
                )

        main_story_roles = sorted(_main_story_roles(blueprint))
        if self.required_main_story_roles:
            missing_roles = sorted(set(self.required_main_story_roles) - set(main_story_roles))
            if missing_roles:
                failure_codes.append("missing-main-story-roles")
                failure_reasons.append(
                    f"`{self.option_id}` requires main-story roles {', '.join(self.required_main_story_roles)}. "
                    f"Missing: {', '.join(missing_roles)}."
                )
            else:
                accepted_checks.append(
                    f"Main story includes the required roles for `{self.option_id}`: {', '.join(self.required_main_story_roles)}."
                )

        appendix_actual = int(getattr(blueprint, "appendix_actual_slide_count", 0) or 0)
        if self.minimum_appendix_slides > 0:
            if appendix_actual < self.minimum_appendix_slides:
                failure_codes.append("appendix-underfilled")
                failure_reasons.append(
                    f"`{self.option_id}` requires at least {self.minimum_appendix_slides} appendix slide(s), "
                    f"but only {appendix_actual} were produced."
                )
            else:
                accepted_checks.append(
                    f"Appendix capacity for `{self.option_id}` is present with {appendix_actual} slide(s)."
                )

        non_appendix_sections = _non_appendix_sections(blueprint)
        if self.minimum_story_sections > 0:
            if len(non_appendix_sections) < self.minimum_story_sections:
                failure_codes.append("insufficient-story-sections")
                failure_reasons.append(
                    f"`{self.option_id}` requires at least {self.minimum_story_sections} non-appendix sections, "
                    f"but only {len(non_appendix_sections)} were produced."
                )
            else:
                accepted_checks.append(
                    f"`{self.option_id}` produced {len(non_appendix_sections)} non-appendix sections."
                )

        if self.maximum_story_sections is not None:
            if len(non_appendix_sections) > self.maximum_story_sections:
                failure_codes.append("too-many-story-sections")
                failure_reasons.append(
                    f"`{self.option_id}` permits at most {self.maximum_story_sections} non-appendix sections, "
                    f"but CONTENT_PLAN produced {len(non_appendix_sections)}."
                )
            else:
                accepted_checks.append(
                    f"`{self.option_id}` kept non-appendix sections within the {self.maximum_story_sections}-section ceiling."
                )

        if self.require_lecture_family:
            if getattr(blueprint, "lecture_family", None) is None:
                failure_codes.append("missing-lecture-family")
                failure_reasons.append(f"`{self.option_id}` requires lecture_family evidence in the blueprint.")
            else:
                accepted_checks.append(
                    f"`{self.option_id}` recorded lecture_family `{blueprint.lecture_family}`."
                )

        if self.require_clustering_decisions:
            clustering_decisions = list(getattr(blueprint, "clustering_decisions", []) or [])
            if not clustering_decisions:
                failure_codes.append("missing-clustering-decisions")
                failure_reasons.append(f"`{self.option_id}` requires clustering_decisions in the blueprint.")
            else:
                accepted_checks.append(
                    f"`{self.option_id}` recorded {len(clustering_decisions)} clustering decision(s)."
                )

        if self.custom_validator is not None:
            custom_checks, custom_failures, custom_failure_codes = self.custom_validator(
                blueprint,
                proof_module_manifest,
                proof_unit_registry,
            )
            accepted_checks.extend(custom_checks)
            failure_reasons.extend(custom_failures)
            failure_codes.extend(custom_failure_codes)

        return accepted_checks, failure_reasons, failure_codes


def _evaluate_tight_main_story(
    blueprint: Blueprint,
    proof_module_manifest: ProofModuleManifest | None = None,
    proof_unit_registry: ProofUnitRegistry | None = None,
) -> ConformanceEvaluation:
    del proof_module_manifest
    del proof_unit_registry
    accepted_checks: list[str] = []
    failure_reasons: list[str] = []
    failure_codes: list[str] = []

    non_appendix_sections = _non_appendix_sections(blueprint)
    if non_appendix_sections != ["Core Story"]:
        failure_codes.append("tight-main-story-main-section-shape")
        failure_reasons.append(
            "`tight-main-story` must keep exactly one non-appendix section titled `Core Story`."
        )
    else:
        accepted_checks.append("`tight-main-story` kept one bounded `Core Story` section before appendix overflow.")

    main_story_slides = _main_story_slides(blueprint)
    if not main_story_slides:
        failure_codes.append("tight-main-story-empty-main-story")
        failure_reasons.append("`tight-main-story` requires at least one main-story slide.")
        return accepted_checks, failure_reasons, failure_codes

    first_role = _slide_role_value(main_story_slides[0])
    if first_role != SlideRole.EXECUTIVE_SUMMARY.value:
        failure_codes.append("tight-main-story-open-mismatch")
        failure_reasons.append(
            "`tight-main-story` must open the main story with an executive-summary slide."
        )
    else:
        accepted_checks.append("`tight-main-story` opens with an executive-summary anchor slide.")

    last_role = _slide_role_value(main_story_slides[-1])
    if last_role != SlideRole.RECOMMENDATION.value:
        failure_codes.append("tight-main-story-close-mismatch")
        failure_reasons.append(
            "`tight-main-story` must close the main story with a recommendation slide."
        )
    else:
        accepted_checks.append("`tight-main-story` closes the main story with a recommendation slide.")

    analysis_slides = [
        slide for slide in main_story_slides if _slide_role_value(slide) == SlideRole.ANALYSIS.value
    ]
    if analysis_slides and any(getattr(slide, "layout_pattern_id", "") == "comparison" for slide in analysis_slides):
        failure_codes.append("tight-main-story-analysis-layout-mismatch")
        failure_reasons.append(
            "`tight-main-story` analysis slides must stay on a role-compatible layout family instead of the evidence-only `comparison` layout."
        )
    elif analysis_slides:
        accepted_checks.append(
            "`tight-main-story` keeps analysis slides on role-compatible layout patterns before the proof slide."
        )

    return accepted_checks, failure_reasons, failure_codes


def _section_id_for_title(blueprint: Blueprint, title: str) -> str | None:
    for section in getattr(blueprint, "story_architecture", []):
        if str(getattr(section, "title", "")) == title:
            section_id = str(getattr(section, "section_id", "")).strip()
            return section_id or None
    return None


def _evaluate_report_with_decision_cut(
    blueprint: Blueprint,
    proof_module_manifest: ProofModuleManifest | None = None,
    proof_unit_registry: ProofUnitRegistry | None = None,
) -> ConformanceEvaluation:
    del proof_module_manifest
    accepted_checks: list[str] = []
    failure_reasons: list[str] = []
    failure_codes: list[str] = []

    policy = shared_proof_consumer_policy("report-with-decision-cut")
    assert policy is not None

    non_appendix_sections = _non_appendix_sections(blueprint)
    expected_sections = list(policy.expected_non_appendix_sections)
    if non_appendix_sections != expected_sections:
        failure_codes.append("report-with-decision-cut-section-shape")
        failure_reasons.append(
            "`report-with-decision-cut` must keep `Executive Summary -> Why Now -> Proof And Options -> Recommendation And Next Steps` as the non-appendix section flow."
        )
    else:
        accepted_checks.append(
            "`report-with-decision-cut` kept the bounded `Executive Summary -> Why Now -> Proof And Options -> Recommendation And Next Steps` section flow."
        )

    main_story_slides = _main_story_slides(blueprint)
    if not main_story_slides:
        failure_codes.append("report-with-decision-cut-empty-main-story")
        failure_reasons.append("`report-with-decision-cut` requires a non-empty main story.")
        return accepted_checks, failure_reasons, failure_codes

    if _slide_role_value(main_story_slides[0]) != SlideRole.EXECUTIVE_SUMMARY.value:
        failure_codes.append("report-with-decision-cut-open-mismatch")
        failure_reasons.append(
            "`report-with-decision-cut` must open the main story with an executive-summary decision frame."
        )
    else:
        accepted_checks.append("`report-with-decision-cut` opens on an executive-summary decision frame.")

    if str(getattr(main_story_slides[-1], "section", "")) != policy.synthesis_anchor_section_title:
        failure_codes.append("report-with-decision-cut-close-mismatch")
        failure_reasons.append(
            "`report-with-decision-cut` must close the main story inside `Recommendation And Next Steps`."
        )
    else:
        accepted_checks.append(
            "`report-with-decision-cut` closes the main story inside `Recommendation And Next Steps`."
        )

    if proof_unit_registry is None:
        failure_codes.append("report-with-decision-cut-missing-proof-unit-registry")
        failure_reasons.append(
            "`report-with-decision-cut` now requires an explicit shared `proof_unit_registry` so the proof-and-options spine is auditable without reconstructing it from slide structure."
        )
        return accepted_checks, failure_reasons, failure_codes

    if proof_unit_registry.workflow_option != "report-with-decision-cut":
        failure_codes.append("report-with-decision-cut-proof-unit-registry-mismatch")
        failure_reasons.append(
            "The shared proof-unit registry does not belong to the locked `report-with-decision-cut` workflow family."
        )
        return accepted_checks, failure_reasons, failure_codes

    accepted_checks.append(
        "`report-with-decision-cut` recorded the proof-and-options spine in the shared proof-unit registry."
    )

    expected_claim_section_id = _section_id_for_title(blueprint, policy.claim_anchor_section_title)
    expected_proof_section_id = _section_id_for_title(blueprint, policy.proof_section_title)
    expected_synthesis_section_id = _section_id_for_title(blueprint, policy.synthesis_anchor_section_title)

    if expected_claim_section_id and proof_unit_registry.claim_anchor_section_id != expected_claim_section_id:
        failure_codes.append("report-with-decision-cut-decision-anchor-mismatch")
        failure_reasons.append(
            "`report-with-decision-cut` proof units must link back to the emitted `Executive Summary` decision-anchor section id."
        )
    if expected_proof_section_id and proof_unit_registry.proof_section_id != expected_proof_section_id:
        failure_codes.append("report-with-decision-cut-proof-unit-registry-mismatch")
        failure_reasons.append(
            "`report-with-decision-cut` proof-unit registry must point at the emitted `Proof And Options` section id."
        )
    if expected_synthesis_section_id and proof_unit_registry.synthesis_anchor_section_id != expected_synthesis_section_id:
        failure_codes.append("report-with-decision-cut-recommendation-anchor-mismatch")
        failure_reasons.append(
            "`report-with-decision-cut` proof units must link forward to the emitted `Recommendation And Next Steps` section id."
        )

    units = list(proof_unit_registry.units)
    if proof_unit_registry.unit_count != len(units):
        failure_codes.append("report-with-decision-cut-proof-unit-registry-mismatch")
        failure_reasons.append(
            "`report-with-decision-cut` proof-unit registry must keep unit_count synchronized with the emitted unit list."
        )

    if proof_unit_registry.unit_minimum < policy.unit_minimum or len(units) < policy.unit_minimum:
        failure_codes.append("report-with-decision-cut-proof-unit-underfilled")
        failure_reasons.append(
            "`report-with-decision-cut` requires three explicit proof units in `Proof And Options`: evidence, option comparison, and tradeoff analysis."
        )
    else:
        accepted_checks.append(
            f"`report-with-decision-cut` emitted {len(units)} explicit proof unit(s) for the `Proof And Options` section."
        )

    proof_slide_numbers = [
        int(getattr(slide, "slide_number", 0) or 0)
        for slide in main_story_slides
        if str(getattr(slide, "section", "")) == policy.proof_section_title
    ]
    registry_slide_numbers = [unit.slide_number for unit in units]
    ordered_indices = [unit.unit_order_index for unit in units]
    if ordered_indices and ordered_indices != list(range(1, len(units) + 1)):
        failure_codes.append("report-with-decision-cut-proof-order-mismatch")
        failure_reasons.append(
            "`report-with-decision-cut` proof units must use a contiguous unit_order_index sequence starting at 1."
        )
    elif registry_slide_numbers != sorted(registry_slide_numbers):
        failure_codes.append("report-with-decision-cut-proof-order-mismatch")
        failure_reasons.append(
            "`report-with-decision-cut` proof-unit registry must keep units in ascending slide order."
        )
    else:
        accepted_checks.append(
            "`report-with-decision-cut` records proof units in explicit slide order inside the shared registry."
        )

    if registry_slide_numbers != proof_slide_numbers:
        failure_codes.append("report-with-decision-cut-proof-unit-registry-mismatch")
        failure_reasons.append(
            "`report-with-decision-cut` proof-unit registry must stay synchronized with the blueprint `Proof And Options` slide references."
        )

    if units:
        decision_context_slide_numbers = [
            int(getattr(slide, "slide_number", 0) or 0)
            for slide in main_story_slides
            if str(getattr(slide, "section", "")) in {policy.claim_anchor_section_title, *policy.bridge_section_titles}
        ]
        recommendation_slide_numbers = [
            int(getattr(slide, "slide_number", 0) or 0)
            for slide in main_story_slides
            if str(getattr(slide, "section", "")) == policy.synthesis_anchor_section_title
        ]
        if not decision_context_slide_numbers or not recommendation_slide_numbers:
            failure_codes.append("report-with-decision-cut-proof-order-mismatch")
            failure_reasons.append(
                "`report-with-decision-cut` requires decision framing/context before `Proof And Options` and a recommendation close after it."
            )
        else:
            decision_close = max(decision_context_slide_numbers)
            recommendation_open = min(recommendation_slide_numbers)
            if registry_slide_numbers[0] <= decision_close or registry_slide_numbers[-1] >= recommendation_open:
                failure_codes.append("report-with-decision-cut-proof-order-mismatch")
                failure_reasons.append(
                    "`report-with-decision-cut` must keep `Proof And Options` between the decision framing/context and the recommendation close."
                )
            else:
                accepted_checks.append(
                    "`report-with-decision-cut` keeps proof units between the decision framing/context and the recommendation close."
                )

    unexpected_roles = [
        _slide_role_value(unit)
        for unit in units
        if getattr(unit, "slide_role", None) not in policy.allowed_unit_roles
    ]
    if unexpected_roles:
        failure_codes.append("report-with-decision-cut-proof-role-mismatch")
        failure_reasons.append(
            "`report-with-decision-cut` proof units must stay within the shared role vocabulary `evidence`, `comparison`, or `analysis`."
        )

    unit_role_values = {_slide_role_value(unit) for unit in units}
    if SlideRole.EVIDENCE.value not in unit_role_values or proof_unit_registry.direct_evidence_unit_count < policy.minimum_direct_evidence_units:
        failure_codes.append("report-with-decision-cut-missing-proof-evidence")
        failure_reasons.append(
            "`report-with-decision-cut` proof units require at least one direct evidence unit in `Proof And Options`."
        )
    else:
        accepted_checks.append(
            "`report-with-decision-cut` keeps direct evidence inside the explicit proof-unit registry."
        )

    if SlideRole.COMPARISON.value not in unit_role_values:
        failure_codes.append("report-with-decision-cut-missing-option-comparison")
        failure_reasons.append(
            "`report-with-decision-cut` proof units require an explicit option-comparison unit before the recommendation close."
        )
    if SlideRole.ANALYSIS.value not in unit_role_values:
        failure_codes.append("report-with-decision-cut-missing-tradeoff-analysis")
        failure_reasons.append(
            "`report-with-decision-cut` proof units require an explicit tradeoff-analysis unit before the recommendation close."
        )
    if proof_unit_registry.synthesis_unit_count < policy.minimum_synthesis_units:
        failure_codes.append("report-with-decision-cut-missing-proof-synthesis")
        failure_reasons.append(
            "`report-with-decision-cut` proof units require both comparison and analysis synthesis coverage inside the main story."
        )
    else:
        accepted_checks.append(
            "`report-with-decision-cut` keeps option comparison and tradeoff analysis inside the shared proof-unit registry."
        )

    claim_slide_numbers = sorted(proof_unit_registry.claim_anchor_slide_numbers)
    synthesis_slide_numbers = sorted(proof_unit_registry.synthesis_anchor_slide_numbers)
    for unit in units:
        if (
            unit.claim_anchor_section_id != proof_unit_registry.claim_anchor_section_id
            or unit.claim_anchor_slide_number not in claim_slide_numbers
        ):
            failure_codes.append("report-with-decision-cut-decision-anchor-mismatch")
            failure_reasons.append(
                "`report-with-decision-cut` proof units must link back to a real executive-summary decision anchor in the shared registry."
            )
            break
    else:
        accepted_checks.append(
            "`report-with-decision-cut` proof units link back to the emitted executive-summary decision anchor."
        )

    for unit in units:
        if (
            unit.synthesis_anchor_section_id != proof_unit_registry.synthesis_anchor_section_id
            or unit.synthesis_anchor_slide_number not in synthesis_slide_numbers
        ):
            failure_codes.append("report-with-decision-cut-recommendation-anchor-mismatch")
            failure_reasons.append(
                "`report-with-decision-cut` proof units must link forward to a real recommendation close in the shared registry."
            )
            break
    else:
        accepted_checks.append(
            "`report-with-decision-cut` proof units link forward to the emitted recommendation close."
        )

    if any(unit.placement != DeckMode.MAIN_STORY for unit in units):
        failure_codes.append("report-with-decision-cut-placement-mismatch")
        failure_reasons.append(
            "`report-with-decision-cut` proof units must remain in main-story placement until overflow is deliberately moved into appendix methods or backup evidence."
        )
    else:
        accepted_checks.append(
            "`report-with-decision-cut` keeps proof units in the main story instead of appendix overflow."
        )

    provenance_gap = not proof_unit_registry.workflow_policy_id.strip()
    for unit in units:
        if unit.status != ProofModuleStatus.READY:
            provenance_gap = True
        if not unit.source_material_refs:
            provenance_gap = True
        if not unit.workflow_policy_id.strip():
            provenance_gap = True
        if not unit.claim_link_reason.strip() or not unit.synthesis_link_reason.strip():
            provenance_gap = True
    if provenance_gap:
        failure_codes.append("report-with-decision-cut-provenance-gap")
        failure_reasons.append(
            "`report-with-decision-cut` proof units require source-material refs, workflow provenance, and explicit decision/recommendation linkage reasons."
        )
    else:
        accepted_checks.append(
            "`report-with-decision-cut` proof units persist source, workflow, decision, and recommendation provenance explicitly."
        )

    return accepted_checks, failure_reasons, failure_codes


def _evaluate_thesis_proof_close(
    blueprint: Blueprint,
    proof_module_manifest: ProofModuleManifest | None = None,
    proof_unit_registry: ProofUnitRegistry | None = None,
) -> ConformanceEvaluation:
    del proof_module_manifest
    accepted_checks: list[str] = []
    failure_reasons: list[str] = []
    failure_codes: list[str] = []

    policy = shared_proof_consumer_policy("thesis-proof-close")
    assert policy is not None

    non_appendix_sections = _non_appendix_sections(blueprint)
    expected_sections = list(policy.expected_non_appendix_sections)
    if non_appendix_sections != expected_sections:
        failure_codes.append("thesis-proof-close-section-shape")
        failure_reasons.append(
            "`thesis-proof-close` must keep `Thesis -> Proof Spine -> Close` as the non-appendix section flow."
        )
    else:
        accepted_checks.append(
            "`thesis-proof-close` kept the bounded `Thesis -> Proof Spine -> Close` section flow."
        )

    main_story_slides = _main_story_slides(blueprint)
    if not main_story_slides:
        failure_codes.append("thesis-proof-close-empty-main-story")
        failure_reasons.append("`thesis-proof-close` requires a non-empty main story.")
        return accepted_checks, failure_reasons, failure_codes

    if (
        _slide_role_value(main_story_slides[0]) != SlideRole.EXECUTIVE_SUMMARY.value
        or str(getattr(main_story_slides[0], "section", "")) != policy.claim_anchor_section_title
    ):
        failure_codes.append("thesis-proof-close-open-mismatch")
        failure_reasons.append(
            "`thesis-proof-close` must open the main story inside `Thesis` with an executive-summary thesis anchor."
        )
    else:
        accepted_checks.append(
            "`thesis-proof-close` opens the main story on an explicit thesis anchor slide."
        )

    if (
        _slide_role_value(main_story_slides[-1]) != SlideRole.RECOMMENDATION.value
        or str(getattr(main_story_slides[-1], "section", "")) != policy.synthesis_anchor_section_title
    ):
        failure_codes.append("thesis-proof-close-close-mismatch")
        failure_reasons.append(
            "`thesis-proof-close` must close the main story inside `Close` with a recommendation or ask slide."
        )
    else:
        accepted_checks.append(
            "`thesis-proof-close` closes the main story inside `Close` on the explicit ask."
        )

    if proof_unit_registry is None:
        failure_codes.append("thesis-proof-close-missing-proof-unit-registry")
        failure_reasons.append(
            "`thesis-proof-close` now requires an explicit shared `proof_unit_registry` so the proof spine is auditable without reconstructing it from slide structure."
        )
        return accepted_checks, failure_reasons, failure_codes

    if proof_unit_registry.workflow_option != "thesis-proof-close":
        failure_codes.append("thesis-proof-close-proof-unit-registry-mismatch")
        failure_reasons.append(
            "The shared proof-unit registry does not belong to the locked `thesis-proof-close` workflow family."
        )
        return accepted_checks, failure_reasons, failure_codes

    accepted_checks.append(
        "`thesis-proof-close` recorded the thesis proof spine in the shared proof-unit registry."
    )

    expected_claim_section_id = _section_id_for_title(blueprint, policy.claim_anchor_section_title)
    expected_proof_section_id = _section_id_for_title(blueprint, policy.proof_section_title)
    expected_synthesis_section_id = _section_id_for_title(blueprint, policy.synthesis_anchor_section_title)

    if expected_claim_section_id and proof_unit_registry.claim_anchor_section_id != expected_claim_section_id:
        failure_codes.append("thesis-proof-close-thesis-linkage-mismatch")
        failure_reasons.append(
            "`thesis-proof-close` proof units must link back to the emitted `Thesis` section id."
        )
    if expected_proof_section_id and proof_unit_registry.proof_section_id != expected_proof_section_id:
        failure_codes.append("thesis-proof-close-proof-unit-registry-mismatch")
        failure_reasons.append(
            "`thesis-proof-close` proof-unit registry must point at the emitted `Proof Spine` section id."
        )
    if expected_synthesis_section_id and proof_unit_registry.synthesis_anchor_section_id != expected_synthesis_section_id:
        failure_codes.append("thesis-proof-close-close-linkage-mismatch")
        failure_reasons.append(
            "`thesis-proof-close` proof units must link forward to the emitted `Close` section id."
        )

    units = list(proof_unit_registry.units)
    if proof_unit_registry.unit_count != len(units):
        failure_codes.append("thesis-proof-close-proof-unit-registry-mismatch")
        failure_reasons.append(
            "`thesis-proof-close` proof-unit registry must keep unit_count synchronized with the emitted unit list."
        )

    if proof_unit_registry.unit_minimum < policy.unit_minimum or len(units) < policy.unit_minimum:
        failure_codes.append("thesis-proof-close-proof-unit-underfilled")
        failure_reasons.append(
            "`thesis-proof-close` requires at least two explicit proof units in `Proof Spine`: one direct proof anchor and one synthesis-oriented bridge into the close."
        )
    else:
        accepted_checks.append(
            f"`thesis-proof-close` emitted {len(units)} explicit proof unit(s) for the `Proof Spine` section."
        )

    proof_slide_numbers = [
        int(getattr(slide, "slide_number", 0) or 0)
        for slide in main_story_slides
        if str(getattr(slide, "section", "")) == policy.proof_section_title
    ]
    registry_slide_numbers = [unit.slide_number for unit in units]
    ordered_indices = [unit.unit_order_index for unit in units]
    if ordered_indices and ordered_indices != list(range(1, len(units) + 1)):
        failure_codes.append("thesis-proof-close-proof-order-mismatch")
        failure_reasons.append(
            "`thesis-proof-close` proof units must use a contiguous unit_order_index sequence starting at 1."
        )
    elif registry_slide_numbers != sorted(registry_slide_numbers):
        failure_codes.append("thesis-proof-close-proof-order-mismatch")
        failure_reasons.append(
            "`thesis-proof-close` proof-unit registry must keep units in ascending slide order."
        )
    else:
        accepted_checks.append(
            "`thesis-proof-close` records proof units in explicit slide order inside the shared registry."
        )

    if registry_slide_numbers != proof_slide_numbers:
        failure_codes.append("thesis-proof-close-proof-unit-registry-mismatch")
        failure_reasons.append(
            "`thesis-proof-close` proof-unit registry must stay synchronized with the blueprint `Proof Spine` slide references."
        )

    thesis_slide_numbers = [
        int(getattr(slide, "slide_number", 0) or 0)
        for slide in main_story_slides
        if str(getattr(slide, "section", "")) == policy.claim_anchor_section_title
    ]
    close_slide_numbers = [
        int(getattr(slide, "slide_number", 0) or 0)
        for slide in main_story_slides
        if str(getattr(slide, "section", "")) == policy.synthesis_anchor_section_title
    ]
    if not thesis_slide_numbers or not close_slide_numbers or not units:
        failure_codes.append("thesis-proof-close-proof-order-mismatch")
        failure_reasons.append(
            "`thesis-proof-close` requires a thesis anchor before the proof spine and a close after it."
        )
    else:
        thesis_close = max(thesis_slide_numbers)
        close_open = min(close_slide_numbers)
        if registry_slide_numbers[0] <= thesis_close or registry_slide_numbers[-1] >= close_open:
            failure_codes.append("thesis-proof-close-proof-order-mismatch")
            failure_reasons.append(
                "`thesis-proof-close` must keep `Proof Spine` between the `Thesis` anchor and the `Close` ask."
            )
        else:
            accepted_checks.append(
                "`thesis-proof-close` keeps proof units between the thesis anchor and the close."
            )

    unexpected_roles = [
        _slide_role_value(unit)
        for unit in units
        if getattr(unit, "slide_role", None) not in policy.allowed_unit_roles
    ]
    if unexpected_roles:
        failure_codes.append("thesis-proof-close-proof-role-mismatch")
        failure_reasons.append(
            "`thesis-proof-close` proof units must stay within the shared role vocabulary `evidence`, `comparison`, or `analysis`."
        )

    direct_evidence_classes = {
        ProofCoverageClass.DIRECT_EVIDENCE,
        ProofCoverageClass.QUANTITATIVE_EVIDENCE,
    }
    synthesis_classes = {
        ProofCoverageClass.COMPARATIVE_SYNTHESIS,
        ProofCoverageClass.INTERPRETIVE_SYNTHESIS,
    }
    if not any(unit.coverage_class in direct_evidence_classes for unit in units) or proof_unit_registry.direct_evidence_unit_count < policy.minimum_direct_evidence_units:
        failure_codes.append("thesis-proof-close-missing-proof-evidence")
        failure_reasons.append(
            "`thesis-proof-close` requires at least one direct or quantitative evidence unit in `Proof Spine`."
        )
    else:
        accepted_checks.append(
            "`thesis-proof-close` keeps direct evidence inside the explicit proof spine."
        )

    if not any(unit.coverage_class in synthesis_classes for unit in units) or proof_unit_registry.synthesis_unit_count < policy.minimum_synthesis_units:
        failure_codes.append("thesis-proof-close-missing-proof-synthesis")
        failure_reasons.append(
            "`thesis-proof-close` requires at least one synthesis-oriented proof unit before the close."
        )
    else:
        accepted_checks.append(
            "`thesis-proof-close` keeps synthesis coverage inside the explicit proof spine."
        )

    if units and units[0].coverage_class not in direct_evidence_classes:
        failure_codes.append("thesis-proof-close-proof-order-mismatch")
        failure_reasons.append(
            "`thesis-proof-close` must open `Proof Spine` with a direct evidence unit before synthesis or comparison units appear."
        )
    if units and units[-1].coverage_class not in synthesis_classes:
        failure_codes.append("thesis-proof-close-close-linkage-mismatch")
        failure_reasons.append(
            "`thesis-proof-close` must end `Proof Spine` on a synthesis-oriented unit so the proof chain lands cleanly in the close."
        )

    claim_slide_numbers = sorted(proof_unit_registry.claim_anchor_slide_numbers)
    synthesis_slide_numbers = sorted(proof_unit_registry.synthesis_anchor_slide_numbers)
    for unit in units:
        if (
            unit.claim_anchor_section_id != proof_unit_registry.claim_anchor_section_id
            or unit.claim_anchor_slide_number not in claim_slide_numbers
        ):
            failure_codes.append("thesis-proof-close-thesis-linkage-mismatch")
            failure_reasons.append(
                "`thesis-proof-close` proof units must link back to a real thesis anchor in the shared registry."
            )
            break
    else:
        accepted_checks.append(
            "`thesis-proof-close` proof units link back to the emitted thesis anchor."
        )

    for unit in units:
        if (
            unit.synthesis_anchor_section_id != proof_unit_registry.synthesis_anchor_section_id
            or unit.synthesis_anchor_slide_number not in synthesis_slide_numbers
        ):
            failure_codes.append("thesis-proof-close-close-linkage-mismatch")
            failure_reasons.append(
                "`thesis-proof-close` proof units must link forward to a real close anchor in the shared registry."
            )
            break
    else:
        accepted_checks.append(
            "`thesis-proof-close` proof units link forward to the emitted close anchor."
        )

    if any(unit.placement != DeckMode.MAIN_STORY for unit in units):
        failure_codes.append("thesis-proof-close-placement-mismatch")
        failure_reasons.append(
            "`thesis-proof-close` proof units must remain in main-story placement until overflow is deliberately moved into appendix support."
        )
    else:
        accepted_checks.append(
            "`thesis-proof-close` keeps proof units in the main story instead of appendix overflow."
        )

    provenance_gap = not proof_unit_registry.workflow_policy_id.strip()
    for unit in units:
        if unit.status != ProofModuleStatus.READY:
            provenance_gap = True
        if not unit.source_material_refs:
            provenance_gap = True
        if not unit.workflow_policy_id.strip():
            provenance_gap = True
        if not unit.claim_link_reason.strip() or not unit.synthesis_link_reason.strip():
            provenance_gap = True
    if provenance_gap:
        failure_codes.append("thesis-proof-close-provenance-gap")
        failure_reasons.append(
            "`thesis-proof-close` proof units require source-material refs, workflow provenance, and explicit thesis/close linkage reasons."
        )
    else:
        accepted_checks.append(
            "`thesis-proof-close` proof units persist source, workflow, thesis, and close provenance explicitly."
        )

    return accepted_checks, failure_reasons, failure_codes


def _evaluate_evidence_backed_core(
    blueprint: Blueprint,
    proof_module_manifest: ProofModuleManifest | None = None,
    proof_unit_registry: ProofUnitRegistry | None = None,
) -> ConformanceEvaluation:
    accepted_checks: list[str] = []
    failure_reasons: list[str] = []
    failure_codes: list[str] = []
    policy = shared_proof_consumer_policy("evidence-backed-core")
    assert policy is not None

    non_appendix_sections = _non_appendix_sections(blueprint)
    expected_sections = ["Core Claim", "Proof Modules", "Implications"]
    if non_appendix_sections != expected_sections:
        failure_codes.append("evidence-backed-core-section-shape")
        failure_reasons.append(
            "`evidence-backed-core` must keep `Core Claim`, `Proof Modules`, and `Implications` as the non-appendix section sequence."
        )
    else:
        accepted_checks.append(
            "`evidence-backed-core` kept the bounded `Core Claim -> Proof Modules -> Implications` section flow."
        )

    main_story_slides = _main_story_slides(blueprint)
    if not main_story_slides:
        failure_codes.append("evidence-backed-core-empty-main-story")
        failure_reasons.append("`evidence-backed-core` requires a non-empty main story.")
        return accepted_checks, failure_reasons, failure_codes

    if _slide_role_value(main_story_slides[0]) != SlideRole.EXECUTIVE_SUMMARY.value:
        failure_codes.append("evidence-backed-core-core-claim-open-mismatch")
        failure_reasons.append(
            "`evidence-backed-core` must open the main story with an executive-summary core-claim slide."
        )
    else:
        accepted_checks.append("`evidence-backed-core` opens on a core-claim executive-summary slide.")

    indexed_sections = [
        (index, str(getattr(slide, "section", "")), _slide_role_value(slide), int(getattr(slide, "slide_number", 0) or 0))
        for index, slide in enumerate(main_story_slides)
    ]
    proof_slide_numbers = [
        slide_number for _index, section, _role, slide_number in indexed_sections if section == "Proof Modules"
    ]
    core_claim_indices = [index for index, section, _role, _slide_number in indexed_sections if section == "Core Claim"]
    implication_indices = [index for index, section, _role, _slide_number in indexed_sections if section == "Implications"]

    if indexed_sections[-1][1] != "Implications":
        failure_codes.append("evidence-backed-core-close-mismatch")
        failure_reasons.append(
            "`evidence-backed-core` must close the main story in the `Implications` section."
        )
    else:
        accepted_checks.append("`evidence-backed-core` closes the main story in the implications section.")

    registry_supplied = proof_unit_registry is not None
    if proof_unit_registry is None and proof_module_manifest is not None:
        try:
            proof_unit_registry = proof_unit_registry_from_proof_module_manifest(proof_module_manifest)
        except ValidationError as exc:
            validation_message = str(exc)
            if "unit_order_index must be contiguous and 1-based" in validation_message:
                failure_codes.append("evidence-backed-core-proof-order-mismatch")
                failure_reasons.append(
                    "`evidence-backed-core` proof units must keep a contiguous 1-based order in the shared proof-unit registry and any legacy manifest migration input."
                )
            else:
                failure_codes.append("evidence-backed-core-proof-unit-registry-mismatch")
                failure_reasons.append(
                    "The legacy `proof_module_manifest` could not be adapted into the shared proof-unit registry shape required for `evidence-backed-core` conformance."
                )
            return accepted_checks, failure_reasons, failure_codes

    if proof_unit_registry is None:
        failure_codes.append("evidence-backed-core-missing-proof-unit-registry")
        failure_reasons.append(
            "`evidence-backed-core` now requires an explicit shared `proof_unit_registry`; legacy `proof_module_manifest` inputs are only accepted through the migration adapter."
        )
        return accepted_checks, failure_reasons, failure_codes

    if proof_unit_registry.workflow_option != "evidence-backed-core":
        failure_codes.append("evidence-backed-core-proof-unit-registry-mismatch")
        failure_reasons.append(
            "The shared proof-unit registry does not belong to the locked `evidence-backed-core` workflow family."
        )
        return accepted_checks, failure_reasons, failure_codes

    if registry_supplied:
        accepted_checks.append(
            "`evidence-backed-core` recorded the proof stack in the shared proof-unit registry instead of relying on slide inference alone."
        )
    else:
        accepted_checks.append(
            "`evidence-backed-core` legacy proof_module_manifest can still be adapted into the shared proof-unit registry shape for migration-only compatibility."
        )

    if proof_module_manifest is not None:
        registry_manifest = proof_module_manifest_from_proof_unit_registry(proof_unit_registry)
        if registry_manifest.model_dump(mode="json") != proof_module_manifest.model_dump(mode="json"):
            failure_codes.append("evidence-backed-core-proof-unit-registry-mismatch")
            failure_reasons.append(
                "`evidence-backed-core` legacy proof_module_manifest must remain a thin compatibility view of the persisted proof-unit registry."
            )

    if not proof_unit_registry.workflow_policy_id.strip():
        failure_codes.append("evidence-backed-core-provenance-gap")
        failure_reasons.append(
            "`evidence-backed-core` proof units must record the workflow-policy provenance that created the proof stack."
        )

    expected_claim_section_id = _section_id_for_title(blueprint, "Core Claim")
    expected_proof_section_id = _section_id_for_title(blueprint, "Proof Modules")
    expected_implication_section_id = _section_id_for_title(blueprint, "Implications")

    if expected_claim_section_id and proof_unit_registry.claim_anchor_section_id != expected_claim_section_id:
        failure_codes.append("evidence-backed-core-claim-linkage-mismatch")
        failure_reasons.append(
            "`evidence-backed-core` proof units must link back to the emitted `Core Claim` section id."
        )
    if expected_proof_section_id and proof_unit_registry.proof_section_id != expected_proof_section_id:
        failure_codes.append("evidence-backed-core-proof-unit-registry-mismatch")
        failure_reasons.append(
            "`evidence-backed-core` proof-unit registry must point at the emitted `Proof Modules` section id."
        )
    if expected_implication_section_id and proof_unit_registry.synthesis_anchor_section_id != expected_implication_section_id:
        failure_codes.append("evidence-backed-core-implication-linkage-mismatch")
        failure_reasons.append(
            "`evidence-backed-core` proof units must link forward to the emitted `Implications` section id."
        )

    units = list(proof_unit_registry.units)
    if proof_unit_registry.unit_count != len(units):
        failure_codes.append("evidence-backed-core-proof-unit-registry-mismatch")
        failure_reasons.append(
            "`evidence-backed-core` proof-unit registry must keep unit_count synchronized with the emitted unit list."
        )

    if proof_unit_registry.unit_minimum < policy.unit_minimum or len(units) < policy.unit_minimum:
        failure_codes.append("evidence-backed-core-proof-unit-underfilled")
        failure_reasons.append(
            "`evidence-backed-core` requires at least two main-story proof units so the core claim is supported by multiple evidence-bearing slides."
        )
    else:
        accepted_checks.append(
            f"`evidence-backed-core` emitted {len(units)} explicit proof unit(s) in the shared registry for the main story."
        )

    allowed_proof_roles = {
        SlideRole.EVIDENCE.value,
        SlideRole.COMPARISON.value,
        SlideRole.ANALYSIS.value,
    }
    proof_roles = [unit.slide_role.value for unit in units]
    invalid_proof_roles = sorted({role for role in proof_roles if role not in allowed_proof_roles})
    if invalid_proof_roles:
        failure_codes.append("evidence-backed-core-proof-role-mismatch")
        failure_reasons.append(
            "`evidence-backed-core` proof units may only use evidence, comparison, or analysis roles. "
            f"Found: {', '.join(invalid_proof_roles)}."
        )
    else:
        accepted_checks.append(
            "`evidence-backed-core` kept explicit proof-unit roles inside the evidence/comparison/analysis set."
        )

    direct_evidence_classes = {
        ProofCoverageClass.DIRECT_EVIDENCE,
        ProofCoverageClass.QUANTITATIVE_EVIDENCE,
    }
    synthesis_classes = {
        ProofCoverageClass.COMPARATIVE_SYNTHESIS,
        ProofCoverageClass.INTERPRETIVE_SYNTHESIS,
    }
    if units and not any(unit.coverage_class in direct_evidence_classes for unit in units):
        failure_codes.append("evidence-backed-core-missing-proof-evidence")
        failure_reasons.append(
            "`evidence-backed-core` requires at least one explicit proof unit with direct or quantitative evidence coverage."
        )
    elif units:
        accepted_checks.append("`evidence-backed-core` records direct evidence coverage inside the proof-unit registry.")

    if units and not any(unit.coverage_class in synthesis_classes for unit in units):
        failure_codes.append("evidence-backed-core-missing-proof-synthesis")
        failure_reasons.append(
            "`evidence-backed-core` requires at least one explicit synthesis proof unit so the proof stack converges before the implications close."
        )
    elif units:
        accepted_checks.append(
            "`evidence-backed-core` records synthesis coverage alongside direct evidence in the proof-unit registry."
        )

    registry_slide_numbers = [unit.slide_number for unit in units]
    expected_order = list(range(1, len(units) + 1))
    if [unit.unit_order_index for unit in units] != expected_order:
        failure_codes.append("evidence-backed-core-proof-order-mismatch")
        failure_reasons.append(
            "`evidence-backed-core` proof units must use a contiguous unit_order_index sequence starting at 1."
        )
    elif registry_slide_numbers != sorted(registry_slide_numbers):
        failure_codes.append("evidence-backed-core-proof-order-mismatch")
        failure_reasons.append(
            "`evidence-backed-core` proof-unit registry must keep units in ascending slide order."
        )
    else:
        accepted_checks.append(
            "`evidence-backed-core` records the proof stack in explicit slide order inside the proof-unit registry."
        )

    if sorted(proof_slide_numbers) != registry_slide_numbers:
        failure_codes.append("evidence-backed-core-proof-unit-registry-mismatch")
        failure_reasons.append(
            "`evidence-backed-core` proof-unit registry must stay synchronized with the blueprint proof-module slide references."
        )

    if not core_claim_indices or not implication_indices or not units:
        failure_codes.append("evidence-backed-core-proof-order-mismatch")
        failure_reasons.append(
            "`evidence-backed-core` requires core-claim slides before proof units and an implications close after the proof stack."
        )
    else:
        first_proof_slide_number = registry_slide_numbers[0]
        last_proof_slide_number = registry_slide_numbers[-1]
        claim_close = max(
            slide_number
            for _index, section, _role, slide_number in indexed_sections
            if section == "Core Claim"
        )
        implication_open = min(
            slide_number
            for _index, section, _role, slide_number in indexed_sections
            if section == "Implications"
        )
        if claim_close >= first_proof_slide_number or last_proof_slide_number >= implication_open:
            failure_codes.append("evidence-backed-core-proof-order-mismatch")
            failure_reasons.append(
                "`evidence-backed-core` must keep proof units between the core-claim opening and the implications close."
            )
        else:
            accepted_checks.append(
                "`evidence-backed-core` keeps proof units ordered between the core-claim opening and the implications close."
            )

    claim_slide_numbers = sorted(proof_unit_registry.claim_anchor_slide_numbers)
    implication_slide_numbers = sorted(proof_unit_registry.synthesis_anchor_slide_numbers)
    for unit in units:
        if (
            unit.claim_anchor_section_id != proof_unit_registry.claim_anchor_section_id
            or unit.claim_anchor_slide_number not in claim_slide_numbers
        ):
            failure_codes.append("evidence-backed-core-claim-linkage-mismatch")
            failure_reasons.append(
                "`evidence-backed-core` proof units must link to a real core-claim slide in the emitted proof-unit registry."
            )
            break
    else:
        accepted_checks.append("`evidence-backed-core` proof units link back to the emitted core-claim slide set.")

    for unit in units:
        if (
            unit.synthesis_anchor_section_id != proof_unit_registry.synthesis_anchor_section_id
            or unit.synthesis_anchor_slide_number not in implication_slide_numbers
        ):
            failure_codes.append("evidence-backed-core-implication-linkage-mismatch")
            failure_reasons.append(
                "`evidence-backed-core` proof units must link forward to a real implications slide in the emitted proof-unit registry."
            )
            break
    else:
        accepted_checks.append("`evidence-backed-core` proof units link forward to the emitted implications close.")

    if any(unit.placement != DeckMode.MAIN_STORY for unit in units):
        failure_codes.append("evidence-backed-core-placement-mismatch")
        failure_reasons.append(
            "`evidence-backed-core` proof units must remain in main-story placement until overflow is deliberately moved to appendix."
        )
    else:
        accepted_checks.append("`evidence-backed-core` keeps proof units in the main story instead of appendix overflow.")

    provenance_gap = False
    for unit in units:
        status_value = str(getattr(getattr(unit, "status", None), "value", getattr(unit, "status", ""))).lower()
        if status_value != "ready":
            provenance_gap = True
        if not unit.source_material_refs:
            provenance_gap = True
        if not unit.workflow_policy_id.strip():
            provenance_gap = True
        if not unit.claim_link_reason.strip() or not unit.synthesis_link_reason.strip():
            provenance_gap = True
    if provenance_gap:
        failure_codes.append("evidence-backed-core-provenance-gap")
        failure_reasons.append(
            "`evidence-backed-core` proof units require source-material refs, workflow provenance, and explicit claim/implication linkage reasons."
        )
    else:
        accepted_checks.append(
            "`evidence-backed-core` proof units persist source, workflow, claim, and implication provenance explicitly."
        )

    return accepted_checks, failure_reasons, failure_codes


WORKFLOW_FAMILY_CONTRACTS: dict[str, WorkflowFamilyContract] = {
    "report-with-decision-cut": WorkflowFamilyContract(
        option_id="report-with-decision-cut",
        contract_state=WorkflowFamilyContractState.CONTRACTABLE,
        shared_proof_artifact_readiness=SharedProofArtifactReadiness.CURRENT_DIRECT_CONSUMER,
        shared_proof_artifact_notes=(
            "report-backed-decision-flow-now-emits-proof-and-options-units-into-the-shared-registry",
            "appendix-methods-and-backup-evidence-remain-separated-from-the-main-story-proof-stack",
        ),
        required_sections=(
            "Executive Summary",
            "Why Now",
            "Proof And Options",
            "Recommendation And Next Steps",
            "Appendix",
        ),
        required_main_story_roles=(
            SlideRole.EXECUTIVE_SUMMARY.value,
            SlideRole.EVIDENCE.value,
            SlideRole.RECOMMENDATION.value,
        ),
        minimum_appendix_slides=1,
        conformance_rule_ids=(
            "required-sections",
            "required-main-story-roles",
            "minimum-appendix-slides",
            "report-with-decision-cut-section-shape",
            "report-with-decision-cut-proof-unit-registry",
            "report-with-decision-cut-decision-anchor-mismatch",
            "report-with-decision-cut-recommendation-anchor-mismatch",
            "report-with-decision-cut-proof-order-mismatch",
            "report-with-decision-cut-proof-role-mismatch",
        ),
        budget_rule_ids=("main-story-budget-band", "appendix-budget-band"),
        provenance_expectations=(
            "selected-option-id-matches-locked-workflow",
            "requested-contract-is-recorded-when-present",
            "proof-unit-registry-persists-proof-and-options-provenance",
        ),
        deterministic_fixture_expectations=("tests.fixture_library.write_runtime_golden_fixture",),
        explanation="Report-backed decision decks must retain the executive summary, proof, recommendation, and appendix separation.",
        custom_validator=_evaluate_report_with_decision_cut,
    ),
    "training-demo-sequence": WorkflowFamilyContract(
        option_id="training-demo-sequence",
        contract_state=WorkflowFamilyContractState.CONTRACTABLE,
        shared_proof_artifact_readiness=SharedProofArtifactReadiness.UNLIKELY_SHARED_PROOF_CONSUMER,
        shared_proof_artifact_notes=(
            "workflow-walkthroughs-rely-on-process-and-rollout-structure-more-than-proof-stacks",
        ),
        required_sections=(
            "Orientation",
            "Workflow Model",
            "Demo Sequence",
            "Rollout And Support",
            "Appendix",
        ),
        required_main_story_roles=(
            SlideRole.EXECUTIVE_SUMMARY.value,
            SlideRole.PROCESS.value,
            SlideRole.EVIDENCE.value,
            SlideRole.RECOMMENDATION.value,
        ),
        minimum_appendix_slides=2,
        conformance_rule_ids=(
            "required-sections",
            "required-main-story-roles",
            "minimum-appendix-slides",
        ),
        budget_rule_ids=("main-story-budget-band", "appendix-budget-band"),
        provenance_expectations=(
            "selected-option-id-matches-locked-workflow",
            "requested-contract-is-recorded-when-present",
        ),
        deterministic_fixture_expectations=("tests.test_workflow_planner.WorkflowPlannerTest._training_demo_brief",),
        explanation="Training/demo decks must teach the workflow before the demo proof and retain rollout support plus appendix capacity.",
    ),
    "graduate-lecture-clustered": WorkflowFamilyContract(
        option_id="graduate-lecture-clustered",
        contract_state=WorkflowFamilyContractState.CONTRACTABLE,
        shared_proof_artifact_readiness=SharedProofArtifactReadiness.UNLIKELY_SHARED_PROOF_CONSUMER,
        shared_proof_artifact_notes=(
            "lecture-clustering-centers-on-concept-dependencies-rather-than-bounded-proof-units",
        ),
        required_sections=(
            "Orientation",
            "Appendix",
        ),
        required_main_story_roles=(
            SlideRole.EXECUTIVE_SUMMARY.value,
            SlideRole.ANALYSIS.value,
            SlideRole.EVIDENCE.value,
        ),
        minimum_appendix_slides=1,
        minimum_story_sections=4,
        require_lecture_family=True,
        require_clustering_decisions=True,
        conformance_rule_ids=(
            "required-sections",
            "required-main-story-roles",
            "minimum-appendix-slides",
            "minimum-story-sections",
            "lecture-family-required",
            "clustering-decisions-required",
        ),
        budget_rule_ids=("main-story-budget-band", "appendix-budget-band"),
        provenance_expectations=(
            "selected-option-id-matches-locked-workflow",
            "requested-contract-is-recorded-when-present",
        ),
        deterministic_fixture_expectations=("tests.test_gate2_planner.Gate2PlannerTest._plan_genetics_ga_outputs",),
        explanation="Graduate lecture workflows must cluster source material into a teaching sequence with explicit lecture-family evidence and appendix support.",
    ),
    "thesis-proof-close": WorkflowFamilyContract(
        option_id="thesis-proof-close",
        contract_state=WorkflowFamilyContractState.CONTRACTABLE,
        shared_proof_artifact_readiness=SharedProofArtifactReadiness.CURRENT_DIRECT_CONSUMER,
        shared_proof_artifact_notes=(
            "thesis-proof-close-now-emits-an-explicit-thesis-proof-close-spine-into-the-shared-registry",
            "the-proof-spine-must-open-on-direct-evidence-and-land-on-synthesis-before-the-close",
        ),
        required_sections=(
            "Thesis",
            "Proof Spine",
            "Close",
            "Appendix",
        ),
        required_main_story_roles=(
            SlideRole.EXECUTIVE_SUMMARY.value,
            SlideRole.EVIDENCE.value,
            SlideRole.COMPARISON.value,
            SlideRole.RECOMMENDATION.value,
        ),
        minimum_appendix_slides=1,
        minimum_story_sections=3,
        maximum_story_sections=3,
        conformance_rule_ids=(
            "required-sections",
            "required-main-story-roles",
            "minimum-appendix-slides",
            "minimum-story-sections",
            "maximum-story-sections",
            "thesis-proof-close-section-shape",
            "thesis-proof-close-open-mismatch",
            "thesis-proof-close-missing-proof-unit-registry",
            "thesis-proof-close-proof-unit-registry-mismatch",
            "thesis-proof-close-proof-unit-underfilled",
            "thesis-proof-close-proof-role-mismatch",
            "thesis-proof-close-missing-proof-evidence",
            "thesis-proof-close-missing-proof-synthesis",
            "thesis-proof-close-proof-order-mismatch",
            "thesis-proof-close-thesis-linkage-mismatch",
            "thesis-proof-close-close-linkage-mismatch",
            "thesis-proof-close-placement-mismatch",
            "thesis-proof-close-provenance-gap",
            "thesis-proof-close-close-mismatch",
        ),
        budget_rule_ids=("main-story-budget-band", "appendix-budget-band"),
        provenance_expectations=(
            "selected-option-id-matches-locked-workflow",
            "requested-contract-is-recorded-when-present",
        ),
        deterministic_fixture_expectations=("tests.fixture_library.write_runtime_thesis_proof_close_fixture",),
        custom_validator=_evaluate_thesis_proof_close,
        explanation="Thesis-proof-close decks must state a thesis, carry an explicit proof spine in the shared registry, close on the ask, and keep overflow in appendix space.",
    ),
    "tight-main-story": WorkflowFamilyContract(
        option_id="tight-main-story",
        contract_state=WorkflowFamilyContractState.CONTRACTABLE,
        shared_proof_artifact_readiness=SharedProofArtifactReadiness.UNLIKELY_SHARED_PROOF_CONSUMER,
        shared_proof_artifact_notes=(
            "compact-story-control-matters-more-than-multi-proof-auditability",
        ),
        required_sections=("Core Story", "Appendix"),
        required_main_story_roles=(
            SlideRole.EXECUTIVE_SUMMARY.value,
            SlideRole.ANALYSIS.value,
            SlideRole.EVIDENCE.value,
            SlideRole.RECOMMENDATION.value,
        ),
        maximum_story_sections=1,
        conformance_rule_ids=(
            "required-sections",
            "required-main-story-roles",
            "maximum-story-sections",
            "tight-main-story-open-mismatch",
            "tight-main-story-close-mismatch",
            "tight-main-story-analysis-layout-mismatch",
        ),
        budget_rule_ids=("main-story-budget-band", "appendix-budget-band"),
        provenance_expectations=(
            "selected-option-id-matches-locked-workflow",
            "requested-contract-is-recorded-when-present",
        ),
        deterministic_fixture_expectations=("tests.fixture_library.write_runtime_tight_main_story_fixture",),
        custom_validator=_evaluate_tight_main_story,
        explanation="Tight-main-story decks must keep one bounded main-story section, open on the decision frame, and close on the recommendation before appendix overflow.",
    ),
    "evidence-backed-core": WorkflowFamilyContract(
        option_id="evidence-backed-core",
        contract_state=WorkflowFamilyContractState.CONTRACTABLE,
        shared_proof_artifact_readiness=SharedProofArtifactReadiness.CURRENT_DIRECT_CONSUMER,
        shared_proof_artifact_notes=(
            "bounded-core-claim-proof-implication-structure-already-emits-explicit-proof-units",
            "shared-proof-registry-is-validated-here-before-other-families-adopt-it",
        ),
        required_sections=(
            "Core Claim",
            "Proof Modules",
            "Implications",
            "Appendix",
        ),
        required_main_story_roles=(
            SlideRole.EXECUTIVE_SUMMARY.value,
            SlideRole.EVIDENCE.value,
            SlideRole.COMPARISON.value,
            SlideRole.ANALYSIS.value,
        ),
        minimum_appendix_slides=1,
        minimum_story_sections=3,
        maximum_story_sections=3,
        conformance_rule_ids=(
            "required-sections",
            "required-main-story-roles",
            "minimum-appendix-slides",
            "minimum-story-sections",
            "maximum-story-sections",
            "evidence-backed-core-section-shape",
            "evidence-backed-core-core-claim-open-mismatch",
            "evidence-backed-core-missing-proof-unit-registry",
            "evidence-backed-core-proof-unit-registry-mismatch",
            "evidence-backed-core-proof-unit-underfilled",
            "evidence-backed-core-proof-role-mismatch",
            "evidence-backed-core-missing-proof-evidence",
            "evidence-backed-core-missing-proof-synthesis",
            "evidence-backed-core-proof-order-mismatch",
            "evidence-backed-core-claim-linkage-mismatch",
            "evidence-backed-core-implication-linkage-mismatch",
            "evidence-backed-core-placement-mismatch",
            "evidence-backed-core-provenance-gap",
            "evidence-backed-core-close-mismatch",
        ),
        budget_rule_ids=("main-story-budget-band", "appendix-budget-band"),
        provenance_expectations=(
            "selected-option-id-matches-locked-workflow",
            "requested-contract-is-recorded-when-present",
        ),
        deterministic_fixture_expectations=("tests.fixture_library.write_runtime_evidence_backed_core_fixture",),
        custom_validator=_evaluate_evidence_backed_core,
        explanation="Evidence-backed-core decks must open on a core claim, carry a bounded multi-proof stack in the main story, and close on the implication that the proof set supports before overflow moves to appendix.",
    ),
    "facilitated-workshop-flow": WorkflowFamilyContract(
        option_id="facilitated-workshop-flow",
        contract_state=WorkflowFamilyContractState.NOT_CONTRACTABLE,
        shared_proof_artifact_readiness=SharedProofArtifactReadiness.UNLIKELY_SHARED_PROOF_CONSUMER,
        shared_proof_artifact_notes=(
            "facilitation-modules-are-not-yet-proof-oriented",
        ),
        reason_code="gate2-workshop-modules-generic",
        next_step_requirements=(
            "add-alignment-exercise-and-decision-modules-to-gate2",
            "normalize-facilitation-role-structure-and-budget-checks",
            "add-deterministic-workshop-fixture-and-qa-path",
        ),
        explanation="Facilitated-workshop-flow is not yet contractable because Gate 2 still shapes it as a generic core-story deck instead of a facilitation spine.",
    ),
    "vision-arc": WorkflowFamilyContract(
        option_id="vision-arc",
        contract_state=WorkflowFamilyContractState.NOT_CONTRACTABLE,
        shared_proof_artifact_readiness=SharedProofArtifactReadiness.BLOCKED_UNTIL_GATE2_PROOF_STRUCTURE,
        shared_proof_artifact_notes=(
            "vision-proof-credibility-is-real-but-gate2-does-not-yet-emit-a-stable-proof-arc",
        ),
        reason_code="gate2-vision-arc-generic",
        next_step_requirements=(
            "add-why-now-destination-proof-action-sections",
            "define-keynote-style-conformance-invariants",
            "add-deterministic-vision-fixture",
        ),
        explanation="Vision-arc is not yet contractable because Gate 2 does not emit a stable keynote-style section arc.",
    ),
    "explainer-then-persuade": WorkflowFamilyContract(
        option_id="explainer-then-persuade",
        contract_state=WorkflowFamilyContractState.NOT_CONTRACTABLE,
        shared_proof_artifact_readiness=SharedProofArtifactReadiness.BLOCKED_UNTIL_GATE2_PROOF_STRUCTURE,
        shared_proof_artifact_notes=(
            "mixed-explainer-persuasion-briefs-lack-a-stable-proof-phase-boundary",
        ),
        reason_code="planner-availability-not-deterministic",
        next_step_requirements=(
            "stabilize-planner-compatibility-for-mixed-explainer-persuasion-briefs",
            "add-explicit-explainer-and-persuasion-phase-structure",
            "add-deterministic-fixture-and-conformance-rules",
        ),
        explanation="Explainer-then-persuade is not yet contractable because planner availability is still heuristic and Gate 2 does not enforce a two-phase story split.",
    ),
    "modular-briefing": WorkflowFamilyContract(
        option_id="modular-briefing",
        contract_state=WorkflowFamilyContractState.NOT_CONTRACTABLE,
        shared_proof_artifact_readiness=SharedProofArtifactReadiness.BLOCKED_UNTIL_GATE2_PROOF_STRUCTURE,
        shared_proof_artifact_notes=(
            "module-boundaries-could-host-shared-proof-units-once-gate2-emits-stable-modules",
        ),
        reason_code="gate2-modularity-not-structured",
        next_step_requirements=(
            "emit-explicit-module-boundaries-in-gate2",
            "define-module-reorder-and-overflow-invariants",
            "add-deterministic-modular-fixture",
        ),
        explanation="Modular-briefing remains non-contractable because Gate 2 does not yet produce stable module boundaries or conformance rules.",
    ),
    "batched-core-and-appendix": WorkflowFamilyContract(
        option_id="batched-core-and-appendix",
        contract_state=WorkflowFamilyContractState.NOT_CONTRACTABLE,
        shared_proof_artifact_readiness=SharedProofArtifactReadiness.UNLIKELY_SHARED_PROOF_CONSUMER,
        shared_proof_artifact_notes=(
            "large-deck-batching-is-a-continuity-overlay-not-a-proof-family",
        ),
        reason_code="continuity-overlay-not-family-structure",
        next_step_requirements=(
            "separate-batching-overlay-from-workflow-family-contract",
            "define-core-and-appendix-batch-invariants",
            "add-deterministic-large-deck-fixture",
        ),
        explanation="Batched-core-and-appendix still behaves as a large-deck continuity overlay rather than a fully specified workflow-family contract.",
    ),
}


def validate_workflow_contract_matrix() -> None:
    errors: list[str] = []
    for option_id, contract in WORKFLOW_FAMILY_CONTRACTS.items():
        if option_id != contract.option_id:
            errors.append(
                f"workflow contract key `{option_id}` does not match embedded option_id `{contract.option_id}`"
            )
        contract_errors = contract.completeness_errors()
        if contract_errors:
            errors.append(f"{option_id}: " + "; ".join(contract_errors))
    if errors:
        joined = "\n".join(f"- {error}" for error in errors)
        raise ValueError(f"workflow contract matrix is incomplete:\n{joined}")


validate_workflow_contract_matrix()


def shared_proof_artifact_readiness_rows() -> list[dict[str, object]]:
    return [
        {
            "option_id": option_id,
            "contract_state": contract.contract_state.value,
            "shared_proof_artifact_readiness": contract.shared_proof_artifact_readiness.value,
            "shared_proof_artifact_notes": list(contract.shared_proof_artifact_notes),
        }
        for option_id, contract in WORKFLOW_FAMILY_CONTRACTS.items()
    ]


def policy_id_for_option(option_id: str | None) -> str:
    if option_id is None:
        return WORKFLOW_CONTRACT_MATRIX_POLICY_ID
    contract = WORKFLOW_FAMILY_CONTRACTS.get(option_id)
    return contract.policy_id if contract is not None else WORKFLOW_CONTRACT_MATRIX_POLICY_ID


def default_workflow_option_provenance(
    selected_option_id: str,
    *,
    available_option_ids: list[str] | None = None,
) -> WorkflowOptionProvenance:
    options = available_option_ids or ([selected_option_id] if selected_option_id else [])
    contractable = [option_id for option_id in options if is_explicit_contract_supported(option_id)]
    return WorkflowOptionProvenance(
        selected_option_id=selected_option_id,
        selection_mode=WorkflowOptionSelectionMode.HEURISTIC_RECOMMENDATION,
        contract_status=WorkflowOptionContractStatus.ABSENT,
        available_option_ids=options,
        contractable_option_ids=contractable,
        policy_id=policy_id_for_option(selected_option_id),
        resolution_code=WorkflowOptionResolutionCode.NO_REQUEST,
        reason="No requested_workflow_option was supplied, so the planner used the heuristic recommendation.",
    )


def available_option_ids(workflow_options: list[WorkflowOption]) -> list[str]:
    return [option.option_id for option in workflow_options]


def contractable_option_ids(workflow_options: list[WorkflowOption]) -> list[str]:
    return [option_id for option_id in available_option_ids(workflow_options) if is_explicit_contract_supported(option_id)]


def is_explicit_contract_supported(option_id: str) -> bool:
    contract = WORKFLOW_FAMILY_CONTRACTS.get(option_id)
    return bool(contract and contract.supports_explicit_contract)


def resolve_requested_workflow_option(
    requested_option_id: str | None,
    workflow_options: list[WorkflowOption],
    recommended_option_id: str,
) -> tuple[str, WorkflowOptionProvenance]:
    option_ids = available_option_ids(workflow_options)
    supported_ids = contractable_option_ids(workflow_options)
    requested = (requested_option_id or "").strip() or None
    if requested is None:
        return recommended_option_id, default_workflow_option_provenance(
            recommended_option_id,
            available_option_ids=option_ids,
        )
    if requested not in option_ids:
        return (
            recommended_option_id,
            WorkflowOptionProvenance(
                requested_option_id=requested,
                selected_option_id=recommended_option_id,
                selection_mode=WorkflowOptionSelectionMode.HEURISTIC_RECOMMENDATION,
                contract_status=WorkflowOptionContractStatus.INCOMPATIBLE,
                available_option_ids=option_ids,
                contractable_option_ids=supported_ids,
                policy_id=policy_id_for_option(recommended_option_id),
                resolution_code=WorkflowOptionResolutionCode.REQUESTED_OPTION_NOT_AVAILABLE,
                reason=(
                    f"requested_workflow_option `{requested}` is incompatible with the current brief. "
                    f"Available workflow options: {', '.join(option_ids)}."
                ),
            ),
        )
    if requested not in supported_ids:
        contract = WORKFLOW_FAMILY_CONTRACTS.get(requested)
        explanation = contract.explanation if contract is not None and contract.explanation else "This workflow family is not yet supported as an explicit runtime contract."
        supported_label = ", ".join(supported_ids) if supported_ids else "none"
        return (
            recommended_option_id,
            WorkflowOptionProvenance(
                requested_option_id=requested,
                selected_option_id=recommended_option_id,
                selection_mode=WorkflowOptionSelectionMode.HEURISTIC_RECOMMENDATION,
                contract_status=WorkflowOptionContractStatus.INCOMPATIBLE,
                available_option_ids=option_ids,
                contractable_option_ids=supported_ids,
                policy_id=policy_id_for_option(recommended_option_id),
                resolution_code=WorkflowOptionResolutionCode.REQUESTED_OPTION_NOT_CONTRACTABLE,
                matrix_reason_code=contract.reason_code if contract is not None else None,
                next_step_requirements=list(contract.next_step_requirements) if contract is not None else [],
                reason=(
                    f"requested_workflow_option `{requested}` is not supported as an explicit workflow contract for this runtime. "
                    f"Supported explicit workflow options for this brief: {supported_label}. {explanation}"
                ),
            ),
        )
    return (
        requested,
        WorkflowOptionProvenance(
            requested_option_id=requested,
            selected_option_id=requested,
            selection_mode=WorkflowOptionSelectionMode.REQUESTED_CONTRACT,
            contract_status=WorkflowOptionContractStatus.HONORED,
            available_option_ids=option_ids,
            contractable_option_ids=supported_ids,
            policy_id=policy_id_for_option(requested),
            resolution_code=WorkflowOptionResolutionCode.REQUEST_HONORED,
            reason=f"Honored requested_workflow_option `{requested}` because it matches a supported explicit workflow contract for this brief.",
        ),
    )


def evaluate_content_plan_conformance(
    workflow_plan: WorkflowPlan,
    blueprint: Blueprint,
    proof_module_manifest: ProofModuleManifest | None = None,
    proof_unit_registry: ProofUnitRegistry | None = None,
) -> ContentPlanConformance:
    provenance = workflow_plan.workflow_option_provenance or default_workflow_option_provenance(
        workflow_plan.workflow_option,
        available_option_ids=[option.option_id for option in workflow_plan.workflow_options],
    )
    selected_option_id = str(getattr(blueprint, "chosen_workflow", workflow_plan.workflow_option))
    accepted_checks: list[str] = []
    failure_reasons: list[str] = []
    failure_codes: list[str] = []
    accepted_basis = [item for item in [provenance.reason] if item]

    if selected_option_id != workflow_plan.workflow_option:
        failure_codes.append("workflow-option-mismatch")
        failure_reasons.append(
            f"Blueprint chose `{selected_option_id}` but workflow_plan locked `{workflow_plan.workflow_option}`."
        )
    else:
        accepted_checks.append(f"Blueprint preserved the locked workflow option `{selected_option_id}`.")

    if provenance.contract_status == WorkflowOptionContractStatus.INCOMPATIBLE:
        failure_codes.append("requested-workflow-option-incompatible")
        failure_reasons.append(provenance.reason)
    elif provenance.requested_option_id is not None:
        if selected_option_id == provenance.requested_option_id:
            accepted_checks.append(f"Explicit workflow contract honored `{provenance.requested_option_id}`.")
        else:
            failure_codes.append("requested-workflow-option-not-honored")
            failure_reasons.append(
                f"Explicit workflow contract requested `{provenance.requested_option_id}` but CONTENT_PLAN selected `{selected_option_id}`."
            )
    else:
        accepted_checks.append("No explicit workflow contract was supplied; CONTENT_PLAN used the approved workflow plan.")

    main_budget = getattr(blueprint, "main_story_slide_budget", None)
    main_actual = getattr(blueprint, "main_story_actual_slide_count", None)
    if main_budget is not None and main_actual is not None:
        if main_budget.start <= main_actual <= main_budget.end:
            accepted_checks.append(f"Main-story slide count {main_actual} stays within the approved {main_budget.label()} budget.")
        else:
            failure_codes.append("main-story-budget-mismatch")
            failure_reasons.append(
                f"Main-story slide count {main_actual} falls outside the approved {main_budget.label()} budget."
            )

    appendix_budget = getattr(blueprint, "appendix_slide_budget", None)
    appendix_actual = getattr(blueprint, "appendix_actual_slide_count", None)
    if appendix_budget is not None and appendix_actual is not None:
        if appendix_budget.start <= appendix_actual <= appendix_budget.end:
            accepted_checks.append(f"Appendix slide count {appendix_actual} stays within the approved {appendix_budget.label()} budget.")
        else:
            failure_codes.append("appendix-budget-mismatch")
            failure_reasons.append(
                f"Appendix slide count {appendix_actual} falls outside the approved {appendix_budget.label()} budget."
            )

    contract = WORKFLOW_FAMILY_CONTRACTS.get(selected_option_id)
    required_sections = list(contract.required_sections) if contract is not None else []
    required_main_story_roles = list(contract.required_main_story_roles) if contract is not None else []
    if contract is not None and contract.supports_explicit_contract:
        contract_checks, contract_failures, contract_failure_codes = contract.evaluate(
            blueprint,
            proof_module_manifest=proof_module_manifest,
            proof_unit_registry=proof_unit_registry,
        )
        accepted_checks.extend(contract_checks)
        failure_reasons.extend(contract_failures)
        failure_codes.extend(contract_failure_codes)
        if contract.explanation:
            accepted_basis.append(contract.explanation)
    elif contract is not None and contract.explanation:
        accepted_basis.append(contract.explanation)

    return ContentPlanConformance(
        status=ContentPlanConformanceStatus.FAIL if failure_reasons else ContentPlanConformanceStatus.PASS,
        requested_option_id=provenance.requested_option_id,
        selected_option_id=selected_option_id,
        contract_status=provenance.contract_status,
        policy_id=contract.policy_id if contract is not None else policy_id_for_option(selected_option_id),
        required_sections=required_sections,
        required_main_story_roles=required_main_story_roles,
        accepted_checks=accepted_checks,
        failure_reasons=failure_reasons,
        failure_codes=failure_codes,
        accepted_basis=accepted_basis,
    )


def _main_story_roles(blueprint: Blueprint) -> set[str]:
    roles: set[str] = set()
    for slide in _main_story_slides(blueprint):
        slide_role = _slide_role_value(slide)
        if slide_role:
            roles.add(slide_role)
    return roles


def _main_story_slides(blueprint: Blueprint) -> list[object]:
    slides: list[object] = []
    for slide in getattr(blueprint, "slides", []):
        deck_mode = getattr(getattr(slide, "deck_mode", None), "value", getattr(slide, "deck_mode", ""))
        if str(deck_mode) == "main-story":
            slides.append(slide)
    return slides


def _non_appendix_sections(blueprint: Blueprint) -> list[str]:
    return [
        str(section.title)
        for section in getattr(blueprint, "story_architecture", [])
        if str(section.title).lower() != "appendix"
    ]


def _slide_role_value(slide: object) -> str | None:
    role = getattr(getattr(slide, "slide_role", None), "value", getattr(slide, "slide_role", None))
    if role is None:
        return None
    text = str(role).strip()
    return text or None
