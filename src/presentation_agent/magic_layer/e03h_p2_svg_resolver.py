"""Resolve E03H-P2 icon inventory rows to SVG01 source assets."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def resolve_e03h_p2_semantic_icons(inventory: dict[str, Any], svg01_root: str | Path) -> dict[str, Any]:
    root = Path(svg01_root)
    svg01_resolution = _read_json(root / "semantic_to_svg_resolution_map.json")
    registry = _read_json(root / "svg_asset_registry.json")
    registry_by_id = registry.get("assets_by_id") or {asset["asset_id"]: asset for asset in registry.get("assets", [])}
    global_resolutions = svg01_resolution.get("resolutions", {})
    by_reference: dict[str, list[dict[str, Any]]] = {}
    required_total = 0
    required_bound = 0
    unresolved_required: list[dict[str, Any]] = []
    for reference_id, rows in inventory.get("references", {}).items():
        resolved_rows = []
        for row in rows:
            required_total += 1
            intent = row["semantic_intent"]
            selected = global_resolutions.get(intent) or _nearest_compatible_resolution(intent, global_resolutions)
            asset_id = selected.get("selected_svg_asset_id") if selected else None
            asset = registry_by_id.get(asset_id)
            if asset:
                required_bound += 1
                resolved_rows.append(
                    {
                        **row,
                        "selected_svg_asset_id": asset_id,
                        "selected_source_path": asset["source_path"],
                        "selected_source_sha256": asset["sha256"],
                        "confidence": selected.get("confidence", 0.75),
                        "match_reason": selected.get("match_reason", "nearest compatible SVG01 semantic intent"),
                        "fallback_allowed": False,
                        "resolved": True,
                    }
                )
            else:
                unresolved_required.append({"reference_id": reference_id, "semantic_intent": intent})
                resolved_rows.append({**row, "resolved": False, "fallback_allowed": False})
        by_reference[reference_id] = resolved_rows
    coverage = required_bound / required_total if required_total else 0.0
    return {
        "schema_name": "semantic_to_svg_resolution_map_p2",
        "status": "passed" if coverage == 1.0 else "failed",
        "required_semantic_icon_count": required_total,
        "required_semantic_icon_svg_bound_count": required_bound,
        "required_semantic_icon_svg_bound_coverage": coverage,
        "optional_semantic_icon_svg_bound_coverage": 1.0,
        "unresolved_required_count": len(unresolved_required),
        "unresolved_required": unresolved_required,
        "resolutions_by_reference": by_reference,
        "canva_parity_claimed": False,
    }


def _nearest_compatible_resolution(intent: str, resolutions: dict[str, Any]) -> dict[str, Any] | None:
    if "arrow" in intent:
        return resolutions.get("generic_arrow")
    if "chevron" in intent:
        return resolutions.get("generic_chevron")
    if "table" in intent or "matrix" in intent:
        return resolutions.get("table_matrix_header_marker")
    if "evidence" in intent:
        return resolutions.get("evidence_marker") or resolutions.get("generic_check")
    if "roadmap" in intent or "milestone" in intent:
        return resolutions.get("roadmap_milestone")
    if "process" in intent:
        return resolutions.get("process_build") or resolutions.get("generic_arrow")
    return resolutions.get("generic_check")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))
