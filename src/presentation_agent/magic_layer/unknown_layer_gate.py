"""D05 unknown-layer policy gate helpers."""

from __future__ import annotations

from typing import Any


def evaluate_unknown_layers(manifest: dict[str, Any]) -> dict[str, Any]:
    unknowns = [layer for layer in manifest.get("layers") or [] if layer.get("layer_type") == "unknown" or layer.get("unknown_disposition") not in {None, "not_unknown"}]
    content_unknowns = [layer for layer in unknowns if layer.get("content_bearing")]
    silently_passed = [layer for layer in unknowns if not layer.get("unknown_disposition")]
    return {
        "schema_name": "unknown_layer_report_d05",
        "reference_id": manifest.get("reference_id"),
        "status": "passed" if not content_unknowns and not silently_passed else "failed",
        "unknown_layer_count": len(unknowns),
        "content_bearing_unknown_layer_count": len(content_unknowns),
        "silently_passed_unknown_layer_count": len(silently_passed),
        "unknown_layers": [
            {
                "layer_id": layer.get("layer_id"),
                "content_bearing": layer.get("content_bearing"),
                "unknown_disposition": layer.get("unknown_disposition"),
                "bbox_norm": layer.get("bbox_norm"),
            }
            for layer in unknowns
        ],
    }


def build_unknown_layer_gate_report(per_reference_reports: list[dict[str, Any]]) -> dict[str, Any]:
    content_unknowns = sum(item.get("content_bearing_unknown_layer_count", 0) for item in per_reference_reports)
    silent = sum(item.get("silently_passed_unknown_layer_count", 0) for item in per_reference_reports)
    return {
        "schema_name": "unknown_layer_gate_report",
        "status": "passed" if content_unknowns == 0 and silent == 0 else "failed",
        "content_bearing_unknown_layer_count": content_unknowns,
        "silently_passed_unknown_layer_count": silent,
        "reference_reports": per_reference_reports,
    }

