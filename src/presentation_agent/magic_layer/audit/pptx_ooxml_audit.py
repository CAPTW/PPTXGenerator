from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any

from .ooxml_package import NS, geometry_known, list_package_parts, parse_bbox, parse_relationships, read_xml, sha256_file


EMU_PER_INCH = 914400


def audit_pptx_package(pptx_path: str | Path) -> dict[str, Any]:
    path = Path(pptx_path)
    base: dict[str, Any] = {
        "pptx_path": str(path),
        "exists": path.is_file(),
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size if path.is_file() else None,
        "slide_count": 0,
        "slide_width_emu": None,
        "slide_height_emu": None,
        "slide_width_in": None,
        "slide_height_in": None,
        "package_parts": {
            "slides": [],
            "slide_layouts": [],
            "slide_masters": [],
            "media": [],
            "charts": [],
            "embeddings": [],
            "themes": [],
            "notes": [],
        },
        "per_slide": [],
        "warnings": [],
        "errors": [],
    }
    if not path.is_file():
        base["errors"].append("PPTX file is missing.")
        return base
    try:
        with zipfile.ZipFile(path) as package:
            names = package.namelist()
            base["package_parts"] = list_package_parts(names)
            _add_slide_size(base, package)
            for index, slide_part in enumerate(base["package_parts"]["slides"], start=1):
                slide = _audit_slide(package, slide_part, index, base["slide_width_emu"], base["slide_height_emu"])
                base["per_slide"].append(slide)
            base["slide_count"] = len(base["per_slide"])
    except zipfile.BadZipFile:
        base["errors"].append("PPTX is not a valid zip package.")
    except OSError as exc:
        base["errors"].append(str(exc))
    return base


def _add_slide_size(result: dict[str, Any], package: zipfile.ZipFile) -> None:
    root = read_xml(package, "ppt/presentation.xml")
    if root is None:
        result["warnings"].append("ppt/presentation.xml could not be parsed; slide size is unknown.")
        return
    size = root.find(".//p:sldSz", NS)
    if size is None:
        result["warnings"].append("Slide size element is missing; slide geometry is unknown.")
        return
    try:
        width = int(size.attrib["cx"])
        height = int(size.attrib["cy"])
    except (KeyError, ValueError):
        result["warnings"].append("Slide size attributes are invalid; slide geometry is unknown.")
        return
    result["slide_width_emu"] = width
    result["slide_height_emu"] = height
    result["slide_width_in"] = round(width / EMU_PER_INCH, 4)
    result["slide_height_in"] = round(height / EMU_PER_INCH, 4)


def _audit_slide(
    package: zipfile.ZipFile,
    slide_part: str,
    slide_index: int,
    slide_width: int | None,
    slide_height: int | None,
) -> dict[str, Any]:
    root = read_xml(package, slide_part)
    rels = parse_relationships(package, slide_part)
    if root is None:
        return {
            "slide_id": slide_index,
            "slide_part": slide_part,
            "shape_count": 0,
            "text_shape_count": 0,
            "picture_count": 0,
            "media_ref_count": 0,
            "chart_count": 0,
            "table_count": 0,
            "group_count": 0,
            "freeform_count": 0,
            "full_slide_raster_candidates": [],
            "screenshot_like_candidates": [],
            "object_names": [],
            "text_runs": [],
            "chart_refs": [],
            "table_refs": [],
            "media_refs": [],
            "pictures": [],
            "geometry_status": "UNKNOWN",
            "errors": ["Slide XML could not be parsed."],
        }

    shapes = root.findall(".//p:sp", NS)
    pictures = root.findall(".//p:pic", NS)
    charts = root.findall(".//c:chart", NS)
    tables = root.findall(".//a:tbl", NS)
    groups = root.findall(".//p:grpSp", NS)
    text_runs = [text.text or "" for text in root.findall(".//a:t", NS)]
    text_shape_count = sum(1 for shape in shapes if shape.find(".//a:t", NS) is not None)
    object_names = [node.attrib.get("name", "") for node in root.findall(".//p:cNvPr", NS) if node.attrib.get("name")]

    picture_rows = [_picture_row(pic, rels, slide_width, slide_height) for pic in pictures]
    media_refs = [row["media_ref"] for row in picture_rows if row.get("media_ref")]
    chart_refs = [_chart_row(chart, rels) for chart in charts]
    table_refs = [{"index": index} for index, _table in enumerate(tables, start=1)]
    geometry_status = "KNOWN" if all(geometry_known(row["bbox"]) for row in picture_rows) else "UNKNOWN" if picture_rows else "NOT_APPLICABLE"

    full_slide_candidates = [
        row for row in picture_rows if isinstance(row.get("area_ratio"), (int, float)) and row["area_ratio"] >= 0.95
    ]
    screenshot_candidates = [
        row
        for row in picture_rows
        if isinstance(row.get("area_ratio"), (int, float))
        and row["area_ratio"] >= 0.80
        and text_shape_count <= 1
        and ("screenshot" in row.get("name", "").lower() or "render" in row.get("name", "").lower())
    ]

    return {
        "slide_id": slide_index,
        "slide_part": slide_part,
        "shape_count": len(shapes),
        "text_shape_count": text_shape_count,
        "picture_count": len(pictures),
        "media_ref_count": len(media_refs),
        "chart_count": len(charts),
        "table_count": len(tables),
        "group_count": len(groups),
        "freeform_count": len(root.findall(".//a:custGeom", NS)),
        "full_slide_raster_candidates": full_slide_candidates,
        "screenshot_like_candidates": screenshot_candidates,
        "object_names": object_names,
        "text_runs": text_runs,
        "chart_refs": chart_refs,
        "table_refs": table_refs,
        "media_refs": media_refs,
        "pictures": picture_rows,
        "geometry_status": geometry_status,
        "errors": [],
    }


def _picture_row(pic: Any, rels: dict[str, dict[str, str]], slide_width: int | None, slide_height: int | None) -> dict[str, Any]:
    name_node = pic.find(".//p:cNvPr", NS)
    blip = pic.find(".//a:blip", NS)
    rel_id = blip.attrib.get(f"{{{NS['r']}}}embed") if blip is not None else None
    rel = rels.get(rel_id or "", {})
    bbox = parse_bbox(pic)
    area_ratio = None
    width_ratio = None
    height_ratio = None
    if geometry_known(bbox) and slide_width and slide_height:
        area_ratio = round((bbox["cx"] * bbox["cy"]) / (slide_width * slide_height), 6)
        width_ratio = round(bbox["cx"] / slide_width, 6)
        height_ratio = round(bbox["cy"] / slide_height, 6)
    return {
        "name": name_node.attrib.get("name", "") if name_node is not None else "",
        "rel_id": rel_id,
        "media_ref": rel.get("target"),
        "relationship_type": rel.get("type"),
        "bbox": bbox,
        "area_ratio": area_ratio,
        "width_ratio": width_ratio,
        "height_ratio": height_ratio,
    }


def _chart_row(chart: Any, rels: dict[str, dict[str, str]]) -> dict[str, str | None]:
    rel_id = chart.attrib.get(f"{{{NS['r']}}}id")
    rel = rels.get(rel_id or "", {})
    return {"rel_id": rel_id, "target": rel.get("target"), "relationship_type": rel.get("type")}
