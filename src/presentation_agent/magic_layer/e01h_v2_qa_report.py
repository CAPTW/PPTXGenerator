"""Shared helpers for E01H-V2 QA audit reports."""

from __future__ import annotations

import json
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


NS = {
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
}
EMU_W = 12191695
EMU_H = 6858000


def read_json(path: str | Path) -> dict[str, Any]:
    file_path = Path(path)
    if not file_path.exists():
        return {}
    return json.loads(file_path.read_text(encoding="utf-8"))


def write_json(path: str | Path, payload: Any) -> None:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def write_md(path: str | Path, content: str) -> None:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content.rstrip() + "\n", encoding="utf-8")


def simple_markdown(payload: dict[str, Any], title: str) -> str:
    lines = [f"# {title}", ""]
    for key, value in payload.items():
        if isinstance(value, (dict, list)):
            continue
        lines.append(f"- {key}: `{value}`")
    return "\n".join(lines) + "\n"


def final_decision_markdown(payload: dict[str, Any]) -> str:
    return (
        "# E01H-V2 QA Final Decision\n\n"
        f"- decision: `{payload.get('decision')}`\n"
        f"- status: `{payload.get('status')}`\n"
        f"- e02h_v2_unlocked: `{payload.get('e02h_v2_unlocked')}`\n"
        f"- e05_unlocked: `{payload.get('e05_unlocked')}`\n"
        f"- reason: {payload.get('reason')}\n"
    )


def extract_pptx_text(pptx_path: str | Path) -> list[str]:
    path = Path(pptx_path)
    texts: list[str] = []
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            if name.startswith("ppt/slides/slide") and name.endswith(".xml"):
                root = ET.fromstring(archive.read(name))
                for text in root.findall(".//a:t", NS):
                    if text.text:
                        texts.append(text.text)
    return texts


def inspect_pptx_picture_layers(pptx_path: str | Path) -> dict[str, Any]:
    path = Path(pptx_path)
    pictures: list[dict[str, Any]] = []
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            if name.startswith("ppt/slides/slide") and name.endswith(".xml"):
                root = ET.fromstring(archive.read(name))
                for pic in root.findall(".//p:pic", NS):
                    c_nv_pr = pic.find(".//p:cNvPr", NS)
                    ext = pic.find(".//a:xfrm/a:ext", NS)
                    off = pic.find(".//a:xfrm/a:off", NS)
                    object_name = c_nv_pr.attrib.get("name", "") if c_nv_pr is not None else ""
                    cx = int(ext.attrib.get("cx", "0")) if ext is not None else 0
                    cy = int(ext.attrib.get("cy", "0")) if ext is not None else 0
                    x = int(off.attrib.get("x", "0")) if off is not None else 0
                    y = int(off.attrib.get("y", "0")) if off is not None else 0
                    area_ratio = (cx * cy) / float(EMU_W * EMU_H) if cx and cy else 0.0
                    pictures.append(
                        {
                            "object_name": object_name,
                            "bbox_norm": [x / EMU_W, y / EMU_H, (x + cx) / EMU_W, (y + cy) / EMU_H],
                            "area_ratio": round(area_ratio, 3),
                            "source": "reference_derived_picture" if "backplate" in object_name.lower() else "picture",
                        }
                    )
    return {
        "schema_name": "pptx_picture_layer_inventory",
        "status": "passed",
        "picture_object_count": len(pictures),
        "largest_picture_area_ratio": max((row["area_ratio"] for row in pictures), default=0.0),
        "pictures": pictures,
    }
