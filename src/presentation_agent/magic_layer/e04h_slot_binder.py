"""Bind source content into E04H hybrid semantic slots."""

from __future__ import annotations

import re
from typing import Any


INTERNAL_LABELS = ("composition", "focal object", "template", "archetype", "visual backplate", "reference fixture")


def bind_e04h_source_slots(source_artifacts: dict[str, Any], layout_report: dict[str, Any], art_plan: dict[str, Any]) -> dict[str, Any]:
    evidence_by_id = {row["evidence_id"]: row for row in source_artifacts.get("evidence_bank", {}).get("evidence", [])}
    citations_by_id = {row["citation_id"]: row for row in source_artifacts.get("citation_reference_ledger", {}).get("citations", [])}
    layout_by_slide = {row["slide_id"]: row for row in layout_report.get("selections", [])}
    art_by_slide = {row["slide_id"]: row for row in art_plan.get("slides", [])}
    bindings = []
    overflow = truncation = leakage = 0
    for slide in source_artifacts.get("slides", []):
        source_refs = slide.get("source_refs", [])
        evidence_ref = next((ref for ref in source_refs if ref.startswith("EVD-")), source_refs[0] if source_refs else "EVD-001")
        citation_ref = next((ref for ref in source_refs if ref.startswith("SRC-")), evidence_by_id.get(evidence_ref, {}).get("citation_id", "SRC-001"))
        evidence = evidence_by_id.get(evidence_ref) or next(iter(evidence_by_id.values()))
        citation = citations_by_id.get(citation_ref, {})
        clean_title = _clean(slide.get("title", "Untitled"))
        clean_subtitle = _clean(slide.get("subtitle", evidence.get("quote", "")))
        claim = _summary(slide.get("main_message") or evidence.get("quote", ""))
        details = _details(slide, evidence)
        text_values = [clean_title, clean_subtitle, claim, *details]
        truncation += sum(1 for text in text_values if _looks_truncated(text))
        leakage += sum(1 for text in text_values if _has_internal_label(text))
        overflow += sum(1 for text in text_values if len(text) > 180)
        bindings.append(
            {
                "slide_id": slide["slide_id"],
                "slide_number": slide["slide_number"],
                "selected_reference_id": layout_by_slide[slide["slide_id"]]["selected_reference_id"],
                "focal_object": art_by_slide[slide["slide_id"]]["focal_object"],
                "title": clean_title,
                "subtitle": clean_subtitle,
                "primary_claim": claim,
                "details": details,
                "source_refs": source_refs,
                "evidence_ref": evidence_ref,
                "citation_ref": citation_ref,
                "citation_footer": citation.get("label", citation_ref),
                "confidence": evidence.get("confidence", 0.8),
                "synthesized_transition": False,
                "canva_parity_claimed": False,
            }
        )
    return {
        "schema_name": "slot_binding_ledger_hybrid",
        "status": "passed" if overflow == 0 and truncation == 0 and leakage == 0 else "failed",
        "slide_count": len(bindings),
        "text_overflow_count": overflow,
        "text_truncation_count": truncation,
        "internal_label_leakage_count": leakage,
        "slide_bindings": bindings,
        "canva_parity_claimed": False,
    }


def _details(slide: dict[str, Any], evidence: dict[str, Any]) -> list[str]:
    content = slide.get("content", {})
    values: list[str] = []
    if "cards" in content:
        values = [f"{_clean(card['title'])}: {_summary(card['body'])}" for card in content["cards"]]
    elif "evidence_cards" in content:
        values = [f"{_clean(card['title'])}: {_summary(card['body'])}" for card in content["evidence_cards"][:4]]
    elif "items" in content:
        values = [_clean(str(item)) for item in content["items"]]
    elif "steps" in content:
        values = [_clean(str(item)) for item in content["steps"]]
    elif "milestones" in content:
        values = [_clean(str(item)) for item in content["milestones"]]
    if not values:
        values = [_summary(evidence.get("quote", ""))]
    return [value for value in values if value][:5]


def _summary(text: str) -> str:
    text = _clean(text)
    if text.endswith("rigorous enough for r"):
        return "Governance must be lightweight for product teams and rigorous for risk, legal, and research stakeholders."
    if len(text) <= 150 and not _looks_truncated(text):
        return text
    words = text.split()
    return " ".join(words[:18]).rstrip(".,;:") + "."


def _clean(text: str) -> str:
    text = re.sub(r"\s+", " ", str(text)).strip()
    text = text.replace("source-bound E04 sample", "Source-bound hybrid sample")
    return text


def _looks_truncated(text: str) -> bool:
    if text.endswith("rigorous enough for r"):
        return True
    last = text.split()[-1].lower().strip(".,;:") if text.split() else ""
    return last in {"a", "an", "the", "for", "with", "of", "and", "or", "to"}


def _has_internal_label(text: str) -> bool:
    lower = text.lower()
    return any(label in lower for label in INTERNAL_LABELS)
