"""Bind explicit content references to existing measured objects.

This consumer keeps codex_semantic_sidecar 1.1.0 intact. It does not discover
associations, measure geometry, translate VSC sampling envelopes into measured
coordinates, flatten structured content, author fragments, or grant QA pass.
The caller remains responsible for the existing reconstruction/preflight gates.
"""
from __future__ import annotations

import copy
import hashlib
import math
import re
from pathlib import Path
from typing import Any

from ..errors import DeckCompilerError
from ..manifest_io import read_json


ASSOCIATION_NAME = "semantic_geometry_associations.json"


def bind_semantic_geometry(root: Path, job: dict[str, Any], work_dir: Path) -> dict[str, Any]:
    """Return a hash-bound job input, or an explicit unresolved status.

    An association addresses content by a JSON pointer inside the live sidecar.
    Optional object IDs must already exist at the supplied identity pointer.
    Measurement collection and ID must both be explicit. No positional, OCR
    equality, or nearest-box matching is permitted here.
    """
    root = root.resolve()
    path = work_dir / ASSOCIATION_NAME
    if not path.is_file():
        return {
            "status": "UNRESOLVED",
            "reason": "no_explicit_content_geometry_associations",
            "bindings": [],
            "coverage": "explicit_associations_only",
            "authoring_and_render_qa_required": True,
        }

    association_ref = _artifact(root, path)
    association = read_json(path)
    inventory_ref = job["vector_preflight"]["measurement_inventory"]
    expected = {
        "workflow_id": job["workflow_id"],
        "slide_number": job["slide_number"],
        "slide_id": job["slide_id"],
        "request_id": job["request_lineage"]["request_id"],
        "source_png_sha256": job["source_png"]["sha256"],
        "semantic_sidecar_sha256": job["semantic_sidecar"]["sha256"],
        "measurement_inventory_sha256": inventory_ref["sha256"],
    }
    for key, value in expected.items():
        if type(association.get(key)) is not type(value) or association.get(key) != value:
            raise _error(f"association {key} does not match this reconstruction job", path)

    _read_bound_artifact(root, job["source_png"], "source_png", json_object=False)
    sidecar = _read_bound_artifact(root, job["semantic_sidecar"], "semantic_sidecar")
    inventory = _read_bound_artifact(root, inventory_ref, "measurement_inventory")
    for key in ("workflow_id", "slide_number", "slide_id", "request_id"):
        if sidecar.get(key) != expected[key]:
            raise _error(f"semantic sidecar {key} mismatch", path)
    if sidecar.get("schema_name") != "codex_semantic_sidecar" or sidecar.get("schema_version") != "1.1.0":
        raise _error("only the current codex_semantic_sidecar 1.1.0 is supported", path)
    width, height = job["source_png"]["width"], job["source_png"]["height"]
    if inventory.get("canvas_px") != {"w": width, "h": height}:
        raise _error("measurement inventory must preserve the source native canvas", path)
    entries = association.get("bindings")
    if not isinstance(entries, list) or not entries:
        raise _error("explicit associations require non-empty bindings", path)

    output = []
    seen_content: list[str] = []
    seen_geometry: set[tuple[str, str]] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise _error("each binding must be an object", path)
        pointer = entry.get("content_pointer")
        if not isinstance(pointer, str) or not (
            pointer == "/exact_title" or pointer == "/exact_on_slide_copy" or pointer.startswith("/exact_on_slide_copy/")
        ):
            raise _error("content_pointer must address exact on-slide content", path)
        if pointer.rsplit("/", 1)[-1] in {"id", "object_id", "slot_id", "block_id"}:
            raise _error("content_pointer cannot treat an object identity field as display content", path)
        value = _pointer(sidecar, pointer, "content_pointer", path)
        if any(pointer == other or pointer.startswith(other + "/") or other.startswith(pointer + "/") for other in seen_content):
            raise _error("duplicate or overlapping content_pointer", path)
        seen_content.append(pointer)

        collection, measured_id = entry.get("measurement_collection"), entry.get("measurement_id")
        if collection not in ("text_blocks", "regions") or not isinstance(measured_id, str) or not measured_id:
            raise _error("measurement_collection and measurement_id must explicitly name an existing object", path)
        rows = inventory.get(collection)
        if not isinstance(rows, list):
            raise _error(f"measurement collection {collection} is absent", path)
        matches = [(index, row) for index, row in enumerate(rows) if isinstance(row, dict) and row.get("id") == measured_id]
        if len(matches) != 1:
            raise _error(f"measurement_id {measured_id!r} must identify exactly one measured object", path)
        key = (collection, measured_id)
        if key in seen_geometry:
            raise _error("duplicate measurement association", path)
        seen_geometry.add(key)
        index, measured = matches[0]
        _validate_bbox(measured.get("bbox_px"), width, height, path)
        bound = {
            "content_pointer": pointer,
            "content_value": copy.deepcopy(value),
            "measurement_collection": collection,
            "measurement_id": measured_id,
            "measurement_pointer": f"/{collection}/{index}",
        }
        identity_pointer = entry.get("content_identity_pointer")
        if identity_pointer is not None:
            identity = _pointer(sidecar, identity_pointer, "content_identity_pointer", path)
            owner = pointer if isinstance(value, dict) else pointer.rsplit("/", 1)[0]
            if (
                identity_pointer.rsplit("/", 1)[0] != owner
                or identity_pointer.rsplit("/", 1)[1] not in {"id", "object_id", "slot_id", "block_id"}
                or not isinstance(identity, str) or not identity.strip()
            ):
                raise _error("content_identity_pointer must name an existing ID on this content object", path)
            bound["content_identity"] = {"pointer": identity_pointer, "value": identity}
        output.append(bound)

    return {
        "status": "EXPLICIT_ASSOCIATIONS_BOUND",
        "association_artifact": association_ref,
        "semantic_sidecar": copy.deepcopy(job["semantic_sidecar"]),
        "measurement_inventory": copy.deepcopy(inventory_ref),
        "source_png_sha256": job["source_png"]["sha256"],
        "bindings": output,
        "coverage": "explicit_associations_only",
        "authoring_and_render_qa_required": True,
    }


