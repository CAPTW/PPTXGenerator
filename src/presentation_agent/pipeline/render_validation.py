"""Local PPTX structural validation helpers."""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path
from xml.etree import ElementTree


def validate_local_pptx(path: str | Path) -> dict[str, object]:
    pptx_path = Path(path)
    if not pptx_path.is_file():
        raise FileNotFoundError(pptx_path)
    size_bytes = pptx_path.stat().st_size
    if size_bytes <= 0:
        raise ValueError(f"PPTX file is empty: {pptx_path}")
    try:
        with zipfile.ZipFile(pptx_path) as archive:
            names = set(archive.namelist())
            if "ppt/presentation.xml" not in names:
                raise ValueError("ppt/presentation.xml is missing from the PPTX archive")
            presentation_xml = archive.read("ppt/presentation.xml")
            slide_names = [name for name in names if name.startswith("ppt/slides/slide") and name.endswith(".xml")]
    except zipfile.BadZipFile as exc:
        raise ValueError(f"PPTX is not a readable zip archive: {pptx_path}") from exc
    try:
        ElementTree.fromstring(presentation_xml)
    except ElementTree.ParseError as exc:
        raise ValueError("ppt/presentation.xml is not valid XML") from exc
    slide_count = len(slide_names)
    if slide_count < 1:
        raise ValueError("PPTX must contain at least one slide")
    checksum = hashlib.sha256(pptx_path.read_bytes()).hexdigest()
    return {
        "file_size_bytes": size_bytes,
        "zip_readable": True,
        "presentation_xml_present": True,
        "slide_count": slide_count,
        "checksum": checksum,
    }
