"""Schema and cross-artifact semantic validation for DeckCompiler contracts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from .identity import stable_evidence_id, stable_source_id
from .manifest_io import read_json
from .models import ValidationIssue, ValidationReport
from .provenance import PRODUCER_NAME, semantic_content_sha256
from .schemas import SCHEMA_FILES, validator_for


def validate_artifact(
    payload: dict[str, Any],
    *,
    schema_name: str | None = None,
    artifact_path: str | Path | None = None,
) -> ValidationReport:
    resolved_schema = schema_name or str(payload.get("schema_name") or "")
    display_path = str(artifact_path) if artifact_path is not None else None
    if resolved_schema not in SCHEMA_FILES:
        return _report(
            resolved_schema or "unknown",
            display_path,
            [_issue("UNKNOWN_SCHEMA", f"unknown DeckCompiler schema: {resolved_schema or '<missing>'}", resolved_schema or "unknown", display_path)],
        )

    issues: list[ValidationIssue] = []
    validator = validator_for(resolved_schema)
    for error in sorted(validator.iter_errors(payload), key=lambda item: (list(item.absolute_path), item.message)):
        issues.append(
            _issue(
                "SCHEMA_VALIDATION_ERROR",
                error.message,
                resolved_schema,
                display_path,
                _json_path(error.absolute_path),
            )
        )
    if not issues:
        issues.extend(_semantic_issues(resolved_schema, payload, display_path))
    return _report(resolved_schema, display_path, issues)


def validate_artifact_graph(artifacts: dict[str, dict[str, Any]]) -> ValidationReport:
    issues: list[ValidationIssue] = []
    for schema_name in sorted(artifacts):
        report = validate_artifact(artifacts[schema_name], schema_name=schema_name)
        issues.extend(report.issues)

    corpus = artifacts.get("source_corpus", {})
    evidence_registry = artifacts.get("evidence_unit_registry", {})
    blueprints = artifacts.get("slide_blueprint_collection", {})
    targets = artifacts.get("visual_target_manifest", {})
    reconstruction = artifacts.get("png_reconstruction_manifest", {})

    source_ids = {item.get("source_id") for item in corpus.get("sources", [])}
    evidence_ids = {item.get("evidence_id") for item in evidence_registry.get("evidence_units", [])}
    slide_ids = {item.get("slide_id") for item in blueprints.get("slides", [])}
    artifact_ids = {
        payload.get("artifact", {}).get("artifact_id")
        for payload in artifacts.values()
        if payload.get("artifact", {}).get("artifact_id")
    }
    for schema_name, payload in sorted(artifacts.items()):
        for input_id in payload.get("artifact", {}).get("provenance", {}).get("input_artifact_ids", []):
            if input_id not in artifact_ids:
                issues.append(
                    _issue(
                        "UNKNOWN_PROVENANCE_INPUT",
                        f"unknown provenance input artifact_id: {input_id}",
                        "artifact_graph",
                        json_path=f"$.{schema_name}.artifact.provenance.input_artifact_ids",
                    )
                )
    for index, item in enumerate(evidence_registry.get("evidence_units", [])):
        source_id = item.get("source_id")
        locator_source_id = item.get("source_locator", {}).get("source_id")
        if source_ids and source_id not in source_ids:
            issues.append(_issue("UNKNOWN_SOURCE_REFERENCE", f"unknown source_id: {source_id}", "artifact_graph", json_path=f"$.evidence_units[{index}].source_id"))
        if source_id != locator_source_id:
            issues.append(_issue("LOCATOR_SOURCE_MISMATCH", "source_id and source_locator.source_id must match", "artifact_graph", json_path=f"$.evidence_units[{index}].source_locator.source_id"))

    for index, binding in enumerate(blueprints.get("evidence_bindings", [])):
        if binding.get("slide_id") not in slide_ids:
            issues.append(_issue("UNKNOWN_SLIDE_REFERENCE", f"unknown slide_id: {binding.get('slide_id')}", "artifact_graph", json_path=f"$.evidence_bindings[{index}].slide_id"))
        for evidence_id in binding.get("evidence_ids", []):
            if evidence_id not in evidence_ids:
                issues.append(_issue("UNKNOWN_EVIDENCE_REFERENCE", f"unknown evidence_id: {evidence_id}", "artifact_graph", json_path=f"$.evidence_bindings[{index}].evidence_ids"))

    target_by_id = {item.get("visual_target_id"): item for item in targets.get("targets", [])}
    if slide_ids:
        for index, target in enumerate(targets.get("targets", [])):
            if target.get("slide_id") not in slide_ids:
                issues.append(_issue("UNKNOWN_SLIDE_REFERENCE", f"unknown slide_id: {target.get('slide_id')}", "artifact_graph", json_path=f"$.targets[{index}].slide_id"))
    for index, record in enumerate(reconstruction.get("reconstructions", [])):
        if slide_ids and record.get("slide_id") not in slide_ids:
            issues.append(_issue("UNKNOWN_SLIDE_REFERENCE", f"unknown slide_id: {record.get('slide_id')}", "artifact_graph", json_path=f"$.reconstructions[{index}].slide_id"))
        target = target_by_id.get(record.get("visual_target_id"))
        if target is None:
            issues.append(_issue("UNKNOWN_VISUAL_TARGET_REFERENCE", f"unknown visual_target_id: {record.get('visual_target_id')}", "artifact_graph", json_path=f"$.reconstructions[{index}].visual_target_id"))
            continue
        if target.get("slide_id") != record.get("slide_id"):
            issues.append(_issue("VISUAL_TARGET_SLIDE_MISMATCH", "visual target and reconstruction slide_id must match", "artifact_graph", json_path=f"$.reconstructions[{index}].slide_id"))
        if target.get("sha256") != record.get("target_sha256"):
            issues.append(_issue("VISUAL_TARGET_HASH_MISMATCH", "visual target and reconstruction hashes must match", "artifact_graph", json_path=f"$.reconstructions[{index}].target_sha256"))

    return _report("artifact_graph", None, issues)


def validate_run_directory(run_directory: str | Path) -> ValidationReport:
    root = Path(run_directory)
    manifest_path = root / "deckcompiler_run_manifest.json"
    issues: list[ValidationIssue] = []
    if not manifest_path.is_file():
        return _report("deckcompiler_run", str(root), [_issue("MISSING_RUN_MANIFEST", "deckcompiler_run_manifest.json is required", "deckcompiler_run", str(root))])
    try:
        manifest = read_json(manifest_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return _report("deckcompiler_run", str(root), [_issue("INVALID_JSON", str(exc), "deckcompiler_run", str(manifest_path))])

    manifest_report = validate_artifact(manifest, schema_name="deckcompiler_run_manifest", artifact_path=manifest_path)
    issues.extend(manifest_report.issues)
    artifacts: dict[str, dict[str, Any]] = {}
    root_resolved = root.resolve()
    for index, entry in enumerate(manifest.get("artifacts", [])):
        relative_path = Path(str(entry.get("path", "")))
        artifact_path = (root / relative_path).resolve()
        if not artifact_path.is_relative_to(root_resolved):
            issues.append(_issue("ARTIFACT_PATH_ESCAPE", "artifact path escapes the run directory", "deckcompiler_run", str(relative_path), f"$.artifacts[{index}].path"))
            continue
        if not artifact_path.is_file():
            if entry.get("required", True):
                issues.append(_issue("MISSING_ARTIFACT", f"required artifact is missing: {relative_path.as_posix()}", "deckcompiler_run", str(relative_path), f"$.artifacts[{index}].path"))
            continue
        try:
            payload = read_json(artifact_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            issues.append(_issue("INVALID_JSON", str(exc), "deckcompiler_run", str(relative_path)))
            continue
        artifact_type = str(entry.get("artifact_type", ""))
        artifacts[artifact_type] = payload
        artifact_report = validate_artifact(payload, schema_name=artifact_type, artifact_path=relative_path)
        issues.extend(artifact_report.issues)
        actual_id = payload.get("artifact", {}).get("artifact_id")
        if actual_id != entry.get("artifact_id"):
            issues.append(_issue("ARTIFACT_ID_MISMATCH", f"manifest artifact_id {entry.get('artifact_id')} does not match payload {actual_id}", "deckcompiler_run", str(relative_path), f"$.artifacts[{index}].artifact_id"))

    issues.extend(validate_artifact_graph(artifacts).issues)
    return _report("deckcompiler_run", str(root), issues)


def build_artifact_graph(run_directory: str | Path) -> dict[str, Any]:
    root = Path(run_directory)
    manifest = read_json(root / "deckcompiler_run_manifest.json")
    nodes: list[dict[str, str]] = []
    edges: list[dict[str, str]] = []
    manifest_envelope = manifest["artifact"]
    nodes.append({"artifact_id": manifest_envelope["artifact_id"], "artifact_type": "deckcompiler_run_manifest", "path": "deckcompiler_run_manifest.json"})
    envelopes: dict[str, dict[str, Any]] = {manifest_envelope["artifact_id"]: manifest_envelope}
    for entry in manifest["artifacts"]:
        path = root / entry["path"]
        if not path.is_file():
            continue
        payload = read_json(path)
        envelope = payload["artifact"]
        envelopes[envelope["artifact_id"]] = envelope
        nodes.append({"artifact_id": envelope["artifact_id"], "artifact_type": entry["artifact_type"], "path": entry["path"]})
    known_ids = set(envelopes)
    for artifact_id, envelope in sorted(envelopes.items()):
        for input_id in envelope["provenance"]["input_artifact_ids"]:
            if input_id in known_ids:
                edges.append({"from": input_id, "to": artifact_id, "relation": "provenance_input"})
    nodes.sort(key=lambda item: item["artifact_id"])
    edges.sort(key=lambda item: (item["from"], item["to"]))
    return {
        "product_name": "PPTX Generator",
        "system_name": "DeckCompiler",
        "system_id": "deckcompiler",
        "run_id": manifest["run_id"],
        "nodes": nodes,
        "edges": edges,
    }


def _semantic_issues(schema_name: str, payload: dict[str, Any], artifact_path: str | None) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    producer_name = payload.get("artifact", {}).get("provenance", {}).get("producer", {}).get("tool_name")
    if producer_name == PRODUCER_NAME:
        expected_hash = payload.get("artifact", {}).get("content_sha256")
        actual_hash = semantic_content_sha256(payload)
        if expected_hash != actual_hash:
            issues.append(
                _issue(
                    "PRODUCER_CONTENT_HASH_MISMATCH",
                    f"artifact content_sha256 {expected_hash or '<missing>'} does not match semantic payload {actual_hash}",
                    schema_name,
                    artifact_path,
                    "$.artifact.content_sha256",
                )
            )
    if schema_name == "source_corpus":
        source_ids = [item["source_id"] for item in payload["sources"]]
        issues.extend(_duplicate_issues(source_ids, "source_id", schema_name, artifact_path, "$.sources"))
        if source_ids != sorted(source_ids):
            issues.append(_issue("NONDETERMINISTIC_ORDER", "sources must be ordered by source_id", schema_name, artifact_path, "$.sources"))
        for index, item in enumerate(payload["sources"]):
            expected_id = stable_source_id(item["source_type"], item["stable_identity"])
            if item["source_id"] != expected_id:
                issues.append(
                    _issue(
                        "NONDETERMINISTIC_SOURCE_ID",
                        f"source_id must equal stable_source_id(source_type, stable_identity): {expected_id}",
                        schema_name,
                        artifact_path,
                        f"$.sources[{index}].source_id",
                    )
                )
        source_id_set = set(source_ids)
        for index, segment in enumerate(payload["normalized_segments"]):
            if segment["source_id"] not in source_id_set:
                issues.append(_issue("UNKNOWN_SOURCE_REFERENCE", f"unknown source_id: {segment['source_id']}", schema_name, artifact_path, f"$.normalized_segments[{index}].source_id"))
    elif schema_name == "evidence_unit_registry":
        ids = [item["evidence_id"] for item in payload["evidence_units"]]
        issues.extend(_duplicate_issues(ids, "evidence_id", schema_name, artifact_path, "$.evidence_units"))
        for index, item in enumerate(payload["evidence_units"]):
            expected_id = stable_evidence_id(item["source_id"], item["source_locator"], item["canonical_content"])
            if item["evidence_id"] != expected_id:
                issues.append(
                    _issue(
                        "NONDETERMINISTIC_EVIDENCE_ID",
                        f"evidence_id must equal stable_evidence_id(source_id, source_locator, canonical_content): {expected_id}",
                        schema_name,
                        artifact_path,
                        f"$.evidence_units[{index}].evidence_id",
                    )
                )
    elif schema_name == "source_locator_registry":
        locator_ids = [item["locator_id"] for item in payload["locators"]]
        issues.extend(_duplicate_issues(locator_ids, "locator_id", schema_name, artifact_path, "$.locators"))
        for index, locator in enumerate(payload["locators"]):
            if locator["locator_type"] == "pdf_text_block":
                if locator["page_number"] != locator["page_index"] + 1:
                    issues.append(
                        _issue(
                            "PDF_PAGE_INDEX_MISMATCH",
                            "page_number must equal zero-based page_index + 1",
                            schema_name,
                            artifact_path,
                            f"$.locators[{index}]",
                        )
                    )
            if locator["text_sha256"] != hashlib.sha256(locator["quote"].encode("utf-8")).hexdigest():
                issues.append(
                    _issue(
                        "LOCATOR_TEXT_HASH_MISMATCH",
                        "locator text_sha256 must bind the normalized quote",
                        schema_name,
                        artifact_path,
                        f"$.locators[{index}].text_sha256",
                    )
                )
    elif schema_name == "phase3_evidence_unit_registry":
        ids = [item["evidence_id"] for item in payload["evidence_units"]]
        issues.extend(_duplicate_issues(ids, "evidence_id", schema_name, artifact_path, "$.evidence_units"))
        for index, item in enumerate(payload["evidence_units"]):
            stable_locator = {key: value for key, value in item["source_locator"].items() if key != "locator_id"}
            expected_id = stable_evidence_id(item["source_id"], stable_locator, item["canonical_content"])
            if item["evidence_id"] != expected_id:
                issues.append(
                    _issue(
                        "NONDETERMINISTIC_EVIDENCE_ID",
                        f"evidence_id does not match canonical source, locator, and content: {expected_id}",
                        schema_name,
                        artifact_path,
                        f"$.evidence_units[{index}].evidence_id",
                    )
                )
    elif schema_name == "slide_blueprint_collection":
        ids = [item["slide_id"] for item in payload["slides"]]
        issues.extend(_duplicate_issues(ids, "slide_id", schema_name, artifact_path, "$.slides"))
    elif schema_name == "visual_target_manifest":
        ids = [item["visual_target_id"] for item in payload["targets"]]
        issues.extend(_duplicate_issues(ids, "visual_target_id", schema_name, artifact_path, "$.targets"))
        for index, target in enumerate(payload["targets"]):
            if target["width"] * 9 != target["height"] * 16:
                issues.append(_issue("INVALID_ASPECT_RATIO", "visual target dimensions must be exactly 16:9", schema_name, artifact_path, f"$.targets[{index}]"))
        if payload["offline_regression_only"]:
            for index, target in enumerate(payload["targets"]):
                if target["generation"]["generation_mode"] != "locked_fixture" or target["generation"]["release_eligible"]:
                    issues.append(_issue("OFFLINE_RELEASE_POLICY_VIOLATION", "offline fixtures must be locked_fixture and release_eligible=false", schema_name, artifact_path, f"$.targets[{index}].generation"))
    elif schema_name == "png_reconstruction_manifest":
        ids = [item["reconstruction_id"] for item in payload["reconstructions"]]
        issues.extend(_duplicate_issues(ids, "reconstruction_id", schema_name, artifact_path, "$.reconstructions"))
    elif schema_name == "deckcompiler_run_manifest":
        types = [item["artifact_type"] for item in payload["artifacts"]]
        issues.extend(_duplicate_issues(types, "artifact_type", schema_name, artifact_path, "$.artifacts"))
    return issues


def _duplicate_issues(values: list[str], field: str, schema_name: str, artifact_path: str | None, json_path: str) -> list[ValidationIssue]:
    duplicates = sorted({value for value in values if values.count(value) > 1})
    return [_issue("DUPLICATE_ID", f"duplicate {field}: {value}", schema_name, artifact_path, json_path) for value in duplicates]


def _issue(code: str, message: str, schema_name: str, artifact_path: str | None = None, json_path: str = "$") -> ValidationIssue:
    return ValidationIssue(code=code, message=message, schema_name=schema_name, artifact_path=artifact_path, json_path=json_path)


def _report(schema_name: str, artifact_path: str | None, issues: Iterable[ValidationIssue]) -> ValidationReport:
    ordered = tuple(sorted(issues, key=lambda item: (item.code, item.artifact_path or "", item.json_path, item.message)))
    return ValidationReport(schema_name=schema_name, artifact_path=artifact_path, issues=ordered)


def _json_path(parts: Iterable[Any]) -> str:
    path = "$"
    for part in parts:
        path += f"[{part}]" if isinstance(part, int) else f".{part}"
    return path


__all__ = ["build_artifact_graph", "validate_artifact", "validate_artifact_graph", "validate_run_directory"]
