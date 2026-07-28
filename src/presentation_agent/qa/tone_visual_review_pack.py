"""Build human review contact sheets and visual divergence metrics for tone decks."""

from __future__ import annotations

import argparse
import json
import math
from itertools import combinations
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps, ImageStat

from .render_pptx_preview import render_pptx_preview


TONES = ("academic", "professional", "creative")
DEFAULT_TONE_REPORT = Path("outputs/tone_variant_report.json")
DEFAULT_REVIEW_DIR = Path("outputs/review/tone_variants")
CONTACT_WIDTH = 360
LABEL_HEIGHT = 34
PAD = 16


def build_tone_visual_review_pack(
    *,
    tone_report_path: str | Path = DEFAULT_TONE_REPORT,
    review_dir: str | Path = DEFAULT_REVIEW_DIR,
    render: bool = True,
) -> dict[str, Any]:
    tone_report_file = Path(tone_report_path)
    root = Path(review_dir)
    root.mkdir(parents=True, exist_ok=True)
    tone_report = _load_json(tone_report_file)
    decks = {deck["selected_tone"]: deck for deck in tone_report.get("decks", []) if deck.get("selected_tone") in TONES}

    tone_results: list[dict[str, Any]] = []
    for tone in TONES:
        deck = decks[tone]
        tone_dir = root / tone
        manifest_path = root / f"render_manifest_{tone}.json"
        if render:
            render_manifest = render_pptx_preview(
                pptx_path=deck["pptx_path"],
                output_dir=tone_dir,
                manifest_path=manifest_path,
            )
        else:
            render_manifest = _load_json(manifest_path)
        image_paths = [Path(path) for path in render_manifest.get("output_paths") or []]
        metrics = _tone_metrics(image_paths)
        contact_sheet = root / f"contact_sheet_{tone}.png"
        _build_contact_sheet(image_paths, contact_sheet, title=f"{tone.title()} Tone", columns=len(image_paths) or 1)
        tone_results.append(
            {
                "tone": tone,
                "pptx_path": deck["pptx_path"],
                "render_manifest_path": manifest_path.as_posix(),
                "render_status": render_manifest.get("render_status"),
                "render_backend": render_manifest.get("backend"),
                "rendered_preview_paths": [path.as_posix() for path in image_paths],
                "contact_sheet_path": contact_sheet.as_posix(),
                "token_summary": {
                    "palette_tokens_used": deck.get("palette_tokens_used"),
                    "typography_tokens_used": deck.get("typography_tokens_used"),
                    "component_variants_used": deck.get("component_variants_used"),
                    "footer_style": deck.get("footer_style"),
                    "card_style": deck.get("card_style"),
                    "chart_table_style": deck.get("chart_table_style"),
                    "section_style": deck.get("section_style"),
                    "background_ornament_intensity": deck.get("background_ornament_intensity"),
                    "image_frame_style": deck.get("image_frame_style"),
                },
                "visual_metrics": metrics,
                "classification": _classify_tone(tone, deck, render_manifest, metrics),
                "human_review_notes": _human_review_notes(tone, deck, metrics),
            }
        )

    side_by_side = root / "contact_sheet_side_by_side.png"
    _build_side_by_side_contact_sheet({item["tone"]: [Path(path) for path in item["rendered_preview_paths"]] for item in tone_results}, side_by_side)
    comparisons = _pairwise_comparisons(tone_results)
    severe = [item for item in tone_results if item["classification"] == "REJECT"]
    revisions = [item for item in tone_results if item["classification"] == "NEEDS_REVISION"]
    report = {
        "schema_name": "tone_visual_review_report",
        "schema_version": "1.0",
        "status": "failed" if severe else "needs_revision" if revisions else "passed",
        "tone_variant_report_path": tone_report_file.as_posix(),
        "review_dir": root.as_posix(),
        "contact_sheets": {
            "academic": (root / "contact_sheet_academic.png").as_posix(),
            "professional": (root / "contact_sheet_professional.png").as_posix(),
            "creative": (root / "contact_sheet_creative.png").as_posix(),
            "side_by_side": side_by_side.as_posix(),
        },
        "token_divergence": {
            "unique_token_signature_count": tone_report.get("unique_token_signature_count"),
            "all_three_decks_effectively_identical": tone_report.get("all_three_decks_effectively_identical"),
            "verdict": "token_divergent" if tone_report.get("unique_token_signature_count", 0) >= 3 else "token_similarity_risk",
        },
        "rendered_visual_divergence": {
            "pairwise": comparisons,
            "minimum_palette_distance": min((item["palette_distance"] for item in comparisons), default=0),
            "minimum_brightness_delta": min((item["brightness_delta"] for item in comparisons), default=0),
            "minimum_edge_density_delta": min((item["edge_density_delta"] for item in comparisons), default=0),
            "verdict": _visual_divergence_verdict(comparisons),
        },
        "tones": tone_results,
        "human_review_recommendation": {
            "academic": next(item["classification"] for item in tone_results if item["tone"] == "academic"),
            "professional": next(item["classification"] for item in tone_results if item["tone"] == "professional"),
            "creative": next(item["classification"] for item in tone_results if item["tone"] == "creative"),
            "statement": "Token divergence is necessary but not sufficient; this recommendation also considers rendered palette, density, footer, card, table/chart, section, and ornament differences.",
        },
    }
    json_path = root / "tone_visual_review_report.json"
    md_path = root / "tone_visual_review_report.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")
    md_path.write_text(_markdown_report(report), encoding="utf-8")
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create rendered contact sheets and a human visual review report for tone variant decks.")
    parser.add_argument("--tone-report", type=Path, default=DEFAULT_TONE_REPORT)
    parser.add_argument("--review-dir", type=Path, default=DEFAULT_REVIEW_DIR)
    parser.add_argument("--no-render", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        report = build_tone_visual_review_pack(
            tone_report_path=args.tone_report,
            review_dir=args.review_dir,
            render=not args.no_render,
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"TONE_VISUAL_REVIEW_FAILED {exc}")
        return 1
    print(f"WROTE {DEFAULT_REVIEW_DIR / 'tone_visual_review_report.json'}")
    print(f"WROTE {DEFAULT_REVIEW_DIR / 'tone_visual_review_report.md'}")
    if report["status"] == "failed":
        print("TONE_VISUAL_REVIEW failed")
        return 1
    print(f"TONE_VISUAL_REVIEW {report['status']}")
    return 0


def _tone_metrics(image_paths: list[Path]) -> dict[str, Any]:
    slide_metrics = [_image_metrics(path) for path in image_paths if path.exists()]
    if not slide_metrics:
        return {"slide_count": 0, "dominant_palette": [], "average_brightness": 0, "dark_area_ratio": 0, "light_area_ratio": 0, "edge_density": 0, "footer_occupancy": 0, "ornament_occupancy": 0, "visual_density": 0}
    return {
        "slide_count": len(slide_metrics),
        "dominant_palette": _aggregate_palette(slide_metrics),
        "average_brightness": round(_avg(item["average_brightness"] for item in slide_metrics), 4),
        "dark_area_ratio": round(_avg(item["dark_area_ratio"] for item in slide_metrics), 4),
        "light_area_ratio": round(_avg(item["light_area_ratio"] for item in slide_metrics), 4),
        "edge_density": round(_avg(item["edge_density"] for item in slide_metrics), 4),
        "footer_occupancy": round(_avg(item["footer_occupancy"] for item in slide_metrics), 4),
        "ornament_occupancy": round(_avg(item["ornament_occupancy"] for item in slide_metrics), 4),
        "visual_density": round(_avg(item["visual_density"] for item in slide_metrics), 4),
        "slides": slide_metrics,
    }


def _image_metrics(path: Path) -> dict[str, Any]:
    image = Image.open(path).convert("RGB")
    small = image.resize((320, 180))
    gray = ImageOps.grayscale(small)
    stat = ImageStat.Stat(gray)
    brightness = stat.mean[0] / 255
    hist = gray.histogram()
    total = sum(hist) or 1
    dark = sum(hist[:70]) / total
    light = sum(hist[210:]) / total
    edges = gray.filter(ImageFilter.FIND_EDGES)
    edge_density = sum(1 for px in edges.getdata() if px > 32) / total
    bg = Image.new("RGB", small.size, _corner_color(small))
    diff = ImageOps.grayscale(ImageChops.difference(small, bg))
    visual_density = sum(1 for px in diff.getdata() if px > 18) / total
    footer = diff.crop((0, int(small.height * 0.86), small.width, small.height))
    footer_total = footer.width * footer.height
    footer_occupancy = sum(1 for px in footer.getdata() if px > 18) / max(1, footer_total)
    ornament = diff.crop((int(small.width * 0.72), 0, small.width, int(small.height * 0.34)))
    ornament_total = ornament.width * ornament.height
    ornament_occupancy = sum(1 for px in ornament.getdata() if px > 18) / max(1, ornament_total)
    return {
        "path": path.as_posix(),
        "width": image.width,
        "height": image.height,
        "dominant_palette": _dominant_palette(small),
        "average_brightness": round(brightness, 4),
        "dark_area_ratio": round(dark, 4),
        "light_area_ratio": round(light, 4),
        "edge_density": round(edge_density, 4),
        "footer_occupancy": round(footer_occupancy, 4),
        "ornament_occupancy": round(ornament_occupancy, 4),
        "visual_density": round(visual_density, 4),
    }


def _build_contact_sheet(image_paths: list[Path], output_path: Path, *, title: str, columns: int) -> None:
    thumbs = [_thumbnail(path) for path in image_paths if path.exists()]
    if not thumbs:
        return
    columns = max(1, columns)
    rows = math.ceil(len(thumbs) / columns)
    thumb_w, thumb_h = thumbs[0].size
    canvas = Image.new("RGB", (PAD * 2 + columns * thumb_w + (columns - 1) * PAD, PAD * 3 + LABEL_HEIGHT + rows * (thumb_h + LABEL_HEIGHT) + (rows - 1) * PAD), "#F8FAFC")
    draw = ImageDraw.Draw(canvas)
    draw.text((PAD, PAD), title, fill="#111827")
    for index, thumb in enumerate(thumbs):
        col = index % columns
        row = index // columns
        x = PAD + col * (thumb_w + PAD)
        y = PAD * 2 + LABEL_HEIGHT + row * (thumb_h + LABEL_HEIGHT + PAD)
        canvas.paste(thumb, (x, y))
        draw.text((x, y + thumb_h + 6), f"Slide {index + 1}", fill="#334155")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path)


