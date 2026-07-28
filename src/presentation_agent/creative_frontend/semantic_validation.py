"""Cross-artifact semantic validation for the creative front-end contracts."""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from typing import Any


def validate_presentation_architecture_semantics(architecture: dict[str, Any]) -> None:
    modules = architecture["modules"]
    slides = architecture["slides"]
    evidence = architecture["evidence_registry"]
    _require_unique(modules, "module_id", "presentation architecture modules")
    _require_unique(slides, "slide_id", "presentation architecture slides")
    _require_unique(evidence, "evidence_id", "presentation architecture evidence")

    orders = [slide["order"] for slide in slides]
    if orders != list(range(1, len(slides) + 1)):
        raise ValueError("presentation architecture slide order must be contiguous and start at 1")

    module_by_id = {module["module_id"]: module for module in modules}
    evidence_by_id = {item["evidence_id"]: item for item in evidence}
    batch_by_id: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    assigned_slide_ids: list[str] = []
    global_positions = {slide["slide_id"]: index for index, slide in enumerate(slides)}

    for module in modules:
        module_slide_ids = module["slide_ids"]
        if len(module_slide_ids) != len(set(module_slide_ids)):
            raise ValueError(f"{module['module_id']}: module slide_ids must be unique")
        positions = [global_positions.get(slide_id, -1) for slide_id in module_slide_ids]
        if -1 in positions or positions != list(range(min(positions), max(positions) + 1)):
            raise ValueError(f"{module['module_id']}: module slides must be a contiguous deck run")
        batch_orders = [batch["order"] for batch in module["batches"]]
        if batch_orders != list(range(1, len(batch_orders) + 1)):
            raise ValueError(f"{module['module_id']}: batch order must be contiguous and start at 1")
        module_batch_slide_ids: list[str] = []
        for batch in module["batches"]:
            batch_id = batch["batch_id"]
            if batch_id in batch_by_id:
                raise ValueError(f"duplicate batch_id: {batch_id}")
            batch_by_id[batch_id] = (module, batch)
            batch_positions = [global_positions.get(slide_id, -1) for slide_id in batch["slide_ids"]]
            if -1 in batch_positions or batch_positions != list(range(min(batch_positions), max(batch_positions) + 1)):
                raise ValueError(f"{batch_id}: batch slides must be contiguous in deck order")
            module_batch_slide_ids.extend(batch["slide_ids"])
        if module_batch_slide_ids != module_slide_ids:
            raise ValueError(f"{module['module_id']}: batches must cover module slides exactly and in order")
        assigned_slide_ids.extend(module_slide_ids)

    if assigned_slide_ids != [slide["slide_id"] for slide in slides]:
        raise ValueError("modules must cover every architecture slide exactly once and in deck order")

    evidence_slides: dict[str, set[str]] = defaultdict(set)
    for slide in slides:
        module = module_by_id.get(slide["module_id"])
        batch_context = batch_by_id.get(slide["batch_id"])
        if module is None or slide["slide_id"] not in module["slide_ids"]:
            raise ValueError(f"{slide['slide_id']}: module reference is inconsistent")
        if batch_context is None or batch_context[0]["module_id"] != slide["module_id"] or slide["slide_id"] not in batch_context[1]["slide_ids"]:
            raise ValueError(f"{slide['slide_id']}: batch reference is inconsistent")
        binding_ids = {binding["evidence_id"] for binding in slide["source_bindings"]}
        if binding_ids != set(slide["evidence_ids"]):
            raise ValueError(f"{slide['slide_id']}: evidence_ids and source_bindings must agree")
        for binding in slide["source_bindings"]:
            record = evidence_by_id.get(binding["evidence_id"])
            if record is None:
                raise ValueError(f"{slide['slide_id']}: unknown evidence_id {binding['evidence_id']}")
            if (binding["label"], binding.get("source")) != (record["label"], record.get("source")):
                raise ValueError(f"{slide['slide_id']}: evidence provenance differs from registry for {binding['evidence_id']}")
            evidence_slides[binding["evidence_id"]].add(slide["slide_id"])

    for evidence_id, record in evidence_by_id.items():
        if set(record["slide_ids"]) != evidence_slides.get(evidence_id, set()):
            raise ValueError(f"{evidence_id}: evidence registry slide_ids do not match source bindings")


