"""Deterministic heuristic planner for local source-to-deck POCs."""

from __future__ import annotations

import math
from pathlib import Path

from .source_planning import (
    AcademicDesignProfile,
    CreativeDesignProfile,
    DeckNarrative,
    DeckSectionPlan,
    DesignMode,
    PresentationAudience,
    PresentationObjective,
    PresentationPlan,
    ProfessionalDesignProfile,
    SlideEvidenceAnchor,
    SlidePlan,
    SlideSpeakerIntent,
    SlideVisualPlan,
    SourceClaim,
    SourceDocument,
    load_source_document,
    with_structural_hash,
    write_source_planning_json,
)


def plan_deck_from_source_document(
    source_document: SourceDocument,
    *,
    design_mode: DesignMode,
    target_slide_count: int,
) -> PresentationPlan:
    if target_slide_count <= 0:
        raise ValueError("target_slide_count must be positive")
    sections = _build_sections(source_document, target_slide_count)
    slides = _build_slides(source_document, sections, target_slide_count, design_mode)
    warnings: list[str] = []
    if source_document.outline.structure_quality in {"none", "weak"}:
        warnings.append("insufficient_source_structure")
    if len(slides) < max(1, target_slide_count - 2) or len(slides) > target_slide_count + 2:
        warnings.append("target_slide_count_approximate")
    provider_notes = [
        "Codex/GPT providers may emit PresentationPlan JSON but must pass validation before rendering.",
        "Ollama/local LLM providers should emit small validated JSON fragments and never execute tools directly.",
        "GPT-Image-2 belongs to structured design proposal JSON, not slide text, evidence, chart data, or geometry truth.",
        "SceneDeck remains the deterministic editable PPTX rendering boundary.",
    ]
    plan = PresentationPlan(
        plan_id=f"plan-{source_document.document_id}-{design_mode}",
        source_document_id=source_document.document_id,
        title=source_document.title,
        audience=_audience_for_mode(design_mode),
        objective=_objective_for_mode(design_mode),
        design_mode=design_mode,
        target_slide_count=target_slide_count,
        design_profile=design_profile_for_mode(design_mode),
        narrative=DeckNarrative(
            thesis=_thesis_from_source(source_document),
            audience_takeaway=_takeaway_for_mode(design_mode, source_document),
            story_arc=[section.title for section in sections],
        ),
        sections=sections,
        slides=slides,
        warnings=warnings,
        provider_boundary_notes=provider_notes,
    )
    return with_structural_hash(plan)  # type: ignore[return-value]


def plan_deck_from_source_document_file(
    *,
    source_document_path: str | Path,
    design_mode: DesignMode,
    target_slide_count: int,
) -> PresentationPlan:
    return plan_deck_from_source_document(
        load_source_document(source_document_path),
        design_mode=design_mode,
        target_slide_count=target_slide_count,
    )


def write_presentation_plan(plan: PresentationPlan, output_path: str | Path) -> Path:
    return write_source_planning_json(plan, output_path)


def design_profile_for_mode(design_mode: DesignMode):
    if design_mode == "academic":
        return AcademicDesignProfile(
            tone="precise, evidence-forward, citation-aware",
            visual_density="high",
            typography_intent="legible scholarly hierarchy with restrained emphasis",
            color_style_intent="low-saturation palette with one analytical accent",
            chart_table_preference="prefer tables, charts, and evidence matrices over decorative visuals",
            citation_footer_behavior="include compact citation/source anchors on evidence-heavy slides",
            section_divider_behavior="minimal divider with research question or module label",
            image_motif_preference="figures and document crops only when source-backed",
            allowed_layout_families=["title", "section-divider", "evidence-table", "concept-explanation", "summary"],
            prohibited_design_behavior=["decorative stock imagery", "unsupported claims", "overly large hero typography"],
        )
    if design_mode == "creative":
        return CreativeDesignProfile(
            tone="expressive, memorable, audience-oriented",
            visual_density="medium",
            typography_intent="strong display moments balanced with readable body text",
            color_style_intent="distinctive palette with controlled accent contrast",
            chart_table_preference="turn data into simple visual metaphors when evidence permits",
            citation_footer_behavior="keep evidence anchors available without dominating the slide",
            section_divider_behavior="use high-signal thematic dividers",
            image_motif_preference="motifs and image directions may be proposed, but source evidence remains textual",
            allowed_layout_families=["title", "section-divider", "story-card", "comparison", "callout", "summary"],
            prohibited_design_behavior=["image as source of truth", "unvalidated visual claims", "busy collage layouts"],
        )
    return ProfessionalDesignProfile(
        tone="clear, decision-oriented, executive-readable",
        visual_density="medium",
        typography_intent="compact business hierarchy with strong scanability",
        color_style_intent="neutral surface palette with action-oriented accent",
        chart_table_preference="prefer concise charts, tables, and comparison views",
        citation_footer_behavior="use short source notes only when needed for credibility",
        section_divider_behavior="use concise business section headers",
        image_motif_preference="use motifs sparingly; prioritize business evidence and diagrams",
        allowed_layout_families=["title", "section-divider", "executive-summary", "chart", "table", "recommendation"],
        prohibited_design_behavior=["academic density on every slide", "unsupported recommendations", "decorative clutter"],
    )