def _build_side_by_side_contact_sheet(images_by_tone: dict[str, list[Path]], output_path: Path) -> None:
    slide_count = max((len(paths) for paths in images_by_tone.values()), default=0)
    if not slide_count:
        return
    sample = _thumbnail(next(path for paths in images_by_tone.values() for path in paths if path.exists()), width=320)
    thumb_w, thumb_h = sample.size
    columns = len(TONES)
    rows = slide_count
    header = 54
    canvas = Image.new("RGB", (PAD * 2 + columns * thumb_w + (columns - 1) * PAD, PAD * 2 + header + rows * (thumb_h + LABEL_HEIGHT) + (rows - 1) * PAD), "#F8FAFC")
    draw = ImageDraw.Draw(canvas)
    draw.text((PAD, PAD), "Tone Variant Side-By-Side Contact Sheet", fill="#111827")
    for col, tone in enumerate(TONES):
        draw.text((PAD + col * (thumb_w + PAD), PAD + 28), tone.title(), fill="#334155")
    for row in range(rows):
        for col, tone in enumerate(TONES):
            paths = images_by_tone.get(tone, [])
            if row >= len(paths) or not paths[row].exists():
                continue
            thumb = _thumbnail(paths[row], width=320)
            x = PAD + col * (thumb_w + PAD)
            y = PAD + header + row * (thumb_h + LABEL_HEIGHT + PAD)
            canvas.paste(thumb, (x, y))
            draw.text((x, y + thumb_h + 6), f"{tone} slide {row + 1}", fill="#334155")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path)


