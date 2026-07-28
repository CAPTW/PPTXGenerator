"""Build E02H-V2 readiness override from E01H-V2 QA audit findings."""

from __future__ import annotations

from typing import Any


def build_readiness_override(case_findings: list[dict[str, Any]]) -> dict[str, Any]:
    reason = None
    for finding in case_findings:
        if finding.get("baseline_shortcut_detected"):
            reason = "baseline_shortcut_detected"
            break
        if finding.get("internal_label_leakage_count", 0) > 0:
            reason = "internal_label_leakage"
            break
        if not finding.get("truth_reconstruction_pass", True):
            reason = "truth_reconstruction_failure"
            break
        if not finding.get("backplate_overlap_pass", True):
            reason = "backplate_overlap_failure"
            break
    unlocked = reason is None
    return {
        "schema_name": "e02h_v2_readiness_after_e01h_v2_qa",
        "status": "ready" if unlocked else "locked",
        "e02h_v2_unlocked": unlocked,
        "lock_reason": reason,
        "case_count": len(case_findings),
        "failing_case_count": sum(1 for row in case_findings if row.get("baseline_shortcut_detected") or row.get("internal_label_leakage_count", 0) > 0 or not row.get("truth_reconstruction_pass", True) or not row.get("backplate_overlap_pass", True)),
        "e02h_v2_started": False,
        "e05_unlocked": False,
        "canva_parity_claimed": False,
    }
