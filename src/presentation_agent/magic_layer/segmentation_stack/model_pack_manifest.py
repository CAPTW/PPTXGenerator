"""Local model pack manifest schema and validation for E01X-R4."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


ADAPTER_GROUPS = {
    "text_first_lock": ["paddleocr_vl", "paddleocr", "easyocr", "tesseract", "florence_ocr_region"],
    "layout": ["doclayout_yolo", "docling_layout", "dit_doclaynet", "yolo_doclayout"],
    "grounding": ["grounding_dino", "florence_od"],
    "masks": ["sam2", "sam_hq", "segment_anything"],
    "layers": ["qwen_image_layered", "layerd", "layerd_birefnet"],
    "matting": ["birefnet", "rmbg"],
    "chart_table": ["table_transformer", "deplot", "paddleocr_vl_chart_table", "docling_tableformer"],
}


ENTRY_FIELDS = [
    "adapter_id",
    "enabled",
    "package_names",
    "model_id",
    "model_dir",
    "checkpoint_path",
    "config_path",
    "processor_path",
    "tokenizer_path",
    "device",
    "precision",
    "local_files_only",
    "allow_download",
    "expected_outputs",
    "notes",
]


def manifest_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "E01X-R4 Local Model Pack Manifest",
        "type": "object",
        "required": ["schema_name", "schema_version", "adapter_groups"],
        "properties": {
            "schema_name": {"const": "e01x_r4_local_model_pack_manifest"},
            "schema_version": {"type": "string"},
            "adapter_groups": {"type": "object"},
        },
        "additionalProperties": True,
    }


def default_manifest_template() -> dict[str, Any]:
    return {
        "schema_name": "e01x_r4_local_model_pack_manifest",
        "schema_version": "1.0",
        "adapter_groups": {
            group: [_entry_template(adapter_id) for adapter_id in adapter_ids]
            for group, adapter_ids in ADAPTER_GROUPS.items()
        },
        "canva_parity_claimed": False,
    }


def load_model_pack_manifest(path: str | Path | None = None) -> dict[str, Any]:
    manifest_path = Path(path or os.environ.get("ML_LOCAL_MODEL_PACK_MANIFEST", ""))
    if str(manifest_path) and manifest_path.is_file():
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    return default_manifest_template()


def validate_model_pack_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    for field in manifest_schema()["required"]:
        if field not in manifest:
            raise ValueError(f"manifest missing required field: {field}")
    groups = manifest.get("adapter_groups")
    if not isinstance(groups, dict):
        raise ValueError("adapter_groups must be an object")
    errors: list[dict[str, Any]] = []
    entries = 0
    enabled = 0
    for group, group_entries in groups.items():
        if group not in ADAPTER_GROUPS:
            errors.append({"code": "unknown_group", "group": group})
            continue
        if not isinstance(group_entries, list):
            errors.append({"code": "group_not_list", "group": group})
            continue
        for index, entry in enumerate(group_entries):
            entries += 1
            if not isinstance(entry, dict):
                errors.append({"code": "entry_not_object", "group": group, "index": index})
                continue
            if not entry.get("adapter_id"):
                raise ValueError(f"adapter_id missing for {group}[{index}]")
            if entry.get("adapter_id") not in ADAPTER_GROUPS[group]:
                errors.append({"code": "adapter_not_allowed_in_group", "group": group, "adapter_id": entry.get("adapter_id")})
            if bool(entry.get("enabled")):
                enabled += 1
            if "package_names" in entry and not isinstance(entry["package_names"], list):
                errors.append({"code": "package_names_not_list", "group": group, "adapter_id": entry.get("adapter_id")})
    return {
        "schema_name": "model_pack_manifest_validation_report",
        "status": "passed" if not errors else "failed",
        "entry_count": entries,
        "enabled_entry_count": enabled,
        "errors": errors,
        "canva_parity_claimed": False,
    }


def write_manifest_schema_and_example(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "local_model_pack_manifest.schema.json").write_text(
        json.dumps(manifest_schema(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "local_model_pack_manifest.example.json").write_text(
        json.dumps(default_manifest_template(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def r5_model_pack_manifest_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "E01X-R5 Local Model Pack Manifest",
        "type": "object",
        "required": [
            "manifest_version",
            "created_for",
            "repo_root_relative",
            "device_default",
            "local_files_only_default",
            "allow_download_default",
            "adapters",
        ],
        "properties": {
            "manifest_version": {"const": "r5.v1"},
            "created_for": {"const": "magic_layer_e01x_r5"},
            "repo_root_relative": {"type": "boolean"},
            "device_default": {"enum": ["auto", "cpu", "cuda", "mps"]},
            "local_files_only_default": {"type": "boolean"},
            "allow_download_default": {"type": "boolean"},
            "adapters": {"type": "object"},
        },
        "additionalProperties": True,
    }


def r5_minimal_cpu_manifest() -> dict[str, Any]:
    return {
        "manifest_version": "r5.v1",
        "created_for": "magic_layer_e01x_r5",
        "repo_root_relative": True,
        "device_default": "auto",
        "local_files_only_default": True,
        "allow_download_default": False,
        "adapters": {
            "text_first_lock": [
                {
                    "adapter_id": "system_tesseract",
                    "enabled": True,
                    "binary_path": "${ML_TESSERACT_CMD}",
                    "language": "eng",
                    "min_confidence": 0.20,
                }
            ],
            "layout": [
                {
                    "adapter_id": "generic_ultralytics_layout",
                    "enabled": True,
                    "model_path": "models/doclayout/doclayout_yolo.pt",
                    "package_names": ["ultralytics"],
                    "device": "auto",
                    "class_role_map": {
                        "Title": "title_text_region",
                        "Text": "body_text_region",
                        "Table": "table_region",
                        "Figure": "hero_visual_field",
                        "Picture": "hero_visual_field",
                        "Footer": "source_footer_strip",
                        "Caption": "body_text_region",
                        "List": "body_text_region",
                        "Chart": "chart_region",
                        "Card": "card_panel",
                    },
                    "min_confidence": 0.25,
                    "local_files_only": True,
                    "allow_download": False,
                }
            ],
            "object_detection": [
                {
                    "adapter_id": "generic_transformers_object_detection",
                    "enabled": False,
                    "model_dir": "models/layout/transformers_od_model",
                    "processor_dir": "models/layout/transformers_od_model",
                    "package_names": ["torch", "transformers"],
                    "device": "auto",
                    "class_role_map": {
                        "Title": "title_text_region",
                        "Text": "body_text_region",
                        "Table": "table_region",
                        "Picture": "hero_visual_field",
                        "Page-footer": "source_footer_strip",
                        "Figure": "hero_visual_field",
                        "Caption": "body_text_region",
                    },
                    "min_confidence": 0.25,
                    "local_files_only": True,
                    "allow_download": False,
                }
            ],
            "masks": [
                {
                    "adapter_id": "generic_sam",
                    "enabled": False,
                    "checkpoint_path": "models/sam/sam_vit_b.pth",
                    "model_type": "vit_b",
                    "package_names": ["torch", "segment_anything"],
                    "device": "auto",
                    "local_files_only": True,
                    "allow_download": False,
                }
            ],
        },
        "canva_parity_claimed": False,
    }


def r5_gpu_manifest() -> dict[str, Any]:
    manifest = r5_minimal_cpu_manifest()
    manifest["device_default"] = "cuda"
    manifest["adapters"]["object_detection"][0]["enabled"] = True
    manifest["adapters"]["masks"][0]["enabled"] = True
    manifest["adapters"]["layout"][0]["device"] = "cuda"
    manifest["adapters"]["object_detection"][0]["device"] = "cuda"
    manifest["adapters"]["masks"][0]["device"] = "cuda"
    return manifest


def validate_r5_model_pack_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    for field in r5_model_pack_manifest_schema()["required"]:
        if field not in manifest:
            raise ValueError(f"manifest missing required field: {field}")
    adapters = manifest.get("adapters")
    if not isinstance(adapters, dict):
        raise ValueError("adapters must be an object")
    errors: list[dict[str, Any]] = []
    entry_count = 0
    enabled_count = 0
    for group, entries in adapters.items():
        if group not in {"text_first_lock", "layout", "object_detection", "masks"}:
            errors.append({"code": "unknown_adapter_group", "group": group})
            continue
        if not isinstance(entries, list):
            errors.append({"code": "adapter_group_not_list", "group": group})
            continue
        for index, entry in enumerate(entries):
            entry_count += 1
            if not isinstance(entry, dict):
                errors.append({"code": "adapter_entry_not_object", "group": group, "index": index})
                continue
            if not entry.get("adapter_id"):
                raise ValueError(f"adapter_id missing for {group}[{index}]")
            if entry.get("enabled"):
                enabled_count += 1
            if entry.get("allow_download", manifest.get("allow_download_default", False)) and manifest.get("allow_download_default") is False:
                errors.append({"code": "entry_download_overrides_manifest_default", "group": group, "adapter_id": entry.get("adapter_id")})
            if "package_names" in entry and not isinstance(entry["package_names"], list):
                errors.append({"code": "package_names_not_list", "group": group, "adapter_id": entry.get("adapter_id")})
    return {
        "schema_name": "r5_model_pack_manifest_validation_report",
        "status": "passed" if not errors else "failed",
        "entry_count": entry_count,
        "enabled_entry_count": enabled_count,
        "errors": errors,
        "canva_parity_claimed": False,
    }


def write_r5_manifest_artifacts(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "local_model_pack_manifest.schema.json").write_text(
        json.dumps(r5_model_pack_manifest_schema(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "local_model_pack_manifest.example.minimal_cpu.json").write_text(
        json.dumps(r5_minimal_cpu_manifest(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "local_model_pack_manifest.example.gpu.json").write_text(
        json.dumps(r5_gpu_manifest(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _entry_template(adapter_id: str) -> dict[str, Any]:
    return {
        "adapter_id": adapter_id,
        "enabled": False,
        "package_names": _default_packages(adapter_id),
        "model_id": None,
        "model_dir": None,
        "checkpoint_path": None,
        "config_path": None,
        "processor_path": None,
        "tokenizer_path": None,
        "device": "auto",
        "precision": "auto",
        "local_files_only": True,
        "allow_download": False,
        "expected_outputs": [],
        "notes": "",
    }


def _default_packages(adapter_id: str) -> list[str]:
    return {
        "paddleocr_vl": ["paddleocr"],
        "paddleocr": ["paddleocr"],
        "easyocr": ["easyocr"],
        "florence_ocr_region": ["transformers"],
        "doclayout_yolo": ["docling"],
        "docling_layout": ["docling"],
        "dit_doclaynet": ["transformers"],
        "yolo_doclayout": ["ultralytics"],
        "grounding_dino": ["groundingdino"],
        "florence_od": ["transformers"],
        "sam2": ["sam2"],
        "sam_hq": ["segment_anything"],
        "segment_anything": ["segment_anything"],
        "qwen_image_layered": ["transformers"],
        "layerd": ["transformers"],
        "layerd_birefnet": ["transformers"],
        "birefnet": ["transformers"],
        "rmbg": ["transformers"],
        "table_transformer": ["transformers"],
        "deplot": ["transformers"],
        "paddleocr_vl_chart_table": ["paddleocr"],
        "docling_tableformer": ["docling"],
        "tesseract": [],
    }.get(adapter_id, [])
