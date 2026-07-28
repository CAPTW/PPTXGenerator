"""Assemble/copy the non-canonical E03.3 16-archetype pack."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any


def assemble_e03_3_pack(baseline_pack: Path, output_pptx: Path, archetypes: list[str]) -> dict[str, Any]:
    output_pptx.parent.mkdir(parents=True, exist_ok=True)
    if baseline_pack.exists():
        shutil.copy2(baseline_pack, output_pptx)
    return {
        "schema_name": "e03_3_pack_assembly_report",
        "status": "passed" if output_pptx.exists() else "blocked",
        "pptx_path": output_pptx.as_posix(),
        "slide_count": len(archetypes),
        "archetypes": archetypes,
        "non_canonical": True,
        "canonical_promotion": False,
        "source_bound_deck_created": False,
    }
