"""Fixed-brief workflow evaluation harness for Gate 1 -> Gate 2 -> compile -> QA robustness."""

from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import Field

from ..pptx_compiler import compile_pptx, write_pptx_compile_outputs
from ..compat.legacy_non_pptx import (
    AssetManifest,
    ContractModel,
    QARecommendationType,
    StageStatus,
    VizManifest,
    save_state_file,
)
from .deck_qa import run_deck_qa, write_deck_qa_outputs
from .gate2_planner import plan_gate2, write_gate2_outputs
from .ship_readiness import derive_release_readiness_summary
from .workflow_planner import WorkflowBriefInput, load_workflow_brief, plan_workflow


REPO_ROOT = Path(__file__).resolve().parents[3]
EVALUATION_BRIEFS_DIR = REPO_ROOT / "examples" / "evaluation-briefs"


class WorkflowEvaluationScorecard(ContractModel):
    brief_id: str
    deck_title: str = ""
    workflow_option: str = ""
    parse_success: bool = False
    gate1_success: bool = False
    gate2_success: bool = False
    compile_success: bool = False
    qa_status: str = "unavailable"
    qa_policy_source: str = "raw-qa-status"
    qa_compile_eligibility: str | None = None
    qa_warning_reason_codes: list[str] = Field(default_factory=list)
    qa_blocking_reason_codes: list[str] = Field(default_factory=list)
    qa_compatibility_warning_codes: list[str] = Field(default_factory=list)
    slide_count: int = 0
    blueprint_completeness: float = 0.0
    rewrite_pressure: float = 0.0
    compile_warning_count: int = 0
    compile_warning_policy_source: str = "none"
    qa_warning_counts_by_category: dict[str, int] = Field(default_factory=dict)
    qa_blocking_counts_by_category: dict[str, int] = Field(default_factory=dict)
    waived_finding_count: int = 0
    remediated_finding_count: int = 0
    unresolved_blocking_count: int = 0
    expired_waiver_count: int = 0
    orphan_waiver_count: int = 0
    orphan_remediation_count: int = 0
    remediation_mismatch_count: int = 0
    depends_on_operator_exceptions: bool = False
    qa_improvement_source: str = "none"
    governance_posture: str = "unavailable"
    ship_ready: bool = False
    release_posture: str = "unavailable"
    release_blocked_under_current_governance: bool = False
    deck_level_quality_notes: list[str] = Field(default_factory=list)
    artifact_dir: str = ""
    error: str | None = None


class WorkflowEvaluationReport(ContractModel):
    schema_name: str = "workflow_evaluation_report"
    schema_version: str = "1.0"
    generated_at: str
    brief_set: list[str] = Field(default_factory=list)
    scorecards: list[WorkflowEvaluationScorecard] = Field(default_factory=list)
    aggregate: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


def _evaluation_brief_paths() -> list[Path]:
    return sorted(path for path in EVALUATION_BRIEFS_DIR.glob("*.yaml") if path.is_file())


def _blueprint_completeness(blueprint) -> float:
    if not blueprint.slides:
        return 0.0
    total_checks = len(blueprint.slides) * 8
    passed = 0
    for slide in blueprint.slides:
        if slide.primary_claim:
            passed += 1
        if slide.audience_intent:
            passed += 1
        if slide.must_keep_text:
            passed += 1
        if {"title", "claim"} <= set(slide.layout_slot_map):
            passed += 1
        if slide.visual_intent:
            passed += 1
        if slide.density_budget.layout_slot_count >= len(set(slide.layout_slot_map.values())):
            passed += 1
        if slide.risk_flags:
            passed += 1
        if slide.qa_acceptance_hints:
            passed += 1
    return round(passed / total_checks, 3)


def _rewrite_pressure(qa_report, slide_count: int) -> float:
    pressure_findings = [
        finding
        for finding in qa_report.findings
        if finding.recommendation_type != QARecommendationType.SAFE_TO_DEFER
    ]
    return round(len(pressure_findings) / max(slide_count, 1), 3)


