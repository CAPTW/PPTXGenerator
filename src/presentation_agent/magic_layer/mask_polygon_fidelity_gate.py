"""D05 mask and polygon fidelity gate helpers."""

from __future__ import annotations

from typing import Any


def evaluate_mask_polygon_fidelity(reference_reports: list[dict[str, Any]]) -> dict[str, Any]:
    total_layers = sum(item.get("layer_count", 0) for item in reference_reports)
    polygon_layers = sum(item.get("polygon_layer_count", 0) for item in reference_reports)
    rectangular_masks = sum(item.get("rectangular_mask_count", 0) for item in reference_reports)
    status = "limited_bounded" if total_layers and polygon_layers == 0 else "passed"
    return {
        "schema_name": "mask_polygon_fidelity_gate_report",
        "status": status,
        "total_layers_checked": total_layers,
        "polygon_layer_count": polygon_layers,
        "rectangular_mask_count": rectangular_masks,
        "risk_status": "limited_rectangular_masks" if status == "limited_bounded" else "bounded",
        "D06_policy": "D06 may proceed with limited masks only when semantic regions do not depend on precise nonrectangular masks.",
        "reference_summaries": reference_reports,
    }

