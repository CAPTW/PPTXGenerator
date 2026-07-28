"""Photoshop-inspired layer protocol helpers for Magic Layer+ validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


PROTOCOL_EXAMPLE_FILES = ["ps_layer_intent_example.json", "ps_layer_as_built_example.json"]
PROTOCOL_SCHEMA_FILE = "ps_layer_protocol_schema.json"
SELECTION_SCHEMA_FILE = "selection_patch_context_schema.json"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_bbox(bbox: Any) -> dict[str, float]:
    if isinstance(bbox, dict):
        return {key: float(bbox[key]) for key in ("x", "y", "w", "h")}
    if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
        return {"x": float(bbox[0]), "y": float(bbox[1]), "w": float(bbox[2]), "h": float(bbox[3])}
    raise ValueError(f"Unsupported bbox shape: {bbox!r}")


def bbox_area(bbox: Any) -> float:
    norm = normalize_bbox(bbox)
    return round(norm["w"] * norm["h"], 10)


def bbox_inside_slide(bbox: Any) -> bool:
    try:
        norm = normalize_bbox(bbox)
    except (KeyError, TypeError, ValueError):
        return False
    return (
        0 <= norm["x"] <= 1
        and 0 <= norm["y"] <= 1
        and norm["w"] > 0
        and norm["h"] > 0
        and norm["x"] + norm["w"] <= 1.0000001
        and norm["y"] + norm["h"] <= 1.0000001
    )


def point_inside_slide(point: Any) -> bool:
    if isinstance(point, dict):
        x = point.get("x")
        y = point.get("y")
    elif isinstance(point, (list, tuple)) and len(point) == 2:
        x, y = point
    else:
        return False
    try:
        return 0 <= float(x) <= 1 and 0 <= float(y) <= 1
    except (TypeError, ValueError):
        return False


def protocol_files(root: Path) -> dict[str, Path]:
    return {
        "protocol_schema": root / PROTOCOL_SCHEMA_FILE,
        "selection_schema": root / SELECTION_SCHEMA_FILE,
        "intent": root / "ps_layer_intent_example.json",
        "as_built": root / "ps_layer_as_built_example.json",
    }


def load_protocol_examples(root: Path) -> dict[str, dict[str, Any]]:
    return {name: read_json(root / name) for name in PROTOCOL_EXAMPLE_FILES}


def validate_protocol_schema_documents(root: Path) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    protocol_documents_validated: list[str] = []
    selection_contexts_validated = 0

    try:
        protocol_schema = read_json(root / PROTOCOL_SCHEMA_FILE)
        selection_schema = read_json(root / SELECTION_SCHEMA_FILE)
        Draft202012Validator.check_schema(protocol_schema)
        Draft202012Validator.check_schema(selection_schema)
    except Exception as exc:  # pragma: no cover - exercised by integration script paths
        return {
            "schema_name": "ps_layer_schema_validation_report",
            "status": "failed",
            "protocol_documents_validated": protocol_documents_validated,
            "selection_contexts_validated": selection_contexts_validated,
            "errors": [{"document": "schema", "path": "", "message": str(exc)}],
        }

    protocol_validator = Draft202012Validator(protocol_schema)
    selection_validator = Draft202012Validator(selection_schema)

    for file_name in PROTOCOL_EXAMPLE_FILES:
        path = root / file_name
        try:
            payload = read_json(path)
        except Exception as exc:
            errors.append({"document": file_name, "path": "", "message": str(exc)})
            continue
        document_errors = _schema_errors(protocol_validator, payload, file_name)
        errors.extend(document_errors)
        if not document_errors:
            protocol_documents_validated.append(file_name)
        for index, context in enumerate(payload.get("selection_patch_contexts", [])):
            wrapped = {"schema_name": "selection_patch_context_v1", "schema_version": "1.0.0", **context}
            context_errors = _schema_errors(selection_validator, wrapped, f"{file_name}#selection_patch_contexts/{index}")
            errors.extend(context_errors)
            if not context_errors:
                selection_contexts_validated += 1

    return {
        "schema_name": "ps_layer_schema_validation_report",
        "status": "passed" if not errors else "failed",
        "protocol_schema_path": str(root / PROTOCOL_SCHEMA_FILE),
        "selection_schema_path": str(root / SELECTION_SCHEMA_FILE),
        "protocol_documents_validated": protocol_documents_validated,
        "selection_contexts_validated": selection_contexts_validated,
        "errors": errors,
    }


def _schema_errors(validator: Draft202012Validator, payload: Any, document: str) -> list[dict[str, Any]]:
    return [
        {"document": document, "path": "/".join(str(part) for part in error.absolute_path), "message": error.message}
        for error in sorted(validator.iter_errors(payload), key=lambda item: list(item.absolute_path))
    ]
