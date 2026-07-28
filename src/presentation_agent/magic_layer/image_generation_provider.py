"""Provider abstraction for D07.2.4 visual-field image generation."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from PIL import Image, ImageDraw


@dataclass(frozen=True)
class ImageGenerationRequest:
    slot_id: str
    prompt: str
    output_path: Path
    requested_size: str
    expected_filename: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class ImageGenerationResult:
    slot_id: str
    status: str
    output_path: str | None
    provider: str
    model: str
    requested_size: str
    prompt_hash: str
    sha256: str | None
    created_at: str
    request_id: str | None = None
    error: str | None = None


class BaseImageGenerationProvider(Protocol):
    provider_name: str
    model: str

    def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        ...


class DryRunImageGenerationProvider:
    """Deterministic local provider for tests only."""

    provider_name = "dry_run"
    model = "dry-run-image"

    def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        width, height = parse_size(request.requested_size)
        request.output_path.parent.mkdir(parents=True, exist_ok=True)
        image = Image.new("RGB", (width, height), "#0B1220")
        draw = ImageDraw.Draw(image)
        for i in range(0, width, max(16, width // 16)):
            color = "#0E7490" if (i // max(16, width // 16)) % 2 else "#14B8A6"
            draw.line([(i, 0), (width - i // 3, height)], fill=color, width=max(2, width // 256))
        draw.rectangle([width // 12, height // 10, width - width // 12, height - height // 10], outline="#C6A15B", width=max(3, width // 192))
        image.save(request.output_path)
        return ImageGenerationResult(
            slot_id=request.slot_id,
            status="generated",
            output_path=request.output_path.as_posix(),
            provider=self.provider_name,
            model=self.model,
            requested_size=request.requested_size,
            prompt_hash=hash_text(request.prompt),
            sha256=sha256_file(request.output_path),
            created_at=datetime.now(timezone.utc).isoformat(),
            request_id="dry-run",
        )


def parse_size(size: str) -> tuple[int, int]:
    left, right = size.lower().split("x", 1)
    return int(left), int(right)


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def select_requested_size(target_aspect_ratio: float, default_size: str | None = None) -> str:
    candidates = ["2048x1152", "1536x1344", "1344x1536", "1536x1024", "1024x1536", "1024x1024"]
    if default_size:
        candidates.insert(0, default_size)
    best = None
    best_delta = float("inf")
    for candidate in candidates:
        try:
            width, height = parse_size(candidate)
        except (ValueError, AttributeError):
            continue
        if width % 16 or height % 16:
            continue
        ratio = width / height
        if ratio > 3 or ratio < 1 / 3:
            continue
        delta = abs(ratio - float(target_aspect_ratio))
        if delta < best_delta:
            best = candidate
            best_delta = delta
    return best or "2048x1152"
