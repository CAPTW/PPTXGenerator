"""Canonical SlideIR primitives used as the preview/compile boundary."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from .compat.presentation_contracts import (
    AssetKind,
    AssetRecord,
    ContractModel,
    DeckMode,
    DesignSystem,
    LayoutPattern,
    ProductionBridge,
    ProductionMode,
    SchemaModel,
    SlideArchetype,
    SlideDensityBudget,
    SlideEvidenceClass,
    SlideLedger,
    SlideLedgerEntry,
    SlideRole,
    VisualSourcePreference,
    VisualType,
    VizRecord,
)


class IRRect(ContractModel):
    """Axis-aligned rectangle in presentation inches."""

    left: float
    top: float
    width: float
    height: float

    @field_validator("width", "height")
    @classmethod
    def _validate_dimensions(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("width and height must be positive")
        return value

    @property
    def right(self) -> float:
        return self.left + self.width

    @property
    def bottom(self) -> float:
        return self.top + self.height


class SlideIRObject(ContractModel):
    """A single placed semantic object in a slide IR scene."""

    object_id: str
    slot: str
    kind: str
    bounds: IRRect
    text: str | None = None
    source: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("slot", "kind")
    @classmethod
    def _validate_short_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("slot and kind are required")
        return value

    @field_validator("object_id")
    @classmethod
    def _validate_object_id(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("object_id is required")
        return value


class SlideIRSlide(ContractModel):
    """Canonical semantic state for one slide."""

    slide_number: int
    slide_id: str
    title: str
    section: str = ""
    one_line_takeaway: str = ""
    main_message: str = ""
    deck_mode: DeckMode
    slide_role: SlideRole
    visual_type: VisualType
    slide_archetype: SlideArchetype | None = None
    layout_pattern_id: str
    layout_family: str
    layout_warnings: list[str] = Field(default_factory=list)
    numbering_label: str | None = None
    objects: list[SlideIRObject] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    primary_claim: str = ""
    audience_intent: str = ""
    must_keep_text: list[str] = Field(default_factory=list)
    optional_text: list[str] = Field(default_factory=list)
    core_content: list[str] = Field(default_factory=list)
    supporting_evidence: list[str] = Field(default_factory=list)
    required_evidence_assets: list[str] = Field(default_factory=list)
    layout_slot_map: dict[str, str] = Field(default_factory=dict)
    density_budget: SlideDensityBudget | None = None
    evidence_class: SlideEvidenceClass = SlideEvidenceClass.MESSAGE_ONLY
    presenter_notes: str | None = None
    production_bridge: ProductionBridge | None = None
    authoring_payload: dict[str, Any] = Field(default_factory=dict)
    visual_source_preference: VisualSourcePreference | None = None
    production_mode: ProductionMode | None = None
    asset_dependency_kinds: list[AssetKind] = Field(default_factory=list)
    batch_id: str | None = None
    change_note: str | None = None
    unresolved_blockers: list[str] = Field(default_factory=list)

    @field_validator("slide_number")
    @classmethod
    def _validate_slide_number(cls, value: int) -> int:
        if value < 1:
            raise ValueError("slide_number must be positive")
        return value


class SlideIRCompileContext(ContractModel):
    """Compile-only catalogs that allow SlideIR to be the sole internal boundary."""

    design_system: DesignSystem | None = None
    layout_patterns: list[LayoutPattern] = Field(default_factory=list)
    assets: list[AssetRecord] = Field(default_factory=list)
    visuals: list[VizRecord] = Field(default_factory=list)
    slide_ledger: SlideLedger | None = None
    ledger_entries: list[SlideLedgerEntry] = Field(default_factory=list)
    appendix_start: int | None = None
    appendix_boundary_rule: str | None = None
    layout_library_slide_ratio: str | None = None


class SlideIRDocument(SchemaModel):
    """Top-level canonical SlideIR artifact."""

    SCHEMA_NAME = "slide_ir"
    SUMMARY = "Canonical scene graph and geometry for one compilation input."

    deck_title: str
    slide_ratio: str
    slide_width_in: float
    slide_height_in: float
    slides: list[SlideIRSlide] = Field(default_factory=list)
    generation_inputs: dict[str, Any] = Field(default_factory=dict)
    style_prior: SlideIRStylePrior | None = None
    warnings: list[str] = Field(default_factory=list)
    continuity: SlideIRDeckContinuityMetadata | None = None
    compile_context: SlideIRCompileContext | None = None

    @field_validator("slide_width_in", "slide_height_in")
    @classmethod
    def _validate_dimensions(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("slide dimensions must be positive")
        return value

    @field_validator("deck_title")
    @classmethod
    def _validate_deck_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("deck_title is required")
        return value


class SlideIRValidationFinding(ContractModel):
    """Geometry quality finding from SlideIR validation."""

    severity: Literal["error", "warning"]
    code: Literal["out_of_bounds", "overlap", "degenerate", "unknown"]
    message: str
    slide_number: int | None = None
    object_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class SlideIRValidationReport(ContractModel):
    """Validation result for SlideIR geometry."""

    is_valid: bool
    object_count: int
    findings: list[SlideIRValidationFinding] = Field(default_factory=list)

    @property
    def warning_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == "warning")

    @property
    def error_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == "error")

    def as_warning_lines(self) -> list[str]:
        return [f"{finding.code}: {finding.message}" for finding in self.findings if finding.severity == "warning"]


class SlideIRDeckIdentity(ContractModel):
    """Stable deck identity metadata for continuity checks."""

    deck_title: str
    slide_ratio: str


class SlideIRThemeIdentity(ContractModel):
    """Theme-level identity metadata carried alongside SlideIR."""

    theme_name: str | None = None
    brand_name: str | None = None
    visual_route_id: str | None = None
    reference_source_family: str | None = None


class SlideIRSectionStructure(ContractModel):
    """Section grouping summary for continuity validation."""

    section: str
    slide_numbers: list[int] = Field(default_factory=list)
    slide_ids: list[str] = Field(default_factory=list)
    deck_modes: list[str] = Field(default_factory=list)
    layout_families: list[str] = Field(default_factory=list)


class SlideIRTypographyScaleReference(ContractModel):
    """Deck typography scale reference used for continuity checks."""

    token: str
    font_family: str
    size_pt: float
    weight: str
    usage: str = ""


class SlideIRSpacingRhythmReference(ContractModel):
    """Deck spacing rhythm reference used for continuity checks."""

    scale_name: str
    scale_steps_pt: list[float] = Field(default_factory=list)
    margin_in: float | None = None
    gap_in: float | None = None


class SlideIRComponentStyleReference(ContractModel):
    """Repeated component style reference used for continuity checks."""

    component_id: str
    style_family: str
    typography_tokens: list[str] = Field(default_factory=list)
    color_tokens: list[str] = Field(default_factory=list)
    spacing_refs: list[str] = Field(default_factory=list)
    layout_families: list[str] = Field(default_factory=list)


class SlideIRDensityBudgetReference(ContractModel):
    """Deck-level density budget summary."""

    text_char_ceiling: int | None = None
    bullet_count_ceiling: int | None = None
    visual_node_ceiling: int | None = None
    evidence_item_ceiling: int | None = None
    layout_slot_count: int | None = None


class SlideIRContinuityAnchor(ContractModel):
    """Continuity link between adjacent slides."""

    from_slide_number: int
    from_slide_id: str
    to_slide_number: int
    to_slide_id: str
    anchor_type: Literal["sequential", "section", "section_transition", "appendix_transition"]
    label: str


class SlideIRDeckContinuityMetadata(ContractModel):
    """Deck-level continuity metadata carried by the canonical SlideIR document."""

    deck_identity: SlideIRDeckIdentity
    theme_identity: SlideIRThemeIdentity | None = None
    section_structure: list[SlideIRSectionStructure] = Field(default_factory=list)
    typography_scale_refs: list[SlideIRTypographyScaleReference] = Field(default_factory=list)
    spacing_rhythm_refs: list[SlideIRSpacingRhythmReference] = Field(default_factory=list)
    repeated_component_style_refs: list[SlideIRComponentStyleReference] = Field(default_factory=list)
    slide_density_budget: SlideIRDensityBudgetReference | None = None
    continuity_anchors: list[SlideIRContinuityAnchor] = Field(default_factory=list)


class SlideIRContinuityFinding(ContractModel):
    """Warning-only continuity finding derived from multi-slide SlideIR review."""

    severity: Literal["warning"] = "warning"
    code: Literal[
        "title_hierarchy_drift",
        "typography_scale_drift",
        "spacing_rhythm_drift",
        "component_style_drift",
        "section_continuity_break",
        "density_outlier",
    ]
    message: str
    slide_number: int | None = None
    slide_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class SlideIRContinuityReport(ContractModel):
    """Deck-level continuity report. Findings remain advisory in this phase."""

    is_valid: bool = True
    findings: list[SlideIRContinuityFinding] = Field(default_factory=list)

    @property
    def warning_count(self) -> int:
        return len(self.findings)

    def as_guidance_lines(self) -> list[str]:
        return [
            f"Slide IR continuity {finding.code}: slide {finding.slide_number or '?'} - {finding.message}"
            for finding in self.findings
        ]

    def as_warning_lines(self) -> list[str]:
        return list(self.as_guidance_lines())


def _dedupe_continuity_lines(items: list[str] | None) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items or []:
        text = str(item).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        ordered.append(text)
    return ordered


class SlideIRPreviewMetadata(ContractModel):
    """Stable preview-facing metadata derived from SlideIR."""

    slide_count: int
    object_count: int
    slide_ids: list[str] = Field(default_factory=list)
    layout_families: list[str] = Field(default_factory=list)


class SlideIRPaletteSeed(ContractModel):
    """Non-structural palette seed emitted by the style-prior layer."""

    token: str
    hex: str
    usage: str

    @field_validator("hex")
    @classmethod
    def _validate_hex(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized.startswith("#") or len(normalized) not in {4, 7}:
            raise ValueError("style-prior palette seeds require #RGB or #RRGGBB hex colors")
        return normalized


class SlideIRSafeAreaMask(ContractModel):
    """Bounded mask that can constrain backgrounds, motifs, or hero visuals."""

    mask_id: str
    applies_to: Literal["background", "motif", "hero-visual"]
    top_in: float = 0.5
    right_in: float = 0.5
    bottom_in: float = 0.45
    left_in: float = 0.5
    notes: list[str] = Field(default_factory=list)

    @field_validator("top_in", "right_in", "bottom_in", "left_in")
    @classmethod
    def _validate_positive_spacing(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("style-prior safe-area masks require positive dimensions")
        return value


class SlideIRBackgroundLayer(ContractModel):
    """Background or motif layer that can influence look without changing structure."""

    layer_id: str
    scope: Literal["deck", "appendix"]
    layer_type: Literal["solid-fill", "band", "motif", "texture-cue"]
    shape_hint: Literal["full-bleed", "top-band", "right-edge", "bottom-band", "corner-accent"]
    color_token: str
    opacity: float = 0.08
    safe_area_mask_id: str | None = None
    cue: str | None = None

    @field_validator("opacity")
    @classmethod
    def _validate_opacity(cls, value: float) -> float:
        if value < 0 or value > 1:
            raise ValueError("style-prior background opacity must be between 0 and 1")
        return value


class SlideIRMotifAssetSuggestion(ContractModel):
    """Optional motif cue that can later be backed by a concrete asset provider."""

    motif_id: str
    cue: str
    source_kind: Literal["stub", "existing-asset", "generated"] = "stub"
    placement_hint_id: str | None = None
    asset_path: str | None = None


class SlideIRVisualPlacementHint(ContractModel):
    """Non-geometric hint for how an existing visual slot should be styled or emphasized."""

    hint_id: str
    target_slot: str
    anchor_preference: Literal["centered", "left-band", "right-band", "full-bleed-underlay"] = "centered"
    chrome_treatment: Literal["none", "soft-frame", "signal-outline", "muted-shadow"] = "none"
    safe_area_mask_id: str | None = None
    cue: str | None = None
    notes: list[str] = Field(default_factory=list)


class SlideIRHeroVisualSuggestion(ContractModel):
    """Slide-level hero visual cue emitted without taking control of layout geometry."""

    slide_number: int
    slide_id: str
    cue: str
    placement_hint_id: str | None = None
    notes: list[str] = Field(default_factory=list)

    @field_validator("slide_number")
    @classmethod
    def _validate_slide_number(cls, value: int) -> int:
        if value < 1:
            raise ValueError("hero visual suggestions require positive slide numbers")
        return value


class SlideIRStylePrior(ContractModel):
    """Bounded non-structural style prior attached to a SlideIR document."""

    provider_name: str
    provider_mode: Literal["stub", "backend"] = "stub"
    structural_policy_version: str = "1.0"
    allowed_influence: list[str] = Field(
        default_factory=lambda: [
            "design_tokens",
            "safe_area_masks",
            "background_layers",
            "motif_layers",
            "visual_asset_placement_hints",
        ]
    )
    disallowed_influence: list[str] = Field(
        default_factory=lambda: [
            "text_box_geometry",
            "chart_geometry",
            "reading_order",
            "content_hierarchy",
        ]
    )
    palette_seeds: list[SlideIRPaletteSeed] = Field(default_factory=list)
    safe_area_masks: list[SlideIRSafeAreaMask] = Field(default_factory=list)
    background_layers: list[SlideIRBackgroundLayer] = Field(default_factory=list)
    motif_assets: list[SlideIRMotifAssetSuggestion] = Field(default_factory=list)
    hero_visual_suggestions: list[SlideIRHeroVisualSuggestion] = Field(default_factory=list)
    visual_placement_hints: list[SlideIRVisualPlacementHint] = Field(default_factory=list)
    texture_cues: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class SlideIRGeometryObjectSummary(ContractModel):
    """Normalized geometry summary for one object."""

    object_id: str
    slot: str
    kind: str
    left: float
    top: float
    width: float
    height: float
    right: float
    bottom: float


class SlideIRGeometrySlideSummary(ContractModel):
    """Normalized geometry summary for one slide."""

    slide_number: int
    slide_id: str
    layout_family: str
    object_count: int
    objects: list[SlideIRGeometryObjectSummary] = Field(default_factory=list)


class SlideIRCompileReport(SchemaModel):
    """Stable compile-time report derived from the canonical SlideIR boundary."""

    SCHEMA_NAME = "slide_ir_compile_report"
    SUMMARY = "Validation, warnings, preview metadata, and normalized geometry summaries for one SlideIR compile run."

    deck_title: str
    slide_ratio: str
    validation: SlideIRValidationReport
    continuity: SlideIRContinuityReport = Field(default_factory=SlideIRContinuityReport)
    continuity_guidance: list[str] = Field(
        default_factory=list,
        description="Operator-facing continuity guidance derived from the structured continuity report.",
    )
    warnings: list[str] = Field(default_factory=list)
    preview_metadata: SlideIRPreviewMetadata
    geometry_summaries: list[SlideIRGeometrySlideSummary] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _normalize_continuity_guidance_and_mirror(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        if "continuity_guidance" not in data and "continuity_warnings" not in data:
            return data
        payload = dict(data)
        canonical_guidance = _dedupe_continuity_lines(payload.get("continuity_guidance"))
        if not canonical_guidance:
            canonical_guidance = _dedupe_continuity_lines(payload.get("continuity_warnings"))
        payload["continuity_guidance"] = list(canonical_guidance)
        payload.pop("continuity_warnings", None)
        return payload


class SlideIRLayoutCandidateScore(ContractModel):
    """Deterministic score breakdown for one bounded layout candidate."""

    slide_number: int
    slide_id: str
    candidate_id: str
    layout_family: str
    selected: bool = False
    patched: bool = False
    total_score: float
    geometry_score: float
    continuity_score: float
    heuristic_score: float
    aesthetic_score: float = 0.0
    geometry_error_count: int = 0
    geometry_warning_count: int = 0
    continuity_warning_count: int = 0
    quality_signals: dict[str, Any] = Field(default_factory=dict)
    preview_summary: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class SlideIRLayoutCriticReport(SchemaModel):
    """Inspectable layout critic artifact emitted from the SlideIR adapter boundary."""

    SCHEMA_NAME = "slide_ir_layout_critic_report"
    SUMMARY = "Bounded candidate scores and selection metadata for one SlideIR adaptation run."

    deck_title: str
    slide_ratio: str
    critic_enabled: bool = True
    deterministic_fallback_available: bool = True
    selected_candidate_ids: list[str] = Field(default_factory=list)
    scores: list[SlideIRLayoutCandidateScore] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)
