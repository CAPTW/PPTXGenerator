"""Normalize prompt-only and reference-grounded inputs into one planning contract."""

from __future__ import annotations

from typing import Any, Mapping

from ..compat.legacy_non_pptx import (
    BriefMaterialType,
    CanonicalGenerationProfile,
    GenerationInputMode,
    GenerationSafeArea,
    PresentationArchetype,
    PresentationBrief,
    ProjectMaterial,
    ReferenceDNA,
    SlideFunction,
    SlideFunctionOutline,
)


REFERENCE_GROUNDING_TYPES = {
    BriefMaterialType.DOCUMENT,
    BriefMaterialType.IMAGE,
    BriefMaterialType.NOTES,
    BriefMaterialType.DECK,
}

PROMPT_ARCHETYPE_COMPONENTS: dict[PresentationArchetype, list[str]] = {
    PresentationArchetype.EXPLAINER: ["editorial-title", "structured-visual", "summary-close"],
    PresentationArchetype.REPORT: ["metric-summary", "trend-chart", "executive-summary"],
    PresentationArchetype.DECISION: ["decision-title", "compare-grid", "recommendation-close"],
    PresentationArchetype.PITCH: ["hero-proof", "traction-metric", "close-next-step"],
    PresentationArchetype.TRAINING: ["agenda-spine", "process-flow", "recap-close"],
    PresentationArchetype.ARCHITECTURE: ["system-map", "interface-callout", "rollout-plan"],
    PresentationArchetype.TIMELINE: ["milestone-strip", "sequence-visual", "summary-close"],
    PresentationArchetype.PROCESS: ["process-flow", "step-callout", "handoff-summary"],
}

SLIDE_FUNCTION_COMPONENTS: dict[SlideFunction, list[str]] = {
    SlideFunction.TITLE: ["title-card"],
    SlideFunction.AGENDA: ["agenda-list"],
    SlideFunction.SECTION_DIVIDER: ["section-divider"],
    SlideFunction.COMPARE: ["compare-grid"],
    SlideFunction.KPI: ["metric-summary"],
    SlideFunction.TIMELINE: ["timeline-sequence"],
    SlideFunction.ARCHITECTURE: ["system-map"],
    SlideFunction.PROCESS: ["process-flow"],
    SlideFunction.SUMMARY: ["summary-close"],
}


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        cleaned = item.strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            ordered.append(cleaned)
    return ordered


def route_generation_mode(
    *,
    materials: list[ProjectMaterial],
    reference_dna: ReferenceDNA | None = None,
) -> GenerationInputMode:
    if reference_dna is not None:
        return GenerationInputMode.REFERENCE_GROUNDED
    if any(material.material_type in REFERENCE_GROUNDING_TYPES for material in materials):
        return GenerationInputMode.REFERENCE_GROUNDED
    return GenerationInputMode.PROMPT_ONLY


def _brand_tokens(
    presentation_brief: PresentationBrief | None,
    brand_context: Mapping[str, Any] | None,
) -> list[str]:
    tokens: list[str] = []
    if presentation_brief is not None:
        tokens.extend(
            [
                f"brand-mode:{presentation_brief.brand_mode.value}",
                f"tone:{presentation_brief.tone}",
                f"archetype:{presentation_brief.archetype.value}",
            ]
        )
    if brand_context is not None:
        for key in ("brand_name", "primary_color", "accent_color", "font_family", "icon_style", "section_divider_style"):
            value = str(brand_context.get(key, "")).strip()
            if value:
                tokens.append(f"{key}:{value}")
        for key in ("tone_keywords", "chart_preferences", "prohibited_elements"):
            values = brand_context.get(key, [])
            if isinstance(values, str):
                values = [values]
            if isinstance(values, list):
                tokens.extend(f"{key}:{str(value).strip()}" for value in values if str(value).strip())
    if not tokens:
        tokens.append("brand:generic-professional")
    return _dedupe(tokens)


def _continuity_defaults(
    mode: GenerationInputMode,
    reference_dna: ReferenceDNA | None,
    presentation_brief: PresentationBrief | None,
) -> list[str]:
    defaults = [
        "Keep title hierarchy stable across the deck.",
        "Maintain one typography scale and spacing rhythm.",
        "Reuse section-divider treatment consistently.",
    ]
    if presentation_brief is not None:
        defaults.append(f"Keep slide density aligned with {presentation_brief.visual_density.value} visual density.")
    if mode == GenerationInputMode.REFERENCE_GROUNDED and reference_dna is not None:
        defaults.extend(reference_dna.hierarchy_behavior[:1])
        defaults.extend(reference_dna.whitespace_behavior[:1])
    return _dedupe(defaults)


def _safe_area(
    mode: GenerationInputMode,
    reference_dna: ReferenceDNA | None,
) -> GenerationSafeArea:
    notes = ["Use compile-safe 16:9 margins after one normalization step."]
    if mode == GenerationInputMode.REFERENCE_GROUNDED and reference_dna is not None:
        notes.extend(reference_dna.whitespace_behavior[:2])
    else:
        notes.append("Prompt-only mode defaults to conservative editorial margins.")
    return GenerationSafeArea(notes=_dedupe(notes))


