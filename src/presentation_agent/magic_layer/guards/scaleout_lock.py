from __future__ import annotations

from typing import Any


BLOCKED_STAGES = {"D08", "C11", "BULK", "CANONICAL_PROMOTION"}


def is_stage_allowed(stage: str, registry: Any, repo_state: dict[str, Any]) -> bool:
    normalized = stage.upper().replace("-", "_")
    if normalized in BLOCKED_STAGES:
        return False
    if normalized == "E03":
        return _has_claim(registry, "E03_PASS")
    if normalized == "E04":
        return _has_claim(registry, "E03_PASS")
    if normalized in {"D08", "C11", "BULK", "CANONICAL"}:
        return False
    return False


def explain_stage_block(stage: str, registry: Any, repo_state: dict[str, Any]) -> dict[str, Any]:
    allowed = is_stage_allowed(stage, registry, repo_state)
    if allowed:
        return {"stage": stage, "allowed": True, "status": "ALLOWED", "reason": "Required prerequisite claim is registered."}
    normalized = stage.upper().replace("-", "_")
    if normalized == "E03":
        reason = "E03 is blocked until an explicit E03 pass exists in the registry."
    elif normalized == "E04":
        reason = "E04 is blocked until E03 pass exists."
    elif normalized in {"D08", "C11", "BULK"}:
        reason = "D08/C11/bulk require E03 pass, E04 source-bound pass, registry clean, and validation CLI pass."
    elif normalized in {"CANONICAL_PROMOTION", "CANONICAL"}:
        reason = "Canonical promotion is blocked while manual-review debt and validation gates remain."
    else:
        reason = "Stage is not enabled by A01 policy."
    return {"stage": stage, "allowed": False, "status": "BLOCKED_BY_SCALEOUT_LOCK", "reason": reason}


def assert_stage_allowed(stage: str, registry: Any, repo_state: dict[str, Any]) -> None:
    result = explain_stage_block(stage, registry, repo_state)
    if not result["allowed"]:
        raise RuntimeError(result["reason"])


def _has_claim(registry: Any, claim: str) -> bool:
    for record in getattr(registry, "records", []):
        if claim in getattr(record, "claims_supported", []):
            return True
    return False
