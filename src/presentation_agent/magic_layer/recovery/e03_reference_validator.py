from __future__ import annotations

import hashlib
import struct
from pathlib import Path
from typing import Any


SUPPORTED_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


def validate_reference_file(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    if not path.is_file():
        return _base(path, "MISSING")
    if path.suffix.lower() not in SUPPORTED_SUFFIXES:
        return _base(path, "FAIL_INVALID_FILETYPE")
    meta = _read_dimensions(path)
    if not meta:
        return _base(path, "FAIL_UNREADABLE_IMAGE") | {"sha256": _sha256(path)}
    width, height, file_type = meta
    ratio = width / height if height else 0
    is_16_9 = abs(ratio - (16 / 9)) < 0.02
    status = "PASS" if is_16_9 else "FAIL_NOT_16_9"
    if is_16_9 and (width, height) != (1920, 1080):
        status = "PASS_WITH_DIMENSION_LIMITATION"
    return {
        **_base(path, status),
        "sha256": _sha256(path),
        "width": width,
        "height": height,
        "aspect_ratio": ratio,
        "is_16_9": is_16_9,
        "file_type_detected": file_type,
    }


def _base(path: Path, status: str) -> dict[str, Any]:
    return {"schema": "e03_reference_file_validation.v1", "path": str(path), "exists": path.is_file(), "extension": path.suffix.lower(), "validation_status": status, "product_pass": False}


def _read_dimensions(path: Path) -> tuple[int, int, str] | None:
    data = path.read_bytes()[:64]
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        width, height = struct.unpack(">II", data[16:24])
        return width, height, "png"
    return None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
