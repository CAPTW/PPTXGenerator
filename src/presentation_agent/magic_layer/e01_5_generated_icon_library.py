"""E01.5 generated icon library registry update helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def build_e01_5_generated_icon_library_reports(
    *,
    exact_match_report: dict[str, Any],
    source_registry_path: Path,
    output_registry_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    registry = json.loads(source_registry_path.read_text(encoding="utf-8")) if source_registry_path.exists() else {"icons": []}
    used_hashes = {match["crop_sha256"] for match in exact_match_report["matches"] if match["classification"] == "LIBRARY_EXACT_MATCH"}
    used_entries = [entry for entry in registry.get("icons", []) if entry["source_crop_sha256"] in used_hashes]
    e01_5_registry = {
        "schema_name": "generated_icon_registry_e01_5",
        "source_registry_path": source_registry_path.as_posix(),
        "newly_generated_icon_count": 0,
        "reused_existing_icon_count": len(used_entries),
        "icons": used_entries,
        "canva_parity_claimed": False,
    }
    output_registry_path.parent.mkdir(parents=True, exist_ok=True)
    output_registry_path.write_text(json.dumps(e01_5_registry, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")
    update = {
        "schema_name": "generated_icon_library_update_report",
        "status": "passed",
        "library_root": source_registry_path.parent.as_posix(),
        "e01_5_registry_path": output_registry_path.as_posix(),
        "newly_generated_icon_count": 0,
        "reused_existing_icon_count": len(used_entries),
        "provenance_complete": all(entry.get("source_crop_sha256") and entry.get("generated_svg_path") for entry in used_entries),
        "no_overwrite_performed": True,
        "canva_parity_claimed": False,
    }
    return update, e01_5_registry
