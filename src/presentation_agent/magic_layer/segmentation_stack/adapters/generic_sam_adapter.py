from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any


class GenericSAMAdapter:
    adapter_id = "generic_sam"
    display_name = "Generic SAM"
    adapter_group = "masks"
    required_packages = ["segment_anything"]
    required_binaries: list[str] = []
    required_model_paths = ["checkpoint_path"]

    def detect_availability(self, config: dict[str, Any]) -> dict[str, Any]:
        if not config.get("enabled", False):
            return {"adapter_id": self.adapter_id, "status": "unavailable_disabled"}
        if importlib.util.find_spec("segment_anything") is None and importlib.util.find_spec("sam2") is None:
            return {"adapter_id": self.adapter_id, "status": "unavailable_missing_package"}
        if not config.get("checkpoint_path") or not Path(config["checkpoint_path"]).is_file():
            return {"adapter_id": self.adapter_id, "status": "unavailable_missing_weights"}
        return {"adapter_id": self.adapter_id, "status": "available"}

    def run(self, reference_image_path: Path, output_dir: Path, config: dict[str, Any]) -> dict[str, Any]:
        availability = self.detect_availability(config)
        if availability["status"] != "available":
            return {"adapter_id": self.adapter_id, "adapter_status": availability["status"], "proposals": [], "real_inference_ran": False, "errors": [availability["status"]]}
        return {"adapter_id": self.adapter_id, "adapter_status": "unsupported_configuration", "proposals": [], "real_inference_ran": False, "errors": ["sam_requires_real_prompt_boxes"]}
