"""Reconstructed state schema contracts for the non-PPTX runtime surface.

Recovered conservatively from import sites, example state artifacts, and the
focused compatibility tests that still lock the public contract.
"""

from __future__ import annotations

import ast
import json
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .contracts import COMPAT_STATE_SCHEMA_NAMES as _CONTRACT_COMPAT_STATE_SCHEMA_NAMES
from .contracts import STATE_SCHEMA_NAMES as _CONTRACT_STATE_SCHEMA_NAMES
from .contracts import WorkflowGate


ROOT = Path(__file__).resolve().parents[3]
PERSISTED_CONTINUITY_WARNING_MIRROR_DEPRECATION_BOUNDARY = "persisted-control-artifacts/v1"

STATE_SCHEMA_NAMES = tuple(_CONTRACT_STATE_SCHEMA_NAMES)
COMPAT_STATE_SCHEMA_NAMES = tuple(_CONTRACT_COMPAT_STATE_SCHEMA_NAMES)
COMPAT_ONLY_EXAMPLE_SCHEMAS = frozenset(COMPAT_STATE_SCHEMA_NAMES)


def _canonical_schema_name(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip().replace("-", "_") or None


def _slug_identifier(value: str | None) -> str | None:
    if value is None:
        return None
    compact = "".join(char.lower() if char.isalnum() else " " for char in value).split()
    if not compact:
        return None
    return "-".join(compact)


def _dedupe_strings(values: Iterable[object]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text and text not in seen:
            seen.add(text)
            ordered.append(text)
    return ordered


def _coerce_string_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return _dedupe_strings([value])
    if isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray, Mapping)):
        return _dedupe_strings(value)
    raise TypeError("expected a string or list-like collection of strings")


def _coerce_optional_iso_datetime_string(value: object) -> object:
    if value is None or isinstance(value, str):
        return value
    if isinstance(value, datetime):
        text = value.isoformat()
        if text.endswith("+00:00"):
            return f"{text[:-6]}Z"
        return text
    return value


def _parse_range_string(value: str) -> dict[str, int]:
    text = value.strip()
    if not text:
        raise ValueError("range string cannot be empty")
    if "-" in text:
        start_text, end_text = text.split("-", 1)
        return {"start": int(start_text), "end": int(end_text)}
    point = int(text)
    return {"start": point, "end": point}


def normalize_continuity_guidance_and_mirror(
    *,
    continuity_guidance: object | None = None,
    continuity_warnings: object | None = None,
) -> tuple[list[str], list[str]]:
    warnings = _coerce_string_list(continuity_warnings)
    if continuity_guidance is None:
        guidance = warnings
    elif isinstance(continuity_guidance, str):
        guidance = _coerce_string_list([continuity_guidance])
    elif isinstance(continuity_guidance, Mapping):
        guidance = warnings
    elif isinstance(continuity_guidance, Iterable) and not isinstance(continuity_guidance, (bytes, bytearray)):
        guidance = _coerce_string_list(continuity_guidance)
    else:
        guidance = warnings
    if not guidance and warnings:
        guidance = warnings
    mirror = list(guidance)
    return guidance, mirror


