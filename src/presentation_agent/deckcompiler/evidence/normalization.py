"""Normalize explicitly labelled source blocks into traceable Evidence Units."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

from ..identity import content_sha256, stable_evidence_id, stable_id
from ..provenance import seal_artifact


NORMALIZATION_VERSION = "deckcompiler-evidence-v1"
LABEL_TYPES = {
    "intent": "intent",
    "instruction": "instruction",
    "constraint": "constraint",
    "definition": "definition",
    "claim": "claim",
    "risk": "claim",
    "process": "process",
    "causal relation": "causal_relation",
    "comparison": "comparison",
    "option": "comparison",
    "statistic": "statistic",
    "table": "table",
    "figure": "figure",
    "methodology": "methodology",
    "result": "result",
    "limitation": "limitation",
    "recommendation": "recommendation",
    "decision criterion": "decision_criterion",
    "contradiction": "contradiction",
}


def build_evidence_registry(
    source_corpus: dict[str, Any],
    source_locator_registry: dict[str, Any],
    *,
    prompt_text: str,
) -> dict[str, Any]:
    source_by_id = {item["source_id"]: item for item in source_corpus["sources"]}
    locators = source_locator_registry["locators"]
    evidence: list[dict[str, Any]] = []
    prompt_source = next(item for item in source_corpus["sources"] if item["source_type"] == "user_prompt")
    prompt_locator = next(item for item in locators if item["source_id"] == prompt_source["source_id"])
    prompt_content = {"text": prompt_text}
    evidence.append(
        _evidence_unit(
            source=prompt_source,
            locator=prompt_locator,
            evidence_type="intent",
            canonical_content=prompt_content,
            factuality_class="instruction",
            documentary=False,
        )
    )

    for locator in locators:
        source = source_by_id[locator["source_id"]]
        if source["source_type"] != "pdf":
            continue
        match = re.match(r"^([A-Za-z ]+):\s+(.+)$", locator["quote"])
        if match is None:
            continue
        label = match.group(1).strip().lower()
        evidence_type = LABEL_TYPES.get(label)
        if evidence_type is None:
            continue
        text = match.group(2).strip()
        canonical_content: dict[str, Any] = {"text": text}
        if evidence_type == "statistic":
            canonical_content["data"] = _statistic_data(text)
        unit = _evidence_unit(
            source=source,
            locator=locator,
            evidence_type=evidence_type,
            canonical_content=canonical_content,
            factuality_class="documentary_fact",
            documentary=True,
        )
        if evidence_type == "recommendation":
            unit["recommendation_origin"] = "documentary_source"
        evidence.append(unit)

    deduplicated = _deduplicate(evidence)
    payload = {
        "schema_name": "phase3_evidence_unit_registry",
        "schema_version": "1.0.0",
        "registry_id": stable_id("registry", [item["evidence_id"] for item in deduplicated]),
        "evidence_units": deduplicated,
        "normalization": {
            "version": NORMALIZATION_VERSION,
            "deduplicated_count": len(evidence) - len(deduplicated),
            "extraction_is_inference": False,
        },
    }
    sealed = seal_artifact(
        payload,
        artifact_type="evidence_unit_registry",
        input_artifact_ids=(
            source_corpus["artifact"]["artifact_id"],
            source_locator_registry["artifact"]["artifact_id"],
        ),
    )
    validate_evidence_graph(sealed, source_corpus, source_locator_registry)
    return sealed


def validate_evidence_graph(
    registry: dict[str, Any],
    source_corpus: dict[str, Any],
    source_locator_registry: dict[str, Any],
) -> None:
    source_ids = {item["source_id"] for item in source_corpus["sources"]}
    locator_by_id = {item["locator_id"]: item for item in source_locator_registry["locators"]}
    evidence_ids = {item["evidence_id"] for item in registry["evidence_units"]}
    if len(evidence_ids) != len(registry["evidence_units"]):
        raise ValueError("DUPLICATE_EVIDENCE_ID: evidence IDs must be unique")
    for item in registry["evidence_units"]:
        source_id = item["source_id"]
        if source_id not in source_ids:
            raise ValueError(f"EVIDENCE_SOURCE_MISMATCH: unknown source {source_id}")
        if item["source_locator"]["source_id"] != source_id:
            raise ValueError("LOCATOR_SOURCE_MISMATCH: embedded locator source differs from evidence source")
        for locator_id in item["source_locator_ids"]:
            locator = locator_by_id.get(locator_id)
            if locator is None:
                raise ValueError(f"INVALID_LOCATOR: unknown locator {locator_id}")
            if locator["source_id"] != source_id:
                raise ValueError("LOCATOR_SOURCE_MISMATCH: registry locator source differs from evidence source")
        for relation in item["relations"]:
            if relation["target_evidence_id"] not in evidence_ids:
                raise ValueError(
                    f"UNKNOWN_EVIDENCE_RELATION: {relation['target_evidence_id']} is not in the evidence registry"
                )


def evidence_coverage(registry: dict[str, Any], source_corpus: dict[str, Any]) -> dict[str, Any]:
    units = registry["evidence_units"]
    type_counts = Counter(item["evidence_type"] for item in units)
    factual_counts = Counter(
        item["source_id"] for item in units if item["factuality_class"] == "documentary_fact"
    )
    source_rows = []
    for source in source_corpus["sources"]:
        source_rows.append(
            {
                "source_id": source["source_id"],
                "source_type": source["source_type"],
                "evidence_count": sum(item["source_id"] == source["source_id"] for item in units),
                "documentary_fact_count": factual_counts[source["source_id"]],
            }
        )
    return {
        "evidence_type_counts": dict(sorted(type_counts.items())),
        "documentary_fact_count": sum(factual_counts.values()),
        "source_contributions": source_rows,
    }


def _evidence_unit(
    *,
    source: dict[str, Any],
    locator: dict[str, Any],
    evidence_type: str,
    canonical_content: dict[str, Any],
    factuality_class: str,
    documentary: bool,
) -> dict[str, Any]:
    stable_locator = {key: value for key, value in locator.items() if key != "locator_id"}
    return {
        "evidence_id": stable_evidence_id(source["source_id"], stable_locator, canonical_content),
        "source_id": source["source_id"],
        "source_locator_ids": [locator["locator_id"]],
        "source_locator": locator,
        "evidence_type": evidence_type,
        "canonical_content": canonical_content,
        "factuality_class": factuality_class,
        "importance": "high" if evidence_type in {"claim", "recommendation", "statistic"} else "medium",
        "confidence": 1.0,
        "visualizable_as": _visualizable_as(evidence_type),
        "relations": [],
        "citation_metadata": {
            "citation_label": (
                f"{source['display_name']}, page {locator['page_number']}"
                if source["source_type"] == "pdf"
                else "User prompt"
            ),
            "repository_authored": True,
            "documentary": documentary,
            "display_locator": (
                f"page {locator['page_number']}, block {locator['block_index']}"
                if source["source_type"] == "pdf"
                else "prompt"
            ),
            "title": source["display_name"],
        },
        "provenance": {
            "extraction_method": "deterministic_label_parser",
            "normalization_version": NORMALIZATION_VERSION,
            "content_sha256": content_sha256(canonical_content),
        },
    }


def _statistic_data(text: str) -> dict[str, Any]:
    match = re.search(r"(?<![A-Za-z])(-?\d+(?:\.\d+)?)\s*([A-Za-z%]+)?", text)
    if match is None:
        return {"value": text, "unit": "unspecified", "context": text}
    raw_value = match.group(1)
    value: int | float = float(raw_value) if "." in raw_value else int(raw_value)
    unit = match.group(2) or ("count" if " of " in text else "unspecified")
    return {"value": value, "unit": unit, "context": text}


def _visualizable_as(evidence_type: str) -> list[str]:
    return {
        "process": ["process", "diagram"],
        "statistic": ["kpi", "chart"],
        "comparison": ["comparison", "table"],
        "table": ["table"],
        "recommendation": ["text", "hero_visual"],
    }.get(evidence_type, ["text"])


def _deduplicate(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for item in items:
        existing = by_id.get(item["evidence_id"])
        if existing is None:
            by_id[item["evidence_id"]] = item
            continue
        existing["source_locator_ids"] = sorted(
            set(existing["source_locator_ids"]) | set(item["source_locator_ids"])
        )
    return sorted(by_id.values(), key=lambda item: item["evidence_id"])


__all__ = ["build_evidence_registry", "evidence_coverage", "validate_evidence_graph"]
