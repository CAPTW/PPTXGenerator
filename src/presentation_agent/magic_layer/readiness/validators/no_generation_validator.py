from __future__ import annotations

from pathlib import Path
from typing import Any


def validate_no_generation(folder: str | Path) -> dict[str, Any]:
    root = Path(folder)
    pptx = list(root.rglob("*.pptx")) if root.exists() else []
    png = list(root.rglob("*.png")) if root.exists() else []
    forbidden = [*pptx, *png]
    return {
        "schema": "no_generation_audit_report.v1",
        "folder": str(root),
        "pptx_count": len(pptx),
        "png_count": len(png),
        "forbidden_artifacts": [str(path) for path in forbidden],
        "source_bound_deck_count": len([path for path in root.rglob("*source*bound*.pptx")]) if root.exists() else 0,
        "template_pack_count": len([path for path in root.rglob("*template*pack*.pptx")]) if root.exists() else 0,
        "canonical_artifact_count": len([path for path in forbidden if path.name in {"golden_template_masters.pptx", "final_deck_large_premium.pptx"}]),
        "pass": not forbidden,
        "product_pass": False,
    }
