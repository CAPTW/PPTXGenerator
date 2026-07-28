"""Source ingestion bridge for the E04 source-bound small deck gate."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from src.presentation_agent.source_ingestion import ingest_source_file


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SOURCE_PATH = REPO_ROOT / "inputs/source_premium_mini_deck.md"


def choose_source_mode(preferred_source_path: str | Path | None = None) -> dict[str, Any]:
    """Choose the source mode for E04 without inventing remote inputs."""

    source_path = _resolve_source_path(preferred_source_path or DEFAULT_SOURCE_PATH)
    if source_path.exists() and source_path.is_file():
        return {
            "schema_name": "source_mode_report",
            "status": "passed",
            "mode": "MODE_A_REAL_SOURCE_DOCUMENT",
            "source_path": _rel(source_path),
            "source_type": source_path.suffix.lower().lstrip("."),
            "real_source_production_claimed": True,
            "controlled_fixture_used": False,
            "reason": "existing local source document selected",
        }

    existing_artifacts = sorted(
        REPO_ROOT.glob("design_runs/run_002/outputs/**/source_document_graph_v1.json")
    )
    if existing_artifacts:
        return {
            "schema_name": "source_mode_report",
            "status": "passed",
            "mode": "MODE_B_EXISTING_SOURCE_GRAPH",
            "source_path": _rel(existing_artifacts[0]),
            "source_type": "source_graph",
            "real_source_production_claimed": True,
            "controlled_fixture_used": False,
            "reason": "existing local source graph selected",
        }

    return {
        "schema_name": "source_mode_report",
        "status": "warning",
        "mode": "MODE_C_CONTROLLED_SOURCE_FIXTURE",
        "source_path": None,
        "source_type": "fixture",
        "real_source_production_claimed": False,
        "controlled_fixture_used": True,
        "reason": "no local source document or source graph found",
    }


def build_source_artifacts(source_path: str | Path = DEFAULT_SOURCE_PATH) -> dict[str, Any]:
    """Ingest a local source and derive the ledgers E04 needs."""

    resolved = _resolve_source_path(source_path)
    document = ingest_source_file(resolved)
    graph = document.model_dump(mode="json", exclude_none=True)
    raw_text = resolved.read_text(encoding="utf-8")
    chunks = graph.get("chunks", [])
    citations = _build_citations(graph, resolved)
    evidence = _build_evidence(graph, citations)
    tables = _parse_markdown_tables(raw_text, chunks)
    charts = _parse_metric_chart(raw_text, chunks)
    element_rows = _build_element_rows(graph, evidence, tables, charts)
    source_mode = choose_source_mode(resolved)
    parse_quality = {
        "schema_name": "source_parse_quality_report",
        "status": "passed" if chunks and evidence and citations else "failed",
        "source_path": _rel(resolved),
        "source_type": graph.get("source_type"),
        "chunk_count": len(chunks),
        "outline_item_count": len(graph.get("outline", {}).get("items", [])),
        "evidence_count": len(evidence),
        "table_count": len(tables),
        "chart_count": len(charts),
        "citation_count": len(citations),
        "warnings": graph.get("warnings", []),
    }
    return {
        "source_mode_report": source_mode,
        "source_document_graph_v1": graph,
        "source_element_ledger": {
            "schema_name": "source_element_ledger",
            "status": "passed",
            "source_path": _rel(resolved),
            "element_count": len(element_rows),
            "elements": element_rows,
        },
        "evidence_bank_v1": {
            "schema_name": "evidence_bank_v1",
            "status": "passed",
            "evidence_count": len(evidence),
            "evidence": evidence,
        },
        "table_data_ledger": {
            "schema_name": "table_data_ledger",
            "status": "passed" if tables else "warning",
            "table_count": len(tables),
            "tables": tables,
        },
        "chart_data_ledger": {
            "schema_name": "chart_data_ledger",
            "status": "passed" if charts else "warning",
            "chart_count": len(charts),
            "charts": charts,
        },
        "citation_reference_ledger": {
            "schema_name": "citation_reference_ledger",
            "status": "passed" if citations else "failed",
            "citation_count": len(citations),
            "citations": citations,
        },
        "source_parse_quality_report": parse_quality,
    }


def _build_citations(graph: dict[str, Any], source_path: Path) -> list[dict[str, Any]]:
    citations = []
    for index, chunk in enumerate(graph.get("chunks", []), start=1):
        heading = " / ".join(chunk.get("heading_path") or []) or graph.get("title", "Source")
        citations.append(
            {
                "citation_id": f"SRC-{index:03d}",
                "label": f"{source_path.name}, lines {chunk.get('start_line')}-{chunk.get('end_line')}",
                "source_path": _rel(source_path),
                "source_chunk_ids": [chunk["chunk_id"]],
                "heading": heading,
                "source_anchor": f"{source_path.name}:{chunk.get('start_line')}",
            }
        )
    return citations


def _build_evidence(graph: dict[str, Any], citations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    citation_by_chunk = {
        chunk_id: citation
        for citation in citations
        for chunk_id in citation.get("source_chunk_ids", [])
    }
    evidence = []
    for index, chunk in enumerate(graph.get("chunks", []), start=1):
        citation = citation_by_chunk.get(chunk["chunk_id"], {})
        evidence.append(
            {
                "evidence_id": f"EVD-{index:03d}",
                "source_chunk_id": chunk["chunk_id"],
                "citation_id": citation.get("citation_id"),
                "heading": " / ".join(chunk.get("heading_path") or []),
                "quote": _first_sentence(chunk.get("text", "")),
                "claim_support": _evidence_support_label(chunk),
                "confidence": 0.82,
            }
        )
    return evidence


def _parse_markdown_tables(raw_text: str, chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    lines = raw_text.splitlines()
    tables: list[dict[str, Any]] = []
    for index, line in enumerate(lines):
        if "|" not in line or line.strip().startswith("|---"):
            continue
        row_block: list[str] = []
        for candidate in lines[index:]:
            if "|" not in candidate.strip():
                break
            if set(candidate.replace("|", "").strip()) <= {"-", ":"}:
                continue
            row_block.append(candidate.strip())
        if len(row_block) < 2:
            continue
        rows = [[cell.strip() for cell in row.split("|")] for row in row_block]
        header = rows[0]
        if len(header) < 2:
            continue
        table_id = f"TBL-{len(tables) + 1:03d}"
        tables.append(
            {
                "table_id": table_id,
                "title": "Operating choice comparison",
                "source_chunk_id": _chunk_for_text(chunks, "Operating choice comparison"),
                "header": header,
                "rows": rows[1:],
                "native_binding_required": True,
                "raster_allowed": False,
            }
        )
        break
    return tables


def _parse_metric_chart(raw_text: str, chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    points = []
    for label, value in re.findall(r"([A-Z][A-Za-z ]+?) reached (\d+) percent", raw_text):
        points.append({"label": label.strip(), "value": int(value), "unit": "percent"})
    if not points:
        return []
    return [
        {
            "chart_id": "CHART-001",
            "title": "Readiness signals",
            "chart_type": "bar",
            "source_chunk_id": _chunk_for_text(chunks, "Trace coverage"),
            "data_points": points,
            "native_binding_required": True,
            "raster_allowed": False,
        }
    ]


def _build_element_rows(
    graph: dict[str, Any],
    evidence: list[dict[str, Any]],
    tables: list[dict[str, Any]],
    charts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = [
        {
            "element_id": f"CHUNK-{index:03d}",
            "element_type": "source_chunk",
            "source_chunk_id": chunk["chunk_id"],
            "heading": " / ".join(chunk.get("heading_path") or []),
            "text_excerpt": chunk.get("text", "")[:220],
        }
        for index, chunk in enumerate(graph.get("chunks", []), start=1)
    ]
    rows.extend({"element_id": item["evidence_id"], "element_type": "evidence", **item} for item in evidence)
    rows.extend({"element_id": item["table_id"], "element_type": "table", **item} for item in tables)
    rows.extend({"element_id": item["chart_id"], "element_type": "chart", **item} for item in charts)
    return rows


def _chunk_for_text(chunks: list[dict[str, Any]], needle: str) -> str | None:
    needle_lower = needle.lower()
    for chunk in chunks:
        if needle_lower in chunk.get("text", "").lower():
            return chunk.get("chunk_id")
    return chunks[0]["chunk_id"] if chunks else None


def _evidence_support_label(chunk: dict[str, Any]) -> str:
    heading = " / ".join(chunk.get("heading_path") or []).lower()
    if "problem" in heading:
        return "problem framing"
    if "framework" in heading:
        return "method framework"
    if "evidence" in heading:
        return "comparison evidence"
    if "metrics" in heading:
        return "dashboard metric"
    if "recommendation" in heading:
        return "recommendation support"
    return "context evidence"


def _first_sentence(text: str) -> str:
    compact = " ".join(text.split())
    for delimiter in (". ", "? ", "! "):
        if delimiter in compact:
            return compact.split(delimiter, 1)[0].strip() + delimiter.strip()
    return compact[:260].strip()


def _resolve_source_path(path: str | Path) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = REPO_ROOT / candidate
    return candidate.resolve()


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.resolve().as_posix()
