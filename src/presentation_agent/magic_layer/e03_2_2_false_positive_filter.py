"""False-positive filtering for observed icon candidates."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageStat


TEXT_FRAGMENT_CONTEXTS = {"source_footer", "footer_source", "source_strip"}
DECORATIVE_OPTIONAL_CONTEXTS = {"footer_action"}


def filter_icon_candidates(inventory: dict[str, Any]) -> dict[str, Any]:
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    decorative: list[dict[str, Any]] = []
    review: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    for icon in inventory.get("icons", []):
        metrics = compute_crop_metrics(Path(icon.get("normalized_crop_path") or icon.get("crop_path", "")))
        classification, category, reason = _classify(icon, metrics)
        row = {
            **icon,
            "hygiene_classification": classification,
            "hygiene_category": category,
            "hygiene_reason": reason,
            "hygiene_metrics": metrics,
            "clean_glyph_candidate": classification in {"auto_accept_clean_icon", "human_review_required"},
        }
        rows.append(row)
        if classification == "auto_accept_clean_icon":
            accepted.append(row)
        elif classification == "auto_reject_non_icon":
            rejected.append(row)
        elif classification == "decorative_optional":
            decorative.append(row)
        else:
            review.append(row)
    accepted_or_review = accepted + review
    return {
        "schema_name": "icon_false_positive_report",
        "status": "passed",
        "raw_candidate_count": len(rows),
        "auto_accept_clean_icon_count": len(accepted),
        "auto_reject_non_icon_count": len(rejected),
        "decorative_optional_count": len(decorative),
        "human_review_required_count": len(review),
        "auto_accept_clean_icons": accepted,
        "auto_reject_non_icons": rejected,
        "decorative_optional_icons": decorative,
        "human_review_required_icons": review,
        "accepted_or_review_icons": accepted_or_review,
        "candidates": rows,
    }


def compute_crop_metrics(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "readable": False,
            "foreground_area_ratio": 0.0,
            "edge_density": 0.0,
            "blankness": 1.0,
            "text_likeness": 0.0,
            "border_likeness": 1.0,
            "line_fragment_likeness": 1.0,
            "color_contrast": 0.0,
            "closed_contour_count": 0,
            "component_count": 0,
            "glyph_compactness": 0.0,
        }
    image = Image.open(path).convert("L")
    width, height = image.size
    stat = ImageStat.Stat(image)
    contrast = float(stat.stddev[0])
    bg = _corner_background(image)
    diff = ImageChops.difference(image, Image.new("L", image.size, bg))
    mask = diff.point(lambda p: 255 if p > 18 else 0)
    pixels = list(mask.getdata())
    foreground = sum(1 for value in pixels if value)
    foreground_ratio = foreground / max(1, width * height)
    bbox = mask.getbbox()
    if bbox:
        bw = bbox[2] - bbox[0]
        bh = bbox[3] - bbox[1]
        bbox_area = max(1, bw * bh)
        aspect = max(bw / max(1, bh), bh / max(1, bw))
        compactness = foreground / bbox_area
    else:
        bw = bh = 0
        aspect = 99.0
        compactness = 0.0
    edge_density = _edge_density(image)
    components = _component_count(mask)
    line_fragment = 1.0 if bbox and (min(bw, bh) <= max(3, int(0.14 * max(width, height))) or aspect > 5.0) else 0.0
    text_likeness = min(1.0, components / 12.0) if foreground_ratio < 0.24 else min(1.0, components / 20.0)
    border_likeness = 1.0 if line_fragment and foreground_ratio < 0.18 else 0.0
    return {
        "readable": True,
        "foreground_area_ratio": round(foreground_ratio, 4),
        "edge_density": round(edge_density, 4),
        "blankness": round(1.0 - min(1.0, contrast / 42.0), 4),
        "text_likeness": round(text_likeness, 4),
        "border_likeness": round(border_likeness, 4),
        "line_fragment_likeness": round(line_fragment, 4),
        "color_contrast": round(contrast, 4),
        "closed_contour_count": max(0, components - 1),
        "component_count": components,
        "glyph_compactness": round(compactness, 4),
    }


def _classify(icon: dict[str, Any], metrics: dict[str, Any]) -> tuple[str, str, str]:
    role = icon.get("likely_role")
    context = icon.get("component_context", "")
    priority = icon.get("priority", "")
    if not metrics["readable"] or metrics["blankness"] > 0.96:
        return "auto_reject_non_icon", "BACKGROUND_TEXTURE_NOT_ICON", "blank_or_unreadable_crop"
    if context in TEXT_FRAGMENT_CONTEXTS or "source_footer" in context:
        if role in {"source", "building", "citation"}:
            category = "TEXT_FRAGMENT_NOT_ICON" if metrics["text_likeness"] > 0.35 else "SOURCE_FOOTER_FRAGMENT_NOT_ICON"
            return "auto_reject_non_icon", category, "source_footer_fragment_is_not_a_clean_icon_glyph"
    if context in DECORATIVE_OPTIONAL_CONTEXTS and role in {"target", "flag"}:
        return "decorative_optional", "DECORATIVE_ICON_OPTIONAL", "footer_action_icon_is_optional_for_icon_library_gate"
    if metrics["border_likeness"] > 0.7 or metrics["line_fragment_likeness"] > 0.7 and metrics["foreground_area_ratio"] < 0.06:
        return "auto_reject_non_icon", "BORDER_FRAGMENT_NOT_ICON", "line_or_border_fragment"
    if metrics["text_likeness"] > 0.82 and role in {"source", "note"}:
        return "auto_reject_non_icon", "TEXT_FRAGMENT_NOT_ICON", "text_like_fragment"
    if metrics["glyph_compactness"] < 0.015 or metrics["foreground_area_ratio"] < 0.006:
        return "human_review_required" if priority.startswith(("P0", "P1")) else "auto_reject_non_icon", "LOW_CONFIDENCE_REVIEW_REQUIRED", "weak_foreground_glyph"
    return "auto_accept_clean_icon", "SEMANTIC_ICON_GLYPH_REQUIRED", "compact_meaningful_glyph_candidate"


def _corner_background(image: Image.Image) -> int:
    width, height = image.size
    samples = [
        image.getpixel((0, 0)),
        image.getpixel((width - 1, 0)),
        image.getpixel((0, height - 1)),
        image.getpixel((width - 1, height - 1)),
    ]
    return int(sorted(samples)[len(samples) // 2])


def _edge_density(image: Image.Image) -> float:
    width, height = image.size
    if width < 2 or height < 2:
        return 0.0
    edges = 0
    total = 0
    pixels = image.load()
    for y in range(height - 1):
        for x in range(width - 1):
            if abs(int(pixels[x, y]) - int(pixels[x + 1, y])) > 24 or abs(int(pixels[x, y]) - int(pixels[x, y + 1])) > 24:
                edges += 1
            total += 1
    return edges / max(1, total)


def _component_count(mask: Image.Image) -> int:
    width, height = mask.size
    data = mask.load()
    seen: set[tuple[int, int]] = set()
    count = 0
    for y in range(height):
        for x in range(width):
            if data[x, y] == 0 or (x, y) in seen:
                continue
            count += 1
            stack = [(x, y)]
            seen.add((x, y))
            while stack:
                sx, sy = stack.pop()
                for nx, ny in ((sx + 1, sy), (sx - 1, sy), (sx, sy + 1), (sx, sy - 1)):
                    if 0 <= nx < width and 0 <= ny < height and data[nx, ny] and (nx, ny) not in seen:
                        seen.add((nx, ny))
                        stack.append((nx, ny))
    return count
