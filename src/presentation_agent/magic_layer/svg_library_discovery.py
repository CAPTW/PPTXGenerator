"""Discover existing local SVG assets for SVG01 binding proof."""

from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from functools import lru_cache
from pathlib import Path
from typing import Any


CANDIDATE_DIRS = ("assets", "icons", "public", "resources", "design_assets", "design_runs", "src")
VISIBLE_TAGS = ("path", "circle", "ellipse", "rect", "line", "polyline", "polygon")
SVG_NS = "{http://www.w3.org/2000/svg}"


def discover_svg_library(repo_root: str | Path) -> dict[str, Any]:
    """Return a normalized discovery report for parseable SVG files."""
    root = Path(repo_root).resolve()
    assets = _discover_cached(root.as_posix())
    return {
        "schema_name": "svg_library_discovery_report",
        "status": "passed" if assets else "failed",
        "repo_root": root.as_posix(),
        "candidate_dirs": [name for name in CANDIDATE_DIRS if (root / name).exists()],
        "svg_asset_count": len(assets),
        "invalid_asset_count": 0,
        "assets": [dict(asset) for asset in assets],
        "canva_parity_claimed": False,
    }


@lru_cache(maxsize=4)
def _discover_cached(root_text: str) -> tuple[dict[str, Any], ...]:
    root = Path(root_text)
    svg_paths: list[Path] = []
    for name in CANDIDATE_DIRS:
        folder = root / name
        if folder.exists():
            svg_paths.extend(folder.rglob("*.svg"))
    parsed: list[dict[str, Any]] = []
    for path in sorted(set(svg_paths), key=lambda p: p.as_posix().lower()):
        asset = _parse_svg_asset(root, path)
        if asset["parse_status"] == "parsed" and asset["validity_status"] == "valid":
            parsed.append(asset)
    return tuple(parsed)


def _parse_svg_asset(root: Path, path: Path) -> dict[str, Any]:
    rel = _relative_posix(root, path)
    data = path.read_bytes()
    text = data.decode("utf-8", errors="ignore")
    base = {
        "asset_id": _asset_id(rel),
        "file_path": rel,
        "filename": path.name,
        "normalized_name": _normalize_name(path.stem),
        "category_guess": _category_guess(rel, path.stem),
        "semantic_keywords": _semantic_keywords(path.stem, rel),
        "file_size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }
    try:
        element = ET.fromstring(text)
    except ET.ParseError as exc:
        return {
            **base,
            "width": None,
            "height": None,
            "viewBox": None,
            "color_mode": "unknown",
            "stroke_usage": "unknown",
            "fill_usage": "unknown",
            "path_count": 0,
            "primitive_count": 0,
            "validity_status": "invalid",
            "parse_status": f"parse_error:{exc}",
        }
    viewbox = element.attrib.get("viewBox") or element.attrib.get("viewbox")
    path_count = len(_findall_any_ns(element, "path"))
    primitive_count = sum(len(_findall_any_ns(element, tag)) for tag in VISIBLE_TAGS if tag != "path")
    lower = text.lower()
    validity_failures = []
    if "<image" in lower or "data:image" in lower or "base64," in lower:
        validity_failures.append("embedded_raster")
    if not viewbox and not (element.attrib.get("width") and element.attrib.get("height")):
        validity_failures.append("missing_normalizable_bounds")
    if path_count + primitive_count == 0:
        validity_failures.append("no_visible_primitives")
    return {
        **base,
        "width": element.attrib.get("width"),
        "height": element.attrib.get("height"),
        "viewBox": viewbox,
        "color_mode": _color_mode(lower),
        "stroke_usage": _usage(lower, "stroke"),
        "fill_usage": _usage(lower, "fill"),
        "path_count": path_count,
        "primitive_count": primitive_count,
        "validity_status": "valid" if not validity_failures else "invalid",
        "validity_failures": validity_failures,
        "parse_status": "parsed",
    }


def _findall_any_ns(element: ET.Element, tag: str) -> list[ET.Element]:
    return list(element.iter(tag)) + list(element.iter(f"{SVG_NS}{tag}"))


def _asset_id(rel_path: str) -> str:
    stem = Path(rel_path).stem
    digest = hashlib.sha1(rel_path.encode("utf-8")).hexdigest()[:8]
    return f"{_normalize_name(stem)}_{digest}"


def _normalize_name(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()
    return value or "svg_asset"


def _semantic_keywords(stem: str, rel: str) -> list[str]:
    tokens = re.split(r"[^a-zA-Z0-9]+", f"{stem} {rel}")
    stop = {"svg", "assets", "icons", "curated", "normalized", "vendor", "outline", "magic", "layer", "v6", "v7", "v7_1"}
    return sorted({token.lower() for token in tokens if token and token.lower() not in stop})


def _category_guess(rel: str, stem: str) -> str:
    text = f"{rel} {stem}".lower()
    if "checklist" in text:
        return "checklist"
    if any(token in text for token in ("ppe", "safety", "leak", "chemical", "teamwork", "hardhat")):
        return "safety"
    if any(token in text for token in ("chart", "kpi", "dashboard", "gauge")):
        return "dashboard"
    if any(token in text for token in ("table", "matrix")):
        return "table_matrix"
    if any(token in text for token in ("arrow", "chevron", "route", "milestone", "process")):
        return "navigation_process"
    return "general"


def _color_mode(lower_svg: str) -> str:
    if "currentcolor" in lower_svg:
        return "currentColor"
    if re.search(r"(stroke|fill)=[\"']#?[0-9a-f]{3,8}[\"']", lower_svg):
        return "fixed"
    return "mixed_or_inherited"


def _usage(lower_svg: str, attr: str) -> str:
    if re.search(rf"\b{attr}=", lower_svg):
        return "present"
    return "absent"


def _relative_posix(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return path.resolve().as_posix()
