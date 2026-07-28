from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .e03_reference_contract import CORE_ARCHETYPES, EXPANSION_ARCHETYPES


def build_reference_registry_template() -> dict[str, Any]:
    references = []
    for archetype in CORE_ARCHETYPES:
        references.append(_entry(archetype, "CORE_VALIDATED_IN_PRIOR_RUN_NEEDS_RV01_REGISTRY_CONFIRMATION", True, True))
    for archetype in EXPANSION_ARCHETYPES:
        references.append(_entry(archetype, "MISSING_OR_NOT_VALIDATED", len([r for r in references if r["required_for_minimum"]]) < 12, True))
    return {
        "schema": "e03_reference_registry.v1",
        "active_run": "run_004",
        "objective": "recovery_validation_planning",
        "generated_by": "RV00",
        "references": references,
        "core_reference_evidence": {
            "p05": "design_runs/run_003/outputs/p05_rx_four_core_pipeline_v2_regression_e02_references",
            "p06": "design_runs/run_003/outputs/p06_rx_four_core_pipeline_v2_aggregate_regression_review_pack",
        },
        "expansion_reference_status": "MISSING_OR_NOT_VALIDATED",
        "product_pass": False,
    }


def write_reference_registry_template(root: str | Path) -> dict[str, Any]:
    path = Path(root) / "design_runs/run_004/inputs/e03_rx/reference_registry.json"
    data = build_reference_registry_template()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "schema": "e03_reference_registry_template_report.v1",
        "registry_path": str(path),
        "reference_count": len(data["references"]),
        "core_status": "CORE_VALIDATED_IN_PRIOR_RUN_NEEDS_RV01_REGISTRY_CONFIRMATION",
        "expansion_reference_status": "MISSING_OR_NOT_VALIDATED",
        "hash_width_height_populated": False,
        "reference_images_copied": 0,
        "product_pass": False,
    }


def load_and_normalize_reference_registry(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    if not path.is_file():
        return {"schema": "e03_reference_registry_load_report.v1", "status": "REGISTRY_MISSING", "registry_path": str(path), "registry": build_reference_registry_template(), "active_registry_updated": False, "product_pass": False}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"schema": "e03_reference_registry_load_report.v1", "status": "REGISTRY_UNREADABLE", "registry_path": str(path), "error": str(exc), "registry": build_reference_registry_template(), "active_registry_updated": False, "product_pass": False}
    changed = False
    data.setdefault("schema", "e03_reference_registry.v1")
    data.setdefault("active_run", "run_004")
    data.setdefault("objective", "recovery_validation_planning")
    refs = data.setdefault("references", [])
    if not isinstance(refs, list):
        refs = []
        data["references"] = refs
        changed = True
    by_id = {item.get("archetype_id"): item for item in refs if isinstance(item, dict)}
    normalized = []
    for template in build_reference_registry_template()["references"]:
        existing = by_id.get(template["archetype_id"], {})
        if not existing:
            changed = True
        merged = {**template, **existing}
        for key in ["hash", "width", "height", "provenance"]:
            merged.setdefault(key, None)
        merged.setdefault("validation_decision", "NOT_VALIDATED")
        merged.setdefault("validation_required", True)
        merged.setdefault("source_policy", "ACTIVE_RUN_004_REGISTERED_INPUT_ONLY")
        normalized.append(merged)
    data["references"] = normalized
    return {
        "schema": "e03_reference_registry_load_report.v1",
        "status": "REGISTRY_LOADED_WITH_NORMALIZATION" if changed else "REGISTRY_LOADED",
        "registry_path": str(path),
        "reference_count": len(normalized),
        "registry": data,
        "active_registry_updated": False,
        "product_pass": False,
    }


def update_registry_with_validation(path: str | Path, validation_rows: list[dict[str, Any]]) -> dict[str, Any]:
    path = Path(path)
    load = load_and_normalize_reference_registry(path)
    registry = load["registry"]
    rows = {row["archetype_id"]: row for row in validation_rows}
    for entry in registry.get("references", []):
        row = rows.get(entry.get("archetype_id"), {})
        entry["status"] = row.get("registry_status_after_rv01", row.get("readiness_decision", entry.get("status")))
        entry["validation_decision"] = row.get("readiness_decision", entry.get("validation_decision", "NOT_VALIDATED"))
        entry["hash"] = row.get("sha256", entry.get("hash"))
        entry["width"] = row.get("width", entry.get("width"))
        entry["height"] = row.get("height", entry.get("height"))
        entry["source_policy_decision"] = row.get("source_policy_decision")
        entry["semantic_contract_decision"] = row.get("semantic_decision")
        entry["blockers"] = row.get("blockers", [])
        entry["limitations"] = row.get("limitations", [])
        entry["validated_at_stage"] = "RV01"
    path.write_text(json.dumps(registry, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"schema": "e03_reference_registry_update_report.v1", "active_registry_updated": True, "registry_path": str(path), "reference_count": len(registry.get("references", [])), "fake_hashes_inserted": False, "product_pass": False}


def build_rv01a_registry_patch(
    path: str | Path,
    *,
    update_active: bool,
    prior_hashes: dict[str, str | None] | None = None,
) -> dict[str, Any]:
    path = Path(path)
    prior_hashes = prior_hashes or {}
    load = load_and_normalize_reference_registry(path)
    registry = load["registry"]
    for entry in registry.get("references", []):
        archetype = entry.get("archetype_id")
        entry["expected_filename"] = f"{archetype}.png"
        entry["status"] = "AWAITING_MANUAL_PLACEMENT"
        entry["validation_decision"] = "MISSING"
        entry["semantic_assertion_required"] = True
        entry["provenance_required"] = True
        entry["hash"] = None
        entry["width"] = None
        entry["height"] = None
        entry["blockers"] = ["MISSING_REFERENCE_FILE"]
        entry["next_validation_stage"] = "RV01_RERUN"
        if archetype in CORE_ARCHETYPES:
            entry["prior_evidence_available"] = True
            entry["prior_evidence_stage"] = "P05/P06/C05"
            entry["prior_hash"] = prior_hashes.get(archetype)
            entry["active_reference_required"] = True
        else:
            entry["prior_evidence_available"] = False
            entry["prior_evidence_stage"] = None
            entry["prior_hash"] = None
            entry["active_reference_required"] = True
    registry["rv01a_status"] = "AWAITING_MANUAL_PLACEMENT"
    registry["product_pass"] = False
    if update_active:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(registry, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "schema": "e03_reference_registry_update_report.v1",
        "registry_path": str(path),
        "active_registry_updated": bool(update_active),
        "reference_count": len(registry.get("references", [])),
        "status": "ACTIVE_REGISTRY_PATCHED_AWAITING_MANUAL_PLACEMENT" if update_active else "PROPOSED_REGISTRY_ONLY",
        "fake_hashes_inserted": False,
        "fake_dimensions_inserted": False,
        "registry": registry,
        "product_pass": False,
    }


def _entry(archetype_id: str, status: str, required_minimum: bool, required_full: bool) -> dict[str, Any]:
    return {
        "archetype_id": archetype_id,
        "expected_path": f"design_runs/run_004/inputs/e03_rx/references/{archetype_id}.png",
        "status": status,
        "required_for_minimum": required_minimum,
        "required_for_full": required_full,
        "source_policy": "ACTIVE_RUN_004_REGISTERED_INPUT_ONLY",
        "validation_required": True,
        "hash": None,
        "width": None,
        "height": None,
        "provenance": None,
        "validation_decision": "NOT_VALIDATED",
    }
