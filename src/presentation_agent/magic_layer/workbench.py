"""Magic Layer decomposition workbench orchestration."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from .crop_mask_extractor import extract_crops_and_masks
from .decomposition_quality import score_decomposition
from .image_asset import read_image_metadata
from .layer_classifier import classify_regions
from .layer_schema_v4 import validate_manifest
from .preview_compositor import write_previews
from .region_detection import detect_regions
from .z_order_estimator import estimate_z_order


class MagicLayerWorkbench:
    def __init__(self, output_root: Path) -> None:
        self.output_root = output_root

    def process_reference(self, image_path: Path, *, reference_id: str, archetype_hint: str = "unknown") -> dict[str, Any]:
        ref_dir = self.output_root / "references" / reference_id
        crops_dir = ref_dir / "crops"
        masks_dir = ref_dir / "masks"
        ref_dir.mkdir(parents=True, exist_ok=True)
        copied_reference = ref_dir / "reference_image.png"
        shutil.copy2(image_path, copied_reference)
        metadata = read_image_metadata(copied_reference)
        proposals = detect_regions(copied_reference, reference_id=reference_id, archetype_hint=archetype_hint)
        layers = classify_regions(
            proposals,
            reference_id=reference_id,
            archetype_hint=archetype_hint,
            image_width=metadata.width,
            image_height=metadata.height,
        )
        layers, z_report = estimate_z_order(layers)
        crop_manifest, mask_manifest, crop_flags = extract_crops_and_masks(copied_reference, layers, crops_dir=crops_dir, masks_dir=masks_dir)
        layer_graph = _build_layer_graph(layers)
        manifest = {
            "schema_name": "layer_manifest_v4",
            "schema_version": "4.0",
            "reference_id": reference_id,
            "archetype_hint": archetype_hint or "unknown",
            "archetype_hint_policy": "optional metadata only; free-form decomposition must not depend on known archetype ids",
            "reference_metadata": metadata.to_dict(),
            "layers": layers,
            "layer_graph": layer_graph,
            "unknown_layer_count": sum(1 for layer in layers if layer["layer_type"] == "unknown"),
            "content_bearing_unknown_layer_count": sum(1 for layer in layers if layer["layer_type"] == "unknown" and layer["content_bearing"]),
            "unknown_policy": "unknown layers must be reported; content-bearing unknown layers block D02 readiness",
            "no_full_slide_crop_accepted": not any(flag["flag"] == "full_slide_crop_rejected" for flag in crop_flags),
        }
        errors = validate_manifest(manifest)
        if errors:
            manifest["validation_errors"] = errors
        quality = score_decomposition(layers, image_width=metadata.width, image_height=metadata.height)
        preview = write_previews(copied_reference, layers, ref_dir)
        bbox_ledger = {
            "schema_name": "object_bbox_ledger",
            "status": "passed",
            "reference_id": reference_id,
            "objects": [
                {
                    "layer_id": layer["layer_id"],
                    "bbox_px": layer["bbox_px"],
                    "bbox_norm": layer["bbox_norm"],
                    "layer_type": layer["layer_type"],
                    "content_bearing": layer["content_bearing"],
                    "confidence": layer["confidence"],
                }
                for layer in layers
            ],
        }
        z_order = {"schema_name": "z_order_estimate", "reference_id": reference_id, "layers": [{"layer_id": layer["layer_id"], "z_order": layer["z_order"], "layer_type": layer["layer_type"], "confidence": layer["confidence"]} for layer in layers], **z_report}
        classification = {"schema_name": "visual_layer_classification", "status": "passed", "reference_id": reference_id, "classifications": [{"layer_id": layer["layer_id"], "layer_type": layer["layer_type"], "semantic_role": layer["semantic_role"], "editability_target": layer["editability_target"], "raster_policy": layer["raster_policy"], "confidence": layer["confidence"]} for layer in layers]}
        unknown_report = {
            "schema_name": "unknown_layer_report",
            "status": "blocking" if manifest["content_bearing_unknown_layer_count"] else "passed",
            "reference_id": reference_id,
            "unknown_layer_count": manifest["unknown_layer_count"],
            "content_bearing_unknown_layer_count": manifest["content_bearing_unknown_layer_count"],
            "unknown_layers": [layer for layer in layers if layer["layer_type"] == "unknown"],
        }
        self._write_json(ref_dir / "reference_metadata.json", metadata.to_dict())
        self._write_json(ref_dir / "layer_manifest_v4.json", manifest)
        self._write_md(ref_dir / "layer_manifest_v4.md", "Layer Manifest V4", [f"- Reference: `{reference_id}`", f"- Layers: {len(layers)}", f"- Unknown layers: {manifest['unknown_layer_count']}", f"- Content-bearing unknown layers: {manifest['content_bearing_unknown_layer_count']}"])
        self._write_json(ref_dir / "object_bbox_ledger.json", bbox_ledger)
        self._write_json(ref_dir / "z_order_estimate.json", z_order)
        self._write_json(ref_dir / "visual_layer_classification.json", classification)
        self._write_json(ref_dir / "crop_manifest.json", crop_manifest)
        self._write_json(ref_dir / "mask_manifest.json", mask_manifest)
        self._write_json(ref_dir / "unknown_layer_report.json", unknown_report)
        self._write_json(ref_dir / "decomposition_quality_report.json", quality)
        self._write_md(ref_dir / "decomposition_quality_report.md", "Decomposition Quality Report", [f"- Status: `{quality['status']}`", f"- Overall score: {quality['overall_score']}", f"- Layer count: {quality['layer_count']}", f"- Content-bearing unknown layers: {quality['content_bearing_unknown_layer_count']}", f"- D02 ready: {str(quality['d02_ready']).lower()}"])
        self._write_json(ref_dir / "preview_composition_report.json", preview)
        self._write_md(ref_dir / "preview_composition_report.md", "Preview Composition Report", ["- Debug preview only; not final PPT output.", f"- Decomposed preview: `{preview['previews']['decomposed_preview']}`", f"- Reference comparison: `{preview['previews']['reference_vs_preview']}`"])
        return {
            "reference_id": reference_id,
            "archetype_hint": archetype_hint,
            "output_dir": str(ref_dir),
            "reference_dir": str(ref_dir),
            "layer_manifest": str(ref_dir / "layer_manifest_v4.json"),
            "manifest_path": str(ref_dir / "layer_manifest_v4.json"),
            "layer_count": len(layers),
            "unknown_layer_count": manifest["unknown_layer_count"],
            "content_bearing_unknown_layer_count": manifest["content_bearing_unknown_layer_count"],
            "quality_status": quality["status"],
            "d02_ready": quality["d02_ready"],
            "manifest_summary": {
                "layer_count": len(layers),
                "crop_count": crop_manifest["crop_count"],
                "mask_count": mask_manifest["mask_count"],
                "unknown_layer_count": manifest["unknown_layer_count"],
                "content_bearing_unknown_layer_count": manifest["content_bearing_unknown_layer_count"],
                "layer_graph_node_count": len(layer_graph["nodes"]),
                "layer_graph_edge_count": len(layer_graph["edges"]),
            },
            "unknown_layer_report": unknown_report,
            "crop_manifest": crop_manifest,
            "quality_report": quality,
        }

    @staticmethod
    def _write_json(path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    @staticmethod
    def _write_md(path: Path, title: str, lines: list[str]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# " + title + "\n\n" + "\n".join(lines) + "\n", encoding="utf-8")


def _build_layer_graph(layers: list[dict[str, Any]]) -> dict[str, Any]:
    nodes = [
        {
            "layer_id": layer["layer_id"],
            "layer_type": layer["layer_type"],
            "semantic_role": layer["semantic_role"],
            "component_identity_candidate": layer.get("component_identity_candidate"),
            "bbox_norm": layer["bbox_norm"],
            "z_order": layer["z_order"],
        }
        for layer in layers
    ]
    edges: list[dict[str, Any]] = []
    ordered = sorted(layers, key=lambda item: item["z_order"])
    for lower, upper in zip(ordered, ordered[1:]):
        edges.append(
            {
                "source_layer_id": lower["layer_id"],
                "target_layer_id": upper["layer_id"],
                "relation": "z_order_before",
                "confidence": min(float(lower["confidence"]), float(upper["confidence"])),
            }
        )
    for index, first in enumerate(layers):
        for second in layers[index + 1 :]:
            overlap = _overlap_ratio(first["bbox_px"], second["bbox_px"])
            if overlap > 0.01:
                edges.append(
                    {
                        "source_layer_id": first["layer_id"],
                        "target_layer_id": second["layer_id"],
                        "relation": "bbox_overlap",
                        "overlap_ratio": round(overlap, 5),
                        "confidence": round(min(float(first["confidence"]), float(second["confidence"])), 4),
                    }
                )
    return {
        "schema_name": "freeform_layer_graph_v1",
        "graph_policy": "independent_of_fixed_archetype_catalog",
        "nodes": nodes,
        "edges": edges,
    }


def _overlap_ratio(first: list[int], second: list[int]) -> float:
    ax, ay, aw, ah = first
    bx, by, bw, bh = second
    ix1 = max(ax, bx)
    iy1 = max(ay, by)
    ix2 = min(ax + aw, bx + bw)
    iy2 = min(ay + ah, by + bh)
    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0
    intersection = (ix2 - ix1) * (iy2 - iy1)
    smaller = min(aw * ah, bw * bh)
    return intersection / smaller if smaller else 0.0
