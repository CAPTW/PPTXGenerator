"""Fail-closed Phase 7 release-contract and provenance primitives."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable

from ..identity import canonical_json_bytes


PROVENANCE_CLASSES = {
    "existing",
    "adapted",
    "build_week_new",
    "external_existing",
    "platform_generated",
    "historical_evidence",
    "protected_not_used",
}
PROTECTED_OUTPUTS = {
    "outputs/editable_template_spec.final.json",
    "outputs/golden_template_masters.pptx",
    "outputs/final_deck_large_premium.pptx",
}
_SECRET = re.compile(
    r"(?i)(?:api[_-]?key|access[_-]?token|client[_-]?secret|password|authorization|bearer)"
    r"\s*[:=]\s*['\"]?[A-Za-z0-9_./+\-=]{8,}"
)
_PRIVATE_KEY = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")
_PATH_LEAK = re.compile(
    r"(?i)(?:[A-Z]:[\\/](?:Users[\\/][^\\/\s]+|dev[\\/])|"
    r"AppData[\\/]Local[\\/]Temp|[A-Z]:[\\/][^\s\"']*[\\/]Temp[\\/])"
)


class ReleaseContractError(RuntimeError):
    """Stable Phase 7 release-contract failure."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}" if detail else code)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind_content_hash(payload: dict[str, Any], field: str) -> dict[str, Any]:
    """Bind a payload to canonical JSON content without a self-reference loop."""

    result = dict(payload)
    result.pop(field, None)
    result[field] = hashlib.sha256(canonical_json_bytes(result)).hexdigest()
    return result


def verify_content_hash(payload: dict[str, Any], field: str) -> bool:
    expected = payload.get(field)
    return isinstance(expected, str) and bind_content_hash(payload, field)[field] == expected


def _require_path(value: Any, code: str, *, directory: bool | None = None) -> Path:
    if not isinstance(value, str) or not value:
        raise ReleaseContractError(code, "path is absent")
    path = Path(value)
    exists = path.is_dir() if directory is True else path.is_file() if directory is False else path.exists()
    if not exists:
        raise ReleaseContractError(code, value)
    return path


def _slash(value: str) -> str:
    return value.replace("\\", "/").lower()


