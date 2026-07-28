"""System Tesseract OCR adapter for R5 text-first lock smoke inference."""

from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
import time
from io import StringIO
from pathlib import Path
from typing import Any

from src.presentation_agent.magic_layer.segmentation_stack.adapter_runtime import sha256_file, sha256_json


COMMON_TESSERACT_PATHS = [
    Path("C:/Program Files/Tesseract-OCR/tesseract.exe"),
    Path("C:/Program Files (x86)/Tesseract-OCR/tesseract.exe"),
]


class SystemTesseractAdapter:
    adapter_id = "system_tesseract"
    display_name = "System Tesseract OCR"
    adapter_group = "text_first_lock"
    required_packages: list[str] = []
    required_binaries = ["tesseract"]
    required_model_paths: list[str] = []

    def detect_availability(self, config: dict[str, Any]) -> dict[str, Any]:
        if not config.get("enabled", False):
            return self._availability("unavailable_disabled", None)
        binary = _resolve_binary(config.get("binary_path"))
        if not binary:
            return self._availability("unavailable_missing_binary", None)
        version = _version(binary)
        return self._availability("available", {"path": binary, "version": version})

    def run(self, reference_image_path: Path, output_dir: Path, config: dict[str, Any]) -> dict[str, Any]:
        output_dir.mkdir(parents=True, exist_ok=True)
        availability = self.detect_availability(config)
        if availability["status"] != "available":
            return _unavailable(self.adapter_id, self.adapter_group, availability["status"], output_dir)
        binary = availability["binary_evidence"]["path"]
        language = config.get("language") or "eng"
        min_confidence = float(config.get("min_confidence", 0.2))
        command = [binary, str(reference_image_path), "stdout", "-l", language, "--psm", "6", "tsv"]
        started = time.monotonic()
        completed = subprocess.run(command, capture_output=True, text=True, timeout=int(config.get("timeout_seconds", 30)), check=False)
        runtime = round(time.monotonic() - started, 4)
        stdout_path = output_dir / "adapter_stdout_stderr.json"
        stdout_path.write_text(
            json.dumps({"command": command, "stdout": completed.stdout, "stderr": completed.stderr, "returncode": completed.returncode}, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        if completed.returncode != 0:
            return _failed(self.adapter_id, self.adapter_group, "failed_runtime", completed.stderr, output_dir, runtime)
        width, height = _image_size(reference_image_path)
        regions = parse_tesseract_tsv(completed.stdout, image_width=width, image_height=height, min_confidence=min_confidence)
        input_sha = sha256_file(reference_image_path)
        proposals = []
        for index, region in enumerate(regions, start=1):
            proposals.append(
                {
                    "proposal_id": f"real_system_tesseract_text_{index:03d}",
                    "source_adapter": self.adapter_id,
                    "source_type": "real_model",
                    "adapter_status": "produced_proposals",
                    "real_inference_ran": True,
                    "bbox_px": region["bbox_px"],
                    "bbox_norm": region["bbox_norm"],
                    "confidence": region["confidence"],
                    "role_candidates": [{"role": "body_text_region", "confidence": region["confidence"]}],
                    "content_bearing_candidate": True,
                    "semantic_candidate": True,
                    "raster_allowed_candidate": False,
                    "editability_target_candidate": "ppt_text_box",
                    "recognized_text": region["recognized_text"],
                    "evidence": [{"type": "tesseract_tsv", "binary": binary, "version": availability["binary_evidence"].get("version")}],
                    "warnings": [],
                    "gate_eligible": True,
                }
            )
        payload = {"adapter_id": self.adapter_id, "proposals": proposals}
        proposal_sha = sha256_json(payload)
        for proposal in proposals:
            proposal["adapter_runtime_evidence"] = {
                "adapter_id": self.adapter_id,
                "real_inference_ran": True,
                "input_image_sha256": input_sha,
                "output_proposal_sha256": proposal_sha,
                "package_or_binary_evidence": availability["binary_evidence"],
                "model_weight_or_engine_evidence": {"system_binary": binary, "version": availability["binary_evidence"].get("version")},
                "proposal_count": len(proposals),
                "runtime_errors": [],
            }
        proposals_path = output_dir / "real_text_region_ledger.json"
        proposals_path.write_text(json.dumps({"regions": proposals}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return {
            "adapter_id": self.adapter_id,
            "adapter_status": "produced_proposals" if proposals else "produced_no_proposals",
            "source_type": "real_model",
            "real_inference_ran": True,
            "input_image_sha256": input_sha,
            "proposal_count": len(proposals),
            "output_proposal_sha256": proposal_sha if proposals else None,
            "package_or_binary_evidence": availability["binary_evidence"],
            "model_weight_or_engine_evidence": {"system_binary": binary},
            "runtime_seconds": runtime,
            "device": "system_binary",
            "stdout_ref": str(stdout_path),
            "stderr_ref": str(stdout_path),
            "warnings": [],
            "errors": [] if proposals else ["tesseract_produced_no_text_boxes"],
            "proposals_path": str(proposals_path),
            "proposals": proposals,
            "canva_parity_claimed": False,
        }

    def _availability(self, status: str, binary_evidence: dict[str, Any] | None) -> dict[str, Any]:
        return {"adapter_id": self.adapter_id, "status": status, "binary_evidence": binary_evidence, "canva_parity_claimed": False}


def parse_tesseract_tsv(tsv: str, *, image_width: int, image_height: int, min_confidence: float) -> list[dict[str, Any]]:
    rows = csv.DictReader(StringIO(tsv), delimiter="\t")
    regions = []
    for row in rows:
        text = (row.get("text") or "").strip()
        if not text:
            continue
        try:
            conf = float(row.get("conf", "-1"))
        except ValueError:
            conf = -1
        normalized_conf = conf / 100.0 if conf > 1 else conf
        if normalized_conf < min_confidence:
            continue
        left = int(float(row.get("left", 0)))
        top = int(float(row.get("top", 0)))
        width = max(1, int(float(row.get("width", 1))))
        height = max(1, int(float(row.get("height", 1))))
        regions.append(
            {
                "recognized_text": text,
                "confidence": round(normalized_conf, 4),
                "bbox_px": {"x": left, "y": top, "w": width, "h": height},
                "bbox_norm": {
                    "x": round(left / image_width, 6),
                    "y": round(top / image_height, 6),
                    "w": round(width / image_width, 6),
                    "h": round(height / image_height, 6),
                },
            }
        )
    return regions


def _resolve_binary(configured: str | None) -> str | None:
    if configured:
        expanded = os.path.expandvars(os.path.expanduser(configured))
        if Path(expanded).is_file():
            return str(Path(expanded))
    path = shutil.which("tesseract") or shutil.which("tesseract.exe")
    if path:
        return path
    return next((str(path) for path in COMMON_TESSERACT_PATHS if path.is_file()), None)


def _version(binary: str) -> str | None:
    try:
        completed = subprocess.run([binary, "--version"], capture_output=True, text=True, timeout=10, check=False)
    except Exception:
        return None
    return (completed.stdout or completed.stderr).splitlines()[0] if (completed.stdout or completed.stderr) else None


def _image_size(path: Path) -> tuple[int, int]:
    try:
        from PIL import Image

        with Image.open(path) as image:
            return image.width, image.height
    except Exception:
        return 1600, 900


def _unavailable(adapter_id: str, group: str, reason: str, output_dir: Path) -> dict[str, Any]:
    (output_dir / "adapter_stdout_stderr.json").write_text(json.dumps({"stdout": "", "stderr": reason}, indent=2) + "\n", encoding="utf-8")
    return {"adapter_id": adapter_id, "adapter_status": reason, "group": group, "proposals": [], "errors": [reason], "real_inference_ran": False, "canva_parity_claimed": False}


def _failed(adapter_id: str, group: str, status: str, error: str, output_dir: Path, runtime: float) -> dict[str, Any]:
    return {"adapter_id": adapter_id, "adapter_status": status, "group": group, "proposals": [], "errors": [error], "runtime_seconds": runtime, "real_inference_ran": False, "canva_parity_claimed": False}
