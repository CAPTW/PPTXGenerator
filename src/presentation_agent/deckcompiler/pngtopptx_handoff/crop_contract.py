"""Fail-closed adapter contract for official PNGtoPPTX crop artifacts.

The installed PNGtoPPTX SkillSet has no machine-readable crop-plan schema. Its
``make_crops.py`` loader and emitted ``assets/manifest.json`` are therefore the
executable authority. DeckCompiler adds a strict lineage envelope around that
observed contract without copying or replacing the official producer.
"""

from __future__ import annotations

import hashlib
import json
import stat
from pathlib import Path
from typing import Any, Iterable, Mapping

from PIL import Image

from ..schemas import validator_for


CROP_PLAN_RELATIVE_PATH = Path("work") / "crop_plan.json"
ASSET_MANIFEST_RELATIVE_PATH = Path("assets") / "manifest.json"
EXPECTED_SLIDE_NUMBERS = tuple(range(1, 7))
EXPECTED_SLIDE_KEYS = tuple(str(number) for number in EXPECTED_SLIDE_NUMBERS)


class CropContractError(RuntimeError):
    """Stable, fail-closed crop contract error."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.detail = message
        super().__init__(f"{code}: {message}")


def _canonical_json_bytes(payload: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _stable_id(prefix: str, payload: Mapping[str, Any]) -> str:
    return f"{prefix}_{_sha256_bytes(_canonical_json_bytes(payload))[:20]}"


def crop_plan_id(payload: Mapping[str, Any]) -> str:
    """Return the deterministic identity for a crop plan, excluding its own id."""
    identity_payload = {key: value for key, value in payload.items() if key != "plan_id"}
    return _stable_id("cropplan", identity_payload)


def build_zero_crop_plan(
    *,
    handoff_id: str,
    mappings: Iterable[Mapping[str, Any]],
    created_at: str,
    timezone: str,
) -> dict[str, Any]:
    """Build an official-loader-compatible, lineage-rich six-slide zero-crop plan."""
    source_assets: list[dict[str, Any]] = []
    ordered_slide_ids: list[str] = []
    for mapping in mappings:
        sequence = int(mapping["sequence"])
        metadata = mapping["sidecar"]["phase4_metadata"]
        source_asset_id = _stable_id(
            "cropsource",
            {
                "sequence": sequence,
                "slide_id": mapping["slide_id"],
                "visual_target_id": mapping["visual_target_id"],
                "sha256": mapping["source_target_sha256"],
            },
        )
        ordered_slide_ids.append(str(mapping["slide_id"]))
        source_assets.append(
            {
                "source_asset_id": source_asset_id,
                "sequence": sequence,
                "slide_id": mapping["slide_id"],
                "visual_target_id": mapping["visual_target_id"],
                "sidecar_id": mapping["sidecar_id"],
                "path": f"src/slide{sequence}.png",
                "sha256": mapping["source_target_sha256"],
                "dimensions": dict(mapping["dimensions"]),
                "format": "PNG",
                "role": "slide_visual_target_design_reference",
                "native_required_slot_ids": list(metadata["native_required_slot_ids"]),
                "raster_allowed_slot_ids": list(metadata["raster_allowed_slot_ids"]),
                "full_slide_raster_forbidden": True,
                "ocr_canonical_text_forbidden": True,
                "validation_status": "PASS",
            }
        )
    payload: dict[str, Any] = {
        "schema_name": "pngtopptx_project_crop_plan",
        "schema_version": "1.0.0",
        "contract_classification": "observed_external_contract_v1",
        "handoff_id": handoff_id,
        "producer": "DeckCompiler thin handoff adapter",
        "created_at": created_at,
        "timezone": timezone,
        "slide_count": len(source_assets),
        "ordered_slide_ids": ordered_slide_ids,
        "ordered_source_asset_ids": [asset["source_asset_id"] for asset in source_assets],
        "source_assets": source_assets,
        "crop_count": 0,
        "crop_state": "ZERO_RASTER_CROPS",
        "crop_state_reason": (
            "No declared raster-allowed slot is materialized as a crop; semantic content remains native."
        ),
        # This shape is consumed directly by official make_crops.py::_load_crop_plan_file.
        "slides": {str(number): [] for number in EXPECTED_SLIDE_NUMBERS},
        "validation_status": "PASS",
    }
    payload["plan_id"] = crop_plan_id(payload)
    return payload


def _load_json(path: Path, *, missing_code: str, invalid_code: str) -> Any:
    if not path.is_file():
        raise CropContractError(missing_code, str(path))
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CropContractError(invalid_code, f"cannot read {path}: {exc}") from exc


def _schema_validate(schema_name: str, payload: Any, code: str) -> None:
    errors = sorted(validator_for(schema_name).iter_errors(payload), key=lambda item: list(item.path))
    if errors:
        error = errors[0]
        location = "/".join(str(part) for part in error.absolute_path) or "$"
        raise CropContractError(code, f"{location}: {error.message}")


def _has_reparse_attribute(path: Path) -> bool:
    try:
        value = path.stat(follow_symlinks=False)
    except OSError:
        return False
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(getattr(value, "st_file_attributes", 0) & reparse_flag)


def _resolve_confined(project_root: Path, relative_value: str, *, code: str) -> Path:
    relative = Path(relative_value)
    if relative.is_absolute() or "\\" in relative_value or ".." in relative.parts:
        raise CropContractError(code, f"unsafe project-relative path: {relative_value!r}")
    root = project_root.resolve()
    candidate = root / relative
    cursor = candidate
    while cursor != root:
        if cursor.is_symlink() or _has_reparse_attribute(cursor):
            raise CropContractError(code, f"symlink/reparse path is forbidden: {candidate}")
        cursor = cursor.parent
    resolved = candidate.resolve(strict=False)
    if resolved != root and not resolved.is_relative_to(root):
        raise CropContractError(code, f"path escapes project root: {relative_value!r}")
    return candidate


def _expected_mapping_by_sequence(
    expected_slides: Iterable[Mapping[str, Any]] | None,
) -> dict[int, Mapping[str, Any]]:
    if expected_slides is None:
        return {}
    return {int(slide["sequence"]): slide for slide in expected_slides}


def validate_crop_plan(
    crop_plan_path: Path,
    project_root: Path,
    *,
    expected_slides: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Validate the strict wrapper plan and all referenced Phase 4 source bytes."""
    payload = _load_json(
        crop_plan_path,
        missing_code="MISSING_CROP_PLAN",
        invalid_code="INVALID_CROP_PLAN",
    )
    if isinstance(payload, dict):
        slides_value = payload.get("slides")
        if isinstance(slides_value, dict) and tuple(slides_value) != EXPECTED_SLIDE_KEYS:
            raise CropContractError(
                "CROP_PLAN_SLIDE_MISMATCH",
                f"expected ordered slide keys {EXPECTED_SLIDE_KEYS}, got {tuple(slides_value)}",
            )
        ordered_ids_value = payload.get("ordered_slide_ids")
        if isinstance(ordered_ids_value, list) and len(set(ordered_ids_value)) != len(ordered_ids_value):
            raise CropContractError("CROP_PLAN_SLIDE_MISMATCH", "ordered slide ids must be unique")
        source_assets_value = payload.get("source_assets")
        if isinstance(source_assets_value, list) and all(isinstance(item, dict) for item in source_assets_value):
            supplied_ids = [item.get("source_asset_id") for item in source_assets_value]
            if len(set(supplied_ids)) != len(supplied_ids):
                raise CropContractError(
                    "CROP_PLAN_SOURCE_ASSET_MISMATCH",
                    "source asset ids must be unique",
                )
    _schema_validate("pngtopptx_project_crop_plan", payload, "CROP_PLAN_SCHEMA_INVALID")
    if payload["plan_id"] != crop_plan_id(payload):
        raise CropContractError("CROP_PLAN_ID_MISMATCH", "plan_id does not match canonical content")

    slide_keys = tuple(payload["slides"].keys())
    if slide_keys != EXPECTED_SLIDE_KEYS:
        raise CropContractError(
            "CROP_PLAN_SLIDE_MISMATCH",
            f"expected ordered slide keys {EXPECTED_SLIDE_KEYS}, got {slide_keys}",
        )
    ordered_slide_ids = payload["ordered_slide_ids"]
    if len(set(ordered_slide_ids)) != 6:
        raise CropContractError("CROP_PLAN_SLIDE_MISMATCH", "ordered slide ids must be unique")

    source_assets = payload["source_assets"]
    source_ids = [asset["source_asset_id"] for asset in source_assets]
    if (
        [asset["sequence"] for asset in source_assets] != list(EXPECTED_SLIDE_NUMBERS)
        or len(set(source_ids)) != 6
        or source_ids != payload["ordered_source_asset_ids"]
        or [asset["slide_id"] for asset in source_assets] != ordered_slide_ids
    ):
        raise CropContractError(
            "CROP_PLAN_SOURCE_ASSET_MISMATCH",
            "source assets must be unique and ordered one-to-one with slides",
        )

    expected_by_sequence = _expected_mapping_by_sequence(expected_slides)
    source_by_id: dict[str, Mapping[str, Any]] = {}
    for asset in source_assets:
        sequence = int(asset["sequence"])
        source_by_id[asset["source_asset_id"]] = asset
        source_path = _resolve_confined(
            project_root,
            str(asset["path"]),
            code="CROP_PLAN_PATH_ESCAPE",
        )
        expected_path = f"src/slide{sequence}.png"
        if asset["path"] != expected_path:
            raise CropContractError(
                "CROP_PLAN_SOURCE_ASSET_MISMATCH",
                f"slide {sequence} source must be {expected_path}",
            )
        if not source_path.is_file():
            raise CropContractError("CROP_PLAN_SOURCE_ASSET_MISMATCH", f"source is missing: {source_path}")
        actual_hash = _sha256_file(source_path)
        if actual_hash != asset["sha256"]:
            raise CropContractError("CROP_PLAN_SOURCE_HASH_MISMATCH", str(source_path))
        try:
            with Image.open(source_path) as image:
                actual_dimensions = {"width": image.width, "height": image.height}
                actual_format = image.format
        except OSError as exc:
            raise CropContractError("CROP_PLAN_SOURCE_DIMENSIONS_MISMATCH", str(source_path)) from exc
        if actual_dimensions != asset["dimensions"] or actual_format != asset["format"]:
            raise CropContractError(
                "CROP_PLAN_SOURCE_DIMENSIONS_MISMATCH",
                f"{source_path}: expected {asset['dimensions']} {asset['format']}, got {actual_dimensions} {actual_format}",
            )
        expected = expected_by_sequence.get(sequence)
        if expected is not None:
            expected_relative = Path(str(expected["exported_target_relative_path"]))
            if expected_relative.parts and expected_relative.parts[0] == "project":
                expected_relative = Path(*expected_relative.parts[1:])
            if (
                asset["slide_id"] != expected["slide_id"]
                or asset["visual_target_id"] != expected["visual_target_id"]
                or asset["sidecar_id"] != expected["sidecar_id"]
                or asset["path"] != expected_relative.as_posix()
                or asset["sha256"] != expected["exported_target_sha256"]
                or asset["dimensions"] != expected["dimensions"]
            ):
                raise CropContractError(
                    "CROP_PLAN_SOURCE_ASSET_MISMATCH",
                    f"source asset {asset['source_asset_id']} does not match handoff slide {sequence}",
                )

    if expected_by_sequence and set(expected_by_sequence) != set(EXPECTED_SLIDE_NUMBERS):
        raise CropContractError("CROP_PLAN_SLIDE_MISMATCH", "handoff manifest is not a six-slide mapping")

    crop_names: set[str] = set()
    computed_crop_count = 0
    for slide_key, crops in payload["slides"].items():
        slide_number = int(slide_key)
        for crop in crops:
            computed_crop_count += 1
            if crop["name"] in crop_names:
                raise CropContractError("CROP_PLAN_SOURCE_ASSET_MISMATCH", f"duplicate crop: {crop['name']}")
            crop_names.add(crop["name"])
            source = source_by_id.get(crop["source_asset_id"])
            if source is None or int(source["sequence"]) != slide_number or crop["slide"] != slide_number:
                raise CropContractError(
                    "CROP_PLAN_SOURCE_ASSET_MISMATCH",
                    f"crop {crop['name']} does not resolve to its declared slide/source asset",
                )
            slot_id = crop["slot_id"]
            if slot_id in source["native_required_slot_ids"]:
                raise CropContractError(
                    "CROP_PLAN_SEMANTIC_SLOT",
                    f"crop {crop['name']} targets native-required slot {slot_id}",
                )
            if slot_id not in source["raster_allowed_slot_ids"]:
                raise CropContractError(
                    "CROP_PLAN_RASTER_SLOT_NOT_ALLOWED",
                    f"crop {crop['name']} targets undeclared raster slot {slot_id}",
                )
            dimensions = source["dimensions"]
            if crop["x"] + crop["w"] > dimensions["width"] or crop["y"] + crop["h"] > dimensions["height"]:
                raise CropContractError(
                    "CROP_PLAN_BBOX_INVALID",
                    f"crop {crop['name']} exceeds source dimensions {dimensions}",
                )

    if computed_crop_count != payload["crop_count"]:
        raise CropContractError(
            "CROP_PLAN_COUNT_MISMATCH",
            f"declared {payload['crop_count']}, observed {computed_crop_count}",
        )
    if computed_crop_count == 0:
        if payload["crop_state"] != "ZERO_RASTER_CROPS":
            raise CropContractError("CROP_PLAN_ZERO_STATE_INVALID", "zero crops require ZERO_RASTER_CROPS")
    elif payload["crop_state"] != "RASTER_CROPS_PRESENT":
        raise CropContractError("CROP_PLAN_ZERO_STATE_INVALID", "nonzero crops require RASTER_CROPS_PRESENT")

    return {
        "valid": True,
        "plan": payload,
        "plan_id": payload["plan_id"],
        "crop_count": computed_crop_count,
        "source_asset_count": len(source_assets),
        "crop_plan_sha256": _sha256_file(crop_plan_path),
    }


