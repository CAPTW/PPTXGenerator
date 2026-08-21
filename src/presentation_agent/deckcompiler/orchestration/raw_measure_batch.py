"""Process a bounded slide batch through the external PPTXlocal/raw detector.

This adapter deliberately imports the external implementation in place.  It
keeps one EasyOCR reader alive for the whole worker batch so a 20-slide run
does not reload OCR weights 20 times.
"""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pipeline-root", type=Path, required=True)
    parser.add_argument("--job-file", type=Path, required=True)
    parser.add_argument("--backend", choices=("easyocr", "tesseract"), required=True)
    parser.add_argument("--deep", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    scripts = (args.pipeline_root / "scripts").resolve()
    detector_path = scripts / "detect_elements.py"
    if not detector_path.is_file():
        raise RuntimeError(f"raw detector is missing: {detector_path}")
    sys.path.insert(0, scripts.as_posix())
    detector = _load_module("pptxlocal_raw_detect_elements", detector_path)
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