def _pointer(document: Any, pointer: Any, label: str, path: Path) -> Any:
    if not isinstance(pointer, str) or not pointer.startswith("/") or re.search(r"~(?:[^01]|$)", pointer):
        raise _error(f"{label} must be a valid JSON pointer", path)
    value = document
    try:
        for raw in pointer[1:].split("/"):
            key = raw.replace("~1", "/").replace("~0", "~")
            if isinstance(value, dict):
                value = value[key]
            elif isinstance(value, list) and re.fullmatch(r"0|[1-9][0-9]*", key):
                value = value[int(key)]
            else:
                raise KeyError(key)
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise _error(f"{label} does not exist in the approved sidecar: {pointer}", path) from exc
    return value


def _artifact(root: Path, path: Path) -> dict[str, str]:
    resolved = path.resolve()
    if not resolved.is_relative_to(root):
        raise _error("artifact path escapes runtime root", path)
    return {"path": resolved.relative_to(root).as_posix(), "sha256": hashlib.sha256(resolved.read_bytes()).hexdigest()}


def _read_bound_artifact(root: Path, reference: Any, label: str, *, json_object: bool = True) -> Any:
    if not isinstance(reference, dict) or not isinstance(reference.get("path"), str):
        raise _error(f"{label} artifact reference is invalid")
    path = root / reference["path"]
    actual = _artifact(root, path)
    if actual["sha256"] != reference.get("sha256"):
        raise _error(f"{label} sha256 mismatch", path)
    return read_json(path) if json_object else None


def _validate_bbox(bbox: Any, width: int, height: int, path: Path) -> None:
    if not isinstance(bbox, dict) or any(type(bbox.get(key)) not in (int, float) or not math.isfinite(bbox[key]) for key in ("x", "y", "w", "h")):
        raise _error("measured object requires a finite existing bbox_px", path)
    x, y, w, h = (bbox[key] for key in ("x", "y", "w", "h"))
    if x < 0 or y < 0 or w <= 0 or h <= 0 or x + w > width or y + h > height:
        raise _error("measured bbox_px must be positive and inside the native canvas", path)


def _error(message: str, path: Path | None = None) -> DeckCompilerError:
    return DeckCompilerError(
        code="DC_SEMANTIC_GEOMETRY_BINDING_INVALID", stage="reconstruction_job_preparation",
        message=message, artifact_path=path.as_posix() if path else None,
        remediation_hint="Provide explicit approved-sidecar references and existing measured-object IDs for this slide; do not infer or fabricate missing associations.",
    )