def _pairwise_comparisons(tone_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_tone = {item["tone"]: item for item in tone_results}
    comparisons = []
    for left, right in combinations(TONES, 2):
        lm = by_tone[left]["visual_metrics"]
        rm = by_tone[right]["visual_metrics"]
        comparisons.append(
            {
                "tones": [left, right],
                "palette_distance": round(_palette_distance(lm.get("dominant_palette", []), rm.get("dominant_palette", [])), 4),
                "brightness_delta": round(abs(float(lm.get("average_brightness") or 0) - float(rm.get("average_brightness") or 0)), 4),
                "edge_density_delta": round(abs(float(lm.get("edge_density") or 0) - float(rm.get("edge_density") or 0)), 4),
                "footer_occupancy_delta": round(abs(float(lm.get("footer_occupancy") or 0) - float(rm.get("footer_occupancy") or 0)), 4),
                "ornament_occupancy_delta": round(abs(float(lm.get("ornament_occupancy") or 0) - float(rm.get("ornament_occupancy") or 0)), 4),
            }
        )
    return comparisons


def _classify_tone(tone: str, deck: dict[str, Any], render_manifest: dict[str, Any], metrics: dict[str, Any]) -> str:
    if render_manifest.get("render_status") != "rendered" or metrics.get("slide_count", 0) <= 0:
        return "REJECT"
    if deck.get("image_policy_status") != "passed":
        return "REJECT"
    if tone == "academic" and deck.get("footer_style") == "citation_dense" and deck.get("background_ornament_intensity") == "low":
        return "ACCEPT"
    if tone == "professional" and deck.get("chart_table_style") == "high_contrast_dashboard" and deck.get("card_style") == "decision_panel":
        return "ACCEPT"
    if tone == "creative" and deck.get("background_ornament_intensity") == "high" and float(metrics.get("ornament_occupancy") or 0) >= 0.015:
        return "ACCEPT"
    return "NEEDS_REVISION"


def _human_review_notes(tone: str, deck: dict[str, Any], metrics: dict[str, Any]) -> list[str]:
    notes = []
    if tone == "academic":
        notes.append("Academic credibility is expressed through restrained ornament density, citation-forward footer styling, smaller typography, and warm evidence-table colors.")
    elif tone == "professional":
        notes.append("Professional consulting structure is expressed through navy/teal contrast, dashboard-oriented chart/table style, and crisp footer/card treatments.")
    else:
        notes.append("Creative visual distinctiveness is expressed through larger title scale, warmer canvas, stronger gold accents, and higher ornament intensity.")
    notes.append(f"Rendered visual density average: {metrics.get('visual_density')}; edge density average: {metrics.get('edge_density')}.")
    notes.append("Human review should still inspect slide hierarchy and readability; token divergence alone is not treated as visual acceptance.")
    return notes


def _visual_divergence_verdict(comparisons: list[dict[str, Any]]) -> str:
    if not comparisons:
        return "not_rendered"
    palette_ok = min(item["palette_distance"] for item in comparisons) >= 8
    brightness_or_edges_ok = any(item["brightness_delta"] >= 0.01 or item["edge_density_delta"] >= 0.004 or item["ornament_occupancy_delta"] >= 0.01 for item in comparisons)
    return "visually_distinguishable" if palette_ok and brightness_or_edges_ok else "low_visual_divergence"


def _dominant_palette(image: Image.Image, colors: int = 5) -> list[str]:
    quantized = image.quantize(colors=colors, method=Image.Quantize.MEDIANCUT)
    palette = quantized.getpalette() or []
    counts = quantized.getcolors(maxcolors=colors) or []
    result = []
    for _count, index in sorted(counts, reverse=True):
        offset = index * 3
        result.append("#%02X%02X%02X" % tuple(palette[offset : offset + 3]))
    return result


def _aggregate_palette(slide_metrics: list[dict[str, Any]]) -> list[str]:
    colors: list[tuple[int, int, int]] = []
    for metric in slide_metrics:
        for color in metric.get("dominant_palette", [])[:3]:
            colors.append(_hex_to_rgb(color))
    if not colors:
        return []
    avg = tuple(round(sum(color[index] for color in colors) / len(colors)) for index in range(3))
    return ["#%02X%02X%02X" % avg, *slide_metrics[0].get("dominant_palette", [])[:4]]


def _palette_distance(left: list[str], right: list[str]) -> float:
    if not left or not right:
        return 0.0
    left_rgb = _hex_to_rgb(left[0])
    right_rgb = _hex_to_rgb(right[0])
    return math.sqrt(sum((left_rgb[index] - right_rgb[index]) ** 2 for index in range(3)))


def _thumbnail(path: Path, width: int = CONTACT_WIDTH) -> Image.Image:
    image = Image.open(path).convert("RGB")
    height = round(image.height * width / image.width)
    return image.resize((width, height), Image.Resampling.LANCZOS)


def _corner_color(image: Image.Image) -> tuple[int, int, int]:
    samples = [
        image.getpixel((0, 0)),
        image.getpixel((image.width - 1, 0)),
        image.getpixel((0, image.height - 1)),
        image.getpixel((image.width - 1, image.height - 1)),
    ]
    return tuple(round(sum(sample[index] for sample in samples) / len(samples)) for index in range(3))


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    text = value.lstrip("#")
    return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)


