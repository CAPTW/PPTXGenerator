"""Deterministic repair loop for local PresentationPlan artifacts."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .pipeline.presentation_plan_validation import validate_presentation_plan, write_presentation_plan_validation_report
from .source_deck_planner import design_profile_for_mode
from .source_planning import (
    DeckSectionPlan,
    PresentationPlan,
    PresentationPlanValidationFinding,
    PresentationPlanValidationReport,
    SlideEvidenceAnchor,
    SlidePlan,
    SourceDocument,
    load_source_document,
    source_planning_model_to_stable_json,
    with_structural_hash,
    write_source_planning_json,
)


REPAIR_REPORT_VERSION = "0.1"
VALID_DESIGN_MODES = {"academic", "professional", "creative"}
VALID_SLIDE_ROLES = {"title", "agenda", "section-divider", "summary", "evidence", "analysis", "recommendation", "appendix", "references"}
VALID_VISUAL_CATEGORIES = {"text", "table", "chart", "process", "comparison", "quote", "image", "framework", "timeline", "section-divider"}
CONTENT_ROLES = {"evidence", "analysis", "recommendation", "appendix"}
STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "by",
    "for",
    "from",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
}


class PresentationPlanRepairModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class PresentationPlanRepairPolicy(PresentationPlanRepairModel):
    allow_id_repair: bool = True
    allow_design_mode_fallback: bool = True
    allow_role_inference: bool = True
    allow_visual_plan_downgrade: bool = True
    allow_evidence_anchor_repair: bool = True
    allow_slide_splitting: bool = True
    allow_section_rebalancing: bool = True
    allow_target_slide_count_adjustment: bool = False
    max_added_evidence_anchors: int = 12
    max_split_slides: int = 2
    max_generated_slide_count: int = 80
    require_source_backing_for_claims: bool = True
    preserve_original_slide_order: bool = True


class PresentationPlanRepairAction(PresentationPlanRepairModel):
    code: str
    message: str
    slide_id: str | None = None
    section_id: str | None = None
    original_value: str | None = None
    repaired_value: str | None = None
    detail: dict[str, Any] = Field(default_factory=dict)


class PresentationPlanRepairFinding(PresentationPlanRepairModel):
    code: str
    severity: Literal["info", "warning", "error"] = "warning"
    message: str
    slide_id: str | None = None
    section_id: str | None = None
    source_chunk_id: str | None = None
    detail: dict[str, Any] = Field(default_factory=dict)


class PresentationPlanRepairSummary(PresentationPlanRepairModel):
    original_validation_status: str
    repaired_validation_status: str
    original_finding_count: int
    repaired_finding_count: int
    repair_action_count: int
    unresolved_finding_count: int
    repaired_slide_count: int
    repaired_section_count: int


class PresentationPlanRepairReport(PresentationPlanRepairModel):
    report_version: str = REPAIR_REPORT_VERSION
    source_document_path: str | None = None
    original_plan_path: str | None = None
    repaired_plan_path: str | None = None
    original_validation_status: str
    repaired_validation_status: str
    original_finding_count: int
    repaired_finding_count: int
    repair_action_count: int
    unresolved_finding_count: int
    repaired_slide_count: int
    repaired_section_count: int
    actions: list[PresentationPlanRepairAction] = Field(default_factory=list)
    unresolved_findings: list[PresentationPlanRepairFinding] = Field(default_factory=list)
    policy: PresentationPlanRepairPolicy = Field(default_factory=PresentationPlanRepairPolicy)
    structural_hash: str = ""


class PresentationPlanRepairResult(PresentationPlanRepairModel):
    repaired_plan: PresentationPlan | None = None
    original_validation_report: PresentationPlanValidationReport
    repaired_validation_report: PresentationPlanValidationReport
    repair_report: PresentationPlanRepairReport


class PartialDeckSectionPlan(PresentationPlanRepairModel):
    section: DeckSectionPlan
    slides: list[SlidePlan] = Field(default_factory=list)


def repair_presentation_plan_from_files(
    *,
    source_document_path: str | Path,
    presentation_plan_path: str | Path,
    policy: PresentationPlanRepairPolicy | None = None,
) -> PresentationPlanRepairResult:
    source_document = load_source_document(source_document_path)
    raw_plan = json.loads(Path(presentation_plan_path).read_text(encoding="utf-8"))
    return repair_presentation_plan(
        source_document=source_document,
        raw_plan=raw_plan,
        source_document_path=str(Path(source_document_path).resolve()),
        original_plan_path=str(Path(presentation_plan_path).resolve()),
        policy=policy,
    )


def repair_presentation_plan(
    *,
    source_document: SourceDocument,
    raw_plan: dict[str, Any] | PresentationPlan,
    source_document_path: str | None = None,
    original_plan_path: str | None = None,
    policy: PresentationPlanRepairPolicy | None = None,
) -> PresentationPlanRepairResult:
    repair_policy = policy or PresentationPlanRepairPolicy()
    raw_payload = raw_plan.model_dump(mode="json", exclude_none=True) if isinstance(raw_plan, PresentationPlan) else _normalize(raw_plan)
    original_plan, original_validation = _parse_and_validate(raw_payload, source_document)
    actions: list[PresentationPlanRepairAction] = []
    repair_findings: list[PresentationPlanRepairFinding] = []

    repaired_payload = _normalize(raw_payload)
    _repair_design_mode(repaired_payload, repair_policy, actions, repair_findings)
    _repair_duplicate_section_ids(repaired_payload, repair_policy, actions, repair_findings)
    _repair_duplicate_slide_ids(repaired_payload, repair_policy, actions, repair_findings)
    _repair_slide_roles(repaired_payload, repair_policy, actions, repair_findings)
    _repair_visual_plans(repaired_payload, repair_policy, actions, repair_findings)
    _repair_orphan_slide_sections(repaired_payload, repair_policy, actions, repair_findings)
    _rebuild_section_slide_ids(repaired_payload)

    repaired_plan, repaired_validation = _parse_and_validate(repaired_payload, source_document)
    if repaired_plan is not None:
        repaired_plan, more_actions, more_findings = _repair_typed_plan(repaired_plan, source_document, repair_policy)
        actions.extend(more_actions)
        repair_findings.extend(more_findings)
        repaired_validation = validate_presentation_plan(repaired_plan, source_document)

    unresolved = _unresolved_findings(repaired_validation, repair_findings)
    report = build_repair_report(
        source_document_path=source_document_path,
        original_plan_path=original_plan_path,
        repaired_plan_path=None,
        original_validation_report=original_validation,
        repaired_validation_report=repaired_validation,
        repaired_plan=repaired_plan,
        actions=actions,
        unresolved_findings=unresolved,
        policy=repair_policy,
    )
    return PresentationPlanRepairResult(
        repaired_plan=repaired_plan,
        original_validation_report=original_validation,
        repaired_validation_report=repaired_validation,
        repair_report=report,
    )


def repair_deck_section_plan(
    *,
    source_document: SourceDocument,
    base_plan: PresentationPlan,
    section_payload: dict[str, Any] | PartialDeckSectionPlan,
    policy: PresentationPlanRepairPolicy | None = None,
) -> PresentationPlanRepairResult:
    partial = section_payload if isinstance(section_payload, PartialDeckSectionPlan) else PartialDeckSectionPlan.model_validate(section_payload)
    raw_plan = base_plan.model_dump(mode="json", exclude_none=True)
    raw_plan["sections"] = [partial.section.model_dump(mode="json", exclude_none=True)]
    raw_plan["slides"] = [slide.model_dump(mode="json", exclude_none=True) for slide in partial.slides]
    return repair_presentation_plan(source_document=source_document, raw_plan=raw_plan, policy=policy)


def merge_repaired_section_into_plan(
    *,
    base_plan: PresentationPlan,
    repaired_section_result: PresentationPlanRepairResult,
) -> PresentationPlan:
    if repaired_section_result.repaired_plan is None:
        raise ValueError("cannot merge section repair without a repaired PresentationPlan")
    repaired = repaired_section_result.repaired_plan
    section_ids = {section.section_id for section in repaired.sections}
    sections = [section for section in base_plan.sections if section.section_id not in section_ids] + list(repaired.sections)
    slides = [slide for slide in base_plan.slides if slide.section_id not in section_ids] + list(repaired.slides)
    sections = sorted(sections, key=lambda section: section.order_index)
    slides = sorted(slides, key=lambda slide: slide.order_index)
    return with_structural_hash(base_plan.model_copy(update={"sections": sections, "slides": slides}))  # type: ignore[return-value]


def build_repair_report(
    *,
    source_document_path: str | None,
    original_plan_path: str | None,
    repaired_plan_path: str | None,
    original_validation_report: PresentationPlanValidationReport,
    repaired_validation_report: PresentationPlanValidationReport,
    repaired_plan: PresentationPlan | None,
    actions: list[PresentationPlanRepairAction],
    unresolved_findings: list[PresentationPlanRepairFinding],
    policy: PresentationPlanRepairPolicy,
) -> PresentationPlanRepairReport:
    report = PresentationPlanRepairReport(
        source_document_path=source_document_path,
        original_plan_path=original_plan_path,
        repaired_plan_path=repaired_plan_path,
        original_validation_status=original_validation_report.status,
        repaired_validation_status=repaired_validation_report.status,
        original_finding_count=original_validation_report.finding_count,
        repaired_finding_count=repaired_validation_report.finding_count,
        repair_action_count=len(actions),
        unresolved_finding_count=len(unresolved_findings),
        repaired_slide_count=len(repaired_plan.slides) if repaired_plan is not None else 0,
        repaired_section_count=len(repaired_plan.sections) if repaired_plan is not None else 0,
        actions=sorted(actions, key=lambda item: (item.slide_id or "", item.section_id or "", item.code, item.message)),
        unresolved_findings=sorted(unresolved_findings, key=lambda item: (item.slide_id or "", item.section_id or "", item.code, item.message)),
        policy=policy,
        structural_hash="",
    )
    return report.model_copy(update={"structural_hash": repair_report_structural_hash(report)})


def write_repaired_plan_artifacts(
    result: PresentationPlanRepairResult,
    *,
    original_plan_payload: dict[str, Any],
    output_dir: str | Path,
    write_markdown: bool = False,
) -> dict[str, Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    paths["original_plan"] = _write_json(output / "original-presentation-plan.json", original_plan_payload)
    paths["original_validation_report"] = write_presentation_plan_validation_report(
        result.original_validation_report,
        output / "original-validation-report.json",
    )
    if result.repaired_plan is not None:
        paths["repaired_plan"] = write_source_planning_json(result.repaired_plan, output / "repaired-presentation-plan.json")
    else:
        paths["repaired_plan"] = _write_json(output / "repaired-presentation-plan.json", original_plan_payload)
    paths["repaired_validation_report"] = write_presentation_plan_validation_report(
        result.repaired_validation_report,
        output / "repaired-validation-report.json",
    )
    report = result.repair_report.model_copy(update={"repaired_plan_path": str(paths["repaired_plan"].resolve())})
    report = report.model_copy(update={"structural_hash": repair_report_structural_hash(report)})
    paths["repair_report"] = write_repair_report(report, output / "presentation-plan-repair-report.json")
    if write_markdown:
        paths["repair_summary_markdown"] = write_repair_summary_markdown(report, output / "presentation-plan-repair-summary.md")
    return paths


def write_repair_report(report: PresentationPlanRepairReport, output_path: str | Path) -> Path:
    return _write_json(output_path, repair_report_to_stable_payload(report))


def write_repair_summary_markdown(report: PresentationPlanRepairReport, output_path: str | Path) -> Path:
    output = Path(output_path)
    lines = [
        "# Presentation Plan Repair Summary",
        "",
        f"- Original validation: `{report.original_validation_status}` ({report.original_finding_count} findings)",
        f"- Repaired validation: `{report.repaired_validation_status}` ({report.repaired_finding_count} findings)",
        f"- Repair actions: `{report.repair_action_count}`",
        f"- Unresolved findings: `{report.unresolved_finding_count}`",
        "",
        "## Actions",
    ]
    if report.actions:
        lines.extend(f"- `{action.code}`: {action.message}" for action in report.actions)
    else:
        lines.append("- None")
    lines.extend(["", "## Unresolved Findings"])
    if report.unresolved_findings:
        lines.extend(f"- `{finding.code}`: {finding.message}" for finding in report.unresolved_findings)
    else:
        lines.append("- None")
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output


def repair_report_to_stable_payload(report: PresentationPlanRepairReport, *, include_paths: bool = True) -> dict[str, Any]:
    payload = report.model_dump(mode="json", exclude_none=True)
    if not include_paths:
        for key in ("source_document_path", "original_plan_path", "repaired_plan_path"):
            payload.pop(key, None)
    return _normalize(payload)


def repair_report_to_stable_json(report: PresentationPlanRepairReport) -> str:
    return json.dumps(repair_report_to_stable_payload(report), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def repair_report_structural_hash(report: PresentationPlanRepairReport) -> str:
    payload = repair_report_to_stable_payload(report, include_paths=False)
    payload.pop("structural_hash", None)
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")).hexdigest()


def summarize_repair_report(report: PresentationPlanRepairReport) -> list[str]:
    return [
        (
            "PRESENTATION_PLAN_REPAIR "
            f"original_status={report.original_validation_status} "
            f"repaired_status={report.repaired_validation_status} "
            f"actions={report.repair_action_count} "
            f"unresolved={report.unresolved_finding_count} "
            f"slides={report.repaired_slide_count}"
        )
    ]


def _repair_design_mode(
    payload: dict[str, Any],
    policy: PresentationPlanRepairPolicy,
    actions: list[PresentationPlanRepairAction],
    findings: list[PresentationPlanRepairFinding],
) -> None:
    mode = payload.get("design_mode")
    if mode in VALID_DESIGN_MODES:
        profile = payload.get("design_profile")
        if isinstance(profile, dict) and profile.get("mode") != mode:
            payload["design_profile"] = design_profile_for_mode(mode).model_dump(mode="json", exclude_none=True)
        return
    if not policy.allow_design_mode_fallback:
        findings.append(PresentationPlanRepairFinding(code="repair_policy_blocked_action", severity="error", message="design mode fallback blocked by policy."))
        return
    original = str(mode) if mode is not None else None
    payload["design_mode"] = "professional"
    payload["design_profile"] = design_profile_for_mode("professional").model_dump(mode="json", exclude_none=True)
    actions.append(PresentationPlanRepairAction(code="design_mode_fallback_applied", message="Unsupported design mode mapped to professional.", original_value=original, repaired_value="professional"))


def _repair_duplicate_section_ids(
    payload: dict[str, Any],
    policy: PresentationPlanRepairPolicy,
    actions: list[PresentationPlanRepairAction],
    findings: list[PresentationPlanRepairFinding],
) -> None:
    sections = payload.get("sections")
    if not isinstance(sections, list):
        return
    seen: Counter[str] = Counter()
    for section in sections:
        if not isinstance(section, dict):
            continue
        section_id = str(section.get("section_id") or "section")
        seen[section_id] += 1
        if seen[section_id] == 1:
            section["section_id"] = section_id
            continue
        if not policy.allow_id_repair:
            findings.append(PresentationPlanRepairFinding(code="repair_policy_blocked_action", severity="error", section_id=section_id, message="duplicate section id repair blocked by policy."))
            continue
        repaired = f"{section_id}-{seen[section_id]:02d}"
        original_slide_ids = {str(slide_id) for slide_id in section.get("slide_ids", [])}
        section["section_id"] = repaired
        slides = payload.get("slides")
        if isinstance(slides, list) and original_slide_ids:
            for slide in slides:
                if isinstance(slide, dict) and str(slide.get("slide_id")) in original_slide_ids:
                    original_section_id = str(slide.get("section_id"))
                    slide["section_id"] = repaired
                    actions.append(
                        PresentationPlanRepairAction(
                            code="section_orphan_reassigned",
                            slide_id=str(slide.get("slide_id")),
                            section_id=repaired,
                            message="Slide section reference updated to match repaired duplicate section id.",
                            original_value=original_section_id,
                            repaired_value=repaired,
                        )
                    )
        actions.append(PresentationPlanRepairAction(code="duplicate_section_id_repaired", section_id=repaired, message="Duplicate section id repaired deterministically.", original_value=section_id, repaired_value=repaired))


def _repair_duplicate_slide_ids(
    payload: dict[str, Any],
    policy: PresentationPlanRepairPolicy,
    actions: list[PresentationPlanRepairAction],
    findings: list[PresentationPlanRepairFinding],
) -> None:
    slides = payload.get("slides")
    if not isinstance(slides, list):
        return
    seen: Counter[str] = Counter()
    for index, slide in enumerate(slides, start=1):
        if not isinstance(slide, dict):
            continue
        slide_id = str(slide.get("slide_id") or f"slide-{index:03d}")
        seen[slide_id] += 1
        if seen[slide_id] == 1:
            slide["slide_id"] = slide_id
            continue
        if not policy.allow_id_repair:
            findings.append(PresentationPlanRepairFinding(code="repair_policy_blocked_action", severity="error", slide_id=slide_id, message="duplicate slide id repair blocked by policy."))
            continue
        repaired = f"{slide_id}-{seen[slide_id]:02d}"
        slide["slide_id"] = repaired
        actions.append(PresentationPlanRepairAction(code="duplicate_slide_id_repaired", slide_id=repaired, message="Duplicate slide id repaired deterministically.", original_value=slide_id, repaired_value=repaired))


def _repair_slide_roles(
    payload: dict[str, Any],
    policy: PresentationPlanRepairPolicy,
    actions: list[PresentationPlanRepairAction],
    findings: list[PresentationPlanRepairFinding],
) -> None:
    slides = payload.get("slides")
    if not isinstance(slides, list):
        return
    for index, slide in enumerate(slides, start=1):
        if not isinstance(slide, dict):
            continue
        role = slide.get("role")
        if role in VALID_SLIDE_ROLES:
            continue
        if not policy.allow_role_inference:
            findings.append(PresentationPlanRepairFinding(code="repair_policy_blocked_action", severity="error", slide_id=str(slide.get("slide_id")), message="slide role inference blocked by policy."))
            continue
        inferred = _infer_role(slide, index, len(slides))
        original = str(role) if role is not None else None
        slide["role"] = inferred
        actions.append(PresentationPlanRepairAction(code="slide_role_inferred", slide_id=str(slide.get("slide_id")), message="Slide role inferred deterministically.", original_value=original, repaired_value=inferred))


def _repair_visual_plans(
    payload: dict[str, Any],
    policy: PresentationPlanRepairPolicy,
    actions: list[PresentationPlanRepairAction],
    findings: list[PresentationPlanRepairFinding],
) -> None:
    slides = payload.get("slides")
    if not isinstance(slides, list):
        return
    for slide in slides:
        if not isinstance(slide, dict):
            continue
        visual = slide.get("visual_plan")
        if not isinstance(visual, dict):
            slide["visual_plan"] = {"visual_category": "text", "description": "Text fallback inserted by deterministic repair."}
            actions.append(PresentationPlanRepairAction(code="unsupported_visual_plan_downgraded", slide_id=str(slide.get("slide_id")), message="Missing visual plan downgraded to text.", repaired_value="text"))
            continue
        category = visual.get("visual_category")
        needs_downgrade = category not in VALID_VISUAL_CATEGORIES
        if category in {"chart", "table"} and not visual.get("source_table_ids") and not visual.get("data_requirements"):
            needs_downgrade = True
        if category == "image" and not visual.get("source_figure_ids"):
            needs_downgrade = True
        if not needs_downgrade:
            continue
        if not policy.allow_visual_plan_downgrade:
            findings.append(PresentationPlanRepairFinding(code="repair_policy_blocked_action", severity="error", slide_id=str(slide.get("slide_id")), message="visual plan downgrade blocked by policy."))
            continue
        original = str(category)
        visual["visual_category"] = "text"
        visual["description"] = f"Text fallback after unsupported or underspecified visual intent: {original}"
        visual.setdefault("data_requirements", [])
        visual.setdefault("source_figure_ids", [])
        visual.setdefault("source_table_ids", [])
        actions.append(PresentationPlanRepairAction(code="unsupported_visual_plan_downgraded", slide_id=str(slide.get("slide_id")), message="Unsupported or underspecified visual plan downgraded to text without fabricating data.", original_value=original, repaired_value="text"))


def _repair_typed_plan(
    plan: PresentationPlan,
    source_document: SourceDocument,
    policy: PresentationPlanRepairPolicy,
) -> tuple[PresentationPlan, list[PresentationPlanRepairAction], list[PresentationPlanRepairFinding]]:
    actions: list[PresentationPlanRepairAction] = []
    findings: list[PresentationPlanRepairFinding] = []
    chunk_by_id = {chunk.chunk_id: chunk for chunk in source_document.chunks}
    added_anchors = 0
    repaired_slides: list[SlidePlan] = []
    split_count = 0
    for slide in plan.slides:
        updated = slide
        matched_chunk = _best_chunk_match(slide, source_document)
        if slide.role in CONTENT_ROLES and not slide.evidence_anchors:
            if policy.allow_evidence_anchor_repair and matched_chunk is not None and added_anchors < policy.max_added_evidence_anchors:
                anchor = SlideEvidenceAnchor(
                    source_chunk_id=matched_chunk.chunk_id,
                    anchor_text=_anchor_text(matched_chunk.text),
                    line_range=(matched_chunk.start_line, matched_chunk.end_line),
                    confidence=0.62,
                )
                updated = updated.model_copy(update={"evidence_anchors": [anchor]})
                added_anchors += 1
                actions.append(PresentationPlanRepairAction(code="evidence_anchor_added", slide_id=slide.slide_id, message="Evidence anchor added from deterministic source text overlap.", repaired_value=matched_chunk.chunk_id))
            else:
                findings.append(PresentationPlanRepairFinding(code="evidence_anchor_unresolved", severity="error", slide_id=slide.slide_id, message="No source chunk met the overlap threshold for missing evidence."))
        repaired_claims = []
        for claim in updated.claims:
            if claim.source_chunk_ids:
                repaired_claims.append(claim)
                continue
            if policy.require_source_backing_for_claims and matched_chunk is not None:
                repaired_claims.append(claim.model_copy(update={"source_chunk_ids": [matched_chunk.chunk_id]}))
                actions.append(PresentationPlanRepairAction(code="claim_source_anchor_added", slide_id=slide.slide_id, message="Claim source chunk added from deterministic overlap.", repaired_value=matched_chunk.chunk_id))
            else:
                repaired_claims.append(claim)
                findings.append(PresentationPlanRepairFinding(code="claim_source_unresolved", severity="error", slide_id=slide.slide_id, message="Claim has no safe source chunk match."))
        if repaired_claims != list(updated.claims):
            updated = updated.model_copy(update={"claims": repaired_claims})
        dense_size = _slide_content_size(updated)
        if dense_size > 900 and policy.allow_slide_splitting and split_count < policy.max_split_slides and len(updated.supporting_points) >= 4 and len(plan.slides) < policy.max_generated_slide_count:
            first_points, second_points = _split_points(updated.supporting_points)
            updated = updated.model_copy(update={"supporting_points": first_points})
            split_slide = updated.model_copy(
                update={
                    "slide_id": _unique_slide_id(f"{updated.slide_id}-split", [slide.slide_id for slide in [*repaired_slides, *plan.slides]]),
                    "order_index": updated.order_index + 1,
                    "title": f"{updated.title} Continued",
                    "supporting_points": second_points,
                }
            )
            repaired_slides.append(updated)
            repaired_slides.append(split_slide)
            split_count += 1
            actions.append(PresentationPlanRepairAction(code="dense_slide_split", slide_id=updated.slide_id, message="Dense slide split into two slides with original evidence anchors preserved.", repaired_value=split_slide.slide_id))
            continue
        if dense_size > 900:
            findings.append(PresentationPlanRepairFinding(code="dense_slide_left_unresolved", severity="warning", slide_id=updated.slide_id, message="Dense slide could not be split safely under policy."))
        repaired_slides.append(updated)
    repaired_slides = [slide.model_copy(update={"order_index": index}) for index, slide in enumerate(repaired_slides, start=1)]
    repaired_sections = _sections_with_rebuilt_slide_ids(plan.sections, repaired_slides, chunk_by_id)
    if len(repaired_slides) < max(1, plan.target_slide_count - 2) or len(repaired_slides) > plan.target_slide_count + 2:
        actions.append(PresentationPlanRepairAction(code="target_slide_count_reported", message=f"Repaired slide count {len(repaired_slides)} remains outside tolerance for target {plan.target_slide_count}."))
    repaired_plan = plan.model_copy(update={"sections": repaired_sections, "slides": repaired_slides})
    return with_structural_hash(repaired_plan), actions, findings  # type: ignore[return-value]


def _parse_and_validate(raw_payload: dict[str, Any], source_document: SourceDocument) -> tuple[PresentationPlan | None, PresentationPlanValidationReport]:
    try:
        plan = PresentationPlan.model_validate(raw_payload)
    except Exception as exc:
        report = _synthetic_validation_report(raw_payload, source_document, exc)
        return None, report
    return plan, validate_presentation_plan(plan, source_document)


def _synthetic_validation_report(raw_payload: dict[str, Any], source_document: SourceDocument, exc: Exception) -> PresentationPlanValidationReport:
    findings = []
    message = str(exc)
    if "design_mode" in message:
        findings.append(PresentationPlanValidationFinding(code="unsupported_design_mode", severity="error", message="schema validation failed for design mode"))
    if "role" in message:
        findings.append(PresentationPlanValidationFinding(code="slide_missing_role", severity="error", message="schema validation failed for slide role"))
    if "visual_category" in message:
        findings.append(PresentationPlanValidationFinding(code="unsupported_visual_plan", severity="error", message="schema validation failed for visual category"))
    if not findings:
        findings.append(PresentationPlanValidationFinding(code="presentation_plan_schema_invalid", severity="error", message=message.splitlines()[0][:240]))
    report = PresentationPlanValidationReport(
        plan_id=str(raw_payload.get("plan_id") or "unparsed-plan"),
        source_document_id=str(raw_payload.get("source_document_id") or source_document.document_id),
        status="failed",
        finding_count=len(findings),
        error_count=len(findings),
        warning_count=0,
        findings=findings,
    )
    return with_structural_hash(report)  # type: ignore[return-value]


def _unresolved_findings(
    validation_report: PresentationPlanValidationReport,
    repair_findings: list[PresentationPlanRepairFinding],
) -> list[PresentationPlanRepairFinding]:
    unresolved = [
        PresentationPlanRepairFinding(
            code=finding.code,
            severity=finding.severity,
            message=finding.message,
            slide_id=finding.slide_id,
            section_id=finding.section_id,
            source_chunk_id=finding.source_chunk_id,
        )
        for finding in validation_report.findings
        if finding.severity == "error"
    ]
    unresolved.extend(repair_findings)
    return unresolved


def _infer_role(slide: dict[str, Any], index: int, slide_count: int) -> str:
    title = str(slide.get("title") or "").lower()
    if index == 1 or "title" in title:
        return "title"
    if "agenda" in title or "roadmap" in title:
        return "agenda"
    if "summary" in title or "takeaway" in title:
        return "summary"
    if "recommend" in title or index == slide_count:
        return "recommendation"
    return "analysis"


def _best_chunk_match(slide: SlidePlan, source_document: SourceDocument):
    query = _tokens(" ".join([slide.title, slide.main_message, *slide.supporting_points, *(claim.text for claim in slide.claims)]))
    if not query:
        return None
    best = None
    best_score = 0.0
    for chunk in source_document.chunks:
        chunk_tokens = _tokens(chunk.text)
        if not chunk_tokens:
            continue
        overlap = len(query & chunk_tokens)
        score = overlap / max(1, min(len(query), len(chunk_tokens)))
        if score > best_score:
            best = chunk
            best_score = score
    return best if best_score >= 0.18 and len(query & _tokens(best.text if best is not None else "")) >= 2 else None


def _tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) > 2 and token not in STOP_WORDS}


def _anchor_text(text: str) -> str:
    return " ".join(text.strip().split())[:220]


def _slide_content_size(slide: SlidePlan) -> int:
    return len(slide.title) + len(slide.main_message) + sum(len(point) for point in slide.supporting_points)


def _split_points(points: list[str]) -> tuple[list[str], list[str]]:
    midpoint = max(1, len(points) // 2)
    return points[:midpoint], points[midpoint:]


def _unique_slide_id(base: str, existing: list[str]) -> str:
    seen = set(existing)
    candidate = base
    index = 2
    while candidate in seen:
        candidate = f"{base}-{index:02d}"
        index += 1
    return candidate


def _rebuild_section_slide_ids(payload: dict[str, Any]) -> None:
    sections = payload.get("sections")
    slides = payload.get("slides")
    if not isinstance(sections, list) or not isinstance(slides, list):
        return
    by_section: dict[str, list[str]] = {}
    for slide in slides:
        if isinstance(slide, dict):
            by_section.setdefault(str(slide.get("section_id")), []).append(str(slide.get("slide_id")))
    for section in sections:
        if isinstance(section, dict):
            section["slide_ids"] = by_section.get(str(section.get("section_id")), [])


def _repair_orphan_slide_sections(
    payload: dict[str, Any],
    policy: PresentationPlanRepairPolicy,
    actions: list[PresentationPlanRepairAction],
    findings: list[PresentationPlanRepairFinding],
) -> None:
    if not policy.allow_section_rebalancing:
        return
    sections = payload.get("sections")
    slides = payload.get("slides")
    if not isinstance(sections, list) or not isinstance(slides, list):
        return
    section_ids = [str(section.get("section_id")) for section in sections if isinstance(section, dict)]
    section_id_set = set(section_ids)
    assigned_counts = Counter(str(slide.get("section_id")) for slide in slides if isinstance(slide, dict))
    empty_sections = [section_id for section_id in section_ids if assigned_counts.get(section_id, 0) == 0]
    for slide in slides:
        if not isinstance(slide, dict):
            continue
        section_id = str(slide.get("section_id"))
        if section_id in section_id_set:
            continue
        if empty_sections:
            repaired = empty_sections.pop(0)
            slide["section_id"] = repaired
            actions.append(PresentationPlanRepairAction(code="section_orphan_reassigned", slide_id=str(slide.get("slide_id")), section_id=repaired, message="Slide referencing a missing section was reassigned to an empty repaired section.", original_value=section_id, repaired_value=repaired))
        else:
            findings.append(PresentationPlanRepairFinding(code="section_orphan_unresolved", severity="error", slide_id=str(slide.get("slide_id")), section_id=section_id, message="Slide references a missing section and no deterministic empty section was available."))


def _sections_with_rebuilt_slide_ids(sections: list[DeckSectionPlan], slides: list[SlidePlan], chunk_by_id: dict[str, Any]) -> list[DeckSectionPlan]:
    by_section: dict[str, list[str]] = {}
    for slide in slides:
        by_section.setdefault(slide.section_id, []).append(slide.slide_id)
    repaired = []
    for section in sections:
        repaired.append(section.model_copy(update={"slide_ids": by_section.get(section.section_id, [])}))
    return repaired


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