def _category_counts(qa_report) -> tuple[dict[str, int], dict[str, int]]:
    warning_counts = Counter(
        finding.category
        for finding in qa_report.findings
        if not finding.blocking
    )
    blocking_counts = Counter(
        finding.category
        for finding in qa_report.findings
        if finding.blocking
    )
    return dict(sorted(warning_counts.items())), dict(sorted(blocking_counts.items()))


def _resolve_qa_policy_summary(qa_report) -> tuple[Any | None, str]:
    summary = getattr(qa_report, "verdict_summary", None)
    if summary is None:
        return None, "raw-qa-status"
    summary_status = getattr(getattr(summary, "qa_status", None), "value", getattr(summary, "qa_status", None))
    raw_status = getattr(getattr(qa_report, "qa_status", None), "value", getattr(qa_report, "qa_status", None))
    if summary_status is None or raw_status is None:
        return None, "raw-qa-status"
    if str(summary_status) != str(raw_status):
        return None, "raw-qa-status-mismatch-fallback"
    return summary, "verdict-summary"


def _resolve_compile_warning_count(qa_policy_summary: Any | None, build_manifest) -> tuple[int, str]:
    raw_build_warning_count = len(build_manifest.warnings)
    compatibility_warning_codes = (
        list(getattr(qa_policy_summary, "compatibility_warning_codes", []))
        if qa_policy_summary is not None
        else []
    )
    if "build-warning-string-surface" in compatibility_warning_codes:
        if raw_build_warning_count > 0:
            return raw_build_warning_count, "structured-compatibility-code"
        return 1, "structured-compatibility-code"
    if raw_build_warning_count > 0:
        return raw_build_warning_count, "raw-build-manifest"
    return 0, "none"


def _deck_level_quality_notes(compile_warning_count: int, qa_report) -> list[str]:
    notes: list[str] = []
    if compile_warning_count:
        notes.append(f"Compile emitted {compile_warning_count} warning(s).")
    category_counts = Counter(finding.category for finding in qa_report.findings)
    for category, count in category_counts.most_common(3):
        notes.append(f"{category}: {count}")
    if not notes:
        notes.append("No QA findings.")
    return notes


def _empty_manifests(deck_title: str) -> tuple[AssetManifest, VizManifest]:
    return AssetManifest(deck_title=deck_title, assets=[]), VizManifest(deck_title=deck_title, visuals=[])


def _write_workflow_eval_artifacts(
    brief_dir: Path,
    workflow_plan,
    gate2_outputs,
    approved_blueprint,
    asset_manifest: AssetManifest,
    viz_manifest: VizManifest,
) -> None:
    state_dir = brief_dir / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    save_state_file(workflow_plan, state_dir / "workflow-plan.json")
    written_gate2 = write_gate2_outputs(gate2_outputs, state_dir)
    save_state_file(approved_blueprint, written_gate2["blueprint"])
    save_state_file(asset_manifest, state_dir / "asset-manifest.json")
    save_state_file(viz_manifest, state_dir / "viz-manifest.json")


