"""Image metadata helpers for Magic Layer decomposition."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from PIL import Image


@dataclass(frozen=True)
class ImageMetadata:
    path: str
    width: int
    height: int
    mode: str
    aspect_ratio: float
    near_16_9: bool
    file_size_bytes: int
    sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_image_metadata(path: Path) -> ImageMetadata:
    with Image.open(path) as image:
        width, height = image.size
        mode = image.mode
    aspect = width / height if height else 0.0
    return ImageMetadata(
        path=str(path),
        width=width,
        height=height,
        mode=mode,
        aspect_ratio=round(aspect, 5),
        near_16_9=abs(aspect - (16 / 9)) <= 0.04,
        file_size_bytes=path.stat().st_size,
        sha256=sha256_file(path),
    )


def load_rgb(path: Path) -> Image.Image:
    return Image.open(path).convert("RGB")
