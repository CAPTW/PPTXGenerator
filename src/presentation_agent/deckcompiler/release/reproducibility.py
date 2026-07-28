"""Deterministic semantic comparison for independent Phase 7C demo runs."""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from pathlib import Path
from typing import Any, Mapping

from ..identity import canonical_json_bytes, stable_id
from ..manifest_io import read_json
from .contracts import bind_content_hash


SEMANTIC_FIELDS = (
    "tested_runtime_commit",
    "source_ids",
    "evidence_hashes",
    "plan_hash",
    "blueprint_hash",
    "presentation_architecture_hash",
    "creative_template_architecture_hash",
    "module_ids",
    "batch_ids",
    "slide_ids",
    "sidecar_hashes",
    "visual_target_hashes",
    "evidence_bindings",
    "selected_layouts",
    "pptx_structural_fingerprint",
    "html_structural_fingerprint",
    "logical_delivery_fingerprint",
)
VOLATILE_FIELDS = {
    "run_id",
    "timestamp",
    "created_at",
    "completed_at",
    "temp_path",
    "runtime_root",
    "output_root",
}
_HTML_VOLATILE = (
    re.compile(
        r'(?i)(\b(?:content|data-created-at)\s*=\s*["\'])(?:[^"\']*)(["\'])'
    ),
    re.compile(r'(?i)(\b(?:run[_-]?id|created[_-]?at)\s*[:=]\s*)([^<,\s;]+)'),
)
_ISO_TIMESTAMP = re.compile(
    r"\b20[0-9]{2}-[0-9]{2}-[0-9]{2}T[0-9:.+-]+(?:Z|[+-][0-9:]+)?\b"
)
_HEX64 = re.compile(r"\b[0-9a-f]{64}\b")
_VOLATILE_JSON_KEYS = {
    "archive_sha256",
    "completed_at",
    "created_at",
    "creation_timestamp",
    "demo_run_manifest_sha256",
    "gate_hash",
    "inventory_hash",
    "manifest_hash",
    "output_root",
    "report_hash",
    "run_id",
    "runtime_identity",
    "runtime_root",
    "started_at",
    "timestamp",
}