def evaluate_workflow_brief(brief_path: str | Path, output_root: str | Path) -> WorkflowEvaluationScorecard:
    brief_file = Path(brief_path)
    brief_dir = Path(output_root) / brief_file.stem
    brief_dir.mkdir(parents=True, exist_ok=True)
    scorecard = WorkflowEvaluationScorecard(
        brief_id=brief_file.stem,
        artifact_dir=str(brief_dir),
    )

    try:
        brief: WorkflowBriefInput = load_workflow_brief(brief_file)
        scorecard.parse_success = True
        scorecard.deck_title = brief.deck_title or brief.topic
        workflow_plan = plan_workflow(brief)
        scorecard.gate1_success = True
        scorecard.workflow_option = workflow_plan.workflow_option
        gate2_outputs = plan_gate2(workflow_plan, brief=brief)
        scorecard.gate2_success = True

        approved_blueprint = gate2_outputs.blueprint.model_copy(update={"approval_status": StageStatus.APPROVED})
        asset_manifest, viz_manifest = _empty_manifests(approved_blueprint.deck_title)
        _write_workflow_eval_artifacts(
            brief_dir,
            workflow_plan,
            gate2_outputs,
            approved_blueprint,
            asset_manifest,
            viz_manifest,
        )

        compile_outputs = compile_pptx(
            blueprint=approved_blueprint,
            design_system=gate2_outputs.design_system,
            deck_constitution=gate2_outputs.deck_constitution,
            layout_library=gate2_outputs.layout_library,
            slide_ledger=gate2_outputs.slide_ledger,
            asset_manifest=asset_manifest,
            viz_manifest=viz_manifest,
            output_dir=brief_dir / "compiled",
            root=brief_dir,
        )
        scorecard.compile_success = True
        scorecard.slide_count = compile_outputs.build_manifest.slide_count
        write_pptx_compile_outputs(compile_outputs, brief_dir / "compiled")

        qa_outputs = run_deck_qa(
            blueprint=approved_blueprint,
            design_system=gate2_outputs.design_system,
            deck_constitution=gate2_outputs.deck_constitution,
            layout_library=gate2_outputs.layout_library,
            slide_ledger=compile_outputs.slide_ledger,
            asset_manifest=asset_manifest,
            viz_manifest=viz_manifest,
            build_manifest=compile_outputs.build_manifest,
            slide_build_linkage=compile_outputs.slide_build_linkage,
            artifact_root=brief_dir,
        )
        write_deck_qa_outputs(qa_outputs, brief_dir / "qa")

        qa_policy_summary, qa_policy_source = _resolve_qa_policy_summary(qa_outputs.qa_report)
        scorecard.qa_policy_source = qa_policy_source
        scorecard.compile_warning_count, scorecard.compile_warning_policy_source = _resolve_compile_warning_count(
            qa_policy_summary,
            compile_outputs.build_manifest,
        )
        if qa_policy_summary is not None:
            scorecard.qa_status = qa_policy_summary.qa_status.value
            scorecard.qa_compile_eligibility = qa_policy_summary.compile_eligibility.value
            scorecard.qa_warning_reason_codes = list(qa_policy_summary.warning_reason_codes)
            scorecard.qa_blocking_reason_codes = list(qa_policy_summary.blocking_reason_codes)
            scorecard.qa_compatibility_warning_codes = list(qa_policy_summary.compatibility_warning_codes)
        else:
            scorecard.qa_status = qa_outputs.qa_report.qa_status.value
        scorecard.blueprint_completeness = _blueprint_completeness(approved_blueprint)
        scorecard.rewrite_pressure = _rewrite_pressure(qa_outputs.qa_report, scorecard.slide_count)
        warning_counts, blocking_counts = _category_counts(qa_outputs.qa_report)
        scorecard.qa_warning_counts_by_category = warning_counts
        scorecard.qa_blocking_counts_by_category = blocking_counts
        if qa_outputs.qa_governance is not None:
            governance = qa_outputs.qa_governance.summary
            release_readiness = derive_release_readiness_summary(
                qa_report=qa_outputs.qa_report,
                qa_governance=qa_outputs.qa_governance,
                build_manifest=compile_outputs.build_manifest,
                ship_gate_ready=True,
                ship_gate_reasons=[],
                related_stage="workflow-evaluation",
                generated_by="workflow-evaluation",
            )
            scorecard.waived_finding_count = governance.waived_findings
            scorecard.remediated_finding_count = governance.remediated_findings
            scorecard.unresolved_blocking_count = governance.blocking_findings_still_open
            scorecard.expired_waiver_count = governance.expired_waiver_count
            scorecard.orphan_waiver_count = governance.orphan_waiver_count
            scorecard.orphan_remediation_count = governance.orphan_remediation_count
            scorecard.remediation_mismatch_count = governance.remediation_mismatch_count
            scorecard.depends_on_operator_exceptions = governance.depends_on_operator_exceptions
            scorecard.qa_improvement_source = governance.qa_improvement_source
            scorecard.governance_posture = governance.release_readiness_posture.value
            scorecard.ship_ready = release_readiness.ship_ready
            scorecard.release_posture = release_readiness.release_posture.value
            scorecard.release_blocked_under_current_governance = not release_readiness.ship_ready
        scorecard.deck_level_quality_notes = _deck_level_quality_notes(
            scorecard.compile_warning_count,
            qa_outputs.qa_report,
        )
        return scorecard
    except Exception as exc:
        scorecard.error = str(exc)
        return scorecard


