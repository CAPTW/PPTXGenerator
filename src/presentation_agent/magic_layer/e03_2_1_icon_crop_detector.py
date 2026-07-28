"""Crop observed icon regions for E03.2.1."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps


def crop_observed_icons(inventory: dict[str, Any], crop_root: Path, normalized_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    crop_root.mkdir(parents=True, exist_ok=True)
    normalized_root.mkdir(parents=True, exist_ok=True)
    cropped_icons = []
    for icon in inventory["icons"]:
        reference = Path(icon["reference_path"])
        with Image.open(reference) as image:
            width, height = image.size
            bbox_px = _bbox_px(icon["bbox_norm"], width, height)
            crop = image.crop((bbox_px[0], bbox_px[1], bbox_px[0] + bbox_px[2], bbox_px[1] + bbox_px[3])).convert("RGB")
        crop_path = crop_root / icon["archetype_id"] / f"{icon['icon_id']}.png"
        norm_path = normalized_root / icon["archetype_id"] / f"{icon['icon_id']}.png"
        crop_path.parent.mkdir(parents=True, exist_ok=True)
        norm_path.parent.mkdir(parents=True, exist_ok=True)
        crop.save(crop_path)
        normalized = ImageOps.contain(crop, (96, 96), Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", (96, 96), "#F8FAFC")
        canvas.paste(normalized, ((96 - normalized.width) // 2, (96 - normalized.height) // 2))
        canvas.save(norm_path)
        updated = {**icon, "bbox_px": bbox_px, "crop_path": crop_path.as_posix(), "normalized_crop_path": norm_path.as_posix(), "crop_sha256": _sha256(crop_path)}
        cropped_icons.append(updated)
    cropped_inventory = {
        **inventory,
        "icons": cropped_icons,
        "crop_status": "passed",
        "crop_count": len(cropped_icons),
        "normalized_crop_count": len(cropped_icons),
    }
    manifest = {
        "schema_name": "icon_crop_manifest",
        "status": "passed",
        "crop_count": len(cropped_icons),
        "normalized_crop_count": len(cropped_icons),
        "icons": [
            {
                "icon_id": icon["icon_id"],
                "archetype_id": icon["archetype_id"],
                "likely_role": icon["likely_role"],
                "bbox_px": icon["bbox_px"],
                "bbox_norm": icon["bbox_norm"],
                "crop_path": icon["crop_path"],
                "normalized_crop_path": icon["normalized_crop_path"],
                "crop_sha256": icon["crop_sha256"],
            }
            for icon in cropped_icons
        ],
    }
    return cropped_inventory, manifest


def _bbox_px(bbox_norm: list[float], width: int, height: int) -> list[int]:
    x0, y0, x1, y1 = bbox_norm
    return [round(x0 * width), round(y0 * height), round((x1 - x0) * width), round((y1 - y0) * height)]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()
