"""Crop and mask extraction for Magic Layer D01."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from .image_asset import load_rgb
from .layer_schema_v4 import bbox_area_ratio


def extract_crops_and_masks(
    image_path: Path,
    layers: list[dict[str, Any]],
    *,
    crops_dir: Path,
    masks_dir: Path,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    image = load_rgb(image_path)
    width, height = image.size
    crops_dir.mkdir(parents=True, exist_ok=True)
    masks_dir.mkdir(parents=True, exist_ok=True)
    crop_entries: list[dict[str, Any]] = []
    mask_entries: list[dict[str, Any]] = []
    flags: list[dict[str, Any]] = []
    for layer in layers:
        layer_id = layer["layer_id"]
        bbox = layer["bbox_px"]
        area_ratio = bbox_area_ratio(bbox, width, height)
        if layer["layer_type"] == "background_base":
            layer["crop_path"] = None
            layer["mask_path"] = None
            flags.append({"layer_id": layer_id, "flag": "background_base_no_crop", "area_ratio": area_ratio})
            continue
        if area_ratio > 0.75:
            layer["crop_path"] = None
            layer["mask_path"] = None
            flags.append({"layer_id": layer_id, "flag": "full_slide_crop_rejected", "area_ratio": round(area_ratio, 4)})
            continue
        x, y, w, h = bbox
        crop = image.crop((x, y, x + w, y + h))
        crop_path = crops_dir / f"{layer_id}.png"
        crop.save(crop_path)
        mask = Image.new("L", (w, h), 0)
        draw = ImageDraw.Draw(mask)
        if layer.get("polygon_px"):
            polygon = [(px - x, py - y) for px, py in layer["polygon_px"]]
            draw.polygon(polygon, fill=255)
            mask_source = "polygon"
        else:
            draw.rectangle((0, 0, w - 1, h - 1), fill=255)
            mask_source = "bbox_rectangular"
        mask_path = masks_dir / f"{layer_id}_mask.png"
        mask.save(mask_path)
        layer["crop_path"] = str(crop_path)
        layer["mask_path"] = str(mask_path)
        crop_entries.append(
            {
                "layer_id": layer_id,
                "crop_path": str(crop_path),
                "bbox_px": bbox,
                "crop_width": w,
                "crop_height": h,
                "area_ratio": round(area_ratio, 5),
                "content_bearing": layer["content_bearing"],
                "semantic_raster_final_use_allowed": layer["editability_target"] in {"replaceable_image_frame", "allowed_decorative_raster"},
                "raster_policy": layer["raster_policy"],
            }
        )
        mask_entries.append(
            {
                "layer_id": layer_id,
                "mask_path": str(mask_path),
                "mask_source": mask_source,
                "bbox_px": bbox,
                "polygon_available": bool(layer.get("polygon_px")),
            }
        )
    return (
        {
            "schema_name": "crop_manifest",
            "status": "passed",
            "crop_count": len(crop_entries),
            "full_slide_crop_violation_count": sum(1 for flag in flags if flag["flag"] == "full_slide_crop_rejected"),
            "crops": crop_entries,
            "flags": flags,
        },
        {"schema_name": "mask_manifest", "status": "passed", "mask_count": len(mask_entries), "masks": mask_entries},
        flags,
    )
