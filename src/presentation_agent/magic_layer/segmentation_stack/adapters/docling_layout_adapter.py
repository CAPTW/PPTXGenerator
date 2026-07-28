from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any


class DoclingLayoutAdapter:
    adapter_id = "docling_layout"
    display_name = "Docling Layout"
    adapter_group = "layout"
    required_packages = ["docling"]
    required_binaries: list[str] = []
    required_model_paths: list[str] = []

    def detect_availability(self, config: dict[str, Any]) -> dict[str, Any]:
        if not config.get("enabled", False):
            return {"adapter_id": self.adapter_id, "status": "unavailable_disabled"}
        if importlib.util.find_spec("docling") is None and importlib.util.find_spec("docling_core") is None:
            return {"adapter_id": self.adapter_id, "status": "unavailable_missing_package"}
        return {"adapter_id": self.adapter_id, "status": "available"}

    def run(self, reference_image_path: Path, output_dir: Path, config: dict[str, Any]) -> dict[str, Any]:
        availability = self.detect_availability(config)
        if availability["status"] != "available":
            return {"adapter_id": self.adapter_id, "adapter_status": availability["status"], "proposals": [], "real_inference_ran": False, "errors": [availability["status"]]}
        return {"adapter_id": self.adapter_id, "adapter_status": "unsupported_configuration", "proposals": [], "real_inference_ran": False, "errors": ["docling_image_layout_api_not_configured"]}
