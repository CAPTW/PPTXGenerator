"""Lossless parsing and fail-closed reconciliation for external visual QA evidence."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..identity import content_sha256
from .contracts import SCHEMA_VERSION, TIMEZONE, sha256_file, verify_report_hash


VALID_STATUSES = {"pass", "fail", "needs_polish", "missing"}
VALID_SEVERITIES = {"pass", "minor", "noticeable", "blocking"}
RESOLUTION_CATEGORIES = {
    "RESOLVED_FALSE_POSITIVE",
    "RESOLVED_METRIC_DELTA",
    "REPAIRED",
    "ACCEPTED_LIMITATION",
    "UNRESOLVED_BLOCKING",
}
SUPPORTED_EXPLICIT_VERSIONS = {"1.0.0"}
OBSERVED_UNVERSIONED_VERSION = "observed-unversioned-slide-visual-polish-qa-v1"


class ExternalVisualQAError(RuntimeError):
    """Stable fail-closed error for unsupported or incomplete external QA evidence."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(f"{code}: {message}")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExternalVisualQAError(
            "BLOCKED_EXTERNAL_VISUAL_QA_EVIDENCE_INSUFFICIENT",
            f"unreadable external QA JSON: {path}",
        ) from exc
    if not isinstance(payload, dict):
        raise ExternalVisualQAError(
            "BLOCKED_EXTERNAL_VISUAL_QA_OUTPUT_UNSUPPORTED",
            "external QA payload must be a JSON object",
        )
    return payload