def _normalize_continuity_payload_fields(payload: Mapping[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    # PR-7.17 narrows the supported handoff compatibility boundary to this
    # guidance-first normalization path rather than raw mirror field presence on
    # repo-outside durable JSON readers. PR-7.18 then demotes newly written
    # handoff packets so older raw-mirror payloads stay compatible only through
    # this normalization seam.
    guidance, mirror = normalize_continuity_guidance_and_mirror(
        continuity_guidance=normalized.get("continuity_guidance"),
        continuity_warnings=normalized.get("continuity_warnings"),
    )
    normalized["continuity_guidance"] = guidance
    normalized["continuity_warnings"] = mirror
    return normalized


class LooseStrEnum(StrEnum):
    @classmethod
    def _missing_(cls, value: object):  # type: ignore[override]
        if not isinstance(value, str):
            return None
        obj = str.__new__(cls, value)
        obj._name_ = value.upper().replace("-", "_").replace(" ", "_").replace("/", "_")
        obj._value_ = value
        return obj


def _enum(name: str, members: dict[str, str]) -> type[LooseStrEnum]:
    return LooseStrEnum(name, members, module=__name__)


_ENUM_SPECS: dict[str, dict[str, str]] = {
    "ApplyDecisionStatus": {"APPLIED": "applied", "BLOCKED": "blocked", "DEFERRED": "deferred", "FAILED": "failed", "PENDING": "pending", "SKIPPED": "skipped"},
    "ApprovalDecisionStatus": {"APPROVED": "approved", "PENDING": "pending", "REJECTED": "rejected"},
    "AssetKind": {"DOCUMENT_CROP": "document-crop", "ICON": "icon", "IMAGE": "image", "LOGO": "logo", "REFERENCE": "reference", "STRUCTURED_VISUAL": "structured-visual"},
    "AssetPriority": {"CRITICAL": "critical", "HIGH": "high", "LOW": "low", "NORMAL": "normal"},
    "AssetStatus": {
        "APPROVED": "approved",
        "PENDING_REVIEW": "pending-review",
        "READY": "ready",
        "REJECTED": "rejected",
        "REQUESTED": "requested",
    },
    "BacklogItemType": {"BLOCKED_MANUAL": "blocked-manual", "FIX": "fix"},
    "BatchIntent": {"HYBRID": "hybrid", "NARRATIVE": "narrative", "QA_REMEDIATION": "qa-remediation"},
    "BatchMode": {"CONTINUITY_SENSITIVE": "continuity-sensitive", "SEQUENTIAL": "sequential"},
    "BriefMaterialType": {"DATA": "data", "DECK": "deck", "DOCUMENT": "document", "IMAGE": "image", "NOTES": "notes", "SPREADSHEET": "spreadsheet"},
    "ChartKind": {"BAR": "bar"},
    "ClosureReasonStatus": {"BLOCKED_MANUAL": "blocked-manual", "CLOSED_APPLIED": "closed-applied", "DEFERRED": "deferred", "FAILED_REVIEW_NEEDED": "failed-review-needed", "OBSOLETE_SUPERSEDED": "obsolete-superseded", "PENDING_APPROVAL": "pending-approval"},
    "CompileEligibility": {"ADVISORY_ONLY": "advisory-only", "ELIGIBLE": "eligible", "INELIGIBLE": "ineligible"},
    "ConceptEdgeType": {"ANALOGY_MAPPING": "analogy-mapping", "APPLICATION_OF": "application-of", "CONTRAST": "contrast", "LIMITATION_OF": "limitation-of", "MECHANISM": "mechanism", "PREREQUISITE": "prerequisite"},
    "ConceptType": {"APPLICATION": "application", "BIOLOGICAL_CONCEPT": "biological-concept", "GA_CONCEPT": "ga-concept", "LIMITATION": "limitation", "MAPPING_CONCEPT": "mapping-concept", "MATHEMATICAL_CONCEPT": "mathematical-concept", "OPERATOR_MECHANISM": "operator-mechanism", "OPTIMIZATION_CONCEPT": "optimization-concept", "PARAMETER_TRADEOFF": "parameter-tradeoff"},
    "ContentPlanConformanceStatus": {"FAIL": "fail", "PASS": "pass"},
    "ContentTier": {"APPENDIX_ONLY": "appendix-only", "LECTURE_CORE": "lecture-core", "SUPPORTING_EXAMPLE": "supporting-example"},
    "CropReviewAction": {"ACCEPT": "accept", "FALLBACK_TO_VISUAL": "fallback-to-visual", "REJECT": "reject", "REVISE": "revise"},
    "CycleStartStage": {"APPLY_APPROVED_FIXES": "apply-approved-fixes", "AUTHOR_UPSTREAM_FIXES": "author-upstream-fixes", "SHIP_DECK": "ship-deck"},
    "DeckHierarchyLevel": {"DECK": "deck", "PART": "part", "SECTION": "section", "SLIDE": "slide", "SLIDE_CLUSTER": "slide-cluster"},
    "DeckMode": {"APPENDIX": "appendix", "MAIN_STORY": "main-story", "MIXED": "mixed"},
    "DeliveryMode": {"ASYNC_READOUT": "async-readout", "DECISION_MEETING": "decision-meeting", "DEMO_SESSION": "demo-session", "LIVE_PRESENTATION": "live-presentation", "TRAINING_SESSION": "training-session", "WORKSHOP": "workshop"},
    "DeltaOperation": {"CHOOSE_ONE": "choose-one", "INSERT": "insert", "REMOVE": "remove", "REPLACE": "replace"},
    "FindingStatus": {"ACCEPTED": "accepted", "OPEN": "open", "RESOLVED": "resolved", "WAIVED": "waived"},
    "FixRiskLevel": {"HIGH": "high", "LOW": "low", "MEDIUM": "medium"},
    "FrameFit": {"FIT": "fit", "SPLIT_RECOMMENDED": "split-recommended", "TIGHT": "tight"},
    "GenerationInputMode": {"PROMPT_ONLY": "prompt-only", "REFERENCE_GROUNDED": "reference-grounded"},
    "LectureFamily": {"APPLICATION_COMPARISON": "application-comparison", "CONCEPT_TO_ALGORITHM_MAPPING": "concept-to-algorithm-mapping", "MECHANISM_PROCESS": "mechanism-process", "OPTIMIZATION_METHOD": "optimization-method"},
    "PacketApprovalMode": {"BUNDLE_REQUIRED": "bundle-required", "INDEPENDENT": "independent"},
    "PolicyEvidenceSource": {"COMPATIBILITY_ONLY": "compatibility-only", "NOT_YET_EVIDENCED": "not-yet-evidenced", "REPO_BACKED": "repo-backed"},
    "PolicyRuleOutcome": {"BLOCKED": "blocked", "PASS": "pass", "WARNING": "warning"},
    "PresentationArchetype": {"ARCHITECTURE": "architecture", "DECISION": "decision", "EXPLAINER": "explainer", "PITCH": "pitch", "PROCESS": "process", "REPORT": "report", "TIMELINE": "timeline", "TRAINING": "training"},
    "PresentationBrandMode": {"BRAND_CONSTRAINED": "brand-constrained", "GENERIC_PROFESSIONAL": "generic-professional", "INTERNAL_DEFAULT": "internal-default", "REFERENCE_ALIGNED": "reference-aligned"},
    "PresentationEvidenceDensity": {"HEAVY": "heavy", "LIGHT": "light", "MEDIUM": "medium"},
    "PresentationType": {"DECISION": "decision", "DEMO": "demo", "EXPLAINER": "explainer", "KEYNOTE": "keynote", "PERSUASION": "persuasion", "PITCH": "pitch", "REPORT": "report", "TRAINING": "training", "WORKSHOP": "workshop"},
    "PresentationVisualDensity": {"HIGH": "high", "LIGHT": "light", "MEDIUM": "medium"},
    "ProductionMode": {"HYBRID": "hybrid", "SOURCE_REUSE": "source-reuse", "STRUCTURED_VISUAL": "structured-visual"},
    "ProofCoverageClass": {"COMPARATIVE_SYNTHESIS": "comparative-synthesis", "DIRECT_EVIDENCE": "direct-evidence", "INTERPRETIVE_SYNTHESIS": "interpretive-synthesis", "QUANTITATIVE_EVIDENCE": "quantitative-evidence"},
    "ProofEvidenceOrigin": {"DATA": "data", "DOCUMENT": "document", "GENERATED": "generated", "MIXED": "mixed", "NOTES": "notes"},
    "ProofModuleStatus": {"INCOMPLETE": "incomplete", "INVALID": "invalid", "READY": "ready"},
    "QAFindingGovernanceDisposition": {"ACCEPTED_RISK": "accepted-risk", "REMEDIATED": "remediated", "UNRESOLVED": "unresolved", "WAIVED": "waived"},
    "QALayer": {"DECK": "deck", "OBJECT": "object", "SLIDE": "slide"},
    "QARecommendationType": {"FIX_NOW_BEFORE_SHIP": "fix-now-before-ship", "NEEDS_ASSET_REGENERATION": "needs-asset-regeneration", "NEEDS_FALLBACK_ROUTE": "needs-fallback-route", "NEEDS_LAYOUT_ADJUSTMENT": "needs-layout-adjustment", "NEEDS_UPSTREAM_CONTENT_CHANGE": "needs-upstream-content-change", "SAFE_TO_DEFER": "safe-to-defer"},
    "QARemediationStatus": {"CANNOT_FIX": "cannot-fix", "FIXED": "fixed", "VERIFIED": "verified", "WAIVED": "waived"},
    "QASeverity": {"CRITICAL": "critical", "INFO": "info", "MAJOR": "major", "MINOR": "minor"},
    "QAStatus": {"CONDITIONAL_PASS": "conditional-pass", "FAIL": "fail", "PASS": "pass"},
    "QAWaiverScope": {"FINDING_LEVEL": "finding-level", "SLIDE_LEVEL": "slide-level"},
    "QAWaiverStatus": {"ACTIVE": "active", "EXPIRED": "expired"},
    "ReadingDirection": {"CENTER_OUT": "center-out", "LEFT_TO_RIGHT": "left-to-right", "TOP_TO_BOTTOM": "top-to-bottom"},
    "ReferenceConfidenceBand": {"HIGH": "high", "LOW": "low", "MEDIUM": "medium"},
    "ReferenceScanMode": {"LOCAL_FIRST": "local-first"},
    "ReleaseReadinessPosture": {"OPERATOR_ENFORCED_EXCEPTION": "operator-enforced-exception", "REPO_BACKED_CLEAR": "repo-backed-clear", "UNRESOLVED_BLOCKING_ISSUE": "unresolved-blocking-issue"},
    "RemediationDisposition": {"BLOCK_SHIP": "block-ship", "FIX_BATCH_REQUIRED": "fix-batch-required", "SAFE_TO_DEFER": "safe-to-defer", "TRIGGER_REBUILD": "trigger-rebuild"},
    "RemediationExecutionAction": {"APPLY_KNOWN_FALLBACK": "apply-known-fallback", "DROP_BLOCKED_DENSE_VISUAL": "drop-blocked-dense-visual", "MARK_BLOCKED": "mark-blocked", "MARK_DEFERRED": "mark-deferred", "MARK_REQUIRES_UPSTREAM_CHANGE": "mark-requires-upstream-change", "PROMOTE_EXISTING_ALTERNATE_ASSET": "promote-existing-alternate-asset", "PROMOTE_SIMPLIFIED_STRUCTURED_VISUAL": "promote-simplified-structured-visual", "RERUN_COMPILER": "rerun-compiler", "RERUN_QA": "rerun-qa", "SYNC_STATUS_ONLY": "sync-status-only"},
    "RemediationExecutionStatus": {"APPLIED": "applied", "BLOCKED": "blocked", "DEFERRED": "deferred", "FAILED": "failed", "SKIPPED": "skipped"},
    "RemediationOwner": {"COMPILER_LAYOUT": "compiler-layout", "CROP_SOURCE_ASSET": "crop-source-asset", "QA_THRESHOLD_POLICY": "qa-threshold-policy", "STRUCTURED_VISUAL": "structured-visual", "UPSTREAM_CONTENT_STORY": "upstream-content-story"},
    "RemediationScope": {"DECK_LEVEL_REFLOW": "deck-level-reflow", "LOCAL_CHANGE_ONLY": "local-change-only", "SECTION_LEVEL_REFLOW": "section-level-reflow"},
    "RenderAdapter": {"DOCX": "docx", "PDF": "pdf", "RASTER_IMAGE": "raster-image"},
    "ScaleMode": {"COMPACT": "compact", "EXTENDED": "extended", "LARGE_DECK": "large-deck", "MEGA_DECK": "mega-deck", "STANDARD": "standard"},
    "ShipReadinessDecision": {"BLOCKED_MANUAL": "blocked-manual", "NEEDS_NEXT_BOUNDED_CYCLE": "needs-next-bounded-cycle", "READY_TO_SHIP": "ready-to-ship", "READY_TO_SHIP_WITH_NON_BLOCKING_BACKLOG": "ready-to-ship-with-non-blocking-backlog"},
    "SlideArchetype": {"ANCHOR_CONCEPT_CARD": "anchor-concept-card", "APPENDIX_ANNOTATED_EXCERPT_CLUSTER": "appendix-annotated-excerpt-cluster", "APPENDIX_COMPARISON_EVIDENCE_CLUSTER": "appendix-comparison-evidence-cluster", "APPENDIX_EVIDENCE_CLUSTER": "appendix-evidence-cluster", "APPENDIX_SOURCE_LOCATION_MATRIX": "appendix-source-location-matrix", "APPENDIX_SOURCE_MAP": "appendix-source-map", "APPENDIX_THEMED_EVIDENCE_CLUSTER": "appendix-themed-evidence-cluster", "APPLICATION_VIGNETTE": "application-vignette", "COMPARISON_MATRIX": "comparison-matrix", "CORRESPONDENCE_MATRIX": "correspondence-matrix", "LIMITATION_PITFALL_CALLOUT": "limitation-pitfall-callout", "PROCESS_FLOW": "process-flow", "STEP_BY_STEP_MECHANISM": "step-by-step-mechanism", "SYNTHESIS_INTEGRATION": "synthesis-integration", "TITLE_ORIENTATION": "title-orientation", "TWO_COLUMN_MAPPING_TABLE": "two-column-mapping-table", "WORKED_EXAMPLE_STATE_TABLE": "worked-example-state-table"},
    "SlideEvidenceClass": {"APPENDIX_SUPPORT": "appendix-support", "DATA_BACKED": "data-backed", "MESSAGE_ONLY": "message-only", "SOURCE_BACKED": "source-backed", "STRUCTURED_LOGIC": "structured-logic", "VISUAL_DEMONSTRATION": "visual-demonstration"},
    "SlideFunction": {"AGENDA": "agenda", "ARCHITECTURE": "architecture", "COMPARE": "compare", "KPI": "kpi", "PROCESS": "process", "SECTION_DIVIDER": "section-divider", "SUMMARY": "summary", "TIMELINE": "timeline", "TITLE": "title"},
    "SlideIntent": {"ANCHOR_CONCEPT": "anchor-concept", "APPENDIX_EVIDENCE_SUPPORT": "appendix-evidence-support", "APPLICATION_VIGNETTE": "application-vignette", "COMPARISON_TRADEOFF": "comparison-tradeoff", "CONCEPT_UNPACKING": "concept-unpacking", "MAPPING_BRIDGE": "mapping-bridge", "MECHANISM_WALKTHROUGH": "mechanism-walkthrough", "MISCONCEPTION_PITFALL": "misconception-pitfall", "ORIENTATION": "orientation", "SUMMARY_INTEGRATION": "summary-integration", "WORKED_EXAMPLE": "worked-example"},
    "SlideRole": {"ANALYSIS": "analysis", "APPENDIX_EVIDENCE": "appendix-evidence", "COMPARISON": "comparison", "EVIDENCE": "evidence", "EXECUTIVE_SUMMARY": "executive-summary", "INFOGRAPHIC": "infographic", "PROCESS": "process", "RECOMMENDATION": "recommendation", "REFERENCES": "references", "SECTION_DIVIDER": "section-divider", "TITLE": "title"},
    "StageStatus": {"APPROVED": "approved", "BLOCKED": "blocked", "COMPLETE": "complete", "DRAFT": "draft", "IN_PROGRESS": "in-progress", "READY": "ready"},
    "TableAlignment": {"CENTER": "center", "LEFT": "left"},
    "UpstreamArtifactName": {"ASSET_REQUESTS": "asset-requests", "BLUEPRINT": "blueprint", "DECK_CONSTITUTION": "deck-constitution", "DESIGN_SYSTEM": "design-system", "LAYOUT_LIBRARY": "layout-library", "SLIDE_LEDGER": "slide-ledger", "VIZ_SPEC": "viz-spec"},
    "VisualSourcePreference": {"DOCUMENT_CROP": "document-crop", "EITHER": "either", "EXISTING_ASSET": "existing-asset", "STRUCTURED_VISUAL": "structured-visual"},
    "VisualType": {"CHART": "chart", "COMPARISON": "comparison", "DECISION_PATH": "decision-path", "DOCUMENT_CROP": "document-crop", "FRAMEWORK": "framework", "HIERARCHY": "hierarchy", "INFOGRAPHIC": "infographic", "METRIC_SUMMARY": "metric-summary", "PHOTO": "photo", "PROCESS": "process", "QUOTE": "quote", "TABLE": "table", "TEXT": "text", "TIMELINE": "timeline"},
    "VizDensityBand": {"HIGH": "high", "LOW": "low", "MEDIUM": "medium"},
    "VizStatus": {"APPROVED": "approved", "REJECTED": "rejected", "RENDERED": "rendered"},
    "WorkflowOptionContractStatus": {"ABSENT": "absent", "HONORED": "honored", "INCOMPATIBLE": "incompatible"},
    "WorkflowOptionResolutionCode": {"NO_REQUEST": "no-request", "REQUESTED_OPTION_NOT_AVAILABLE": "requested-option-not-available", "REQUESTED_OPTION_NOT_CONTRACTABLE": "requested-option-not-contractable", "REQUEST_HONORED": "request-honored"},
    "WorkflowOptionSelectionMode": {"HEURISTIC_RECOMMENDATION": "heuristic-recommendation", "REQUESTED_CONTRACT": "requested-contract"},
}

globals().update({name: _enum(name, members) for name, members in _ENUM_SPECS.items()})


class ContractModel(BaseModel):
    model_config = ConfigDict(
        extra="allow",
        populate_by_name=True,
        arbitrary_types_allowed=True,
        ignored_types=(str,),
    )

    def to_payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=True)


class SchemaModel(ContractModel):
    schema_name: str | None = None
    schema_version: str = "1.0"

    @model_validator(mode="before")
    @classmethod
    def _populate_schema_name(cls, value: object) -> object:
        if isinstance(value, Mapping):
            payload = dict(value)
            if not payload.get("schema_name"):
                schema_name = getattr(cls, "SCHEMA_NAME", None)
                if isinstance(schema_name, str) and schema_name.strip():
                    payload["schema_name"] = schema_name.strip()
            return payload
        return value

    @model_validator(mode="after")
    def _require_schema_name(self) -> "SchemaModel":
        if not self.schema_name:
            schema_name = getattr(type(self), "SCHEMA_NAME", None)
            if isinstance(schema_name, str) and schema_name.strip():
                self.schema_name = schema_name.strip()
        if not self.schema_name:
            raise ValueError("schema_name is required")
        return self


BaseState = SchemaModel


class SlideRange(ContractModel):
    start: int
    end: int

    @model_validator(mode="before")
    @classmethod
    def _coerce_input(cls, value: object) -> object:
        if isinstance(value, str):
            return _parse_range_string(value)
        return value

    @model_validator(mode="after")
    def _validate_bounds(self) -> "SlideRange":
        if self.end < self.start:
            raise ValueError("end must be greater than or equal to start")
        return self

    @classmethod
    def from_value(cls, value: "SlideRange | Mapping[str, Any] | str | None") -> "SlideRange | None":
        if value is None:
            return None
        if isinstance(value, SlideRange):
            return value
        return cls.model_validate(value)

    def label(self) -> str:
        return str(self.start) if self.start == self.end else f"{self.start}-{self.end}"


class CountRange(SlideRange):
    pass


class StateFilePointer(ContractModel):
    schema_name: str
    path: str
    required: bool = False


class ProjectMaterial(ContractModel):
    label: str
    material_type: BriefMaterialType
    path: str
    notes: str | None = None


class SourceMaterialRef(ContractModel):
    source_id: str
    label: str
    path: str
    page: int | None = None


class ProjectSnapshot(ContractModel):
    topic: str
    audience: list[str] = Field(default_factory=list)
    purpose: str
    delivery_mode: DeliveryMode
    expected_duration_minutes: int | None = None
    expected_scale_hint: str | None = None
    current_materials: list[ProjectMaterial] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class PresentationTypeDiagnosis(ContractModel):
    primary_type: PresentationType
    secondary_types: list[PresentationType] = Field(default_factory=list)
    diagnosis_label: str
    reasoning: list[str] = Field(default_factory=list)


class WorkflowPhase(ContractModel):
    phase_id: str
    label: str
    objective: str
    expected_outputs: list[str] = Field(default_factory=list)


class WorkflowOption(ContractModel):
    option_id: str
    label: str
    summary: str
    main_story_slide_count_range: CountRange
    appendix_candidate_slide_count_range: CountRange
    when_it_fits_best: list[str] = Field(default_factory=list)
    phases: list[WorkflowPhase] = Field(default_factory=list)
    expected_outputs: list[str] = Field(default_factory=list)
    benefits: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    fit_rationale: list[str] = Field(default_factory=list)
    tradeoffs: list[str] = Field(default_factory=list)


class WorkflowOptionProvenance(ContractModel):
    selected_option_id: str
    selection_mode: WorkflowOptionSelectionMode
    contract_status: WorkflowOptionContractStatus
    available_option_ids: list[str] = Field(default_factory=list)
    contractable_option_ids: list[str] = Field(default_factory=list)
    policy_id: str | None = None
    resolution_code: WorkflowOptionResolutionCode
    next_step_requirements: list[str] = Field(default_factory=list)
    reason: str | None = None


class GateStatus(ContractModel):
    gate: WorkflowGate
    status: StageStatus


class SlideContentBudget(ContractModel):
    slide_function: SlideFunction | str | None = None
    max_bullets: int | None = None
    max_words: int | None = None


class WorkflowPlan(SchemaModel):
    schema_name: str = "workflow_plan"
    request_id: str
    deck_title: str
    objective: str
    project_snapshot: ProjectSnapshot
    presentation_type_diagnosis: PresentationTypeDiagnosis
    workflow_option: str
    workflow_option_provenance: WorkflowOptionProvenance
    optimal_slide_count_range: CountRange
    smallest_effective_slide_count: int
    main_story_slide_count_range: CountRange
    appendix_candidate_slide_count_range: CountRange
    workflow_options: list[WorkflowOption] = Field(default_factory=list)
    audience: list[str] = Field(default_factory=list)
    deck_mode: DeckMode | None = None
    scale_mode: ScaleMode | None = None
    slide_ratio: str | None = None
    gates: list[GateStatus] = Field(default_factory=list)
    content_budgets: list[SlideContentBudget] = Field(default_factory=list)


class CommunicationCore(ContractModel):
    pass


class VisualRoute(ContractModel):
    route_id: str
    label: str
    description: str | None = None


class VerificationPoint(ContractModel):
    pass


class StorySection(ContractModel):
    section_id: str
    title: str
    purpose: str | None = None
    deck_mode: DeckMode | None = None
    slide_count_range: CountRange | None = None
    slide_roles: list[SlideRole] = Field(default_factory=list)


class VisualReferenceSummary(ContractModel):
    pass


class InfographicPlanItem(ContractModel):
    pass


class EvidencePlanItem(ContractModel):
    pass


class StoryArchitectureSummary(ContractModel):
    pass


class SlideDensityBudget(ContractModel):
    text_char_ceiling: int = 560
    bullet_count_ceiling: int = 3
    visual_node_ceiling: int = 6
    evidence_item_ceiling: int = 2
    layout_slot_count: int = 0


class ProductionBridge(ContractModel):
    visual_source_preference: VisualSourcePreference
    source_material_refs: list[SourceMaterialRef] = Field(default_factory=list)
    crop_subject_hint: str | None = None
    fallback_visual: VisualType | None = None
    production_mode: ProductionMode


class BlueprintSlide(ContractModel):
    slide_number: int
    section: str
    slide_role: SlideRole
    slide_intent: SlideIntent | None = None
    title: str
    one_line_takeaway: str
    main_message: str
    pedagogical_goal: str | None = None
    concept_ids: list[str] = Field(default_factory=list)
    visual_type: VisualType
    layout_pattern_id: str
    production_bridge: ProductionBridge
    deck_mode: DeckMode = DeckMode.MAIN_STORY
    content_tier: ContentTier | str | None = None
    audience_intent: str | None = None
    primary_claim: str | None = None
    supporting_evidence: list[str] = Field(default_factory=list)
    evidence_class: SlideEvidenceClass = SlideEvidenceClass.MESSAGE_ONLY
    must_keep_text: list[str] = Field(default_factory=list)
    optional_text: list[str] = Field(default_factory=list)
    visual_intent: str | None = None
    density_budget: SlideDensityBudget = Field(default_factory=SlideDensityBudget)
    risk_flags: list[str] = Field(default_factory=list)
    qa_acceptance_hints: list[str] = Field(default_factory=list)
    slide_archetype: SlideArchetype | None = None
    chosen_layout_family: str | None = None
    primary_visual_structure: str | None = None
    chrome_blocks_used: list[str] = Field(default_factory=list)
    content_budget_summary: dict[str, Any] = Field(default_factory=dict)
    duplicate_text_flags: list[str] = Field(default_factory=list)
    authoring_payload: dict[str, Any] = Field(default_factory=dict)
    core_content: list[str] = Field(default_factory=list)
    verification_flags: list[str] = Field(default_factory=list)
    required_evidence_assets: list[str] = Field(default_factory=list)
    presenter_notes: str | None = None
    slide_id: str | None = None
    section_id: str | None = None
    part_id: str | None = None
    cluster_id: str | None = None
    lineage_id: str | None = None
    layout_slot_map: dict[str, str] = Field(default_factory=dict)

    @field_validator("main_message")
    @classmethod
    def _single_line_main_message(cls, value: str) -> str:
        if "\n" in value:
            raise ValueError("main_message must be a single line")
        return value

    @model_validator(mode="after")
    def _populate_compile_defaults(self) -> "BlueprintSlide":
        if self.content_tier is None:
            self.content_tier = (
                ContentTier.APPENDIX_ONLY if self.deck_mode == DeckMode.APPENDIX else ContentTier.LECTURE_CORE
            )
        if self.section_id is None:
            self.section_id = _slug_identifier(self.section)
        original_layout_pattern_id = self.layout_pattern_id
        if original_layout_pattern_id == "cover":
            self.chosen_layout_family = self.chosen_layout_family or "cover"
            self.layout_pattern_id = "cover-signal"
        elif original_layout_pattern_id == "worked-example":
            self.chosen_layout_family = self.chosen_layout_family or "worked-example"
            if self.visual_type == VisualType.CHART:
                self.layout_pattern_id = "title-chart-insight"
            elif self.visual_type in {VisualType.TABLE, VisualType.COMPARISON}:
                self.layout_pattern_id = "evidence-table"
            elif self.visual_type in {VisualType.PROCESS, VisualType.TIMELINE, VisualType.DECISION_PATH}:
                self.layout_pattern_id = "process-flow"
            else:
                self.layout_pattern_id = "title-visual-caption"
        elif original_layout_pattern_id == "summary":
            self.chosen_layout_family = self.chosen_layout_family or "summary"
            self.layout_pattern_id = "headline-evidence"
        elif original_layout_pattern_id == "section-divider":
            self.chosen_layout_family = self.chosen_layout_family or "section-divider"
            self.layout_pattern_id = "section-divider-band"
        elif original_layout_pattern_id == "definition-theorem":
            self.chosen_layout_family = self.chosen_layout_family or "definition-theorem"
            self.layout_pattern_id = "title-thesis-body"
        elif original_layout_pattern_id == "comparison":
            self.chosen_layout_family = self.chosen_layout_family or "comparison"
            self.layout_pattern_id = "evidence-table"

        if self.primary_claim is None:
            self.primary_claim = self.main_message
        if self.audience_intent is None:
            self.audience_intent = self.one_line_takeaway
        if not self.must_keep_text:
            self.must_keep_text = [self.title, self.one_line_takeaway, self.main_message]
        if not self.core_content:
            self.core_content = [self.main_message]
        if not self.visual_intent:
            self.visual_intent = self.visual_type.value
        if not self.layout_slot_map:
            slot_map: dict[str, str] = {"title": "header", "claim": "header"}
            if self.slide_role in {SlideRole.TITLE, SlideRole.SECTION_DIVIDER}:
                slot_map["supporting_text"] = "body-1"
            elif self.visual_type in {VisualType.TEXT, VisualType.QUOTE}:
                slot_map["supporting_text"] = "body-1"
                if self.supporting_evidence and self.deck_mode == DeckMode.APPENDIX:
                    slot_map["evidence_marker"] = "body-1"
            else:
                single_body_layout = self.layout_pattern_id in {"evidence-table", "process-flow"}
                slot_map["primary_visual"] = "body-1"
                if single_body_layout and (self.core_content or self.supporting_evidence or self.deck_mode == DeckMode.APPENDIX):
                    slot_map["supporting_text"] = "body-1"
                elif self.core_content or self.supporting_evidence or self.deck_mode == DeckMode.APPENDIX:
                    slot_map["supporting_text"] = "body-2"
                if self.supporting_evidence:
                    slot_map["evidence_marker"] = "body-1" if single_body_layout else "body-2"
            self.layout_slot_map = slot_map
        if self.density_budget.layout_slot_count == 0:
            self.density_budget.layout_slot_count = len(set(self.layout_slot_map.values())) or len(self.layout_slot_map)
        if self.deck_mode == DeckMode.APPENDIX:
            self.density_budget.text_char_ceiling = max(self.density_budget.text_char_ceiling, 720)
            self.density_budget.bullet_count_ceiling = max(self.density_budget.bullet_count_ceiling, 5)
            self.density_budget.visual_node_ceiling = max(self.density_budget.visual_node_ceiling, 8)
            self.density_budget.evidence_item_ceiling = max(self.density_budget.evidence_item_ceiling, 3)
        if self.visual_type in {VisualType.TEXT, VisualType.QUOTE}:
            self.density_budget.text_char_ceiling = max(self.density_budget.text_char_ceiling, 640)
            self.density_budget.bullet_count_ceiling = max(self.density_budget.bullet_count_ceiling, 4)
        if self.visual_type in {VisualType.TABLE, VisualType.CHART, VisualType.COMPARISON}:
            self.density_budget.text_char_ceiling = max(self.density_budget.text_char_ceiling, 660)
            self.density_budget.visual_node_ceiling = max(self.density_budget.visual_node_ceiling, 8)
        if self.visual_type in {VisualType.FRAMEWORK, VisualType.PROCESS, VisualType.TIMELINE, VisualType.INFOGRAPHIC}:
            self.density_budget.text_char_ceiling = min(self.density_budget.text_char_ceiling, 520 if self.deck_mode != DeckMode.APPENDIX else 680)
        self.density_budget.bullet_count_ceiling = max(self.density_budget.bullet_count_ceiling, len(self.core_content))
        self.density_budget.evidence_item_ceiling = max(self.density_budget.evidence_item_ceiling, len(self.supporting_evidence))
        return self


class Blueprint(SchemaModel):
    schema_name: str = "blueprint"
    deck_title: str
    chosen_workflow: str
    lecture_family: LectureFamily | None = None
    presentation_brief: PresentationBrief | None = None
    canonical_generation_profile: CanonicalGenerationProfile | None = None
    slide_function_outline: SlideFunctionOutline | None = None
    communication_core: CommunicationCore
    recommended_route: str
    visual_routes: list[VisualRoute] = Field(default_factory=list)
    story_architecture: list[StorySection] = Field(default_factory=list)
    story_structure: ContractModel | dict[str, Any] | None = None
    deck_mode: DeckMode | str | None = None
    slide_ratio: str | None = None
    approval_status: StageStatus | str | None = None
    visual_reference_summary: VisualReferenceSummary | None = None
    recommended_route_reason: str | None = None
    infographic_plan: list[InfographicPlanItem] = Field(default_factory=list)
    evidence_asset_plan: list[EvidencePlanItem] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    verification_points: list[VerificationPoint] = Field(default_factory=list)
    slides: list[BlueprintSlide] = Field(default_factory=list)
    appendix_start: int | None = None
    main_story_slide_budget: CountRange | None = None
    appendix_slide_budget: CountRange | None = None
    main_story_actual_slide_count: int | None = None
    appendix_actual_slide_count: int | None = None

    @model_validator(mode="after")
    def _validate_visual_routes(self) -> "Blueprint":
        if not self.visual_routes:
            raise ValueError("visual_routes must remain present")
        return self


class DesignSystem(SchemaModel):
    schema_name: str = "design_system"
    deck_title: str
    theme_name: str
    visual_route_id: str
    section_divider_style: str
    layout_rules: list[str] = Field(default_factory=list)
    visual_system_rules: list[str] = Field(default_factory=list)
    color_tokens: list["ColorToken"] = Field(default_factory=list)
    typography_tokens: list["TypographyToken"] = Field(default_factory=list)
    chart_rules: list[str] = Field(default_factory=list)
    table_rules: list[str] = Field(default_factory=list)
    screenshot_rules: list[str] = Field(default_factory=list)
    highlight_rules: list[str] = Field(default_factory=list)
    callout_method: str | None = None
    title_rules: list[str] = Field(default_factory=list)
    visual_families: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_title_rules(self) -> "DesignSystem":
        if not self.title_rules:
            raise ValueError("title_rules must remain present")
        return self


class ColorToken(ContractModel):
    token: str
    hex: str | None = None
    usage: str | None = None


class TypographyToken(ContractModel):
    token: str
    font_family: str | None = None
    size_pt: float | None = None
    weight: str | None = None
    usage: str | None = None


class LayoutPattern(ContractModel):
    pass


class LayoutLibrary(SchemaModel):
    schema_name: str = "layout_library"
    deck_title: str | None = None
    patterns: list[LayoutPattern] = Field(default_factory=list)


class DeckConstitution(SchemaModel):
    schema_name: str = "deck_constitution"
    deck_title: str | None = None
    appendix_boundary_rule: str | None = None
    terminology_rules: list[str] = Field(default_factory=list)
    title_rules: list[str] = Field(default_factory=list)
    numbering_rules: list[str] = Field(default_factory=list)
    section_divider_rules: list[str] = Field(default_factory=list)


class SlideLedgerEntry(ContractModel):
    slide_number: int
    slide_id: str
    slide_role: SlideRole
    title: str
    final_title: str | None = None
    one_line_takeaway: str
    main_message: str
    section: str
    deck_mode: DeckMode
    content_tier: ContentTier | str | None = None
    visual_type: VisualType
    visual_source_preference: VisualSourcePreference
    production_mode: ProductionMode
    layout_pattern_id: str
    part_id: str | None = None
    section_id: str | None = None
    cluster_id: str | None = None
    lineage_id: str | None = None
    batch_id: str | None = None
    depends_on: list[int] = Field(default_factory=list)
    change_note: str | None = None
    unresolved_blockers: list[str] | None = None
    required_evidence_assets: list[str] = Field(default_factory=list)
    asset_request_ids: list[str] = Field(default_factory=list)
    asset_dependency_kinds: list[AssetKind] = Field(default_factory=list)
    blueprint_status: StageStatus | None = None
    asset_status: StageStatus | None = None
    compile_status: StageStatus | None = None
    qa_status: QAStatus | None = None

    @field_validator("depends_on", mode="before")
    @classmethod
    def _coerce_depends_on(cls, value: object) -> object:
        if value is None:
            return []
        if isinstance(value, Iterable) and not isinstance(value, (str, bytes, bytearray, Mapping)):
            return [int(item) for item in value]
        return value

    @model_validator(mode="after")
    def _populate_lineage_defaults(self) -> "SlideLedgerEntry":
        if self.lineage_id is None:
            self.lineage_id = self.slide_id
        if self.final_title is None:
            self.final_title = self.title
        if self.section_id is None:
            self.section_id = _slug_identifier(self.section)
        if self.content_tier is None:
            self.content_tier = (
                ContentTier.APPENDIX_ONLY if self.deck_mode == DeckMode.APPENDIX else ContentTier.LECTURE_CORE
            )
        return self


class SlideLedger(SchemaModel):
    schema_name: str = "slide_ledger"
    deck_title: str
    entries: list[SlideLedgerEntry] = Field(default_factory=list)
    continuity_notes: list[str] = Field(default_factory=list)


class CropBounds(ContractModel):
    left: float
    top: float
    width: float
    height: float


class AssetRenderSettings(ContractModel):
    adapter: RenderAdapter | str
    dpi: int | None = None
    image_format: str | None = None


class AssetProvenance(ContractModel):
    source_file: str
    slide_id: str | None = None
    page_number: int | None = None
    candidate_id: str | None = None
    render_settings: AssetRenderSettings | None = None
    crop_box: CropBounds | None = None
    limitations: list[str] = Field(default_factory=list)


class AssetRequest(ContractModel):
    request_id: str
    slide_number: int
    slide_id: str
    slide_message: str
    asset_kind: AssetKind
    priority: AssetPriority
    brief: str
    required_visual_type: VisualType
    visual_type: VisualType
    visual_source_preference: VisualSourcePreference
    source_material_refs: list[SourceMaterialRef] = Field(default_factory=list)
    preferred_source_doc: str | None = None
    page_hint: int | None = None
    crop_subject_hint: str | None = None
    fallback_visual: VisualType | None = None
    fallback_ladder: list[VisualType] = Field(default_factory=list)
    approval_status: StageStatus | None = None
    production_mode: ProductionMode
    asset_quality_requirements: list[str] = Field(default_factory=list)
    allowed_crop_review_actions: list[CropReviewAction] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_crop_request(self) -> "AssetRequest":
        valid_priorities = {member.value for member in AssetPriority}
        priority_value = str(getattr(self.priority, "value", self.priority))
        if priority_value not in valid_priorities:
            raise ValueError("priority must be a supported asset priority")
        valid_actions = {member.value for member in CropReviewAction}
        for action in self.allowed_crop_review_actions:
            action_value = str(getattr(action, "value", action))
            if action_value not in valid_actions:
                raise ValueError("allowed_crop_review_actions contains an unsupported action")
        if AssetKind(self.asset_kind) == AssetKind.DOCUMENT_CROP and not self.allowed_crop_review_actions:
            raise ValueError("document crop requests require allowed_crop_review_actions")
        return self


class AssetRequests(SchemaModel):
    schema_name: str = "asset_requests"
    deck_title: str | None = None
    requests: list[AssetRequest] = Field(default_factory=list)


class AssetRecord(ContractModel):
    asset_id: str | None = None
    request_id: str | None = None
    slide_number: int | None = None
    slide_id: str | None = None
    asset_kind: AssetKind | None = None
    status: AssetStatus | None = None
    local_path: str | None = None
    visual_source_preference: VisualSourcePreference | None = None
    source_material_refs: list[SourceMaterialRef] = Field(default_factory=list)
    crop_subject_hint: str | None = None
    fallback_visual: VisualType | None = None
    production_mode: ProductionMode | None = None
    review_action: CropReviewAction | None = None
    crop_bounds: CropBounds | None = None
    candidate_id: str | None = None
    render_settings: AssetRenderSettings | None = None
    provenance: AssetProvenance | None = None
    notes: str | None = None
    limitations: list[str] = Field(default_factory=list)


class AssetManifest(SchemaModel):
    schema_name: str = "asset_manifest"
    deck_title: str | None = None
    assets: list[AssetRecord] = Field(default_factory=list)


class VizChartSeries(ContractModel):
    series_id: str
    label: str
    values: list[float] = Field(default_factory=list)
    color_token: str | None = None


class VizChartData(ContractModel):
    chart_kind: ChartKind
    categories: list[str] = Field(default_factory=list)
    series: list[VizChartSeries] = Field(default_factory=list)
    unit_label: str | None = None
    direct_labels: bool | None = None


class VizMetricSummaryData(ContractModel):
    pass


class VizTableColumn(ContractModel):
    key: str
    label: str
    alignment: TableAlignment = TableAlignment.LEFT


class VizTableRow(ContractModel):
    values: dict[str, Any] = Field(default_factory=dict)


class VizTableData(ContractModel):
    columns: list[VizTableColumn] = Field(default_factory=list)
    rows: list[VizTableRow] = Field(default_factory=list)


class VizStyleProfile(ContractModel):
    pass


class VizReadability(ContractModel):
    reading_path: str
    node_count: int
    label_count: int
    frame_fit: FrameFit
    simplified: bool


class VizSpec(ContractModel):
    spec_id: str
    slide_number: int
    title: str
    message: str
    visual_type: VisualType
    layout_pattern_id: str
    visual_source_preference: VisualSourcePreference
    source_material_refs: list[SourceMaterialRef] = Field(default_factory=list)
    fallback_visual: VisualType | None = None
    production_mode: ProductionMode
    deck_title: str | None = None
    slide_id: str | None = None
    crop_subject_hint: str | None = None
    chart: VizChartData | None = None
    table: VizTableData | None = None
    style_tokens: list[str] = Field(default_factory=list)
    style_profile: VizStyleProfile | None = None
    data_contract: list[str] = Field(default_factory=list)
    readability: VizReadability | None = None
    simpler_variant: str | None = None

    @model_validator(mode="after")
    def _validate_visual_contract(self) -> "VizSpec":
        valid_visual_types = {member.value for member in VisualType}
        visual_value = str(getattr(self.visual_type, "value", self.visual_type))
        if visual_value not in valid_visual_types:
            raise ValueError("visual_type must be a supported visual type")
        if VisualType(self.visual_type) == VisualType.CHART and self.chart is None:
            raise ValueError("chart visuals require chart data")
        if VisualSourcePreference(self.visual_source_preference) == VisualSourcePreference.EXISTING_ASSET and not self.source_material_refs:
            raise ValueError("existing-asset visual preference requires source_material_refs")
        return self


class VizSpecSet(SchemaModel):
    schema_name: str = "viz_spec"
    deck_title: str
    specs: list[VizSpec] = Field(default_factory=list)


class VizRecord(ContractModel):
    spec: VizSpec
    status: VizStatus | None = None
    output_path: str | None = None
    fallback_output_path: str | None = None
    data_output_path: str | None = None
    applied_color_tokens: list[str] = Field(default_factory=list)
    applied_typography_tokens: list[str] = Field(default_factory=list)
    notes: str | None = None


class VizManifest(SchemaModel):
    schema_name: str = "viz_manifest"
    deck_title: str
    visuals: list[VizRecord] = Field(default_factory=list)


class DeckHierarchyNode(ContractModel):
    node_id: str
    level: DeckHierarchyLevel
    title: str
    slide_range: SlideRange
    deck_mode: DeckMode | None = None
    child_ids: list[str] = Field(default_factory=list)
    parent_id: str | None = None
    batch_id: str | None = None


class ContextLockDecision(ContractModel):
    decision_key: str
    locked_value: str
    rationale: str
    affected_batches: list[str] = Field(default_factory=list)
    updated_at: str | None = None


class LockedDesignSystem(ContractModel):
    theme_name: str | None = None
    visual_route_id: str | None = None
    color_tokens: list[str] = Field(default_factory=list)
    typography_tokens: list[str] = Field(default_factory=list)
    section_divider_style: str | None = None
    chart_rules: list[str] = Field(default_factory=list)
    table_rules: list[str] = Field(default_factory=list)
    highlight_rules: list[str] = Field(default_factory=list)


class BatchBoundaryContinuityAlert(ContractModel):
    alert_id: str
    source_batch_id: str
    target_batch_id: str
    boundary_slide_range: str | SlideRange
    summary: str
    terminology_change_rate: float = 0.0
    numbering_change_rate: float = 0.0
    design_token_change_rate: float = 0.0
    warning_codes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_rates(self) -> "BatchBoundaryContinuityAlert":
        for field_name in ("terminology_change_rate", "numbering_change_rate", "design_token_change_rate"):
            value = getattr(self, field_name)
            if value < 0.0 or value > 1.0:
                raise ValueError(f"{field_name} must be normalized to [0, 1]")
        return self


class BatchChunk(ContractModel):
    batch_id: str
    batch_mode: BatchMode
    slide_range: SlideRange
    reason: str
    title: str | None = None
    status: StageStatus = StageStatus.DRAFT
    part_id: str | None = None
    section_id: str | None = None
    cluster_id: str | None = None
    deck_mode: DeckMode | None = None
    intent: BatchIntent | None = None
    continuity_anchor: str | None = None
    objective: str | None = None
    locked_decision_keys: list[str] = Field(default_factory=list)
    continuity_inputs_needed: list[str] = Field(default_factory=list)
    assets_needed: list[str] = Field(default_factory=list)
    expected_output_scope: list[str] = Field(default_factory=list)
    remediation_finding_ids: list[str] = Field(default_factory=list)
    remediation_notes: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_batch_mode(self) -> "BatchChunk":
        valid_batch_modes = {member.value for member in BatchMode}
        batch_mode_value = str(getattr(self.batch_mode, "value", self.batch_mode))
        if batch_mode_value not in valid_batch_modes:
            raise ValueError("batch_mode must be a supported batch mode")
        return self


class _ContinuitySurface(ContractModel):
    continuity_guidance: list[str] = Field(default_factory=list)
    continuity_alerts: list[BatchBoundaryContinuityAlert] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _normalize_control_surface(cls, value: object) -> object:
        if isinstance(value, Mapping):
            return _normalize_continuity_payload_fields(value)
        return value


def _continuity_warning_description(*, durable_field_presence_supported: bool = True) -> str:
    if durable_field_presence_supported:
        contract_note = (
            "This field remains part of the supported persisted state-file contract until "
            "downstream acknowledgement completes a versioned deprecation path. "
        )
    else:
        contract_note = (
            "For handoff_packet, newly written persisted state files omit this raw field; older "
            "artifacts still load through guidance-first normalization and the in-memory mirror "
            "remains derived for compatibility. "
        )
    return (
        "Deprecated compatibility mirror for continuity guidance. "
        f"{contract_note}"
        "Not a canonical policy input. "
        f"Boundary marker: {PERSISTED_CONTINUITY_WARNING_MIRROR_DEPRECATION_BOUNDARY}."
    )


def _continuity_warning_metadata(
    *,
    artifact_family: str,
    artifact_filename: str,
    artifact_level_retirement_status: str,
    artifact_reader_role: str,
    artifact_rollout_classification: str,
    artifact_first_rollout_candidate_status: str,
    artifact_ack_requirement: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "compatibility_status": "deprecated_compatibility_mirror",
        "deprecation_boundary": PERSISTED_CONTINUITY_WARNING_MIRROR_DEPRECATION_BOUNDARY,
        "boundary_mode": "schema-metadata-only",
        "artifact_family": artifact_family,
        "artifact_filename": artifact_filename,
        "artifact_rollout_group": "shared-persisted-control-artifact-contract",
        "artifact_level_retirement_status": artifact_level_retirement_status,
        "artifact_family_rollout_classification": artifact_rollout_classification,
        "artifact_first_rollout_candidate_status": artifact_first_rollout_candidate_status,
        "artifact_in_repo_reader_roles": [artifact_reader_role],
        "artifact_named_acknowledgement_requirements": [artifact_ack_requirement],
        "supported_usage": ["durable-json-compatibility-field-presence"],
        "canonical_replacements": ["continuity_guidance", "continuity_alerts"],
        "unsupported_usage": ["canonical-policy-input", "stale-mirror-precedence", "normalization-bypass-reader"],
        "retirement_requires": ["downstream-acknowledgement-or-support-boundary-change", "versioned-write-shape-deprecation"],
    }
    if extra:
        metadata.update(extra)
    return metadata


class BatchManifest(_ContinuitySurface, SchemaModel):
    schema_name: str = "batch_manifest"
    deck_title: str
    scale_mode: ScaleMode
    batch_mode: BatchMode
    hierarchy: list[DeckHierarchyNode] = Field(default_factory=list)
    batches: list[BatchChunk] = Field(default_factory=list)
    next_recommended_range: SlideRange | None = None
    continuity_warnings: list[str] = Field(default_factory=list, description=_continuity_warning_description(), json_schema_extra=_continuity_warning_metadata(artifact_family="batch_manifest", artifact_filename="batch-manifest.json", artifact_level_retirement_status="not-authorized-yet", artifact_reader_role="compile-input", artifact_rollout_classification="not separable yet because it still shares a durable contract with the others", artifact_first_rollout_candidate_status="not a first-family candidate", artifact_ack_requirement="pptx_compiler.compile_pptx_from_files acknowledgement"))


class ContextLock(_ContinuitySurface, SchemaModel):
    schema_name: str = "context_lock"
    deck_title: str
    scale_mode: ScaleMode | None = None
    approved_workflow: str | None = None
    approved_visual_route: str | None = None
    locked_design_system: LockedDesignSystem | None = None
    locked_terminology: list[str] = Field(default_factory=list)
    title_rules: list[str] = Field(default_factory=list)
    numbering_rules: list[str] = Field(default_factory=list)
    section_divider_rules: list[str] = Field(default_factory=list)
    appendix_boundary_rule: str | None = None
    active_numbering_range: SlideRange | None = None
    active_section_ids: list[str] = Field(default_factory=list)
    active_cluster_ids: list[str] = Field(default_factory=list)
    unresolved_risks: list[str] = Field(default_factory=list)
    qa_blockers: list[str] = Field(default_factory=list)
    locked_decisions: list[ContextLockDecision] = Field(default_factory=list)
    continuity_warnings: list[str] = Field(default_factory=list, description=_continuity_warning_description(), json_schema_extra=_continuity_warning_metadata(artifact_family="context_lock", artifact_filename="context-lock.json", artifact_level_retirement_status="not-authorized-yet", artifact_reader_role="orchestration-revision", artifact_rollout_classification="not separable yet because it still shares a durable contract with the others", artifact_first_rollout_candidate_status="not a first-family candidate", artifact_ack_requirement="large_deck_orchestration.revise_context_lock_decision acknowledgement"))


class HandoffPacket(_ContinuitySurface, SchemaModel):
    schema_name: str = "handoff_packet"
    deck_title: str
    pointer_root: str | None = None
    canonical_state_root: str | None = None
    file_pointers: list[StateFilePointer] = Field(default_factory=list)
    reviewed_artifacts: list[str] = Field(default_factory=list)
    updated_artifacts: list[str] = Field(default_factory=list)
    continuity_warnings: list[str] = Field(default_factory=list, description=_continuity_warning_description(durable_field_presence_supported=False), json_schema_extra=_continuity_warning_metadata(artifact_family="handoff_packet", artifact_filename="handoff-packet.json", artifact_level_retirement_status="writer-demotion-complete-load-compatible", artifact_reader_role="upstream-fix", artifact_rollout_classification="handoff-packet writer demotion is complete for newly written artifacts; guidance-first normalization and older-artifact load compatibility remain the supported boundary", artifact_first_rollout_candidate_status="first-family writer demotion completed; broader persisted control-artifact mirror retirement remains out of scope", artifact_ack_requirement="named handoff file seams must stay guidance-first compatible after writer demotion", extra={"supported_usage": [], "artifact_named_acknowledgement_evidence": ["ship_readiness.assess_ship_readiness_from_files loads handoff_packet through load_state_file normalization"], "artifact_named_writer_acknowledgement_evidence": ["ship_readiness.write_ship_readiness_outputs saves the normalized handoff_packet through save_state_file and omits raw continuity_warnings from newly emitted JSON"], "artifact_field_presence_reader_acknowledgement_status": "no acknowledged in-repo handoff reader or writer requires raw continuity_warnings field presence, and repo-outside raw field-presence readers are now outside the supported handoff contract", "artifact_supported_raw_json_contract": "newly written handoff packets omit raw continuity_warnings; supported in-repo compatibility depends on canonical continuity_guidance plus guidance-first load_state_file/save_state_file normalization for older artifacts", "artifact_external_reader_evidence_status": "repo evidence still does not confirm any concrete repo-outside handoff-packet readers, and PR-7.17 narrows raw field-presence reliance out of the supported handoff contract", "artifact_external_reader_support_boundary": "repo-outside handoff-packet durable JSON readers that rely on raw continuity_warnings field presence are unsupported/out-of-scope; supported handoff compatibility stops at canonical continuity_guidance plus state-schema normalization on in-repo load_state_file/save_state_file boundaries", "artifact_support_boundary_decision": "PR-7.18 executes the authorized handoff-only writer demotion so newly written handoff-packet.json omits raw continuity_warnings while older artifacts remain load-compatible through normalization", "artifact_replacement_boundary": "supported in-repo handoff readers and writers should consume normalized continuity_guidance and continuity_alerts through load_state_file/save_state_file boundaries rather than raw continuity_warnings field presence", "artifact_legacy_compatibility_path": "older handoff packets may still carry continuity_warnings and load_state_file normalization continues to derive the in-memory mirror from canonical guidance-first state even though new writes omit the raw field", "artifact_required_replacement_boundary_coverage": ["guidance-only handoff payload survives a named file-based reader/writer seam without raw continuity_warnings being re-emitted, while load_state_file still derives the in-memory mirror"], "artifact_demotion_preflight_status": "writer demotion is complete for newly written handoff packets and malformed-payload/load compatibility remains locked at the schema boundary", "artifact_demotion_preflight_requirements": ["state-schema continuity normalization must keep guidance-only, stale-mirror, malformed-scalar, and malformed-mapping handoff payload regressions green after the writer change lands"], "artifact_remaining_rollout_blockers": ["broader persisted control-artifact mirror retirement outside handoff-packet.json remains out of scope for this writer-demotion slice"]}))

    @model_validator(mode="before")
    @classmethod
    def _accept_legacy_pointer_field(cls, value: object) -> object:
        if isinstance(value, Mapping) and "file_pointers" not in value and "state_file_pointers" in value:
            payload = dict(value)
            payload["file_pointers"] = payload.pop("state_file_pointers")
            return payload
        return value


class StateCapsule(_ContinuitySurface, SchemaModel):
    schema_name: str = "state_capsule"
    capsule_id: str
    deck_title: str
    active_gate: WorkflowGate
    blueprint_approved: bool
    total_planned_range: SlideRange | None = None
    next_recommended_range: SlideRange | None = None
    file_pointers: list[StateFilePointer] = Field(default_factory=list)
    canonical_state_root: str | None = None
    approved_visual_route: str | None = None
    cycle_outcome: ShipReadinessDecision | str | None = None
    continuity_warnings: list[str] = Field(
        default_factory=list,
        description=_continuity_warning_description(),
        json_schema_extra=_continuity_warning_metadata(
            artifact_family="state_capsule",
            artifact_filename="state-capsule.json",
            artifact_level_retirement_status="not-authorized-yet",
            artifact_reader_role="qa-runtime",
            artifact_rollout_classification="permanently compatibility-bound for now",
            artifact_first_rollout_candidate_status="not a first-family candidate",
            artifact_ack_requirement="deck_qa.run_deck_qa_from_files acknowledgement",
            extra={
                "artifact_named_acknowledgement_evidence": [
                    "deck_qa.run_deck_qa_from_files loads state_capsule for continuity and QA-round fallback",
                    "pipeline.executors._execute_qa may load persisted state_capsule continuity inputs when QA verdict fallback needs them",
                    "pptx_compiler.compile_pptx_from_files optionally loads state_capsule before compile-time approval and pending-action updates",
                    "remediation_execution.apply_bounded_remediation_from_files reloads state_capsule before compile, QA, and orchestration reruns",
                    "approved_apply.apply_approved_fixes_from_files reloads state_capsule before compile, QA, and orchestration reruns",
                    "post_apply_closure.close_approved_fixes_from_files reloads state_capsule before backlog and closure synchronization",
                    "ship_readiness.assess_ship_readiness_from_files reloads state_capsule before ship gating and release-candidate coordination",
                ],
                "artifact_named_writer_acknowledgement_evidence": [
                    "large_deck_orchestration.write_large_deck_outputs persists state_capsule as the initial durable control artifact",
                    "pptx_compiler.write_pptx_compile_outputs rewrites state_capsule with compile-stage pending action updates",
                    "deck_qa.write_deck_qa_outputs rewrites state_capsule with QA-round and continuity updates",
                    "remediation_execution.write_remediation_execution_outputs rewrites state_capsule after remediation reruns",
                    "approved_apply.write_approved_apply_outputs rewrites state_capsule after approved bounded changes",
                    "post_apply_closure.write_post_apply_closure_outputs rewrites state_capsule with closure and backlog synchronization",
                    "ship_readiness.write_ship_readiness_outputs rewrites state_capsule with ship decision and release-candidate pointers",
                ],
                "artifact_supported_raw_json_contract": "newly written state-capsule.json still emits raw continuity_warnings beside canonical continuity_guidance and continuity_alerts; supported in-repo readers must stay guidance-first through load_state_file normalization",
                "artifact_support_boundary_decision": "PR-7.20 keeps state-capsule.json compatibility-bound for now because named runtime seams still cross large-deck orchestration, compile, deck QA, remediation, approved apply, post-apply closure, ship readiness, and executor continuity fallback",
                "artifact_remaining_rollout_blockers": [
                    "pptx_compiler.compile_pptx_from_files and write_pptx_compile_outputs still read and rewrite state-capsule.json as a supported compile control artifact",
                    "deck_qa.run_deck_qa_from_files, deck_qa.write_deck_qa_outputs, and pipeline.executors._execute_qa still consume or rewrite state_capsule continuity and QA-round state",
                    "remediation_execution, approved_apply, post_apply_closure, and ship_readiness still reload and rewrite state-capsule.json as a shared durable control-plane artifact",
                ],
            },
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def _accept_legacy_pointer_field(cls, value: object) -> object:
        if isinstance(value, Mapping) and "file_pointers" not in value and "state_file_pointers" in value:
            payload = dict(value)
            payload["file_pointers"] = payload.pop("state_file_pointers")
            return payload
        return value

    @model_validator(mode="after")
    def _validate_state_gate(self) -> "StateCapsule":
        if self.active_gate == WorkflowGate.PRODUCTION_AND_QA and not self.blueprint_approved:
            raise ValueError("blueprint must be approved before production-and-qa")
        if self.next_recommended_range is not None and self.total_planned_range is None:
            raise ValueError("total_planned_range is required when next_recommended_range is set")
        return self


class PolicyRuleResult(ContractModel):
    rule_id: str
    outcome: PolicyRuleOutcome | str
    evidence_source: PolicyEvidenceSource | str | None = None
    summary: str | None = None
    reason_codes: list[str] = Field(default_factory=list)


class QAFinding(ContractModel):
    finding_id: str
    severity: QASeverity
    status: FindingStatus
    qa_layer: QALayer
    category: str
    summary: str
    slide_number: int | None = None
    slide_id: str | None = None
    slide_range: SlideRange | str | None = None
    build_link_index: int | None = None
    remediation_skill: str | None = None
    recommendation_type: QARecommendationType | None = None
    recommendation: str | None = None
    blocking: bool = False
    tags: list[str] = Field(default_factory=list)

    @field_validator("slide_range", mode="before")
    @classmethod
    def _coerce_slide_range(cls, value: object) -> object:
        if isinstance(value, str):
            return SlideRange.model_validate(_parse_range_string(value))
        return value


class QASlideResult(ContractModel):
    slide_number: int
    slide_id: str | None = None
    qa_status: QAStatus
    compile_status: StageStatus | None = None


class QASummary(ContractModel):
    finding_count: int = 0
    blocking_count: int = 0
    severity_counts: dict[str, int] = Field(default_factory=dict)
    recommendation_counts: dict[str, int] = Field(default_factory=dict)
    fail_slide_count: int = 0
    pass_slide_count: int = 0


class QAVerdictSummary(ContractModel):
    qa_status: QAStatus
    compile_eligibility: CompileEligibility | None = None
    render_checks_present: bool | None = None
    render_check_source: PolicyEvidenceSource | None = None
    warning_reason_codes: list[str] = Field(default_factory=list)
    blocking_reason_codes: list[str] = Field(default_factory=list)
    compatibility_warning_codes: list[str] = Field(default_factory=list)
    rule_results: list[PolicyRuleResult] = Field(default_factory=list)


class QAReport(SchemaModel):
    schema_name: str = "qa_report"
    report_id: str
    deck_title: str
    qa_status: QAStatus
    audited_scope: str
    findings: list[QAFinding] = Field(default_factory=list)
    slide_results: list[QASlideResult] = Field(default_factory=list)
    summary: QASummary | None = None
    checked_artifacts: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    bounded_round: int = 0
    max_rounds: int = 1
    drift_checks: list[str] = Field(default_factory=list)
    stop_condition_reached: bool = False
    verdict_summary: QAVerdictSummary | None = None

    @model_validator(mode="after")
    def _build_summary(self) -> "QAReport":
        if self.summary is None:
            severity_counts: dict[str, int] = {}
            recommendation_counts: dict[str, int] = {}
            blocking_count = 0
            for finding in self.findings:
                severity = str(getattr(finding.severity, "value", finding.severity))
                severity_counts[severity] = severity_counts.get(severity, 0) + 1
                if finding.recommendation_type is not None:
                    recommendation = str(getattr(finding.recommendation_type, "value", finding.recommendation_type))
                    recommendation_counts[recommendation] = recommendation_counts.get(recommendation, 0) + 1
                if finding.blocking:
                    blocking_count += 1
            self.summary = QASummary(
                finding_count=len(self.findings),
                blocking_count=blocking_count,
                severity_counts=severity_counts,
                recommendation_counts=recommendation_counts,
                fail_slide_count=sum(1 for result in self.slide_results if QAStatus(result.qa_status) == QAStatus.FAIL),
                pass_slide_count=sum(1 for result in self.slide_results if QAStatus(result.qa_status) == QAStatus.PASS),
            )
        if not self.recommended_actions:
            self.recommended_actions = _dedupe_strings(finding.recommendation for finding in self.findings if finding.recommendation)
        return self


class QAWaiverRecord(ContractModel):
    waiver_id: str
    scope: QAWaiverScope | str
    related_stage: str | None = None
    related_artifacts: list[str] = Field(default_factory=list)
    related_finding_ids: list[str] = Field(default_factory=list)
    rationale: str | None = None
    approver: str | None = None
    approved_at: str | None = None
    status: QAWaiverStatus | str | None = None
    review_by: str | None = None
    notes: list[str] = Field(default_factory=list)

    @field_validator("approved_at", mode="before")
    @classmethod
    def _normalize_approved_at(cls, value: object) -> object:
        return _coerce_optional_iso_datetime_string(value)


class QARemediationRecord(ContractModel):
    remediation_id: str
    related_finding_ids: list[str] = Field(default_factory=list)
    action_summary: str | None = None
    touched_artifacts: list[str] = Field(default_factory=list)
    status: QARemediationStatus | str | None = None


class QAGovernanceSummary(ContractModel):
    total_findings: int = 0
    unresolved_findings: int = 0
    remediated_findings: int = 0
    waived_findings: int = 0
    accepted_risk_findings: int = 0
    expired_waiver_count: int = 0
    orphan_waiver_count: int = 0
    orphan_remediation_count: int = 0
    remediation_mismatch_count: int = 0
    blocking_findings_still_open: int = 0
    depends_on_operator_exceptions: bool = False
    qa_improvement_source: str = "none"
    release_readiness_posture: ReleaseReadinessPosture | str = ReleaseReadinessPosture.UNRESOLVED_BLOCKING_ISSUE


class QAGovernance(SchemaModel):
    schema_name: str = "qa_governance"
    governance_id: str
    deck_title: str
    source_report_id: str | None = None
    waivers: list[QAWaiverRecord] = Field(default_factory=list)
    remediations: list[QARemediationRecord] = Field(default_factory=list)
    finding_statuses: list[ContractModel] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    summary: QAGovernanceSummary = Field(default_factory=QAGovernanceSummary)


class RemediationAction(ContractModel):
    action_id: str | None = None
    finding_id: str | None = None
    severity: QASeverity = QASeverity.MINOR
    owner: RemediationOwner = RemediationOwner.UPSTREAM_CONTENT_STORY
    scope: RemediationScope = RemediationScope.LOCAL_CHANGE_ONLY
    disposition: RemediationDisposition = RemediationDisposition.SAFE_TO_DEFER
    rerun_stages: list[str] = Field(default_factory=list)
    rationale: str | None = None
    qa_layer: QALayer | None = None
    category: str | None = None
    target_skill: str | None = None
    next_action: str | None = None
    blocking: bool = False
    execution_action: RemediationExecutionAction | None = None
    slide_number: int | None = None
    slide_id: str | None = None
    slide_range: SlideRange | None = None
    target_batch_id: str | None = None
    tags: list[str] = Field(default_factory=list)


class RemediationBatch(ContractModel):
    batch_id: str | None = None
    actions: list[RemediationAction] = Field(default_factory=list)
    finding_ids: list[str] = Field(default_factory=list)


class RemediationSummary(ContractModel):
    pass


class RemediationPlan(SchemaModel):
    schema_name: str = "remediation_plan"
    plan_id: str | None = None
    deck_title: str | None = None
    actions: list[RemediationAction] = Field(default_factory=list)
    fix_batches: list[RemediationBatch] = Field(default_factory=list)
    ship_blocked: bool = False
    safe_to_ship_with_deferrals: bool = False

    @model_validator(mode="before")
    @classmethod
    def _normalize_fix_batches(cls, value: object) -> object:
        if not isinstance(value, Mapping):
            return value
        data = dict(value)
        if "fix_batches" not in data and data.get("batches") is not None:
            data["fix_batches"] = data["batches"]
        return data

    @property
    def batches(self) -> list[RemediationBatch]:
        return self.fix_batches


class RemediationExecutionItem(ContractModel):
    action_id: str | None = None
    finding_id: str | None = None
    scope: RemediationScope | None = None
    owner: RemediationOwner | None = None
    requested_action: RemediationExecutionAction | None = None
    execution_status: RemediationExecutionStatus | None = None
    action_taken: str | None = None
    downstream_stages_rerun: list[str] = Field(default_factory=list)
    updated_artifacts: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    slide_number: int | None = None
    slide_range: SlideRange | None = None
    target_batch_id: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _normalize_execution_item(cls, value: object) -> object:
        if not isinstance(value, Mapping):
            return value
        data = dict(value)
        if "execution_status" not in data and data.get("status") is not None:
            data["execution_status"] = data["status"]
        if "requested_action" not in data and data.get("execution_action") is not None:
            data["requested_action"] = data["execution_action"]
        return data


class RemediationExecutionSummary(ContractModel):
    pass


class RemediationExecutionReport(SchemaModel):
    schema_name: str = "remediation_execution_report"
    report_id: str | None = None
    deck_title: str | None = None
    items: list[RemediationExecutionItem] = Field(default_factory=list)
    summary: RemediationExecutionSummary | None = None
    ship_blocked_after_execution: bool = False
    remaining_blocking_finding_ids: list[str] = Field(default_factory=list)


class BlockedManualUpstreamIssue(ContractModel):
    issue_id: str


class UpstreamFixProposal(ContractModel):
    fix_id: str
    summary: str | None = None
    source_action_ids: list[str] = Field(default_factory=list)
    source_finding_ids: list[str] = Field(default_factory=list)
    scope: RemediationScope | str | None = None
    affected_slide_range: SlideRange | None = None
    affected_batch_ids: list[str] = Field(default_factory=list)
    affected_section_ids: list[str] = Field(default_factory=list)
    target_artifacts: list[UpstreamArtifactName] = Field(default_factory=list)
    selectors: list[str] = Field(default_factory=list)
    delta_ids: list[str] = Field(default_factory=list)
    rationale: str | None = None
    downstream_rerun_stages: list[str] = Field(default_factory=list)
    approval_requirement: str | None = None
    risk_level: FixRiskLevel | str | None = None
    approval_status: ApprovalDecisionStatus | str = ApprovalDecisionStatus.PENDING
    apply_status: ApplyDecisionStatus | str = ApplyDecisionStatus.PENDING

    @model_validator(mode="before")
    @classmethod
    def _normalize_upstream_fix(cls, value: object) -> object:
        if not isinstance(value, Mapping):
            return value
        data = dict(value)
        if "apply_status" not in data and data.get("status") is not None:
            data["apply_status"] = data["status"]
        return data


class UpstreamFixPlan(SchemaModel):
    schema_name: str = "upstream_fix_plan"
    plan_id: str
    deck_title: str
    source_execution_report_id: str | None = None
    fixes: list[UpstreamFixProposal] = Field(default_factory=list)
    blocked_manual_items: list[BlockedManualUpstreamIssue] = Field(default_factory=list)
    deferred_or_noop_action_ids: list[str] = Field(default_factory=list)


class DeltaOption(ContractModel):
    option_id: str
    label: str | None = None
    value: Any = None
    rationale: str | None = None


class DeltaOptionSelection(ContractModel):
    delta_id: str
    option_id: str


class AuthoringDeltaRecord(ContractModel):
    delta_id: str
    fix_id: str | None = None
    source_finding_ids: list[str] = Field(default_factory=list)
    target_artifact: UpstreamArtifactName | None = None
    selector: str | None = None
    field_path: str | None = None
    operation: DeltaOperation | str | None = None
    current_value: Any = None
    proposed_value: Any = None
    selected_option_id: str | None = None
    approval_status: ApprovalDecisionStatus | str = ApprovalDecisionStatus.PENDING
    apply_status: ApplyDecisionStatus | str = ApplyDecisionStatus.PENDING
    options: list[DeltaOption] = Field(default_factory=list)
    rationale: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _normalize_authoring_delta(cls, value: object) -> object:
        if not isinstance(value, Mapping):
            return value
        data = dict(value)
        if "apply_status" not in data and data.get("status") is not None:
            data["apply_status"] = data["status"]
        return data


class AuthoringDeltas(SchemaModel):
    schema_name: str = "authoring_deltas"
    deck_title: str | None = None
    deltas: list[AuthoringDeltaRecord] = Field(default_factory=list)


class ApprovalPacket(ContractModel):
    packet_id: str
    fix_id: str | None = None
    objective: str | None = None
    scope: RemediationScope | str | None = None
    included_fix_ids: list[str] = Field(default_factory=list)
    affected_slide_range: SlideRange | None = None
    affected_batch_ids: list[str] = Field(default_factory=list)
    affected_section_ids: list[str] = Field(default_factory=list)
    target_artifacts: list[UpstreamArtifactName] = Field(default_factory=list)
    rationale_summary: str | None = None
    risk_summary: str | None = None
    required_approvals: list[str] = Field(default_factory=list)
    expected_downstream_reruns: list[str] = Field(default_factory=list)
    approval_mode: PacketApprovalMode | str | None = None
    safe_to_approve_independently: bool = False
    approval_status: ApprovalDecisionStatus | str = ApprovalDecisionStatus.PENDING
    apply_status: ApplyDecisionStatus | str = ApplyDecisionStatus.PENDING
    selected_delta_options: list[DeltaOptionSelection] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _normalize_approval_packet(cls, value: object) -> object:
        if not isinstance(value, Mapping):
            return value
        data = dict(value)
        if "approval_status" not in data and data.get("status") is not None:
            data["approval_status"] = data["status"]
        if not data.get("included_fix_ids") and data.get("fix_id"):
            data["included_fix_ids"] = [str(data["fix_id"])]
        return data


class ApprovalPacketSet(SchemaModel):
    schema_name: str = "approval_packet"
    deck_title: str | None = None
    approval_mode: PacketApprovalMode | str | None = None
    packets: list[ApprovalPacket] = Field(default_factory=list)


class ApprovedApplyFixResult(ContractModel):
    fix_id: str
    packet_id: str | None = None
    finding_ids: list[str] = Field(default_factory=list)
    source_action_ids: list[str] = Field(default_factory=list)
    approval_status: ApprovalDecisionStatus = ApprovalDecisionStatus.PENDING
    apply_status: ApplyDecisionStatus = ApplyDecisionStatus.PENDING
    target_artifacts: list[UpstreamArtifactName] = Field(default_factory=list)
    delta_ids: list[str] = Field(default_factory=list)
    affected_slide_range: SlideRange | None = None
    downstream_rerun_stages_requested: list[str] = Field(default_factory=list)
    downstream_rerun_stages_selected: list[str] = Field(default_factory=list)
    delta_results: list["ApprovedApplyDeltaResult"] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ApprovedApplyDeltaResult(ContractModel):
    delta_id: str
    fix_id: str | None = None
    packet_id: str | None = None
    finding_ids: list[str] = Field(default_factory=list)
    target_artifact: UpstreamArtifactName | None = None
    selector: str | None = None
    field_path: str | None = None
    operation: DeltaOperation | None = None
    approval_status: ApprovalDecisionStatus = ApprovalDecisionStatus.PENDING
    apply_status: ApplyDecisionStatus = ApplyDecisionStatus.PENDING
    before_value: Any = None
    after_value: Any = None
    selected_option_id: str | None = None
    notes: list[str] = Field(default_factory=list)


class ApprovedApplySummary(ContractModel):
    total_proposals_seen: int = 0
    approved_proposals_seen: int = 0
    applied_count: int = 0
    skipped_count: int = 0
    deferred_count: int = 0
    blocked_count: int = 0
    failed_count: int = 0


class ApprovedApplyReport(SchemaModel):
    schema_name: str = "approved_apply_report"
    report_id: str | None = None
    deck_title: str | None = None
    source_plan_id: str | None = None
    source_execution_report_id: str | None = None
    summary: ApprovedApplySummary | None = None
    fix_results: list[ApprovedApplyFixResult] = Field(default_factory=list)
    target_artifacts_touched: list[UpstreamArtifactName] = Field(default_factory=list)
    downstream_stages_rerun: list[str] = Field(default_factory=list)
    canonical_artifacts_refreshed: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    remaining_pending_packet_ids: list[str] = Field(default_factory=list)
    remaining_pending_fix_ids: list[str] = Field(default_factory=list)
    remaining_blocked_issue_ids: list[str] = Field(default_factory=list)
    canonical_state_root: str | None = None


class ClosureReportSummary(ContractModel):
    still_open_packet_count: int = 0
    item_counts_by_closure_reason: dict[str, int] = Field(default_factory=dict)


class ClosureReport(SchemaModel):
    schema_name: str = "closure_report"
    report_id: str | None = None
    deck_title: str | None = None
    source_plan_id: str | None = None
    source_execution_report_id: str | None = None
    still_open_packet_ids: list[str] = Field(default_factory=list)
    remaining_fix_ids: list[str] = Field(default_factory=list)
    blocked_issue_ids: list[str] = Field(default_factory=list)
    still_open_packet_count: int = 0
    summary: ClosureReportSummary = Field(default_factory=ClosureReportSummary)
    canonical_state_root: str | None = None


class RemainingBacklogItem(ContractModel):
    item_id: str | None = None
    item_type: BacklogItemType | None = None
    summary: str | None = None
    fix_id: str | None = None
    packet_id: str | None = None
    issue_id: str | None = None
    finding_ids: list[str] = Field(default_factory=list)
    source_action_ids: list[str] = Field(default_factory=list)
    delta_ids: list[str] = Field(default_factory=list)
    status: ClosureReasonStatus | None = None
    severity: QASeverity | None = None
    scope: RemediationScope | None = None
    owners: list[RemediationOwner] = Field(default_factory=list)
    target_artifacts: list[UpstreamArtifactName] = Field(default_factory=list)
    affected_slide_range: SlideRange | None = None
    affected_batch_ids: list[str] = Field(default_factory=list)
    affected_section_ids: list[str] = Field(default_factory=list)
    downstream_stages: list[str] = Field(default_factory=list)
    recommended_next_action: str | None = None
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _normalize_backlog_item(cls, value: object) -> object:
        if not isinstance(value, Mapping):
            return value
        data = dict(value)
        owner = data.pop("owner", None)
        if "owners" not in data and owner is not None:
            data["owners"] = [owner]
        stage = data.pop("stage", None)
        if "downstream_stages" not in data and stage is not None:
            data["downstream_stages"] = [stage]
        return data


class RemainingBacklogSummary(ContractModel):
    total_items_considered: int = 0
    remaining_actionable_items: int = 0
    pending_approval_items: int = 0
    deferred_items: int = 0
    blocked_manual_items: int = 0
    obsolete_superseded_items: int = 0
    failed_review_items: int = 0
    severity_counts: dict[str, int] = Field(default_factory=dict)
    scope_counts: dict[str, int] = Field(default_factory=dict)
    owner_counts: dict[str, int] = Field(default_factory=dict)
    stage_counts: dict[str, int] = Field(default_factory=dict)


class RemainingBacklogSnapshot(ContractModel):
    total_items_considered: int = 0
    remaining_actionable_items: int = 0
    pending_approval_items: int = 0
    deferred_items: int = 0
    blocked_manual_items: int = 0
    obsolete_superseded_items: int = 0
    failed_review_items: int = 0


class RemainingBacklog(SchemaModel):
    schema_name: str = "remaining_backlog"
    deck_title: str | None = None
    items: list[RemainingBacklogItem] = Field(default_factory=list)
    pending_packet_ids: list[str] = Field(default_factory=list)
    remaining_fix_ids: list[str] = Field(default_factory=list)
    blocked_issue_ids: list[str] = Field(default_factory=list)
    recommended_next_actions: list[str] = Field(default_factory=list)
    summary: RemainingBacklogSummary = Field(default_factory=RemainingBacklogSummary)
    canonical_state_root: str | None = None


class PendingApprovalSummary(ContractModel):
    pass


class CompileQAHealthSummary(ContractModel):
    qa_status: QAStatus | None = None
    compile_eligibility: CompileEligibility | None = None
    qa_warning_reason_codes: list[str] = Field(default_factory=list)
    qa_blocking_reason_codes: list[str] = Field(default_factory=list)
    compatibility_warning_codes: list[str] = Field(default_factory=list)
    qa_open_finding_count: int = 0
    qa_blocking_finding_count: int = 0
    qa_open_finding_ids: list[str] = Field(default_factory=list)
    qa_blocking_finding_ids: list[str] = Field(default_factory=list)
    build_warning_count: int = 0
    build_warnings: list[str] = Field(default_factory=list)
    compile_incomplete_slide_count: int = 0
    compile_incomplete_slide_numbers: list[int] = Field(default_factory=list)
    missing_dependency_count: int = 0
    missing_dependency_slide_numbers: list[int] = Field(default_factory=list)


class ReleaseReadinessSummary(ContractModel):
    ship_ready: bool = False
    release_posture: ReleaseReadinessPosture = ReleaseReadinessPosture.UNRESOLVED_BLOCKING_ISSUE
    operator_exception_dependency: bool = False
    blocking_findings_open_count: int = 0
    waived_findings_count: int = 0
    accepted_risk_count: int = 0
    remediated_findings_count: int = 0
    expired_waiver_count: int = 0
    orphan_waiver_count: int = 0
    orphan_remediation_count: int = 0
    remediation_mismatch_count: int = 0
    rationale_summary: str = ""


class ReleaseCandidate(SchemaModel):
    schema_name: str = "release_candidate"
    decision: ShipReadinessDecision
    may_ship_now: bool = True
    release_readiness: ReleaseReadinessSummary
    compile_qa_health: CompileQAHealthSummary = Field(default_factory=CompileQAHealthSummary)


class ShipReadinessReport(SchemaModel):
    schema_name: str = "ship_readiness_report"
    decision: ShipReadinessDecision
    may_ship_now: bool
    release_readiness: ReleaseReadinessSummary
    compile_qa_health: CompileQAHealthSummary


class CycleResetPlan(SchemaModel):
    schema_name: str = "cycle_reset_plan"
    next_recommended_starting_stage: CycleStartStage | str


class ProofUnit(ContractModel):
    pass


class ProofModule(ContractModel):
    pass


class ProofUnitRegistry(SchemaModel):
    schema_name: str = "proof_unit_registry"
    deck_title: str
    workflow_option: str
    unit_count: int | None = None
    units: list[ProofUnit] = Field(default_factory=list)


class ProofModuleManifest(SchemaModel):
    schema_name: str = "proof_module_manifest"
    deck_title: str
    workflow_option: str
    module_count: int | None = None
    modules: list[ProofModule] = Field(default_factory=list)


def proof_module_manifest_from_proof_unit_registry(registry: ProofUnitRegistry) -> ProofModuleManifest:
    payload = registry.model_dump(mode="json", exclude_none=True)
    payload["schema_name"] = "proof_module_manifest"
    payload["core_claim_section_id"] = payload.pop("claim_anchor_section_id", None)
    payload["implication_section_id"] = payload.pop("synthesis_anchor_section_id", None)
    payload["claim_slide_numbers"] = payload.pop("claim_anchor_slide_numbers", [])
    payload["implication_slide_numbers"] = payload.pop("synthesis_anchor_slide_numbers", [])
    payload["module_minimum"] = payload.pop("unit_minimum", None)
    payload["module_count"] = payload.pop("unit_count", None)
    payload["direct_evidence_module_count"] = payload.pop("direct_evidence_unit_count", None)
    payload["synthesis_module_count"] = payload.pop("synthesis_unit_count", None)
    payload["modules"] = []
    for item in payload.pop("units", []):
        module = dict(item)
        module["module_id"] = module.pop("unit_id", None)
        module["module_order_index"] = module.pop("unit_order_index", None)
        module["claim_section_id"] = module.pop("claim_anchor_section_id", None)
        module["claim_slide_number"] = module.pop("claim_anchor_slide_number", None)
        module["implication_section_id"] = module.pop("synthesis_anchor_section_id", None)
        module["implication_slide_number"] = module.pop("synthesis_anchor_slide_number", None)
        module["implication_link_reason"] = module.pop("synthesis_link_reason", None)
        payload["modules"].append(module)
    return ProofModuleManifest.model_validate(payload)


def proof_unit_registry_from_proof_module_manifest(manifest: ProofModuleManifest) -> ProofUnitRegistry:
    payload = manifest.model_dump(mode="json", exclude_none=True)
    payload["schema_name"] = "proof_unit_registry"
    payload["claim_anchor_section_id"] = payload.pop("core_claim_section_id", None)
    payload["synthesis_anchor_section_id"] = payload.pop("implication_section_id", None)
    payload["claim_anchor_slide_numbers"] = payload.pop("claim_slide_numbers", [])
    payload["synthesis_anchor_slide_numbers"] = payload.pop("implication_slide_numbers", [])
    payload["unit_minimum"] = payload.pop("module_minimum", None)
    payload["unit_count"] = payload.pop("module_count", None)
    payload["direct_evidence_unit_count"] = payload.pop("direct_evidence_module_count", None)
    payload["synthesis_unit_count"] = payload.pop("synthesis_module_count", None)
    payload["units"] = []
    for item in payload.pop("modules", []):
        unit = dict(item)
        unit["unit_id"] = unit.pop("module_id", None)
        unit["unit_order_index"] = unit.pop("module_order_index", None)
        unit["claim_anchor_section_id"] = unit.pop("claim_section_id", None)
        unit["claim_anchor_slide_number"] = unit.pop("claim_slide_number", None)
        unit["synthesis_anchor_section_id"] = unit.pop("implication_section_id", None)
        unit["synthesis_anchor_slide_number"] = unit.pop("implication_slide_number", None)
        unit["synthesis_link_reason"] = unit.pop("implication_link_reason", None)
        payload["units"].append(unit)
    return ProofUnitRegistry.model_validate(payload)


def _make_shell_model(name: str) -> type[ContractModel]:
    cls = type(name, (ContractModel,), {"__module__": __name__})
    globals()[name] = cls
    return cls


def _make_shell_schema_model(name: str, schema_name: str) -> type[SchemaModel]:
    cls = type(name, (SchemaModel,), {"__module__": __name__, "__annotations__": {"schema_name": str}, "schema_name": schema_name})
    globals()[name] = cls
    return cls


PresentationBrief = _make_shell_schema_model("PresentationBrief", "presentation_brief")


class GenerationSafeArea(ContractModel):
    top_in: float | None = None
    right_in: float | None = None
    bottom_in: float | None = None
    left_in: float | None = None
    gutter_in: float | None = None
    notes: list[str] = Field(default_factory=list)


class CanonicalGenerationProfile(SchemaModel):
    schema_name: str = "canonical_generation_profile"
    safe_area: GenerationSafeArea | None = None


SlideFunctionOutline = _make_shell_schema_model("SlideFunctionOutline", "slide_function_outline")
ProofArtifactDoctorReport = _make_shell_schema_model("ProofArtifactDoctorReport", "proof_artifact_doctor_report")
ProofArtifactFleetReport = _make_shell_schema_model("ProofArtifactFleetReport", "proof_artifact_fleet_report")
ProofArtifactVNextBlockerReport = _make_shell_schema_model("ProofArtifactVNextBlockerReport", "proof_artifact_vnext_blocker_report")
AuthoringPreview = _make_shell_schema_model("AuthoringPreview", "authoring_preview")
ReferenceDNA = _make_shell_schema_model("ReferenceDNA", "reference_dna")

AuthoringPreviewSlide = _make_shell_model("AuthoringPreviewSlide")
BlueprintPreview = _make_shell_model("BlueprintPreview")
ConceptEdge = _make_shell_model("ConceptEdge")
ConceptNode = _make_shell_model("ConceptNode")
ConceptGraph = _make_shell_model("ConceptGraph")
ContentPlanConformance = _make_shell_model("ContentPlanConformance")
TeachingPlan = _make_shell_model("TeachingPlan")
TeachingPlanSlide = _make_shell_model("TeachingPlanSlide")
WorkflowDeltaDetail = _make_shell_model("WorkflowDeltaDetail")
SlideFunctionPlanItem = _make_shell_model("SlideFunctionPlanItem")


DEFAULT_STATE_FILENAMES: dict[str, str] = {
    "workflow_plan": "workflow-plan.json",
    "presentation_brief": "presentation-brief.json",
    "canonical_generation_profile": "canonical-generation-profile.json",
    "slide_function_outline": "slide-function-outline.json",
    "blueprint": "blueprint.json",
    "proof_unit_registry": "proof-unit-registry.json",
    "proof_artifact_doctor_report": "proof-artifact-doctor-report.json",
    "proof_artifact_fleet_report": "proof-artifact-fleet-report.json",
    "proof_artifact_vnext_blocker_report": "proof-artifact-vnext-blocker-report.json",
    "authoring_preview": "authoring-preview.json",
    "design_system": "design-system.json",
    "reference_dna": "reference-dna.json",
    "deck_constitution": "deck-constitution.json",
    "layout_library": "layout-library.json",
    "slide_ledger": "slide-ledger.json",
    "asset_requests": "asset-requests.json",
    "asset_manifest": "asset-manifest.json",
    "viz_spec": "viz-spec.json",
    "viz_manifest": "viz-manifest.json",
    "batch_manifest": "batch-manifest.json",
    "context_lock": "context-lock.json",
    "handoff_packet": "handoff-packet.json",
    "state_capsule": "state-capsule.json",
    "remediation_plan": "remediation-plan.json",
    "remediation_execution_report": "remediation-execution-report.json",
    "qa_report": "qa-report.json",
    "qa_governance": "qa-governance.json",
    "upstream_fix_plan": "upstream-fix-plan.json",
    "approval_packet": "approval-packet.json",
    "authoring_deltas": "authoring-deltas.json",
    "approved_apply_report": "approved-apply-report.json",
    "closure_report": "closure-report.json",
    "remaining_backlog": "remaining-backlog.json",
    "ship_readiness_report": "ship-readiness-report.json",
    "cycle_reset_plan": "cycle-reset-plan.json",
    "proof_module_manifest": "proof-module-manifest.json",
    "release_candidate": "release-candidate.json",
    "build_manifest": "build-manifest.json",
}

SCHEMA_REGISTRY: dict[str, type[SchemaModel]] = {
    "workflow_plan": WorkflowPlan,
    "presentation_brief": PresentationBrief,
    "canonical_generation_profile": CanonicalGenerationProfile,
    "slide_function_outline": SlideFunctionOutline,
    "blueprint": Blueprint,
    "proof_unit_registry": ProofUnitRegistry,
    "proof_artifact_doctor_report": ProofArtifactDoctorReport,
    "proof_artifact_fleet_report": ProofArtifactFleetReport,
    "proof_artifact_vnext_blocker_report": ProofArtifactVNextBlockerReport,
    "authoring_preview": AuthoringPreview,
    "design_system": DesignSystem,
    "reference_dna": ReferenceDNA,
    "deck_constitution": DeckConstitution,
    "layout_library": LayoutLibrary,
    "slide_ledger": SlideLedger,
    "asset_requests": AssetRequests,
    "asset_manifest": AssetManifest,
    "viz_spec": VizSpecSet,
    "viz_manifest": VizManifest,
    "batch_manifest": BatchManifest,
    "context_lock": ContextLock,
    "handoff_packet": HandoffPacket,
    "state_capsule": StateCapsule,
    "remediation_plan": RemediationPlan,
    "remediation_execution_report": RemediationExecutionReport,
    "qa_report": QAReport,
    "qa_governance": QAGovernance,
    "upstream_fix_plan": UpstreamFixPlan,
    "approval_packet": ApprovalPacketSet,
    "authoring_deltas": AuthoringDeltas,
    "approved_apply_report": ApprovedApplyReport,
    "closure_report": ClosureReport,
    "remaining_backlog": RemainingBacklog,
    "ship_readiness_report": ShipReadinessReport,
    "cycle_reset_plan": CycleResetPlan,
    "proof_module_manifest": ProofModuleManifest,
    "release_candidate": ReleaseCandidate,
}
STATE_SCHEMA_MODEL_TYPES = dict(SCHEMA_REGISTRY)

_SCHEMA_COLLECTION_FIELDS: dict[str, list[str]] = {
    "viz_spec": ["specs"],
    "viz_manifest": ["visuals"],
    "asset_requests": ["requests"],
    "asset_manifest": ["assets"],
    "slide_ledger": ["entries"],
    "batch_manifest": ["batches"],
    "approval_packet": ["packets"],
    "authoring_deltas": ["deltas"],
    "remaining_backlog": ["items"],
}


def example_state_path(schema_name: str) -> Path:
    canonical = _canonical_schema_name(schema_name)
    if canonical is None:
        raise KeyError("schema_name is required")
    filename = DEFAULT_STATE_FILENAMES[canonical]
    root = ROOT / "examples" / ("compat-state" if canonical in COMPAT_ONLY_EXAMPLE_SCHEMAS else "state")
    return root / filename


def _model_required_fields(model_cls: type[SchemaModel]) -> list[str]:
    return [
        name
        for name, field in model_cls.model_fields.items()
        if name not in {"schema_name", "schema_version"} and field.is_required()
    ]


def _schema_summary(schema_name: str) -> str:
    return "Structured visual specification set." if schema_name == "viz_spec" else f"Persisted state contract for {schema_name}."


def schema_expectations(schema_name: str | None = None) -> list[dict[str, Any]]:
    if schema_name is None:
        names = [name for name in STATE_SCHEMA_NAMES if name not in COMPAT_ONLY_EXAMPLE_SCHEMAS]
    else:
        canonical = _canonical_schema_name(schema_name)
        if canonical is None or canonical not in SCHEMA_REGISTRY:
            return []
        names = [canonical]
    return [
        {
            "schema_name": name,
            "filename": DEFAULT_STATE_FILENAMES[name],
            "summary": _schema_summary(name),
            "required_fields": _model_required_fields(SCHEMA_REGISTRY[name]),
            "collection_fields": list(_SCHEMA_COLLECTION_FIELDS.get(name, [])),
        }
        for name in names
    ]


def schema_summaries() -> list[dict[str, Any]]:
    return schema_expectations()


def upgrade_state_payload(payload: Mapping[str, Any], filename: str | None = None) -> dict[str, Any]:
    upgraded = json.loads(json.dumps(dict(payload)))
    schema_name = _canonical_schema_name(str(upgraded.get("schema_name"))) if upgraded.get("schema_name") else None
    if "viz_specs" in upgraded:
        upgraded["schema_name"] = "viz_manifest"
        upgraded["visuals"] = [{"spec": spec, "status": "approved"} for spec in upgraded.pop("viz_specs", [])]
        return upgraded
    if schema_name == "viz_spec" and "viz_spec" in upgraded:
        upgraded["schema_name"] = "viz_spec"
        upgraded["specs"] = [upgraded.pop("viz_spec")]
        return upgraded
    if schema_name == "workflow_plan" and upgraded.get("scale_mode") == "large":
        upgraded["scale_mode"] = "large-deck"
    if schema_name is None and filename:
        inferred = _canonical_schema_name(Path(filename).name.removesuffix(".json").removesuffix(".yaml").removesuffix(".yml"))
        if inferred in SCHEMA_REGISTRY:
            upgraded["schema_name"] = inferred
    if "schema_name" in upgraded:
        upgraded["schema_name"] = _canonical_schema_name(str(upgraded["schema_name"]))
    return upgraded


def _read_payload(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    payload = yaml.safe_load(text) if path.suffix.lower() in {".yaml", ".yml"} else json.loads(text)
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        raise ValueError(f"state file must contain a top-level object: {path}")
    return payload


def load_state_file(path: str | Path) -> SchemaModel:
    file_path = Path(path)
    upgraded = upgrade_state_payload(_read_payload(file_path), file_path.name)
    schema_name = _canonical_schema_name(str(upgraded.get("schema_name"))) if upgraded.get("schema_name") else None
    if schema_name is None:
        raise KeyError(f"could not resolve schema_name for {file_path}")
    return SCHEMA_REGISTRY[schema_name].model_validate(upgraded)


def validate_state_file(path: str | Path) -> SchemaModel:
    return load_state_file(path)


def _serialized_state_payload(model: SchemaModel) -> dict[str, Any]:
    payload = model.to_payload()
    if model.schema_name == "handoff_packet":
        payload.pop("continuity_warnings", None)
    return payload


def save_state_file(model: SchemaModel, path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = _serialized_state_payload(model)
    text = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True) if output_path.suffix.lower() in {".yaml", ".yml"} else json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    output_path.write_text(text, encoding="utf-8")
    return output_path


def build_sample_state(schema_name: str) -> SchemaModel:
    return load_state_file(example_state_path(schema_name))


def build_empty_state(schema_name: str) -> SchemaModel:
    canonical = _canonical_schema_name(schema_name)
    if canonical is None:
        raise KeyError("schema_name is required")
    return SCHEMA_REGISTRY[canonical]()


def generate_state_model(schema_name: str, *, mode: str = "sample") -> SchemaModel:
    if mode == "sample":
        return build_sample_state(schema_name)
    if mode == "empty":
        return build_empty_state(schema_name)
    raise ValueError(f"unsupported generation mode {mode!r}")


def _collect_direct_import_names() -> set[str]:
    names: set[str] = set()
    target_modules = {"presentation_agent.state_schemas", "presentation_agent.non_pptx_modules.state_schemas"}
    for root in (ROOT / "src", ROOT / "tests"):
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            try:
                module = ast.parse(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            for node in ast.walk(module):
                if isinstance(node, ast.ImportFrom) and node.module in target_modules:
                    names.update(alias.name for alias in node.names if alias.name != "*")
    return names


for _import_name in sorted(_collect_direct_import_names()):
    if _import_name and _import_name[0].isupper() and _import_name not in globals():
        _make_shell_model(_import_name)


DesignSystem.model_rebuild(force=True, _types_namespace=globals())


def __getattr__(name: str):
    if name and name[0].isupper():
        return _make_shell_model(name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = sorted(
    name
    for name, value in globals().items()
    if not name.startswith("_") and (name.isupper() or getattr(value, "__module__", None) == __name__)
)
