"""Approximate text contrast and capacity checks for E01.2."""

from __future__ import annotations

from typing import Any


def contrast_ratio(foreground_hex: str, background_hex: str) -> float:
    def channel(value: int) -> float:
        c = value / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    def luminance(color: str) -> float:
        color = color.lstrip("#")
        r, g, b = int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)
        return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)

    l1 = luminance(foreground_hex)
    l2 = luminance(background_hex)
    bright, dark = max(l1, l2), min(l1, l2)
    return round((bright + 0.05) / (dark + 0.05), 2)


def evaluate_text_contrast_capacity(text_regions: list[dict[str, Any]]) -> dict[str, Any]:
    defects: list[dict[str, Any]] = []
    for region in text_regions:
        ratio = contrast_ratio(region["font_color"], region["background_color"])
        capacity_ok = len(region["text"]) <= region["max_chars"]
        if ratio < region.get("min_contrast", 4.5):
            defects.append({"region_id": region["region_id"], "defect": "contrast_below_threshold", "ratio": ratio})
        if not capacity_ok:
            defects.append({"region_id": region["region_id"], "defect": "text_capacity_exceeded"})
    return {
        "schema_name": "text_contrast_and_capacity_report",
        "status": "passed" if not defects else "failed",
        "region_count": len(text_regions),
        "defect_count": len(defects),
        "defects": defects,
        "text_overflow_count": len([d for d in defects if d["defect"] == "text_capacity_exceeded"]),
        "canva_parity_claimed": False,
    }

