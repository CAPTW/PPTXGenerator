"""Conservative PNG-to-SVG tracing for bounded, flat, non-semantic regions.

The implementation is derived from the validated PPTXlocal vector-first
prototype. It intentionally rejects continuous-tone imagery and never accepts a
whole-slide region. The output is reconstruction evidence for the canonical
PNGtoPPTX SkillSet, not a competing PPTX renderer.
"""

from __future__ import annotations

import hashlib
import math
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any, Iterable

from PIL import Image, ImageChops, ImageFilter, ImageStat

from .svg_gate import validate_svg


MAX_INPUT_PIXELS = 2_500_000
MAX_PALETTE_COLORS = 8
MAX_APPROXIMATE_COLORS = 96
DEFAULT_SIMPLIFY_TOLERANCE = 0.75
MAX_BOUNDED_AREA_RATIO = 0.35


def trace_png_to_svg(
    input_path: Path,
    output_path: Path,
    *,
    region_area_ratio: float,
    semantic_text_overlap: bool,
    max_colors: int = 6,
    simplify_tolerance: float = DEFAULT_SIMPLIFY_TOLERANCE,
) -> dict[str, Any]:
    """Trace one flat-art crop and verify its sanitized rendered fidelity."""

    if not 1 <= max_colors <= MAX_PALETTE_COLORS:
        raise ValueError(f"max_colors must be between 1 and {MAX_PALETTE_COLORS}")
    if simplify_tolerance < 0:
        raise ValueError("simplify_tolerance must be non-negative")
    source = Image.open(input_path).convert("RGBA")
    width, height = source.size
    analysis = {
        **analyze_png(source),
        "region_area_ratio": region_area_ratio,
        "semantic_text_overlap": semantic_text_overlap,
    }
    if not 0 < region_area_ratio <= MAX_BOUNDED_AREA_RATIO:
        return _rejected(input_path, output_path, analysis, "bounded_region_context_required")
    if semantic_text_overlap:
        return _rejected(input_path, output_path, analysis, "semantic_text_overlap_forbidden")
    if width * height > MAX_INPUT_PIXELS:
        return _rejected(input_path, output_path, analysis, "input_pixel_budget_exceeded")
    if analysis["continuous_tone"]:
        return _rejected(input_path, output_path, analysis, "continuous_tone_not_vector_safe")

    quantized, palette = _quantize(source, max_colors)
    background = _background_color(source, quantized)
    paths: list[dict[str, Any]] = []
    total_points = 0
    for color, count in palette:
        if background is not None and color == background:
            continue
        mask = _color_mask(source, quantized, color)
        if count < 2 or not any(mask):
            continue
        loops: list[list[tuple[int, int]]] = []
        for component in _components(mask, width, height):
            loops.extend(_boundary_loops(component))
        simplified = [
            _simplify_closed(loop, simplify_tolerance)
            for loop in loops
            if len(loop) >= 4
        ]
        simplified = [loop for loop in simplified if len(loop) >= 3]
        if not simplified:
            continue
        total_points += sum(len(loop) for loop in simplified)
        paths.append({"color": color, "loops": simplified, "pixel_count": count})

    if not paths:
        return _rejected(input_path, output_path, analysis, "no_vector_paths")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(_svg_document(width, height, paths), encoding="utf-8", newline="\n")
    gate = validate_svg(output_path)
    preview_path = output_path.with_suffix(".preview.png")
    try:
        fidelity = _fidelity_report(source, output_path, preview_path)
    except (ImportError, OSError) as exc:
        output_path.unlink(missing_ok=True)
        return _rejected(
            input_path,
            output_path,
            analysis,
            f"svg_preview_unavailable:{type(exc).__name__}",
        )
    passed = (
        gate["status"] == "passed"
        and gate["path_count"] <= 256
        and total_points <= 16_000
        and fidelity["mean_absolute_error"] <= 0.09
        and fidelity["pixel_difference_ratio"] <= 0.18
    )
    return {
        "schema_name": "pngtosvg_bounded_trace_report",
        "schema_version": "1.0.0",
        "status": "passed" if passed else "failed",
        "input_png": input_path.resolve().as_posix(),
        "input_sha256": _sha256(input_path),
        "output_svg": output_path.resolve().as_posix(),
        "output_sha256": _sha256(output_path),
        "preview_png": preview_path.resolve().as_posix(),
        "preview_sha256": _sha256(preview_path),
        "width": width,
        "height": height,
        "analysis": analysis,
        "background_color": _hex(background) if background else None,
        "palette_color_count": len(paths),
        "path_count": len(paths),
        "point_count": total_points,
        "svg_gate": gate,
        "fidelity": fidelity,
        "fallback_required": not passed,
        "fallback": "native_rebuild_or_skill_bounded_raster_review",
    }


