"""Inspect PPTX package proof for SVG-source semantic icon bindings."""

from __future__ import annotations

import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


CNVPR = ".//{http://schemas.openxmlformats.org/presentationml/2006/main}cNvPr"
REL = "{http://schemas.openxmlformats.org/package/2006/relationships}Relationship"


def inspect_svg_pptx_package(pptx_path: str | Path) -> dict[str, Any]:
    path = Path(pptx_path)
    names: list[str] = []
    svg_media: list[str] = []
    raster_media: list[str] = []
    svg_relationships: list[dict[str, str]] = []
    has_svg_content_type = False
    with zipfile.ZipFile(path) as archive:
        namelist = archive.namelist()
        for name in namelist:
            lower = name.lower()
            if lower.startswith("ppt/media/") and lower.endswith(".svg"):
                svg_media.append(name)
            if lower.startswith("ppt/media/") and lower.endswith((".png", ".jpg", ".jpeg")):
                raster_media.append(name)
        if "[Content_Types].xml" in namelist:
            has_svg_content_type = "image/svg+xml" in archive.read("[Content_Types].xml").decode("utf-8", errors="ignore")
        for name in namelist:
            lower = name.lower()
            if lower.startswith("ppt/slides/slide") and lower.endswith(".xml"):
                root = ET.fromstring(archive.read(name))
                for element in root.findall(CNVPR):
                    shape_name = element.attrib.get("name", "")
                    if shape_name:
                        names.append(shape_name)
            if lower.startswith("ppt/slides/_rels/") and lower.endswith(".rels"):
                root = ET.fromstring(archive.read(name))
                for rel in root.findall(REL):
                    target = rel.attrib.get("Target", "")
                    if target.lower().endswith(".svg"):
                        svg_relationships.append({"rels_part": name, "target": target, "relationship_id": rel.attrib.get("Id", "")})
    native_names = [name for name in names if name.startswith("svg_native::")]
    svg_media_names = [name for name in names if name.startswith("svg_media::")]
    provenance_intents = _unique_intents(native_names + svg_media_names)
    native_without_source = [name for name in native_names if len(name.split("::")) < 4 or not name.split("::")[2]]
    raster_fallback = [name for name in names if "raster_fallback" in name or name.startswith("sem_icon_png::")]
    empty_circle = [name for name in names if "empty_circle" in name]
    insertion_mode = "NATIVE_PATH_CONVERSION" if native_names else ("DIRECT_SVG_MEDIA" if svg_media else "NONE")
    status = "passed" if provenance_intents and not native_without_source and not raster_fallback and not empty_circle else "failed"
    return {
        "schema_name": "svg_package_inventory",
        "status": status,
        "pptx_path": path.as_posix(),
        "ppt_media_svg_count": len(svg_media),
        "ppt_media_png_count": len(raster_media),
        "svg_media": svg_media,
        "raster_media": raster_media,
        "content_types_include_image_svg_xml": has_svg_content_type,
        "svg_relationship_count": len(svg_relationships),
        "svg_relationships": svg_relationships,
        "slide_object_name_count": len(names),
        "semantic_icon_native_shape_count": len(native_names),
        "semantic_icon_svg_media_object_count": len(svg_media_names),
        "semantic_icon_with_source_svg_provenance_count": len(provenance_intents),
        "semantic_icon_raster_fallback_count": len(raster_fallback),
        "empty_circle_placeholder_count": len(empty_circle),
        "procedural_native_without_source_svg_asset_id_count": len(native_without_source),
        "insertion_mode_detected": insertion_mode,
        "object_names": names,
        "source_svg_provenance_intents": sorted(provenance_intents),
        "canva_parity_claimed": False,
    }


def _unique_intents(names: list[str]) -> set[str]:
    intents = set()
    for name in names:
        match = re.match(r"^(?:svg_native|svg_media)::([^:]+)::([^:]+)", name)
        if match and match.group(2):
            intents.add(match.group(1))
    return intents
