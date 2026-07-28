from __future__ import annotations

from pathlib import Path
from typing import Any

from .generic_transformers_object_detection_adapter import GenericTransformersObjectDetectionAdapter


class GenericTransformersSegmentationAdapter(GenericTransformersObjectDetectionAdapter):
    adapter_id = "generic_transformers_segmentation"
    display_name = "Generic Transformers Segmentation"
    adapter_group = "masks"

    def run(self, reference_image_path: Path, output_dir: Path, config: dict[str, Any]) -> dict[str, Any]:
        availability = self.detect_availability(config)
        if availability["status"] != "available":
            return {"adapter_id": self.adapter_id, "adapter_status": availability["status"], "proposals": [], "real_inference_ran": False, "errors": [availability["status"]]}
        return {"adapter_id": self.adapter_id, "adapter_status": "unsupported_configuration", "proposals": [], "real_inference_ran": False, "errors": ["segmentation_postprocess_not_configured"]}
