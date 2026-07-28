from __future__ import annotations

from pathlib import Path
from typing import Any

from .aggregate_report import read_json, sha256_file
from .aggregate_scope_guard import ARCHETYPES


def build_p06_input_inventory(p05_run: str | Path) -> dict[str, Any]:
    root = Path(p05_run)
    rows: dict[str, dict[str, Any]] = {}
    complete = True
    for index, archetype in enumerate(ARCHETYPES, start=1):
        folder = root / "archetypes" / archetype
        decision = read_json(folder / "archetype_decision.json")
        b03 = read_json(folder / "b03_validation_report.json")
        b01 = read_json(folder / "b01_review_packet.json")
        gate = read_json(folder / "archetype_gate_report.json")
        full = read_json(folder / "pptx_full_slide_raster_check.json")
        semantic = read_json(folder / "pptx_semantic_editability_ledger.json")
        pptx = folder / "controlled_candidate.pptx"
        render = folder / "rendered_slide.png"
        present = all(path.is_file() for path in [folder / "archetype_decision.json", pptx, folder / "b03_validation_report.json", render, folder / "b01_review_packet.json", folder / "archetype_gate_report.json"])
        allowed = present and decision.get("decision") in {"ARCHETYPE_P05_PASS", "ARCHETYPE_P05_PASS_WITH_LIMITATIONS"} and b03.get("status") in {"PASS", "PASS_WITH_LIMITATIONS"} and b01.get("decision") in {"REVIEW_READY", "REVIEW_READY_WITH_LIMITATIONS"}
        if not allowed:
            complete = False
        rows[archetype] = {
            "schema": "p06_archetype_input_inventory.v1",
            "archetype_id": archetype,
            "aggregate_slide_index": index,
            "p05_folder_path": str(folder),
            "p05_decision": decision.get("decision"),
            "p05_reference_hash": _reference_hash(folder),
            "p05_pptx_path": str(pptx),
            "p05_pptx_hash": sha256_file(pptx),
            "p05_render_path": str(render),
            "p05_render_hash": sha256_file(render),
            "p05_b03_status": b03.get("status"),
            "p05_b01_status": b01.get("decision"),
            "full_slide_raster_count": int(full.get("full_slide_raster_count", 0) or 0),
            "semantic_raster_violation_count": int(semantic.get("semantic_raster_violation_count", 0) or 0),
            "unknown_content_bearing_count": int(semantic.get("unknown_content_bearing_count", 0) or 0),
            "native_component_status": gate.get("chart_table_native_policy"),
            "limitations": gate.get("limitations", []),
            "allowed_for_aggregate": bool(allowed),
            "render_used_as_slide_content": False,
            "historical_e02_used_as_source_pack": False,
            "product_pass": False,
        }
    return {
        "schema": "p06_input_inventory.v1",
        "p05_run": str(root),
        "archetypes": rows,
        "complete": complete,
        "entry_status": "PASS" if complete else "BLOCKED_INCOMPLETE_P05_INPUTS",
        "product_pass": False,
    }


def build_lineage_report(inventory: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "p06_per_archetype_lineage_report.v1",
        "status": "P06_AGGREGATE_LINEAGE_MATCH_WITH_LIMITATIONS" if inventory.get("complete") else "P06_AGGREGATE_INSUFFICIENT_EVIDENCE",
        "archetypes": {
            archetype: {**row, "source_stage": "P05"}
            for archetype, row in inventory.get("archetypes", {}).items()
        },
        "product_pass": False,
        "limitations": ["P06 aggregates noncanonical P05 controlled regression outputs only"],
    }


def _reference_hash(folder: Path) -> str | None:
    manifest = read_json(folder / "input/source_fixture_manifest.json")
    source = manifest.get("reference_source")
    if source:
        return sha256_file(source)
    return sha256_file(folder / "input/reference_image.png")
