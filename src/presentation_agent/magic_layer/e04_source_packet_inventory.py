"""Find and validate the approved source packet for E04."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .e03_16_orchestrator import read_json


def inventory_e04_source_packets(repo_root: Path, run_root: Path) -> dict[str, Any]:
    search_paths = [
        run_root / "source_packets",
        run_root / "inputs",
        run_root / "outputs",
        repo_root / "tests" / "fixtures",
    ]
    candidates: list[dict[str, Any]] = []
    for root in search_paths:
        if not root.exists():
            continue
        for path in root.rglob("*.json"):
            name = path.name.lower()
            if "source_document_manifest" in name or "source_packet" in name or "source_bound_small_deck_manifest" in name:
                payload = read_json(path, default={})
                candidates.append(_candidate(path, payload, repo_root))
    approved = sorted(
        [row for row in candidates if row["approved"]],
        key=lambda row: (
            "harness_v3_source_bound_small_deck" not in row["path"],
            "source_document_manifest_c08.json" not in row["path"],
            row["path"],
        ),
    )
    selected = approved[0] if approved else None
    source_records = _records_from_manifest(selected, repo_root) if selected else []
    return {
        "schema_name": "e04_source_packet_inventory",
        "status": "passed" if selected else "blocked",
        "decision": "E04_SOURCE_PACKET_SELECTED" if selected else "E04_BLOCKED_MISSING_APPROVED_SOURCE_PACKET",
        "source_packet_status": "approved_source_packet_found" if selected else "missing_approved_source_packet",
        "source_packet_type": "preferred_real_source" if selected else None,
        "real_world_claims": bool(selected),
        "selected_source_packet": selected,
        "candidate_count": len(candidates),
        "approved_candidate_count": len(approved),
        "candidates": candidates,
        "source_records": source_records,
        "source_record_count": len(source_records),
    }


def build_missing_source_packet_requirements() -> dict[str, Any]:
    return {
        "schema_name": "e04_source_packet_requirements",
        "status": "blocked",
        "decision": "E04_BLOCKED_MISSING_APPROVED_SOURCE_PACKET",
        "requirements": [
            "source_id, title, source_type, excerpt/data payload",
            "citation_id and visible citation text",
            "allowed claims, metrics, table rows, and chart values",
            "applicable slide/archetype mapping",
        ],
    }


def _candidate(path: Path, payload: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    source_docs = payload.get("source_documents", [])
    source_exists = all((repo_root / doc.get("path", "")).exists() for doc in source_docs if doc.get("path"))
    approved = (
        payload.get("status") == "passed"
        and payload.get("selected_source_mode") == "preferred_real_source"
        and bool(payload.get("citations"))
        and source_exists
    )
    return {
        "path": path.as_posix(),
        "schema_name": payload.get("schema_name"),
        "status": payload.get("status"),
        "selected_source_mode": payload.get("selected_source_mode"),
        "citation_count": len(payload.get("citations", [])),
        "source_document_count": len(source_docs),
        "source_documents_exist": source_exists,
        "approved": approved,
    }


def _records_from_manifest(selected: dict[str, Any] | None, repo_root: Path) -> list[dict[str, Any]]:
    if not selected:
        return []
    manifest = read_json(Path(selected["path"]))
    rows: list[dict[str, Any]] = []
    for citation in manifest.get("citations", []):
        rows.append(
            {
                "source_id": citation["source_id"],
                "title": citation.get("label"),
                "source_type": "markdown",
                "excerpt": citation.get("snippet"),
                "citation_id": citation["citation_id"],
                "citation_text": f"{citation.get('label')} | {citation['citation_id']} | {citation.get('anchor')}",
                "owner_or_authority": "local approved source packet",
                "applicable_slide_or_archetype": "E04 deck plan",
                "allowed_claims": [citation.get("snippet")],
                "allowed_metrics": [],
                "allowed_table_rows": [],
                "allowed_chart_values": [],
                "freshness_label": "local source packet",
                "anchor": citation.get("anchor"),
            }
        )
    return rows
