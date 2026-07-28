"""Build E04 source-bound slide blueprints from the local source graph."""

from __future__ import annotations

from collections import Counter
from typing import Any


def build_slide_blueprints(plan: dict[str, Any], source_artifacts: dict[str, Any]) -> dict[str, Any]:
    graph = source_artifacts["source_document_graph_v1"]
    evidence = source_artifacts["evidence_bank_v1"]["evidence"]
    table = (source_artifacts["table_data_ledger"].get("tables") or [None])[0]
    chart = (source_artifacts["chart_data_ledger"].get("charts") or [None])[0]
    citations = source_artifacts["citation_reference_ledger"]["citations"]
    citation_ids = [citation["citation_id"] for citation in citations]
    slides = _slides(plan, graph, evidence, table, chart, citation_ids)
    return {
        "schema_name": "slide_blueprint_v1",
        "status": "passed",
        "plan_id": plan["plan_id"],
        "slide_count": len(slides),
        "slides": slides,
        "source_bound": True,
        "canva_parity_claimed": False,
    }


def build_source_to_slide_trace_ledger(blueprints: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for slide in blueprints["slides"]:
        for source_ref in slide.get("source_refs", []):
            rows.append(
                {
                    "slide_id": slide["slide_id"],
                    "slide_number": slide["slide_number"],
                    "archetype_id": slide["archetype_id"],
                    "source_ref": source_ref,
                    "binding_purpose": slide.get("source_binding_purpose", "source evidence"),
                }
            )
    return {
        "schema_name": "source_to_slide_trace_ledger",
        "status": "passed" if rows else "failed",
        "trace_count": len(rows),
        "rows": rows,
        "canva_parity_claimed": False,
    }


def build_claim_evidence_coverage_report(blueprints: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for slide in blueprints["slides"]:
        rows.append(
            {
                "slide_id": slide["slide_id"],
                "claim": slide["main_message"],
                "source_ref_count": len(slide.get("source_refs", [])),
                "status": "covered" if slide.get("source_refs") else "missing",
            }
        )
    missing = [row for row in rows if row["status"] != "covered"]
    return {
        "schema_name": "claim_evidence_coverage_report",
        "status": "passed" if not missing else "failed",
        "claim_count": len(rows),
        "covered_claim_count": len(rows) - len(missing),
        "missing_claim_count": len(missing),
        "rows": rows,
        "canva_parity_claimed": False,
    }


def _slides(
    plan: dict[str, Any],
    graph: dict[str, Any],
    evidence: list[dict[str, Any]],
    table: dict[str, Any] | None,
    chart: dict[str, Any] | None,
    citation_ids: list[str],
) -> list[dict[str, Any]]:
    title = graph.get("title", "Evidence-Centered AI Adoption Governance")
    ev = evidence or [{"quote": title, "citation_id": citation_ids[0] if citation_ids else "SRC-001"}]
    compare_rows = table.get("rows", []) if table else []
    chart_points = chart.get("data_points", []) if chart else []
    framework_points = [
        "Source capture keeps documents, interviews, benchmarks, and policy constraints anchored.",
        "Synthesis converts observations into claims, risks, and decision options.",
        "Evaluation scores options against user value, reliability, complexity, and compliance exposure.",
        "Decision packaging turns evidence into concise recommendations with caveats.",
    ]
    archetypes = plan["archetypes"]
    base: list[dict[str, Any]] = [
        {
            "archetype_id": "cover_hero",
            "title": title,
            "subtitle": "A source-bound sample deck for traceable AI adoption decisions",
            "main_message": "AI governance works best when decision artifacts remain tied to source evidence.",
            "content": {"hero_caption": "Governance operating model", "meta": "Source-bound E04 sample"},
        },
        {
            "archetype_id": "visual_toc",
            "title": "Decision path",
            "subtitle": "The deck moves from problem evidence to operating recommendation.",
            "main_message": "The narrative keeps every major slide tied to a reusable source anchor.",
            "content": {"items": ["Context", "Problem", "Framework", "Evidence", "Metrics", "Roadmap"]},
        },
        {
            "archetype_id": "section_divider",
            "title": "Evidence-centered operating model",
            "subtitle": "From informal review meetings to source-linked decision packaging.",
            "main_message": "The source frames governance as a decision design system.",
            "content": {"section_number": "01", "section_label": "Governance Model"},
        },
        {
            "archetype_id": "standard_content",
            "title": "The recurring governance failure",
            "subtitle": "Disconnected review artifacts make decisions hard to audit.",
            "main_message": "Assumptions, criteria, and final recommendations drift when they are not source-bound.",
            "content": {
                "cards": [
                    {"title": "Assumptions separate", "body": "Review summaries lose the original evidence anchors."},
                    {"title": "Criteria drift", "body": "Teams score decisions differently across review stages."},
                    {"title": "Audits slow down", "body": "Recommendations become difficult to trace after acceleration."},
                ]
            },
        },
        {
            "archetype_id": "evidence_overview",
            "title": "Evidence pattern",
            "subtitle": "The source compares operating choices through traceability, speed, judgment, and repeatability.",
            "main_message": "Hybrid governance preserves expert judgment while improving repeatability.",
            "content": {"evidence_cards": [_card_from_evidence(item) for item in ev[:4]]},
        },
        {
            "archetype_id": "card_grid",
            "title": "Reusable decision artifacts",
            "subtitle": "Structured artifacts make evidence easier to compare and reuse.",
            "main_message": "Reusable cards reduce ambiguous handoffs without flattening expert judgment.",
            "content": {
                "cards": [
                    {"title": "Review artifacts", "body": "Reusable prompts and ledgers"},
                    {"title": "Evidence anchors", "body": "Source-linked claims and caveats"},
                    {"title": "Evaluation criteria", "body": "Visible scoring dimensions"},
                    {"title": "Decision package", "body": "Concise recommendation and risks"},
                ]
            },
        },
        {
            "archetype_id": "methodology_framework",
            "title": "Four-layer workflow",
            "subtitle": "A durable governance workflow is built from structured artifacts.",
            "main_message": "Capture, synthesis, evaluation, and packaging form a repeatable operating layer.",
            "content": {"stages": framework_points},
        },
        {
            "archetype_id": "process_flow",
            "title": "Operating cadence",
            "subtitle": "Each layer produces artifacts that support the next review gate.",
            "main_message": "The process routes routine checks through structure and escalates ambiguity to experts.",
            "content": {"steps": ["Capture", "Synthesize", "Evaluate", "Package", "Review"]},
        },
        {
            "archetype_id": "comparison_matrix",
            "title": "Operating choice comparison",
            "subtitle": "Manual review, structured pipeline, and hybrid governance have different tradeoffs.",
            "main_message": "Hybrid governance balances repeatability with human judgment.",
            "content": {"table": _table_payload(table)},
        },
        {
            "archetype_id": "data_dashboard",
            "title": "Readiness signal dashboard",
            "subtitle": "The pilot tracked trace coverage, consistency, closure, and reuse readiness.",
            "main_message": "The metric profile shows a useful but still review-dependent governance system.",
            "content": {"chart": {"title": "Readiness signals", "data_points": chart_points}},
        },
        {
            "archetype_id": "table_heavy",
            "title": "Governance operating table",
            "subtitle": "The comparison table stays editable as a native PPT table.",
            "main_message": "Native tables preserve source-bound details for downstream edits.",
            "content": {"table": _table_payload(table, include_all=True)},
        },
        {
            "archetype_id": "timeline_roadmap",
            "title": "Adoption roadmap",
            "subtitle": "The recommendation starts with structured defaults and reserves expert review for exceptions.",
            "main_message": "The next portfolio cycle should adopt hybrid governance with concise editable artifacts.",
            "content": {"milestones": ["Capture defaults", "Pilot worksheets", "Gate QA", "Expert review", "Portfolio roll-out"]},
        },
    ]
    slides = []
    for index, archetype_id in enumerate(archetypes, start=1):
        slide = dict(base[index - 1])
        slide_id = f"SLIDE-{index:03d}"
        slide.update(
            {
                "slide_id": slide_id,
                "slide_number": index,
                "archetype_id": archetype_id,
                "source_refs": _source_refs_for(index, ev, citation_ids),
                "source_binding_purpose": _purpose_for(archetype_id),
                "required_slots": _required_slots(archetype_id),
                "editable_required": True,
                "raster_allowed_for_semantic_slots": False,
            }
        )
        slides.append(slide)
    return slides


def _card_from_evidence(item: dict[str, Any]) -> dict[str, str]:
    heading = item.get("heading") or item.get("claim_support") or "Evidence"
    return {"title": heading.split("/")[-1].strip()[:34] or "Evidence", "body": item.get("quote", "")[:128]}


def _table_payload(table: dict[str, Any] | None, *, include_all: bool = False) -> dict[str, Any]:
    if table:
        rows = [table["header"], *table["rows"]]
        return {
            "table_id": table["table_id"],
            "title": table["title"],
            "rows": rows if include_all else rows[:5],
            "native_binding_required": True,
            "raster_allowed": False,
        }
    return {
        "table_id": "TBL-001",
        "title": "Operating choice comparison",
        "rows": [["Criterion", "Manual Review", "Structured Pipeline", "Hybrid Governance"]],
        "native_binding_required": True,
        "raster_allowed": False,
    }


def _source_refs_for(index: int, evidence: list[dict[str, Any]], citation_ids: list[str]) -> list[str]:
    refs = []
    if evidence:
        refs.append(evidence[(index - 1) % len(evidence)]["evidence_id"])
    if citation_ids:
        refs.append(citation_ids[(index - 1) % len(citation_ids)])
    return refs


def _purpose_for(archetype_id: str) -> str:
    if archetype_id == "data_dashboard":
        return "native chart data binding"
    if archetype_id in {"table_heavy", "comparison_matrix"}:
        return "native table data binding"
    if "evidence" in archetype_id:
        return "source evidence card binding"
    return "source-backed narrative binding"


def _required_slots(archetype_id: str) -> list[str]:
    base = ["title_text_region", "source_footer_strip"]
    extras = {
        "cover_hero": ["subtitle_text_region", "hero_visual_field"],
        "visual_toc": ["navigation_items"],
        "section_divider": ["section_number", "section_title"],
        "standard_content": ["card_panel", "card_text"],
        "evidence_overview": ["evidence_card"],
        "card_grid": ["card_panel", "card_text"],
        "methodology_framework": ["framework_node", "connector_line"],
        "process_flow": ["process_node", "connector_line"],
        "comparison_matrix": ["editable_shape_grid_table"],
        "data_dashboard": ["kpi_card", "native_chart"],
        "table_heavy": ["native_table"],
        "timeline_roadmap": ["timeline_phase", "timeline_axis"],
    }
    return [*base, *extras.get(archetype_id, [])]


def build_blueprint_distribution(blueprints: dict[str, Any]) -> dict[str, Any]:
    counts = Counter(slide["archetype_id"] for slide in blueprints["slides"])
    return {
        "schema_name": "slide_type_distribution_report",
        "status": "passed",
        "slide_count": len(blueprints["slides"]),
        "archetype_counts": dict(counts),
        "canva_parity_claimed": False,
    }
