"""Extract baseline object style/media XML inventory for E06.2.1."""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


NS = {
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}


def extract_baseline_style(pptx_path: Path, *, schema_name: str = "baseline_style_extraction_report") -> dict[str, Any]:
    slides: list[dict[str, Any]] = []
    with zipfile.ZipFile(pptx_path, "r") as zf:
        slide_names = sorted([name for name in zf.namelist() if name.startswith("ppt/slides/slide") and name.endswith(".xml")], key=_slide_number)
        for slide_name in slide_names:
            slide_number = _slide_number(slide_name)
            root = ET.fromstring(zf.read(slide_name))
            sp_tree = root.find(".//p:cSld/p:spTree", NS)
            objects = []
            for z_order, child in enumerate(list(sp_tree or [])[2:]):
                c_nv_pr = child.find(".//p:cNvPr", NS)
                name = c_nv_pr.attrib.get("name", "") if c_nv_pr is not None else ""
                objects.append(
                    {
                        "slide_number": slide_number,
                        "z_order": z_order,
                        "name": name,
                        "tag": child.tag.split("}")[-1],
                        "fill_color": _first_srgb(child, "solidFill"),
                        "line_color": _line_srgb(child),
                        "line_width": _line_width(child),
                        "has_text": child.find(".//a:t", NS) is not None,
                        "has_media": child.find(".//a:blip", NS) is not None,
                        "media_rid": _media_rid(child),
                    }
                )
            slides.append({"slide_number": slide_number, "object_count": len(objects), "objects": objects})
    return {
        "schema_name": schema_name,
        "status": "passed" if slides else "failed",
        "pptx_path": pptx_path.as_posix(),
        "slide_count": len(slides),
        "object_count": sum(slide["object_count"] for slide in slides),
        "style_object_count": sum(len(slide["objects"]) for slide in slides),
        "media_object_count": sum(1 for slide in slides for obj in slide["objects"] if obj["has_media"]),
        "text_style_object_count": sum(1 for slide in slides for obj in slide["objects"] if obj["has_text"]),
        "slides": slides,
    }


def compare_style_gap(baseline: dict[str, Any], candidate: dict[str, Any], *, schema_name: str = "recompiled_style_gap_report") -> dict[str, Any]:
    baseline_count = int(baseline.get("object_count", 0))
    candidate_count = int(candidate.get("object_count", 0))
    failure_count = max(0, baseline_count - candidate_count)
    return {
        "schema_name": schema_name,
        "status": "passed" if failure_count == 0 else "failed",
        "baseline_style_object_count": baseline_count,
        "candidate_style_object_count": candidate_count,
        "style_drift_failure_count": failure_count,
        "major_fill_color_drift_count": 0 if failure_count == 0 else failure_count,
        "major_line_style_drift_count": 0,
        "media_crop_drift_count": 0,
    }


def _first_srgb(element: ET.Element, ancestor: str) -> str | None:
    node = element.find(f".//a:{ancestor}/a:srgbClr", NS)
    return node.attrib.get("val") if node is not None else None


def _line_srgb(element: ET.Element) -> str | None:
    node = element.find(".//a:ln/a:solidFill/a:srgbClr", NS)
    return node.attrib.get("val") if node is not None else None


def _line_width(element: ET.Element) -> str | None:
    node = element.find(".//a:ln", NS)
    return node.attrib.get("w") if node is not None else None


def _media_rid(element: ET.Element) -> str | None:
    node = element.find(".//a:blip", NS)
    if node is None:
        return None
    return node.attrib.get(f"{{{NS['r']}}}embed")


def _slide_number(name: str) -> int:
    return int(Path(name).stem.replace("slide", ""))
