"""Select the E03.2 golden-slide target."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image


DEFAULT_TARGET = "visual_toc"


def select_e03_2_target(ref_root: Path, e03_1_archetype_root: Path, visual_gap_matrix: dict[str, Any]) -> dict[str, Any]:
    default_ref = ref_root / f"{DEFAULT_TARGET}.png"
    default_render = e03_1_archetype_root / DEFAULT_TARGET / "e03_1_rendered_candidate.png"
    if _valid_image(default_ref) and _valid_image(default_render):
        target = DEFAULT_TARGET
        reason = "default_hard_target_available"
    else:
        target = _largest_gap(visual_gap_matrix)
        reason = "default_missing_or_unusable_largest_gap_selected"
    return {
        "schema_name": "e03_2_target_selection_report",
        "status": "passed",
        "target_archetype": target,
        "selection_reason": reason,
        "why_selected": (
            "visual_toc stresses object placement because it combines a header system, six card modules, "
            "a progress path, active state, right meta rail, icons, connectors, footer/source, and layered chrome."
        ),
        "what_makes_it_hard": [
            "six repeated cards must align without collapsing into horizontal bars",
            "the active state must preserve larger gold marker and highlighted card",
            "connectors and reading path need correct z-order and spacing",
            "right meta panel must remain separate from content cards",
            "footer/source system must stay editable and visually distinct",
        ],
        "reference_specific_elements_to_preserve": [
            "dark header with TITLE cluster",
            "white main stage with top notch/chrome",
            "six vertical module cards",
            "02 active module state",
            "right metadata card",
            "reading path connector",
            "footer/source strip",
        ],
        "meaning_before_batch_work": "A convincing visual_toc conversion proves object placement and layer grammar before reapplying the gate to the remaining 15 archetypes.",
        "do_not_start_e04": True,
    }


def _valid_image(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        with Image.open(path) as image:
            width, height = image.size
        return width > 1000 and height > 500 and abs(width / height - 16 / 9) < 0.08
    except OSError:
        return False


def _largest_gap(visual_gap_matrix: dict[str, Any]) -> str:
    rows = visual_gap_matrix.get("archetypes", {})
    if not rows:
        return DEFAULT_TARGET
    return max(rows, key=lambda key: 1.0 - float(rows[key].get("metrics", {}).get("visual_similarity_proxy", 0.0)))