def analyze_png(image: Image.Image) -> dict[str, Any]:
    rgba = image.convert("RGBA")
    sample = rgba.copy()
    sample.thumbnail((256, 256), Image.Resampling.LANCZOS)
    opaque = [pixel[:3] for pixel in _pixels(sample) if pixel[3] > 16]
    approximate = Counter(tuple((channel // 16) * 16 for channel in rgb) for rgb in opaque)
    approximate_color_count = len(approximate)
    grayscale = sample.convert("L")
    edges = ImageChops.difference(grayscale, grayscale.filter(ImageFilter.SMOOTH))
    edge_mean = ImageStat.Stat(edges).mean[0] / 255.0
    entropy = _entropy(approximate.values())
    continuous_tone = approximate_color_count > MAX_APPROXIMATE_COLORS or (
        approximate_color_count > 48 and entropy > 4.5 and edge_mean > 0.025
    )
    return {
        "width": rgba.width,
        "height": rgba.height,
        "approximate_color_count": approximate_color_count,
        "color_entropy": round(entropy, 6),
        "edge_mean": round(edge_mean, 6),
        "has_transparency": any(pixel[3] < 250 for pixel in _pixels(sample)),
        "continuous_tone": continuous_tone,
    }


def _quantize(
    image: Image.Image, max_colors: int
) -> tuple[Image.Image, list[tuple[tuple[int, int, int], int]]]:
    rgb = _composite_white(image)
    quantized = rgb.quantize(
        colors=max_colors,
        method=Image.Quantize.MEDIANCUT,
        dither=Image.Dither.NONE,
    ).convert("RGB")
    counts = Counter(_pixels(quantized))
    return quantized, counts.most_common()


def _background_color(
    source: Image.Image, quantized: Image.Image
) -> tuple[int, int, int] | None:
    if any(alpha < 250 for *_rgb, alpha in _pixels(source)):
        return None
    width, height = quantized.size
    border = []
    for x in range(width):
        border.append(quantized.getpixel((x, 0)))
        border.append(quantized.getpixel((x, height - 1)))
    for y in range(1, height - 1):
        border.append(quantized.getpixel((0, y)))
        border.append(quantized.getpixel((width - 1, y)))
    return Counter(border).most_common(1)[0][0] if border else None


def _color_mask(
    source: Image.Image, quantized: Image.Image, color: tuple[int, int, int]
) -> list[bool]:
    return [
        quantized_pixel == color and source_pixel[3] > 16
        for source_pixel, quantized_pixel in zip(_pixels(source), _pixels(quantized))
    ]


def _components(
    mask: list[bool], width: int, height: int
) -> Iterable[set[tuple[int, int]]]:
    remaining = {index for index, value in enumerate(mask) if value}
    while remaining:
        start = min(remaining)
        queue = deque([start])
        remaining.remove(start)
        component: set[tuple[int, int]] = set()
        while queue:
            index = queue.popleft()
            x, y = index % width, index // width
            component.add((x, y))
            for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if 0 <= nx < width and 0 <= ny < height:
                    neighbor = ny * width + nx
                    if neighbor in remaining:
                        remaining.remove(neighbor)
                        queue.append(neighbor)
        yield component


def _boundary_loops(
    component: set[tuple[int, int]],
) -> list[list[tuple[int, int]]]:
    edges: set[tuple[tuple[int, int], tuple[int, int]]] = set()
    for x, y in component:
        if (x, y - 1) not in component:
            edges.add(((x, y), (x + 1, y)))
        if (x + 1, y) not in component:
            edges.add(((x + 1, y), (x + 1, y + 1)))
        if (x, y + 1) not in component:
            edges.add(((x + 1, y + 1), (x, y + 1)))
        if (x - 1, y) not in component:
            edges.add(((x, y + 1), (x, y)))
    outgoing: dict[tuple[int, int], list[tuple[int, int]]] = defaultdict(list)
    for start, end in edges:
        outgoing[start].append(end)
    for values in outgoing.values():
        values.sort()
    loops: list[list[tuple[int, int]]] = []
    unused = set(edges)
    while unused:
        start_edge = min(unused)
        start, current = start_edge
        unused.remove(start_edge)
        loop = [start, current]
        while current != start:
            candidates = [
                end for end in outgoing.get(current, []) if (current, end) in unused
            ]
            if not candidates:
                break
            end = candidates[0]
            unused.remove((current, end))
            current = end
            loop.append(current)
        if loop[-1] == start:
            loops.append(loop[:-1])
    return loops


def _simplify_closed(
    points: list[tuple[int, int]], tolerance: float
) -> list[tuple[int, int]]:
    cleaned: list[tuple[int, int]] = []
    for point in points:
        if not cleaned or point != cleaned[-1]:
            cleaned.append(point)
    if len(cleaned) < 4:
        return cleaned
    cleaned = _remove_collinear(cleaned)
    if tolerance <= 0 or len(cleaned) < 5:
        return cleaned
    anchor = min(
        range(len(cleaned)), key=lambda index: (cleaned[index][0], cleaned[index][1])
    )
    rotated = cleaned[anchor:] + cleaned[:anchor]
    simplified = _rdp(rotated + [rotated[0]], tolerance)
    if simplified and simplified[-1] == simplified[0]:
        simplified = simplified[:-1]
    return _remove_collinear(simplified)


def _remove_collinear(points: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if len(points) < 3:
        return points
    output = []
    for index, point in enumerate(points):
        before = points[index - 1]
        after = points[(index + 1) % len(points)]
        if (point[0] - before[0]) * (after[1] - point[1]) == (
            point[1] - before[1]
        ) * (after[0] - point[0]):
            continue
        output.append(point)
    return output


def _rdp(points: list[tuple[int, int]], epsilon: float) -> list[tuple[int, int]]:
    if len(points) <= 2:
        return points
    start, end = points[0], points[-1]
    distance, index = max(
        (
            (_point_line_distance(point, start, end), idx)
            for idx, point in enumerate(points[1:-1], start=1)
        ),
        default=(0.0, 0),
    )
    if distance > epsilon:
        left = _rdp(points[: index + 1], epsilon)
        right = _rdp(points[index:], epsilon)
        return left[:-1] + right
    return [start, end]


def _point_line_distance(
    point: tuple[int, int], start: tuple[int, int], end: tuple[int, int]
) -> float:
    if start == end:
        return math.dist(point, start)
    numerator = abs(
        (end[1] - start[1]) * point[0]
        - (end[0] - start[0]) * point[1]
        + end[0] * start[1]
        - end[1] * start[0]
    )
    return numerator / math.dist(start, end)


def _svg_document(width: int, height: int, paths: list[dict[str, Any]]) -> str:
    monochrome = len(paths) == 1
    body = []
    for row in paths:
        data = " ".join(
            "M " + " L ".join(f"{x} {y}" for x, y in loop) + " Z"
            for loop in row["loops"]
        )
        fill = "currentColor" if monochrome else _hex(row["color"])
        body.append(f'<path d="{data}" fill="{fill}" fill-rule="evenodd"/>')
    original = _hex(paths[0]["color"]) if monochrome else None
    metadata = (
        f' data-original-color="{original}" color="{original}"' if original else ""
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}"'
        f' width="{width}" height="{height}"{metadata}>\n  '
        + "\n  ".join(body)
        + "\n</svg>\n"
    )


def _fidelity_report(
    source: Image.Image, svg_path: Path, preview_path: Path
) -> dict[str, Any]:
    import cairosvg

    cairosvg.svg2png(
        url=svg_path.as_posix(),
        write_to=preview_path.as_posix(),
        output_width=source.width,
        output_height=source.height,
        background_color="#ffffff",
    )
    rendered = Image.open(preview_path).convert("RGB")
    expected = _composite_white(source)
    difference = ImageChops.difference(expected, rendered)
    stat = ImageStat.Stat(difference)
    mae = sum(stat.mean) / (3 * 255.0)
    changed = sum(max(pixel) > 24 for pixel in _pixels(difference))
    ratio = changed / (source.width * source.height)
    return {
        "mean_absolute_error": round(mae, 6),
        "pixel_difference_ratio": round(ratio, 6),
        "thresholds": {
            "mean_absolute_error_max": 0.09,
            "pixel_difference_ratio_max": 0.18,
        },
    }


def _composite_white(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    white = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
    return Image.alpha_composite(white, rgba).convert("RGB")


def _pixels(image: Image.Image):
    flattened = getattr(image, "get_flattened_data", None)
    return flattened() if callable(flattened) else image.getdata()


def _entropy(counts: Iterable[int]) -> float:
    values = list(counts)
    total = sum(values)
    if total <= 0:
        return 0.0
    return -sum(
        (value / total) * math.log2(value / total) for value in values if value
    )


def _rejected(
    input_path: Path,
    output_path: Path,
    analysis: dict[str, Any],
    reason: str,
) -> dict[str, Any]:
    return {
        "schema_name": "pngtosvg_bounded_trace_report",
        "schema_version": "1.0.0",
        "status": "rejected",
        "reason": reason,
        "input_png": input_path.resolve().as_posix(),
        "input_sha256": _sha256(input_path),
        "output_svg": output_path.resolve().as_posix(),
        "analysis": analysis,
        "fallback_required": True,
        "fallback": "native_rebuild_or_skill_bounded_raster_review",
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _hex(color: tuple[int, int, int] | None) -> str:
    if color is None:
        return "#000000"
    return "#" + "".join(f"{channel:02x}" for channel in color)


__all__ = ["MAX_BOUNDED_AREA_RATIO", "analyze_png", "trace_png_to_svg"]
