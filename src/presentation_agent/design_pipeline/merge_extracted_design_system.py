"""Merge heuristic and Codex-assisted extracted design-system artifacts."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from jsonschema.exceptions import ValidationError

from ..generator_contracts import validateExtractedDesignSystem


CODEX_PRIORITY_FIELDS = [
    "layout_grid",
    "footer_observations",
    "card_observations",
    "diagonal_panel_observations",
    "background_ornament_observations",
    "typography_estimates",
    "density_profile",
]

HEURISTIC_FALLBACK_FIELDS = [
    "source_template_images",
    "canvas",
    "detected_palette",
    "safe_margins",
]


def merge_extracted_design_systems(
    heuristic: dict[str, Any] | None,
    codex: dict[str, Any] | None,
) -> dict[str, Any]:
    valid_heuristic = _valid_or_none(heuristic)
    valid_codex = _valid_or_none(codex)

    if valid_heuristic is None and valid_codex is None:
        if codex is not None:
            raise ValueError("Codex extracted design system is invalid and no heuristic fallback was provided.")
        raise ValueError("No extracted design-system artifact was provided.")

    if valid_heuristic is None:
        merged = deepcopy(valid_codex)
        merged["extraction_warnings"] = _warnings(merged) + [
            _warning("CODEX_ONLY_EXTRACTION_USED", "Codex-assisted extraction was used without a heuristic fallback artifact.", "info")
        ]
        validateExtractedDesignSystem(merged)
        return merged

    merged = deepcopy(valid_heuristic)
    if codex is None:
        merged["extraction_warnings"] = _warnings(merged) + [
            _warning("CODEX_EXTRACTION_NOT_PROVIDED", "No extracted_design_system.codex.json artifact was present; heuristic extraction was used.", "info")
        ]
        validateExtractedDesignSystem(merged)
        return merged

    if valid_codex is None:
        merged["extraction_warnings"] = _warnings(merged) + [
            _warning("CODEX_EXTRACTION_INVALID_IGNORED", "The Codex-assisted extraction artifact failed validation and was ignored.", "warning")
        ]
        validateExtractedDesignSystem(merged)
        return merged

    for field in CODEX_PRIORITY_FIELDS:
        if _has_payload(valid_codex.get(field)):
            merged[field] = deepcopy(valid_codex[field])

    for field in HEURISTIC_FALLBACK_FIELDS:
        if _has_payload(valid_heuristic.get(field)):
            merged[field] = deepcopy(valid_heuristic[field])

    merged["confidence_scores"] = _merge_confidence_scores(valid_heuristic, valid_codex)
    merged["component_observations"] = _merge_observation_list(
        valid_heuristic.get("component_observations") or [],
        valid_codex.get("component_observations") or [],
    )
    for field in ("chart_frame_observations", "table_frame_observations", "image_frame_observations"):
        if _has_payload(valid_codex.get(field)):
            merged[field] = deepcopy(valid_codex[field])

    merged["extraction_warnings"] = _warnings(valid_heuristic) + _warnings(valid_codex) + [
        _warning(
            "CODEX_EXTRACTION_MERGED",
            "Codex-assisted observations were merged with heuristic image metrics; Codex fields took priority for layout and component observations.",
            "info",
        )
    ]
    validateExtractedDesignSystem(merged)
    return merged


def merge_extracted_design_system_files(
    *,
    heuristic_path: str | Path | None,
    codex_path: str | Path | None,
    output_path: str | Path,
) -> Path:
    heuristic = _load_optional_json(heuristic_path)
    codex = _load_optional_json(codex_path)
    merged = merge_extracted_design_systems(heuristic, codex)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(merged, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")
    return output


def _valid_or_none(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if payload is None:
        return None
    try:
        validateExtractedDesignSystem(payload)
    except (ValidationError, ValueError, TypeError):
        return None
    return payload


def _load_optional_json(path: str | Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    artifact_path = Path(path)
    if not artifact_path.exists():
        return None
    try:
        payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"schema_name": "invalid_codex_design_system"}
    return payload if isinstance(payload, dict) else {"schema_name": "invalid_codex_design_system"}


def _merge_confidence_scores(heuristic: dict[str, Any], codex: dict[str, Any]) -> dict[str, float]:
    merged = dict(heuristic.get("confidence_scores") or {})
    codex_scores = codex.get("confidence_scores") or {}
    for key, value in codex_scores.items():
        if key not in {"image_size", "palette", "blank_area", "edge_density"}:
            merged[key] = value
    merged["codex_observations"] = max(float(merged.get("codex_observations", 0.0)), 0.78)
    return merged


def _merge_observation_list(heuristic_items: list[dict[str, Any]], codex_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not codex_items:
        return deepcopy(heuristic_items)
    seen: set[str] = set()
    merged: list[dict[str, Any]] = []
    for item in codex_items + heuristic_items:
        observation_id = str(item.get("observation_id") or "")
        if observation_id and observation_id in seen:
            continue
        if observation_id:
            seen.add(observation_id)
        merged.append(deepcopy(item))
    return merged


def _has_payload(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, (list, dict, str)):
        return bool(value)
    return True


def _warnings(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [warning for warning in payload.get("extraction_warnings") or [] if isinstance(warning, dict)]


def _warning(code: str, message: str, severity: str) -> dict[str, str]:
    return {"code": code, "message": message, "severity": severity}
