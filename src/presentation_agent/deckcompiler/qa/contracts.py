"""Hash-bound Phase 6 QA report and finding helpers."""

from __future__ import annotations

import hashlib
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from ..identity import content_sha256, stable_id
from ..manifest_io import write_json


SCHEMA_VERSION = "1.0.0"
DETECTOR_VERSION = "1.0.0"
TIMEZONE = "Asia/Seoul"


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artifact_ref(path: Path, logical_path: str, artifact_id: str | None = None) -> dict[str, str]:
    return {
        "artifact_id": artifact_id or stable_id("artifact", logical_path, sha256_file(path)),
        "path": logical_path.replace("\\", "/"),
        "sha256": sha256_file(path),
    }


def report_hash(payload: dict[str, Any]) -> str:
    unhashed = {key: value for key, value in payload.items() if key != "report_hash"}
    return content_sha256(unhashed)


def with_report_hash(payload: dict[str, Any]) -> dict[str, Any]:
    result = dict(payload)
    result["report_hash"] = report_hash(result)
    return result


def verify_report_hash(payload: dict[str, Any]) -> bool:
    return isinstance(payload.get("report_hash"), str) and payload["report_hash"] == report_hash(payload)


def make_finding(
    *,
    gate: str,
    category: str,
    severity: str,
    rule_id: str,
    message: str,
    evidence: dict[str, Any],
    owning_artifact: str,
    recommended_action: str,
    repairable: bool,
    release_blocking: bool,
    resolved: bool = False,
    slide_id: str | None = None,
    artifact_id: str | None = None,
    finding_id: str | None = None,
    detector: str = "DeckCompiler composite QA",
) -> dict[str, Any]:
    identity = finding_id or stable_id(
        "finding", gate, category, rule_id, slide_id, artifact_id, evidence, owning_artifact
    )
    payload: dict[str, Any] = {
        "finding_id": identity,
        "gate": gate,
        "category": category,
        "severity": severity,
        "slide_id": slide_id,
        "artifact_id": artifact_id,
        "rule_id": rule_id,
        "message": message,
        "evidence": evidence,
        "owning_artifact": owning_artifact,
        "recommended_action": recommended_action,
        "repairable": repairable,
        "release_blocking": release_blocking,
        "resolved": resolved,
        "detector": detector,
        "detector_version": DETECTOR_VERSION,
    }
    payload["finding_hash"] = content_sha256(payload)
    return payload


def severity_counts(findings: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(item["severity"] for item in findings)
    return {name: counts.get(name, 0) for name in ("info", "warning", "error", "severe")}


def verify_finding_hash(payload: dict[str, Any]) -> bool:
    expected = payload.get("finding_hash")
    unhashed = {key: value for key, value in payload.items() if key != "finding_hash"}
    return isinstance(expected, str) and expected == content_sha256(unhashed)


def gate_status(findings: list[dict[str, Any]], checks_pass: bool = True) -> str:
    if not checks_pass:
        return "BLOCKED"
    if any(item["severity"] in {"error", "severe"} for item in findings):
        return "NEEDS_REPAIR" if all(item["repairable"] for item in findings if item["severity"] in {"error", "severe"}) else "BLOCKED"
    if any(item["release_blocking"] for item in findings):
        return "NEEDS_REPAIR" if all(item["repairable"] for item in findings if item["release_blocking"]) else "BLOCKED"
    if any(item["repairable"] and not item["resolved"] for item in findings):
        return "NEEDS_REPAIR"
    return "PASS"


def implementation_provenance(commit: str) -> dict[str, Any]:
    return {
        "component": "presentation_agent.deckcompiler.qa",
        "deckcompiler_commit": commit,
        "detector_version": DETECTOR_VERSION,
        "acceptance_authority": "DeckCompiler independent composite gate",
        "external_outputs_may_self_accept": False,
    }


def build_report(
    *,
    schema_name: str,
    run_id: str,
    source_artifacts: list[dict[str, str]],
    producer: str,
    checks: dict[str, Any],
    findings: list[dict[str, Any]],
    created_at: str,
    commit: str,
    status: str | None = None,
) -> dict[str, Any]:
    payload = {
        "schema_name": schema_name,
        "schema_version": SCHEMA_VERSION,
        "report_id": stable_id("report", schema_name, run_id, source_artifacts),
        "run_id": run_id,
        "source_artifacts": source_artifacts,
        "producer": producer,
        "checks": checks,
        "findings": findings,
        "severity_counts": severity_counts(findings),
        "status": status or gate_status(findings),
        "created_at": created_at,
        "timezone": TIMEZONE,
        "implementation_provenance": implementation_provenance(commit),
    }
    return with_report_hash(payload)


def write_report(path: Path, payload: dict[str, Any]) -> Path:
    if not verify_report_hash(payload):
        raise ValueError(f"refusing to write report with invalid report_hash: {path}")
    return write_json(path, payload)


def now_iso() -> str:
    return datetime.now().astimezone().isoformat()


__all__ = [
    "DETECTOR_VERSION",
    "SCHEMA_VERSION",
    "TIMEZONE",
    "artifact_ref",
    "build_report",
    "gate_status",
    "implementation_provenance",
    "make_finding",
    "now_iso",
    "report_hash",
    "severity_counts",
    "sha256_file",
    "verify_report_hash",
    "verify_finding_hash",
    "with_report_hash",
    "write_report",
]