def _read_stdout_json(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ExternalVisualQAError(
            "BLOCKED_EXTERNAL_VISUAL_QA_EVIDENCE_INSUFFICIENT",
            f"unreadable external QA stdout: {path}",
        ) from exc
    candidates = [text.strip()]
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        candidates.append(text[start : end + 1])
    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    raise ExternalVisualQAError(
        "BLOCKED_EXTERNAL_VISUAL_QA_OUTPUT_UNSUPPORTED",
        "stdout did not contain one supported JSON object",
    )


def _with_report_hash(payload: dict[str, Any]) -> dict[str, Any]:
    result = dict(payload)
    result.pop("report_hash", None)
    result["report_hash"] = content_sha256(result)
    return result


def verify_bound_report_hash(payload: Mapping[str, Any]) -> bool:
    candidate = dict(payload)
    expected = candidate.pop("report_hash", None)
    return isinstance(expected, str) and expected == content_sha256(candidate)


def _safe_reference(project_root: Path, path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(project_root.resolve()).as_posix()
    except ValueError as exc:
        raise ExternalVisualQAError(
            "BLOCKED_EXTERNAL_VISUAL_QA_EVIDENCE_INSUFFICIENT",
            f"external QA artifact escapes the isolated project: {resolved}",
        ) from exc


def _runtime_reference(project_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def _resolve_reference(project_root: Path, raw: Any) -> Path | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = project_root / candidate
    _safe_reference(project_root, candidate)
    return candidate.resolve()


def _normalized_counts(payload: Mapping[str, Any]) -> dict[str, int]:
    raw = payload.get("counts")
    if not isinstance(raw, Mapping):
        raw = {
            "pass": payload.get("passed", 0),
            "fail": payload.get("failed", 0),
            "needs_polish": payload.get("needsPolish", 0),
            "missing": payload.get("missing", 0),
        }
    counts: dict[str, int] = {}
    for status in ("fail", "needs_polish", "pass", "missing"):
        value = raw.get(status, 0)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ExternalVisualQAError(
                "BLOCKED_EXTERNAL_VISUAL_QA_CONSERVATION_FAILURE",
                f"invalid summary count for {status}",
            )
        counts[status] = value
    total = sum(counts.values())
    declared_total = payload.get("total")
    if declared_total is not None and declared_total != total:
        raise ExternalVisualQAError(
            "BLOCKED_EXTERNAL_VISUAL_QA_CONSERVATION_FAILURE",
            f"reported total {declared_total} does not equal count sum {total}",
        )
    return counts


def _validated_status(value: Any) -> str:
    if not isinstance(value, str) or value not in VALID_STATUSES:
        raise ExternalVisualQAError(
            "BLOCKED_EXTERNAL_VISUAL_QA_OUTPUT_UNSUPPORTED",
            f"STATUS is malformed or unsupported: {value!r}",
        )
    return value


def _validated_severity(value: Any, status: str) -> str:
    fallback = {"pass": "pass", "needs_polish": "noticeable", "fail": "blocking", "missing": "blocking"}[status]
    value = value or fallback
    if not isinstance(value, str) or value not in VALID_SEVERITIES:
        raise ExternalVisualQAError(
            "BLOCKED_EXTERNAL_VISUAL_QA_OUTPUT_UNSUPPORTED",
            f"severity is malformed or unsupported: {value!r}",
        )
    return value


def _metric_evidence(issue: Mapping[str, Any], metrics: Mapping[str, Any]) -> list[dict[str, Any]]:
    direct = issue.get("metric_evidence")
    if isinstance(direct, list) and direct:
        return [dict(row) for row in direct if isinstance(row, Mapping)]
    if issue.get("metric") is not None and issue.get("actual") is not None and issue.get("threshold") is not None:
        return [
            {
                "metric": issue.get("metric"),
                "actual": issue.get("actual"),
                "threshold": issue.get("threshold"),
                "signal": issue.get("signal") or "inline_metric",
                "comparison": issue.get("comparison"),
            }
        ]
    comparison_name = issue.get("comparison")
    comparisons = metrics.get("comparisons", {})
    comparison = comparisons.get(comparison_name, {}) if isinstance(comparisons, Mapping) else {}
    signals = comparison.get("metricSignals", {}).get("knownBadSignals", []) if isinstance(comparison, Mapping) else []
    evidence: list[dict[str, Any]] = []
    for signal in signals if isinstance(signals, list) else []:
        if not isinstance(signal, Mapping):
            continue
        evidence.append(
            {
                "metric": signal.get("metric"),
                "actual": signal.get("value"),
                "threshold": signal.get("threshold"),
                "signal": signal.get("signal"),
                "comparison": comparison_name,
            }
        )
    if evidence:
        return evidence
    threshold_names = {"pixel_difference_ratio": "pixel", "edge_difference_ratio": "edge", "approx_ssim": "ssim"}
    thresholds = metrics.get("thresholds", {}) if isinstance(metrics.get("thresholds"), Mapping) else {}
    if isinstance(comparison, Mapping):
        for metric, threshold_name in threshold_names.items():
            actual, threshold = comparison.get(metric), thresholds.get(threshold_name)
            if isinstance(actual, (int, float)) and isinstance(threshold, (int, float)):
                evidence.append(
                    {
                        "metric": metric,
                        "actual": actual,
                        "threshold": threshold,
                        "signal": "observed_metric",
                        "comparison": comparison_name,
                    }
                )
    return evidence


def _rule_record(
    issue: Mapping[str, Any],
    metrics: Mapping[str, Any],
    *,
    slide: int,
    index: int,
    status: str,
) -> dict[str, Any]:
    issue_id = issue.get("id")
    source_rule_id = issue.get("rule_id") or "not_exposed"
    issue_type = str(issue.get("type") or "other")
    return {
        "source_issue_id": str(issue_id or f"slide-{slide:03d}-issue-{index:03d}"),
        "source_rule_id": str(source_rule_id),
        "source_issue_index": index,
        "source_type": issue_type,
        "source_severity": _validated_severity(issue.get("severity"), status),
        "source_comparison": issue.get("comparison"),
        "source_observed": issue.get("observed"),
        "source_expected": issue.get("expected"),
        "source_message": issue.get("message") or issue.get("observed"),
        "source_region": issue.get("region"),
        "source_target_file": issue.get("targetFile"),
        "metric_evidence": _metric_evidence(issue, metrics),
        "metric_signal_context": (
            metrics.get("comparisons", {})
            .get(issue.get("comparison"), {})
            .get("metricSignals", {})
            if isinstance(metrics.get("comparisons"), Mapping)
            else {}
        ),
        "source_raw_fragment_hash": content_sha256(dict(issue)),
    }


def _tool_hashes(source_tool_root: Path | None) -> dict[str, str]:
    if source_tool_root is None:
        return {}
    files = {
        "skill": source_tool_root / "SKILL.md",
        "summary_generator": source_tool_root / "scripts" / "generate_visual_qa_summary.js",
        "enforcer": source_tool_root / "scripts" / "enforce_visual_qa.js",
    }
    return {name: sha256_file(path) for name, path in files.items() if path.is_file()}


def parse_external_visual_qa(
    summary_path: str | Path | None,
    *,
    project_root: str | Path,
    stdout_path: str | Path | None = None,
    stderr_path: str | Path | None = None,
    source_tool_root: str | Path | None = None,
    source_command: Sequence[str] = (),
    created_at: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Parse the observed external output without dropping slide or rule evidence."""

    project = Path(project_root).resolve()
    summary = Path(summary_path).resolve() if summary_path is not None else None
    stdout = Path(stdout_path).resolve() if stdout_path is not None else None
    stderr = Path(stderr_path).resolve() if stderr_path is not None else None
    if summary is not None and summary.is_file():
        payload = _read_json(summary)
        source_channel = "json_report"
        source_hash = sha256_file(summary)
        source_reference = _safe_reference(project, summary)
    elif stdout is not None and stdout.is_file():
        payload = _read_stdout_json(stdout)
        source_channel = "stdout_json"
        source_hash = sha256_file(stdout)
        source_reference = _safe_reference(project, stdout)
    else:
        raise ExternalVisualQAError(
            "BLOCKED_EXTERNAL_VISUAL_QA_EVIDENCE_INSUFFICIENT",
            "fresh external QA summary or stdout JSON is required",
        )

    explicit_version = payload.get("schema_version") or payload.get("schemaVersion") or payload.get("version")
    if explicit_version is not None and str(explicit_version) not in SUPPORTED_EXPLICIT_VERSIONS:
        raise ExternalVisualQAError(
            "BLOCKED_EXTERNAL_VISUAL_QA_OUTPUT_UNSUPPORTED",
            f"unsupported external output version: {explicit_version}",
        )
    output_version = str(explicit_version or OBSERVED_UNVERSIONED_VERSION)
    counts = _normalized_counts(payload)
    reported_total = sum(counts.values())
    reported_nonpass = counts["fail"] + counts["needs_polish"] + counts["missing"]

    if isinstance(payload.get("results"), list):
        rows = payload["results"]
        detected_format = "rule_level_records"
    elif "slides" in payload:
        rows = payload.get("slides")
        if not isinstance(rows, list):
            raise ExternalVisualQAError(
                "BLOCKED_EXTERNAL_VISUAL_QA_OUTPUT_UNSUPPORTED",
                "slides must be an array",
            )
        if reported_total and not rows:
            raise ExternalVisualQAError(
                "BLOCKED_EXTERNAL_VISUAL_QA_CONSERVATION_FAILURE",
                "nonzero summary has an explicitly empty slides array",
            )
        detected_format = "slide_verdict_with_rule_records"
    else:
        rows = None
        detected_format = "summary_only"

    source_results: list[dict[str, Any]] = []
    inventory: list[dict[str, Any]] = []
    if summary is not None and summary.is_file():
        inventory.append({"artifact_type": "summary", "path": source_reference, "sha256": source_hash})
    seen_results: set[str] = set()
    seen_rules: set[tuple[int, str]] = set()
    official_rule_ids_exposed = False
    parsed_rule_count = 0

    if rows is None:
        source_results.append(
            {
                "source_result_id": "extqa-summary-nonpass",
                "source_result_index": 0,
                "source_granularity": "summary",
                "source_tool": "slide-visual-polish-qa",
                "source_command": list(source_command),
                "source_output_version": output_version,
                "source_report_reference": source_reference,
                "source_report_sha256": source_hash,
                "source_slide_id": None,
                "source_rule_id": "not_exposed",
                "source_status": "fail" if reported_nonpass else "pass",
                "source_severity": "blocking" if reported_nonpass else "pass",
                "source_metric": None,
                "source_actual": counts,
                "source_threshold": None,
                "source_message": "Only aggregate summary counts were exposed.",
                "source_raw_fragment_hash": content_sha256({"counts": counts}),
                "covered_result_count": reported_total,
                "parse_status": "PASS",
                "canonicalization_status": "UNRESOLVED_BLOCKING" if reported_nonpass else "MAPPED",
                "rule_records": [],
                "evidence_files": [],
                "critical_issue_signals": [],
            }
        )
    else:
        for index, raw_row in enumerate(rows):
            if not isinstance(raw_row, Mapping):
                raise ExternalVisualQAError(
                    "BLOCKED_EXTERNAL_VISUAL_QA_OUTPUT_UNSUPPORTED",
                    f"result {index} is not an object",
                )
            slide_raw = raw_row.get("slide") or raw_row.get("slide_id")
            try:
                slide = int(str(slide_raw).removeprefix("slide-").removeprefix("slide"))
            except (TypeError, ValueError) as exc:
                raise ExternalVisualQAError(
                    "BLOCKED_EXTERNAL_VISUAL_QA_OUTPUT_UNSUPPORTED",
                    f"result {index} has no valid slide identity",
                ) from exc
            status = _validated_status(raw_row.get("status"))
            severity = _validated_severity(raw_row.get("severity"), status)
            if detected_format == "rule_level_records":
                record_identity = raw_row.get("id") or raw_row.get("source_result_id") or content_sha256(dict(raw_row))
                result_key = f"slide-{slide:03d}:rule:{record_identity}"
                source_result_id = f"extqa-rule-slide-{slide:03d}-{content_sha256({'identity': str(record_identity), 'raw': dict(raw_row)})[:12]}"
            else:
                result_key = f"slide-{slide:03d}"
                source_result_id = f"extqa-slide-{slide:03d}-{status}"
            if result_key in seen_results:
                raise ExternalVisualQAError(
                    "BLOCKED_EXTERNAL_VISUAL_QA_DUPLICATE_RESULT",
                    f"DUPLICATE source result for {result_key}",
                )
            seen_results.add(result_key)

            metrics_path = _resolve_reference(project, raw_row.get("metricsPath"))
            fixes_path = _resolve_reference(project, raw_row.get("fixesPath"))
            metrics: dict[str, Any] = {}
            fixes: dict[str, Any] = {}
            evidence_files: list[dict[str, Any]] = []
            for artifact_type, path in (("visual_metrics", metrics_path), ("visual_polish_fixes", fixes_path)):
                if path is None:
                    continue
                if not path.is_file():
                    raise ExternalVisualQAError(
                        "BLOCKED_EXTERNAL_VISUAL_QA_EVIDENCE_INSUFFICIENT",
                        f"referenced {artifact_type} is missing for slide {slide}",
                    )
                value = _read_json(path)
                if artifact_type == "visual_metrics":
                    metrics = value
                else:
                    fixes = value
                record = {"artifact_type": artifact_type, "path": _safe_reference(project, path), "sha256": sha256_file(path)}
                evidence_files.append(record)
                inventory.append(record)

            if detected_format == "rule_level_records":
                issues = [raw_row]
                source_rule_id = raw_row.get("rule_id") or "not_exposed"
                granularity = "rule_record"
            else:
                issues_value = fixes.get("issues") if isinstance(fixes.get("issues"), list) else metrics.get("issues")
                if not isinstance(issues_value, list):
                    issues_value = raw_row.get("issues", [])
                issues = issues_value if isinstance(issues_value, list) else []
                source_rule_id = "not_exposed"
                granularity = "slide_verdict"

            rule_records: list[dict[str, Any]] = []
            for rule_index, issue in enumerate(issues, 1):
                if not isinstance(issue, Mapping):
                    raise ExternalVisualQAError(
                        "BLOCKED_EXTERNAL_VISUAL_QA_OUTPUT_UNSUPPORTED",
                        f"slide {slide} issue {rule_index} is not an object",
                    )
                issue_index = index + 1 if detected_format == "rule_level_records" else rule_index
                rule = _rule_record(issue, metrics, slide=slide, index=issue_index, status=status)
                duplicate_key = (slide, rule["source_issue_id"])
                if duplicate_key in seen_rules:
                    raise ExternalVisualQAError(
                        "BLOCKED_EXTERNAL_VISUAL_QA_DUPLICATE_RESULT",
                        f"DUPLICATE rule record {rule['source_issue_id']} on slide {slide}",
                    )
                seen_rules.add(duplicate_key)
                official_rule_ids_exposed = official_rule_ids_exposed or rule["source_rule_id"] != "not_exposed"
                rule_records.append(rule)
            parsed_rule_count += len(rule_records)

            render_hashes = metrics.get("hashes", {}) if isinstance(metrics.get("hashes"), Mapping) else {}
            for key, filename in (("source", "source.png"), ("pptx_raster", "pptx_raster.png"), ("html_screenshot", "html_screenshot.png")):
                if metrics_path is None:
                    continue
                artifact_path = metrics_path.parent / filename
                if artifact_path.is_file():
                    actual = sha256_file(artifact_path)
                    expected = render_hashes.get(key)
                    if expected and expected != actual:
                        raise ExternalVisualQAError(
                            "BLOCKED_EXTERNAL_VISUAL_QA_EVIDENCE_INSUFFICIENT",
                            f"current slide {slide} {key} hash does not match visual metrics",
                        )
                    record = {"artifact_type": key, "path": _safe_reference(project, artifact_path), "sha256": actual}
                    evidence_files.append(record)
                    inventory.append(record)

            message_parts = [str(rule.get("source_message")) for rule in rule_records if rule.get("source_message")]
            source_results.append(
                {
                    "source_result_id": source_result_id,
                    "source_result_index": index,
                    "source_granularity": granularity,
                    "source_tool": "slide-visual-polish-qa",
                    "source_command": list(source_command),
                    "source_output_version": output_version,
                    "source_report_reference": source_reference,
                    "source_report_sha256": source_hash,
                    "source_slide_id": f"slide-{slide:03d}",
                    "source_rule_id": str(source_rule_id),
                    "source_status": status,
                    "source_severity": severity,
                    "source_metric": [row.get("metric") for rule in rule_records for row in rule.get("metric_evidence", [])],
                    "source_actual": [row.get("actual") for rule in rule_records for row in rule.get("metric_evidence", [])],
                    "source_threshold": [row.get("threshold") for rule in rule_records for row in rule.get("metric_evidence", [])],
                    "source_message": "; ".join(message_parts) or f"External slide verdict: {status}/{severity}",
                    "source_raw_fragment_hash": content_sha256(dict(raw_row)),
                    "covered_result_count": 1,
                    "parse_status": "PASS",
                    "canonicalization_status": "MAPPED",
                    "rule_records": rule_records,
                    "evidence_files": evidence_files,
                    "critical_issue_signals": metrics.get("issueSignals", []) if isinstance(metrics.get("issueSignals"), list) else [],
                }
            )

        parsed_counts = {status: sum(row["source_status"] == status for row in source_results) for status in VALID_STATUSES}
        if len(source_results) != reported_total or any(parsed_counts[status] != counts[status] for status in VALID_STATUSES):
            raise ExternalVisualQAError(
                "BLOCKED_EXTERNAL_VISUAL_QA_CONSERVATION_FAILURE",
                f"parsed source result counts {parsed_counts} do not conserve reported counts {counts}",
            )

    source_payload = _with_report_hash(
        {
            "schema_name": "external_visual_qa_source_results",
            "schema_version": SCHEMA_VERSION,
            "source_tool": "slide-visual-polish-qa",
            "source_command": list(source_command),
            "source_output_version": output_version,
            "source_summary_reference": source_reference,
            "source_summary_sha256": source_hash,
            "reported_counts": counts,
            "reported_total": reported_total,
            "reported_nonpass_count": reported_nonpass,
            "parsed_source_result_count": len(source_results) if rows is not None else 0,
            "parsed_summary_record_count": 1 if rows is None else 0,
            "parsed_rule_record_count": parsed_rule_count,
            "duplicate_source_result_count": 0,
            "unsupported_source_result_count": 0,
            "source_results": source_results,
            "conservation": {
                "reported_total_equation": "PASS",
                "parsed_total_matches_reported": "PASS" if rows is not None and len(source_results) == reported_total else "NOT_APPLICABLE",
                "summary_covered_count_matches_reported": "PASS" if rows is None and source_results[0]["covered_result_count"] == reported_total else "NOT_APPLICABLE",
            },
            "status": "BLOCKED" if rows is None and reported_nonpass else "PASS",
            "created_at": created_at,
            "timezone": TIMEZONE,
        }
    )

    known_top_level = {
        "createdAt", "project", "slidesRequested", "counts", "passed", "needsPolish", "failed", "missing",
        "total", "issueSeverityCounts", "blockingIssues", "noticeableIssues", "minorIssues", "commonIssueTypes",
        "commonFixStrategies", "cropRecommendations", "worstSlides", "recommendedNextRepairWaves", "slides",
        "results", "schema_version", "schemaVersion", "version",
    }
    tool_root = Path(source_tool_root).resolve() if source_tool_root is not None else None
    audit = _with_report_hash(
        {
            "schema_name": "external_visual_qa_output_contract_audit",
            "schema_version": SCHEMA_VERSION,
            "tool_identity": "slide-visual-polish-qa",
            "source_command": list(source_command),
            "tool_hashes": _tool_hashes(tool_root),
            "source_channel": source_channel,
            "stdout": {"path": _runtime_reference(project, stdout), "sha256": sha256_file(stdout)} if stdout and stdout.is_file() else None,
            "stderr": {"path": _runtime_reference(project, stderr), "sha256": sha256_file(stderr)} if stderr and stderr.is_file() else None,
            "source_output_inventory": inventory,
            "detected_output_format": detected_format,
            "detected_output_version": output_version,
            "summary_location": source_reference,
            "result_array_paths": ["$.results[]"] if detected_format == "rule_level_records" else (["$.slides[]"] if rows is not None else []),
            "slide_level_paths": ["$.slides[].slide", "$.slides[].status", "$.slides[].severity"] if rows is not None else [],
            "rule_level_paths": ["visual_metrics.json.issues[]", "visual_polish_fixes.json.issues[]"] if detected_format == "slide_verdict_with_rule_records" else (["$.results[]"] if detected_format == "rule_level_records" else []),
            "metric_paths": ["visual_metrics.json.comparisons.*.metricSignals.knownBadSignals[]"],
            "reason_message_paths": ["issues[].observed", "issues[].expected", "issues[].recommendedFix"],
            "official_rule_ids_exposed": official_rule_ids_exposed,
            "slide_ids_exposed": bool(rows is not None),
            "severity_exposed": bool(rows is not None),
            "unknown_fields": sorted(set(payload) - known_top_level),
            "parser_verdict": "BLOCKED" if source_payload["status"] == "BLOCKED" else "PASS",
            "created_at": created_at,
            "timezone": TIMEZONE,
        }
    )
    return audit, source_payload


def validate_resolution_record(record: Mapping[str, Any]) -> dict[str, str]:
    category = record.get("resolution_category")
    if category not in RESOLUTION_CATEGORIES:
        raise ExternalVisualQAError(
            "BLOCKED_EXTERNAL_VISUAL_QA_UNRESOLVED",
            f"unsupported resolution category: {category}",
        )
    if category == "UNRESOLVED_BLOCKING":
        return {"status": "BLOCKED"}
    if record.get("resolution_evidence_fresh") is not True:
        raise ExternalVisualQAError("BLOCKED_EXTERNAL_VISUAL_QA_UNRESOLVED", "resolution evidence is stale")
    for field in ("current_pptx_sha256", "current_html_sha256", "source_report_hash"):
        value = record.get(field)
        if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
            raise ExternalVisualQAError("BLOCKED_EXTERNAL_VISUAL_QA_UNRESOLVED", f"{field} must bind current output evidence")
    if not record.get("canonical_rule_id"):
        raise ExternalVisualQAError("BLOCKED_EXTERNAL_VISUAL_QA_UNRESOLVED", "an exact canonical rule ID is required")
    evidence = record.get("independent_evidence")
    if not isinstance(evidence, Mapping) or evidence.get("rule_specific") is not True or evidence.get("current_output_bound") is not True:
        raise ExternalVisualQAError(
            "BLOCKED_EXTERNAL_VISUAL_QA_UNRESOLVED",
            "generic Composite PASS is not rule-specific independent evidence",
        )
    if category == "RESOLVED_METRIC_DELTA":
        metrics = record.get("metric_evidence")
        if not isinstance(metrics, list) or not metrics:
            raise ExternalVisualQAError("BLOCKED_EXTERNAL_VISUAL_QA_UNRESOLVED", "metric delta requires exact metrics")
        if any(not isinstance(row, Mapping) or row.get("metric") is None or row.get("actual") is None or row.get("threshold") is None for row in metrics):
            raise ExternalVisualQAError("BLOCKED_EXTERNAL_VISUAL_QA_UNRESOLVED", "metric evidence lacks actual value or threshold")
    if category == "ACCEPTED_LIMITATION" and not record.get("decision_log_id"):
        raise ExternalVisualQAError("BLOCKED_EXTERNAL_VISUAL_QA_UNRESOLVED", "accepted limitation requires a Decision Log ID")
    if category == "REPAIRED":
        if not record.get("upstream_before_sha256") or not record.get("upstream_after_sha256"):
            raise ExternalVisualQAError("BLOCKED_EXTERNAL_VISUAL_QA_UNRESOLVED", "repaired finding requires before/after hashes")
    return {"status": "PASS"}


def _load_dimension_reports(qa_dir: Path) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    paths = {
        "semantic": qa_dir / "semantic_qa_report.json",
        "editability": qa_dir / "editability_qa_report.json",
        "package_render": qa_dir / "package_render_qa_report.json",
        "visual": qa_dir / "visual_qa_report.json",
        "raster_crop": qa_dir / "raster_crop_qa_report.json",
        "parity": qa_dir / "cross_output_parity_qa_report.json",
    }
    reports: dict[str, dict[str, Any]] = {}
    refs: list[dict[str, Any]] = []
    for name, path in paths.items():
        if not path.is_file():
            raise ExternalVisualQAError(
                "BLOCKED_EXTERNAL_VISUAL_QA_EVIDENCE_INSUFFICIENT",
                f"missing independent {name} report",
            )
        reports[name] = _read_json(path)
        if not verify_report_hash(reports[name]):
            raise ExternalVisualQAError(
                "BLOCKED_EXTERNAL_VISUAL_QA_EVIDENCE_INSUFFICIENT",
                f"independent {name} report hash mismatch",
            )
        refs.append({"rule": name, "path": path.name, "sha256": sha256_file(path), "status": reports[name].get("status")})
    return reports, refs


def _independent_evidence_passes(reports: Mapping[str, Mapping[str, Any]]) -> bool:
    visual = reports["visual"].get("checks", {})
    review = visual.get("model_assisted_review", {}) if isinstance(visual.get("model_assisted_review"), Mapping) else {}
    return all(report.get("status") == "PASS" for report in reports.values()) and all(
        (
            reports["semantic"].get("checks", {}).get("pptx_fidelity") == 1.0,
            reports["semantic"].get("checks", {}).get("html_fidelity") == 1.0,
            reports["editability"].get("checks", {}).get("native_requirement_coverage") == 1.0,
            reports["editability"].get("checks", {}).get("semantic_raster_violation_count") == 0,
            reports["package_render"].get("checks", {}).get("render_count") == 6,
            reports["raster_crop"].get("checks", {}).get("full_slide_raster_count") == 0,
            reports["raster_crop"].get("checks", {}).get("screenshot_slide_count") == 0,
            reports["parity"].get("checks", {}).get("parity_fidelity") == 1.0,
            visual.get("off_canvas_count") == 0,
            visual.get("severe_overlap_count") == 0,
            visual.get("title_safe_area_failures") == [],
            visual.get("footer_citation_safe_area_failures") == [],
            review.get("hierarchy") == "PASS",
            review.get("legibility") == "PASS",
            review.get("visual_target_intent_fidelity") == "PASS",
        )
    )


def _controlled_expected_fault_evidence_passes(
    reports: Mapping[str, Mapping[str, Any]],
    material_findings: Sequence[Mapping[str, Any]],
    expected_finding_ids: set[str],
) -> bool:
    """Allow only the declared off-canvas fault to scope otherwise clean evidence.

    This does not turn the fault into a pass.  It permits external metric-only
    findings on unaffected slides to resolve while the one affected slide stays
    NEEDS_REPAIR.  Any undeclared, non-repairable, or additional material
    finding keeps reconciliation BLOCKED.
    """

    if not expected_finding_ids or not material_findings:
        return False
    material_ids = {str(row.get("finding_id")) for row in material_findings}
    if material_ids != expected_finding_ids:
        return False
    if any(
        row.get("severity") not in {"error", "severe"}
        or row.get("release_blocking") is not True
        or row.get("repairable") is not True
        or row.get("resolved") is True
        or row.get("rule_id") != "P6-VIS-TEXT-OFF-CANVAS-001"
        for row in material_findings
    ):
        return False
    if any(report.get("status") != "PASS" for name, report in reports.items() if name != "visual"):
        return False
    visual_report = reports["visual"]
    visual = visual_report.get("checks", {})
    review = visual.get("model_assisted_review", {}) if isinstance(visual.get("model_assisted_review"), Mapping) else {}
    return all(
        (
            visual_report.get("status") == "NEEDS_REPAIR",
            visual.get("off_canvas_count") == len(material_findings),
            visual.get("title_safe_area_failures") == [],
            visual.get("footer_citation_safe_area_failures") == [],
            visual.get("severe_overlap_count") == 0,
            reports["semantic"].get("checks", {}).get("pptx_fidelity") == 1.0,
            reports["semantic"].get("checks", {}).get("html_fidelity") == 1.0,
            reports["editability"].get("checks", {}).get("native_requirement_coverage") == 1.0,
            reports["editability"].get("checks", {}).get("semantic_raster_violation_count") == 0,
            reports["package_render"].get("checks", {}).get("render_count") == 6,
            reports["raster_crop"].get("checks", {}).get("full_slide_raster_count") == 0,
            reports["raster_crop"].get("checks", {}).get("screenshot_slide_count") == 0,
            reports["parity"].get("checks", {}).get("parity_fidelity") == 1.0,
            review.get("hierarchy") == "PASS",
            review.get("legibility") == "PASS",
            review.get("visual_target_intent_fidelity") == "PASS",
        )
    )


def _current_outputs_bound(
    reports: Mapping[str, Mapping[str, Any]],
    current_pptx_sha256: str,
    current_html_sha256: str,
) -> bool:
    expected = {"active-pptx": current_pptx_sha256, "active-html": current_html_sha256}
    for report in reports.values():
        refs = report.get("source_artifacts")
        if not isinstance(refs, list):
            return False
        bound = {
            str(row.get("artifact_id")): row.get("sha256")
            for row in refs
            if isinstance(row, Mapping) and row.get("artifact_id") in expected
        }
        if bound != expected:
            return False
    return True


def _finding_id(source: Mapping[str, Any]) -> str:
    slide = str(source.get("source_slide_id") or "SUMMARY").upper().replace("-", "_")
    status = str(source.get("source_status") or "UNKNOWN").upper()
    if source.get("source_granularity") == "rule_record":
        rule = re.sub(r"[^A-Z0-9]+", "_", str(source.get("source_rule_id") or "UNSPECIFIED").upper()).strip("_")
        if not rule or rule == "NOT_EXPOSED":
            rule = "UNSPECIFIED"
        identity = content_sha256(str(source.get("source_result_id")))[:10].upper()
        return f"EXT_VISUAL_QA_{slide}_RULE_{rule}_{identity}_{status}"
    return f"EXT_VISUAL_QA_{slide}_{status}"


def build_external_visual_qa_reconciliation(
    source_results: Mapping[str, Any],
    composite_qa_dir: str | Path,
    *,
    project_root: str | Path,
    current_pptx_sha256: str,
    current_html_sha256: str,
    created_at: str,
    expected_finding_ids: Sequence[str] = (),
) -> dict[str, Any]:
    """Map every external non-pass verdict to a traceable canonical finding."""

    for label, value in (("current PPTX", current_pptx_sha256), ("current HTML", current_html_sha256)):
        if re.fullmatch(r"[0-9a-f]{64}", value or "") is None:
            raise ExternalVisualQAError(
                "BLOCKED_EXTERNAL_VISUAL_QA_EVIDENCE_INSUFFICIENT",
                f"{label} hash is required",
            )
    project = Path(project_root).resolve()
    qa_dir = Path(composite_qa_dir).resolve()
    reports, evidence_refs = _load_dimension_reports(qa_dir)
    source_hash_valid = verify_bound_report_hash(source_results)
    counts = dict(source_results.get("reported_counts", {}))
    reported_nonpass = int(source_results.get("reported_nonpass_count", 0) or 0)
    expected = set(expected_finding_ids)
    material = [
        finding
        for finding in reports["visual"].get("findings", [])
        if finding.get("severity") in {"severe", "error"} or finding.get("release_blocking") is True
    ]
    current_outputs_bound = _current_outputs_bound(reports, current_pptx_sha256, current_html_sha256)
    independent_pass = _independent_evidence_passes(reports) and current_outputs_bound
    controlled_expected_fault = (
        _controlled_expected_fault_evidence_passes(reports, material, expected)
        and current_outputs_bound
    )
    findings: list[dict[str, Any]] = []
    mapped_covered = 0
    resolved_covered = 0
    unresolved_covered = 0
    repairable_unresolved = True

    rows = source_results.get("source_results", []) if source_hash_valid else []
    for source in rows if isinstance(rows, list) else []:
        if not isinstance(source, Mapping) or source.get("source_status") == "pass":
            continue
        covered = int(source.get("covered_result_count", 0) or 0)
        mapped_covered += covered
        evidence_files = source.get("evidence_files", [])
        evidence_types = {
            row.get("artifact_type")
            for row in evidence_files
            if isinstance(row, Mapping)
        } if isinstance(evidence_files, list) else set()
        source_evidence_fresh = {"pptx_raster", "html_screenshot"}.issubset(evidence_types)
        for evidence_file in evidence_files if isinstance(evidence_files, list) else []:
            if not isinstance(evidence_file, Mapping):
                source_evidence_fresh = False
                continue
            reference = evidence_file.get("path")
            expected_hash = evidence_file.get("sha256")
            if not isinstance(reference, str) or not isinstance(expected_hash, str):
                source_evidence_fresh = False
                continue
            current_path = (project / reference).resolve()
            try:
                current_path.relative_to(project)
            except ValueError:
                source_evidence_fresh = False
                continue
            if not current_path.is_file() or sha256_file(current_path) != expected_hash:
                source_evidence_fresh = False
        slide_material = [row for row in material if row.get("slide_id") in {None, source.get("source_slide_id")}]
        rule_resolutions: list[dict[str, Any]] = []
        critical_signals = source.get("critical_issue_signals", [])
        rules = source.get("rule_records", [])
        if not isinstance(rules, list) or not rules or source.get("source_granularity") == "summary":
            resolved = False
        else:
            scoped_independent_pass = independent_pass or (controlled_expected_fault and not slide_material)
            resolved = scoped_independent_pass and source_evidence_fresh and not critical_signals and not slide_material
            for rule in rules:
                metric_evidence = rule.get("metric_evidence", []) if isinstance(rule, Mapping) else []
                signal_context = rule.get("metric_signal_context", {}) if isinstance(rule, Mapping) else {}
                explicit_blocking = isinstance(signal_context, Mapping) and signal_context.get("explicitBlockingContext") is True
                record = {
                    "resolution_category": "RESOLVED_METRIC_DELTA" if resolved and metric_evidence and not explicit_blocking else "UNRESOLVED_BLOCKING",
                    "canonical_rule_id": f"EXT-VIS-{str(rule.get('source_type', 'UNKNOWN')).upper().replace('_', '-')}",
                    "current_pptx_sha256": current_pptx_sha256,
                    "current_html_sha256": current_html_sha256,
                    "source_report_hash": source.get("source_report_sha256"),
                    "independent_evidence": {
                        "rule_specific": bool(metric_evidence),
                        "current_output_bound": source_evidence_fresh and current_outputs_bound,
                        "semantic_fidelity": reports["semantic"].get("checks", {}).get("pptx_fidelity"),
                        "html_fidelity": reports["semantic"].get("checks", {}).get("html_fidelity"),
                        "native_editability": reports["editability"].get("checks", {}).get("native_requirement_coverage"),
                        "off_canvas_count": reports["visual"].get("checks", {}).get("off_canvas_count"),
                        "severe_overlap_count": reports["visual"].get("checks", {}).get("severe_overlap_count"),
                        "parity_fidelity": reports["parity"].get("checks", {}).get("parity_fidelity"),
                    },
                    "metric_evidence": metric_evidence,
                    "resolution_evidence_fresh": source_evidence_fresh and current_outputs_bound,
                }
                if record["resolution_category"] != "UNRESOLVED_BLOCKING":
                    try:
                        validate_resolution_record(record)
                    except ExternalVisualQAError:
                        record["resolution_category"] = "UNRESOLVED_BLOCKING"
                        resolved = False
                rule_resolutions.append(record)
            resolved = resolved and bool(rule_resolutions) and all(row["resolution_category"] != "UNRESOLVED_BLOCKING" for row in rule_resolutions)

        if resolved:
            resolution_category = "RESOLVED_METRIC_DELTA"
            final_status = "RESOLVED"
            release_blocking = False
            resolved_covered += covered
        else:
            resolution_category = "UNRESOLVED_BLOCKING"
            final_status = "NEEDS_REPAIR" if slide_material and all(row.get("finding_id") in expected and row.get("repairable") for row in slide_material) else "UNRESOLVED_BLOCKING"
            release_blocking = True
            unresolved_covered += covered
            repairable_unresolved = repairable_unresolved and final_status == "NEEDS_REPAIR" and bool(slide_material)

        hashes = {row.get("artifact_type"): row.get("sha256") for row in source.get("evidence_files", []) if isinstance(row, Mapping)}
        finding: dict[str, Any] = {
            "finding_id": _finding_id(source),
            "source_result_ids": [source.get("source_result_id")],
            "covered_result_count": covered,
            "source_tool": source.get("source_tool"),
            "source_command": source.get("source_command"),
            "source_report_hash": source.get("source_report_sha256"),
            "source_granularity": source.get("source_granularity"),
            "source_slide_id": source.get("source_slide_id"),
            "source_rule_id": source.get("source_rule_id"),
            "source_status": source.get("source_status"),
            "source_severity": source.get("source_severity"),
            "source_metric": source.get("source_metric"),
            "source_actual": source.get("source_actual"),
            "source_threshold": source.get("source_threshold"),
            "source_message": source.get("source_message"),
            "canonical_rule_id": f"EXT-VIS-QA-{str(source.get('source_slide_id') or 'SUMMARY').upper()}-VERDICT",
            "canonical_category": "external_visual_metric_delta" if resolved else "external_visual_unresolved",
            "canonical_severity": source.get("source_severity"),
            "current_pptx_sha256": current_pptx_sha256,
            "current_html_sha256": current_html_sha256,
            "current_render_screenshot_evidence_hashes": {
                "source": hashes.get("source"),
                "pptx_raster": hashes.get("pptx_raster"),
                "html_screenshot": hashes.get("html_screenshot"),
            },
            "resolution_category": resolution_category,
            "resolution_evidence": {
                "rule_resolutions": rule_resolutions,
                "independent_report_refs": evidence_refs,
                "critical_issue_signals": critical_signals,
                "material_visual_findings": [row.get("finding_id") for row in slide_material],
            },
            "decision_log_id": None,
            "release_blocking": release_blocking,
            "final_status": final_status,
        }
        finding["finding_hash"] = content_sha256(finding)
        findings.append(finding)

    coverage = mapped_covered / reported_nonpass if reported_nonpass else 1.0
    unsupported = int(source_results.get("unsupported_source_result_count", 0) or 0)
    duplicates = int(source_results.get("duplicate_source_result_count", 0) or 0)
    errors: list[str] = []
    if not source_hash_valid:
        errors.append("SOURCE_RESULTS_REPORT_HASH_MISMATCH")
    if coverage != 1.0:
        errors.append("NONPASS_MAPPING_COVERAGE_INCOMPLETE")
    if reported_nonpass and not findings:
        errors.append("NONPASS_WITH_ZERO_CANONICAL_FINDINGS")
    if unsupported:
        errors.append("UNSUPPORTED_SOURCE_RESULTS")
    if duplicates:
        errors.append("DUPLICATE_SOURCE_RESULTS")
    if not current_outputs_bound:
        errors.append("CURRENT_OUTPUT_REPORT_LINKAGE_MISMATCH")
    if errors or (unresolved_covered and not repairable_unresolved):
        status = "BLOCKED"
    elif unresolved_covered:
        status = "NEEDS_REPAIR"
    else:
        status = "PASS"

    resolution_counts = {category: 0 for category in RESOLUTION_CATEGORIES}
    for finding in findings:
        resolution_counts[finding["resolution_category"]] += int(finding["covered_result_count"])
    payload = {
        "schema_name": "external_visual_qa_reconciliation",
        "schema_version": SCHEMA_VERSION,
        "source_output_inventory": source_results.get("source_summary_reference"),
        "source_summary_sha256": source_results.get("source_summary_sha256"),
        "source_results_report_hash": source_results.get("report_hash"),
        "source_output_version": source_results.get("source_output_version"),
        "canonical_output_sha256": current_pptx_sha256,
        "current_pptx_sha256": current_pptx_sha256,
        "current_html_sha256": current_html_sha256,
        "external_counts": counts,
        "reported_counts": counts,
        "parsed_counts": {"source_results": source_results.get("parsed_source_result_count", 0), "rule_records": source_results.get("parsed_rule_record_count", 0)},
        "mapped_counts": {"canonical_findings": len(findings)},
        "covered_counts": {"reported_nonpass": reported_nonpass, "mapped_nonpass": mapped_covered, "resolved": resolved_covered, "unresolved": unresolved_covered},
        "reported_nonpass_count": reported_nonpass,
        "mapped_nonpass_covered_count": mapped_covered,
        "mapped_coverage_ratio": coverage,
        "canonical_finding_count": len(findings),
        "external_finding_count": len(findings),
        "findings": findings,
        "resolution_category_counts": resolution_counts,
        "resolved_covered_count": resolved_covered,
        "unresolved_covered_count": unresolved_covered,
        "unresolved_external_finding_count": unresolved_covered,
        "repaired_covered_count": resolution_counts["REPAIRED"],
        "accepted_limitation_covered_count": resolution_counts["ACCEPTED_LIMITATION"],
        "unsupported_count": unsupported,
        "duplicate_count": duplicates,
        "unsupported_informational_classification_count": 0,
        "conservation_checks": {
            "summary_total": sum(int(counts.get(name, 0) or 0) for name in VALID_STATUSES),
            "reported_nonpass": reported_nonpass,
            "mapped_nonpass": mapped_covered,
            "coverage_ratio": coverage,
        },
        "errors": errors,
        "warnings": [],
        "created_at": created_at,
        "timezone": TIMEZONE,
        "status": status,
    }
    return _with_report_hash(payload)


__all__ = [
    "ExternalVisualQAError",
    "build_external_visual_qa_reconciliation",
    "parse_external_visual_qa",
    "validate_resolution_record",
    "verify_bound_report_hash",
]
