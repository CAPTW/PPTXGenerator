"""Deterministic QA governance refresh for persisted waivers and remediation linkage."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import UTC, datetime

from ..compat.legacy_non_pptx import (
    QAFinding,
    QAFindingGovernanceDisposition,
    QAFindingGovernanceStatus,
    QAGovernance,
    QAGovernanceIssue,
    QAGovernanceSummary,
    QARemediationRecord,
    QARemediationStatus,
    QAReport,
    QASeverity,
    QAWaiverRecord,
    QAWaiverScope,
    QAWaiverStatus,
    ReleaseReadinessPosture,
)


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        value = str(item).strip()
        if not value or value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def _slug(text: str) -> str:
    chars = [char.lower() if char.isalnum() else "-" for char in text]
    slug = "".join(chars).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug or "item"


def _waiver_status(waiver: QAWaiverRecord) -> QAWaiverStatus | str:
    return getattr(waiver, "status", None) or QAWaiverStatus.ACTIVE


def _is_expired(waiver: QAWaiverRecord, evaluated_at: datetime) -> bool:
    if _waiver_status(waiver) == QAWaiverStatus.EXPIRED:
        return True
    expires_at = getattr(waiver, "expires_at", None)
    return expires_at is not None and expires_at <= evaluated_at


def _waiver_matches_finding(waiver: QAWaiverRecord, finding: QAFinding) -> bool:
    related_slide_ids = list(getattr(waiver, "related_slide_ids", []) or [])
    related_finding_ids = list(getattr(waiver, "related_finding_ids", []) or [])
    related_finding_categories = list(getattr(waiver, "related_finding_categories", []) or [])
    if waiver.scope == QAWaiverScope.SLIDE_LEVEL:
        if finding.slide_id is None or finding.slide_id not in related_slide_ids:
            return False
    if related_finding_ids and finding.finding_id not in related_finding_ids:
        return False
    if related_finding_categories and finding.category not in related_finding_categories:
        return False
    if waiver.scope == QAWaiverScope.FINDING_LEVEL:
        return bool(related_finding_ids or related_finding_categories)
    if waiver.scope == QAWaiverScope.SLIDE_LEVEL:
        return True
    return True


def _issue_builder() -> tuple[list[QAGovernanceIssue], callable]:
    issues: list[QAGovernanceIssue] = []
    counters: Counter[str] = Counter()

    def _add_issue(
        category: str,
        summary: str,
        *,
        severity: QASeverity = QASeverity.MINOR,
        finding_ids: list[str] | None = None,
        waiver_ids: list[str] | None = None,
        remediation_ids: list[str] | None = None,
    ) -> None:
        counters[category] += 1
        issues.append(
            QAGovernanceIssue(
                issue_id=f"gov-{_slug(category)}-{counters[category]:03d}",
                category=category,
                severity=severity,
                summary=summary,
                related_finding_ids=finding_ids or [],
                related_waiver_ids=waiver_ids or [],
                related_remediation_ids=remediation_ids or [],
            )
        )

    return issues, _add_issue


def refresh_qa_governance(
    qa_report: QAReport,
    *,
    prior_report: QAReport | None = None,
    persisted_governance: QAGovernance | None = None,
    evaluated_at: datetime | None = None,
) -> QAGovernance:
    now = evaluated_at or datetime.now(UTC)
    waivers = list(persisted_governance.waivers if persisted_governance is not None else [])
    remediations = list(persisted_governance.remediations if persisted_governance is not None else [])
    current_findings = {finding.finding_id: finding for finding in qa_report.findings}
    prior_findings = {finding.finding_id: finding for finding in prior_report.findings} if prior_report is not None else {}
    known_findings = dict(prior_findings)
    known_findings.update(current_findings)
    issues, add_issue = _issue_builder()

    matched_findings_by_waiver: dict[str, list[str]] = {}
    active_waiver_ids_by_finding: dict[str, list[str]] = defaultdict(list)
    expired_waiver_ids_by_finding: dict[str, list[str]] = defaultdict(list)
    expired_waiver_count = 0
    orphan_waiver_count = 0

    for waiver in waivers:
        matched = [
            finding_id
            for finding_id, finding in known_findings.items()
            if _waiver_matches_finding(waiver, finding)
        ]
        matched_findings_by_waiver[waiver.waiver_id] = matched
        if not matched:
            orphan_waiver_count += 1
            add_issue(
                "orphan-waiver",
                f"Waiver `{waiver.waiver_id}` does not match any current or prior QA finding scope.",
                severity=QASeverity.MAJOR,
                waiver_ids=[waiver.waiver_id],
            )
        if _is_expired(waiver, now):
            expired_waiver_count += 1
            add_issue(
                "expired-waiver",
                f"Waiver `{waiver.waiver_id}` is expired and no longer clears linked findings.",
                severity=QASeverity.MAJOR,
                finding_ids=matched,
                waiver_ids=[waiver.waiver_id],
            )
            for finding_id in matched:
                expired_waiver_ids_by_finding[finding_id].append(waiver.waiver_id)
            continue
        if _waiver_status(waiver) != QAWaiverStatus.ACTIVE:
            continue
        for finding_id in matched:
            active_waiver_ids_by_finding[finding_id].append(waiver.waiver_id)

    matching_findings_by_remediation: dict[str, list[str]] = {}
    remediations_by_finding: dict[str, list[QARemediationRecord]] = defaultdict(list)
    orphan_remediation_count = 0
    for remediation in remediations:
        matched = [finding_id for finding_id in remediation.related_finding_ids if finding_id in known_findings]
        matching_findings_by_remediation[remediation.remediation_id] = matched
        if not matched:
            orphan_remediation_count += 1
            add_issue(
                "orphan-remediation",
                f"Remediation `{remediation.remediation_id}` does not match any current or prior QA finding id.",
                severity=QASeverity.MAJOR,
                remediation_ids=[remediation.remediation_id],
            )
            continue
        for finding_id in matched:
            remediations_by_finding[finding_id].append(remediation)

    finding_statuses: list[QAFindingGovernanceStatus] = []
    remediated_prior_count = 0
    unresolved_findings = 0
    waived_findings = 0
    accepted_risk_findings = 0
    blocking_findings_still_open = 0
    remediation_mismatch_count = 0

    for finding_id, finding in current_findings.items():
        active_waiver_ids = _dedupe(active_waiver_ids_by_finding.get(finding_id, []))
        expired_waiver_ids = _dedupe(expired_waiver_ids_by_finding.get(finding_id, []))
        matching_remediations = remediations_by_finding.get(finding_id, [])
        remediation_ids = _dedupe([record.remediation_id for record in matching_remediations])
        notes: list[str] = []

        if expired_waiver_ids:
            notes.append(f"Expired waiver ids: {', '.join(expired_waiver_ids)}.")

        waived_without_active = [
            record.remediation_id
            for record in matching_remediations
            if record.status == QARemediationStatus.WAIVED
        ]
        if waived_without_active and not active_waiver_ids:
            add_issue(
                "waived-without-active-waiver",
                f"Finding `{finding_id}` is marked waived in remediation state but has no active waiver record.",
                severity=QASeverity.MAJOR,
                finding_ids=[finding_id],
                remediation_ids=waived_without_active,
            )
            notes.append("Remediation status says waived, but no active waiver is persisted.")

        mismatch_ids = [
            record.remediation_id
            for record in matching_remediations
            if record.status in {QARemediationStatus.FIXED, QARemediationStatus.VERIFIED}
        ]
        if mismatch_ids:
            remediation_mismatch_count += 1
            add_issue(
                "remediation-verification-mismatch",
                f"Finding `{finding_id}` is still present after remediation claimed it was fixed or verified.",
                severity=QASeverity.CRITICAL if finding.blocking else QASeverity.MAJOR,
                finding_ids=[finding_id],
                remediation_ids=mismatch_ids,
            )
            notes.append("Current QA still detects the finding after a fixed/verified remediation record.")

        cannot_fix_ids = [
            record.remediation_id
            for record in matching_remediations
            if record.status == QARemediationStatus.CANNOT_FIX
        ]
        if active_waiver_ids:
            if cannot_fix_ids:
                disposition = QAFindingGovernanceDisposition.ACCEPTED_RISK
                accepted_risk_findings += 1
                notes.append("Accepted risk is backed by an active waiver.")
            else:
                disposition = QAFindingGovernanceDisposition.WAIVED
                waived_findings += 1
        else:
            disposition = QAFindingGovernanceDisposition.UNRESOLVED
            unresolved_findings += 1
            if finding.blocking:
                blocking_findings_still_open += 1

        finding_statuses.append(
            QAFindingGovernanceStatus(
                finding_id=finding_id,
                category=finding.category,
                blocking=finding.blocking,
                current_report_present=True,
                disposition=disposition,
                slide_number=finding.slide_number,
                slide_id=finding.slide_id,
                waiver_ids=active_waiver_ids,
                remediation_ids=remediation_ids,
                notes=notes,
            )
        )

    for finding_id, finding in prior_findings.items():
        if finding_id in current_findings:
            continue
        matching_remediations = remediations_by_finding.get(finding_id, [])
        if not matching_remediations:
            continue
        if not any(record.status in {QARemediationStatus.FIXED, QARemediationStatus.VERIFIED} for record in matching_remediations):
            continue
        remediated_prior_count += 1
        finding_statuses.append(
            QAFindingGovernanceStatus(
                finding_id=finding_id,
                category=finding.category,
                blocking=finding.blocking,
                current_report_present=False,
                disposition=QAFindingGovernanceDisposition.REMEDIATED,
                slide_number=finding.slide_number,
                slide_id=finding.slide_id,
                remediation_ids=_dedupe([record.remediation_id for record in matching_remediations]),
                notes=["The finding was present in the prior report and is absent from the current QA run."],
            )
        )

    depends_on_operator_exceptions = (waived_findings + accepted_risk_findings) > 0
    if remediated_prior_count and depends_on_operator_exceptions:
        qa_improvement_source = "mixed"
    elif remediated_prior_count:
        qa_improvement_source = "real-remediation"
    elif depends_on_operator_exceptions:
        qa_improvement_source = "waiver-only"
    else:
        qa_improvement_source = "none"

    if blocking_findings_still_open:
        release_posture = ReleaseReadinessPosture.UNRESOLVED_BLOCKING_ISSUE
    elif depends_on_operator_exceptions:
        release_posture = ReleaseReadinessPosture.OPERATOR_ENFORCED_EXCEPTION
    else:
        release_posture = ReleaseReadinessPosture.REPO_BACKED_CLEAR

    summary = QAGovernanceSummary(
        total_findings=len(finding_statuses),
        unresolved_findings=unresolved_findings,
        remediated_findings=remediated_prior_count,
        waived_findings=waived_findings,
        accepted_risk_findings=accepted_risk_findings,
        expired_waiver_count=expired_waiver_count,
        orphan_waiver_count=orphan_waiver_count,
        orphan_remediation_count=orphan_remediation_count,
        remediation_mismatch_count=remediation_mismatch_count,
        blocking_findings_still_open=blocking_findings_still_open,
        depends_on_operator_exceptions=depends_on_operator_exceptions,
        qa_improvement_source=qa_improvement_source,
        release_readiness_posture=release_posture,
    )
    notes: list[str] = []
    if depends_on_operator_exceptions:
        notes.append("Current QA posture depends on operator-approved waivers rather than on remediation alone.")
    if remediated_prior_count:
        notes.append("At least one prior QA finding cleared after a persisted remediation record.")

    return QAGovernance(
        governance_id=f"qa-governance-{qa_report.report_id}",
        deck_title=qa_report.deck_title,
        source_report_id=qa_report.report_id,
        prior_report_id=prior_report.report_id if prior_report is not None else None,
        generated_at=now,
        waivers=waivers,
        remediations=remediations,
        finding_statuses=sorted(finding_statuses, key=lambda item: (item.current_report_present is False, item.finding_id)),
        issues=issues,
        summary=summary,
        notes=notes,
    )
