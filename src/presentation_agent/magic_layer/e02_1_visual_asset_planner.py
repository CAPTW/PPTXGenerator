"""Bounded visual asset planning for E02.1."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from PIL import Image


ASSET_BBOXES: dict[str, list[dict[str, Any]]] = {
    "cover_hero": [
        {
            "asset_id": "cover_hero_visual_field_crop",
            "source_bbox_norm": {"x": 0.50, "y": 0.00, "w": 0.50, "h": 0.88},
            "target_bbox_in": {"x": 7.22, "y": 0.34, "w": 7.78, "h": 7.64},
            "classification": "bounded_hero_visual_field",
            "semantic_content": False,
        }
    ],
    "standard_content": [
        {
            "asset_id": "standard_left_circuit_decorative_crop",
            "source_bbox_norm": {"x": 0.00, "y": 0.00, "w": 0.20, "h": 0.86},
            "target_bbox_in": {"x": 0.0, "y": 0.0, "w": 2.4, "h": 7.76},
            "classification": "bounded_nonsemantic_decorative_chrome",
            "semantic_content": False,
        }
    ],
    "data_dashboard": [],
    "table_heavy": [],
}


def build_visual_asset_plan(archetype_id: str, reference_image: Path, output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    assets: list[dict[str, Any]] = []
    for spec in ASSET_BBOXES[archetype_id]:
        asset_path = output_dir / f"{spec['asset_id']}.png"
        _crop(reference_image, spec["source_bbox_norm"], asset_path)
        assets.append(
            {
                **spec,
                "asset_path": asset_path.as_posix(),
                "sha256": _sha256(asset_path),
                "full_slide_raster": False,
                "screenshot_slide": False,
                "semantic_raster_fallback": False,
                "replaceable_or_decorative": True,
            }
        )
    return {
        "schema_name": "e02_1_visual_asset_plan",
        "status": "passed",
        "archetype_id": archetype_id,
        "visual_asset_count": len(assets),
        "bounded_visual_asset_count": len(assets),
        "semantic_raster_asset_count": 0,
        "full_slide_raster_count": 0,
        "assets": assets,
    }


def _crop(reference_image: Path, bbox: dict[str, float], output_path: Path) -> None:
    with Image.open(reference_image) as image:
        width, height = image.size
        box = (
            round(bbox["x"] * width),
            round(bbox["y"] * height),
            round((bbox["x"] + bbox["w"]) * width),
            round((bbox["y"] + bbox["h"]) * height),
        )
        image.crop(box).save(output_path)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()
