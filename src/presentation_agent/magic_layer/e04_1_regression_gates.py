"""Regression gates for E04.1."""

from __future__ import annotations

from typing import Any


def build_source_citation_binding_regression_report(slot_ledger: dict[str, Any], source_ledger: dict[str, Any], citation_ledger: dict[str, Any]) -> dict[str, Any]:
    source_regression = 178 - int(source_ledger.get("source_binding_count", 0))
    citation_regression = 178 - int(citation_ledger.get("citation_binding_count", 0))
    slot_regression = 178 - int(slot_ledger.get("slot_binding_count", 0))
    return {
        "schema_name": "source_citation_binding_regression_report",
        "status": "passed" if source_regression == 0 and citation_regression == 0 and slot_regression == 0 else "failed",
        "source_binding_regression_count": max(0, source_regression),
        "citation_binding_regression_count": max(0, citation_regression),
        "slot_binding_regression_count": max(0, slot_regression),
        "source_binding_count": source_ledger.get("source_binding_count", 0),
        "citation_binding_count": citation_ledger.get("citation_binding_count", 0),
        "slot_binding_count": slot_ledger.get("slot_binding_count", 0),
    }


def build_contract_v2_regression_report(e04_contract_status: str) -> dict[str, Any]:
    return {
        "schema_name": "contract_v2_regression_report",
        "status": "passed" if e04_contract_status == "passed" else "failed",
        "contract_v2_status": e04_contract_status,
        "fatal_warning_regression_count": 0 if e04_contract_status == "passed" else 1,
    }
