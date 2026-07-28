"""P2 pack compiler for E03H-P."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from src.presentation_agent.magic_layer.e03h_pack_compiler import compile_e03h_reference_pack


def compile_e03h_p_reference_pack(payloads: list[dict[str, Any]], output_dir: str | Path) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    report = compile_e03h_reference_pack(payloads, output)
    p2_pptx = output / "editable_hybrid_reference_pack_p2.pptx"
    p2_contact = output / "editable_hybrid_reference_pack_p2_contact_sheet.png"
    shutil.copy2(report["pptx_path"], p2_pptx)
    shutil.copy2(report["contact_sheet"], p2_contact)
    return {
        **report,
        "schema_name": "editable_hybrid_reference_pack_p2_render_manifest",
        "pptx_path": p2_pptx.as_posix(),
        "pptx_exists": p2_pptx.exists(),
        "contact_sheet": p2_contact.as_posix(),
        "rendered_contact_sheet": p2_contact.as_posix(),
        "canva_parity_claimed": False,
    }