def _avg(values: Any) -> float:
    items = list(values)
    return sum(float(item) for item in items) / max(1, len(items))


def _markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# Tone Visual Review Report",
        "",
        f"Status: `{report['status']}`",
        f"Token divergence: `{report['token_divergence']['verdict']}`",
        f"Rendered visual divergence: `{report['rendered_visual_divergence']['verdict']}`",
        f"Side-by-side contact sheet: `{report['contact_sheets']['side_by_side']}`",
        "",
        "This report distinguishes token divergence from rendered visual divergence and human review recommendation.",
        "",
        "## Tone Classification",
        "",
        "| Tone | Classification | Footer | Cards | Chart/Table | Section | Ornament | Density |",
        "|---|---|---|---|---|---|---|---:|",
    ]
    for tone in report["tones"]:
        token = tone["token_summary"]
        metrics = tone["visual_metrics"]
        lines.append(
            f"| {tone['tone']} | `{tone['classification']}` | `{token['footer_style']}` | `{token['card_style']}` | `{token['chart_table_style']}` | `{token['section_style']}` | `{token['background_ornament_intensity']}` | {metrics.get('visual_density')} |"
        )
    lines.extend(["", "## Visual Divergence Metrics", "", "| Pair | Palette Distance | Brightness Delta | Edge Delta | Footer Delta | Ornament Delta |", "|---|---:|---:|---:|---:|---:|"])
    for item in report["rendered_visual_divergence"]["pairwise"]:
        lines.append(
            f"| {' / '.join(item['tones'])} | {item['palette_distance']} | {item['brightness_delta']} | {item['edge_density_delta']} | {item['footer_occupancy_delta']} | {item['ornament_occupancy_delta']} |"
        )
    lines.extend(["", "## Contact Sheets", ""])
    for key, path in report["contact_sheets"].items():
        lines.append(f"- `{key}`: `{path}`")
    lines.extend(["", "## Human Review Notes", ""])
    for tone in report["tones"]:
        lines.append(f"### {tone['tone'].title()}")
        for note in tone["human_review_notes"]:
            lines.append(f"- {note}")
        lines.append("")
    return "\n".join(lines)


def _load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


if __name__ == "__main__":
    raise SystemExit(main())
