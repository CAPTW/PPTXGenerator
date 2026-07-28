"""Bridge validated PresentationPlan artifacts into draft compile state."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .compat.state_io import load_state_file
from .pipeline.presentation_plan_validation import (
    PresentationPlanValidationReport,
    validate_presentation_plan,
    write_presentation_plan_validation_report,
)
from .source_planning import (
    PresentationPlan,
    SlidePlan,
    SourceDocument,
    load_presentation_plan,
    load_source_document,
    source_planning_model_to_stable_json,
    write_source_planning_json,
)


BRIDGE_REPORT_VERSION = "0.1"

SUPPORTED_LAYOUT_PATTERN_IDS = {
    "cover-signal",
    "agenda-roadmap",
    "headline-evidence",
    "appendix-reference",
    "comparison",
    "process-flow",
}
CONTENT_ROLES = {"analysis", "evidence", "recommendation", "appendix", "summary"}


class PresentationPlanBridgeModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class BridgeFinding(PresentationPlanBridgeModel):
    code: str
    severity: Literal["info", "warning", "error"] = "warning"
    message: str
    slide_id: str | None = None
    detail: dict[str, Any] = Field(default_factory=dict)


class SourceEvidenceMapEntry(PresentationPlanBridgeModel):
    plan_slide_id: str
    state_slide_id: str
    slide_number: int
    title: str
    source_chunk_ids: list[str] = Field(default_factory=list)
    anchors: list[dict[str, Any]] = Field(default_factory=list)
    evidence_snippets: list[str] = Field(default_factory=list)


class SourceEvidenceMap(PresentationPlanBridgeModel):
    schema_name: str = "source_evidence_map"
    schema_version: str = "0.1"
    source_document_id: str
    presentation_plan_id: str
    slide_count: int
    entries: list[SourceEvidenceMapEntry] = Field(default_factory=list)
    structural_hash: str = ""


class PresentationPlanBridgeReport(PresentationPlanBridgeModel):
    report_version: str = BRIDGE_REPORT_VERSION
    source_document_path: str
    presentation_plan_path: str
    output_state_dir: str
    design_mode: str
    target_slide_count: int
    generated_slide_count: int
    section_count: int
    evidence_anchor_count: int
    slides_with_evidence_count: int
    slides_without_evidence_count: int
    generated_artifacts: dict[str, str] = Field(default_factory=dict)
    copied_template_artifacts: dict[str, str] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    findings: list[BridgeFinding] = Field(default_factory=list)
    structural_hash: str = ""


class PresentationPlanBridgeOutputs(PresentationPlanBridgeModel):
    report: PresentationPlanBridgeReport
    validation_report: PresentationPlanValidationReport
    artifact_paths: dict[str, str]


def build_state_from_presentation_plan_files(
    *,
    source_document_path: str | Path,
    presentation_plan_path: str | Path,
    output_state_dir: str | Path,
    validation_output_path: str | Path | None = None,
) -> PresentationPlanBridgeOutputs:
    source_document = load_source_document(source_document_path)
    plan = load_presentation_plan(presentation_plan_path)
    validation_report = validate_presentation_plan(plan, source_document)
    if validation_report.status == "failed":
        raise ValueError("presentation plan validation failed; refusing to build draft state")
    return build_state_from_presentation_plan(
        source_document=source_document,
        presentation_plan=plan,
        source_document_path=source_document_path,
        presentation_plan_path=presentation_plan_path,
        output_state_dir=output_state_dir,
        validation_report=validation_report,
        validation_output_path=validation_output_path,
    )


def build_state_from_presentation_plan(
    *,
    source_document: SourceDocument,
    presentation_plan: PresentationPlan,
    source_document_path: str | Path,
    presentation_plan_path: str | Path,
    output_state_dir: str | Path,
    validation_report: PresentationPlanValidationReport | None = None,
    validation_output_path: str | Path | None = None,
) -> PresentationPlanBridgeOutputs:
    validation = validation_report or validate_presentation_plan(presentation_plan, source_document)
    if validation.status == "failed":
        raise ValueError("presentation plan validation failed; refusing to build draft state")

    output_dir = Path(output_state_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    findings: list[BridgeFinding] = []
    warnings: list[str] = []
    deck_title = presentation_plan.title
    slide_records = [
        _map_slide_to_state(slide, index, presentation_plan, source_document, findings)
        for index, slide in enumerate(presentation_plan.slides, start=1)
    ]
    evidence_map = _build_evidence_map(source_document, presentation_plan, slide_records)
    artifacts: dict[str, Path] = {}
    copied: dict[str, str] = {}

    artifacts["source_document"] = write_source_planning_json(source_document, output_dir / "source-document.json")
    artifacts["presentation_plan"] = write_source_planning_json(presentation_plan, output_dir / "presentation-plan.json")
    artifacts["presentation_plan_validation"] = write_presentation_plan_validation_report(
        validation,
        validation_output_path or output_dir / "presentation-plan-validation.json",
    )
    artifacts["blueprint"] = _write_json(output_dir / "blueprint.json", _build_blueprint(deck_title, presentation_plan, slide_records))
    artifacts["design_system"] = _write_json(output_dir / "design-system.json", _build_design_system(deck_title, presentation_plan))
    artifacts["deck_constitution"] = _write_json(output_dir / "deck-constitution.json", _build_deck_constitution(deck_title, presentation_plan))
    artifacts["layout_library"] = _write_json(output_dir / "layout-library.json", _build_layout_library(deck_title))
    artifacts["slide_ledger"] = _write_json(output_dir / "slide-ledger.json", _build_slide_ledger(deck_title, slide_records))
    artifacts["asset_manifest"] = _write_json(output_dir / "asset-manifest.json", _build_asset_manifest(deck_title, findings))
    artifacts["viz_manifest"] = _write_json(output_dir / "viz-manifest.json", _build_viz_manifest(deck_title, findings))
    artifacts["source_evidence_map"] = _write_json(
        output_dir / "source-evidence-map.json",
        _model_payload_with_hash(evidence_map),
    )
    _validate_generated_state_artifacts(output_dir, artifacts, findings)
    artifacts["bridge_report"] = output_dir / "bridge-report.json"

    evidence_anchor_count = sum(len(slide.evidence_anchors) for slide in presentation_plan.slides)
    slides_with_evidence = sum(1 for slide in presentation_plan.slides if slide.evidence_anchors)
    report = PresentationPlanBridgeReport(
        source_document_path=str(Path(source_document_path).resolve()),
        presentation_plan_path=str(Path(presentation_plan_path).resolve()),
        output_state_dir=str(output_dir),
        design_mode=presentation_plan.design_mode,
        target_slide_count=presentation_plan.target_slide_count,
        generated_slide_count=len(presentation_plan.slides),
        section_count=len(presentation_plan.sections),
        evidence_anchor_count=evidence_anchor_count,
        slides_with_evidence_count=slides_with_evidence,
        slides_without_evidence_count=len(presentation_plan.slides) - slides_with_evidence,
        generated_artifacts={key: str(path.resolve()) for key, path in sorted(artifacts.items())},
        copied_template_artifacts=copied,
        warnings=warnings,
        findings=sorted(findings, key=lambda item: (item.severity, item.code, item.slide_id or "", item.message)),
        structural_hash="",
    )
    report = report.model_copy(update={"structural_hash": bridge_report_structural_hash(report)})
    report_path = write_bridge_report(report, artifacts["bridge_report"])
    return PresentationPlanBridgeOutputs(
        report=report,
        validation_report=validation,
        artifact_paths={key: str(path.resolve()) for key, path in sorted(artifacts.items())},
    )


def write_bridge_report(report: PresentationPlanBridgeReport, output_path: str | Path) -> Path:
    return _write_json(output_path, bridge_report_to_stable_payload(report))


def bridge_report_to_stable_json(report: PresentationPlanBridgeReport) -> str:
    return json.dumps(bridge_report_to_stable_payload(report), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def bridge_report_to_stable_payload(report: PresentationPlanBridgeReport, *, include_paths: bool = True) -> dict[str, Any]:
    payload = report.model_dump(mode="json", exclude_none=True)
    if not include_paths:
        for key in ("source_document_path", "presentation_plan_path", "output_state_dir", "generated_artifacts", "copied_template_artifacts"):
            payload.pop(key, None)
    return _normalize(payload)


def bridge_report_structural_hash(report: PresentationPlanBridgeReport) -> str:
    payload = bridge_report_to_stable_payload(report, include_paths=False)
    payload.pop("structural_hash", None)
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")).hexdigest()


def source_evidence_map_structural_hash(evidence_map: SourceEvidenceMap) -> str:
    payload = evidence_map.model_dump(mode="json", exclude_none=True)
    payload.pop("structural_hash", None)
    return hashlib.sha256(json.dumps(_normalize(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")).hexdigest()


def summarize_bridge_report(report: PresentationPlanBridgeReport) -> list[str]:
    error_count = sum(1 for finding in report.findings if finding.severity == "error")
    warning_count = sum(1 for finding in report.findings if finding.severity == "warning")
    return [
        (
            "PRESENTATION_PLAN_BRIDGE "
            f"design_mode={report.design_mode} "
            f"slides={report.generated_slide_count} "
            f"sections={report.section_count} "
            f"evidence_anchors={report.evidence_anchor_count} "
            f"findings={len(report.findings)} "
            f"errors={error_count} "
            f"warnings={warning_count}"
        )
    ]


def _map_slide_to_state(
    slide: SlidePlan,
    slide_number: int,
    plan: PresentationPlan,
    source_document: SourceDocument,
    findings: list[BridgeFinding],
) -> dict[str, Any]:
    slide_role = _state_slide_role(slide.role)
    if slide.role == "section-divider":
        findings.append(
            BridgeFinding(
                code="bridge_layout_family_fallback",
                severity="warning",
                slide_id=slide.slide_id,
                message="Section divider intent mapped to a summary-compatible layout because the current SceneDeck adapter does not support section-divider layout family.",
            )
        )
    visual_type, visual_source_preference, production_mode, fallback = _visual_mapping(slide, source_document, findings)
    layout_pattern_id = _layout_pattern_id(slide_role, visual_type, slide, plan.design_mode, findings)
    section = _section_for_slide(plan, slide.section_id)
    deck_mode = "appendix" if slide.role in {"appendix", "references"} else "main-story"
    source_refs = _source_refs_for_slide(slide, source_document)
    evidence_summary = _evidence_summary(slide)
    notes = _speaker_notes(slide)
    return {
        "slide_number": slide_number,
        "slide_id": slide.slide_id,
        "lineage_id": slide.slide_id,
        "section": section["title"],
        "section_id": slide.section_id,
        "part_id": deck_mode,
        "cluster_id": f"cluster-{slide.section_id}",
        "deck_mode": deck_mode,
        "slide_role": slide_role,
        "title": slide.title,
        "one_line_takeaway": slide.main_message,
        "main_message": slide.main_message,
        "visual_type": visual_type,
        "layout_pattern_id": layout_pattern_id,
        "production_bridge": {
            "visual_source_preference": visual_source_preference,
            "source_material_refs": source_refs,
            "fallback_visual": fallback,
            "production_mode": production_mode,
        },
        "required_evidence_assets": evidence_summary,
        "supporting_evidence": [],
        "core_content": slide.supporting_points[:4],
        "must_keep_text": [slide.main_message],
        "optional_text": slide.uncertainty_notes,
        "presenter_notes": notes,
        "evidence_class": "source-backed" if slide.evidence_anchors else "message-only",
        "layout_slot_map": _layout_slot_map(visual_type),
        "density_budget": _density_budget(plan.design_mode),
        "verification_flags": [f"source_chunk:{anchor.source_chunk_id}" for anchor in slide.evidence_anchors],
        "authoring_payload": {
            "plan_slide_id": slide.slide_id,
            "source_chunk_ids": sorted({anchor.source_chunk_id for anchor in slide.evidence_anchors}),
            "evidence_anchors": [anchor.model_dump(mode="json", exclude_none=True) for anchor in slide.evidence_anchors],
            "visual_plan": slide.visual_plan.model_dump(mode="json", exclude_none=True),
        },
    }


def _build_blueprint(deck_title: str, plan: PresentationPlan, slide_records: list[dict[str, Any]]) -> dict[str, Any]:
    route_id = _visual_route(plan.design_mode)
    return {
        "schema_name": "blueprint",
        "schema_version": "1.0",
        "deck_title": deck_title,
        "chosen_workflow": "local-source-to-deck-poc",
        "chosen_workflow_label": "Local source-to-deck POC",
        "chosen_workflow_summary": "Deterministic bridge from validated PresentationPlan to draft compile state.",
        "workflow_delta": ["Generated from validated PresentationPlan; no external model calls."],
        "communication_core": {
            "audience_outcome": plan.narrative.audience_takeaway,
            "deck_promise": plan.narrative.thesis,
            "single_decision_or_shift": plan.objective.objective_type,
            "memory_line": plan.narrative.audience_takeaway,
            "key_question": plan.narrative.thesis,
        },
        "story_architecture": [
            {
                "section_id": section.section_id,
                "title": section.title,
                "purpose": section.objective,
                "deck_mode": "main-story",
                "slide_count_range": {"start": max(1, len(section.slide_ids)), "end": max(1, len(section.slide_ids))},
                "slide_roles": [_state_slide_role(slide.role) for slide in plan.slides if slide.section_id == section.section_id],
            }
            for section in plan.sections
        ],
        "story_structure": {
            "overall_narrative": plan.narrative.thesis,
            "message_flow": plan.narrative.story_arc,
            "audience_journey": [plan.narrative.audience_takeaway],
            "fit_rationale": "Generated from a validated local PresentationPlan.",
        },
        "deck_mode": "main-story",
        "slide_ratio": "16:9",
        "approval_status": "draft",
        "visual_routes": [
            {
                "route_id": route_id,
                "label": f"Source-grounded {plan.design_mode}",
                "description": "Deterministic local source-to-deck route with editable SceneDeck output as the downstream target.",
            }
        ],
        "recommended_route": route_id,
        "recommended_route_reason": "Mapped deterministically from source planning design mode.",
        "assumptions": list(plan.warnings),
        "risks": ["Draft state generated by deterministic bridge; review before production use."],
        "verification_points": [{"checkpoint": "Evidence anchors", "rationale": "Check source-evidence-map.json before production."}],
        "slides": slide_records,
        "appendix_start": len(slide_records) + 1,
    }


def _build_design_system(deck_title: str, plan: PresentationPlan) -> dict[str, Any]:
    mode = plan.design_mode
    palette = {
        "academic": {"accent": "#2563EB", "signal": "#1D4ED8", "background": "#F8FAFC"},
        "professional": {"accent": "#0F766E", "signal": "#C2410C", "background": "#F8FAFC"},
        "creative": {"accent": "#7C3AED", "signal": "#DB2777", "background": "#FAFAF9"},
    }[mode]
    profile = plan.design_profile
    return {
        "schema_name": "design_system",
        "schema_version": "1.0",
        "deck_title": deck_title,
        "slide_ratio": "16:9",
        "brand_name": f"Local Source {mode.title()}",
        "theme_name": f"local-source-{mode}",
        "visual_route_id": _visual_route(mode),
        "reference_source_family": f"local source-grounded {mode} family",
        "tone_keywords": profile.tone.split(", "),
        "color_tokens": [
            {"token": "background", "hex": palette["background"], "usage": "Slide background"},
            {"token": "surface", "hex": "#FFFFFF", "usage": "Content surfaces"},
            {"token": "panel", "hex": "#EEF2FF", "usage": "Subtle panels"},
            {"token": "border", "hex": "#CBD5E1", "usage": "Dividers and table borders"},
            {"token": "text", "hex": "#111827", "usage": "Primary text"},
            {"token": "text-muted", "hex": "#475569", "usage": "Captions and source notes"},
            {"token": "accent", "hex": palette["accent"], "usage": "Design accent"},
            {"token": "signal", "hex": palette["signal"], "usage": "Emphasis"},
        ],
        "typography_tokens": [
            {"token": "title", "font_family": "Aptos Display", "size_pt": 24.0, "weight": "bold", "usage": "Slide titles"},
            {"token": "heading", "font_family": "Aptos Display", "size_pt": 18.0, "weight": "bold", "usage": "Section and body headings"},
            {"token": "body", "font_family": "Aptos", "size_pt": 11.0, "weight": "regular", "usage": "Body text"},
            {"token": "caption", "font_family": "Aptos", "size_pt": 9.0, "weight": "regular", "usage": "Source notes"},
        ],
        "spacing_scale": [4, 8, 16, 24, 32],
        "layout_principles": [
            profile.typography_intent,
            profile.color_style_intent,
            profile.chart_table_preference,
            "Preserve source evidence anchors in notes and state artifacts.",
        ],
        "layout_rules": [
            "Use one source-backed message per slide.",
            "Keep section hierarchy aligned with the PresentationPlan.",
        ],
        "visual_system_rules": [
            profile.color_style_intent,
            "Use editable text, shapes, tables, and charts only when source evidence supports them.",
        ],
        "chart_rules": [profile.chart_table_preference, "Do not fabricate chart values from prose-only evidence."],
        "table_rules": [profile.chart_table_preference, "Do not fabricate table rows from prose-only evidence."],
        "screenshot_rules": ["Screenshots are not part of the local source-to-state bridge."],
        "highlight_rules": ["Use accent and signal tokens for source-grounded emphasis."],
        "callout_method": "Source-backed summary callouts only",
        "title_rules": ["Use claim-led titles derived from source-backed slide messages."],
        "section_divider_style": profile.section_divider_behavior,
        "visual_families": list(profile.allowed_layout_families),
        "icon_style": "Minimal editable geometry only",
    }


def _build_deck_constitution(deck_title: str, plan: PresentationPlan) -> dict[str, Any]:
    profile = plan.design_profile
    return {
        "schema_name": "deck_constitution",
        "schema_version": "1.0",
        "deck_title": deck_title,
        "deck_mode": "main-story",
        "locked_workflow": "local-source-to-deck-poc",
        "deck_objective": plan.narrative.thesis,
        "audience_definition": [plan.audience.label, plan.audience.expertise_level],
        "delivery_mode": "live-presentation",
        "message_spine": [slide.main_message for slide in plan.slides],
        "narrative_promise": plan.narrative.audience_takeaway,
        "section_logic": [f"{section.title}: {section.objective}" for section in plan.sections],
        "story_rules": ["One slide carries one source-backed message.", "Content slides must preserve evidence anchors."],
        "title_rules": ["Use claim-led titles derived from the validated PresentationPlan."],
        "tone_voice": profile.tone.split(", "),
        "approved_visual_route": _visual_route(plan.design_mode),
        "design_token_refs": ["background", "surface", "panel", "border", "text", "text-muted", "accent", "signal", "title", "heading", "body", "caption"],
        "layout_pattern_ids": sorted(SUPPORTED_LAYOUT_PATTERN_IDS),
        "references_policy": profile.citation_footer_behavior,
        "source_handling_rules": [
            "Do not fabricate source evidence, chart values, table rows, or figure assets.",
            "Use source-evidence-map.json as the evidence handoff surface.",
        ],
        "recurring_motifs": [profile.image_motif_preference],
        "visual_consistency_rules": [profile.color_style_intent, profile.typography_intent],
    }


def _build_layout_library(deck_title: str) -> dict[str, Any]:
    return {
        "schema_name": "layout_library",
        "schema_version": "1.0",
        "deck_title": deck_title,
        "slide_ratio": "16:9",
        "patterns": [
            {
                "pattern_id": "cover-signal",
                "name": "Cover signal",
                "slide_roles": ["title"],
                "supported_visual_types": ["text", "quote"],
                "export_safe": True,
            },
            {
                "pattern_id": "agenda-roadmap",
                "name": "Agenda roadmap",
                "slide_roles": ["executive-summary", "process"],
                "supported_visual_types": ["text", "process", "timeline"],
                "export_safe": True,
            },
            {
                "pattern_id": "headline-evidence",
                "name": "Headline with source-backed body",
                "slide_roles": ["title", "executive-summary", "recommendation", "analysis", "evidence", "references"],
                "supported_visual_types": ["text", "quote", "comparison"],
                "export_safe": True,
            },
            {
                "pattern_id": "comparison",
                "name": "Comparison",
                "slide_roles": ["analysis", "comparison", "recommendation"],
                "supported_visual_types": ["comparison", "text"],
                "export_safe": True,
            },
            {
                "pattern_id": "process-flow",
                "name": "Process flow",
                "slide_roles": ["process", "recommendation", "executive-summary"],
                "supported_visual_types": ["process", "timeline", "text"],
                "export_safe": True,
            },
            {
                "pattern_id": "appendix-reference",
                "name": "Appendix reference",
                "slide_roles": ["appendix-evidence", "references"],
                "supported_visual_types": ["text", "table", "document-crop"],
                "export_safe": True,
            },
        ],
    }


def _build_slide_ledger(deck_title: str, slide_records: list[dict[str, Any]]) -> dict[str, Any]:
    entries = []
    for slide in slide_records:
        entries.append(
            {
                key: slide[key]
                for key in (
                    "slide_number",
                    "slide_id",
                    "lineage_id",
                    "slide_role",
                    "title",
                    "one_line_takeaway",
                    "main_message",
                    "section",
                    "part_id",
                    "section_id",
                    "cluster_id",
                    "deck_mode",
                    "visual_type",
                    "layout_pattern_id",
                    "required_evidence_assets",
                )
            }
            | {
                "title_status": "draft",
                "visual_source_preference": slide["production_bridge"]["visual_source_preference"],
                "production_mode": slide["production_bridge"]["production_mode"],
                "asset_request_ids": [],
                "asset_dependency_kinds": [],
                "batch_id": f"batch-{slide['section_id']}",
                "blueprint_status": "draft",
                "asset_status": "not-required",
                "visual_status": "draft",
                "compile_status": "draft",
                "qa_status": "pending",
                "remediation_finding_ids": [],
                "remediation_batch_ids": [],
                "depends_on": [],
                "change_note": "Generated by PresentationPlan bridge.",
            }
        )
    return {"schema_name": "slide_ledger", "schema_version": "1.0", "deck_title": deck_title, "entries": entries, "continuity_notes": ["Generated from validated PresentationPlan."]}


def _build_asset_manifest(deck_title: str, findings: list[BridgeFinding]) -> dict[str, Any]:
    findings.append(BridgeFinding(code="bridge_placeholder_asset_manifest", severity="info", message="asset-manifest.json emitted empty; source POC does not create assets."))
    return {"schema_name": "asset_manifest", "schema_version": "1.0", "deck_title": deck_title, "assets": []}


def _build_viz_manifest(deck_title: str, findings: list[BridgeFinding]) -> dict[str, Any]:
    findings.append(BridgeFinding(code="bridge_placeholder_viz_manifest", severity="info", message="viz-manifest.json emitted empty; bridge does not fabricate chart/table data."))
    return {"schema_name": "viz_manifest", "schema_version": "1.0", "deck_title": deck_title, "visuals": []}


def _build_evidence_map(source_document: SourceDocument, plan: PresentationPlan, slide_records: list[dict[str, Any]]) -> SourceEvidenceMap:
    chunk_by_id = {chunk.chunk_id: chunk for chunk in source_document.chunks}
    entries: list[SourceEvidenceMapEntry] = []
    for slide, record in zip(plan.slides, slide_records):
        chunk_ids = sorted({anchor.source_chunk_id for anchor in slide.evidence_anchors})
        entries.append(
            SourceEvidenceMapEntry(
                plan_slide_id=slide.slide_id,
                state_slide_id=record["slide_id"],
                slide_number=record["slide_number"],
                title=slide.title,
                source_chunk_ids=chunk_ids,
                anchors=[
                    {
                        "source_chunk_id": anchor.source_chunk_id,
                        "line_range": list(anchor.line_range) if anchor.line_range else None,
                        "anchor_text": anchor.anchor_text,
                        "confidence": anchor.confidence,
                    }
                    for anchor in slide.evidence_anchors
                ],
                evidence_snippets=[chunk_by_id[chunk_id].text[:280] for chunk_id in chunk_ids if chunk_id in chunk_by_id],
            )
        )
    evidence_map = SourceEvidenceMap(
        source_document_id=source_document.document_id,
        presentation_plan_id=plan.plan_id,
        slide_count=len(entries),
        entries=entries,
        structural_hash="",
    )
    return evidence_map.model_copy(update={"structural_hash": source_evidence_map_structural_hash(evidence_map)})


def _visual_mapping(
    slide: SlidePlan,
    source_document: SourceDocument,
    findings: list[BridgeFinding],
) -> tuple[str, str, str, str]:
    category = slide.visual_plan.visual_category
    if category == "chart":
        findings.append(BridgeFinding(code="bridge_missing_table_source", severity="warning", slide_id=slide.slide_id, message="Chart intent had no structured numeric data; text fallback used."))
        return "text", "structured-visual", "structured-visual", "table"
    if category == "table":
        findings.append(BridgeFinding(code="bridge_missing_table_source", severity="warning", slide_id=slide.slide_id, message="Table intent had no structured rows/columns; text fallback used."))
        return "text", "structured-visual", "structured-visual", "table"
    if category == "image":
        findings.append(BridgeFinding(code="bridge_missing_figure_source", severity="warning", slide_id=slide.slide_id, message="Figure/image intent has no local image asset; text fallback used."))
        return "text", "structured-visual", "structured-visual", "text"
    if category in {"process", "timeline"}:
        return category, "structured-visual", "structured-visual", "text"
    if category == "framework":
        findings.append(BridgeFinding(code="bridge_unsupported_visual_plan", severity="warning", slide_id=slide.slide_id, message="Framework intent has no structured node spec; text fallback used."))
        return "text", "structured-visual", "structured-visual", "text"
    if category == "comparison":
        findings.append(BridgeFinding(code="bridge_unsupported_visual_plan", severity="warning", slide_id=slide.slide_id, message="Comparison intent has no structured comparison spec; text fallback used."))
        return "text", "structured-visual", "structured-visual", "text"
    if category in {"quote", "section-divider", "text"}:
        return "text", "structured-visual", "structured-visual", "text"
    findings.append(BridgeFinding(code="bridge_unsupported_visual_plan", severity="warning", slide_id=slide.slide_id, message=f"Unsupported visual category {category!r}; text fallback used."))
    return "text", "structured-visual", "structured-visual", "text"


def _layout_pattern_id(slide_role: str, visual_type: str, slide: SlidePlan, design_mode: str, findings: list[BridgeFinding]) -> str:
    if slide_role == "title":
        return "cover-signal"
    if slide_role == "executive-summary":
        return "agenda-roadmap" if slide.role == "agenda" else "headline-evidence"
    if slide_role == "appendix-evidence":
        return "appendix-reference"
    if visual_type == "framework":
        return "framework-grid"
    if visual_type in {"process", "timeline"}:
        return "process-flow"
    if slide_role == "recommendation":
        return "headline-evidence"
    if slide_role in {"analysis", "evidence"}:
        return "headline-evidence"
    findings.append(BridgeFinding(code="bridge_layout_family_fallback", severity="warning", slide_id=slide.slide_id, message=f"Role {slide_role!r} used title-thesis-body fallback."))
    return "title-thesis-body"


def _state_slide_role(role: str) -> str:
    return {
        "title": "title",
        "agenda": "executive-summary",
        "section-divider": "executive-summary",
        "summary": "executive-summary",
        "evidence": "evidence",
        "analysis": "analysis",
        "recommendation": "recommendation",
        "appendix": "appendix-evidence",
        "references": "references",
    }.get(role, "analysis")


def _section_for_slide(plan: PresentationPlan, section_id: str) -> dict[str, str]:
    for section in plan.sections:
        if section.section_id == section_id:
            return {"section_id": section.section_id, "title": section.title}
    return {"section_id": section_id, "title": section_id}


def _source_refs_for_slide(slide: SlidePlan, source_document: SourceDocument) -> list[dict[str, Any]]:
    if not slide.evidence_anchors:
        return []
    first = slide.evidence_anchors[0]
    return [
        {
            "source_id": source_document.document_id,
            "label": source_document.title,
            "path": source_document.source_path,
            "page": None,
            "chunk_id": first.source_chunk_id,
        }
    ]


def _evidence_summary(slide: SlidePlan) -> list[str]:
    if slide.evidence_anchors:
        return [f"{anchor.source_chunk_id}: {anchor.anchor_text[:120]}" for anchor in slide.evidence_anchors[:3]]
    return []


def _speaker_notes(slide: SlidePlan) -> str:
    notes = [slide.speaker_intent.primary_intent, *slide.speaker_intent.speaker_notes_seed]
    for anchor in slide.evidence_anchors:
        notes.append(f"Evidence: {anchor.source_chunk_id} lines {anchor.line_range}: {anchor.anchor_text}")
    return "\n".join(item for item in notes if item)


def _layout_slot_map(visual_type: str) -> dict[str, str]:
    mapping = {"title": "title", "claim": "claim"}
    if visual_type not in {"text", "quote"}:
        mapping["primary_visual"] = "primary_visual"
    return mapping


def _density_budget(design_mode: str) -> dict[str, int]:
    if design_mode == "academic":
        return {"text_char_ceiling": 900, "bullet_count_ceiling": 5, "evidence_item_ceiling": 4}
    if design_mode == "creative":
        return {"text_char_ceiling": 520, "bullet_count_ceiling": 3, "evidence_item_ceiling": 2}
    return {"text_char_ceiling": 700, "bullet_count_ceiling": 4, "evidence_item_ceiling": 3}


def _visual_route(design_mode: str) -> str:
    return {
        "academic": "source-grounded-academic",
        "professional": "source-grounded-professional",
        "creative": "source-grounded-creative",
    }.get(design_mode, "source-grounded-professional")


def _validate_generated_state_artifacts(output_dir: Path, artifacts: dict[str, Path], findings: list[BridgeFinding]) -> None:
    for key in ("blueprint", "design_system", "deck_constitution", "layout_library", "slide_ledger", "asset_manifest", "viz_manifest"):
        path = artifacts[key]
        if not path.is_file():
            findings.append(BridgeFinding(code="bridge_artifact_missing", severity="error", message=f"generated artifact missing: {key}"))
            continue
        load_state_file(path)


def _model_payload_with_hash(model: BaseModel) -> dict[str, Any]:
    return _normalize(model.model_dump(mode="json", exclude_none=True))


def _write_json(output_path: str | Path, payload: dict[str, Any]) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(_normalize(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n", encoding="utf-8")
    return output


def _normalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _normalize(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    if isinstance(value, tuple):
        return [_normalize(item) for item in value]
    if isinstance(value, float):
        normalized = round(value, 6)
        if normalized == 0:
            return 0
        if float(normalized).is_integer():
            return int(normalized)
        return normalized
    return value
