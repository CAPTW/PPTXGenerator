"""Analyze template-reference PNGs into an extracted design-system observation artifact."""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any

from PIL import Image

from ..generator_contracts import validateDesignBrief, validateExtractedDesignSystem
from .merge_extracted_design_system import merge_extracted_design_system_files
from .template_archetypes import load_template_archetype_registry


DEFAULT_TEMPLATE_IMAGE_MANIFEST = Path("outputs/template_images/template_image_manifest.json")
DEFAULT_DESIGN_BRIEF = Path("outputs/design_brief.json")
DEFAULT_OUTPUT = Path("outputs/extracted_design_system.json")
DEFAULT_CODEX_EXTRACTION = Path("outputs/extracted_design_system.codex.json")
DEFAULT_MERGED_OUTPUT = Path("outputs/extracted_design_system.merged.json")
CANVAS = {"width": 13.333, "height": 7.5, "unit": "in", "ratio": "16:9"}
DEFAULT_PALETTE = [
    ("paper", "#F8FAFC", "background", 0.55),
    ("ink", "#111827", "primary text", 0.55),
    ("accent", "#2563EB", "accent", 0.45),
]


def analyze_template_images(
    template_image_manifest: dict[str, Any],
    design_brief: dict[str, Any],
    *,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    validateDesignBrief(design_brief)
    environment = env if env is not None else os.environ
    registry = _registry_by_id()
    warnings: list[dict[str, Any]] = []
    image_observations: list[dict[str, Any]] = []
    palette_votes: Counter[tuple[int, int, int]] = Counter()
    metrics_by_archetype: dict[str, dict[str, float]] = {}

    vision_enabled = _vision_enabled(environment)
    if vision_enabled:
        warnings.append(
            _warning(
                "VISION_MODE_REQUESTED_HEURISTIC_FALLBACK",
                "Vision extraction flags are enabled, but this MVP keeps extraction deterministic and writes heuristic observations.",
                "info",
            )
        )
    else:
        warnings.append(
            _warning(
                "HEURISTIC_EXTRACTION_USED",
                "Offline deterministic image heuristics were used because vision extraction is disabled or unavailable.",
                "info",
            )
        )

    for record in _manifest_images(template_image_manifest):
        archetype_id = str(record.get("archetype_id") or "standard_content")
        image_path = Path(str(record.get("image_output_path") or ""))
        prompt_file = str(record.get("prompt_file_path") or record.get("prompt_file") or "")
        record_generation_mode = str(record.get("generation_mode") or "")
        source_record = {
            "archetype_id": archetype_id,
            "image_path": _display_path(image_path),
            "prompt_file": prompt_file or "unknown",
            "source_role": "mock_reference" if record_generation_mode.startswith("mock") else "template_reference",
        }
        try:
            metrics = _analyze_png(image_path)
            source_record["width_px"] = int(metrics["width_px"])
            source_record["height_px"] = int(metrics["height_px"])
            palette_votes.update(metrics["dominant_colors"])
            metrics_by_archetype[archetype_id] = metrics
        except OSError as exc:
            metrics = _fallback_metrics()
            metrics_by_archetype[archetype_id] = metrics
            warnings.append(
                _warning(
                    "TEMPLATE_IMAGE_READ_FAILED",
                    f"Could not read template image {image_path}: {exc}",
                    "warning",
                    archetype_id,
                )
            )
        image_observations.append(source_record)

    if not image_observations:
        image_observations.append(
            {
                "archetype_id": "standard_content",
                "image_path": "outputs/template_images/standard_content.png",
                "prompt_file": "outputs/template_image_prompts/standard_content.prompt.txt",
                "source_role": "mock_reference",
            }
        )
        metrics_by_archetype["standard_content"] = _fallback_metrics()
        warnings.append(_warning("NO_TEMPLATE_IMAGES_FOUND", "No image records were found; fallback observations were emitted.", "warning"))

    palette = _palette_from_votes(palette_votes)
    density_profile = _density_profile(metrics_by_archetype, registry)
    artifact = {
        "schema_name": "extracted_design_system",
        "schema_version": "1.0",
        "source_template_images": image_observations,
        "canvas": dict(CANVAS),
        "detected_palette": palette,
        "typography_estimates": _typography_estimates(design_brief, metrics_by_archetype),
        "layout_grid": _layout_grid(metrics_by_archetype),
        "safe_margins": {"top": 0.45, "right": 0.6, "bottom": 0.45, "left": 0.6, "unit": "in"},
        "component_observations": _component_observations(metrics_by_archetype),
        "footer_observations": _footer_observations(metrics_by_archetype),
        "card_observations": _typed_observations(metrics_by_archetype, "card", {"x": 0.72, "y": 1.55, "w": 3.4, "h": 1.18}),
        "chart_frame_observations": _typed_observations(metrics_by_archetype, "chart_frame", {"x": 4.75, "y": 1.45, "w": 5.3, "h": 3.1}),
        "table_frame_observations": _typed_observations(metrics_by_archetype, "table_frame", {"x": 0.72, "y": 2.05, "w": 11.9, "h": 4.25}),
        "image_frame_observations": _typed_observations(metrics_by_archetype, "image_frame", {"x": 7.2, "y": 0.72, "w": 5.0, "h": 5.65}),
        "diagonal_panel_observations": _typed_observations(metrics_by_archetype, "diagonal_photo_panel", {"x": 6.85, "y": 0.45, "w": 5.8, "h": 6.2}),
        "background_ornament_observations": _background_observations(metrics_by_archetype),
        "density_profile": density_profile,
        "confidence_scores": _confidence_scores(metrics_by_archetype, vision_enabled),
        "extraction_warnings": warnings,
    }
    validateExtractedDesignSystem(artifact)
    return artifact


def analyze_template_images_from_files(
    *,
    template_image_manifest_path: str | Path = DEFAULT_TEMPLATE_IMAGE_MANIFEST,
    design_brief_path: str | Path = DEFAULT_DESIGN_BRIEF,
    output_path: str | Path = DEFAULT_OUTPUT,
    codex_extraction_path: str | Path = DEFAULT_CODEX_EXTRACTION,
    merged_output_path: str | Path = DEFAULT_MERGED_OUTPUT,
    env: dict[str, str] | None = None,
) -> Path:
    template_image_manifest = _load_json(template_image_manifest_path)
    design_brief = _load_json(design_brief_path)
    artifact = analyze_template_images(template_image_manifest, design_brief, env=env)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(artifact, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")
    merge_extracted_design_system_files(
        heuristic_path=output,
        codex_path=codex_extraction_path,
        output_path=merged_output_path,
    )
    return output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze template reference PNGs into outputs/extracted_design_system.json.")
    parser.add_argument("--template-image-manifest", type=Path, default=DEFAULT_TEMPLATE_IMAGE_MANIFEST)
    parser.add_argument("--design-brief", type=Path, default=DEFAULT_DESIGN_BRIEF)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--codex-extraction", type=Path, default=DEFAULT_CODEX_EXTRACTION)
    parser.add_argument("--merged-output", type=Path, default=DEFAULT_MERGED_OUTPUT)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        output = analyze_template_images_from_files(
            template_image_manifest_path=args.template_image_manifest,
            design_brief_path=args.design_brief,
            output_path=args.output,
            codex_extraction_path=args.codex_extraction,
            merged_output_path=args.merged_output,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ANALYZE_TEMPLATE_IMAGES_FAILED {exc}")
        return 1
    print(f"WROTE {output}")
    return 0


def _analyze_png(path: Path) -> dict[str, Any]:
    with Image.open(path) as image:
        rgb = image.convert("RGB")
        width, height = rgb.size
        sample = rgb.resize((80, 45))
        get_pixels = getattr(sample, "get_flattened_data", sample.getdata)
        pixels = list(get_pixels())
    dominant = _dominant_colors(pixels)
    background = dominant[0][0] if dominant else (248, 250, 252)
    blank_ratio = sum(1 for pixel in pixels if _color_distance(pixel, background) < 26) / max(1, len(pixels))
    edge_density = _edge_density(sample)
    return {
        "width_px": float(width),
        "height_px": float(height),
        "dominant_colors": Counter({color: count for color, count in dominant}),
        "blank_area_ratio": blank_ratio,
        "edge_density": edge_density,
    }


def _dominant_colors(pixels: list[tuple[int, int, int]]) -> list[tuple[tuple[int, int, int], int]]:
    buckets: Counter[tuple[int, int, int]] = Counter()
    for red, green, blue in pixels:
        bucket = (round(red / 32) * 32, round(green / 32) * 32, round(blue / 32) * 32)
        buckets[tuple(min(255, max(0, value)) for value in bucket)] += 1
    return buckets.most_common(8)


def _edge_density(image: Image.Image) -> float:
    gray = image.convert("L")
    pixels = gray.load()
    width, height = gray.size
    edges = 0
    total = 0
    for y in range(height - 1):
        for x in range(width - 1):
            current = pixels[x, y]
            if abs(current - pixels[x + 1, y]) > 24 or abs(current - pixels[x, y + 1]) > 24:
                edges += 1
            total += 1
    return edges / max(1, total)


def _palette_from_votes(votes: Counter[tuple[int, int, int]]) -> list[dict[str, Any]]:
    if not votes:
        return [_palette_item(name, hex_value, role, confidence) for name, hex_value, role, confidence in DEFAULT_PALETTE]
    total = sum(votes.values())
    roles = ["background", "surface", "accent", "line", "muted text", "primary text"]
    palette: list[dict[str, Any]] = []
    for index, (color, count) in enumerate(votes.most_common(6)):
        role = roles[min(index, len(roles) - 1)]
        confidence = min(0.92, max(0.35, count / max(1, total) + 0.35))
        palette.append(_palette_item(f"observed_{index + 1}", _hex(color), role, round(confidence, 3)))
    return palette


def _typography_estimates(design_brief: dict[str, Any], metrics_by_archetype: dict[str, dict[str, float]]) -> list[dict[str, Any]]:
    edge = _average(metrics_by_archetype, "edge_density")
    confidence = round(max(0.45, min(0.72, 0.62 - edge * 0.4)), 3)
    tone = str(design_brief.get("tone") or "").lower()
    family = "Aptos Display" if "professional" in tone or "academic" in tone else "Aptos"
    return [
        {"role": "title", "estimated_font_family": family, "size_pt": 32, "weight": "semibold", "confidence": confidence},
        {"role": "body", "estimated_font_family": "Aptos", "size_pt": 13, "weight": "regular", "confidence": max(0.4, confidence - 0.05)},
        {"role": "footer", "estimated_font_family": "Aptos", "size_pt": 7.5, "weight": "regular", "confidence": max(0.35, confidence - 0.1)},
    ]


def _layout_grid(metrics_by_archetype: dict[str, dict[str, float]]) -> dict[str, Any]:
    edge = _average(metrics_by_archetype, "edge_density")
    columns = 12 if edge >= 0.02 else 10
    return {
        "columns": columns,
        "rows": 8,
        "gutter": 0.18,
        "baseline_step": 0.12,
        "notes": f"Heuristic grid from sampled edge density {edge:.3f}; intended as observation, not final template geometry.",
    }


def _component_observations(metrics_by_archetype: dict[str, dict[str, float]]) -> list[dict[str, Any]]:
    return [
        _observation(
            f"obs-title-{archetype_id}",
            archetype_id,
            "title_block",
            {"x": 0.72, "y": 0.62, "w": 7.4, "h": 0.82},
            "Likely title area inferred from standard presentation hierarchy.",
            "Use editable PPT text box with title token.",
            _confidence_from_metrics(metrics),
        )
        for archetype_id, metrics in metrics_by_archetype.items()
    ]


def _footer_observations(metrics_by_archetype: dict[str, dict[str, float]]) -> list[dict[str, Any]]:
    return [
        _observation(
            f"obs-footer-{archetype_id}",
            archetype_id,
            "footer_standard",
            {"x": 0.72, "y": 6.84, "w": 11.9, "h": 0.28},
            "Footer lane inferred near lower safe margin.",
            "Use editable footer text and PPT line rule.",
            _confidence_from_metrics(metrics),
        )
        for archetype_id, metrics in metrics_by_archetype.items()
    ]


def _typed_observations(metrics_by_archetype: dict[str, dict[str, float]], component_type: str, bounds: dict[str, float]) -> list[dict[str, Any]]:
    target_tokens = {
        "card": ("card", "grid", "content", "standard", "closing"),
        "chart_frame": ("dashboard", "chart", "data", "kpi", "metrics"),
        "table_frame": ("table", "matrix", "comparison"),
        "image_frame": ("cover", "hero", "case", "image"),
        "diagonal_photo_panel": ("cover", "hero", "case"),
    }[component_type]
    observations = []
    for archetype_id, metrics in metrics_by_archetype.items():
        if any(token in archetype_id for token in target_tokens):
            observations.append(
                _observation(
                    f"obs-{component_type}-{archetype_id}",
                    archetype_id,
                    component_type,
                    bounds,
                    f"{component_type} region inferred from archetype and image density heuristics.",
                    "Compile as editable PowerPoint primitive, not rasterized slide content.",
                    _confidence_from_metrics(metrics),
                )
            )
    return observations


def _background_observations(metrics_by_archetype: dict[str, dict[str, float]]) -> list[dict[str, Any]]:
    return [
        _observation(
            f"obs-background-{archetype_id}",
            archetype_id,
            "background_grid",
            {"x": 0.6, "y": 0.45, "w": 12.1, "h": 6.6},
            f"Blank area ratio {metrics.get('blank_area_ratio', 0):.3f} suggests editable background field and subtle ornaments.",
            "Use PPT lines or SVG vector ornaments; do not use full-slide raster backgrounds.",
            _confidence_from_metrics(metrics),
        )
        for archetype_id, metrics in metrics_by_archetype.items()
    ]


def _density_profile(metrics_by_archetype: dict[str, dict[str, float]], registry: dict[str, dict[str, Any]]) -> dict[str, Any]:
    by_archetype: dict[str, str] = {}
    for archetype_id, metrics in metrics_by_archetype.items():
        registry_density = registry.get(archetype_id, {}).get("density_range") or []
        if "high" in registry_density:
            density = "high"
        elif metrics.get("edge_density", 0) > 0.08 or metrics.get("blank_area_ratio", 1) < 0.45:
            density = "high"
        elif metrics.get("edge_density", 0) > 0.035:
            density = "medium"
        else:
            density = str(registry_density[-1] if registry_density else "medium")
        by_archetype[archetype_id] = density if density in {"low", "medium", "high"} else "medium"
    values = set(by_archetype.values())
    overall = values.pop() if len(values) == 1 else "mixed"
    return {"overall": overall, "by_archetype": by_archetype}


def _confidence_scores(metrics_by_archetype: dict[str, dict[str, float]], vision_enabled: bool) -> dict[str, float]:
    confidence_base = 0.58 if vision_enabled else 0.5
    edge_count = len(metrics_by_archetype)
    edge_penalty = min(0.12, _average(metrics_by_archetype, "edge_density"))
    return {
        "image_size": 0.92 if edge_count else 0.35,
        "palette": round(max(0.35, confidence_base + 0.12), 3),
        "blank_area": round(max(0.35, confidence_base - edge_penalty), 3),
        "edge_density": round(max(0.35, confidence_base - edge_penalty / 2), 3),
        "component_bounds": round(max(0.3, confidence_base - 0.12), 3),
    }


def _confidence_from_metrics(metrics: dict[str, float]) -> float:
    edge = float(metrics.get("edge_density", 0.04))
    blank = float(metrics.get("blank_area_ratio", 0.5))
    return round(max(0.35, min(0.78, 0.52 + blank * 0.18 - edge * 0.25)), 3)


def _observation(
    observation_id: str,
    archetype_id: str,
    component_type: str,
    bounds: dict[str, float],
    visual_notes: str,
    editable_spec_hint: str,
    confidence: float,
) -> dict[str, Any]:
    return {
        "observation_id": observation_id,
        "source_archetype_id": archetype_id,
        "component_type": component_type,
        "bounds": bounds,
        "visual_notes": visual_notes,
        "editable_spec_hint": editable_spec_hint,
        "confidence": confidence,
    }


def _manifest_images(template_image_manifest: dict[str, Any]) -> list[dict[str, Any]]:
    images = template_image_manifest.get("images")
    return [item for item in images if isinstance(item, dict)] if isinstance(images, list) else []


def _registry_by_id() -> dict[str, dict[str, Any]]:
    try:
        return {item["id"]: item for item in load_template_archetype_registry()}
    except (OSError, ValueError, KeyError):
        return {}


def _vision_enabled(environment: dict[str, str]) -> bool:
    return environment.get("ENABLE_VISION_DESIGN_EXTRACTION", "").lower() == "true" and bool(environment.get("OPENAI_API_KEY"))


def _fallback_metrics() -> dict[str, Any]:
    return {
        "width_px": 1600.0,
        "height_px": 900.0,
        "dominant_colors": Counter({(248, 250, 252): 1, (17, 24, 39): 1, (37, 99, 235): 1}),
        "blank_area_ratio": 0.55,
        "edge_density": 0.04,
    }


def _palette_item(name: str, hex_value: str, role: str, confidence: float) -> dict[str, Any]:
    return {"name": name, "hex": hex_value, "role": role, "confidence": confidence}


def _average(metrics_by_archetype: dict[str, dict[str, float]], key: str) -> float:
    values = [float(metrics.get(key, 0.0)) for metrics in metrics_by_archetype.values()]
    return sum(values) / max(1, len(values))


def _color_distance(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    return sum(abs(a[index] - b[index]) for index in range(3)) / 3


def _hex(color: tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*color)


def _warning(code: str, message: str, severity: str, source_archetype_id: str | None = None) -> dict[str, Any]:
    warning = {"code": code, "message": message, "severity": severity}
    if source_archetype_id:
        warning["source_archetype_id"] = source_archetype_id
    return warning


def _load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _display_path(path: Path) -> str:
    return str(path.as_posix())


if __name__ == "__main__":
    raise SystemExit(main())
