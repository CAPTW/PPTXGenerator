from __future__ import annotations

from typing import Any, Iterable

from .non_pptx_modules.state_schemas import (
    CompileEligibility,
    PolicyEvidenceSource,
    PolicyRuleOutcome,
    PolicyRuleResult,
    QAReport,
    QAStatus,
    QAVerdictSummary,
    RenderValidationVerdict,
)
from .pptx_compiler import BuildManifest
from .review_loop_policy import CropVisualReviewReport


def _dedupe(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        ordered.append(text)
    return ordered


def _rule(
    rule_id: str,
    outcome: PolicyRuleOutcome,
    evidence_source: PolicyEvidenceSource,
    summary: str,
    *,
    reason_codes: Iterable[str] = (),
) -> PolicyRuleResult:
    return PolicyRuleResult(
        rule_id=rule_id,
        outcome=outcome,
        evidence_source=evidence_source,
        summary=summary,
        reason_codes=_dedupe(reason_codes),
    )


def _coerce_review_loop_report(review_loop_report: CropVisualReviewReport | dict[str, Any] | None) -> CropVisualReviewReport | None:
    if review_loop_report is None:
        return None
    if isinstance(review_loop_report, CropVisualReviewReport):
        return review_loop_report
    if isinstance(review_loop_report, dict):
        return CropVisualReviewReport.model_validate(review_loop_report)
    raise TypeError(f"unsupported review_loop_report type: {type(review_loop_report).__name__}")


def _coerce_qa_verdict(summary: QAVerdictSummary | dict[str, Any] | None) -> QAVerdictSummary | None:
    if summary is None:
        return None
    if isinstance(summary, QAVerdictSummary):
        return summary
    if isinstance(summary, dict):
        return QAVerdictSummary.model_validate(summary)
    raise TypeError(f"unsupported qa verdict type: {type(summary).__name__}")


def _continuity_rule_from_existing_verdict(
    summary: QAVerdictSummary | dict[str, Any] | None,
    *,
    qa_status: QAStatus,
) -> tuple[PolicyRuleResult | None, PolicyEvidenceSource | None, list[str]]:
    existing_summary = _coerce_qa_verdict(summary)
    if existing_summary is None or existing_summary.qa_status != qa_status:
        return None, None, []
    continuity_rule = next(
        (rule for rule in existing_summary.rule_results if rule.rule_id == "continuity-policy-input"),
        None,
    )
    if continuity_rule is None:
        return None, None, []
    compatibility_codes: list[str] = []
    if (
        continuity_rule.evidence_source == PolicyEvidenceSource.COMPATIBILITY_ONLY
        or existing_summary.continuity_signal_source == PolicyEvidenceSource.COMPATIBILITY_ONLY
    ):
        compatibility_codes.append("continuity-warning-strings-only")
    return (
        continuity_rule,
        existing_summary.continuity_signal_source or continuity_rule.evidence_source,
        _dedupe(compatibility_codes),
    )


def _flatten_alert_codes(continuity_alerts: Iterable[Any] | None) -> list[str]:
    if continuity_alerts is None:
        return []
    codes: list[str] = []
    for alert in continuity_alerts:
        warning_codes = getattr(alert, "warning_codes", None)
        if warning_codes is None and isinstance(alert, dict):
            warning_codes = alert.get("warning_codes")
        if isinstance(warning_codes, list):
            codes.extend(str(code) for code in warning_codes)
    return _dedupe(codes)


def summarize_qa_verdict(
    *,
    qa_report: QAReport,
    build_manifest: BuildManifest,
    render_checks_present: bool,
    render_check_failure_codes: list[str] | None = None,
    continuity_alerts: Iterable[Any] | None = None,
    continuity_guidance_lines: Iterable[str] | None = None,
    continuity_warnings: Iterable[str] | None = None,
    existing_verdict_summary: QAVerdictSummary | dict[str, Any] | None = None,
    approval_outcome: str | None = None,
    review_loop_report: CropVisualReviewReport | dict[str, Any] | None = None,
) -> QAVerdictSummary:
    rule_results: list[PolicyRuleResult] = []
    render_check_failure_codes = _dedupe(render_check_failure_codes or [])
    continuity_warning_lines = _dedupe(continuity_guidance_lines or continuity_warnings or [])
    continuity_alert_codes = _flatten_alert_codes(continuity_alerts)
    compatibility_warning_codes: list[str] = []
    review_signal_source: PolicyEvidenceSource | None = None

    if qa_report.qa_status == QAStatus.FAIL:
        rule_results.append(
            _rule(
                "qa-status",
                PolicyRuleOutcome.BLOCKED,
                PolicyEvidenceSource.REPO_BACKED,
                "QA findings block compile readiness.",
                reason_codes=("qa-fail",),
            )
        )
    elif qa_report.qa_status == QAStatus.CONDITIONAL_PASS:
        rule_results.append(
            _rule(
                "qa-status",
                PolicyRuleOutcome.WARNING,
                PolicyEvidenceSource.REPO_BACKED,
                "QA findings remain advisory and require repair before stronger enforcement.",
                reason_codes=("qa-conditional-pass",),
            )
        )
    else:
        rule_results.append(
            _rule(
                "qa-status",
                PolicyRuleOutcome.PASS,
                PolicyEvidenceSource.REPO_BACKED,
                "QA findings are clear for the current compiled scope.",
            )
        )

    if render_check_failure_codes:
        rule_results.append(
            _rule(
                "compiled-deck-render-checks",
                PolicyRuleOutcome.BLOCKED,
                PolicyEvidenceSource.REPO_BACKED,
                "Render-backed compiled-deck checks failed for the current QA scope.",
                reason_codes=render_check_failure_codes,
            )
        )
        render_check_source = PolicyEvidenceSource.REPO_BACKED
    elif render_checks_present:
        rule_results.append(
            _rule(
                "compiled-deck-render-checks",
                PolicyRuleOutcome.PASS,
                PolicyEvidenceSource.REPO_BACKED,
                "Render-backed compiled-deck checks were available during QA.",
            )
        )
        render_check_source = PolicyEvidenceSource.REPO_BACKED
    else:
        rule_results.append(
            _rule(
                "compiled-deck-render-checks",
                PolicyRuleOutcome.WARNING,
                PolicyEvidenceSource.NOT_YET_EVIDENCED,
                "Render-backed compiled-deck checks are not yet evidenced for this QA result.",
                reason_codes=("render-checks-not-yet-evidenced",),
            )
        )
        render_check_source = PolicyEvidenceSource.NOT_YET_EVIDENCED

    continuity_signal_source: PolicyEvidenceSource | None = None
    if continuity_alert_codes:
        rule_results.append(
            _rule(
                "continuity-policy-input",
                PolicyRuleOutcome.WARNING,
                PolicyEvidenceSource.REPO_BACKED,
                "Structured continuity alerts remain advisory inputs for compile readiness.",
                reason_codes=continuity_alert_codes,
            )
        )
        continuity_signal_source = PolicyEvidenceSource.REPO_BACKED
    elif continuity_warning_lines:
        compatibility_warning_codes.append("continuity-warning-strings-only")
        rule_results.append(
            _rule(
                "continuity-policy-input",
                PolicyRuleOutcome.WARNING,
                PolicyEvidenceSource.COMPATIBILITY_ONLY,
                "Legacy continuity warning strings remain advisory until structured alerts are the sole policy input.",
                reason_codes=("continuity-warning-strings-only",),
            )
        )
        continuity_signal_source = PolicyEvidenceSource.COMPATIBILITY_ONLY
    else:
        existing_continuity_rule, existing_signal_source, existing_compatibility_codes = _continuity_rule_from_existing_verdict(
            existing_verdict_summary,
            qa_status=qa_report.qa_status,
        )
        if existing_continuity_rule is not None:
            rule_results.append(
                _rule(
                    "continuity-policy-input",
                    existing_continuity_rule.outcome,
                    existing_continuity_rule.evidence_source,
                    existing_continuity_rule.summary,
                    reason_codes=existing_continuity_rule.reason_codes,
                )
            )
            continuity_signal_source = existing_signal_source
            compatibility_warning_codes.extend(existing_compatibility_codes)

    review_report = _coerce_review_loop_report(review_loop_report)
    if review_report is not None:
        review_signal_source = PolicyEvidenceSource.REPO_BACKED
        review_codes = _dedupe(review_report.compile_warning_codes)
        if review_report.approval_outcome == "approved" and not review_codes:
            rule_results.append(
                _rule(
                    "review-loop-policy",
                    PolicyRuleOutcome.PASS,
                    PolicyEvidenceSource.REPO_BACKED,
                    "Structured crop/visual approval-loop data confirms compile-ready inputs.",
                )
            )
        else:
            fallback_code = f"review-loop-{review_report.approval_outcome}"
            rule_results.append(
                _rule(
                    "review-loop-policy",
                    PolicyRuleOutcome.WARNING,
                    PolicyEvidenceSource.REPO_BACKED,
                    "Structured crop/visual approval-loop data remains advisory for compile readiness in this phase.",
                    reason_codes=review_codes or (fallback_code,),
                )
            )
    elif approval_outcome is not None:
        review_signal_source = PolicyEvidenceSource.REPO_BACKED
        normalized_outcome = str(approval_outcome).strip().lower()
        if normalized_outcome == "approved":
            rule_results.append(
                _rule(
                    "review-loop-policy",
                    PolicyRuleOutcome.PASS,
                    PolicyEvidenceSource.REPO_BACKED,
                    "Approval outcome confirms compile-ready asset selection.",
                )
            )
        else:
            rule_results.append(
                _rule(
                    "review-loop-policy",
                    PolicyRuleOutcome.WARNING,
                    PolicyEvidenceSource.REPO_BACKED,
                    "Approval outcome remains advisory and does not block compile by itself in this phase.",
                    reason_codes=(f"review-loop-{normalized_outcome}",),
                )
            )

    if build_manifest.warnings:
        compatibility_warning_codes.append("build-warning-string-surface")
        rule_results.append(
            _rule(
                "build-warning-compatibility",
                PolicyRuleOutcome.WARNING,
                PolicyEvidenceSource.COMPATIBILITY_ONLY,
                "Compiler warning strings remain available for compatibility consumers.",
                reason_codes=("build-warning-string-surface",),
            )
        )

    blocking_reason_codes = _dedupe(
        code
        for rule in rule_results
        if rule.outcome == PolicyRuleOutcome.BLOCKED
        for code in rule.reason_codes
    )
    warning_reason_codes = _dedupe(
        code
        for rule in rule_results
        if rule.outcome == PolicyRuleOutcome.WARNING
        for code in rule.reason_codes
    )
    compatibility_warning_codes = _dedupe(compatibility_warning_codes)

    compile_eligibility = CompileEligibility.ELIGIBLE
    if blocking_reason_codes:
        compile_eligibility = CompileEligibility.INELIGIBLE
    elif warning_reason_codes:
        compile_eligibility = CompileEligibility.ADVISORY_ONLY

    return QAVerdictSummary(
        qa_status=qa_report.qa_status,
        compile_eligibility=compile_eligibility,
        render_checks_present=render_checks_present,
        render_check_source=render_check_source,
        continuity_signal_source=continuity_signal_source,
        review_signal_source=review_signal_source,
        blocking_reason_codes=blocking_reason_codes,
        warning_reason_codes=warning_reason_codes,
        compatibility_warning_codes=compatibility_warning_codes,
        rule_results=rule_results,
    )


def summarize_render_validation_verdict(
    *,
    render_validation: dict[str, Any],
    failure_reason: str | None,
    qa_verdict_summary: QAVerdictSummary | dict[str, Any] | None,
    build_manifest: BuildManifest,
) -> RenderValidationVerdict:
    rule_results: list[PolicyRuleResult] = []
    compatibility_warning_codes: list[str] = []

    validation_passed = failure_reason is None
    if validation_passed:
        rule_results.append(
            _rule(
                "local-pptx-render-validation",
                PolicyRuleOutcome.PASS,
                PolicyEvidenceSource.REPO_BACKED,
                "Local PPTX render validation passed against the compiled archive.",
            )
        )
    else:
        reason_codes = ["render-validation-failed"]
        if render_validation.get("slide_count") in {0, None}:
            reason_codes.append("render-validation-slide-count-missing")
        if render_validation.get("zip_readable") is not True:
            reason_codes.append("render-validation-zip-unreadable")
        if render_validation.get("presentation_xml_present") is not True:
            reason_codes.append("render-validation-presentation-xml-missing")
        rule_results.append(
            _rule(
                "local-pptx-render-validation",
                PolicyRuleOutcome.BLOCKED,
                PolicyEvidenceSource.REPO_BACKED,
                str(failure_reason or "Local PPTX render validation failed."),
                reason_codes=reason_codes,
            )
        )

    qa_summary = _coerce_qa_verdict(qa_verdict_summary)
    qa_status: QAStatus | None = None
    if qa_summary is None:
        rule_results.append(
            _rule(
                "qa-compile-eligibility",
                PolicyRuleOutcome.WARNING,
                PolicyEvidenceSource.NOT_YET_EVIDENCED,
                "Structured QA compile-readiness evidence is not yet attached to the render report.",
                reason_codes=("qa-verdict-summary-missing",),
            )
        )
    else:
        qa_status = qa_summary.qa_status
        if qa_summary.compile_eligibility == CompileEligibility.INELIGIBLE:
            rule_results.append(
                _rule(
                    "qa-compile-eligibility",
                    PolicyRuleOutcome.BLOCKED,
                    PolicyEvidenceSource.REPO_BACKED,
                    "Structured QA policy marks the compiled deck as ineligible for compile-ready promotion.",
                    reason_codes=qa_summary.blocking_reason_codes or ("qa-compile-ineligible",),
                )
            )
        elif qa_summary.compile_eligibility == CompileEligibility.ADVISORY_ONLY:
            rule_results.append(
                _rule(
                    "qa-compile-eligibility",
                    PolicyRuleOutcome.WARNING,
                    PolicyEvidenceSource.REPO_BACKED,
                    "Structured QA policy keeps compile readiness advisory-only for this deck.",
                    reason_codes=qa_summary.warning_reason_codes or ("qa-compile-advisory-only",),
                )
            )
        else:
            rule_results.append(
                _rule(
                    "qa-compile-eligibility",
                    PolicyRuleOutcome.PASS,
                    PolicyEvidenceSource.REPO_BACKED,
                    "Structured QA policy marks the compiled deck as compile-ready.",
                )
            )
        compatibility_warning_codes.extend(qa_summary.compatibility_warning_codes)

    if build_manifest.warnings:
        compatibility_warning_codes.append("build-warning-string-surface")
        rule_results.append(
            _rule(
                "build-warning-compatibility",
                PolicyRuleOutcome.WARNING,
                PolicyEvidenceSource.COMPATIBILITY_ONLY,
                "Compiler warning strings remain available for legacy consumers of the render report.",
                reason_codes=("build-warning-string-surface",),
            )
        )

    blocking_reason_codes = _dedupe(
        code
        for rule in rule_results
        if rule.outcome == PolicyRuleOutcome.BLOCKED
        for code in rule.reason_codes
    )
    warning_reason_codes = _dedupe(
        code
        for rule in rule_results
        if rule.outcome == PolicyRuleOutcome.WARNING
        for code in rule.reason_codes
    )
    compatibility_warning_codes = _dedupe(compatibility_warning_codes)

    compile_eligibility = CompileEligibility.ELIGIBLE
    if blocking_reason_codes:
        compile_eligibility = CompileEligibility.INELIGIBLE
    elif warning_reason_codes:
        compile_eligibility = CompileEligibility.ADVISORY_ONLY

    return RenderValidationVerdict(
        validation_passed=validation_passed,
        compile_eligibility=compile_eligibility,
        qa_status=qa_status,
        blocking_reason_codes=blocking_reason_codes,
        warning_reason_codes=warning_reason_codes,
        compatibility_warning_codes=compatibility_warning_codes,
        rule_results=rule_results,
    )
