from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any


class PaddleOCRAdapter:
    adapter_id = "paddleocr"
    display_name = "PaddleOCR"
    adapter_group = "text_first_lock"
    required_packages = ["paddleocr"]
    required_binaries: list[str] = []
    required_model_paths: list[str] = []

    def detect_availability(self, config: dict[str, Any]) -> dict[str, Any]:
        if not config.get("enabled", False):
            return {"adapter_id": self.adapter_id, "status": "unavailable_disabled"}
        if importlib.util.find_spec("paddleocr") is None:
            return {"adapter_id": self.adapter_id, "status": "unavailable_missing_package"}
        if config.get("local_files_only", True) and not config.get("model_dir"):
            return {"adapter_id": self.adapter_id, "status": "unavailable_missing_weights", "reason": "model_dir_required_when_downloads_disabled"}
        return {"adapter_id": self.adapter_id, "status": "available"}

    def run(self, reference_image_path: Path, output_dir: Path, config: dict[str, Any]) -> dict[str, Any]:
        availability = self.detect_availability(config)
        if availability["status"] != "available":
            return {"adapter_id": self.adapter_id, "adapter_status": availability["status"], "proposals": [], "real_inference_ran": False, "errors": [availability["status"]]}
        return {"adapter_id": self.adapter_id, "adapter_status": "unsupported_configuration", "proposals": [], "real_inference_ran": False, "errors": ["paddleocr_runtime_not_implemented_for_this_local_pack"]}