def _build_sections(source_document: SourceDocument, target_slide_count: int) -> list[DeckSectionPlan]:
    chunk_ids = [chunk.chunk_id for chunk in source_document.chunks]
    outline_items = [item for item in source_document.outline.items if item.source_chunk_ids]
    if not outline_items:
        outline_items = []
    section_count = min(max(1, len(outline_items)), max(1, target_slide_count - 2))
    if section_count == 0:
        section_count = 1
    sections: list[DeckSectionPlan] = []
    if outline_items:
        for index, item in enumerate(outline_items[:section_count], start=1):
            sections.append(
                DeckSectionPlan(
                    section_id=f"section-{index:02d}",
                    title=item.title,
                    order_index=index,
                    objective=f"Explain {item.title}",
                    target_slide_count=max(1, math.ceil(target_slide_count / max(1, section_count))),
                    source_chunk_ids=list(item.source_chunk_ids),
                    slide_ids=[],
                )
            )
    else:
        sections.append(
            DeckSectionPlan(
                section_id="section-01",
                title="Source Overview",
                order_index=1,
                objective="Summarize the source document",
                target_slide_count=max(1, target_slide_count),
                source_chunk_ids=chunk_ids,
                slide_ids=[],
            )
        )
    assigned = {chunk_id for section in sections for chunk_id in section.source_chunk_ids}
    for chunk_id in chunk_ids:
        if chunk_id not in assigned:
            sections[-1].source_chunk_ids.append(chunk_id)
    return sections


def _build_slides(
    source_document: SourceDocument,
    sections: list[DeckSectionPlan],
    target_slide_count: int,
    design_mode: DesignMode,
) -> list[SlidePlan]:
    slides: list[SlidePlan] = []
    title_section_id = sections[0].section_id if sections else "section-01"
    slides.append(
        SlidePlan(
            slide_id="slide-001",
            section_id=title_section_id,
            order_index=1,
            role="title",
            title=source_document.title,
            main_message=_thesis_from_source(source_document),
            supporting_points=[],
            evidence_anchors=[],
            visual_plan=SlideVisualPlan(visual_category="text", description="Title and framing statement"),
            speaker_intent=SlideSpeakerIntent(primary_intent="Orient the audience to the source-derived deck."),
        )
    )
    if sections:
        sections[0].slide_ids.append("slide-001")
    slides.append(
        SlidePlan(
            slide_id="slide-002",
            section_id=title_section_id,
            order_index=2,
            role="agenda",
            title="Roadmap",
            main_message="The deck follows the source structure and keeps claims tied to evidence anchors.",
            supporting_points=[section.title for section in sections],
            evidence_anchors=[],
            visual_plan=SlideVisualPlan(visual_category="text", description="Agenda based on detected source sections"),
            speaker_intent=SlideSpeakerIntent(primary_intent="Preview the source-derived section structure."),
        )
    )
    if sections:
        sections[0].slide_ids.append("slide-002")
    for section in sections:
        slide_id = f"slide-{len(slides) + 1:03d}"
        slides.append(
            SlidePlan(
                slide_id=slide_id,
                section_id=section.section_id,
                order_index=len(slides) + 1,
                role="section-divider",
                title=section.title,
                main_message=section.objective,
                supporting_points=[],
                evidence_anchors=[],
                visual_plan=SlideVisualPlan(visual_category="section-divider", description="Section divider from source outline"),
                speaker_intent=SlideSpeakerIntent(primary_intent=f"Transition into {section.title}."),
            )
        )
        section.slide_ids.append(slide_id)
    content_budget = max(1, target_slide_count - 2)
    content_chunks = _select_content_chunks(source_document, content_budget)
    chunk_by_id = {chunk.chunk_id: chunk for chunk in source_document.chunks}
    section_by_chunk: dict[str, DeckSectionPlan] = {}
    for section in sections:
        for chunk_id in section.source_chunk_ids:
            section_by_chunk[chunk_id] = section
    for chunk in content_chunks:
        section = section_by_chunk.get(chunk.chunk_id, sections[-1])
        slide_id = f"slide-{len(slides) + 1:03d}"
        claim = SourceClaim(
            claim_id=f"claim-{len(slides):03d}",
            text=_main_message(chunk.text),
            source_chunk_ids=[chunk.chunk_id],
            confidence=0.65,
        )
        slide = SlidePlan(
            slide_id=slide_id,
            section_id=section.section_id,
            order_index=len(slides) + 1,
            role=_role_for_mode(design_mode, chunk.text),
            title=_slide_title(chunk, section.title),
            main_message=claim.text,
            supporting_points=_supporting_points(chunk.text),
            claims=[claim],
            evidence_anchors=[
                SlideEvidenceAnchor(
                    source_chunk_id=chunk.chunk_id,
                    anchor_text=_anchor_text(chunk.text),
                    line_range=(chunk.start_line, chunk.end_line),
                    confidence=0.7,
                )
            ],
            visual_plan=_visual_plan_for_chunk(chunk.text, design_mode),
            speaker_intent=SlideSpeakerIntent(
                primary_intent=f"Explain the source-backed point from {section.title}.",
                speaker_notes_seed=[_anchor_text(chunk.text)],
            ),
        )
        slides.append(slide)
        section.slide_ids.append(slide_id)
    slides.append(
        SlidePlan(
            slide_id=f"slide-{len(slides) + 1:03d}",
            section_id=sections[-1].section_id,
            order_index=len(slides) + 1,
            role="summary",
            title="Key Takeaways",
            main_message=_takeaway_for_mode(design_mode, source_document),
            supporting_points=[section.title for section in sections[:4]],
            evidence_anchors=[
                SlideEvidenceAnchor(
                    source_chunk_id=source_document.chunks[0].chunk_id,
                    anchor_text=_anchor_text(source_document.chunks[0].text),
                    line_range=(source_document.chunks[0].start_line, source_document.chunks[0].end_line),
                    confidence=0.6,
                )
            ]
            if source_document.chunks
            else [],
            visual_plan=SlideVisualPlan(visual_category="framework", description="Summary of the deck's source-backed arc"),
            speaker_intent=SlideSpeakerIntent(primary_intent="Close with the most important source-backed implications."),
        )
    )
    sections[-1].slide_ids.append(slides[-1].slide_id)
    return slides


