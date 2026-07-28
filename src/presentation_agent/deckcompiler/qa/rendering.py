"""Canonical PowerPoint COM rendering and deterministic contact sheets."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from .contracts import sha256_file


@dataclass(frozen=True)
class RenderResult:
    renderer_identity: str
    renderer_version: str
    render_dir: Path
    slides: tuple[dict[str, Any], ...]
    repair_warning_count: int


def render_with_powerpoint(pptx_path: Path, render_dir: Path) -> RenderResult:
    """Render every slide through a fresh hidden PowerPoint COM instance."""

    try:
        import win32com.client  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - Windows gate
        raise RuntimeError("BLOCKED_REAL_RENDERER_UNAVAILABLE: pywin32 is unavailable") from exc

    render_dir.mkdir(parents=True, exist_ok=False)
    app = win32com.client.DispatchEx("PowerPoint.Application")
    presentation = None
    try:
        app.DisplayAlerts = 0
        presentation = app.Presentations.Open(
            str(pptx_path.resolve()), ReadOnly=True, Untitled=False, WithWindow=False
        )
        version = str(app.Version)
        for slide_number in range(1, int(presentation.Slides.Count) + 1):
            presentation.Slides(slide_number).Export(
                str((render_dir / f"slide-{slide_number:03d}.png").resolve()),
                "PNG",
                1920,
                1080,
            )
    except Exception as exc:  # pragma: no cover - depends on Office
        raise RuntimeError(f"BLOCKED_REAL_RENDERER_UNAVAILABLE: {exc}") from exc
    finally:
        if presentation is not None:
            presentation.Close()
        app.Quit()
    return inspect_renders(render_dir, renderer_version=version)


def inspect_renders(
    render_dir: Path,
    *,
    renderer_version: str = "16.0",
    renderer_identity: str = "Microsoft PowerPoint COM",
) -> RenderResult:
    paths = sorted(render_dir.glob("slide-*.png"))
    slides: list[dict[str, Any]] = []
    for slide_number, path in enumerate(paths, 1):
        with Image.open(path) as image:
            image.load()
            width, height = image.size
        slides.append(
            {
                "slide": slide_number,
                "path": f"renders/{path.name}",
                "sha256": sha256_file(path),
                "byte_size": path.stat().st_size,
                "width": width,
                "height": height,
                "aspect_ratio": "16:9" if width * 9 == height * 16 else "other",
                "decode_valid": True,
            }
        )
    return RenderResult(
        renderer_identity=renderer_identity,
        renderer_version=renderer_version,
        render_dir=render_dir,
        slides=tuple(slides),
        repair_warning_count=0,
    )


def build_contact_sheet(render_result: RenderResult, output_path: Path) -> dict[str, Any]:
    if len(render_result.slides) != 6:
        raise ValueError("contact sheet requires exactly six renders")
    thumb_width, thumb_height = 576, 324
    margin, label_height = 24, 40
    width = margin + 3 * (thumb_width + margin)
    height = margin + 2 * (label_height + thumb_height + margin)
    canvas = Image.new("RGB", (width, height), "#e9eef5")
    draw = ImageDraw.Draw(canvas)
    for index, slide in enumerate(render_result.slides):
        source = render_result.render_dir / Path(slide["path"]).name
        with Image.open(source) as image:
            tile = image.convert("RGB")
            tile.thumbnail((thumb_width, thumb_height))
        column, row = index % 3, index // 3
        x = margin + column * (thumb_width + margin)
        y = margin + row * (label_height + thumb_height + margin)
        draw.text((x, y + 8), f"Slide {index + 1:02d} / slide-{index + 1:03d}", fill="#102a43")
        canvas.paste(tile, (x, y + label_height))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, format="PNG", optimize=True)
    return {
        "path": "contact_sheet.png",
        "sha256": sha256_file(output_path),
        "byte_size": output_path.stat().st_size,
        "width": width,
        "height": height,
        "columns": 3,
        "rows": 2,
    }


def build_before_faulty_after_sheet(
    baseline: Path, faulty: Path, repaired: Path, output_path: Path, *, slide_number: int
) -> dict[str, Any]:
    sources = [("BASELINE", baseline), ("FAULTY", faulty), ("REPAIRED", repaired)]
    thumb_width, thumb_height = 576, 324
    margin, label_height = 24, 42
    canvas = Image.new(
        "RGB", (margin + 3 * (thumb_width + margin), margin * 2 + label_height + thumb_height), "#e9eef5"
    )
    draw = ImageDraw.Draw(canvas)
    for index, (label, source) in enumerate(sources):
        with Image.open(source) as image:
            tile = image.convert("RGB")
            tile.thumbnail((thumb_width, thumb_height))
        x = margin + index * (thumb_width + margin)
        draw.text((x, margin + 8), f"{label} / slide-{slide_number:03d}", fill="#102a43")
        canvas.paste(tile, (x, margin + label_height))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, format="PNG", optimize=True)
    return {
        "path": "before_faulty_after_contact_sheet.png",
        "sha256": sha256_file(output_path),
        "byte_size": output_path.stat().st_size,
        "width": canvas.width,
        "height": canvas.height,
        "columns": 3,
        "rows": 1,
    }


__all__ = [
    "RenderResult",
    "build_before_faulty_after_sheet",
    "build_contact_sheet",
    "inspect_renders",
    "render_with_powerpoint",
]
