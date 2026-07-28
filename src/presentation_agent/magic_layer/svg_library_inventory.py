"""Local SVG inventory helpers for Magic Layer D03."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any


DEFAULT_SVG_ROOTS = [
    Path("assets/icons/normalized/tabler"),
    Path("assets/icons/normalized"),
    Path("assets/icons"),
    Path("design_runs/run_002/outputs/harness_v3_svg_icon_promotion/generated_svg"),
]


def build_svg_library_inventory(repo_root: Path, roots: list[Path] | None = None) -> dict[str, Any]:
    """Scan local SVG files without modifying them."""

    active_roots = roots or DEFAULT_SVG_ROOTS
    seen_paths: set[Path] = set()
    entries: list[dict[str, Any]] = []
    for root in active_roots:
        abs_root = repo_root / root
        if not abs_root.exists():
            continue
        for path in sorted(abs_root.rglob("*.svg")):
            resolved = path.resolve()
            if resolved in seen_paths:
                continue
            seen_paths.add(resolved)
            entries.append(_svg_entry(repo_root, path))

    name_counts = Counter(entry["filename"] for entry in entries)
    duplicate_names = sorted(name for name, count in name_counts.items() if count > 1)
    normalized_entries = [entry for entry in entries if "/normalized/" in entry["path"].replace("\\", "/")]
    preferred_root = repo_root / "assets/icons/normalized/tabler"
    return {
        "schema_name": "svg_library_inventory_d03",
        "status": "passed" if entries else "missing_svg_assets",
        "preferred_library_path": _rel(repo_root, preferred_root),
        "total_svg_count": len(entries),
        "normalized_svg_count": len(normalized_entries),
        "files_with_currentColor": sum(1 for entry in entries if entry["has_currentColor"]),
        "files_with_viewBox": sum(1 for entry in entries if entry["has_viewBox"]),
        "files_missing_viewBox": sum(1 for entry in entries if not entry["has_viewBox"]),
        "files_with_fixed_fill_or_stroke_colors": sum(1 for entry in entries if entry["has_fixed_fill_or_stroke_color"]),
        "duplicate_names": duplicate_names,
        "source_svg_files_modified": False,
        "entries": entries,
        "icon_filename_aliases": _aliases(entries),
    }


def find_svg_for_names(inventory: dict[str, Any], names: list[str]) -> dict[str, Any] | None:
    """Return the first matching inventory entry for preferred/fallback names."""

    entries = inventory.get("entries") or []
    by_alias: dict[str, dict[str, Any]] = {}
    for entry in entries:
        for alias in entry.get("aliases") or []:
            by_alias.setdefault(alias.lower(), entry)
    for name in names:
        key = name.lower().replace(".svg", "")
        if key in by_alias:
            return by_alias[key]
    return None


def _svg_entry(repo_root: Path, path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    stem = path.stem
    rel_path = _rel(repo_root, path)
    fixed_color_tokens = ["fill=\"#", "fill=' #", "stroke=\"#", "stroke='#", "fill=\"rgb", "stroke=\"rgb"]
    has_fixed = any(token in text for token in fixed_color_tokens)
    aliases = {stem, stem.replace("tabler__", ""), stem.replace("_", "-")}
    if not stem.startswith("tabler__"):
        aliases.add(f"tabler__{stem}")
    if stem.startswith("tabler__"):
        aliases.add(stem.removeprefix("tabler__"))
    return {
        "path": rel_path,
        "filename": path.name,
        "icon_id": stem,
        "aliases": sorted(alias for alias in aliases if alias),
        "has_currentColor": "currentColor" in text,
        "has_viewBox": "viewBox" in text,
        "has_fixed_fill_or_stroke_color": has_fixed,
        "byte_size": path.stat().st_size,
        "preferred_normalized": "/normalized/tabler/" in rel_path.replace("\\", "/"),
    }


def _aliases(entries: list[dict[str, Any]]) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for entry in entries:
        for alias in entry.get("aliases") or []:
            aliases.setdefault(alias, entry["path"])
    return aliases


def _rel(repo_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()