def _source_summary(
    mode: GenerationInputMode,
    materials: list[ProjectMaterial],
    reference_dna: ReferenceDNA | None,
    presentation_brief: PresentationBrief | None,
) -> list[str]:
    if mode == GenerationInputMode.REFERENCE_GROUNDED:
        if reference_dna is not None and reference_dna.source_files:
            return _dedupe([f"{source.label} ({source.material_type.value})" for source in reference_dna.source_files])
        return _dedupe([f"{material.label} ({material.material_type.value})" for material in materials]) or [
            "Reference-grounded mode without a scanned reference pack."
        ]
    prompt = (presentation_brief.source_prompt if presentation_brief is not None else "").strip() if presentation_brief else ""
    summary = ["Prompt-only brief inference with no attached reference pack."]
    if prompt:
        summary.append(prompt)
    return _dedupe(summary)


def _reference_structure_hints(reference_dna: ReferenceDNA | None) -> list[str]:
    if reference_dna is None:
        return ["Reference-grounded materials are present; preserve a one-message-per-slide structure."]
    return _dedupe(
        [
            *reference_dna.layout_logic[:3],
            *reference_dna.hierarchy_behavior[:2],
            *reference_dna.whitespace_behavior[:2],
            *reference_dna.pacing_and_title_behavior[:2],
        ]
    ) or ["Preserve the strongest reference layout signals after normalization."]


def _prompt_structure_hints(
    presentation_brief: PresentationBrief | None,
    slide_function_outline: SlideFunctionOutline | None,
) -> list[str]:
    hints = ["One main message per slide.", "Resolve planning before layout selection begins."]
    if presentation_brief is not None:
        hints.append(f"Archetype-led structure: {presentation_brief.archetype.value}.")
    if slide_function_outline is not None:
        hints.append(f"Function-tagged outline with {slide_function_outline.target_slide_count} planned slides.")
    return _dedupe(hints)


def _reference_style_tokens(reference_dna: ReferenceDNA | None) -> list[str]:
    if reference_dna is None:
        return ["reference-mode", "default-editorial-spacing"]
    return _dedupe(
        [
            f"source-family:{reference_dna.source_family}",
            *reference_dna.patterns_worth_borrowing[:4],
            reference_dna.section_divider_style,
            *reference_dna.chart_table_treatment[:2],
            *reference_dna.icon_illustration_treatment[:2],
        ]
    )


def _prompt_style_tokens(presentation_brief: PresentationBrief | None) -> list[str]:
    tokens = ["prompt-mode", "default-editorial-spacing"]
    if presentation_brief is not None:
        tokens.extend(
            [
                f"archetype:{presentation_brief.archetype.value}",
                f"evidence-density:{presentation_brief.evidence_density.value}",
                f"visual-density:{presentation_brief.visual_density.value}",
            ]
        )
    return _dedupe(tokens)


def _reference_component_archetypes(materials: list[ProjectMaterial], reference_dna: ReferenceDNA | None) -> list[str]:
    archetypes: list[str] = []
    for material in materials:
        if material.material_type == BriefMaterialType.DOCUMENT:
            archetypes.append("document-crop")
        elif material.material_type == BriefMaterialType.IMAGE:
            archetypes.append("annotated-image")
        elif material.material_type == BriefMaterialType.DECK:
            archetypes.append("layout-remix")
        elif material.material_type == BriefMaterialType.NOTES:
            archetypes.append("editorial-annotation")
        elif material.material_type in {BriefMaterialType.DATA, BriefMaterialType.SPREADSHEET}:
            archetypes.append("structured-visual")
    if reference_dna is not None:
        for pattern in reference_dna.patterns_worth_borrowing:
            lowered = pattern.lower()
            if "divider" in lowered:
                archetypes.append("section-divider")
            if "chart" in lowered or "table" in lowered:
                archetypes.append("structured-visual")
            if "screenshot" in lowered or "screen" in lowered:
                archetypes.append("annotated-image")
    return _dedupe(archetypes) or ["document-crop", "structured-visual"]


def _prompt_component_archetypes(
    presentation_brief: PresentationBrief | None,
    slide_function_outline: SlideFunctionOutline | None,
) -> list[str]:
    archetypes: list[str] = []
    if presentation_brief is not None:
        archetypes.extend(PROMPT_ARCHETYPE_COMPONENTS.get(presentation_brief.archetype, ["structured-visual"]))
    if slide_function_outline is not None:
        for item in slide_function_outline.slides:
            archetypes.extend(SLIDE_FUNCTION_COMPONENTS.get(item.slide_function, []))
    return _dedupe(archetypes) or ["title-card", "structured-visual"]


