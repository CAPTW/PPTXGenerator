"""Process a bounded slide batch through the external PPTXlocal/raw detector.

This adapter deliberately imports the external implementation in place.  It
keeps one EasyOCR reader alive for the whole worker batch so a 20-slide run
does not reload OCR weights 20 times.
"""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import hashlib
import inspect
import json
import math
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pipeline-root", type=Path, required=True)
    parser.add_argument("--job-file", type=Path, required=True)
    parser.add_argument("--backend", choices=("easyocr", "tesseract"), required=True)
    parser.add_argument("--deep", action="store_true")
    parser.add_argument("--preserve-region-candidates", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    scripts = (args.pipeline_root / "scripts").resolve()
    detector_path = scripts / "detect_elements.py"
    if not detector_path.is_file():
        raise RuntimeError(f"raw detector is missing: {detector_path}")
    sys.path.insert(0, scripts.as_posix())
    detector = _load_module("pptxlocal_raw_detect_elements", detector_path)
    capture_options: dict[str, Any] = {}
    if args.preserve_region_candidates:
        try:
            parameter = inspect.signature(detector.build_inventory).parameters.get("preserve_region_candidates")
        except (TypeError, ValueError) as exc:
            raise RuntimeError("cannot confirm raw detector support for preserve_region_candidates") from exc
        if parameter is None or parameter.kind not in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY):
            raise RuntimeError("raw detector does not support preserve_region_candidates")
        capture_options["preserve_region_candidates"] = True
    jobs = _load_jobs(args.job_file)
    _validate_ocr_runtime(args.backend, args.deep)
    reader = detector.get_easyocr_reader() if args.backend == "easyocr" else None
    deep_scan = importlib.import_module("deep_scan") if args.deep else None

    for job in jobs:
        inventory, image = detector.build_inventory(
            job["source_png"],
            backend=args.backend,
            canvas="native",
            reader=reader,
            deep_text=True,
            **capture_options,
        )
        validate_ocr_inventory(inventory)
        validate_region_candidate_evidence(
            inventory, Path(job["source_png"]), required=args.preserve_region_candidates
        )
        if deep_scan is not None:
            inventory["deep"] = [
                deep_scan.scan_region(
                    image,
                    dict(region["bbox_px"], id=region.get("id")),
                )
                for region in inventory.get("regions", [])
                if region.get("kind_hint") in {"photo", "complex_graphic", "gradient"}
                and region.get("bbox_px", {}).get("w", 0) >= 120
            ]
        output = Path(job["inventory_path"])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(inventory, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(
            f"measured slide={job['slide_number']} "
            f"text={len(inventory.get('text_blocks', []))} "
            f"regions={len(inventory.get('regions', []))}"
        )
    return 0


def validate_region_candidate_evidence(
    inventory: dict[str, Any], source: Path, *, required: bool = False
) -> None:
    """Check source-bound evidence without granting semantic or asset authority."""
    if "region_candidate_evidence" not in inventory:
        if required:
            raise ValueError("required region_candidate_evidence is missing from raw detector output")
        return
    evidence = inventory["region_candidate_evidence"]
    if not isinstance(evidence, dict):
        raise ValueError("region_candidate_evidence must be an object")
    if (type(evidence.get("schema_version")) is not int or evidence["schema_version"] != 1
        or evidence.get("status") != "unadjudicated"
        or evidence.get("method") != "detect_regions_without_ocr_mask"):
        raise ValueError("region_candidate_evidence has unsupported schema/status/method")
    authority = evidence.get("authority")
    authority_keys = {"text_removal", "native_admission", "vector_eligibility", "quality_accepted"}
    if (not isinstance(authority, dict) or set(authority) != authority_keys
        or any(value is not False for value in authority.values())):
        raise ValueError("region_candidate_evidence must grant no authority")
    from PIL import Image

    with Image.open(source) as opened:
        image = opened.convert("RGB")
    width, height = image.size
    canvas = evidence.get("canvas_px")
    if (not isinstance(canvas, dict) or set(canvas) != {"w", "h"}
        or any(type(canvas.get(key)) is not int or canvas[key] != expected
               for key, expected in (("w", width), ("h", height)))):
        raise ValueError("region_candidate_evidence must use the native source frame")
    if evidence.get("canvas_rgb_sha256") != hashlib.sha256(image.tobytes()).hexdigest():
        raise ValueError("region_candidate_evidence source RGB hash mismatch")
    area = evidence.get("min_area_fraction")
    if type(area) not in (int, float) or not 0 <= area <= 1:
        raise ValueError("region_candidate_evidence min_area_fraction is invalid")
    notes, candidates = evidence.get("notes"), evidence.get("candidates")
    if not isinstance(notes, list) or any(not isinstance(note, str) for note in notes):
        raise ValueError("region_candidate_evidence notes must be strings")
    if not isinstance(candidates, list):
        raise ValueError("region_candidate_evidence candidates must be an array")
    for index, candidate in enumerate(candidates, 1):
        if not isinstance(candidate, dict) or candidate.get("candidate_id") != f"U{index:02d}":
            raise ValueError("region_candidate_evidence candidate identity is invalid")
        measured = candidate.get("measurement")
        box = measured.get("bbox_px") if isinstance(measured, dict) else None
        if not isinstance(box, dict) or any(
            type(box.get(key)) not in (int, float)
            or (type(box[key]) is float and not math.isfinite(box[key]))
            for key in ("x", "y", "w", "h")
        ):
            raise ValueError("region_candidate_evidence measurement bbox is invalid")
        x, y, w, h = (box[key] for key in ("x", "y", "w", "h"))
        if (x < 0 or y < 0 or w <= 0 or h <= 0 or x > width or y > height
            or w > width or h > height or Fraction(x) + Fraction(w) > width
            or Fraction(y) + Fraction(h) > height):
            raise ValueError("region_candidate_evidence measurement escapes native frame")
        expected_norm = {key: round(value / (width if key in ("x", "w") else height), 4)
                         for key, value in box.items() if key in ("x", "y", "w", "h")}
        normalized = measured.get("bbox_norm")
        if (not isinstance(normalized, dict) or set(normalized) != set(expected_norm)
            or any(type(normalized[key]) not in (int, float) or normalized[key] != expected_norm[key]
                   for key in expected_norm)):
            raise ValueError("region_candidate_evidence normalized bbox mismatch")
        for key in ("overlapping_ocr_mask_ids", "overlapping_masked_region_ids"):
            links = candidate.get(key)
            if not isinstance(links, list) or any(not isinstance(value, str) for value in links):
                raise ValueError(f"region_candidate_evidence {key} must be string IDs")


def validate_ocr_inventory(inventory: dict[str, Any]) -> None:
    """Reject the detector's explicit OCR failures, not successful empty text.

    The external detector can catch image-level OCR errors after the runtime
    check and return region-only measurements. Its emitted warning must not
    become successful measurement evidence or be reused from a cached receipt.
    """
    notes = inventory.get("notes", [])
    if not isinstance(notes, list) or any(not isinstance(note, str) for note in notes):
        raise ValueError("raw detector notes must be an array of strings")
    for note in notes:
        normalized = note.strip().casefold()
        if (
            normalized in {
                "pytesseract not installed — text boxes unavailable",
                "pytesseract not installed",
                "text boxes unavailable",
            }
            or (
                normalized.startswith("ocr failed (")
                and normalized.endswith("); falling back to region detection only")
            )
        ):
            raise ValueError(f"raw OCR measurement failed or is unavailable: {note}")


def _validate_ocr_runtime(backend: str, deep: bool) -> None:
    if backend != "tesseract" and not deep:
        return
    try:
        import pytesseract

        pytesseract.get_tesseract_version()
        languages = set(pytesseract.get_languages(config=""))
    except Exception as exc:
        raise RuntimeError(
            "raw OCR runtime is incomplete: install pytesseract and make "
            "tesseract executable available"
        ) from exc
    missing = {"eng", "kor"} - languages
    if missing:
        raise RuntimeError(
            "raw OCR runtime is missing Tesseract language packs: "
            + ", ".join(sorted(missing))
        )


def _load_jobs(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    jobs = payload.get("jobs") if isinstance(payload, dict) else None
    if not isinstance(jobs, list) or not jobs:
        raise ValueError("raw measurement job file must contain a non-empty jobs array")
    return jobs


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load external raw detector: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


if __name__ == "__main__":
    raise SystemExit(main())
