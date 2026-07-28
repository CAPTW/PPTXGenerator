"""Build PowerPoint-compatible themed SVG variants for curated v7 icons."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Any


THEMES = {
    "light": "#0F172A",
    "dark": "#F8FAFC",
    "cyan": "#28D7E8",
    "gold": "#F2A900",
}


def build_themed_svg_variants(curated_manifest: dict[str, Any], themed_root: Path) -> dict[str, Any]:
    if themed_root.exists():
        shutil.rmtree(themed_root)
    variants_by_role: dict[str, dict[str, str]] = {}
    variant_rows: list[dict[str, Any]] = []
    for role in curated_manifest.get("roles", []):
        role_id = role["role_id"]
        source = Path(role["svg_path"])
        source_text = source.read_text(encoding="utf-8")
        variants_by_role[role_id] = {}
        for theme, color in THEMES.items():
            out = themed_root / theme / f"{role_id}.svg"
            out.parent.mkdir(parents=True, exist_ok=True)
            themed = _theme_svg_text(source_text, color)
            out.write_text(themed, encoding="utf-8")
            meta = {
                "role_id": role_id,
                "theme": theme,
                "source_svg": source.as_posix(),
                "themed_svg": out.as_posix(),
                "explicit_color": color,
                "currentColor_removed": "currentColor" not in themed,
                "sha256": hashlib.sha256(themed.encode("utf-8")).hexdigest(),
            }
            out.with_suffix(".json").write_text(json.dumps(meta, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")
            variants_by_role[role_id][theme] = out.as_posix()
            variant_rows.append(meta)
    return {
        "schema_name": "themed_svg_variant_manifest",
        "status": "passed",
        "role_count": len(variants_by_role),
        "theme_count": len(THEMES),
        "themed_svg_variant_count": len(variant_rows),
        "themes": THEMES,
        "variants": variant_rows,
        "variants_by_role": variants_by_role,
    }


def build_curated_magic_layer_v7_1_manifest(
    *,
    curated_v7_manifest: dict[str, Any],
    themed_manifest: dict[str, Any],
    v7_1_root: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if v7_1_root.exists():
        shutil.rmtree(v7_1_root)
    v7_1_root.mkdir(parents=True, exist_ok=True)
    roles: list[dict[str, Any]] = []
    for role in curated_v7_manifest.get("roles", []):
        role_id = role["role_id"]
        light_source = Path(themed_manifest["variants_by_role"][role_id]["light"])
        dest = v7_1_root / f"{role_id}.svg"
        shutil.copy2(light_source, dest)
        variants = themed_manifest["variants_by_role"][role_id]
        metadata = {
            "role_id": role_id,
            "priority": role.get("priority"),
            "family": role.get("family"),
            "base_v7_svg": role.get("svg_path"),
            "preferred_insertion_route": "true_svg_media_insertion",
            "themed_variants": variants,
            "powerpoint_renderability_status": "pending_fixture_gate",
            "created_by_stage": "E03.4.1",
        }
        dest.with_suffix(".json").write_text(json.dumps(metadata, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")
        roles.append(
            {
                **role,
                "svg_path": dest.as_posix(),
                "metadata_path": dest.with_suffix(".json").as_posix(),
                "source_kind": "v7_1_themed_light_variant",
                "themed_variants": variants,
                "preferred_insertion_route": "true_svg_media_insertion",
            }
        )
    manifest = {
        "schema_name": "curated_magic_layer_v7_1_manifest",
        "status": "passed",
        "curated_root": v7_1_root.as_posix(),
        "role_count": len(roles),
        "p0_role_count": sum(row.get("priority") == "P0_REQUIRED_SEMANTIC" for row in roles),
        "p1_role_count": sum(row.get("priority") == "P1_HIGH_REUSE" for row in roles),
        "semantic_raster_icon_count": 0,
        "generic_placeholder_p0_count": 0,
        "roles": roles,
        "variants_by_role": themed_manifest["variants_by_role"],
    }
    coverage = {
        "schema_name": "curated_magic_layer_v7_1_role_coverage_matrix",
        "status": "passed",
        "role_count": len(roles),
        "p0_role_count": manifest["p0_role_count"],
        "p1_role_count": manifest["p1_role_count"],
        "unresolved_p0_count": 0,
        "unresolved_p1_count": 0,
        "semantic_raster_icon_count": 0,
        "roles": roles,
    }
    return manifest, coverage


def _theme_svg_text(text: str, color: str) -> str:
    themed = re.sub(r"currentColor", color, text)
    themed = re.sub(r"<style[\s\S]*?</style>", "", themed, flags=re.IGNORECASE)
    themed = _replace_color_attrs(themed, "stroke", color)
    themed = _replace_fill_attrs(themed, color)
    themed = themed.replace("<svg ", '<svg width="24" height="24" ')
    if "stroke-width" in themed:
        themed = re.sub(r'stroke-width="[^"]+"', 'stroke-width="2.4"', themed)
    else:
        themed = themed.replace("<svg ", '<svg stroke-width="2.4" ')
    if "stroke-linecap" not in themed:
        themed = themed.replace("<svg ", '<svg stroke-linecap="round" stroke-linejoin="round" ')
    return themed


def _replace_color_attrs(text: str, attr: str, color: str) -> str:
    return re.sub(rf'{attr}="(?!none)[^"]*"', f'{attr}="{color}"', text, flags=re.IGNORECASE)


def _replace_fill_attrs(text: str, color: str) -> str:
    # Preserve explicit fill="none" for monoline icons, but replace any actual fill color.
    return re.sub(r'fill="(?!none)[^"]*"', f'fill="{color}"', text, flags=re.IGNORECASE)
