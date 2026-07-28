"""Adapter registry and write-target safety for E01X-R5."""

from __future__ import annotations

from pathlib import Path
from typing import Any


R5_OUTPUT_ROOT = Path("design_runs/run_002/outputs/magic_layer_engine_e01x_r5_minimal_model_pack")
PREVIOUS_E01X_ROOT = Path("design_runs/run_002/outputs/magic_layer_engine_e01x_segmentation_stack_benchmark")
PREVIOUS_R4_ROOT = Path("design_runs/run_002/outputs/magic_layer_engine_e01x_r4_real_model_bootstrap")
PROTECTED_CANONICAL_ARTIFACTS = (
    "outputs/editable_template_spec.final.json",
    "outputs/golden_template_masters.pptx",
    "outputs/final_deck_large_premium.pptx",
)


def r5_adapter_registry() -> dict[str, Any]:
    adapters = [
        _entry("system_tesseract", "System Tesseract OCR", "text_first_lock", [], ["tesseract"], []),
        _entry("paddleocr", "PaddleOCR", "text_first_lock", ["paddleocr"], [], []),
        _entry("easyocr", "EasyOCR", "text_first_lock", ["easyocr"], [], []),
        _entry("generic_ultralytics_layout", "Generic Ultralytics Layout", "layout", ["ultralytics"], [], ["model_path"]),
        _entry("generic_transformers_object_detection", "Generic Transformers Object Detection", "object_detection", ["torch", "transformers"], [], ["model_dir", "processor_dir"]),
        _entry("generic_transformers_segmentation", "Generic Transformers Segmentation", "masks", ["torch", "transformers"], [], ["model_dir", "processor_dir"]),
        _entry("generic_sam", "Generic SAM", "masks", ["torch", "segment_anything"], [], ["checkpoint_path"]),
        _entry("docling_layout", "Docling Layout", "layout", ["docling"], [], []),
    ]
    return {"schema_name": "adapter_registry_report", "adapters": adapters, "canva_parity_claimed": False}


def adapter_runtime_plan() -> dict[str, Any]:
    return {
        "schema_name": "adapter_runtime_plan",
        "mode": "smoke_inference",
        "order": [
            "system_tesseract",
            "paddleocr",
            "easyocr",
            "generic_ultralytics_layout",
            "generic_transformers_object_detection",
            "docling_layout",
            "generic_transformers_segmentation",
            "generic_sam",
        ],
        "downloads_default": False,
        "canva_parity_claimed": False,
    }


def adapter_registry_markdown(registry: dict[str, Any]) -> str:
    lines = ["# Adapter Registry", "", "| Adapter | Group | Packages | Binaries | Paths |", "|---|---|---|---|---|"]
    for adapter in registry["adapters"]:
        lines.append(
            f"| `{adapter['adapter_id']}` | `{adapter['adapter_group']}` | `{', '.join(adapter['required_packages']) or '-'}` | `{', '.join(adapter['required_binaries']) or '-'}` | `{', '.join(adapter['required_model_paths']) or '-'}` |"
        )
    lines.append("")
    lines.append("Canva parity claimed: `False`")
    return "\n".join(lines) + "\n"


def adapter_runtime_plan_markdown(plan: dict[str, Any]) -> str:
    lines = ["# Adapter Runtime Plan", "", f"- Mode: `{plan['mode']}`", f"- Downloads default: `{plan['downloads_default']}`", "", "## Order", ""]
    lines.extend(f"- `{item}`" for item in plan["order"])
    lines.append("")
    lines.append("Canva parity claimed: `False`")
    return "\n".join(lines) + "\n"


def protected_and_previous_paths_are_not_targets(output_root: Path) -> dict[str, Any]:
    root = str(output_root).replace("\\", "/")
    write_targets = [
        f"{root}/model_pack",
        f"{root}/doctor",
        f"{root}/setup",
        f"{root}/adapters",
        f"{root}/smoke",
        f"{root}/qa",
        f"{root}/decision",
    ]
    forbidden = {str(PREVIOUS_E01X_ROOT).replace("\\", "/"), str(PREVIOUS_R4_ROOT).replace("\\", "/"), *PROTECTED_CANONICAL_ARTIFACTS}
    violations = [target for target in write_targets if target in forbidden or target.startswith("outputs/")]
    return {
        "schema_name": "r5_write_target_safety_report",
        "status": "passed" if not violations else "failed",
        "write_targets": write_targets,
        "forbidden_targets": sorted(forbidden),
        "violations": violations,
        "canva_parity_claimed": False,
    }


def _entry(adapter_id: str, display_name: str, group: str, packages: list[str], binaries: list[str], paths: list[str]) -> dict[str, Any]:
    return {
        "adapter_id": adapter_id,
        "display_name": display_name,
        "adapter_group": group,
        "required_packages": packages,
        "required_binaries": binaries,
        "required_model_paths": paths,
    }
