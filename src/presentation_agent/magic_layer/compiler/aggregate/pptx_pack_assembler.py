from __future__ import annotations

from pathlib import Path
from typing import Any

from .ooxml_slide_importer import source_slide_manifest
from .powerpoint_com_pack_assembler import assemble_with_powerpoint_com


def assemble_pptx_review_pack(source_pptx: list[str | Path], output_path: str | Path) -> dict[str, Any]:
    report = assemble_with_powerpoint_com(source_pptx, output_path)
    report["source_slide_manifest"] = source_slide_manifest(source_pptx)
    return report