def evaluate_workflow_harness(output_root: str | Path) -> WorkflowEvaluationReport:
    output_dir = Path(output_root)
    output_dir.mkdir(parents=True, exist_ok=True)
    brief_paths = _evaluation_brief_paths()
    scorecards = [evaluate_workflow_brief(path, output_dir) for path in brief_paths]
    warning_totals = Counter()
    blocking_totals = Counter()
    qa_status_counts = Counter()
    compile_eligibility_counts = Counter()
    qa_policy_source_counts = Counter()
    compile_warning_policy_source_counts = Counter()
    for scorecard in scorecards:
        warning_totals.update(scorecard.qa_warning_counts_by_category)
        blocking_totals.update(scorecard.qa_blocking_counts_by_category)
        qa_status_counts.update([scorecard.qa_status])
        compile_eligibility_counts.update([scorecard.qa_compile_eligibility or "unavailable"])
        qa_policy_source_counts.update([scorecard.qa_policy_source])
        compile_warning_policy_source_counts.update([scorecard.compile_warning_policy_source])
    aggregate = {
        "brief_count": len(scorecards),
        "parse_success_count": sum(1 for card in scorecards if card.parse_success),
        "gate1_success_count": sum(1 for card in scorecards if card.gate1_success),
        "gate2_success_count": sum(1 for card in scorecards if card.gate2_success),
        "compile_success_count": sum(1 for card in scorecards if card.compile_success),
        "qa_status_counts": dict(sorted(qa_status_counts.items())),
        "compile_eligibility_counts": dict(sorted(compile_eligibility_counts.items())),
        "qa_policy_source_counts": dict(sorted(qa_policy_source_counts.items())),
        "compile_warning_policy_source_counts": dict(sorted(compile_warning_policy_source_counts.items())),
        "average_blueprint_completeness": round(
            sum(card.blueprint_completeness for card in scorecards) / max(len(scorecards), 1),
            3,
        ),
        "average_rewrite_pressure": round(
            sum(card.rewrite_pressure for card in scorecards) / max(len(scorecards), 1),
            3,
        ),
        "waived_finding_count": sum(card.waived_finding_count for card in scorecards),
        "remediated_finding_count": sum(card.remediated_finding_count for card in scorecards),
        "unresolved_blocking_count": sum(card.unresolved_blocking_count for card in scorecards),
        "expired_waiver_count": sum(card.expired_waiver_count for card in scorecards),
        "orphan_waiver_count": sum(card.orphan_waiver_count for card in scorecards),
        "orphan_remediation_count": sum(card.orphan_remediation_count for card in scorecards),
        "remediation_mismatch_count": sum(card.remediation_mismatch_count for card in scorecards),
        "operator_exception_run_count": sum(1 for card in scorecards if card.depends_on_operator_exceptions),
        "ship_ready_count": sum(1 for card in scorecards if card.ship_ready),
        "release_blocked_count": sum(1 for card in scorecards if card.release_blocked_under_current_governance),
        "release_posture_counts": dict(sorted(Counter(card.release_posture for card in scorecards).items())),
        "qa_improvement_counts": dict(sorted(Counter(card.qa_improvement_source for card in scorecards).items())),
        "governance_posture_counts": dict(sorted(Counter(card.governance_posture for card in scorecards).items())),
        "qa_warning_counts_by_category": dict(sorted(warning_totals.items())),
        "qa_blocking_counts_by_category": dict(sorted(blocking_totals.items())),
    }
    notes = [
        "The harness marks Gate 2 blueprints approved before compile so workflow robustness can be evaluated without simulating human review UI.",
        "This harness measures contract strength and downstream stability, not model benchmark quality.",
        "Release-readiness signals here are derived from build plus persisted QA governance only; later approval-backlog phases are out of scope for this harness.",
    ]
    return WorkflowEvaluationReport(
        generated_at=datetime.now(UTC).isoformat(),
        brief_set=[path.name for path in brief_paths],
        scorecards=scorecards,
        aggregate=aggregate,
        notes=notes,
    )


def write_workflow_evaluation_report(report: WorkflowEvaluationReport, output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2), encoding="utf-8")
    return path
