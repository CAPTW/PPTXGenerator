"""Optional source-bound visual-review claims, with no adjudication authority.

The fixed local file is an explicit opt-in. Its absence changes no job bytes;
its presence requires a structurally consistent review of existing observations.
Roles and declared visual-review provenance follow the compatible VSC concepts,
but this is not a VSC assessment, authenticated approval, or execution plan.
Complete coverage means every listed observation was addressed, not that the
image is fully segmented or any semantic conflict is resolved.

Input: schema_name/version, workflow_id/slide_number/slide_id/request_id,
source_png_sha256, semantic_sidecar_sha256, measurement_inventory_sha256,
region_candidate_evidence_sha256 (canonical content_sha256), canvas_px and
canvas_rgb_sha256; origin/method and reviewer {name, reviewed_at}; coverage
(partial/complete); decisions [{collection, observation_id, role, reason}];
and the four exact false AUTHORITY fields. Collections address text_blocks,
suppressed_text or region_candidate_evidence.candidates. Roles are claims, not
permitted actions. Opted-in text_alternative_evidence.observations and linked
legacy assemblies always remain needs_review, regardless of a declared role.
Omitted, mixed, uncertain and conflicting observations stay
needs_review. A 'recorded' row only means its claim was transported intact.
"""
from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime
from fractions import Fraction
from pathlib import Path
from typing import Any

from ..errors import DeckCompilerError
from ..identity import content_sha256
from .raw_measure_batch import (validate_region_candidate_evidence,
    validate_text_alternative_evidence, TEXT_ALTERNATIVE_COLLECTION)
from .vector_preflight import _semantic_boxes


REVIEW_NAME = "region_classification_review.json"
CANDIDATE_COLLECTION = "region_candidate_evidence.candidates"
ROLES = {"text", "graphic", "mixed", "uncertain"}
AUTHORITY = {key: False for key in (
    "text_removal", "native_admission", "vector_eligibility", "quality_accepted")}


def bind_region_classification_review(
    root: Path, job: dict[str, Any], work_dir: Path
) -> dict[str, Any] | None:
    """Bind optional review claims; never rewrite evidence or approve an effect."""
    path = work_dir / REVIEW_NAME
    if not path.exists() and not path.is_symlink():
        return None
    try:
        root = root.resolve()
        if path.is_symlink() or not path.resolve().is_relative_to(root) or not path.is_file():
            raise ValueError("review must be a local regular file, not a symlink")
        data = path.read_bytes()
        review = _json_object(data)
        source = _bound_path(root, job["source_png"], "source_png")
        _bound_path(root, job["semantic_sidecar"], "semantic_sidecar")
        inventory_ref = job["vector_preflight"]["measurement_inventory"]
        inventory = _json_object(_bound_path(root, inventory_ref, "measurement_inventory").read_bytes())
        validate_region_candidate_evidence(inventory, source, required=True)
        validate_text_alternative_evidence(inventory, source)
        evidence = inventory["region_candidate_evidence"]
        frame = evidence["canvas_px"]
        if any(type(job["source_png"].get(key)) is not int or job["source_png"][key] != frame[axis]
               for key, axis in (("width", "w"), ("height", "h"))):
            raise ValueError("job dimensions do not match native review frame")
        if content_sha256(inventory.get("canvas_px")) != content_sha256(frame):
            raise ValueError("measurement inventory frame mismatch")
        # Reuse the unchanged protected-text geometry and OCR-failure contract.
        _semantic_boxes(inventory, frame["w"], frame["h"])
        expected = {
            "schema_name": "codex_region_classification_review", "schema_version": "1.0.0",
            "workflow_id": job["workflow_id"], "slide_number": job["slide_number"], "slide_id": job["slide_id"],
            "request_id": job["request_lineage"]["request_id"],
            "source_png_sha256": job["source_png"]["sha256"],
            "semantic_sidecar_sha256": job["semantic_sidecar"]["sha256"],
            "measurement_inventory_sha256": inventory_ref["sha256"],
            "region_candidate_evidence_sha256": content_sha256(evidence),
            "canvas_px": frame, "canvas_rgb_sha256": evidence["canvas_rgb_sha256"],
        }
        _exact(review, set(expected) | {"origin", "method", "reviewer", "coverage", "authority", "decisions"}, "review")
        for key, value in expected.items():
            if content_sha256(review[key]) != content_sha256(value):
                raise ValueError(f"review {key} does not match this job's source evidence")
        if (review["origin"], review["method"]) not in (
            ("assistant_mediated", "assistant_visual_review"), ("user_review", "user_visual_region_review")
        ):
            raise ValueError("review requires declared visual-review origin and method")
        reviewer = review["reviewer"]
        _exact(reviewer, {"name", "reviewed_at"}, "reviewer")
        _nonempty(reviewer["name"], "reviewer name")
        date = reviewer["reviewed_at"]
        if not isinstance(date, str) or datetime.strptime(date, "%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%dT%H:%M:%SZ") != date:
            raise ValueError("reviewer reviewed_at must be a UTC timestamp")
        _exact(review["authority"], set(AUTHORITY), "authority")
        if any(value is not False for value in review["authority"].values()):
            raise ValueError("review must grant no authority")
        if review["coverage"] not in ("partial", "complete"):
            raise ValueError("review coverage must be partial or complete")
        observations = _observations(inventory)
        decisions = review["decisions"]
        if not isinstance(decisions, list):
            raise ValueError("review decisions must be an array")
        by_id = {}
        for row in decisions:
            _exact(row, {"collection", "observation_id", "role", "reason"}, "review decision")
            _nonempty(row["collection"], "collection")
            _nonempty(row["observation_id"], "observation_id")
            ident = (row["collection"], row["observation_id"])
            if ident not in observations or ident in by_id:
                raise ValueError("unknown or duplicate reviewed observation identity")
            if not isinstance(row["role"], str) or row["role"] not in ROLES:
                raise ValueError("review role must be text, graphic, mixed or uncertain")
            _nonempty(row["reason"], "review reason")
            by_id[ident] = row
        missing = [ident for ident in observations if ident not in by_id]
        if review["coverage"] == "complete" and missing:
            raise ValueError("complete coverage requires every source observation identity")
        conflicts, pending = _conflicts(observations, by_id)
        pending.update(missing)
        alternative_evidence = inventory.get("text_alternative_evidence")
        if alternative_evidence is not None:
            unresolved_blocks = {row["block_id"] for row in alternative_evidence["legacy_assemblies"]}
            unresolved = [key for key in observations if key[0] == TEXT_ALTERNATIVE_COLLECTION
                or (key[0] in ("text_blocks", "suppressed_text") and key[1] in unresolved_blocks)]
            pending.update(unresolved)
            conflicts.extend({"reason": "unresolved_text_alternative_or_legacy_assembly", "observations": [_ref(key)]}
                             for key in unresolved)
        return {
            "status": "STRUCTURALLY_BOUND_REVIEW",
            "review_artifact": {"path": path.resolve().relative_to(root).as_posix(),
                                "sha256": hashlib.sha256(data).hexdigest()},
            "provenance_attestation": "unverified_declarations",
            "semantic_truth_verified": False,
            "scope": "text_observations_and_unadjudicated_candidates",
            "coverage": {"declared": review["coverage"], "observation_count": len(observations),
                         "reviewed_count": len(by_id), "unreviewed": [_ref(i) for i in missing],
                         "needs_review": [_ref(i) for i in observations if i in pending]},
            "decisions": [{**copy.deepcopy(row), "review_status": "needs_review" if ident in pending else "recorded"}
                          for ident, row in by_id.items()],
            "conflicts": conflicts, "authority": AUTHORITY.copy(),
        }
    except (OSError, ValueError, TypeError, KeyError, DeckCompilerError) as exc:
        raise DeckCompilerError(
            code="DC_REGION_CLASSIFICATION_REVIEW_INVALID", stage="reconstruction_job_preparation",
            message=f"region classification review is invalid: {exc}", artifact_path=path.as_posix(),
        ) from exc


