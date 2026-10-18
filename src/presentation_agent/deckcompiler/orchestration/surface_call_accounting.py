"""Optional accounting of source observations against recorded surface calls.

The fixed per-slide file is an explicit post-render opt-in. Absence is a no-op.
It requires a job-bound region_classification_review, but that review's roles,
glyph memberships and decorative/background purposes remain unauthenticated
claims. A complete ledger does not prove semantic truth, exact text, visual
fidelity, source segmentation completeness, or serialized/native PPTX objects.
The official manifest records surface calls; it does not attest serialization.

Contract: schema_name/version, job_id/job_content_hash/slide_number; bindings
of source PNG, inventory, review, fragment, integrated JS, native manifest and
render trace SHA256; groups [{group_id, source, glyph_members, objects, reason}],
unresolved [{source, disposition: unresolved|deferred, objects, reason}], extras
[{object, purpose: decorative|background|unresolved, reason}]; exact false
AUTHORITY fields. Source refs require {collection, observation_id}; object refs
require {pointer, object_sha256}. Pointers are /slides/N/objects/I in the exact
bound manifest. Every source observation and every object must be used once.
Explicit glyph members are reviewed text candidates of a protected-text group.
Unknown/conflicting observations can only appear in unresolved, even when a
surface call is associated with them. No OCR protection or vector policy changes.
"""
from __future__ import annotations

import hashlib
import math
import re
from pathlib import Path
from typing import Any

from ..errors import DeckCompilerError
from ..identity import content_sha256
from .region_classification_review import (
    CANDIDATE_COLLECTION,
    _bound_path,
    _exact,
    _json_object,
    _nonempty,
    _observations,
    bind_region_classification_review,
)


ACCOUNTING_NAME = "surface_call_accounting.json"
AUTHORITY = {key: False for key in (
    "semantic_truth", "text_removal", "native_admission", "vector_eligibility", "quality_accepted")}
GRAPHIC_TYPES = {"shape", "panel", "rule", "line", "icon", "image", "table", "chart", "badge", "callout"}


