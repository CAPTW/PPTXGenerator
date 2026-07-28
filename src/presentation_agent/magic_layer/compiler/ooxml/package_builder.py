from __future__ import annotations

import zipfile
from pathlib import Path

from .content_types import build_content_types_xml
from .master_layout_builder import build_slide_layout_xml, build_slide_master_xml
from .presentation_parts import (
    build_app_props_xml,
    build_core_props_xml,
    build_pres_props_xml,
    build_presentation_xml,
    build_slide_xml,
    build_table_styles_xml,
    build_view_props_xml,
)
from .relationships import (
    build_presentation_rels_xml,
    build_root_rels_xml,
    build_slide_layout_rels_xml,
    build_slide_master_rels_xml,
    build_slide_rels_xml,
)
from .theme_builder import build_theme_xml


FIXED_ZIP_DATE = (2026, 1, 1, 0, 0, 0)


def build_compatible_package_parts(shapes_xml: str) -> dict[str, str]:
    return {
        "[Content_Types].xml": build_content_types_xml(),
        "_rels/.rels": build_root_rels_xml(),
        "docProps/core.xml": build_core_props_xml(),
        "docProps/app.xml": build_app_props_xml(),
        "ppt/presentation.xml": build_presentation_xml(),
        "ppt/_rels/presentation.xml.rels": build_presentation_rels_xml(),
        "ppt/slides/slide1.xml": build_slide_xml(shapes_xml),
        "ppt/slides/_rels/slide1.xml.rels": build_slide_rels_xml(),
        "ppt/slideMasters/slideMaster1.xml": build_slide_master_xml(),
        "ppt/slideMasters/_rels/slideMaster1.xml.rels": build_slide_master_rels_xml(),
        "ppt/slideLayouts/slideLayout1.xml": build_slide_layout_xml(),
        "ppt/slideLayouts/_rels/slideLayout1.xml.rels": build_slide_layout_rels_xml(),
        "ppt/theme/theme1.xml": build_theme_xml(),
        "ppt/presProps.xml": build_pres_props_xml(),
        "ppt/viewProps.xml": build_view_props_xml(),
        "ppt/tableStyles.xml": build_table_styles_xml(),
    }


def write_deterministic_package(output_path: str | Path, parts: dict[str, str]) -> None:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as package:
        for name in sorted(parts):
            info = zipfile.ZipInfo(filename=name, date_time=FIXED_ZIP_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            package.writestr(info, parts[name])

