from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any


def profile_render_image(image_path: str | Path, *, expected_min_width: int = 800, expected_min_height: int = 450) -> dict[str, Any]:
    path = Path(image_path)
    base: dict[str, Any] = {
        "schema": "controlled_minimal_render_image_profile.v1",
        "image_path": str(path),
        "image_exists": path.is_file(),
        "width": None,
        "height": None,
        "aspect_ratio": None,
        "likely_16_9": False,
        "image_mode": None,
        "sha256": _sha(path),
        "blank_image_risk": None,
        "tiny_output_risk": None,
        "expected_min_width": expected_min_width,
        "expected_min_height": expected_min_height,
        "validation_status": "FAIL_MISSING_IMAGE",
        "product_pass": False,
    }
    if not path.is_file():
        return base
    try:
        from PIL import Image

        with Image.open(path) as image:
            width, height = image.size
            ratio = width / height if height else 0
            base.update(
                {
                    "width": width,
                    "height": height,
                    "aspect_ratio": round(ratio, 6),
                    "likely_16_9": 1.72 <= ratio <= 1.84,
                    "image_mode": image.mode,
                    "tiny_output_risk": width < expected_min_width or height < expected_min_height,
                    "blank_image_risk": _blank_risk(image),
                }
            )
    except Exception as exc:
        base["validation_status"] = "FAIL_UNREADABLE_IMAGE"
        base["error"] = str(exc)
        return base
    if not base["likely_16_9"]:
        base["validation_status"] = "FAIL_WRONG_ASPECT_RATIO"
    elif base["blank_image_risk"]:
        base["validation_status"] = "FAIL_BLANK_RENDER"
    elif base["tiny_output_risk"]:
        base["validation_status"] = "FAIL_TINY_RENDER"
    elif (base["width"] or 0) < 1200 or (base["height"] or 0) < 675:
        base["validation_status"] = "WARNING_LOW_RESOLUTION"
    else:
        base["validation_status"] = "PASS"
    return base


def _sha(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _blank_risk(image: Any) -> bool:
    extrema = image.convert("RGB").getextrema()
    return all(channel[0] == channel[1] for channel in extrema)