def _select_content_chunks(source_document: SourceDocument, content_budget: int):
    chunks = source_document.chunks
    if len(chunks) <= content_budget:
        return chunks
    if content_budget <= 1:
        return chunks[:1]
    step = (len(chunks) - 1) / (content_budget - 1)
    selected_indexes = sorted({round(index * step) for index in range(content_budget)})
    return [chunks[index] for index in selected_indexes[:content_budget]]


def _audience_for_mode(design_mode: DesignMode) -> PresentationAudience:
    if design_mode == "academic":
        return PresentationAudience(label="academic audience", expertise_level="expert", needs=["evidence traceability", "method clarity"])
    if design_mode == "creative":
        return PresentationAudience(label="creative audience", expertise_level="working", needs=["memorable story", "clear evidence"])
    return PresentationAudience(label="professional audience", expertise_level="working", needs=["executive summary", "decision-ready implications"])


def _objective_for_mode(design_mode: DesignMode) -> PresentationObjective:
    if design_mode == "academic":
        return PresentationObjective(objective_type="teach", success_criteria=["claims are source-backed", "figures and tables are traceable"])
    if design_mode == "creative":
        return PresentationObjective(objective_type="inspire", success_criteria=["story is memorable", "claims remain evidence-backed"])
    return PresentationObjective(objective_type="inform", success_criteria=["recommendations are clear", "source-backed implications are easy to scan"])


def _thesis_from_source(source_document: SourceDocument) -> str:
    if source_document.chunks:
        return _main_message(source_document.chunks[0].text)
    return f"Source-derived presentation plan for {source_document.title}"


def _takeaway_for_mode(design_mode: DesignMode, source_document: SourceDocument) -> str:
    prefix = {
        "academic": "The source supports a structured evidence path:",
        "professional": "The source can be translated into a decision-ready storyline:",
        "creative": "The source can become a memorable evidence-backed narrative:",
    }[design_mode]
    return f"{prefix} {source_document.title}"


def _role_for_mode(design_mode: DesignMode, text: str) -> str:
    lower = text.lower()
    if "recommend" in lower or "should" in lower:
        return "recommendation"
    if "table" in lower or "figure" in lower or "data" in lower:
        return "evidence"
    if design_mode == "creative":
        return "analysis"
    return "analysis"


def _visual_plan_for_chunk(text: str, design_mode: DesignMode) -> SlideVisualPlan:
    lower = text.lower()
    if "table" in lower:
        return SlideVisualPlan(visual_category="table", description="Source-backed table or matrix derived from referenced table text")
    if "figure" in lower or "fig." in lower:
        return SlideVisualPlan(visual_category="image", description="Source figure reference or document crop candidate")
    if "trend" in lower or "increase" in lower or "decrease" in lower or "%" in lower or "percent" in lower:
        return SlideVisualPlan(visual_category="chart", description="Simple chart if structured numeric data is available")
    if design_mode == "creative":
        return SlideVisualPlan(visual_category="framework", description="Narrative visual framework anchored to source text")
    return SlideVisualPlan(visual_category="text", description="Text-led slide with concise source-backed points")


def _slide_title(chunk, fallback: str) -> str:
    if chunk.heading_path:
        return chunk.heading_path[-1]
    return fallback


def _main_message(text: str) -> str:
    compact = " ".join(text.split())
    if not compact:
        return "Source-backed point requires additional text."
    first = compact.split(". ", 1)[0].strip()
    return first[:180] + ("..." if len(first) > 180 else "")


def _supporting_points(text: str) -> list[str]:
    sentences = [sentence.strip() for sentence in " ".join(text.split()).split(". ") if sentence.strip()]
    return [sentence[:160] for sentence in sentences[1:4]]


def _anchor_text(text: str) -> str:
    return " ".join(text.split())[:240]
