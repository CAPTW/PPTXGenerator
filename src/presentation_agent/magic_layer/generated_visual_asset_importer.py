"""Process generated visual assets and copy them to D07.2 import filenames."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps

from .image_generation_provider import sha256_file


def process_and_copy_generated_assets(
    validation_report: dict[str, Any],
    resolved_map: dict[str, Any],
    *,
    processed_dir: Path,
    import_dir: Path,
) -> dict[str, Any]:
    processed_dir.mkdir(parents=True, exist_ok=True)
    import_dir.mkdir(parents=True, exist_ok=True)
    slots = {slot["slot_id"]: slot for slot in resolved_map.get("slots") or []}
    copied: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    accepted_by_slot = {item["slot_id"]: item for item in validation_report.get("accepted_assets") or []}
    for slot_id, slot in slots.items():
        accepted = accepted_by_slot.get(slot_id)
        if not accepted:
            failed.append({"slot_id": slot_id, "reason": "asset_not_accepted"})
            continue
        source = Path(accepted["asset_path"])
        expected = slot["expected_import_filename"]
        processed = processed_dir / expected
        import_path = import_dir / expected
        try:
            _process_asset(source, processed, float(slot.get("target_aspect_ratio") or 1.7778))
            shutil.copy2(processed, import_path)
            _write_sidecar(import_path.with_suffix(".json"), slot, source, processed)
            copied.append(
                {
                    "slot_id": slot_id,
                    "slide_id": slot["slide_id"],
                    "archetype_id": slot["archetype_id"],
                    "expected_import_filename": expected,
                    "source_path": source.as_posix(),
                    "processed_path": processed.as_posix(),
                    "copied_to_import_path": import_path.as_posix(),
                    "sha256": sha256_file(import_path),
                    "crop_or_pad_used": True,
                }
            )
        except Exception as exc:  # noqa: BLE001
            failed.append({"slot_id": slot_id, "reason": str(exc)})
    return {
        "schema_name": "generated_asset_import_copy_report",
        "status": "passed" if copied and len(copied) == len(slots) and not failed else "blocked",
        "expected_asset_count": len(slots),
        "copied_asset_count": len(copied),
        "failed_copy_count": len(failed),
        "copied_assets": copied,
        "failed_assets": failed,
        "canva_parity_claimed": False,
    }


def _process_asset(source: Path, output: Path, target_ratio: float) -> None:
    with Image.open(source) as image:
        rgb = image.convert("RGB")
        width, height = rgb.size
        source_ratio = width / height
        if abs(source_ratio - target_ratio) / max(target_ratio, 0.1) < 0.08:
            processed = rgb
        else:
            if source_ratio > target_ratio:
                new_width = int(height * target_ratio)
                left = max(0, (width - new_width) // 2)
                processed = rgb.crop((left, 0, left + new_width, height))
            else:
                new_height = int(width / target_ratio)
                top = max(0, (height - new_height) // 2)
                processed = rgb.crop((0, top, width, top + new_height))
        min_w, min_h = 1280, 720
        if processed.width < min_w or processed.height < min_h:
            processed = ImageOps.contain(processed, (max(min_w, processed.width), max(min_h, processed.height)))
        output.parent.mkdir(parents=True, exist_ok=True)
        processed.save(output, "PNG")


def _write_sidecar(path: Path, slot: dict[str, Any], source: Path, processed: Path) -> None:
    payload = {
        "schema_name": "visual_asset_import_sidecar",
        "slot_id": slot["slot_id"],
        "slide_id": slot["slide_id"],
        "archetype_id": slot["archetype_id"],
        "role": slot["role"],
        "declared_no_readable_text": True,
        "declared_no_semantic_chart_table_icon": True,
        "declared_no_source_citation_footer_text": True,
        "declared_not_full_slide_background": True,
        "source_generated_original": source.as_posix(),
        "processed_asset_path": processed.as_posix(),
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