def validate_creative_template_architecture_semantics(
    creative: dict[str, Any],
    presentation: dict[str, Any],
    editable_template_spec: dict[str, Any],
) -> None:
    if creative["deck_id"] != presentation["deck_id"] or creative["presentation_architecture_id"] != presentation["architecture_id"]:
        raise ValueError("creative template architecture does not reference the supplied presentation architecture")
    weights = creative["fit_policy"]["weights"]
    if not math.isclose(sum(float(value) for value in weights.values()), 1.0, rel_tol=0, abs_tol=1e-9):
        raise ValueError("creative fit weights must sum to 1.0")

    decisions = creative["slide_fit_decisions"]
    _require_unique(decisions, "slide_id", "creative fit decisions")
    expected_slide_ids = [slide["slide_id"] for slide in presentation["slides"]]
    if [decision["slide_id"] for decision in decisions] != expected_slide_ids:
        raise ValueError("creative fit decisions must cover presentation slides exactly and in order")
    layout_by_id = {layout["layout_id"]: layout for layout in editable_template_spec["layouts"]}
    threshold = float(creative["fit_policy"]["pass_threshold"])
    for decision in decisions:
        layout = layout_by_id.get(decision["layout_id"])
        if layout is None and decision["status"] != "blocked":
            raise ValueError(f"{decision['slide_id']}: non-blocked decision references unknown layout")
        if layout is not None and decision["template_family_id"] != str(layout.get("layout_family_id") or "NO_FAMILY"):
            raise ValueError(f"{decision['slide_id']}: decision family does not match selected layout")
        expected_score = round(sum(float(decision["scores"][key]) * float(weights[key]) for key in weights), 4)
        if not math.isclose(float(decision["overall_score"]), expected_score, rel_tol=0, abs_tol=1e-4):
            raise ValueError(f"{decision['slide_id']}: overall fit score does not match weighted component scores")
        if decision["status"] == "pass":
            if float(decision["overall_score"]) < threshold:
                raise ValueError(f"{decision['slide_id']}: pass decision is below threshold")
            if float(decision["scores"]["semantic"]) < 1.0 or float(decision["scores"]["editability"]) < 1.0:
                raise ValueError(f"{decision['slide_id']}: pass decision lacks full semantic/editability coverage")

    direction_by_module = {module["module_id"]: module for module in creative["modules"]}
    if set(direction_by_module) != {module["module_id"] for module in presentation["modules"]}:
        raise ValueError("creative module directions must cover presentation modules exactly")
    for module in presentation["modules"]:
        direction = direction_by_module[module["module_id"]]
        family_by_batch = {item["batch_id"]: item for item in direction["batch_template_families"]}
        expected_batches = {batch["batch_id"] for batch in module["batches"]}
        if set(family_by_batch) != expected_batches:
            raise ValueError(f"{module['module_id']}: creative batch families do not cover module batches")
        for batch_id, family in family_by_batch.items():
            if not set(family["selected_family_ids"]).issubset(set(family["candidate_family_ids"])):
                raise ValueError(f"{batch_id}: selected families must be a subset of candidates")


def validate_sidecar_semantics(
    sidecars: list[dict[str, Any]],
    presentation: dict[str, Any],
    creative: dict[str, Any],
) -> None:
    _require_unique(sidecars, "slide_id", "semantic sidecars")
    sidecar_by_id = {sidecar["slide_id"]: sidecar for sidecar in sidecars}
    expected_slide_ids = [slide["slide_id"] for slide in presentation["slides"]]
    if [sidecar["slide_id"] for sidecar in sidecars] != expected_slide_ids:
        raise ValueError("semantic sidecars must cover presentation slides exactly and in order")
    presentation_slide_by_id = {slide["slide_id"]: slide for slide in presentation["slides"]}
    decision_by_id = {decision["slide_id"]: decision for decision in creative["slide_fit_decisions"]}
    evidence_ids = {record["evidence_id"] for record in presentation["evidence_registry"]}

    for slide_id in expected_slide_ids:
        sidecar = sidecar_by_id[slide_id]
        architecture_slide = presentation_slide_by_id[slide_id]
        decision = decision_by_id[slide_id]
        if (sidecar["module_id"], sidecar["batch_id"]) != (architecture_slide["module_id"], architecture_slide["batch_id"]):
            raise ValueError(f"{slide_id}: sidecar module/batch reference mismatch")
        if (sidecar["layout_id"], sidecar["template_family_id"]) != (decision["layout_id"], decision["template_family_id"]):
            raise ValueError(f"{slide_id}: sidecar layout/family reference mismatch")
        expected_hash = _content_hash(sidecar["canonical_content"], sidecar["source_bindings"])
        if sidecar["content_hash"] != expected_hash:
            raise ValueError(f"{slide_id}: semantic content_hash does not match canonical content")
        native_slots = {item["slot_id"] for item in sidecar["native_required"]}
        raster_slots = {item["slot_id"] for item in sidecar["raster_allowed"]}
        if native_slots & raster_slots:
            raise ValueError(f"{slide_id}: native and raster slot policies conflict")
        for item in sidecar["canonical_content"]:
            if item["kind"] != "image_need" and item["slot_id"] not in native_slots:
                raise ValueError(f"{slide_id}: canonical content slot {item['slot_id']} lacks a native requirement")
        bound_evidence_ids = {evidence_id for binding in sidecar["source_bindings"] for evidence_id in binding["evidence_ids"]}
        if not bound_evidence_ids.issubset(evidence_ids):
            raise ValueError(f"{slide_id}: sidecar references unknown evidence")
        expected_bindings: dict[str, set[str]] = defaultdict(set)
        for binding in architecture_slide["source_bindings"]:
            expected_bindings[binding["slot_id"]].add(binding["evidence_id"])
        actual_bindings = {binding["element"]: set(binding["evidence_ids"]) for binding in sidecar["source_bindings"]}
        if dict(expected_bindings) != actual_bindings:
            raise ValueError(f"{slide_id}: sidecar source bindings differ from presentation architecture")


def _content_hash(content: list[dict[str, Any]], source_bindings: list[dict[str, Any]]) -> str:
    payload = json.dumps(
        {"canonical_content": content, "source_bindings": source_bindings},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _require_unique(items: list[dict[str, Any]], key: str, label: str) -> None:
    values = [str(item[key]) for item in items]
    duplicates = sorted(value for value, count in Counter(values).items() if count > 1)
    if duplicates:
        raise ValueError(f"{label} contain duplicate {key} values: {', '.join(duplicates)}")