def _reference_sectioning_hints(reference_dna: ReferenceDNA | None) -> list[str]:
    if reference_dna is None:
        return ["Reference-grounded mode preserves appendix separation and source-led section breaks."]
    return _dedupe(
        [
            reference_dna.section_divider_style,
            *reference_dna.section_guardrails[:3],
            *reference_dna.pacing_and_title_behavior[:2],
        ]
    )


def _prompt_sectioning_hints(slide_function_outline: SlideFunctionOutline | None) -> list[str]:
    hints = ["Keep appendix detail outside the core story by default."]
    if slide_function_outline is not None:
        hints.extend(f"{item.slide_number}:{item.section}" for item in slide_function_outline.slides[:10])
    return _dedupe(hints)


def _reference_visual_motifs(reference_dna: ReferenceDNA | None) -> list[str]:
    if reference_dna is None:
        return ["Use local proof objects and restrained annotations."]
    return _dedupe(
        [
            *reference_dna.patterns_worth_borrowing[:4],
            *reference_dna.layout_logic[:2],
            *reference_dna.chart_table_treatment[:2],
        ]
    )


def _prompt_visual_motifs(
    presentation_brief: PresentationBrief | None,
    slide_function_outline: SlideFunctionOutline | None,
) -> list[str]:
    motifs = ["One dominant visual zone per slide.", "Short thesis title with compact support copy."]
    if presentation_brief is not None and presentation_brief.archetype == PresentationArchetype.ARCHITECTURE:
        motifs.append("Prefer structural diagrams and process sequencing over decorative visuals.")
    if slide_function_outline is not None:
        functions = [item.slide_function for item in slide_function_outline.slides]
        if SlideFunction.KPI in functions:
            motifs.append("Lead quantitative slides with one primary metric frame.")
        if SlideFunction.COMPARE in functions:
            motifs.append("Keep comparison slides tightly bounded around explicit tradeoffs.")
    return _dedupe(motifs)


def _slide_function_defaults(slide_function_outline: SlideFunctionOutline | None) -> list[str]:
    if slide_function_outline is None:
        return ["title", "summary"]
    return _dedupe([item.slide_function.value for item in slide_function_outline.slides])


def build_canonical_generation_profile(
    *,
    deck_title: str,
    materials: list[ProjectMaterial],
    presentation_brief: PresentationBrief | None,
    slide_function_outline: SlideFunctionOutline | None,
    reference_dna: ReferenceDNA | None = None,
    brand_context: Mapping[str, Any] | None = None,
) -> CanonicalGenerationProfile:
    mode = route_generation_mode(materials=materials, reference_dna=reference_dna)
    if mode == GenerationInputMode.REFERENCE_GROUNDED:
        return CanonicalGenerationProfile(
            deck_title=deck_title,
            mode=mode,
            source_prompt=presentation_brief.source_prompt if presentation_brief is not None else None,
            reference_source_family=reference_dna.source_family if reference_dna is not None else None,
            source_summary=_source_summary(mode, materials, reference_dna, presentation_brief),
            structure_hints=_reference_structure_hints(reference_dna),
            style_tokens=_reference_style_tokens(reference_dna),
            safe_area=_safe_area(mode, reference_dna),
            component_archetypes=_reference_component_archetypes(materials, reference_dna),
            sectioning_hints=_reference_sectioning_hints(reference_dna),
            reusable_visual_motifs=_reference_visual_motifs(reference_dna),
            brand_token_set=_brand_tokens(presentation_brief, brand_context),
            deck_continuity_defaults=_continuity_defaults(mode, reference_dna, presentation_brief),
            slide_function_defaults=_slide_function_defaults(slide_function_outline),
            notes=[
                "Reference-grounded inputs are normalized before canonical planning and SlideIR adaptation.",
                "Downstream compile and preview consume the same canonical profile regardless of source mode.",
            ],
        )
    return CanonicalGenerationProfile(
        deck_title=deck_title,
        mode=mode,
        source_prompt=presentation_brief.source_prompt if presentation_brief is not None else None,
        source_summary=_source_summary(mode, materials, reference_dna, presentation_brief),
        structure_hints=_prompt_structure_hints(presentation_brief, slide_function_outline),
        style_tokens=_prompt_style_tokens(presentation_brief),
        safe_area=_safe_area(mode, reference_dna),
        component_archetypes=_prompt_component_archetypes(presentation_brief, slide_function_outline),
        sectioning_hints=_prompt_sectioning_hints(slide_function_outline),
        reusable_visual_motifs=_prompt_visual_motifs(presentation_brief, slide_function_outline),
        brand_token_set=_brand_tokens(presentation_brief, brand_context),
        deck_continuity_defaults=_continuity_defaults(mode, reference_dna, presentation_brief),
        slide_function_defaults=_slide_function_defaults(slide_function_outline),
        notes=[
            "Prompt-only inputs are normalized before canonical planning and SlideIR adaptation.",
            "Downstream compile and preview consume the same canonical profile regardless of source mode.",
        ],
    )
