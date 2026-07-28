"""Compatibility wrapper for local template image ingest.

The repository does not call an image generation API. Codex Desktop generates
template reference PNGs manually; this module only ingests those PNGs or writes
local mock fixtures for smoke tests.
"""

from __future__ import annotations

import os
from pathlib import Path

from .ingest_template_images import (
    DEFAULT_FIXTURE_DIR,
    DEFAULT_IMAGE_DIR,
    DEFAULT_PROMPT_MANIFEST,
    ingest_template_images,
    main,
)


def generate_template_images_from_manifest(
    *,
    prompt_manifest_path: str | Path = DEFAULT_PROMPT_MANIFEST,
    output_dir: str | Path = DEFAULT_IMAGE_DIR,
    fixture_dir: str | Path = DEFAULT_FIXTURE_DIR,
    env: dict[str, str] | None = None,
    timestamp: str | None = None,
) -> Path:
    environment = env if env is not None else os.environ
    mode = environment.get("TEMPLATE_IMAGE_MODE") or environment.get("STAGE4_TEMPLATE_IMAGE_MODE") or "mock_fixture"
    return ingest_template_images(
        prompt_manifest_path=prompt_manifest_path,
        image_dir=output_dir,
        fixture_dir=fixture_dir,
        generation_mode=mode,
        allow_mock_fallback=True,
        timestamp=timestamp or environment.get("TEMPLATE_IMAGE_GENERATION_TIMESTAMP"),
    )


if __name__ == "__main__":
    raise SystemExit(main())