def validate_release_contract(
    payload: dict[str, Any], *, observed_os: str, observed_python: str
) -> bool:
    """Validate Phase 7A invariants that must hold before demo execution."""

    if payload.get("supported_os") != observed_os:
        raise ReleaseContractError("DC_UNSUPPORTED_OS", observed_os)
    if payload.get("python_version") != observed_python:
        raise ReleaseContractError("DC_UNSUPPORTED_PYTHON", observed_python)
    lock = _require_path(payload.get("python_lock_path"), "DC_LOCK_MISSING", directory=False)
    if sha256_file(lock) != payload.get("python_lock_sha256"):
        raise ReleaseContractError("DC_LOCK_HASH_MISMATCH", str(lock))
    dependency_manifest_path = _require_path(
        payload.get("external_python_dependency_manifest_path"),
        "DC_EXTERNAL_PY_DEPENDENCY_MANIFEST_MISSING",
        directory=False,
    )
    if (
        sha256_file(dependency_manifest_path)
        != payload.get("external_python_dependency_manifest_sha256")
    ):
        raise ReleaseContractError(
            "DC_EXTERNAL_PY_DEPENDENCY_MANIFEST_MISSING",
            "file hash mismatch",
        )
    dependency_manifest = json.loads(
        dependency_manifest_path.read_text(encoding="utf-8")
    )
    if (
        not verify_content_hash(dependency_manifest, "manifest_hash")
        or dependency_manifest.get("manifest_hash")
        != payload.get("external_python_dependency_manifest_hash")
        or dependency_manifest.get("lock", {}).get("sha256")
        != payload.get("python_lock_sha256")
    ):
        raise ReleaseContractError(
            "DC_EXTERNAL_PY_DEPENDENCY_LOCK_MISMATCH",
            str(dependency_manifest_path),
        )
    dependency_policy = payload.get("external_python_dependency_policy", {})
    if (
        dependency_policy.get("interpreter_owner")
        != "deckcompiler_sys_executable"
        or dependency_policy.get("path_fallback") is not False
        or dependency_policy.get("system_site_packages") is not False
        or dependency_policy.get("user_site_packages") is not False
    ):
        raise ReleaseContractError(
            "DC_EXTERNAL_PY_ENTRYPOINT_CANARY_FAILED",
            "interpreter ownership policy",
        )
    if payload.get("powerpoint_com_available") is not True:
        raise ReleaseContractError("DC_POWERPOINT_REQUIRED")
    if payload.get("playwright_chromium_available") is not True:
        raise ReleaseContractError("DC_CHROMIUM_REQUIRED")
    pin = _require_path(payload.get("external_pin_path"), "DC_EXTERNAL_PIN_MISSING", directory=False)
    if sha256_file(pin) != payload.get("external_pin_sha256"):
        raise ReleaseContractError("DC_EXTERNAL_PIN_HASH_MISMATCH", str(pin))
    if payload.get("credential_requirement") is not False:
        raise ReleaseContractError("DC_CREDENTIAL_FORBIDDEN")
    for raw in payload.get("input_paths", []):
        normalized = _slash(str(raw))
        if normalized.startswith("outputs/") or "/outputs/" in normalized:
            if any(normalized.endswith(item) or item in normalized for item in PROTECTED_OUTPUTS):
                raise ReleaseContractError("DC_PROTECTED_INPUT", str(raw))
            raise ReleaseContractError("DC_GENERATED_OUTPUT_INPUT", str(raw))
        if any(normalized.endswith(item) or item in normalized for item in PROTECTED_OUTPUTS):
            raise ReleaseContractError("DC_PROTECTED_INPUT", str(raw))
    _require_path(payload.get("phase4_bundle_path"), "DC_PHASE4_MISSING", directory=True)
    _require_path(payload.get("phase5_bundle_path"), "DC_PHASE5_MISSING", directory=True)
    _require_path(payload.get("phase6_evidence_path"), "DC_PHASE6_MISSING", directory=True)
    _require_path(payload.get("canonical_config_path"), "DC_CONFIG_MISSING", directory=False)
    policy_path = _require_path(
        payload.get("bundle_fingerprint_policy_path"),
        "DC_BUNDLE_FINGERPRINT_POLICY_MISSING",
        directory=False,
    )
    for key in (
        "phase4_authority_manifest_path",
        "phase5_authority_manifest_path",
        "phase4_runtime_compatibility_report_path",
        "phase5_runtime_compatibility_report_path",
        "phase6_authority_bridge_path",
    ):
        _require_path(payload.get(key), "DC_BUNDLE_AUTHORITY_EVIDENCE_MISSING", directory=False)
    if payload.get("phase6_status") != "ELIGIBLE_FOR_PACKAGING":
        raise ReleaseContractError("DC_PHASE6_NOT_ELIGIBLE", str(payload.get("phase6_status")))
    if payload.get("selected_route") != "editable_pngtopptx":
        raise ReleaseContractError("DC_STRICT_ROUTE_REQUIRED")
    if payload.get("live_image_generation_mode") != "disabled_frozen_verified_visual_bundle":
        raise ReleaseContractError("DC_LIVE_IMAGE_GENERATION_FORBIDDEN")
    if payload.get("final_release_eligible") is not False:
        raise ReleaseContractError("DC_SELF_DECLARED_RELEASE")
    if payload.get("devpost_release_eligible") is not False:
        raise ReleaseContractError("DC_SELF_DECLARED_RELEASE")
    if any(
        payload.get(field) is not False
        for field in ("submission_performed", "push_performed", "tag_created")
    ):
        raise ReleaseContractError("DC_RELEASE_ACTION_ALREADY_PERFORMED")

    from .bundle_fingerprint import (
        validate_release_bundle_authorities,
        validate_supported_release_checkout,
        verify_bound_hash,
    )
    from ..schemas import validator_for

    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    policy_errors = list(validator_for("bundle_fingerprint_policy").iter_errors(policy))
    if policy_errors or not verify_bound_hash(policy, "policy_hash"):
        raise ReleaseContractError("DC_BUNDLE_FINGERPRINT_POLICY_INVALID")
    try:
        repository_root = Path(__file__).resolve().parents[4]
        validate_release_bundle_authorities(repository_root, payload)
        checkout = payload.get("supported_release_checkout", {})
        checkout_result = validate_supported_release_checkout(
            repository_root,
            checkout.get("exact_runtime_text_path", ""),
            expected_sha256=str(checkout.get("exact_runtime_text_sha256", "")),
            required_core_autocrlf=bool(checkout.get("core_autocrlf")),
        )
    except Exception as exc:
        raise ReleaseContractError(
            getattr(exc, "code", "DC_BUNDLE_AUTHORITY_INVALID"), str(exc)
        ) from exc
    if checkout_result["status"] != "PASS":
        raise ReleaseContractError("DC_RELEASE_CHECKOUT_UNSUPPORTED")
    return True


