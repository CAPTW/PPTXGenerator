"""Validation for local source-to-deck PresentationPlan artifacts."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Iterable

from ..source_planning import (
    PresentationPlan,
    PresentationPlanValidationFinding,
    PresentationPlanValidationReport,
    SourceDocument,
    VisualCategory,
    load_presentation_plan,
    load_source_document,
    source_planning_model_to_stable_json,
    with_structural_hash,
    write_source_planning_json,
)


CONTENT_SLIDE_ROLES = {"evidence", "analysis", "recommendation", "appendix"}
EVIDENCE_EXEMPT_ROLES = {"title", "agenda", "section-divider", "references"}
SUPPORTED_VISUAL_CATEGORIES: set[str] = {
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
}


def validate_presentation_plan(plan: PresentationPlan, source_document: SourceDocument) -> PresentationPlanValidationReport:
    findings: list[PresentationPlanValidationFinding] = []
    chunk_ids = {chunk.chunk_id for chunk in source_document.chunks}
    section_ids = [section.section_id for section in plan.sections]
    slide_ids = [slide.slide_id for slide in plan.slides]

    findings.extend(_duplicate_findings(section_ids, code="duplicate_section_id", field="section_id"))
    findings.extend(_duplicate_findings(slide_ids, code="duplicate_slide_id", field="slide_id"))

    if plan.design_mode not in {"academic", "professional", "creative"}:
        findings.append(_finding("unsupported_design_mode", "error", f"unsupported design mode: {plan.design_mode}"))

    section_id_set = set(section_ids)
    for section in plan.sections:
        if not section.slide_ids:
            findings.append(
                _finding(
                    "section_without_slides",
                    "warning",
                    f"section has no planned slides: {section.section_id}",
                    section_id=section.section_id,
                )
            )
        for chunk_id in section.source_chunk_ids:
            if chunk_id not in chunk_ids:
                findings.append(
                    _finding(
                        "source_chunk_missing",
                        "error",
                        f"section references missing source chunk: {chunk_id}",
                        section_id=section.section_id,
                        source_chunk_id=chunk_id,
                    )
                )

    for slide in plan.slides:
        if slide.section_id not in section_id_set:
            findings.append(
                _finding(
                    "section_without_slides",
                    "error",
                    f"slide references missing section: {slide.section_id}",
                    slide_id=slide.slide_id,
                    section_id=slide.section_id,
                )
            )
        if not slide.role:
            findings.append(_finding("slide_missing_role", "error", "slide role is required", slide_id=slide.slide_id))
        if slide.role in CONTENT_SLIDE_ROLES and not slide.evidence_anchors:
            findings.append(
                _finding(
                    "slide_missing_evidence",
                    "error",
                    "content slide requires at least one evidence anchor",
                    slide_id=slide.slide_id,
                )
            )
        if slide.role not in EVIDENCE_EXEMPT_ROLES:
            for claim in slide.claims:
                if not claim.source_chunk_ids:
                    findings.append(
                        _finding(
                            "claim_without_source",
                            "error",
                            f"claim has no source chunk ids: {claim.claim_id}",
                            slide_id=slide.slide_id,
                        )
                    )
                for chunk_id in claim.source_chunk_ids:
                    if chunk_id not in chunk_ids:
                        findings.append(
                            _finding(
                                "source_chunk_missing",
                                "error",
                                f"claim references missing source chunk: {chunk_id}",
                                slide_id=slide.slide_id,
                                source_chunk_id=chunk_id,
                            )
                        )
        for anchor in slide.evidence_anchors:
            if anchor.source_chunk_id not in chunk_ids:
                findings.append(
                    _finding(
                        "source_chunk_missing",
                        "error",
                        f"evidence anchor references missing source chunk: {anchor.source_chunk_id}",
                        slide_id=slide.slide_id,
                        source_chunk_id=anchor.source_chunk_id,
                    )
                )
            if not anchor.anchor_text.strip():
                findings.append(
                    _finding(
                        "evidence_anchor_missing_text",
                        "error",
                        "evidence anchor text is required",
                        slide_id=slide.slide_id,
                        source_chunk_id=anchor.source_chunk_id,
                    )
                )
        if slide.visual_plan.visual_category not in SUPPORTED_VISUAL_CATEGORIES:
            findings.append(
                _finding(
                    "unsupported_visual_plan",
                    "error",
                    f"unsupported visual category: {slide.visual_plan.visual_category}",
                    slide_id=slide.slide_id,
                )
            )
        if _slide_content_size(slide) > 900:
            findings.append(
                _finding(
                    "slide_content_too_dense",
                    "warning",
                    "slide has too much planned text for a single slide",
                    slide_id=slide.slide_id,
                )
            )

    if len(plan.slides) < max(1, plan.target_slide_count - 2) or len(plan.slides) > plan.target_slide_count + 2:
        findings.append(
            _finding(
                "target_slide_count_mismatch",
                "warning",
                f"planned slide count {len(plan.slides)} is outside tolerance for target {plan.target_slide_count}",
            )
        )
    if source_document.outline.structure_quality in {"none", "weak"}:
        findings.append(
            _finding(
                "insufficient_source_structure",
                "warning",
                f"source outline quality is {source_document.outline.structure_quality}",
            )
        )
    findings = sorted(findings, key=lambda item: (item.severity, item.code, item.section_id or "", item.slide_id or "", item.source_chunk_id or "", item.message))
    error_count = sum(1 for finding in findings if finding.severity == "error")
    warning_count = sum(1 for finding in findings if finding.severity == "warning")
    status = "failed" if error_count else "warnings" if warning_count else "passed"
    report = PresentationPlanValidationReport(
        plan_id=plan.plan_id,
        source_document_id=source_document.document_id,
        status=status,
        finding_count=len(findings),
        error_count=error_count,
        warning_count=warning_count,
        findings=findings,
    )
    return with_structural_hash(report)  # type: ignore[return-value]


def validate_presentation_plan_files(
    *,
    plan_path: str | Path,
    source_document_path: str | Path,
) -> PresentationPlanValidationReport:
    return validate_presentation_plan(load_presentation_plan(plan_path), load_source_document(source_document_path))


def write_presentation_plan_validation_report(
    report: PresentationPlanValidationReport,
    output_path: str | Path,
) -> Path:
    return write_source_planning_json(report, output_path)


def presentation_plan_validation_report_to_stable_json(report: PresentationPlanValidationReport) -> str:
    return source_planning_model_to_stable_json(report)


def summarize_presentation_plan_validation(report: PresentationPlanValidationReport) -> list[str]:
    return [
        (
            "PRESENTATION_PLAN_VALIDATION "
            f"status={report.status} "
            f"findings={report.finding_count} "
            f"errors={report.error_count} "
            f"warnings={report.warning_count}"
        )
    ]


def _duplicate_findings(values: Iterable[str], *, code: str, field: str) -> list[PresentationPlanValidationFinding]:
    counts = Counter(values)
    findings: list[PresentationPlanValidationFinding] = []
    for value in sorted(item for item, count in counts.items() if count > 1):
        kwargs = {"section_id": value} if field == "section_id" else {"slide_id": value}
        findings.append(
            _finding(
                code,
                "error",
                f"duplicate {field}: {value}",
                **kwargs,
            )
        )
    return findings


def _slide_content_size(slide) -> int:
    return len(slide.title) + len(slide.main_message) + sum(len(point) for point in slide.supporting_points)


def _finding(
    code: str,
    severity: str,
    message: str,
    *,
    slide_id: str | None = None,
    section_id: str | None = None,
    source_chunk_id: str | None = None,
) -> PresentationPlanValidationFinding:
    return PresentationPlanValidationFinding(
        code=code,
        severity=severity,  # type: ignore[arg-type]
        message=message,
        slide_id=slide_id,
        section_id=section_id,
        source_chunk_id=source_chunk_id,
    )
