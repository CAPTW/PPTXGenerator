from __future__ import annotations

import hashlib
import re
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


NS = {
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "c": "http://schemas.openxmlformats.org/drawingml/2006/chart",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_xml(package: zipfile.ZipFile, part: str) -> ET.Element | None:
    try:
        return ET.fromstring(package.read(part))
    except (KeyError, ET.ParseError):
        return None


def numeric_slide_sort(path: str) -> tuple[int, str]:
    match = re.search(r"slide(\d+)\.xml$", path)
    return (int(match.group(1)) if match else 10_000, path)


def list_package_parts(names: list[str]) -> dict[str, list[str]]:
    return {
        "slides": sorted([name for name in names if name.startswith("ppt/slides/slide") and name.endswith(".xml")], key=numeric_slide_sort),
        "slide_layouts": sorted([name for name in names if name.startswith("ppt/slideLayouts/") and name.endswith(".xml")]),
        "slide_masters": sorted([name for name in names if name.startswith("ppt/slideMasters/") and name.endswith(".xml")]),
        "media": sorted([name for name in names if name.startswith("ppt/media/")]),
        "charts": sorted([name for name in names if name.startswith("ppt/charts/") and name.endswith(".xml")]),
        "embeddings": sorted([name for name in names if name.startswith("ppt/embeddings/")]),
        "themes": sorted([name for name in names if name.startswith("ppt/theme/") and name.endswith(".xml")]),
        "notes": sorted([name for name in names if name.startswith("ppt/notesSlides/") and name.endswith(".xml")]),
    }


def parse_relationships(package: zipfile.ZipFile, slide_part: str) -> dict[str, dict[str, str]]:
    rel_part = slide_part.replace("ppt/slides/", "ppt/slides/_rels/") + ".rels"
    root = read_xml(package, rel_part)
    if root is None:
        return {}
    rels: dict[str, dict[str, str]] = {}
    for rel in root.findall("rel:Relationship", NS):
        rel_id = rel.attrib.get("Id")
        if rel_id:
            rels[rel_id] = {
                "id": rel_id,
                "type": rel.attrib.get("Type", ""),
                "target": rel.attrib.get("Target", ""),
            }
    return rels


def parse_bbox(element: ET.Element) -> dict[str, int | None]:
    xfrm = element.find(".//a:xfrm", NS)
    if xfrm is None:
        return {"x": None, "y": None, "cx": None, "cy": None}
    off = xfrm.find("a:off", NS)
    ext = xfrm.find("a:ext", NS)
    return {
        "x": _int_attr(off, "x"),
        "y": _int_attr(off, "y"),
        "cx": _int_attr(ext, "cx"),
        "cy": _int_attr(ext, "cy"),
    }


def geometry_known(bbox: dict[str, Any]) -> bool:
    return all(isinstance(bbox.get(key), int) for key in ("x", "y", "cx", "cy"))


def _int_attr(element: ET.Element | None, attr: str) -> int | None:
    if element is None:
        return None
    value = element.attrib.get(attr)
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None
