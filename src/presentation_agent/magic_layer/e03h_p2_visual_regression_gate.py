"""Visual regression checks for E03H-P2 SVG rebinding."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image


def build_e03h_p2_visual_richness_regression_report(
    original_rendered: str | Path,
    patched_rendered: str | Path,
    *,
    semantic_icon_count: int,
) -> dict[str, Any]:
    original = Path(original_rendered)
    patched = Path(patched_rendered)
    failures = []
    if not original.exists():
        failures.append("missing_original_render")
    if not patched.exists():
        failures.append("missing_patched_render")
    same_size = False
    if original.exists() and patched.exists():
        with Image.open(original) as a, Image.open(patched) as b:
            same_size = a.size == b.size
            if not same_size:
                failures.append("render_dimensions_changed")
    if semantic_icon_count <= 0:
        failures.append("no_svg_provenanced_icons_added")
    return {
        "schema_name": "e03h_p2_visual_richness_regression_report",
        "status": "passed" if not failures else "failed",
        "visual_richness_regressed": bool(failures and failures != ["no_svg_provenanced_icons_added"]),
        "semantic_icons_more_provenanced": semantic_icon_count > 0,
        "render_dimensions_preserved": same_size,
        "failures": failures,
        "canva_parity_claimed": False,
    }