class ReproducibilityError(RuntimeError):
    """Stable fail-closed semantic-comparison error."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}" if detail else code)


def normalize_volatile_values(text: str) -> str:
    """Remove run-local HTML values while preserving semantic content."""

    normalized = text.replace("\r\n", "\n")
    normalized = _ISO_TIMESTAMP.sub("<timestamp>", normalized)
    for pattern in _HTML_VOLATILE:
        normalized = pattern.sub(r"\1<volatile>\2", normalized)
    return normalized


def _normalize_json(
    value: Any,
    *,
    drop_hashes: bool = False,
    extra_volatile_keys: frozenset[str] = frozenset(),
) -> Any:
    if isinstance(value, dict):
        return {
            key: _normalize_json(
                item,
                drop_hashes=drop_hashes,
                extra_volatile_keys=extra_volatile_keys,
            )
            for key, item in sorted(value.items())
            if key not in _VOLATILE_JSON_KEYS
            and key not in extra_volatile_keys
            and not (
                drop_hashes
                and (
                    key.lower().endswith("hash")
                    or key.lower().endswith("sha256")
                )
            )
        }
    if isinstance(value, list):
        return [
            _normalize_json(
                item,
                drop_hashes=drop_hashes,
                extra_volatile_keys=extra_volatile_keys,
            )
            for item in value
        ]
    if isinstance(value, str):
        return normalize_volatile_values(value)
    return value


def pptx_structural_fingerprint(path: str | Path) -> str:
    """Hash OPC member names and bytes, excluding ZIP timestamps and ordering."""

    source = Path(path)
    if not source.is_file():
        raise ReproducibilityError("DC_REPRO_PPTX_MISSING", str(source))
    try:
        with zipfile.ZipFile(source) as archive:
            rows = []
            for info in archive.infolist():
                member = info.filename.replace("\\", "/")
                if info.is_dir() or member in {
                    "docProps/core.xml",
                    "docProps/custom.xml",
                }:
                    continue
                data = archive.read(info.filename)
                if member.endswith((".xml", ".rels")):
                    try:
                        data = normalize_volatile_values(
                            data.decode("utf-8")
                        ).encode("utf-8")
                    except UnicodeDecodeError:
                        pass
                rows.append(
                    {
                        "path": member,
                        "size": len(data),
                        "sha256": hashlib.sha256(data).hexdigest(),
                    }
                )
    except (OSError, zipfile.BadZipFile) as exc:
        raise ReproducibilityError("DC_REPRO_PPTX_INVALID", str(source)) from exc
    rows.sort(key=lambda row: row["path"])
    return hashlib.sha256(canonical_json_bytes(rows)).hexdigest()


def html_structural_fingerprint(path: str | Path) -> str:
    """Hash normalized HTML semantics without run-local identity attributes."""

    source = Path(path)
    if not source.is_file():
        raise ReproducibilityError("DC_REPRO_HTML_MISSING", str(source))
    normalized = normalize_volatile_values(source.read_text(encoding="utf-8"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _semantic_file_fingerprint(path: Path, relative: str) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pptx":
        return pptx_structural_fingerprint(path)
    if suffix in {".html", ".htm"}:
        return html_structural_fingerprint(path)
    if suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        drop_hashes = relative.startswith("qa/")
        extra_volatile = (
            frozenset({"report_id"}) if relative.startswith("qa/") else frozenset()
        )
        if relative == "provenance/demo_run_manifest.json":
            drop_hashes = True
            extra_volatile = frozenset({"input_hashes", "output_hashes"})
        elif relative == "provenance/semantic_reproducibility_report.json":
            extra_volatile = frozenset({"comparison_id", "run_ids"})
        return hashlib.sha256(
            canonical_json_bytes(
                _normalize_json(
                    payload,
                    drop_hashes=drop_hashes,
                    extra_volatile_keys=extra_volatile,
                )
            )
        ).hexdigest()
    if suffix in {".md", ".txt", ".css", ".js", ".xml", ".yaml", ".yml"}:
        text = normalize_volatile_values(path.read_text(encoding="utf-8"))
        if relative.startswith("devpost/"):
            text = _HEX64.sub("<hash>", text)
        return hashlib.sha256(text.encode("utf-8")).hexdigest()
    if suffix == ".png":
        try:
            from PIL import Image

            with Image.open(path) as image:
                rgba = image.convert("RGBA")
                header = f"{rgba.width}x{rgba.height}:RGBA:".encode()
                return hashlib.sha256(header + rgba.tobytes()).hexdigest()
        except Exception:
            return hashlib.sha256(path.read_bytes()).hexdigest()
    return hashlib.sha256(path.read_bytes()).hexdigest()


def semantic_package_fingerprint(delivery_root: str | Path) -> str:
    """Compare package meaning while tolerating container/metadata byte drift."""

    root = Path(delivery_root)
    rows = []
    for path in sorted(
        (item for item in root.rglob("*") if item.is_file()),
        key=lambda item: item.relative_to(root).as_posix(),
    ):
        relative = path.relative_to(root).as_posix()
        if relative in {"delivery_manifest.json", "release_candidate_gate.json"}:
            continue
        rows.append(
            {
                "path": relative,
                "semantic_fingerprint": _semantic_file_fingerprint(path, relative),
            }
        )
    return hashlib.sha256(canonical_json_bytes(rows)).hexdigest()


def extract_semantic_snapshot(output_root: str | Path) -> dict[str, Any]:
    """Extract the exact Phase 7C cross-run comparison contract."""

    output = Path(output_root)
    phase3 = output / "run" / "phase3"
    delivery = output / "delivery"
    run_manifest = read_json(output / "demo_run_manifest.json")
    phase3_manifest = read_json(phase3 / "deckcompiler_run_manifest.json")
    artifact_hashes = {
        str(row["path"]): str(row["semantic_content_sha256"])
        for row in phase3_manifest.get("artifacts", [])
        if row.get("semantic_content_sha256")
    }

    def artifact_hash(name: str) -> str:
        try:
            return artifact_hashes[name]
        except KeyError as exc:
            raise ReproducibilityError(
                "DC_REPRO_REQUIRED_ARTIFACT_MISSING", name
            ) from exc

    corpus = read_json(phase3 / "source_corpus.json")
    evidence = read_json(phase3 / "evidence_unit_registry.json")
    blueprint = read_json(phase3 / "slide_blueprint_collection.json")
    architecture = read_json(phase3 / "presentation_architecture.json")
    creative = read_json(phase3 / "creative_template_architecture.json")
    target_manifest = read_json(delivery / "visual" / "visual_target_manifest.json")
    delivery_manifest = read_json(delivery / "delivery_manifest.json")
    modules = architecture.get("modules", [])
    slide_rows = architecture.get("slides", [])
    sidecar_hashes: dict[str, str] = {}
    for path in sorted(
        (delivery / "visual" / "semantic_sidecars").glob("*.semantic.json")
    ):
        payload = read_json(path)
        slide_id = str(payload.get("sidecar", {}).get("slide_id"))
        sidecar_hashes[slide_id] = hashlib.sha256(path.read_bytes()).hexdigest()
    visual_target_hashes = {
        str(row["slide_id"]): str(row["sha256"])
        for row in target_manifest.get("targets", [])
    }
    selected_layouts = {
        str(row["slide_id"]): {
            "layout_id": row.get("layout_id"),
            "template_family_id": row.get("template_family_id"),
        }
        for row in creative.get("slide_fit_decisions", [])
    }
    provenance = {
        str(row["path"]): str(row["provenance_classification"])
        for row in delivery_manifest.get("files", [])
    }
    return {
        "run_id": run_manifest["run_id"],
        "timestamp": run_manifest.get("completed_at"),
        "temp_path": str(output),
        "tested_runtime_commit": run_manifest["source_commit"],
        "source_ids": [str(row["source_id"]) for row in corpus.get("sources", [])],
        "evidence_hashes": {
            str(row["evidence_id"]): str(
                row.get("provenance", {}).get("content_sha256")
            )
            for row in evidence.get("evidence_units", [])
        },
        "plan_hash": artifact_hash("presentation_plan.json"),
        "blueprint_hash": artifact_hash("slide_blueprint_collection.json"),
        "presentation_architecture_hash": artifact_hash(
            "presentation_architecture.json"
        ),
        "creative_template_architecture_hash": artifact_hash(
            "creative_template_architecture.json"
        ),
        "module_ids": [str(row["module_id"]) for row in modules],
        "batch_ids": [
            str(batch["batch_id"])
            for module in modules
            for batch in module.get("batches", [])
        ],
        "slide_ids": [str(row["slide_id"]) for row in slide_rows],
        "sidecar_hashes": sidecar_hashes,
        "visual_target_hashes": visual_target_hashes,
        "evidence_bindings": blueprint.get("evidence_bindings", []),
        "selected_layouts": selected_layouts,
        "pptx_structural_fingerprint": pptx_structural_fingerprint(
            delivery / "output" / "pptx_generator_demo.pptx"
        ),
        "html_structural_fingerprint": html_structural_fingerprint(
            delivery / "output" / "html" / "index.html"
        ),
        "logical_delivery_fingerprint": semantic_package_fingerprint(delivery),
        "provenance_classifications": provenance,
    }


def _canonical_semantic(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    missing = [field for field in SEMANTIC_FIELDS if field not in snapshot]
    if missing:
        raise ReproducibilityError(
            "DC_REPRO_REQUIRED_FIELD_MISSING", ",".join(missing)
        )
    return {field: snapshot[field] for field in SEMANTIC_FIELDS}


def compare_semantic_snapshots(
    first: Mapping[str, Any], second: Mapping[str, Any]
) -> dict[str, Any]:
    """Compare two independent runs, ignoring only explicitly volatile fields."""

    first_provenance = first.get("provenance_classifications")
    second_provenance = second.get("provenance_classifications")
    if first_provenance != second_provenance:
        raise ReproducibilityError("DC_REPRO_PROVENANCE_DIVERGENCE")

    left = _canonical_semantic(first)
    right = _canonical_semantic(second)
    field_results = {field: left[field] == right[field] for field in SEMANTIC_FIELDS}
    semantic_hash_fields = tuple(
        field
        for field in SEMANTIC_FIELDS
        if field
        not in {
            "slide_ids",
            "sidecar_hashes",
            "visual_target_hashes",
            "evidence_bindings",
            "pptx_structural_fingerprint",
            "html_structural_fingerprint",
            "logical_delivery_fingerprint",
        }
    )
    mismatch_fields = sorted(
        field for field, matches in field_results.items() if not matches
    )
    report = {
        "schema_name": "semantic_reproducibility_report",
        "schema_version": "1.0.0",
        "comparison_id": stable_id(
            "comparison",
            str(first.get("run_id", "run-a")),
            str(second.get("run_id", "run-b")),
            hashlib.sha256(canonical_json_bytes(left)).hexdigest(),
            hashlib.sha256(canonical_json_bytes(right)).hexdigest(),
        ),
        "run_ids": [
            str(first.get("run_id", "run-a")),
            str(second.get("run_id", "run-b")),
        ],
        "semantic_artifact_hash_maps_equal": all(
            field_results[field] for field in semantic_hash_fields
        ),
        "slide_ids_order_equal": field_results["slide_ids"],
        "sidecar_hashes_equal": field_results["sidecar_hashes"],
        "visual_target_hashes_equal": field_results["visual_target_hashes"],
        "evidence_bindings_equal": field_results["evidence_bindings"],
        "pptx_structural_fingerprint_equal": field_results[
            "pptx_structural_fingerprint"
        ],
        "html_structural_fingerprint_equal": field_results[
            "html_structural_fingerprint"
        ],
        "logical_delivery_fingerprint_equivalent": field_results[
            "logical_delivery_fingerprint"
        ],
        "ignored_volatile_fields": sorted(VOLATILE_FIELDS),
        "mismatch_fields": mismatch_fields,
        "unexplained_divergence_count": len(mismatch_fields),
        "status": "PASS" if not mismatch_fields else "BLOCKED",
    }
    return bind_content_hash(report, "report_hash")


__all__ = [
    "ReproducibilityError",
    "SEMANTIC_FIELDS",
    "VOLATILE_FIELDS",
    "compare_semantic_snapshots",
    "extract_semantic_snapshot",
    "html_structural_fingerprint",
    "normalize_volatile_values",
    "pptx_structural_fingerprint",
    "semantic_package_fingerprint",
]
