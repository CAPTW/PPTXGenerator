from __future__ import annotations

import posixpath
from dataclasses import dataclass
from xml.etree import ElementTree as ET


REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
OFFICE_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"


@dataclass(frozen=True)
class Relationship:
    rel_id: str
    rel_type: str
    target: str


def build_relationships_xml(relationships: list[Relationship]) -> str:
    rows = "\n".join(
        f'  <Relationship Id="{rel.rel_id}" Type="{rel.rel_type}" Target="{rel.target}"/>'
        for rel in relationships
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<Relationships xmlns="{REL_NS}">\n{rows}\n</Relationships>'
    )


def build_root_rels_xml() -> str:
    return build_relationships_xml(
        [
            Relationship("rId1", f"{OFFICE_REL}/officeDocument", "ppt/presentation.xml"),
            Relationship("rId2", f"{PKG_REL}/metadata/core-properties", "docProps/core.xml"),
            Relationship("rId3", f"{OFFICE_REL}/extended-properties", "docProps/app.xml"),
        ]
    )


def build_presentation_rels_xml() -> str:
    return build_relationships_xml(
        [
            Relationship("rId1", f"{OFFICE_REL}/slideMaster", "slideMasters/slideMaster1.xml"),
            Relationship("rId2", f"{OFFICE_REL}/slide", "slides/slide1.xml"),
            Relationship("rId3", f"{OFFICE_REL}/theme", "theme/theme1.xml"),
            Relationship("rId4", f"{OFFICE_REL}/presProps", "presProps.xml"),
            Relationship("rId5", f"{OFFICE_REL}/viewProps", "viewProps.xml"),
            Relationship("rId6", f"{OFFICE_REL}/tableStyles", "tableStyles.xml"),
        ]
    )


def build_slide_rels_xml() -> str:
    return build_relationships_xml(
        [Relationship("rId1", f"{OFFICE_REL}/slideLayout", "../slideLayouts/slideLayout1.xml")]
    )


def build_slide_master_rels_xml() -> str:
    return build_relationships_xml(
        [
            Relationship("rId1", f"{OFFICE_REL}/slideLayout", "../slideLayouts/slideLayout1.xml"),
            Relationship("rId2", f"{OFFICE_REL}/theme", "../theme/theme1.xml"),
        ]
    )


def build_slide_layout_rels_xml() -> str:
    return build_relationships_xml(
        [Relationship("rId1", f"{OFFICE_REL}/slideMaster", "../slideMasters/slideMaster1.xml")]
    )


def parse_relationships_xml(xml_bytes: bytes) -> list[Relationship]:
    root = ET.fromstring(xml_bytes)
    return [
        Relationship(
            rel_id=str(node.attrib.get("Id", "")),
            rel_type=str(node.attrib.get("Type", "")),
            target=str(node.attrib.get("Target", "")),
        )
        for node in root.findall(f"{{{REL_NS}}}Relationship")
    ]


def source_part_for_rels(rels_part: str) -> str:
    if rels_part == "_rels/.rels":
        return ""
    marker = "/_rels/"
    if marker not in rels_part or not rels_part.endswith(".rels"):
        return ""
    prefix, filename = rels_part.split(marker, 1)
    return f"{prefix}/{filename[:-5]}"


def resolve_relationship_target(source_part: str, target: str) -> str:
    if target.startswith("/"):
        return target.lstrip("/")
    if not source_part:
        base = ""
    else:
        base = posixpath.dirname(source_part)
    return posixpath.normpath(posixpath.join(base, target)).replace("\\", "/")