def _observations(inventory: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    result = {}
    for collection in ("text_blocks", "suppressed_text", CANDIDATE_COLLECTION):
        rows = (inventory["region_candidate_evidence"]["candidates"] if collection == CANDIDATE_COLLECTION
                else inventory.get(collection, []))
        for row in rows:
            ident = row.get("candidate_id" if collection == CANDIDATE_COLLECTION else "id")
            _nonempty(ident, "source observation identity")
            key = (collection, ident)
            if key in result:
                raise ValueError("duplicate source observation identity")
            result[key] = (row["measurement"] if collection == CANDIDATE_COLLECTION else row)["bbox_px"]
    for row in inventory.get("text_alternative_evidence", {}).get("observations", []):
        key = (TEXT_ALTERNATIVE_COLLECTION, row["observation_id"])
        if key in result:
            raise ValueError("duplicate text alternative identity")
        result[key] = row["bbox_px"]
    return result


def _conflicts(observations, decisions):
    """Record disagreement; overlap is not semantic truth or removal permission."""
    conflicts = []
    pending = {key for key, row in decisions.items() if row["role"] in {"mixed", "uncertain"}}

    def add(reason, *identities):
        conflicts.append({"reason": reason, "observations": [_ref(i) for i in identities]})
        pending.update(identities)

    for key, row in decisions.items():
        if key[0] != CANDIDATE_COLLECTION and row["role"] in {"graphic", "mixed"}:
            add("protected_text_classified_nontext", key)
        if key[0] == CANDIDATE_COLLECTION and row["role"] in {"graphic", "mixed"}:
            for other, box in observations.items():
                if other[0] != CANDIDATE_COLLECTION and _overlaps(observations[key], box):
                    add("graphic_candidate_overlaps_protected_text", key, other)
    keys = list(decisions)
    for index, key in enumerate(keys):
        for other in keys[index + 1:]:
            if {decisions[key]["role"], decisions[other]["role"]} == {"text", "graphic"} and _overlaps(observations[key], observations[other]):
                add("inconsistent_overlap_roles", key, other)
    return conflicts, pending


def _overlaps(left, right):
    # Exact arithmetic avoids turning a small positive overlap into a touch.
    return all(max(Fraction(left[axis]), Fraction(right[axis])) <
               min(Fraction(left[axis]) + Fraction(left[size]), Fraction(right[axis]) + Fraction(right[size]))
               for axis, size in (("x", "w"), ("y", "h")))


def _ref(identity):
    return {"collection": identity[0], "observation_id": identity[1]}


def _exact(value, keys, label):
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError(f"{label} must have exactly {sorted(keys)}")


def _nonempty(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a nonempty string")


def _json_object(data):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate JSON key {key}")
            result[key] = value
        return result

    value = json.loads(data, object_pairs_hook=pairs)
    if not isinstance(value, dict):
        raise ValueError("JSON artifact must be an object")
    content_sha256(value)  # Reject nonfinite JSON values.
    return value


def _bound_path(root, reference, label):
    if not isinstance(reference, dict) or not isinstance(reference.get("path"), str):
        raise ValueError(f"{label} artifact reference is invalid")
    path = (root / reference["path"]).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError(f"{label} must be an existing artifact inside the runtime")
    if hashlib.sha256(path.read_bytes()).hexdigest() != reference.get("sha256"):
        raise ValueError(f"{label} sha256 mismatch")
    return path
