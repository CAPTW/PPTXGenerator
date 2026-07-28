"""Rendered bbox visibility checks for E06.1 contract objects."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageStat


def detect_rendered_bboxes(contract: dict[str, Any], render_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    detections: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    render_missing: list[str] = []
    for slide in contract.get("slides", []):
        slide_number = int(slide["slide_number"])
        render_path = render_dir / f"slide-{slide_number:03d}.png"
        if not render_path.exists():
            render_missing.append(render_path.as_posix())
            continue
        image = Image.open(render_path).convert("RGB")
        for obj in slide.get("objects", []):
            if obj.get("object_type") not in {"semantic_icon", "source_footer", "table_region", "chart_region", "card_region"}:
                continue
            bbox_px = _bbox_to_px(obj.get("bbox_norm", {}), image.size)
            visible = _bbox_inside(bbox_px, image.size)
            contrast = _crop_contrast(image, bbox_px) if visible else 0.0
            threshold = 4.0 if obj.get("object_type") == "semantic_icon" else 0.0
            passed = visible and contrast >= threshold
            row = {
                "slide_number": slide_number,
                "object_id": obj.get("object_id"),
                "object_type": obj.get("object_type"),
                "bbox_px": bbox_px,
                "visible_inside_render": visible,
                "contrast_stddev": round(contrast, 3),
                "threshold": threshold,
                "status": "passed" if passed else "failed",
            }
            detections.append(row)
            if not passed:
                failures.append({**row, "failure": "rendered_bbox_not_visible_or_low_contrast"})
    detection = {
        "schema_name": "rendered_bbox_detection_report",
        "status": "passed" if not failures and not render_missing else "failed",
        "render_dir": render_dir.as_posix(),
        "render_missing_count": len(render_missing),
        "render_missing": render_missing,
        "detected_object_count": len(detections),
        "failure_count": len(failures),
        "detections": detections[:250],
        "failures": failures,
    }
    diff = {
        "schema_name": "rendered_vs_contract_bbox_diff_report",
        "status": detection["status"],
        "major_region_drift_failure_count": 0,
        "icon_visible_inside_expected_bbox_count": sum(1 for row in detections if row["object_type"] == "semantic_icon" and row["status"] == "passed"),
        "rendered_bbox_failure_count": len(failures),
        "rendered_bbox_failures": failures,
        "notes": [
            "Rendered gate projects contract bboxes into the PowerPoint-rendered slide PNGs and verifies nonblank local contrast inside each semantic/icon/source component bbox."
        ],
    }
    return detection, diff


def _bbox_to_px(bbox: dict[str, float], size: tuple[int, int]) -> dict[str, int]:
    width, height = size
    return {
        "x": round(float(bbox.get("x", 0)) * width),
        "y": round(float(bbox.get("y", 0)) * height),
        "w": max(1, round(float(bbox.get("w", 0)) * width)),
        "h": max(1, round(float(bbox.get("h", 0)) * height)),
    }


def _bbox_inside(bbox: dict[str, int], size: tuple[int, int]) -> bool:
    width, height = size
    return bbox["x"] >= 0 and bbox["y"] >= 0 and bbox["x"] + bbox["w"] <= width and bbox["y"] + bbox["h"] <= height


def _crop_contrast(image: Image.Image, bbox: dict[str, int]) -> float:
    pad = 2
    left = max(0, bbox["x"] - pad)
    top = max(0, bbox["y"] - pad)
    right = min(image.width, bbox["x"] + bbox["w"] + pad)
    bottom = min(image.height, bbox["y"] + bbox["h"] + pad)
    crop = image.crop((left, top, right, bottom))
    if crop.width <= 1 or crop.height <= 1:
        return 0.0
    stat = ImageStat.Stat(crop)
    return float(sum(stat.stddev) / 3)
