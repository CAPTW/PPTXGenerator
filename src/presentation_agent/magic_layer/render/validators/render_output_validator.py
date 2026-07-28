from __future__ import annotations

from pathlib import Path
from typing import Any

from ..render_image_profile import profile_render_image


def validate_render_output(image_path: str | Path) -> dict[str, Any]:
    profile = profile_render_image(image_path)
    return {
        "schema": "render_output_validator.v1",
        "pass": profile["validation_status"] in {"PASS", "WARNING_LOW_RESOLUTION"},
        "profile": profile,
        "product_pass": False,
    }
