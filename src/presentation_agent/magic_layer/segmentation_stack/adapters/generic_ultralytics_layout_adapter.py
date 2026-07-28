"""Generic local Ultralytics layout adapter."""

from __future__ import annotations

import importlib.util
import json
import time
from pathlib import Path
from typing import Any

from src.presentation_agent.magic_layer.segmentation_stack.adapter_runtime import sha256_file, sha256_json


class GenericUltralyticsLayoutAdapter:
    adapter_id = "generic_ultralytics_layout"
    display_name = "Generic Ultralytics Layout"
    adapter_group = "layout"
    required_packages = ["ultralytics"]
    required_binaries: list[str] = []
    required_model_paths = ["model_path"]

    def detect_availability(self, config: dict[str, Any]) -> dict[str, Any]:
        if not config.get("enabled", False):
            return {"adapter_id": self.adapter_id, "status": "unavailable_disabled"}
        if importlib.util.find_spec("ultralytics") is None:
            return {"adapter_id": self.adapter_id, "status": "unavailable_missing_package"}
        if not config.get("model_path") or not Path(config["model_path"]).is_file():
            return {"adapter_id": self.adapter_id, "status": "unavailable_missing_weights"}
        return {"adapter_id": self.adapter_id, "status": "available"}

    def run(self, reference_image_path: Path, output_dir: Path, config: dict[str, Any]) -> dict[str, Any]:
        output_dir.mkdir(parents=True, exist_ok=True)
        availability = self.detect_availability(config)
        if availability["status"] != "available":
            (output_dir / "adapter_stdout_stderr.json").write_text(json.dumps({"stderr": availability["status"], "stdout": ""}, indent=2) + "\n", encoding="utf-8")
            return {"adapter_id": self.adapter_id, "adapter_status": availability["status"], "proposals": [], "real_inference_ran": False, "errors": [availability["status"]]}
        from ultralytics import YOLO

        started = time.monotonic()
        model = YOLO(config["model_path"])
        results = model(str(reference_image_path), verbose=False)
        runtime = round(time.monotonic() - started, 4)
        width, height = _image_size(reference_image_path)
        proposals = yolo_results_to_proposals(
            results,
            image_width=width,
            image_height=height,
            adapter_id=self.adapter_id,
            class_role_map=config.get("class_role_map", {}),
            min_confidence=float(config.get("min_confidence", 0.25)),
        )
        proposal_sha = sha256_json({"adapter_id": self.adapter_id, "proposals": proposals})
        input_sha = sha256_file(reference_image_path)
        model_sha = sha256_file(Path(config["model_path"]))
        for proposal in proposals:
            proposal["adapter_runtime_evidence"] = {
                "adapter_id": self.adapter_id,
                "real_inference_ran": True,
                "input_image_sha256": input_sha,
                "output_proposal_sha256": proposal_sha,
                "package_or_binary_evidence": {"package": "ultralytics"},
                "model_weight_or_engine_evidence": {"model_path": config["model_path"], "sha256": model_sha},
                "proposal_count": len(proposals),
                "runtime_errors": [],
            }
        path = output_dir / "real_layout_region_proposals.json"
        path.write_text(json.dumps({"proposals": proposals}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (output_dir / "adapter_stdout_stderr.json").write_text(json.dumps({"stdout": "", "stderr": "", "runtime_seconds": runtime}, indent=2) + "\n", encoding="utf-8")
        return {"adapter_id": self.adapter_id, "adapter_status": "produced_proposals" if proposals else "produced_no_proposals", "proposals": proposals, "real_inference_ran": True, "proposal_count": len(proposals), "output_proposal_sha256": proposal_sha, "runtime_seconds": runtime}


def yolo_results_to_proposals(
    results: list[Any],
    *,
    image_width: int,
    image_height: int,
    adapter_id: str,
    class_role_map: dict[str, str],
    min_confidence: float,
) -> list[dict[str, Any]]:
    proposals = []
    for result in results:
        names = getattr(result, "names", {}) or {}
        boxes = getattr(result, "boxes", []) or []
        for box_index, box in enumerate(boxes, start=1):
            xyxy = _first(getattr(box, "xyxy", [[0, 0, 1, 1]]))
            conf = float(_first(getattr(box, "conf", [0])))
            if conf < min_confidence:
                continue
            cls_index = int(float(_first(getattr(box, "cls", [0]))))
            label = names.get(cls_index, str(cls_index)) if isinstance(names, dict) else str(cls_index)
            role = class_role_map.get(label, "unknown")
            x1, y1, x2, y2 = [float(value) for value in xyxy]
            w = max(1.0, x2 - x1)
            h = max(1.0, y2 - y1)
            proposals.append(
                {
                    "proposal_id": f"real_{adapter_id}_{len(proposals) + 1:03d}",
                    "source_adapter": adapter_id,
                    "source_type": "real_model",
                    "adapter_status": "produced_proposals",
                    "real_inference_ran": True,
                    "bbox_px": {"x": round(x1), "y": round(y1), "w": round(w), "h": round(h)},
                    "bbox_norm": {"x": round(x1 / image_width, 6), "y": round(y1 / image_height, 6), "w": round(w / image_width, 6), "h": round(h / image_height, 6)},
                    "confidence": round(conf, 6),
                    "role_candidates": [{"role": role, "confidence": round(conf, 6), "label": label}],
                    "content_bearing_candidate": role != "decorative_texture",
                    "semantic_candidate": role != "unknown",
                    "raster_allowed_candidate": role in {"hero_visual_field", "replaceable_image_frame", "decorative_texture"},
                    "editability_target_candidate": _target_for_role(role),
                    "evidence": [{"type": "ultralytics_box", "label": label, "class_index": cls_index}],
                    "warnings": [] if role != "unknown" else ["unmapped_class_label"],
                    "gate_eligible": True,
                }
            )
    return proposals


def _first(value: Any) -> Any:
    if hasattr(value, "tolist"):
        value = value.tolist()
    return value[0] if isinstance(value, (list, tuple)) else value


def _target_for_role(role: str) -> str:
    if "text" in role or role == "source_footer_strip":
        return "ppt_text_box"
    if role == "table_region":
        return "native_table"
    if role == "chart_region":
        return "native_chart"
    if role in {"hero_visual_field", "replaceable_image_frame"}:
        return "replaceable_image_frame"
    if role == "icon_region":
        return "svg_vector"
    if role == "unknown":
        return "reject_unknown"
    return "ppt_shape_group"


def _image_size(path: Path) -> tuple[int, int]:
    try:
        from PIL import Image

        with Image.open(path) as image:
            return image.width, image.height
    except Exception:
        return 1600, 900
