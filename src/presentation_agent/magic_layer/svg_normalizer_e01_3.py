"""SVG normalizer for E01.3 generated and copied icons."""

from __future__ import annotations

from pathlib import Path


def normalize_svg_text(svg_text: str) -> str:
    text = svg_text.replace('width="24"', "").replace('height="24"', "")
    if "viewBox=" not in text:
        text = text.replace("<svg ", '<svg viewBox="0 0 24 24" ', 1)
    text = text.replace('stroke="#000"', 'stroke="currentColor"').replace('stroke="black"', 'stroke="currentColor"')
    if "stroke=" not in text:
        text = text.replace("<svg ", '<svg stroke="currentColor" ', 1)
    if "fill=" not in text:
        text = text.replace("<svg ", '<svg fill="none" ', 1)
    return text


def normalize_svg_file(source: Path, target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(normalize_svg_text(source.read_text(encoding="utf-8")), encoding="utf-8")
    return target

