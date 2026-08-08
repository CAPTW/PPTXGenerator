"""High-fidelity acceptance policy layered on top of visual-polish QA.

The external visual QA Skill deliberately reports small renderer differences as
``needs_polish``.  Those differences are useful diagnostics, but they should not
force a full-deck rebuild when they match the known native-PPTX/HTML drift seen
in the accepted quality canary.  Content, hierarchy, geometry, and readability
issues remain release blocking.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from ..manifest_io import read_json


ALLOWED_NOTICEABLE_ISSUE_TYPES = frozenset(
    {
        "palette_drift",
        "pptx_html_edge_mismatch",
    }
)
CANARY_METRIC_LIMITS = {
    "palette_drift": {
        "metric": "color_palette_drift",
        "maximum": 0.265,
        "minimum_ssim": 0.70,
    },
    "pptx_html_edge_mismatch": {
        "metric": "edge_difference_ratio",
        "maximum": 0.102,
        "minimum_ssim": 0.82,
    },
}


def evaluate_visual_quality_acceptance(
    *,
    project: Path,
    summary_path: Path,
    slides: Iterable[int],
) -> dict[str, Any]:
    """Return a fail-closed quality verdict for the final rendered slide set."""

    root = project.resolve()
    requested = sorted({int(value) for value in slides})
    issues: list[str] = []
    allowed_needs_polish: list[int] = []

    try:
        summary = read_json(summary_path.resolve())
    except (OSError, ValueError, TypeError) as exc:
        return _report(requested, [], [f"visual QA summary cannot be read: {exc}"])

    summary_project = summary.get("project")
    if not isinstance(summary_project, str) or Path(summary_project).resolve() != root:
        issues.append("visual QA summary project does not match the final project")
    if summary.get("slidesRequested") != requested:
        issues.append(f"visual QA summary slidesRequested must be {requested}")
    if _integer(summary.get("failed")) != 0:
        issues.append("visual QA summary contains failed slides")
    if _integer(summary.get("blockingIssues")) != 0:
        issues.append("visual QA summary contains blocking issues")

    rows = summary.get("slides")
    if not isinstance(rows, list):
        issues.append("visual QA summary slides must be an array")
        rows = []
    rows_by_slide = {
        row.get("slide"): row
        for row in rows
        if isinstance(row, dict) and isinstance(row.get("slide"), int)
    }

    for slide in requested:
        row = rows_by_slide.get(slide)
        if not isinstance(row, dict):
            issues.append(f"slide {slide}: missing final visual QA summary row")
            continue
        status = str(row.get("status", "")).lower()
        metrics_path = (
            root / "work" / f"slide{slide:02d}" / "visual_qa" / "visual_metrics.json"
        )
        try:
            metrics = read_json(metrics_path)
        except (OSError, ValueError, TypeError) as exc:
            issues.append(f"slide {slide}: visual_metrics.json cannot be read: {exc}")
            continue
        metric_status = str(
            metrics.get("overallStatus", metrics.get("status", ""))
        ).lower()
        if metric_status != status:
            issues.append(
                f"slide {slide}: summary status {status!r} does not match metrics {metric_status!r}"
            )
            continue
        metric_issues = metrics.get("issues")
        if not isinstance(metric_issues, list):
            issues.append(f"slide {slide}: metrics issues must be an array")
            continue
        blocking = [
            item
            for item in metric_issues
            if isinstance(item, dict)
            and str(item.get("severity", "")).lower() == "blocking"
        ]
        if status == "fail" or blocking:
            issues.append(f"slide {slide}: final visual QA contains a blocking failure")
            continue
        if status == "pass":
            continue
        if status != "needs_polish":
            issues.append(f"slide {slide}: invalid final visual QA status {status!r}")
            continue
        if not metric_issues:
            issues.append(
                f"slide {slide}: needs_polish is not backed by typed diagnostic issues"
            )
            continue
        disallowed: list[str] = []
        metric_rejections: list[str] = []
        for item in metric_issues:
            if not isinstance(item, dict):
                disallowed.append("malformed_issue")
                continue
            issue_type = str(item.get("type", "")).strip().lower()
            severity = str(item.get("severity", "")).strip().lower()
            if severity not in {"minor", "noticeable"}:
                disallowed.append(issue_type or "unknown")
            elif issue_type not in ALLOWED_NOTICEABLE_ISSUE_TYPES:
                disallowed.append(issue_type or "unknown")
            else:
                metric_issue = _canary_metric_issue(metrics, item, issue_type)
                if metric_issue:
                    metric_rejections.append(metric_issue)
        if disallowed:
            issues.append(
                f"slide {slide}: high-fidelity policy rejects issue types "
                + ", ".join(sorted(set(disallowed)))
            )
        elif metric_rejections:
            issues.extend(f"slide {slide}: {value}" for value in metric_rejections)
        else:
            allowed_needs_polish.append(slide)

    return _report(requested, allowed_needs_polish, issues)


def _integer(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return -1


def _canary_metric_issue(
    metrics: dict[str, Any],
    issue: dict[str, Any],
    issue_type: str,
) -> str | None:
    comparison_name = str(issue.get("comparison", "")).strip()
    comparisons = metrics.get("comparisons")
    if not comparison_name or not isinstance(comparisons, dict):
        return f"{issue_type} lacks comparison metrics required by the canary policy"
    comparison = comparisons.get(comparison_name)
    if not isinstance(comparison, dict):
        return f"{issue_type} comparison {comparison_name!r} is missing"
    limit = CANARY_METRIC_LIMITS[issue_type]
    metric_name = str(limit["metric"])
    metric_value = _float(comparison.get(metric_name))
    ssim_value = _float(comparison.get("approx_ssim"))
    if metric_value is None or ssim_value is None:
        return f"{issue_type} lacks {metric_name}/approx_ssim canary evidence"
    if metric_value > float(limit["maximum"]):
        return (
            f"{issue_type} exceeds the accepted canary ceiling: "
            f"{metric_name}={metric_value:.4f} > {float(limit['maximum']):.4f}"
        )
    if ssim_value < float(limit["minimum_ssim"]):
        return (
            f"{issue_type} falls below the accepted canary floor: "
            f"approx_ssim={ssim_value:.4f} < {float(limit['minimum_ssim']):.4f}"
        )
    return None


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _report(
    requested: list[int],
    allowed_needs_polish: list[int],
    issues: list[str],
) -> dict[str, Any]:
    return {
        "accepted": not issues,
        "slides": requested,
        "allowed_issue_types": sorted(ALLOWED_NOTICEABLE_ISSUE_TYPES),
        "allowed_needs_polish_slides": allowed_needs_polish,
        "issues": issues,
    }


__all__ = [
    "ALLOWED_NOTICEABLE_ISSUE_TYPES",
    "CANARY_METRIC_LIMITS",
    "evaluate_visual_quality_acceptance",
]
