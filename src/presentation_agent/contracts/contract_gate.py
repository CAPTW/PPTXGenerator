"""Executable Template Contract V2 gate functions."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from jsonschema.exceptions import ValidationError

from .template_contract_v2 import (
    contract_allowlist,
    is_supported_contract_version,
    load_template_contract,
    required_slot_ids,
    slot_contracts_by_id,
    validate_template_contract_payload,
)
from .warning_policy import DEFAULT_FATAL_WARNING_CODES, evaluate_warning_records


DEFAULT_REPORT_DIR = Path("analysis_runs/contract_v2_gate_latest")


@dataclass(frozen=True, slots=True)
class GateFinding:
    code: str
    severity: str
    stage: str
    message: str
    object_id: str | None = None
    slot_id: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_report(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "code": self.code,
            "severity": self.severity,
            "stage": self.stage,
            "message": self.message,
            "details": self.details,
        }
        if self.object_id is not None:
            payload["object_id"] = self.object_id
        if self.slot_id is not None:
            payload["slot_id"] = self.slot_id
        return payload


@dataclass(frozen=True, slots=True)
class GateResult:
    stage: str
    findings: tuple[GateFinding, ...] = ()

    @property
    def passed(self) -> bool:
        return not any(finding.severity == "fatal" for finding in self.findings)

    @property
    def fatal_findings(self) -> tuple[GateFinding, ...]:
        return tuple(finding for finding in self.findings if finding.severity == "fatal")

    @property
    def fatal_codes(self) -> tuple[str, ...]:
        return tuple(finding.code for finding in self.fatal_findings)

    @property
    def warning_codes(self) -> tuple[str, ...]:
        return tuple(finding.code for finding in self.findings if finding.severity == "warning")

    def extend(self, findings: Iterable[GateFinding]) -> GateResult:
        return GateResult(stage=self.stage, findings=(*self.findings, *tuple(findings)))

    def to_report(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "passed": self.passed,
            "summary": {
                "total": len(self.findings),
                "fatal": len(self.fatal_findings),
                "warning": len(self.warning_codes),
            },
            "fatal_codes": list(self.fatal_codes),
            "findings": [finding.to_report() for finding in self.findings],
        }


def contract_preflight_gate(
    contract: dict[str, Any] | str | Path | None,
    *,
    slide_blueprint: dict[str, Any] | None = None,
) -> GateResult:
    resolved, findings = _resolve_contract(contract, stage="preflight")
    if resolved is None:
        return GateResult(stage="preflight", findings=tuple(findings))

    slot_contracts = slot_contracts_by_id(resolved)
    for slot_id in required_slot_ids(resolved):
        slot = slot_contracts.get(slot_id)
        if slot is None:
            findings.append(_finding("REQUIRED_SLOT_MISSING", "preflight", f"Required slot {slot_id!r} has no slot contract.", slot_id=slot_id))
            continue
        if not _declares_capacity(slot):
            findings.append(_finding("SLOT_CAPACITY_UNDECLARED", "preflight", f"Required slot {slot_id!r} does not declare bounded text capacity.", slot_id=slot_id))

    if slide_blueprint is not None:
        blueprint_slots = _blueprint_slots_by_id(slide_blueprint)
        for slot_id in required_slot_ids(resolved):
            if slot_id not in blueprint_slots:
                findings.append(_finding("REQUIRED_SLOT_MISSING", "preflight", f"Required slot {slot_id!r} is missing from slide blueprint.", slot_id=slot_id))
                continue
            _validate_bound_slot(slot_contracts.get(slot_id, {}), blueprint_slots[slot_id], findings)

    return _with_policy_findings("preflight", resolved, findings)


def compile_route_gate(contract: dict[str, Any] | str | Path | None, *, selected_route: str | None) -> GateResult:
    resolved, findings = _resolve_contract(contract, stage="compile_route")
    if resolved is None:
        return GateResult(stage="compile_route", findings=tuple(findings))
    required_route = str((resolved.get("qa_policy") or {}).get("selected_route_required") or "")
    if required_route and str(selected_route or "") != required_route:
        findings.append(
            _finding(
                "COMPILER_ROUTE_NOT_EDITABLE_TEMPLATE",
                "compile_route",
                f"Compiler selected_route must be {required_route!r}, got {selected_route!r}.",
                details={"required_route": required_route, "selected_route": selected_route},
            )
        )
    return _with_policy_findings("compile_route", resolved, findings)


def post_compile_structural_gate(
    contract: dict[str, Any] | str | Path | None,
    *,
    structural_ledger: dict[str, Any] | None,
    qa_report: dict[str, Any] | None = None,
    render_report: dict[str, Any] | None = None,
    fallback_events: list[dict[str, Any]] | None = None,
) -> GateResult:
    resolved, findings = _resolve_contract(contract, stage="post_compile")
    if resolved is None:
        return GateResult(stage="post_compile", findings=tuple(findings))

    ledger_required = bool((resolved.get("structural_ledger_requirements") or {}).get("required", True))
    render_skipped = str((render_report or {}).get("status") or "").lower() == "skipped"
    ledger_required_if_render_skipped = bool((resolved.get("render_policy") or {}).get("structural_ledger_required_if_render_skipped", True))
    if structural_ledger is None and (ledger_required or (render_skipped and ledger_required_if_render_skipped)):
        findings.append(_finding("STRUCTURAL_LEDGER_MISSING", "post_compile", "Structural OOXML/object ledger is required and was not supplied."))
        return _with_policy_findings("post_compile", resolved, findings)

    qa_required = bool((resolved.get("qa_policy") or {}).get("qa_report_required", False))
    if qa_required and qa_report is None:
        findings.append(_finding("QA_REPORT_MISSING", "post_compile", "QA report is required by contract qa_policy."))

    for obj in _ledger_objects(structural_ledger or {}):
        findings.extend(_object_policy_findings(resolved, obj))

    fallback_policy = resolved.get("fallback_policy") if isinstance(resolved.get("fallback_policy"), dict) else {}
    for event in fallback_events or []:
        if fallback_policy.get("all_fallbacks_must_be_recorded", True) and not bool(event.get("recorded", True)):
            findings.append(
                _finding(
                    "UNRECORDED_FALLBACK",
                    "post_compile",
                    "Fallback event was not recorded with required component metadata.",
                    object_id=_optional_str(event.get("object_id") or event.get("component_id")),
                    details={"fallback_event": dict(event)},
                )
            )
        elif not bool(event.get("allowlisted", False)) and not bool(fallback_policy.get("fallback_allowed", False)):
            findings.append(
                _finding(
                    "UNALLOWLISTED_FALLBACK",
                    "post_compile",
                    "Fallback event is not allowlisted and contract fallback_policy is fail-closed.",
                    object_id=_optional_str(event.get("object_id") or event.get("component_id")),
                    details={"fallback_event": dict(event)},
                )
            )

    if isinstance(qa_report, dict):
        warnings = qa_report.get("warnings")
        if isinstance(warnings, list):
            findings.extend(_policy_result_findings("post_compile", evaluate_warning_records(warnings, allowlist=contract_allowlist(resolved))))

    return _with_policy_findings("post_compile", resolved, findings)


def source_bound_deck_gate(
    contract: dict[str, Any] | str | Path | None,
    *,
    slides: list[dict[str, Any]] | tuple[dict[str, Any], ...],
) -> GateResult:
    resolved, findings = _resolve_contract(contract, stage="source_bound")
    if resolved is None:
        return GateResult(stage="source_bound", findings=tuple(findings))

    source_required_slots = _binding_required_slots(resolved, kind="source")
    citation_required_slots = _binding_required_slots(resolved, kind="citation")
    for slide in slides:
        if slide.get("content_slide") is False:
            continue
        bindings = {
            str(item.get("slot_id")): item
            for item in slide.get("slot_bindings") or []
            if isinstance(item, dict) and str(item.get("slot_id") or "").strip()
        }
        for slot_id in sorted(source_required_slots):
            binding = bindings.get(slot_id)
            if binding is None or not str(binding.get("source_id") or "").strip():
                findings.append(_finding("SOURCE_BINDING_MISSING", "source_bound", f"Slot {slot_id!r} is missing source binding.", slot_id=slot_id, details={"slide_id": slide.get("slide_id")}))
        for slot_id in sorted(citation_required_slots):
            binding = bindings.get(slot_id)
            if binding is None or not str(binding.get("citation_id") or "").strip():
                findings.append(_finding("CITATION_BINDING_MISSING", "source_bound", f"Slot {slot_id!r} is missing citation binding.", slot_id=slot_id, details={"slide_id": slide.get("slide_id")}))

    return _with_policy_findings("source_bound", resolved, findings)


def protected_zone_gate(
    contract: dict[str, Any] | str | Path | None,
    *,
    intrusions: list[dict[str, Any]] | tuple[dict[str, Any], ...],
) -> GateResult:
    resolved, findings = _resolve_contract(contract, stage="protected_zone")
    if resolved is None:
        return GateResult(stage="protected_zone", findings=tuple(findings))
    warnings = []
    for intrusion in intrusions:
        code = str(intrusion.get("code") or "PROTECTED_ZONE_INTRUSION")
        warnings.append({**dict(intrusion), "code": code})
    findings.extend(_policy_result_findings("protected_zone", evaluate_warning_records(warnings, allowlist=contract_allowlist(resolved))))
    return GateResult(stage="protected_zone", findings=tuple(findings))


def build_contract_v2_gate_report(
    *,
    files_created_or_modified: list[str],
    schema_validation_results: dict[str, Any],
    tests_run: list[dict[str, Any]],
    protected_artifact_check_status: dict[str, Any] | None,
    unresolved_risks: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "schema_name": "contract_v2_gate_report",
        "schema_version": "1.0",
        "files_created_or_modified": files_created_or_modified,
        "schema_validation_results": schema_validation_results,
        "warning_taxonomy": DEFAULT_FATAL_WARNING_CODES_REPORT,
        "fatal_by_default_codes": sorted(DEFAULT_FATAL_WARNING_CODES),
        "allowlist_rules": {
            "entries_must_include": ["code", "reason", "owner", "object_id_or_slot_id", "expiration_or_scope"],
            "global_silent_allowlists_allowed": False,
            "unknown_warning_codes_are_fatal": True,
            "fatal_warning_downgrade_without_allowlist_is_fatal": True,
        },
        "tests_run": tests_run,
        "pass_fail_summary": {
            "passed": all(item.get("exit_code") == 0 for item in tests_run)
            and (protected_artifact_check_status or {}).get("status") in {None, "passed"},
            "test_failures": [item for item in tests_run if item.get("exit_code") != 0],
        },
        "protected_artifact_check_status": protected_artifact_check_status,
        "unresolved_risks": unresolved_risks or [],
    }


def write_contract_v2_gate_report(report: dict[str, Any], output_dir: str | Path = DEFAULT_REPORT_DIR) -> tuple[Path, Path]:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    json_path = directory / "contract_v2_gate_report.json"
    md_path = directory / "contract_v2_gate_report.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")
    md_path.write_text(_contract_v2_gate_report_md(report), encoding="utf-8")
    return json_path, md_path


DEFAULT_FATAL_WARNING_CODES_REPORT = {code: "fatal" for code in sorted(DEFAULT_FATAL_WARNING_CODES)}


def _contract_v2_gate_report_md(report: dict[str, Any]) -> str:
    summary = report.get("pass_fail_summary") or {}
    protected = report.get("protected_artifact_check_status") or {}
    lines = [
        "# Contract V2 Gate Report",
        "",
        f"Status: `{'passed' if summary.get('passed') else 'failed'}`",
        f"Protected artifact check: `{protected.get('status', 'unknown')}`",
        "",
        "## Files Created Or Modified",
        "",
    ]
    for path in report.get("files_created_or_modified") or []:
        lines.append(f"- `{path}`")
    lines.extend(["", "## Fatal-By-Default Codes", ""])
    for code in report.get("fatal_by_default_codes") or []:
        lines.append(f"- `{code}`")
    lines.extend(["", "## Allowlist Rules", ""])
    rules = report.get("allowlist_rules") or {}
    for key, value in rules.items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Tests Run", ""])
    for item in report.get("tests_run") or []:
        lines.append(f"- `{item.get('command')}` -> exit `{item.get('exit_code')}`")
    lines.extend(["", "## Unresolved Risks", ""])
    risks = report.get("unresolved_risks") or []
    if risks:
        for risk in risks:
            lines.append(f"- {risk}")
    else:
        lines.append("- None")
    return "\n".join(lines) + "\n"


def _resolve_contract(contract: dict[str, Any] | str | Path | None, *, stage: str) -> tuple[dict[str, Any] | None, list[GateFinding]]:
    if contract is None:
        return None, [_finding("CONTRACT_NOT_FOUND", stage, "Template Contract V2 was not supplied.")]
    if isinstance(contract, (str, Path)):
        path = Path(contract)
        if not path.exists():
            return None, [_finding("CONTRACT_NOT_FOUND", stage, f"Template Contract V2 not found at {path.as_posix()}.")]
        try:
            return load_template_contract(path), []
        except (OSError, json.JSONDecodeError, ValidationError, ValueError) as exc:
            return None, [_contract_validation_finding(contract_payload=None, stage=stage, exc=exc)]
    if not is_supported_contract_version(contract):
        return None, [_finding("CONTRACT_VERSION_UNSUPPORTED", stage, "Template Contract V2 requires contract_version '2'.", details={"contract_version": contract.get("contract_version")})]
    try:
        validate_template_contract_payload(contract)
    except ValidationError as exc:
        return None, [_contract_validation_finding(contract_payload=contract, stage=stage, exc=exc)]
    return contract, []


def _contract_validation_finding(contract_payload: dict[str, Any] | None, *, stage: str, exc: Exception) -> GateFinding:
    if isinstance(contract_payload, dict) and not is_supported_contract_version(contract_payload):
        return _finding("CONTRACT_VERSION_UNSUPPORTED", stage, "Template Contract V2 requires contract_version '2'.", details={"contract_version": contract_payload.get("contract_version")})
    return _finding("CONTRACT_VERSION_UNSUPPORTED", stage, f"Template contract is invalid or unsupported: {exc}", details={"error": str(exc)})


def _with_policy_findings(stage: str, contract: dict[str, Any], findings: list[GateFinding]) -> GateResult:
    warning_records = [finding.to_report() for finding in findings if finding.code in DEFAULT_FATAL_WARNING_CODES]
    policy = evaluate_warning_records(warning_records, allowlist=contract_allowlist(contract))
    policy_keys = {(finding.code, finding.object_id, finding.slot_id) for finding in policy.findings}
    existing_keys = {(finding.code, finding.object_id, finding.slot_id) for finding in findings}
    extra = [
        _policy_finding_to_gate(stage, finding)
        for finding in policy.findings
        if (finding.code, finding.object_id, finding.slot_id) not in existing_keys or (finding.code, finding.object_id, finding.slot_id) not in policy_keys
    ]
    return GateResult(stage=stage, findings=tuple([*findings, *extra]))


def _policy_result_findings(stage: str, result: Any) -> list[GateFinding]:
    return [_policy_finding_to_gate(stage, finding) for finding in result.findings]


def _policy_finding_to_gate(stage: str, finding: Any) -> GateFinding:
    return GateFinding(
        code=finding.code,
        severity=finding.severity,
        stage=stage,
        message=finding.message,
        object_id=finding.object_id,
        slot_id=finding.slot_id,
        details=finding.details,
    )


def _finding(
    code: str,
    stage: str,
    message: str,
    *,
    object_id: str | None = None,
    slot_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> GateFinding:
    return GateFinding(code=code, severity="fatal", stage=stage, message=message, object_id=object_id, slot_id=slot_id, details=details or {})


def _declares_capacity(slot: dict[str, Any]) -> bool:
    min_chars = slot.get("min_capacity_chars")
    max_chars = slot.get("max_capacity_chars")
    if not isinstance(min_chars, int) or not isinstance(max_chars, int):
        return False
    return min_chars >= 0 and max_chars >= min_chars


def _blueprint_slots_by_id(slide_blueprint: dict[str, Any]) -> dict[str, dict[str, Any]]:
    slots = slide_blueprint.get("slots")
    if isinstance(slots, list):
        return {
            str(slot.get("slot_id")): slot
            for slot in slots
            if isinstance(slot, dict) and str(slot.get("slot_id") or "").strip()
        }
    slot_bindings = slide_blueprint.get("slot_bindings")
    if isinstance(slot_bindings, list):
        return {
            str(slot.get("slot_id")): slot
            for slot in slot_bindings
            if isinstance(slot, dict) and str(slot.get("slot_id") or "").strip()
        }
    return {}


def _validate_bound_slot(slot_contract: dict[str, Any], bound_slot: dict[str, Any], findings: list[GateFinding]) -> None:
    slot_id = str(slot_contract.get("slot_id") or bound_slot.get("slot_id") or "")
    if slot_contract.get("editable_required") and bound_slot.get("editable") is False:
        findings.append(_finding("NON_EDITABLE_REQUIRED_TEXT", "preflight", f"Slot {slot_id!r} must remain editable.", slot_id=slot_id))
    primitive = str(bound_slot.get("primitive") or "")
    if primitive and primitive in {str(item) for item in slot_contract.get("forbidden_primitives") or []}:
        findings.append(_finding("NON_EDITABLE_REQUIRED_TEXT", "preflight", f"Slot {slot_id!r} uses forbidden primitive {primitive!r}.", slot_id=slot_id, details={"primitive": primitive}))
    text = str(bound_slot.get("text") or bound_slot.get("content") or "")
    max_capacity = slot_contract.get("max_capacity_chars")
    if isinstance(max_capacity, int) and len(text) > max_capacity and not bool(slot_contract.get("overflow_allowed")):
        findings.append(_finding("TEXT_OVERFLOW", "preflight", f"Slot {slot_id!r} text exceeds declared max capacity.", slot_id=slot_id, details={"chars": len(text), "max_capacity_chars": max_capacity}))
    if slot_contract.get("required") and not text and not bound_slot.get("object_id"):
        findings.append(_finding("SLOT_BINDING_MISSING", "preflight", f"Required slot {slot_id!r} has no bound content/object.", slot_id=slot_id))
    if slot_contract.get("source_binding_required") and not str(bound_slot.get("source_id") or "").strip():
        findings.append(_finding("SOURCE_BINDING_MISSING", "preflight", f"Slot {slot_id!r} requires source binding.", slot_id=slot_id))
    if slot_contract.get("citation_binding_required") and not str(bound_slot.get("citation_id") or "").strip():
        findings.append(_finding("CITATION_BINDING_MISSING", "preflight", f"Slot {slot_id!r} requires citation binding.", slot_id=slot_id))


def _ledger_objects(ledger: dict[str, Any]) -> list[dict[str, Any]]:
    objects: list[dict[str, Any]] = []
    for slide in ledger.get("slides") or []:
        if not isinstance(slide, dict):
            continue
        for obj in slide.get("objects") or []:
            if isinstance(obj, dict):
                objects.append({**obj, "slide_number": slide.get("slide_number")})
        inventory = slide.get("inventory")
        if isinstance(inventory, dict):
            for obj in inventory.get("shapes") or []:
                if isinstance(obj, dict):
                    objects.append({**obj, "slide_number": slide.get("slide_number")})
    for obj in ledger.get("objects") or []:
        if isinstance(obj, dict):
            objects.append(obj)
    return objects


def _object_policy_findings(contract: dict[str, Any], obj: dict[str, Any]) -> list[GateFinding]:
    findings: list[GateFinding] = []
    raster_policy = contract.get("raster_policy") if isinstance(contract.get("raster_policy"), dict) else {}
    semantic_type = str(obj.get("semantic_type") or obj.get("semantic_kind") or "").lower()
    primitive = str(obj.get("primitive") or obj.get("shape_type") or "").lower()
    object_id = _optional_str(obj.get("object_id") or obj.get("name"))
    slot_id = _optional_str(obj.get("slot_id"))
    is_raster = bool(obj.get("raster")) or primitive in {"raster_image", "bitmap", "picture"} or "image" in primitive and primitive != "image_frame"
    if is_raster:
        if (bool(obj.get("full_slide")) or float(obj.get("coverage_ratio") or 0.0) >= 0.95) and not bool(raster_policy.get("full_slide_raster_allowed", False)):
            findings.append(_finding("FULL_SLIDE_RASTER", "post_compile", "Full-slide raster object is forbidden.", object_id=object_id, slot_id=slot_id, details={"object": obj}))
        if bool(obj.get("content_bearing")) and not bool(raster_policy.get("content_bearing_raster_allowed", False)):
            findings.append(_finding("CONTENT_BEARING_RASTER", "post_compile", "Content-bearing raster object is forbidden.", object_id=object_id, slot_id=slot_id, details={"object": obj}))
        if bool(obj.get("contains_text") or obj.get("baked_text")):
            findings.append(_finding("BAKED_TEXT_RASTER", "post_compile", "Raster object contains baked text.", object_id=object_id, slot_id=slot_id, details={"object": obj}))
        if semantic_type == "icon" and not bool(raster_policy.get("semantic_component_raster_allowed", False)):
            findings.append(_finding("SEMANTIC_ICON_RASTER", "post_compile", "Semantic icon was emitted as raster.", object_id=object_id, slot_id=slot_id, details={"object": obj}))
        if semantic_type == "table" and not bool(raster_policy.get("semantic_component_raster_allowed", False)):
            findings.append(_finding("SEMANTIC_TABLE_RASTER", "post_compile", "Semantic table was emitted as raster.", object_id=object_id, slot_id=slot_id, details={"object": obj}))
        if semantic_type == "chart" and not bool(raster_policy.get("semantic_component_raster_allowed", False)):
            findings.append(_finding("SEMANTIC_CHART_RASTER", "post_compile", "Semantic chart was emitted as raster.", object_id=object_id, slot_id=slot_id, details={"object": obj}))

    slot_contract = slot_contracts_by_id(contract).get(slot_id or "")
    if slot_contract and slot_contract.get("editable_required") and (obj.get("editable") is False or (semantic_type == "text" and primitive not in {"ppt_text", "text", "textbox"})):
        findings.append(_finding("NON_EDITABLE_REQUIRED_TEXT", "post_compile", f"Required editable slot {slot_id!r} was not emitted as editable PPT text.", object_id=object_id, slot_id=slot_id, details={"object": obj}))
    return findings


def _binding_required_slots(contract: dict[str, Any], *, kind: str) -> set[str]:
    slot_contracts = slot_contracts_by_id(contract)
    required: set[str] = {
        slot_id
        for slot_id, slot in slot_contracts.items()
        if bool(slot.get(f"{kind}_binding_required"))
    }
    key = "source_binding_requirements" if kind == "source" else "citation_binding_requirements"
    requirements = contract.get(key) if isinstance(contract.get(key), dict) else {}
    if requirements.get("required_for_content_slides"):
        required_types = {str(item) for item in requirements.get("required_slot_types") or []}
        for slot_id, slot in slot_contracts.items():
            if str(slot.get("slot_type")) in required_types:
                required.add(slot_id)
    return required


def _optional_str(value: Any) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None
