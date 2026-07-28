"""Runtime helpers for local adapter smoke inference."""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROTECTED_CANONICAL_ARTIFACTS = (
    "outputs/editable_template_spec.final.json",
    "outputs/golden_template_masters.pptx",
    "outputs/final_deck_large_premium.pptx",
)


@dataclass(frozen=True)
class AdapterRuntimeConfig:
    output_root: Path
    mode: str = "smoke_inference"
    timeout_seconds: int = 30
    device: str = "auto"
    allow_model_downloads: bool = False


@dataclass
class AdapterRunResult:
    adapter_id: str
    adapter_status: str
    source_type: str
    real_inference_ran: bool
    input_image_sha256: str | None
    proposal_count: int
    output_proposal_sha256: str | None
    package_or_binary_evidence: dict[str, Any] | None
    model_weight_or_engine_evidence: dict[str, Any] | None
    runtime_seconds: float
    device: str
    stdout_ref: str | None
    stderr_ref: str | None
    warnings: list[str]
    errors: list[str]
    proposals_path: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "adapter_id": self.adapter_id,
            "adapter_status": self.adapter_status,
            "source_type": self.source_type,
            "real_inference_ran": self.real_inference_ran,
            "input_image_sha256": self.input_image_sha256,
            "proposal_count": self.proposal_count,
            "output_proposal_sha256": self.output_proposal_sha256,
            "package_or_binary_evidence": self.package_or_binary_evidence,
            "model_weight_or_engine_evidence": self.model_weight_or_engine_evidence,
            "runtime_seconds": self.runtime_seconds,
            "device": self.device,
            "stdout_ref": self.stdout_ref,
            "stderr_ref": self.stderr_ref,
            "warnings": self.warnings,
            "errors": self.errors,
            "proposals_path": self.proposals_path,
            "canva_parity_claimed": False,
        }


def python_environment_report() -> dict[str, Any]:
    return {
        "schema_name": "python_environment_report",
        "python_executable": sys.executable,
        "python_version": sys.version,
        "platform": platform.platform(),
        "canva_parity_claimed": False,
    }


def protected_paths_are_not_targets(config: AdapterRuntimeConfig) -> dict[str, Any]:
    root = str(config.output_root).replace("\\", "/")
    write_targets = [
        f"{root}/smoke_tests",
        f"{root}/inventory",
        f"{root}/fusion",
        f"{root}/qa",
        f"{root}/decision",
    ]
    violations = [path for path in write_targets if path in PROTECTED_CANONICAL_ARTIFACTS or path.startswith("outputs/")]
    return {
        "schema_name": "protected_write_target_report",
        "status": "passed" if not violations else "failed",
        "write_targets": write_targets,
        "protected_canonical_artifacts": list(PROTECTED_CANONICAL_ARTIFACTS),
        "violations": violations,
        "canva_parity_claimed": False,
    }