def _flatten_crops(plan: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        str(crop["name"]): crop
        for crops in plan["slides"].values()
        for crop in crops
    }


def validate_asset_manifest(
    asset_manifest_path: Path,
    project_root: Path,
    crop_plan: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate exact official ``make_crops.py`` output against the input plan."""
    payload = _load_json(
        asset_manifest_path,
        missing_code="MISSING_ASSET_MANIFEST",
        invalid_code="INVALID_ASSET_MANIFEST",
    )
    _schema_validate(
        "pngtopptx_project_asset_manifest",
        payload,
        "ASSET_MANIFEST_SCHEMA_INVALID",
    )
    expected_crops = _flatten_crops(crop_plan)
    if set(payload) != set(expected_crops):
        raise CropContractError(
            "ASSET_MANIFEST_MISMATCH",
            f"expected crop assets {sorted(expected_crops)}, got {sorted(payload)}",
        )

    asset_hashes: dict[str, str] = {}
    for name, entry in payload.items():
        crop = expected_crops[name]
        expected_fields = {
            key: value
            for key, value in crop.items()
            if key != "feather_edges"
        }
        expected_fields["file"] = f"{name}.png"
        if entry != expected_fields:
            raise CropContractError(
                "ASSET_MANIFEST_MISMATCH",
                f"manifest entry {name} is not the official projection of its crop plan entry",
            )
        asset_path = _resolve_confined(
            project_root,
            f"assets/{entry['file']}",
            code="ASSET_MANIFEST_PATH_ESCAPE",
        )
        if not asset_path.is_file():
            raise CropContractError("ASSET_FILE_MISSING", str(asset_path))
        try:
            with Image.open(asset_path) as image:
                dimensions = (image.width, image.height)
                image_format = image.format
        except OSError as exc:
            raise CropContractError("ASSET_FILE_INVALID", str(asset_path)) from exc
        if dimensions != (entry["w"], entry["h"]) or image_format != "PNG":
            raise CropContractError(
                "ASSET_FILE_INVALID",
                f"{asset_path}: expected {entry['w']}x{entry['h']} PNG, got {dimensions} {image_format}",
            )
        asset_hashes[name] = _sha256_file(asset_path)

    return {
        "valid": True,
        "asset_count": len(payload),
        "asset_manifest_sha256": _sha256_file(asset_manifest_path),
        "asset_sha256": asset_hashes,
    }


def validate_project_crop_artifacts(
    project_root: Path,
    *,
    expected_slides: Iterable[Mapping[str, Any]] | None = None,
    require_asset_manifest: bool = True,
) -> dict[str, Any]:
    """Validate the project-level crop input and, when required, official output."""
    project = project_root.resolve()
    plan_path = project / CROP_PLAN_RELATIVE_PATH
    manifest_path = project / ASSET_MANIFEST_RELATIVE_PATH
    plan_report = validate_crop_plan(plan_path, project, expected_slides=expected_slides)
    if not require_asset_manifest and not manifest_path.is_file():
        return {
            "valid": True,
            "status": "PENDING_OFFICIAL_CROP_PREPARATION",
            "crop_plan": plan_report,
            "asset_manifest": None,
        }
    manifest_report = validate_asset_manifest(manifest_path, project, plan_report["plan"])
    return {
        "valid": True,
        "status": "PASS_ZERO_RASTER" if plan_report["crop_count"] == 0 else "PASS",
        "crop_plan": plan_report,
        "asset_manifest": manifest_report,
    }


__all__ = [
    "ASSET_MANIFEST_RELATIVE_PATH",
    "CROP_PLAN_RELATIVE_PATH",
    "CropContractError",
    "build_zero_crop_plan",
    "crop_plan_id",
    "validate_asset_manifest",
    "validate_crop_plan",
    "validate_project_crop_artifacts",
]
