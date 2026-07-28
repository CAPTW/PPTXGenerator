"""Generated icon registry patch for E03.2.1."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .e03_16_orchestrator import write_json


def build_generated_icon_registry_patch(generated_manifest: dict[str, Any], quality_report: dict[str, Any], registry_path: Path) -> dict[str, Any]:
    quality_by_path = {row["svg_path"]: row for row in quality_report["icons"]}
    entries = []
    for icon in generated_manifest["icons"]:
        quality = quality_by_path.get(icon["svg_path"], {})
        entries.append(
            {
                "icon_id": Path(icon["svg_path"]).stem,
                "role_hint": icon["likely_role"],
                "source_reference_id": icon["archetype_id"],
                "source_crop_path": icon["source_crop_path"],
                "source_crop_sha256": icon["crop_sha256"],
                "generated_svg_path": icon["svg_path"],
                "viewBox": "0 0 24 24",
                "stroke_or_fill_style": "currentColor stroke",
                "created_stage": "E03.2.1",
                "generation_method": icon["generation_method"],
                "policy_status": quality.get("status", "failed"),
                "render_match_score": quality.get("shape_similarity_to_crop", 0.0),
                "reusable": True,
            }
        )
    patch = {"schema_name": "generated_icon_registry_patch", "status": "passed" if all(entry["policy_status"] == "passed" for entry in entries) else "failed", "entry_count": len(entries), "entries": entries}
    write_json(registry_path, patch)
    return patch
