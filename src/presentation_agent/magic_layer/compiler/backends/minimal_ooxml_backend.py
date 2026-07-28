from __future__ import annotations

import html
from pathlib import Path
from typing import Any

from ..ooxml.package_builder import build_compatible_package_parts, write_deterministic_package


EMU_PER_INCH = 914400
SLIDE_WIDTH_EMU = 12192000
SLIDE_HEIGHT_EMU = 6858000


class MinimalOoxmlBackend:
    backend_name = "minimal_ooxml"
    supported_object_types = ["text_box", "shape", "editable_shape_chart", "editable_shape_grid_table"]
    unsupported_object_types = [
        "native_chart",
        "native_table",
        "replaceable_image_frame",
        "svg_icon",
        "group",
    ]

    def compile_minimal(self, bundle: dict[str, Any], output_path: str | Path) -> dict[str, Any]:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        objects = _extract_objects(bundle)
        supported_objects = [
            obj
            for obj in objects
            if str(obj.get("pptx_object_type")) in {"text_box", "shape", "editable_shape_chart", "editable_shape_grid_table"}
        ]
        if not supported_objects:
            supported_objects = [_fallback_title_object()]

        shapes = "\n".join(_shape_xml(obj, index + 1) for index, obj in enumerate(supported_objects, start=1))
        write_deterministic_package(output, build_compatible_package_parts(shapes))

        return {
            "backend": self.backend_name,
            "output_path": str(output),
            "output_exists": output.is_file(),
            "object_count": len(supported_objects),
            "media_count": 0,
            "pptx_generated": output.is_file(),
            "render_generated": False,
            "product_pass": False,
        }


