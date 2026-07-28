from __future__ import annotations

from pathlib import Path
from typing import Any


def validate_render_review_fixture(_fixtures_root: str | Path) -> dict[str, Any]:
    return {
        "schema": "render_review_fixture_validator.v1",
        "overall_status": "CONTROLLED_SAMPLE_ONLY",
        "product_pass": False,
        "e03_e04_d08_unlocked": False,
    }