def validate_surface_call_accounting(
    root: Path, job: dict[str, Any], work_dir: Path
) -> dict[str, Any] | None:
    """Reconcile an optional ledger without giving its claims semantic authority."""
    path = work_dir / ACCOUNTING_NAME
    if not path.exists() and not path.is_symlink():
        return None
    try:
        root = root.resolve()
        data = _local_bytes(root, path)
        ledger = _json_object(data)
        review = bind_region_classification_review(root, job, work_dir)
        if review is None or content_sha256(review) != content_sha256(job.get("region_classification_review")):
            raise ValueError("accounting requires the unchanged job-bound classification review")
        inventory_ref = job["vector_preflight"]["measurement_inventory"]
        inventory = _json_object(_bound_path(root, inventory_ref, "measurement_inventory").read_bytes())
        observations = _observations(inventory)
        decisions = {(row["collection"], row["observation_id"]): row for row in review["decisions"]}
        slide = job["slide_number"]
        if type(slide) is not int or slide <= 0:
            raise ValueError("slide_number must be a positive integer")
        project = root / "pngtopptx-project"
        fragment = _local_bytes(root, work_dir / f"s{slide}.fragment.js")
        integrated = _local_bytes(root, project / "lib/slides.js")
        native_data = _local_bytes(root, project / "out/native_object_manifest.json")
        trace_data = _local_bytes(root, project / "out/render_trace.json")
        native, trace = _json_object(native_data), _json_object(trace_data)
        bindings = {
            "source_png_sha256": job["source_png"]["sha256"],
            "measurement_inventory_sha256": inventory_ref["sha256"],
            "review_artifact_sha256": review["review_artifact"]["sha256"],
            "fragment_sha256": _sha(fragment), "integrated_slides_sha256": _sha(integrated),
            "native_manifest_sha256": _sha(native_data), "render_trace_sha256": _sha(trace_data),
        }
        _exact(ledger, {"schema_name", "schema_version", "job_id", "job_content_hash", "slide_number",
                        "bindings", "groups", "unresolved", "extras", "authority"}, "surface-call accounting")
        expected = {"schema_name": "codex_surface_call_accounting", "schema_version": "1.0.0",
                    "job_id": job["job_id"], "job_content_hash": job["content_hash"], "slide_number": slide,
                    "bindings": bindings, "authority": AUTHORITY}
        for key, value in expected.items():
            if content_sha256(ledger[key]) != content_sha256(value):
                raise ValueError(f"accounting {key} does not match this job and its bound artifacts")
        if (trace.get("projectRoot") != project.resolve().as_posix()
                or not isinstance(trace.get("hashes"), dict)
                or trace["hashes"].get("slidesJs") != bindings["integrated_slides_sha256"]
                or trace.get("nativeObjectManifestHash") != bindings["native_manifest_sha256"]):
            raise ValueError("render trace does not bind the current project, integrated source and native manifest")
        if native.get("source") != "actual-render-surface-calls":
            raise ValueError("native manifest must record actual-render-surface-calls")
        slides = native.get("slides")
        if not isinstance(slides, dict) or not isinstance(slides.get(str(slide)), dict):
            raise ValueError("native manifest lacks this slide")
        objects = slides[str(slide)].get("objects")
        if not isinstance(objects, list):
            raise ValueError("native manifest objects must be an array")
        for obj in objects:
            _validate_object(obj)
        for key in ("groups", "unresolved", "extras"):
            if not isinstance(ledger[key], list):
                raise ValueError(f"accounting {key} must be an array")

        seen_sources: set[tuple[str, str]] = set()
        seen_objects: set[int] = set()
        group_ids: set[str] = set()

        def source_ref(value):
            _exact(value, {"collection", "observation_id"}, "source reference")
            _nonempty(value["collection"], "source collection")
            _nonempty(value["observation_id"], "source observation_id")
            ident = (value["collection"], value["observation_id"])
            if ident not in observations or ident in seen_sources:
                raise ValueError("unknown or duplicate source observation")
            seen_sources.add(ident)
            return ident

        def object_ref(value):
            _exact(value, {"pointer", "object_sha256"}, "object reference")
            pointer = value["pointer"]
            match = re.fullmatch(rf"/slides/{slide}/objects/(0|[1-9][0-9]*)", pointer) if isinstance(pointer, str) else None
            if match is None:
                raise ValueError("object pointer must select this slide with a canonical index")
            index = int(match.group(1))
            if index >= len(objects) or index in seen_objects:
                raise ValueError("missing or duplicate surface object pointer")
            obj = objects[index]
            if content_sha256(obj) != value["object_sha256"]:
                raise ValueError("object pointer sha256 does not match the bound manifest row")
            seen_objects.add(index)
            return obj

        def recorded_role(ident):
            row = decisions.get(ident)
            if row is None or row["review_status"] != "recorded" or row["role"] not in ("text", "graphic"):
                raise ValueError("unknown or disputed observations must remain unresolved/deferred")
            return row["role"]

        linked = 0
        for group in ledger["groups"]:
            _exact(group, {"group_id", "source", "glyph_members", "objects", "reason"}, "accounting group")
            _nonempty(group["group_id"], "group_id")
            _nonempty(group["reason"], "group reason")
            if group["group_id"] in group_ids:
                raise ValueError("duplicate group_id")
            group_ids.add(group["group_id"])
            primary = source_ref(group["source"])
            role = recorded_role(primary)
            members = group["glyph_members"]
            if not isinstance(members, list):
                raise ValueError("glyph_members must be an explicit array")
            if members and (role != "text" or primary[0] not in ("text_blocks", "suppressed_text")):
                raise ValueError("glyph members require a protected-text primary")
            for member in members:
                ident = source_ref(member)
                if ident[0] != CANDIDATE_COLLECTION or recorded_role(ident) != "text":
                    raise ValueError("glyph members must be uniquely linked reviewed text candidates")
            refs = group["objects"]
            if not isinstance(refs, list) or not refs:
                raise ValueError("a linked group must reference at least one surface object")
            for reference in refs:
                obj = object_ref(reference)
                if role == "text" and not (obj["type"] == "text" and obj["editable"] is True and obj["textLength"] > 0):
                    raise ValueError("text claims require nonempty editable text surface calls")
                if role == "graphic" and obj["type"] not in GRAPHIC_TYPES:
                    raise ValueError("graphic claims require non-text surface calls")
            linked += 1 + len(members)

        deferred = unresolved_objects = 0
        for row in ledger["unresolved"]:
            _exact(row, {"source", "disposition", "objects", "reason"}, "unresolved observation")
            source_ref(row["source"])
            _nonempty(row["reason"], "unresolved reason")
            if row["disposition"] not in ("unresolved", "deferred") or not isinstance(row["objects"], list):
                raise ValueError("unresolved observations require a disposition and explicit object array")
            deferred += row["disposition"] == "deferred"
            for reference in row["objects"]:
                object_ref(reference)
                unresolved_objects += 1
        for row in ledger["extras"]:
            _exact(row, {"object", "purpose", "reason"}, "extra object")
            _nonempty(row["reason"], "extra object reason")
            if row["purpose"] not in ("decorative", "background", "unresolved"):
                raise ValueError("extra objects require an explicit decorative/background/unresolved purpose")
            obj = object_ref(row["object"])
            if row["purpose"] != "unresolved" and obj["type"] not in GRAPHIC_TYPES:
                raise ValueError("text surface calls cannot be classified decorative/background")
            unresolved_objects += row["purpose"] == "unresolved"
        if seen_sources != set(observations):
            raise ValueError("accounting must cover every source observation explicitly")
        if seen_objects != set(range(len(objects))):
            raise ValueError("accounting must cover every surface object explicitly")
        return {
            "status": "SURFACE_CALLS_ACCOUNTED", "scope": "surface_calls_not_serialized_pptx",
            "artifact": {"path": path.resolve().relative_to(root).as_posix(), "sha256": _sha(data)},
            "bindings": bindings, "accounting_complete": True,
            "representation_status": "NOT_ESTABLISHED", "provenance_attestation": "unverified_declarations",
            "source_observation_count": len(observations), "surface_object_count": len(objects),
            "linked_observations": linked, "unresolved_observations": len(ledger["unresolved"]),
            "deferred_observations": deferred, "unresolved_surface_objects": unresolved_objects,
            "authority": AUTHORITY.copy(),
        }
    except (OSError, ValueError, TypeError, KeyError, OverflowError, DeckCompilerError) as exc:
        raise DeckCompilerError(
            code="DC_SURFACE_CALL_ACCOUNTING_INVALID", stage="reconstruction_completion",
            message=f"surface-call accounting is invalid: {exc}", artifact_path=path.as_posix(),
        ) from exc


def _local_bytes(root, path):
    if path.is_symlink() or not path.resolve().is_relative_to(root) or not path.is_file():
        raise ValueError("accounting dependencies must be local regular files, not symlinks")
    return path.read_bytes()


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _validate_object(obj):
    if not isinstance(obj, dict) or not isinstance(obj.get("type"), str) or obj["type"] not in GRAPHIC_TYPES | {"text"}:
        raise ValueError("unsupported native manifest surface object type")
    if type(obj.get("editable")) is not bool:
        raise ValueError("native manifest editable must be a boolean")
    for key in ("x", "y", "w", "h", "textLength"):
        value = obj.get(key)
        # Preserve signed geometry recorded by the official manifest; this is
        # accounting, not a new geometry/layout quality policy.
        if type(value) not in (int, float) or not math.isfinite(value) or (key == "textLength" and value < 0):
            raise ValueError(f"native manifest {key} must be a finite valid number")
