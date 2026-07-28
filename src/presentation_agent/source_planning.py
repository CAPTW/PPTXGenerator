"""Strict local contracts for source-to-deck planning artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


SOURCE_DOCUMENT_SCHEMA_NAME = "source_document"
SOURCE_DOCUMENT_SCHEMA_VERSION = "0.1"
PRESENTATION_PLAN_SCHEMA_NAME = "presentation_plan"
PRESENTATION_PLAN_SCHEMA_VERSION = "0.1"
PRESENTATION_PLAN_VALIDATION_SCHEMA_NAME = "presentation_plan_validation"
PRESENTATION_PLAN_VALIDATION_SCHEMA_VERSION = "0.1"

DesignMode = Literal["academic", "professional", "creative"]
SlideRole = Literal[
    "title",
    "agenda",
    "section-divider",
    "summary",
    "evidence",
    "analysis",
    "recommendation",
    "appendix",
    "references",
]
VisualCategory = Literal[
    "text",
    "table",
    "chart",
    "process",
    "comparison",
    "quote",
    "image",
    "framework",
    "timeline",
    "section-divider",
]
ValidationSeverity = Literal["info", "warning", "error"]
ValidationStatus = Literal["passed", "warnings", "failed"]


class SourcePlanningModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class SourceCitation(SourcePlanningModel):
    citation_id: str
    label: str
    source_chunk_ids: list[str] = Field(default_factory=list)


class SourceFigureRef(SourcePlanningModel):
    figure_id: str
    label: str
    caption: str | None = None
    source_chunk_id: str | None = None


class SourceTableRef(SourcePlanningModel):
    table_id: str
    label: str
    caption: str | None = None
    source_chunk_id: str | None = None


class SourceChunk(SourcePlanningModel):
    chunk_id: str
    text: str
    heading_path: list[str] = Field(default_factory=list)
    heading_level: int | None = None
    start_line: int
    end_line: int
    start_char: int
    end_char: int
    token_estimate: int = 0

    @model_validator(mode="after")
    def _validate_ranges(self) -> "SourceChunk":
        if self.end_line < self.start_line:
            raise ValueError("end_line must be greater than or equal to start_line")
        if self.end_char < self.start_char:
            raise ValueError("end_char must be greater than or equal to start_char")
        return self


class SourceOutlineItem(SourcePlanningModel):
    outline_id: str
    title: str
    level: int
    source_chunk_ids: list[str] = Field(default_factory=list)
    children: list["SourceOutlineItem"] = Field(default_factory=list)

    @field_validator("level")
    @classmethod
    def _validate_level(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("outline level must be positive")
        return value


class SourceOutline(SourcePlanningModel):
    items: list[SourceOutlineItem] = Field(default_factory=list)
    structure_quality: Literal["none", "weak", "usable", "strong"] = "none"


class SourceEvidence(SourcePlanningModel):
    evidence_id: str
    source_chunk_id: str
    quote: str
    relevance: str
    confidence: float = 0.7

    @field_validator("confidence")
    @classmethod
    def _validate_confidence(cls, value: float) -> float:
        if value < 0 or value > 1:
            raise ValueError("confidence must be in [0, 1]")
        return value


class SourceClaim(SourcePlanningModel):
    claim_id: str
    text: str
    source_chunk_ids: list[str] = Field(default_factory=list)
    confidence: float = 0.7
    uncertainty_notes: list[str] = Field(default_factory=list)

    @field_validator("confidence")
    @classmethod
    def _validate_confidence(cls, value: float) -> float:
        if value < 0 or value > 1:
            raise ValueError("confidence must be in [0, 1]")
        return value


class SourceDocument(SourcePlanningModel):
    schema_name: str = SOURCE_DOCUMENT_SCHEMA_NAME
    schema_version: str = SOURCE_DOCUMENT_SCHEMA_VERSION
    document_id: str
    source_path: str
    source_type: Literal["txt", "md", "pdf", "docx"]
    title: str
    chunks: list[SourceChunk] = Field(default_factory=list)
    outline: SourceOutline = Field(default_factory=SourceOutline)
    claims: list[SourceClaim] = Field(default_factory=list)
    evidence: list[SourceEvidence] = Field(default_factory=list)
    figures: list[SourceFigureRef] = Field(default_factory=list)
    tables: list[SourceTableRef] = Field(default_factory=list)
    citations: list[SourceCitation] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    structural_hash: str = ""


class PresentationAudience(SourcePlanningModel):
    label: str = "general"
    expertise_level: Literal["introductory", "working", "expert"] = "working"
    needs: list[str] = Field(default_factory=list)


class PresentationObjective(SourcePlanningModel):
    objective_type: Literal["teach", "inform", "persuade", "decide", "inspire"] = "inform"
    success_criteria: list[str] = Field(default_factory=list)


class DeckNarrative(SourcePlanningModel):
    thesis: str
    audience_takeaway: str
    story_arc: list[str] = Field(default_factory=list)


class BaseDesignProfile(SourcePlanningModel):
    mode: DesignMode
    tone: str
    visual_density: Literal["low", "medium", "high"]
    typography_intent: str
    color_style_intent: str
    chart_table_preference: str
    citation_footer_behavior: str
    section_divider_behavior: str
    image_motif_preference: str
    allowed_layout_families: list[str] = Field(default_factory=list)
    prohibited_design_behavior: list[str] = Field(default_factory=list)


class AcademicDesignProfile(BaseDesignProfile):
    mode: Literal["academic"] = "academic"


class ProfessionalDesignProfile(BaseDesignProfile):
    mode: Literal["professional"] = "professional"


class CreativeDesignProfile(BaseDesignProfile):
    mode: Literal["creative"] = "creative"


DesignProfile = AcademicDesignProfile | ProfessionalDesignProfile | CreativeDesignProfile


class SlideEvidenceAnchor(SourcePlanningModel):
    source_chunk_id: str
    evidence_id: str | None = None
    anchor_text: str
    line_range: tuple[int, int] | None = None
    confidence: float = 0.7

    @field_validator("confidence")
    @classmethod
    def _validate_confidence(cls, value: float) -> float:
        if value < 0 or value > 1:
            raise ValueError("confidence must be in [0, 1]")
        return value


class SlideVisualPlan(SourcePlanningModel):
    visual_category: VisualCategory
    description: str
    source_figure_ids: list[str] = Field(default_factory=list)
    source_table_ids: list[str] = Field(default_factory=list)
    data_requirements: list[str] = Field(default_factory=list)


class SlideSpeakerIntent(SourcePlanningModel):
    primary_intent: str
    speaker_notes_seed: list[str] = Field(default_factory=list)


class SlidePlan(SourcePlanningModel):
    slide_id: str
    section_id: str
    order_index: int
    role: SlideRole
    title: str
    main_message: str
    supporting_points: list[str] = Field(default_factory=list)
    claims: list[SourceClaim] = Field(default_factory=list)
    evidence_anchors: list[SlideEvidenceAnchor] = Field(default_factory=list)
    visual_plan: SlideVisualPlan
    speaker_intent: SlideSpeakerIntent
    uncertainty_notes: list[str] = Field(default_factory=list)

    @field_validator("order_index")
    @classmethod
    def _validate_order_index(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("order_index must be positive")
        return value


class DeckSectionPlan(SourcePlanningModel):
    section_id: str
    title: str
    order_index: int
    objective: str
    target_slide_count: int
    source_chunk_ids: list[str] = Field(default_factory=list)
    slide_ids: list[str] = Field(default_factory=list)

    @field_validator("order_index", "target_slide_count")
    @classmethod
    def _validate_positive_int(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("value must be positive")
        return value


class PresentationPlan(SourcePlanningModel):
    schema_name: str = PRESENTATION_PLAN_SCHEMA_NAME
    schema_version: str = PRESENTATION_PLAN_SCHEMA_VERSION
    plan_id: str
    source_document_id: str
    title: str
    audience: PresentationAudience
    objective: PresentationObjective
    design_mode: DesignMode
    target_slide_count: int
    design_profile: DesignProfile = Field(discriminator="mode")
    narrative: DeckNarrative
    sections: list[DeckSectionPlan] = Field(default_factory=list)
    slides: list[SlidePlan] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    provider_boundary_notes: list[str] = Field(default_factory=list)
    structural_hash: str = ""

    @field_validator("target_slide_count")
    @classmethod
    def _validate_target_slide_count(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("target_slide_count must be positive")
        return value

    @model_validator(mode="after")
    def _validate_design_profile_mode(self) -> "PresentationPlan":
        if self.design_profile.mode != self.design_mode:
            raise ValueError("design_profile.mode must match design_mode")
        return self


class PresentationPlanValidationFinding(SourcePlanningModel):
    code: str
    severity: ValidationSeverity
    message: str
    slide_id: str | None = None
    section_id: str | None = None
    source_chunk_id: str | None = None


class PresentationPlanValidationReport(SourcePlanningModel):
    schema_name: str = PRESENTATION_PLAN_VALIDATION_SCHEMA_NAME
    schema_version: str = PRESENTATION_PLAN_VALIDATION_SCHEMA_VERSION
    plan_id: str
    source_document_id: str
    status: ValidationStatus
    finding_count: int
    error_count: int
    warning_count: int
    findings: list[PresentationPlanValidationFinding] = Field(default_factory=list)
    structural_hash: str = ""


def source_planning_model_to_stable_payload(model: BaseModel, *, include_hash: bool = True) -> dict[str, Any]:
    payload = model.model_dump(mode="json", exclude_none=True, by_alias=True)
    if not include_hash:
        payload.pop("structural_hash", None)
    return _normalize_for_stable_json(payload)


def source_planning_model_to_stable_json(model: BaseModel) -> str:
    return json.dumps(
        source_planning_model_to_stable_payload(model),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def source_planning_structural_hash(model: BaseModel) -> str:
    payload = source_planning_model_to_stable_payload(model, include_hash=False)
    stable_json = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(stable_json.encode("utf-8")).hexdigest()


def with_structural_hash(model: BaseModel) -> BaseModel:
    return model.model_copy(update={"structural_hash": source_planning_structural_hash(model)})


def write_source_planning_json(model: BaseModel, output_path: str | Path) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(source_planning_model_to_stable_json(model) + "\n", encoding="utf-8")
    return output


def load_source_document(path: str | Path) -> SourceDocument:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return SourceDocument.model_validate(payload)


def load_presentation_plan(path: str | Path) -> PresentationPlan:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return PresentationPlan.model_validate(payload)


def _normalize_for_stable_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _normalize_for_stable_json(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_normalize_for_stable_json(item) for item in value]
    if isinstance(value, tuple):
        return [_normalize_for_stable_json(item) for item in value]
    if isinstance(value, float):
        normalized = round(value, 6)
        if normalized == 0:
            return 0
        if float(normalized).is_integer():
            return int(normalized)
        return normalized
    return value
