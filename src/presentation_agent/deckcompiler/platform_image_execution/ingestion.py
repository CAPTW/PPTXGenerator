"""Local ingestion and independent verification for platform-generated images.

The platform tool call itself is intentionally outside repository code. This
module accepts already-retrieved local bytes, normalizes them without stretching,
and emits hash-bound evidence records.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image

from ..errors import DeckCompilerError
from ..identity import content_sha256, stable_id
from ..manifest_io import read_json, write_json
from .contracts import hash_bound_payload, verify_hash_bound_payload


@dataclass(frozen=True, slots=True)
class FinalizedImageAttempt:
    execution_record_path: Path
    verification_report_path: Path
    visual_review_path: Path
    normalized_path: Path
    execution_record: dict[str, Any]
    verification: dict[str, Any]
    review: dict[str, Any]


@dataclass(frozen=True, slots=True)
class RecordedAttemptAudit:
    valid: bool
    issues: tuple[str, ...]


def _error(code: str, message: str, *, path: Path | None = None) -> DeckCompilerError:
    return DeckCompilerError(
        code=code,
        stage="phase4_platform_image_ingestion",
        message=message,
        artifact_path=path.as_posix() if path else None,
    )


def _inside(root: Path, path: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _relative(root: Path, path: Path) -> str:
    if not _inside(root, path):
        raise _error("DC_PHASE4_OUTPUT_PATH", "Image output path escapes the approved runtime root.", path=path)
    return path.resolve().relative_to(root.resolve()).as_posix()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _inspect_image(path: Path) -> dict[str, Any]:
    try:
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            image_format = (image.format or "unknown").upper()
            width, height = image.size
    except (OSError, ValueError) as exc:
        raise _error("DC_PHASE4_IMAGE_DECODE", f"Generated image cannot be decoded: {exc}", path=path) from exc
    return {
        "format": image_format,
        "dimensions": {"width": width, "height": height},
        "file_size_bytes": path.stat().st_size,
        "sha256": _file_sha256(path),
    }


def normalize_generated_image(original_path: Path, normalized_path: Path) -> dict[str, Any]:
    """Create an exact 16:9 PNG without non-uniform scaling or overwrite."""

    original = Path(original_path).resolve()
    normalized = Path(normalized_path).resolve()
    if not original.is_file():
        raise _error("DC_PHASE4_OUTPUT_MISSING", "Retrieved platform output is missing.", path=original)
    if normalized.exists():
        raise _error("DC_PHASE4_OUTPUT_EXISTS", "Refusing to overwrite an existing normalized output.", path=normalized)
    original_info = _inspect_image(original)
    width = original_info["dimensions"]["width"]
    height = original_info["dimensions"]["height"]

    scale = min(width // 16, height // 9)
    if scale < 1:
        raise _error("DC_PHASE4_IMAGE_DIMENSIONS", "Image is too small to normalize to 16:9.", path=original)
    crop_width, crop_height = scale * 16, scale * 9
    left = (width - crop_width) // 2
    top = (height - crop_height) // 2
    crop_box = (left, top, left + crop_width, top + crop_height)
    requires_crop = (crop_width, crop_height) != (width, height)
    requires_resize = crop_width < 1600 or crop_height < 900
    final_size = (1600, 900) if requires_resize else (crop_width, crop_height)

    normalized.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(original) as image:
        output = image.crop(crop_box) if requires_crop else image.copy()
        if requires_resize:
            output = output.resize(final_size, Image.Resampling.LANCZOS)
        if output.mode not in {"RGB", "RGBA"}:
            output = output.convert("RGBA" if "A" in output.getbands() else "RGB")
        output.save(normalized, format="PNG", optimize=True)

    normalized_info = _inspect_image(normalized)
    normalized_width = normalized_info["dimensions"]["width"]
    normalized_height = normalized_info["dimensions"]["height"]
    if normalized_width * 9 != normalized_height * 16:
        normalized.unlink(missing_ok=True)
        raise _error("DC_PHASE4_ASPECT_RATIO", "Normalized output is not exact 16:9.", path=normalized)
    if normalized_width < 1600 or normalized_height < 900:
        normalized.unlink(missing_ok=True)
        raise _error("DC_PHASE4_MINIMUM_RESOLUTION", "Normalized output is below 1600x900.", path=normalized)

    if requires_crop and requires_resize:
        transformation_type = "aspect_preserving_crop_and_uniform_resize"
    elif requires_crop:
        transformation_type = "aspect_preserving_crop"
    elif requires_resize:
        transformation_type = "uniform_resize"
    else:
        transformation_type = "png_reencode_only"
    return {
        "original_format": original_info["format"],
        "original_dimensions": original_info["dimensions"],
        "original_file_size_bytes": original_info["file_size_bytes"],
        "original_sha256": original_info["sha256"],
        "normalized_format": normalized_info["format"],
        "normalized_dimensions": normalized_info["dimensions"],
        "normalized_file_size_bytes": normalized_info["file_size_bytes"],
        "normalized_sha256": normalized_info["sha256"],
        "transformation": {
            "type": transformation_type,
            "crop_box": list(crop_box),
            "uniform_resize_to": list(final_size) if requires_resize else None,
            "stretch_used": False,
            "nonuniform_resize_used": False,
        },
    }


def _write_new_json(path: Path, payload: dict[str, Any]) -> Path:
    if path.exists():
        raise _error("DC_PHASE4_RECORD_EXISTS", "Refusing to overwrite an existing attempt record.", path=path)
    return write_json(path, payload)


def finalize_platform_image_attempt(
    *,
    phase4_run: Path,
    prompt_path: Path,
    seal_path: Path,
    reviewer: str,
    visual_checks: dict[str, bool],
    findings: list[str],
    visual_review_status: str,
    selected: bool,
    request_timestamp: str,
    completion_timestamp: str,
) -> FinalizedImageAttempt:
    """Finalize one already-executed attempt and write immutable evidence."""

    root = Path(phase4_run).resolve()
    prompt_file = Path(prompt_path).resolve()
    seal_file = Path(seal_path).resolve()
    if not root.is_dir() or not _inside(root, prompt_file) or not _inside(root, seal_file):
        raise _error("DC_PHASE4_OUTPUT_PATH", "Prompt, seal, and output must remain inside the runtime root.")
    prompt = read_json(prompt_file)
    seal = read_json(seal_file)
    prompt_value = dict(prompt)
    expected_prompt_hash = prompt_value.pop("prompt_hash", None)
    if not isinstance(expected_prompt_hash, str) or content_sha256(prompt_value) != expected_prompt_hash:
        raise _error("DC_PHASE4_PROMPT_HASH", "Prompt artifact hash is invalid.", path=prompt_file)
    relation_fields = ("request_id", "target_artifact_id", "prompt_id", "prompt_hash")
    if any(seal.get(field) != prompt.get(field) for field in relation_fields):
        raise _error("DC_PHASE4_REQUEST_RELATION", "Attempt seal does not match the prompt artifact.", path=seal_file)
    if seal.get("execution_mode") != "platform_managed_tool" or seal.get("platform_tool_id") != "image_gen.imagegen":
        raise _error("DC_PHASE4_EXECUTION_MODE", "Attempt is not sealed for the built-in platform image tool.", path=seal_file)
    if seal.get("external_transport_used") is not False or seal.get("credential_lookups") != 0:
        raise _error("DC_PHASE4_EXTERNAL_EXECUTION", "External transport or credential lookup is forbidden.", path=seal_file)
    if visual_review_status not in {"ACCEPTED_FOR_PHASE4", "REJECTED"}:
        raise _error("DC_PHASE4_REVIEW_STATE", "Unknown visual review state.")
    if selected != (visual_review_status == "ACCEPTED_FOR_PHASE4"):
        raise _error("DC_PHASE4_REVIEW_STATE", "Only an accepted attempt may be selected.")

    output_relative = seal.get("expected_output_relative_path")
    if not isinstance(output_relative, str) or Path(output_relative).is_absolute():
        raise _error("DC_PHASE4_OUTPUT_PATH", "Expected output path must be runtime-relative.", path=seal_file)
    original = (root / output_relative).resolve()
    _relative(root, original)
    if not original.is_file():
        raise _error("DC_PHASE4_OUTPUT_MISSING", "Platform output bytes are not locally retrievable.", path=original)
    normalized = original.with_name("normalized.png")

    attempt_id = seal["attempt_id"]
    execution_path = root / "records" / "execution" / f"{attempt_id}.json"
    verification_path = root / "records" / "verification" / f"{attempt_id}.json"
    review_path = root / "records" / "visual_review" / f"{attempt_id}.json"
    for record_path in (execution_path, verification_path, review_path, normalized):
        if record_path.exists():
            code = "DC_PHASE4_OUTPUT_EXISTS" if record_path == normalized else "DC_PHASE4_RECORD_EXISTS"
            raise _error(code, "Refusing to overwrite an existing attempt artifact.", path=record_path)

    image = normalize_generated_image(original, normalized)
    record_id = stable_id("imageexecution", attempt_id, prompt["prompt_hash"], image["normalized_sha256"])
    output = {
        "target_type": seal["target_type"],
        "prompt_id": prompt["prompt_id"],
        "prompt_hash": prompt["prompt_hash"],
        "prompt_relative_path": _relative(root, prompt_file),
        "seal_relative_path": _relative(root, seal_file),
        "request_timestamp": request_timestamp,
        "completion_timestamp": completion_timestamp,
        "original_relative_path": _relative(root, original),
        "original_format": image["original_format"],
        "original_dimensions": image["original_dimensions"],
        "original_file_size_bytes": image["original_file_size_bytes"],
        "original_sha256": image["original_sha256"],
        "normalized_relative_path": _relative(root, normalized),
        "normalized_format": image["normalized_format"],
        "normalized_dimensions": image["normalized_dimensions"],
        "normalized_file_size_bytes": image["normalized_file_size_bytes"],
        "normalized_sha256": image["normalized_sha256"],
        "transformation": image["transformation"],
        "verification_status": "VERIFIED",
        "visual_review_status": visual_review_status,
        "selected": selected,
        "rejection_reason": None if selected else "; ".join(findings),
        "prior_attempt_id": seal.get("prior_attempt_id"),
        "reference_artifacts": seal.get("reference_artifacts", []),
    }
    execution = hash_bound_payload(
        {
            "schema_name": "platform_image_execution_record",
            "schema_version": "1.0.0",
            "record_id": record_id,
            "attempt_id": attempt_id,
            "request_id": prompt["request_id"],
            "target_artifact_id": prompt["target_artifact_id"],
            "execution_mode": "platform_managed_tool",
            "platform_tool_id": "image_gen.imagegen",
            "platform_tool_channel": "commentary",
            "image_model": "not_exposed_by_tool",
            "tool_call_id": "not_exposed",
            "external_provider_id": None,
            "external_transport_used": False,
            "repository_network_calls": 0,
            "credential_lookups": 0,
            "platform_tool_invocation_count": 1,
            "actual_generation": True,
            "output": output,
        },
        "record_hash",
    )
    verification = hash_bound_payload(
        {
            "schema_name": "platform_image_verification_report",
            "schema_version": "1.0.0",
            "verification_id": stable_id("imageverification", record_id),
            "record_id": record_id,
            "attempt_id": attempt_id,
            "target_artifact_id": prompt["target_artifact_id"],
            "actual_bytes_retrievable": True,
            "decode_valid": True,
            "format": image["normalized_format"],
            "width": image["normalized_dimensions"]["width"],
            "height": image["normalized_dimensions"]["height"],
            "aspect_ratio_valid": True,
            "minimum_resolution_valid": True,
            "file_size_bytes": image["normalized_file_size_bytes"],
            "sha256": image["normalized_sha256"],
            "request_relation_valid": True,
            "record_hash_valid": True,
            "output_path_inside_runtime_root": True,
            "status": "VERIFIED",
        },
        "report_hash",
    )
    review = hash_bound_payload(
        {
            "schema_name": "platform_image_visual_review",
            "schema_version": "1.0.0",
            "review_id": stable_id("imagereview", attempt_id, visual_review_status, visual_checks, findings),
            "attempt_id": attempt_id,
            "target_artifact_id": prompt["target_artifact_id"],
            "reviewer": reviewer,
            "checks": visual_checks,
            "findings": findings,
            "visual_review_status": visual_review_status,
            "selected": selected,
        },
        "review_hash",
    )
    _write_new_json(execution_path, execution)
    _write_new_json(verification_path, verification)
    _write_new_json(review_path, review)
    return FinalizedImageAttempt(
        execution_record_path=execution_path,
        verification_report_path=verification_path,
        visual_review_path=review_path,
        normalized_path=normalized,
        execution_record=execution,
        verification=verification,
        review=review,
    )


def verify_recorded_image_attempt(phase4_run: Path, execution_record_path: Path) -> RecordedAttemptAudit:
    """Recompute hashes, dimensions, and request linkage from recorded bytes."""

    root = Path(phase4_run).resolve()
    record_path = Path(execution_record_path).resolve()
    issues: list[str] = []
    if not _inside(root, record_path):
        return RecordedAttemptAudit(False, ("execution_record_path_outside_runtime",))
    try:
        record = read_json(record_path)
    except (OSError, ValueError) as exc:
        return RecordedAttemptAudit(False, (f"execution_record_unreadable:{exc}",))
    if not verify_hash_bound_payload(record, "record_hash"):
        issues.append("record_hash_mismatch")
    output = record.get("output", {})
    for prefix in ("original", "normalized"):
        relative = output.get(f"{prefix}_relative_path")
        if not isinstance(relative, str):
            issues.append(f"{prefix}_path_missing")
            continue
        path = (root / relative).resolve()
        if not _inside(root, path):
            issues.append(f"{prefix}_path_outside_runtime")
            continue
        if not path.is_file():
            issues.append(f"{prefix}_missing")
            continue
        try:
            info = _inspect_image(path)
        except DeckCompilerError:
            issues.append(f"{prefix}_decode_invalid")
            continue
        if info["sha256"] != output.get(f"{prefix}_sha256"):
            issues.append(f"{prefix}_sha256_mismatch")
        if info["dimensions"] != output.get(f"{prefix}_dimensions"):
            issues.append(f"{prefix}_dimensions_mismatch")
        if info["file_size_bytes"] != output.get(f"{prefix}_file_size_bytes"):
            issues.append(f"{prefix}_file_size_mismatch")
    prompt_relative = output.get("prompt_relative_path")
    if not isinstance(prompt_relative, str):
        issues.append("prompt_path_missing")
    else:
        prompt_path = (root / prompt_relative).resolve()
        if not _inside(root, prompt_path) or not prompt_path.is_file():
            issues.append("prompt_missing_or_outside_runtime")
        else:
            prompt = read_json(prompt_path)
            prompt_value = dict(prompt)
            prompt_hash = prompt_value.pop("prompt_hash", None)
            if prompt_hash != output.get("prompt_hash") or content_sha256(prompt_value) != prompt_hash:
                issues.append("prompt_hash_mismatch")
            if prompt.get("request_id") != record.get("request_id"):
                issues.append("request_id_mismatch")
            if prompt.get("target_artifact_id") != record.get("target_artifact_id"):
                issues.append("target_artifact_id_mismatch")
    if record.get("external_transport_used") is not False:
        issues.append("external_transport_used")
    if record.get("credential_lookups") != 0:
        issues.append("credential_lookup_nonzero")
    return RecordedAttemptAudit(not issues, tuple(issues))


__all__ = [
    "FinalizedImageAttempt",
    "RecordedAttemptAudit",
    "finalize_platform_image_attempt",
    "normalize_generated_image",
    "verify_recorded_image_attempt",
]
