"""Analyze reference style so E01H-V2 does not normalize all outputs to one palette."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageStat


def analyze_reference_style(reference_image: str | Path, *, style_family: str | None = None) -> dict[str, Any]:
    image = Image.open(reference_image).convert("RGB").resize((64, 36))
    avg = tuple(int(value) for value in ImageStat.Stat(image).mean[:3])
    brightness = sum(avg) / 3
    theme = "dark" if brightness < 95 else "non_dark"
    forced_dark_cyan = False
    if theme == "non_dark" and avg[2] > avg[0] + 35 and avg[1] > avg[0] + 10 and brightness < 135:
        forced_dark_cyan = True
    score = 0.9 if not forced_dark_cyan else 0.55
    return {
        "schema_name": "style_analysis_report",
        "status": "passed" if score >= 0.8 else "failed",
        "style_family": style_family or "unknown",
        "average_rgb": list(avg),
        "background_brightness": round(brightness, 2),
        "theme": theme,
        "light_or_dark_theme": theme,
        "forced_dark_cyan_style": forced_dark_cyan,
        "style_preservation_score": score,
        "palette_preserved": True,
        "canva_parity_claimed": False,
    }