def _extract_objects(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    spec = bundle.get("editable_candidate_spec") if isinstance(bundle.get("editable_candidate_spec"), dict) else bundle
    objects = spec.get("objects", [])
    return [item for item in objects if isinstance(item, dict)]


def _fallback_title_object() -> dict[str, Any]:
    return {
        "instruction_id": "instr_obj_title",
        "object_id": "obj_title",
        "slot_id": "SLOT_TITLE",
        "object_name": "SLOT_TITLE",
        "pptx_object_type": "text_box",
        "geometry": {"x_in": 1.3333, "y_in": 0.75, "width_in": 8.0, "height_in": 0.9},
        "text": {"placeholder": "TEXT"},
        "semantic_role": "title",
        "editable_required": True,
        "raster_allowed": False,
    }


def _text_value(obj: dict[str, Any]) -> str:
    text = obj.get("text")
    if isinstance(text, dict):
        return str(text.get("content") or text.get("placeholder") or text.get("default") or "TEXT")
    if isinstance(text, str):
        return text
    if str(obj.get("pptx_object_type")) in {"editable_shape_chart", "editable_shape_grid_table"}:
        return str(obj.get("object_name") or obj.get("slot_id") or obj.get("object_id") or "")
    if str(obj.get("pptx_object_type")) == "text_box":
        return "TEXT"
    return ""


def _geom(obj: dict[str, Any]) -> dict[str, int]:
    geometry = obj.get("geometry") if isinstance(obj.get("geometry"), dict) else {}
    if {"x_in", "y_in", "width_in", "height_in"}.issubset(geometry):
        x = float(geometry.get("x_in") or 0)
        y = float(geometry.get("y_in") or 0)
        w = float(geometry.get("width_in") or 1)
        h = float(geometry.get("height_in") or 0.5)
    else:
        bbox = geometry.get("bbox_norm") if isinstance(geometry.get("bbox_norm"), list) else [0.1, 0.1, 0.6, 0.12]
        x = float(bbox[0]) * (SLIDE_WIDTH_EMU / EMU_PER_INCH)
        y = float(bbox[1]) * (SLIDE_HEIGHT_EMU / EMU_PER_INCH)
        w = float(bbox[2]) * (SLIDE_WIDTH_EMU / EMU_PER_INCH)
        h = float(bbox[3]) * (SLIDE_HEIGHT_EMU / EMU_PER_INCH)
        return {"x": int(x * EMU_PER_INCH), "y": int(y * EMU_PER_INCH), "cx": int(w * EMU_PER_INCH), "cy": int(h * EMU_PER_INCH)}
    return {"x": int(x * EMU_PER_INCH), "y": int(y * EMU_PER_INCH), "cx": int(w * EMU_PER_INCH), "cy": int(h * EMU_PER_INCH)}


def _shape_xml(obj: dict[str, Any], shape_id: int) -> str:
    geom = _geom(obj)
    name = html.escape(str(obj.get("object_name") or obj.get("slot_id") or obj.get("object_id") or f"OBJECT_{shape_id}"))
    object_type = str(obj.get("pptx_object_type"))
    text = html.escape(_text_value(obj))
    fill = "<a:noFill/>" if object_type == "text_box" else '<a:solidFill><a:srgbClr val="F8FAFC"><a:alpha val="18000"/></a:srgbClr></a:solidFill>'
    line = '<a:ln><a:noFill/></a:ln>' if object_type == "text_box" else '<a:ln w="9525"><a:solidFill><a:srgbClr val="64748B"/></a:solidFill></a:ln>'
    tx_box = "1" if object_type == "text_box" else "0"
    return f"""<p:sp>
  <p:nvSpPr>
    <p:cNvPr id="{shape_id}" name="{name}"/>
    <p:cNvSpPr txBox="{tx_box}"/>
    <p:nvPr/>
  </p:nvSpPr>
  <p:spPr>
    <a:xfrm><a:off x="{geom['x']}" y="{geom['y']}"/><a:ext cx="{geom['cx']}" cy="{geom['cy']}"/></a:xfrm>
    <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
    {fill}
    {line}
  </p:spPr>
  <p:txBody>
    <a:bodyPr wrap="square"/>
    <a:lstStyle/>
    <a:p><a:r><a:rPr lang="en-US" sz="3200"/><a:t>{text}</a:t></a:r><a:endParaRPr lang="en-US" sz="3200"/></a:p>
  </p:txBody>
</p:sp>"""


def _package_parts(text_objects: list[dict[str, Any]]) -> dict[str, str]:
    shapes = "\n".join(_shape_xml(obj, index + 1) for index, obj in enumerate(text_objects, start=1))
    return {
        "[Content_Types].xml": _content_types(),
        "_rels/.rels": _root_rels(),
        "docProps/core.xml": _core_props(),
        "docProps/app.xml": _app_props(),
        "ppt/presentation.xml": _presentation(),
        "ppt/_rels/presentation.xml.rels": _presentation_rels(),
        "ppt/slides/slide1.xml": _slide(shapes),
        "ppt/slides/_rels/slide1.xml.rels": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>""",
        "ppt/slideMasters/slideMaster1.xml": _slide_master(),
        "ppt/slideMasters/_rels/slideMaster1.xml.rels": _slide_master_rels(),
        "ppt/slideLayouts/slideLayout1.xml": _slide_layout(),
        "ppt/slideLayouts/_rels/slideLayout1.xml.rels": _slide_layout_rels(),
        "ppt/theme/theme1.xml": _theme(),
    }


def _content_types() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
  <Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>
  <Override PartName="/ppt/slides/slide1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>
  <Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>
  <Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>
  <Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>
</Types>"""


def _root_rels() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>"""


def _presentation() -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst>
  <p:sldIdLst><p:sldId id="256" r:id="rId2"/></p:sldIdLst>
  <p:sldSz cx="{SLIDE_WIDTH_EMU}" cy="{SLIDE_HEIGHT_EMU}" type="screen16x9"/>
  <p:notesSz cx="6858000" cy="9144000"/>
</p:presentation>"""


def _presentation_rels() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide1.xml"/>
</Relationships>"""


def _slide(shapes: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld>
    <p:spTree>
      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
      <p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
      {shapes}
    </p:spTree>
  </p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sld>"""


def _slide_master() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/></p:spTree></p:cSld>
  <p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>
  <p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst>
</p:sldMaster>"""


def _slide_master_rels() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme1.xml"/>
</Relationships>"""


def _slide_layout() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" type="blank" preserve="1">
  <p:cSld name="Blank"><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/></p:spTree></p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sldLayout>"""


def _slide_layout_rels() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/>
</Relationships>"""


def _theme() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="C02 Minimal Theme">
  <a:themeElements>
    <a:clrScheme name="Minimal"><a:dk1><a:srgbClr val="111111"/></a:dk1><a:lt1><a:srgbClr val="FFFFFF"/></a:lt1><a:dk2><a:srgbClr val="222222"/></a:dk2><a:lt2><a:srgbClr val="F5F5F5"/></a:lt2><a:accent1><a:srgbClr val="2F5597"/></a:accent1><a:accent2><a:srgbClr val="70AD47"/></a:accent2><a:accent3><a:srgbClr val="FFC000"/></a:accent3><a:accent4><a:srgbClr val="C00000"/></a:accent4><a:accent5><a:srgbClr val="7030A0"/></a:accent5><a:accent6><a:srgbClr val="00B0F0"/></a:accent6><a:hlink><a:srgbClr val="0563C1"/></a:hlink><a:folHlink><a:srgbClr val="954F72"/></a:folHlink></a:clrScheme>
    <a:fontScheme name="Minimal"><a:majorFont><a:latin typeface="Arial"/></a:majorFont><a:minorFont><a:latin typeface="Arial"/></a:minorFont></a:fontScheme>
    <a:fmtScheme name="Minimal"><a:fillStyleLst/><a:lnStyleLst/><a:effectStyleLst/><a:bgFillStyleLst/></a:fmtScheme>
  </a:themeElements>
</a:theme>"""


def _core_props() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>C02 controlled minimal editable candidate</dc:title>
  <dc:creator>PPTXlocal C02 minimal compiler</dc:creator>
</cp:coreProperties>"""


def _app_props() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>PPTXlocal</Application>
  <Slides>1</Slides>
</Properties>"""
