"""SVG icon resolution and OOXML injection for E06.2 contract compilation."""

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
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
    "ct": "http://schemas.openxmlformats.org/package/2006/content-types",
}

for prefix in ("p", "a", "r"):
    ET.register_namespace(prefix, NS[prefix])


def resolve_icon_svg(icon_root: Path, role: str) -> Path | None:
    candidate = icon_root / f"{role}.svg"
    return candidate if candidate.exists() else None


def build_svg_icon_instructions(contract: dict[str, Any], icon_root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    instructions: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    for slide in contract.get("slides", []):
        slide_number = int(slide["slide_number"])
        for obj in slide.get("objects", []):
            if obj.get("object_type") != "semantic_icon":
                continue
            role = str(obj.get("semantic_role") or "")
            svg = resolve_icon_svg(icon_root, role)
            row = {
                "slide_number": slide_number,
                "contract_object_id": obj["object_id"],
                "placeholder_name": contract_shape_name(obj),
                "semantic_role": role,
                "svg_path": svg.as_posix() if svg else None,
            }
            if svg:
                instructions.append(row)
            else:
                missing.append(row)
    return instructions, {
        "schema_name": "svg_icon_resolution_report",
        "status": "passed" if not missing else "failed",
        "semantic_icon_count": len(instructions) + len(missing),
        "resolved_svg_icon_count": len(instructions),
        "missing_svg_icon_count": len(missing),
        "missing": missing,
    }


def inject_svg_icons(pptx_path: Path, instructions: list[dict[str, Any]]) -> dict[str, Any]:
    if not instructions:
        return {"schema_name": "svg_icon_injection_report", "status": "passed", "injected_svg_icon_count": 0}
    with tempfile.TemporaryDirectory() as tmp:
        tmp_pptx = Path(tmp) / "patched.pptx"
        with zipfile.ZipFile(pptx_path, "r") as zin, zipfile.ZipFile(tmp_pptx, "w", compression=zipfile.ZIP_DEFLATED) as zout:
            names = set(zin.namelist())
            content_types = _ensure_svg_content_type(ET.fromstring(zin.read("[Content_Types].xml")))
            slide_groups: dict[int, list[dict[str, Any]]] = {}
            for instruction in instructions:
                slide_groups.setdefault(int(instruction["slide_number"]), []).append(instruction)
            for name in zin.namelist():
                if name == "[Content_Types].xml":
                    zout.writestr(name, _xml_bytes(content_types))
                elif name.startswith("ppt/slides/slide") and name.endswith(".xml") and _slide_number_from_name(name) in slide_groups:
                    slide_number = _slide_number_from_name(name)
                    rel_name = f"ppt/slides/_rels/slide{slide_number}.xml.rels"
                    rels_root = ET.fromstring(zin.read(rel_name))
                    slide_root = ET.fromstring(zin.read(name))
                    for instruction in slide_groups[slide_number]:
                        media_name = f"ppt/media/e06_2_icon_{slide_number:02d}_{len(instruction['contract_object_id'])}_{abs(hash(instruction['contract_object_id'])) % 1000000}.svg"
                        rid = _next_rid(rels_root)
                        ET.SubElement(
                            rels_root,
                            f"{{{NS['rel']}}}Relationship",
                            {
                                "Id": rid,
                                "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image",
                                "Target": f"../media/{Path(media_name).name}",
                            },
                        )
                        _replace_placeholder_with_pic(slide_root, instruction["placeholder_name"], rid)
                        zout.writestr(media_name, Path(instruction["svg_path"]).read_bytes())
                        names.add(media_name)
                    zout.writestr(name, _xml_bytes(slide_root))
                    zout.writestr(rel_name, _xml_bytes(rels_root))
                elif name.startswith("ppt/slides/_rels/slide") and name.endswith(".xml.rels"):
                    slide_number = _rels_slide_number_from_name(name)
                    if slide_number in slide_groups:
                        continue
                    zout.writestr(name, zin.read(name))
                else:
                    zout.writestr(name, zin.read(name))
        shutil.copy2(tmp_pptx, pptx_path)
    return {
        "schema_name": "svg_icon_injection_report",
        "status": "passed",
        "injected_svg_icon_count": len(instructions),
        "semantic_raster_icon_count": 0,
    }


def _replace_placeholder_with_pic(slide_root: ET.Element, placeholder_name: str, rid: str) -> None:
    tree = slide_root.find(".//p:cSld/p:spTree", NS)
    if tree is None:
        raise ValueError("spTree not found")
    for idx, child in enumerate(list(tree)):
        if child.tag != f"{{{NS['p']}}}sp":
            continue
        c_nv_pr = child.find("./p:nvSpPr/p:cNvPr", NS)
        if c_nv_pr is None or c_nv_pr.attrib.get("name") != placeholder_name:
            continue
        xfrm = child.find("./p:spPr/a:xfrm", NS)
        c_id = c_nv_pr.attrib.get("id", "1")
        pic = _pic_xml(c_id, placeholder_name, rid, xfrm)
        tree.remove(child)
        tree.insert(idx, pic)
        return
    raise ValueError(f"placeholder not found: {placeholder_name}")


def _pic_xml(c_id: str, name: str, rid: str, xfrm: ET.Element | None) -> ET.Element:
    pic = ET.Element(f"{{{NS['p']}}}pic")
    nv = ET.SubElement(pic, f"{{{NS['p']}}}nvPicPr")
    ET.SubElement(nv, f"{{{NS['p']}}}cNvPr", {"id": c_id, "name": name, "descr": "e06_2_contract_svg_icon"})
    c_nv_pic = ET.SubElement(nv, f"{{{NS['p']}}}cNvPicPr")
    ET.SubElement(c_nv_pic, f"{{{NS['a']}}}picLocks", {"noChangeAspect": "1"})
    ET.SubElement(nv, f"{{{NS['p']}}}nvPr")
    blip_fill = ET.SubElement(pic, f"{{{NS['p']}}}blipFill")
    ET.SubElement(blip_fill, f"{{{NS['a']}}}blip", {f"{{{NS['r']}}}embed": rid})
    stretch = ET.SubElement(blip_fill, f"{{{NS['a']}}}stretch")
    ET.SubElement(stretch, f"{{{NS['a']}}}fillRect")
    sppr = ET.SubElement(pic, f"{{{NS['p']}}}spPr")
    if xfrm is not None:
        sppr.append(deepcopy(xfrm))
    geom = ET.SubElement(sppr, f"{{{NS['a']}}}prstGeom", {"prst": "rect"})
    ET.SubElement(geom, f"{{{NS['a']}}}avLst")
    return pic


def _ensure_svg_content_type(root: ET.Element) -> ET.Element:
    for child in root:
        if child.attrib.get("Extension") == "svg":
            return root
    ET.SubElement(root, f"{{{NS['ct']}}}Default", {"Extension": "svg", "ContentType": "image/svg+xml"})
    return root


def _next_rid(rels_root: ET.Element) -> str:
    max_id = 0
    for rel in rels_root:
        rid = rel.attrib.get("Id", "")
        if rid.startswith("rId") and rid[3:].isdigit():
            max_id = max(max_id, int(rid[3:]))
    return f"rId{max_id + 1}"


def _slide_number_from_name(name: str) -> int:
    return int(Path(name).stem.replace("slide", ""))


def _rels_slide_number_from_name(name: str) -> int:
    return int(Path(name).name.replace("slide", "").replace(".xml.rels", ""))


def _xml_bytes(root: ET.Element) -> bytes:
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)
