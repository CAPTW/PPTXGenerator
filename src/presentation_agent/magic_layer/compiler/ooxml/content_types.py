from __future__ import annotations


REQUIRED_PART_CONTENT_TYPES: dict[str, str] = {
    "/docProps/core.xml": "application/vnd.openxmlformats-package.core-properties+xml",
    "/docProps/app.xml": "application/vnd.openxmlformats-officedocument.extended-properties+xml",
    "/ppt/presentation.xml": "application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml",
    "/ppt/slides/slide1.xml": "application/vnd.openxmlformats-officedocument.presentationml.slide+xml",
    "/ppt/slideMasters/slideMaster1.xml": "application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml",
    "/ppt/slideLayouts/slideLayout1.xml": "application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml",
    "/ppt/theme/theme1.xml": "application/vnd.openxmlformats-officedocument.theme+xml",
    "/ppt/presProps.xml": "application/vnd.openxmlformats-officedocument.presentationml.presProps+xml",
    "/ppt/viewProps.xml": "application/vnd.openxmlformats-officedocument.presentationml.viewProps+xml",
    "/ppt/tableStyles.xml": "application/vnd.openxmlformats-officedocument.presentationml.tableStyles+xml",
}


def build_content_types_xml() -> str:
    overrides = "\n".join(
        f'  <Override PartName="{part}" ContentType="{content_type}"/>'
        for part, content_type in REQUIRED_PART_CONTENT_TYPES.items()
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
        '  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>\n'
        '  <Default Extension="xml" ContentType="application/xml"/>\n'
        f"{overrides}\n"
        "</Types>"
    )