def build_unavailable_runtime_result(adapter_id: str, group: str, reason: str, output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    result = {
        "adapter_id": adapter_id,
        "group": group,
        "status": "unavailable",
        "reason": reason,
        "proposals": [],
        "runtime_evidence": {
            "adapter_id": adapter_id,
            "real_inference_ran": False,
            "input_image_sha256": None,
            "output_proposal_sha256": None,
            "package_or_binary_evidence": None,
            "model_weight_or_engine_evidence": None,
            "proposal_count": 0,
            "runtime_errors": [reason],
        },
        "stdout": "",
        "stderr": "",
        "duration_seconds": 0,
        "canva_parity_claimed": False,
    }
    (output_dir / "adapter_stdout_stderr.json").write_text(json.dumps({"stdout": "", "stderr": "", "reason": reason}, indent=2) + "\n", encoding="utf-8")
    return result


def run_tesseract_smoke(reference_image: Path, output_dir: Path, resolved_entry: dict[str, Any], config: AdapterRuntimeConfig) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    binary_path = (resolved_entry.get("binary_evidence") or {}).get("path") or "tesseract"
    started = time.monotonic()
    command = [binary_path, str(reference_image), "stdout", "--psm", "6"]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=config.timeout_seconds, check=False)
        stdout = completed.stdout
        stderr = completed.stderr
        returncode = completed.returncode
    except Exception as exc:
        stdout = ""
        stderr = str(exc)
        returncode = 1
    duration = round(time.monotonic() - started, 4)
    (output_dir / "adapter_stdout_stderr.json").write_text(
        json.dumps({"command": command, "stdout": stdout, "stderr": stderr, "returncode": returncode}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    proposals = []
    if returncode == 0 and stdout.strip():
        proposals.append(_text_proposal_from_tesseract(stdout, reference_image, resolved_entry))
    proposal_payload = {"adapter_id": "tesseract", "proposal_count": len(proposals), "proposals": proposals}
    proposal_sha = sha256_json(proposal_payload)
    for proposal in proposals:
        proposal["adapter_runtime_evidence"]["output_proposal_sha256"] = proposal_sha
    return {
        "adapter_id": "tesseract",
        "group": "text_first_lock",
        "status": "produced_proposals" if proposals else "failed_runtime",
        "reason": None if proposals else "tesseract_returned_no_text_regions",
        "proposals": proposals,
        "runtime_evidence": {
            "adapter_id": "tesseract",
            "real_inference_ran": returncode == 0,
            "input_image_sha256": sha256_file(reference_image),
            "output_proposal_sha256": proposal_sha if proposals else None,
            "package_or_binary_evidence": resolved_entry.get("binary_evidence"),
            "model_weight_or_engine_evidence": {"system_binary": binary_path},
            "proposal_count": len(proposals),
            "runtime_errors": [] if proposals else ["no_text_regions_or_empty_text"],
        },
        "stdout": stdout,
        "stderr": stderr,
        "duration_seconds": duration,
        "canva_parity_claimed": False,
    }


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_json(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _text_proposal_from_tesseract(stdout: str, reference_image: Path, resolved_entry: dict[str, Any]) -> dict[str, Any]:
    try:
        from PIL import Image

        with Image.open(reference_image) as image:
            width, height = image.size
    except Exception:
        width, height = (1600, 900)
    text = stdout.strip()
    bbox_px = {"x": 0, "y": 0, "w": width, "h": max(1, min(height, int(height * 0.25)))}
    bbox_norm = {"x": 0.0, "y": 0.0, "w": 1.0, "h": round(bbox_px["h"] / height, 6)}
    input_sha = sha256_file(reference_image)
    runtime_evidence = {
        "adapter_id": "tesseract",
        "real_inference_ran": True,
        "input_image_sha256": input_sha,
        "output_proposal_sha256": None,
        "package_or_binary_evidence": resolved_entry.get("binary_evidence"),
        "model_weight_or_engine_evidence": {"system_binary": (resolved_entry.get("binary_evidence") or {}).get("path")},
        "proposal_count": 1,
        "runtime_errors": [],
    }
    return {
        "proposal_id": "real_tesseract_text_region_001",
        "source_adapter": "tesseract",
        "source_type": "real_model",
        "adapter_status": "produced_proposals",
        "bbox_px": bbox_px,
        "bbox_norm": bbox_norm,
        "confidence": 0.5,
        "role_candidates": [{"role": "body_text_region", "confidence": 0.5}],
        "content_bearing_candidate": True,
        "semantic_candidate": True,
        "raster_allowed_candidate": False,
        "editability_target_candidate": "ppt_text_box",
        "recognized_text": text,
        "evidence": [{"type": "system_ocr_stdout", "text_length": len(text)}],
        "warnings": ["tesseract_smoke_has_text_without_precise_boxes"],
        "gate_eligible": True,
        "adapter_runtime_evidence": runtime_evidence,
    }