def validate_component_provenance(items: Iterable[dict[str, Any]]) -> bool:
    for item in items:
        classification = item.get("classification")
        if classification not in PROVENANCE_CLASSES:
            raise ReleaseContractError("DC_PROVENANCE_CLASS_UNKNOWN", str(classification))
        origin = item.get("origin")
        if classification == "build_week_new" and origin in {"pre_baseline", "external"}:
            raise ReleaseContractError("DC_PROVENANCE_OVERCLAIM", str(item.get("component")))
        if origin == "external" and classification != "external_existing":
            raise ReleaseContractError("DC_PROVENANCE_OVERCLAIM", str(item.get("component")))
    return True


def build_component_provenance(items: Iterable[dict[str, Any]]) -> dict[str, Any]:
    components = sorted((dict(item) for item in items), key=lambda item: str(item.get("component")))
    validate_component_provenance(components)
    counts = {name: sum(item["classification"] == name for item in components) for name in sorted(PROVENANCE_CLASSES)}
    return bind_content_hash(
        {
            "schema_name": "component_provenance_manifest",
            "schema_version": "1.0.0",
            "components": components,
            "classification_counts": counts,
            "component_count": len(components),
            "no_overclaim": True,
        },
        "provenance_hash",
    )


def build_runtime_environment_manifest(**values: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_name": "runtime_environment_manifest",
        "schema_version": "1.0.0",
        "credential_requirement": False,
        "canonical_timezone": "Asia/Seoul",
        "path_sanitization_policy": "curated_artifacts_use_placeholders_and_relative_paths",
        "setup_verification_status": "PASS",
    }
    payload.update(values)
    return bind_content_hash(payload, "manifest_hash")


def scan_release_text(text: str) -> dict[str, int]:
    return {
        "secret_count": len(_SECRET.findall(text)),
        "private_key_count": len(_PRIVATE_KEY.findall(text)),
        "path_leak_count": int(_PATH_LEAK.search(text) is not None),
    }


def validate_license_report(payload: dict[str, Any]) -> bool:
    if payload.get("unresolved_redistribution_blocker_count") != 0:
        raise ReleaseContractError("BLOCKED_LICENSE_PROVENANCE_INCOMPLETE")
    if payload.get("external_skill_source_included", False):
        raise ReleaseContractError("BLOCKED_LICENSE_PROVENANCE_INCOMPLETE", "external Skill source included")
    return True


def schema_ids_are_unique(schema_root: Path) -> bool:
    ids: list[str] = []
    for path in sorted(schema_root.glob("*.schema.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        schema_id = payload.get("$id")
        if not isinstance(schema_id, str) or not schema_id:
            return False
        ids.append(schema_id)
    return len(ids) == len(set(ids))


__all__ = [
    "PROVENANCE_CLASSES",
    "PROTECTED_OUTPUTS",
    "ReleaseContractError",
    "bind_content_hash",
    "build_component_provenance",
    "build_runtime_environment_manifest",
    "schema_ids_are_unique",
    "scan_release_text",
    "sha256_file",
    "validate_component_provenance",
    "validate_license_report",
    "validate_release_contract",
    "verify_content_hash",
]
