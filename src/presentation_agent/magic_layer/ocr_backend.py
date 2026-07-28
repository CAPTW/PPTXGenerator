"""Local OCR backend detection and execution for D02."""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image


@dataclass(frozen=True)
class OCRCapability:
    status: str
    pytesseract_available: bool
    tesseract_executable_available: bool
    backend: str
    reason: str
    expected_confidence_limits: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "pytesseract_available": self.pytesseract_available,
            "tesseract_executable_available": self.tesseract_executable_available,
            "backend": self.backend,
            "reason": self.reason,
            "expected_confidence_limits": self.expected_confidence_limits,
            "remote_ocr_used": False,
            "model_downloaded": False,
        }


class OCRBackend:
    def __init__(self, *, force_unavailable: bool = False) -> None:
        self.force_unavailable = force_unavailable
        self.capability = detect_ocr_capability(force_unavailable=force_unavailable)

    def run_ocr(self, image_path: Path, candidate: dict[str, Any]) -> dict[str, Any]:
        if self.capability.status != "available":
            return _unavailable_result(candidate, self.capability.reason)
        try:
            import pytesseract  # type: ignore

            bbox = [int(v) for v in candidate["bbox_px"]]
            with Image.open(image_path) as image:
                crop = image.convert("RGB").crop((bbox[0], bbox[1], bbox[0] + bbox[2], bbox[1] + bbox[3]))
            data = pytesseract.image_to_data(crop, output_type=pytesseract.Output.DICT, config="--psm 6")
            words: list[str] = []
            confidences: list[float] = []
            boxes: list[dict[str, int]] = []
            for i, raw_text in enumerate(data.get("text") or []):
                text = str(raw_text or "").strip()
                raw_conf = data.get("conf", [])[i]
                try:
                    conf = float(raw_conf)
                except Exception:
                    conf = -1.0
                if not text or conf < 0:
                    continue
                words.append(text)
                confidences.append(conf)
                boxes.append(
                    {
                        "x": bbox[0] + int(data["left"][i]),
                        "y": bbox[1] + int(data["top"][i]),
                        "w": int(data["width"][i]),
                        "h": int(data["height"][i]),
                    }
                )
            raw_text = " ".join(words).strip()
            avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
            return {
                "candidate_id": candidate["candidate_id"],
                "ocr_status": "TEXT_RECOGNIZED" if raw_text else "EMPTY_RESULT",
                "backend": "pytesseract+tesseract",
                "raw_text": raw_text,
                "normalized_text": _normalize_text(raw_text),
                "confidence": round(avg_conf / 100.0, 4),
                "word_boxes": boxes,
                "language": "default",
                "config": "--psm 6",
                "errors": [],
                "final_copy_allowed": False,
            }
        except Exception as exc:  # noqa: BLE001 - OCR failures should be recorded, not crash D02.
            return {
                "candidate_id": candidate["candidate_id"],
                "ocr_status": "OCR_ERROR",
                "backend": "pytesseract+tesseract",
                "raw_text": "",
                "normalized_text": "",
                "confidence": 0.0,
                "word_boxes": [],
                "language": "default",
                "config": "--psm 6",
                "errors": [str(exc)],
                "final_copy_allowed": False,
            }


def detect_ocr_capability(*, force_unavailable: bool = False) -> OCRCapability:
    pytesseract_available = importlib.util.find_spec("pytesseract") is not None
    tesseract_path = shutil.which("tesseract")
    if force_unavailable:
        return OCRCapability(
            status="unavailable",
            pytesseract_available=pytesseract_available,
            tesseract_executable_available=bool(tesseract_path),
            backend="none",
            reason="forced_unavailable_for_test_or_policy",
            expected_confidence_limits="D02 will emit candidates and OCR_UNAVAILABLE without text.",
        )
    if not pytesseract_available:
        return OCRCapability(
            status="unavailable",
            pytesseract_available=False,
            tesseract_executable_available=bool(tesseract_path),
            backend="none",
            reason="pytesseract_not_installed",
            expected_confidence_limits="D02 will emit candidates and OCR_UNAVAILABLE without text.",
        )
    if not tesseract_path:
        return OCRCapability(
            status="unavailable",
            pytesseract_available=True,
            tesseract_executable_available=False,
            backend="none",
            reason="tesseract_executable_not_found",
            expected_confidence_limits="D02 will emit candidates and OCR_UNAVAILABLE without text.",
        )
    version = "unknown"
    try:
        completed = subprocess.run(["tesseract", "--version"], capture_output=True, text=True, timeout=5, check=False)
        version = (completed.stdout or completed.stderr).splitlines()[0] if (completed.stdout or completed.stderr) else "unknown"
    except Exception:
        version = "version_check_failed"
    return OCRCapability(
        status="available",
        pytesseract_available=True,
        tesseract_executable_available=True,
        backend="pytesseract+tesseract",
        reason=version,
        expected_confidence_limits="Generated references often contain stylized placeholder text; OCR is evidence only and not final copy.",
    )


def _unavailable_result(candidate: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        "candidate_id": candidate["candidate_id"],
        "ocr_status": "OCR_UNAVAILABLE",
        "backend": "none",
        "raw_text": "",
        "normalized_text": "",
        "confidence": 0.0,
        "word_boxes": [],
        "language": None,
        "config": None,
        "errors": [reason],
        "final_copy_allowed": False,
    }


def _normalize_text(text: str) -> str:
    return " ".join(text.replace("\n", " ").split()).strip()
