"""E00-RX anti-scaleout lock helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


class ScaleoutBlockedError(AssertionError):
    """Raised when a downstream scaleout stage is requested before gates pass."""


E01_PASS_DECISIONS = {
    "E01_PASS_START_E02_4CORE_MAGIC_LAYER_PLUS",
    "E01_7_PASS_CANVA_PLUS_SINGLE_SLIDE_START_E02_4CORE_MAGIC_LAYER_PLUS",
}
E02_PASS_DECISIONS = {
    "E02_PASS_START_E03_12_16_ARCHETYPE_TEMPLATE_PACK",
    "E02_READY_START_4CORE_MAGIC_LAYER_PLUS_CONVERSION",
}
E03_PASS_DECISIONS = {"E03_PASS_START_E04_SOURCE_BOUND_SMALL_DECK"}
E04_PASS_DECISIONS = {"E04_PASS_START_E05_LARGE_DECK_SCALEOUT"}

BLOCKED_STAGE_FAMILIES = {"D08", "C11", "BULK", "LARGE_DECK", "34_SLIDE", "50_SLIDE", "70_SLIDE", "E05"}


def is_e01_passed(path: str | Path | Mapping[str, Any] | None) -> bool:
    report = _load_mapping(path)
    return _is_gate_pass(report, E01_PASS_DECISIONS)


def is_e02_passed(path: str | Path | Mapping[str, Any] | None) -> bool:
    report = _load_mapping(path)
    return _is_gate_pass(report, E02_PASS_DECISIONS)


def explain_scaleout_block(stage: str) -> dict[str, Any]:
    normalized = _normalize_stage(stage)
    if normalized == "E02":
        required = "E01_PASS_START_E02_4CORE_MAGIC_LAYER_PLUS"
    elif normalized == "E03":
        required = "E02_PASS_START_E03_12_16_ARCHETYPE_TEMPLATE_PACK"
    elif normalized == "E04":
        required = "E03_PASS_START_E04_SOURCE_BOUND_SMALL_DECK"
    else:
        required = "E04_PASS_START_E05_LARGE_DECK_SCALEOUT"
    return {
        "stage": stage,
        "normalized_stage": normalized,
        "allowed": False,
        "required_gate": required,
        "reason": "D07 route proofs, R00/R00X audits, and source-bound decks cannot unlock scaleout.",
    }


def assert_scaleout_allowed(stage: str, readiness_paths: Mapping[str, Any] | None = None) -> bool:
    """Assert that a downstream stage is unlocked by the required passing gates."""

    readiness = dict(readiness_paths or {})
    normalized = _normalize_stage(stage)

    if normalized == "E01":
        return True
    if normalized == "E02":
        if is_e01_passed(readiness.get("e01") or readiness.get("E01")):
            return True
        raise ScaleoutBlockedError(explain_scaleout_block(stage)["reason"])
    if normalized == "E03":
        if is_e01_passed(readiness.get("e01") or readiness.get("E01")) and is_e02_passed(
            readiness.get("e02") or readiness.get("E02")
        ):
            return True
        raise ScaleoutBlockedError(explain_scaleout_block(stage)["reason"])
    if normalized in {"E04"} | BLOCKED_STAGE_FAMILIES:
        if _chain_passed(readiness):
            return True
        raise ScaleoutBlockedError(explain_scaleout_block(stage)["reason"])
    raise ScaleoutBlockedError(f"Unknown or unsupported stage is blocked by default: {stage}")


def _chain_passed(readiness: Mapping[str, Any]) -> bool:
    return (
        is_e01_passed(readiness.get("e01") or readiness.get("E01"))
        and is_e02_passed(readiness.get("e02") or readiness.get("E02"))
        and _is_gate_pass(_load_mapping(readiness.get("e03") or readiness.get("E03")), E03_PASS_DECISIONS)
        and _is_gate_pass(_load_mapping(readiness.get("e04") or readiness.get("E04")), E04_PASS_DECISIONS)
    )


def _normalize_stage(stage: str) -> str:
    text = stage.strip().upper().replace("-", "_")
    if text.startswith("E01"):
        return "E01"
    if text.startswith("E02"):
        return "E02"
    if text.startswith("E03"):
        return "E03"
    if text.startswith("E04"):
        return "E04"
    if text.startswith("E05"):
        return "E05"
    if text.startswith("D08"):
        return "D08"
    if text.startswith("C11"):
        return "C11"
    if "BULK" in text:
        return "BULK"
    if "70" in text:
        return "70_SLIDE"
    if "50" in text:
        return "50_SLIDE"
    if "34" in text:
        return "34_SLIDE"
    if "LARGE" in text or "SCALEOUT" in text:
        return "LARGE_DECK"
    return text


def _is_gate_pass(report: Mapping[str, Any], allowed_decisions: set[str]) -> bool:
    decision = str(report.get("decision") or report.get("decision_label") or "")
    status = str(report.get("status") or report.get("gate_status") or "").lower()
    return decision in allowed_decisions and status in {"passed", "pass"}


def _load_mapping(value: str | Path | Mapping[str, Any] | None) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    path = Path(value)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))
