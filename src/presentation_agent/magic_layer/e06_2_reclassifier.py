"""E06.1 reclassification for the E06.2 contract-first compile gate."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


RECLASSIFICATION_DECISION = "E06_1_RECLASSIFIED_LAYOUT_INVENTORY_PASS_CONTRACT_FIRST_RECOMPILE_REQUIRED"


def build_e06_1_reclassification_report(e06_1_root: Path) -> dict[str, Any]:
    report = _read_json(e06_1_root / "e06_1_layout_contract_precision_report.json")
    readiness = _read_json(e06_1_root / "e07_readiness_report.json")
    html_index = e06_1_root / "html_workbench" / "index.html"
    checks = {
        "e06_1_final_decision_passed": report.get("decision") == "E06_1_PASS_START_E07_BASELINE_PROMOTION_REVIEW_WITH_LAYOUT_CONTRACT",
        "layout_contract_exists": (e06_1_root / "layout_contract_16_slides.json").exists(),
        "html_workbench_exists": html_index.exists(),
        "coordinate_extraction_exists": (e06_1_root / "pptx_coordinate_extraction_report.json").exists(),
        "e07_previous_ready_with_inventory": readiness.get("decision") == "E07_READY_START_BASELINE_PROMOTION_REVIEW_WITH_LAYOUT_CONTRACT",
        "protected_artifacts_unchanged": bool(report.get("protected_artifacts_unchanged", False)),
    }
    return {
        "schema_name": "e06_1_reclassification_report",
        "decision": RECLASSIFICATION_DECISION,
        "e06_1_layout_inventory_status": "PASS" if checks["layout_contract_exists"] and checks["e06_1_final_decision_passed"] else "NOT_PROVEN",
        "e06_1_html_workbench_status": "PASS" if checks["html_workbench_exists"] else "MISSING",
        "e06_1_pptx_coordinate_extraction_status": "PASS" if checks["coordinate_extraction_exists"] else "MISSING",
        "e06_1_coordinate_extraction_status": "PASS" if checks["coordinate_extraction_exists"] else "MISSING",
        "e06_1_contract_first_compile_status": "NOT_PROVEN",
        "e07_unlock_status": "REVOKED_PENDING_E06_2",
        "broad_canva_parity_claimed": False,
        "status": "passed" if all(checks.values()) else "blocked",
        "checks": checks,
    }


def build_contract_first_compile_policy_v1() -> dict[str, Any]:
    return {
        "schema_name": "contract_first_compile_policy_v1",
        "source_of_truth": "layout_contract_16_slides.json",
        "rules": [
            "Objects are created from contract records.",
            "Coordinates are converted from contract EMU fields; inch and normalized coordinates are retained for validation.",
            "Z-order follows contract order.",
            "Semantic icon media resolves from curated Magic Layer v7.1 SVG assets.",
            "Source, citation, and slot binding identifiers are preserved in generated object metadata.",
            "Semantic object names include the contract object_id.",
            "No existing slide XML is copied wholesale.",
            "No screenshot, full-slide raster, or semantic raster fallback is allowed.",
        ],
        "allowed_reuse": [
            "bounded raster visual assets referenced by contract media part names",
            "curated v7.1 SVG icon assets",
            "source-bound text/data from existing ledgers",
            "style tokens derived from object type and contract role",
        ],
        "forbidden": [
            "wholesale copy of existing slide shapes without contract object mapping",
            "hidden duplicate objects",
            "unrecorded fallback",
            "coordinate magic numbers not present in contract",
            "unanchored semantic icons",
        ],
        "broad_canva_parity_claimed": False,
    }


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))
