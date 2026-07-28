"""Generic local Transformers object detection adapter."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any


class GenericTransformersObjectDetectionAdapter:
    adapter_id = "generic_transformers_object_detection"
    display_name = "Generic Transformers Object Detection"
    adapter_group = "object_detection"
    required_packages = ["torch", "transformers"]
    required_binaries: list[str] = []
    required_model_paths = ["model_dir", "processor_dir"]

    def detect_availability(self, config: dict[str, Any]) -> dict[str, Any]:
        if not config.get("enabled", False):
            return {"adapter_id": self.adapter_id, "status": "unavailable_disabled"}
        missing = [name for name in self.required_packages if importlib.util.find_spec(name) is None]
        if missing:
            return {"adapter_id": self.adapter_id, "status": "unavailable_missing_package", "missing_packages": missing}
        for field in ("model_dir", "processor_dir"):
            if not config.get(field) or not Path(config[field]).exists():
                return {"adapter_id": self.adapter_id, "status": "unavailable_missing_weights", "missing_path": field}
        return {"adapter_id": self.adapter_id, "status": "available"}

    def validate_processor_support(self, processor: Any) -> dict[str, Any]:
        if not hasattr(processor, "post_process_object_detection"):
            return {
                "adapter_id": self.adapter_id,
                "status": "unsupported_configuration",
                "reason": "processor missing post_process_object_detection",
            }
        return {"adapter_id": self.adapter_id, "status": "available"}

    def run(self, reference_image_path: Path, output_dir: Path, config: dict[str, Any]) -> dict[str, Any]:
        availability = self.detect_availability(config)
        if availability["status"] != "available":
            return {"adapter_id": self.adapter_id, "adapter_status": availability["status"], "proposals": [], "real_inference_ran": False, "errors": [availability["status"]]}
        return {"adapter_id": self.adapter_id, "adapter_status": "unsupported_configuration", "proposals": [], "real_inference_ran": False, "errors": ["runtime_loading_not_enabled_in_smoke_without_explicit_model_support"]}
