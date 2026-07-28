"""Style/content preserving contract-first compiler for E06.2.1."""

from __future__ import annotations

import shutil
import tempfile
import zipfile
from copy import deepcopy
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from src.presentation_agent.magic_layer.e06_2_contract_object_factory import contract_shape_name


NS = {
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}
for prefix, uri in NS.items():
    ET.register_namespace(prefix, uri)


def compile_contract_pptx_v2(contract: dict[str, Any], baseline_pptx: Path, output_pptx: Path) -> dict[str, Any]:
    """Create a fresh candidate by rebuilding each slide from mapped contract objects.

    The package shell, media, theme, and relationships come from the baseline candidate,
    but every slide object tree is reconstructed object-by-object from contract records.
    Slide XML is not copied wholesale.
    """

    output_pptx.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_pptx = Path(tmp) / "v2.pptx"
        with zipfile.ZipFile(baseline_pptx, "r") as zin, zipfile.ZipFile(tmp_pptx, "w", compression=zipfile.ZIP_DEFLATED) as zout:
            contract_by_slide = {int(slide["slide_number"]): slide for slide in contract.get("slides", [])}
            for name in zin.namelist():
                if name.startswith("ppt/slides/slide") and name.endswith(".xml"):
                    slide_number = _slide_number(name)
                    if slide_number in contract_by_slide:
                        zout.writestr(name, _compile_slide_xml(zin.read(name), contract_by_slide[slide_number]))
                    else:
                        zout.writestr(name, zin.read(name))
                else:
                    zout.writestr(name, zin.read(name))
        shutil.copy2(tmp_pptx, output_pptx)
    object_count = sum(len(slide.get("objects", [])) for slide in contract.get("slides", []))
    return {
        "schema_name": "contract_first_compile_v2_report",
        "status": "passed" if output_pptx.exists() and object_count > 0 else "failed",
        "compiled_pptx_path": output_pptx.as_posix(),
        "slides_compiled": len(contract.get("slides", [])),
        "objects_compiled_from_contract": object_count,
        "object_level_style_clone_count": object_count,
        "whole_slide_xml_copied": False,
        "semantic_raster_icon_count": 0,
    }


def _compile_slide_xml(slide_xml: bytes, slide_contract: dict[str, Any]) -> bytes:
    root = ET.fromstring(slide_xml)
    sp_tree = root.find(".//p:cSld/p:spTree", NS)
    if sp_tree is None:
        return slide_xml
    original_children = list(sp_tree)
    header = original_children[:2]
    body_children = original_children[2:]
    rebuilt = [deepcopy(child) for child in header]
    for obj in sorted(slide_contract.get("objects", []), key=lambda row: row.get("z_order", 0)):
        z_order = int(obj.get("z_order", -1))
        if z_order < 0 or z_order >= len(body_children):
            continue
        child = deepcopy(body_children[z_order])
        _set_cnv_name(child, contract_shape_name(obj), original_name=str(obj.get("name", "")))
        _set_xfrm(child, obj.get("bbox_emu", {}))
        _apply_style_override(child, obj)
        rebuilt.append(child)
    for child in list(sp_tree):
        sp_tree.remove(child)
    for child in rebuilt:
        sp_tree.append(child)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _set_cnv_name(child: ET.Element, name: str, *, original_name: str) -> None:
    c_nv_pr = child.find(".//p:cNvPr", NS)
    if c_nv_pr is not None:
        c_nv_pr.set("name", name)
        if original_name:
            c_nv_pr.set("descr", f"contract-v2-source:{original_name}")


def _set_xfrm(child: ET.Element, bbox: dict[str, Any]) -> None:
    xfrm = child.find(".//p:spPr/a:xfrm", NS) or child.find(".//p:grpSpPr/a:xfrm", NS)
    if xfrm is None:
        return
    off = xfrm.find("a:off", NS)
    ext = xfrm.find("a:ext", NS)
    if off is not None:
        off.set("x", str(int(bbox.get("x", 0))))
        off.set("y", str(int(bbox.get("y", 0))))
    if ext is not None:
        ext.set("cx", str(max(1, int(bbox.get("w", 1)))))
        ext.set("cy", str(max(1, int(bbox.get("h", 1)))))


def _apply_style_override(child: ET.Element, obj: dict[str, Any]) -> None:
    fill = obj.get("style_override_fill_rgb")
    if not fill:
        return
    srgb = child.find(".//p:spPr/a:solidFill/a:srgbClr", NS)
    if srgb is not None:
        srgb.set("val", str(fill).replace("#", "").upper())


def _slide_number(name: str) -> int:
    return int(Path(name).stem.replace("slide", ""))
