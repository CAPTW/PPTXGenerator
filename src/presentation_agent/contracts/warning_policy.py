"""Central warning taxonomy and scoped allowlist evaluation for Contract V2."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


DEFAULT_FATAL_WARNING_CODES: frozenset[str] = frozenset(
    {
        "CONTRACT_NOT_FOUND",
        "CONTRACT_VERSION_UNSUPPORTED",
        "REQUIRED_SLOT_MISSING",
        "SLOT_CAPACITY_UNDECLARED",
        "SLOT_BINDING_MISSING",
        "SOURCE_BINDING_MISSING",
        "CITATION_BINDING_MISSING",
        "FULL_SLIDE_RASTER",
        "CONTENT_BEARING_RASTER",
        "BAKED_TEXT_RASTER",
        "SEMANTIC_ICON_RASTER",
        "SEMANTIC_TABLE_RASTER",
        "SEMANTIC_CHART_RASTER",
        "NON_EDITABLE_REQUIRED_TEXT",
        "TEXT_OVERFLOW",
        "PROTECTED_ZONE_INTRUSION",
        "DECORATION_OVER_PROTECTED_ZONE",
        "UNRECORDED_FALLBACK",
        "UNALLOWLISTED_FALLBACK",
        "COMPILER_ROUTE_NOT_EDITABLE_TEMPLATE",
        "STRUCTURAL_LEDGER_MISSING",
        "QA_REPORT_MISSING",
        "UNKNOWN_WARNING_CODE",
    }
)

DEFAULT_WARNING_TAXONOMY: dict[str, str] = {
    **{code: "fatal" for code in sorted(DEFAULT_FATAL_WARNING_CODES)},
}

_VALID_SEVERITIES = {"fatal", "warning", "allowed", "deprecated"}


@dataclass(frozen=True, slots=True)
class WarningPolicyFinding:
    code: str
    severity: str
    message: str
    object_id: str | None = None
    slot_id: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class WarningPolicyResult:
    passed: bool
    findings: tuple[WarningPolicyFinding, ...]

    @property
    def fatal_findings(self) -> tuple[WarningPolicyFinding, ...]:
        return tuple(finding for finding in self.findings if finding.severity == "fatal")

    @property
    def fatal_codes(self) -> tuple[str, ...]:
        return tuple(finding.code for finding in self.fatal_findings)

    @property
    def warning_codes(self) -> tuple[str, ...]:
        return tuple(finding.code for finding in self.findings if finding.severity == "warning")

    @property
    def allowed_codes(self) -> tuple[str, ...]:
        return tuple(finding.code for finding in self.findings if finding.severity == "allowed")

    def to_report(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "summary": {
                "total": len(self.findings),
                "fatal": len(self.fatal_findings),
                "warning": len(self.warning_codes),
                "allowed": len(self.allowed_codes),
            },
            "findings": [
                {
                    "code": finding.code,
                    "severity": finding.severity,
                    "message": finding.message,
                    **({"object_id": finding.object_id} if finding.object_id is not None else {}),
                    **({"slot_id": finding.slot_id} if finding.slot_id is not None else {}),
                    "details": finding.details,
                }
                for finding in self.findings
            ],
        }


def evaluate_warning_records(
    warnings: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    *,
    allowlist: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None = None,
    taxonomy: dict[str, str] | None = None,
) -> WarningPolicyResult:
    severity_map = taxonomy or DEFAULT_WARNING_TAXONOMY
    scoped_allowlist = [item for item in allowlist or [] if _allowlist_entry_is_scoped(item)]
    findings: list[WarningPolicyFinding] = []

    for warning in warnings:
        code = str(warning.get("code") or "").strip()
        object_id = _optional_str(warning.get("object_id") or warning.get("component_id"))
        slot_id = _optional_str(warning.get("slot_id"))
        if not code or code not in severity_map:
            findings.append(
                WarningPolicyFinding(
                    code="UNKNOWN_WARNING_CODE",
                    severity="fatal",
                    message=f"Unknown warning code is fatal: {code or '<missing>'}.",
                    object_id=object_id,
                    slot_id=slot_id,
                    details={"original_warning": dict(warning)},
                )
            )
            continue

        configured_severity = severity_map[code]
        if configured_severity not in _VALID_SEVERITIES:
            findings.append(
                WarningPolicyFinding(
                    code="UNKNOWN_WARNING_CODE",
                    severity="fatal",
                    message=f"Warning code {code} has invalid configured severity {configured_severity!r}.",
                    object_id=object_id,
                    slot_id=slot_id,
                    details={"original_warning": dict(warning)},
                )
            )
            continue

        if configured_severity == "fatal":
            if _is_allowlisted(warning, scoped_allowlist):
                findings.append(
                    WarningPolicyFinding(
                        code=code,
                        severity="allowed",
                        message=f"Fatal warning {code} was explicitly scoped and allowlisted.",
                        object_id=object_id,
                        slot_id=slot_id,
                        details={"warning": dict(warning)},
                    )
                )
                continue
            findings.append(
                WarningPolicyFinding(
                    code=code,
                    severity="fatal",
                    message=f"Warning {code} is fatal by default and is not scoped in the allowlist.",
                    object_id=object_id,
                    slot_id=slot_id,
                    details={"warning": dict(warning)},
                )
            )
            continue

        if configured_severity == "allowed":
            findings.append(
                WarningPolicyFinding(
                    code=code,
                    severity="allowed",
                    message=f"Warning {code} is allowed by taxonomy.",
                    object_id=object_id,
                    slot_id=slot_id,
                    details={"warning": dict(warning)},
                )
            )
            continue

        findings.append(
            WarningPolicyFinding(
                code=code,
                severity=configured_severity,
                message=f"Warning {code} classified as {configured_severity}.",
                object_id=object_id,
                slot_id=slot_id,
                details={"warning": dict(warning)},
            )
        )

    fatal_count = sum(1 for finding in findings if finding.severity == "fatal")
    return WarningPolicyResult(passed=fatal_count == 0, findings=tuple(findings))


def _allowlist_entry_is_scoped(entry: dict[str, Any]) -> bool:
    if not isinstance(entry, dict):
        return False
    if not str(entry.get("code") or "").strip():
        return False
    if not str(entry.get("reason") or "").strip():
        return False
    if not str(entry.get("owner") or "").strip():
        return False
    if not (str(entry.get("expiration") or "").strip() or str(entry.get("scope") or "").strip()):
        return False
    return bool(str(entry.get("object_id") or "").strip() or str(entry.get("slot_id") or "").strip())


def _is_allowlisted(warning: dict[str, Any], allowlist: list[dict[str, Any]]) -> bool:
    code = str(warning.get("code") or "").strip()
    object_id = str(warning.get("object_id") or warning.get("component_id") or "").strip()
    slot_id = str(warning.get("slot_id") or "").strip()
    for entry in allowlist:
        if str(entry.get("code") or "").strip() != code:
            continue
        entry_object_id = str(entry.get("object_id") or "").strip()
        entry_slot_id = str(entry.get("slot_id") or "").strip()
        if entry_object_id and object_id and entry_object_id == object_id:
            return True
        if entry_slot_id and slot_id and entry_slot_id == slot_id:
            return True
    return False


def _optional_str(value: Any) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None
