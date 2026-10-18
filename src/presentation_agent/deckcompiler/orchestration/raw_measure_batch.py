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
    parser.add_argument("--preserve-text-alternatives", action="store_true")
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
    if args.preserve_text_alternatives:
        if args.backend != "easyocr":
            raise RuntimeError("preserve_text_alternatives requires easyocr")
        try:
            parameter = inspect.signature(detector.build_inventory).parameters.get("preserve_text_alternatives")
        except (TypeError, ValueError) as exc:
            raise RuntimeError("cannot confirm raw detector support for preserve_text_alternatives") from exc
        if parameter is None or parameter.kind not in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY):
            raise RuntimeError("raw detector does not support preserve_text_alternatives")
        capture_options["preserve_text_alternatives"] = True
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
        validate_text_alternative_evidence(
            inventory, Path(job["source_png"]), required=args.preserve_text_alternatives
        )
        if "text_alternative_evidence" in inventory and not args.preserve_text_alternatives:
            raise ValueError("text_alternative_evidence requires explicit preserve_text_alternatives mode")
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


TEXT_ALTERNATIVE_COLLECTION = "text_alternative_evidence.observations"
TEXT_ALTERNATIVE_CAPABILITY = "unresolved_text_alternative_assemblies_v1"


def _alternative_digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def validate_text_alternative_evidence(
    inventory: dict[str, Any], source: Path, *, required: bool = False
) -> None:
    """Check declared mapped observations, not OCR truth or historical attestation."""
    if "text_alternative_evidence" not in inventory:
        if required:
            raise ValueError("required text_alternative_evidence is missing")
        return
    validate_ocr_inventory(inventory)
    from PIL import Image
    with Image.open(source) as opened:
        image = opened.convert("RGB")
    _validate_text_alternative_contract(inventory, *image.size,
        rgb_sha256=hashlib.sha256(image.tobytes()).hexdigest())


def _validate_text_alternative_contract(
    inventory: dict[str, Any], width: int, height: int, *, rgb_sha256: str | None = None
) -> None:
    """Independent implementation of the versioned additive producer contract.

    IDs, graph and counts are recomputed from the declared multiset. Assembly
    membership is a bound producer claim, not recoverable historical OCR order.
    Native consumers reject off-frame boxes rather than weakening protection.
    """
    if "text_alternative_evidence" not in inventory:
        return
    e = inventory["text_alternative_evidence"]

    def exact(value, keys, label):
        if not isinstance(value, dict) or set(value) != set(keys):
            raise ValueError(f"text_alternative_evidence {label} has invalid fields")

    def same(value, expected, label):
        if _alternative_digest(value) != _alternative_digest(expected):
            raise ValueError(f"text_alternative_evidence {label} mismatch")

    def array(value, label):
        if not isinstance(value, list):
            raise ValueError(f"text_alternative_evidence {label} must be an array")
        return value

    exact(e, {"schema_version", "status", "method", "backend", "required_consumer_capability",
        "canvas_px", "canvas_rgb_sha256", "duplicate_rule", "observations", "source_lines",
        "edges", "ambiguity_groups", "legacy_assemblies", "coverage", "authority"}, "envelope")
    for key, expected in {"schema_version": 1, "status": "unadjudicated",
        "method": "pre_nms_mapped_ocr_connected_ambiguity_v1", "backend": "easyocr",
        "required_consumer_capability": TEXT_ALTERNATIVE_CAPABILITY,
        "canvas_px": {"w": width, "h": height},
        "duplicate_rule": {"same_line": "_merge_dets_into_lines", "overlap_fraction": 0.5,
            "near_duplicate_ned": 0.3, "exact_text_must_differ": True},
        "authority": {key: False for key in ("text_removal", "native_admission", "vector_eligibility",
            "quality_accepted", "text_selection", "reading_order")}}.items():
        same(e[key], expected, key)
    rgb = e["canvas_rgb_sha256"]
    if (not isinstance(rgb, str) or len(rgb) != 64 or any(c not in "0123456789abcdef" for c in rgb)
        or (rgb_sha256 is not None and rgb != rgb_sha256)):
        raise ValueError("text_alternative_evidence source RGB hash mismatch")
    observations = {}
    for row in array(e["observations"], "observations"):
        exact(row, {"observation_id", "bbox_px", "text", "confidence", "occurrences"}, "observation")
        box = row["bbox_px"]
        exact(box, {"x", "y", "w", "h"}, "observation bbox")
        if any(type(box[k]) is not int for k in box):
            raise ValueError("text alternative mapped boxes must contain integers")
        x, y, w, h = (box[k] for k in ("x", "y", "w", "h"))
        if x < 0 or y < 0 or w <= 0 or h <= 0 or x + w > width or y + h > height:
            raise ValueError("text alternative box escapes native frame")
        if (not isinstance(row["text"], str) or not row["text"].strip()
            or type(row["confidence"]) is not float or not math.isfinite(row["confidence"])
            or type(row["occurrences"]) is not int or row["occurrences"] <= 0):
            raise ValueError("text alternative text/confidence/occurrences is invalid")
        body = {k: row[k] for k in ("bbox_px", "text", "confidence")}
        ident = "O" + _alternative_digest(body)
        if row["observation_id"] != ident or ident in observations:
            raise ValueError("text alternative observation identity mismatch/duplicate")
        observations[ident] = row
    ids = sorted(observations)
    same(e["observations"], [observations[i] for i in ids], "observation ordering")

    # Geometric connectivity is explicitly the declared existing line rule.
    adjacency = {i: set() for i in ids}
    for n, left in enumerate(ids):
        a = observations[left]["bbox_px"]
        for right in ids[n + 1:]:
            b = observations[right]["bbox_px"]
            if (abs((a["y"] + a["h"] / 2) - (b["y"] + b["h"] / 2)) <= 0.5 * min(a["h"], b["h"])
                and max(a["x"], b["x"]) - min(a["x"] + a["w"], b["x"] + b["w"]) < max(a["h"], b["h"])):
                adjacency[left].add(right); adjacency[right].add(left)

    def components(graph):
        remaining = set(graph)
        result = []
        while remaining:
            todo = [min(remaining)]; seen = set()
            while todo:
                node = todo.pop()
                if node not in seen:
                    seen.add(node); todo.extend(graph[node] - seen)
            remaining.difference_update(seen); result.append(sorted(seen))
        return result

    lines = []
    line_by_observation = {}
    for members in components(adjacency):
        ident = "L" + _alternative_digest(members)
        lines.append({"line_id": ident, "observation_ids": members,
            "observation_occurrences": sum(observations[i]["occurrences"] for i in members)})
        line_by_observation.update((i, ident) for i in members)
    lines.sort(key=lambda r: r["line_id"])
    same(e["source_lines"], lines, "source lines/coverage")

    def fuzzy(left, right):
        a, b = left.strip(), right.strip()
        if not a or not b or a in b or b in a:
            return True
        distance = list(range(len(b) + 1))
        for i, char in enumerate(a, 1):
            current = [i]
            for j, other in enumerate(b, 1):
                current.append(min(current[-1] + 1, distance[j] + 1, distance[j - 1] + (char != other)))
            distance = current
        return distance[-1] / max(len(a), len(b)) <= 0.3

    edges = []
    graph = {}
    for line in lines:
        for n, left in enumerate(line["observation_ids"]):
            a = observations[left]; ab = a["bbox_px"]
            for right in line["observation_ids"][n + 1:]:
                b = observations[right]; bb = b["bbox_px"]
                overlap = min(ab["x"] + ab["w"], bb["x"] + bb["w"]) - max(ab["x"], bb["x"])
                if a["text"] != b["text"] and overlap > 0.5 * min(ab["w"], bb["w"]) and fuzzy(a["text"], b["text"]):
                    body = {"a": left, "b": right, "line_id": line["line_id"],
                        "reason": "same_line_overlap_and_fuzzy_duplicate"}
                    edges.append({"edge_id": "E" + _alternative_digest(body), **body})
                    graph.setdefault(left, set()).add(right); graph.setdefault(right, set()).add(left)
    edges.sort(key=lambda r: r["edge_id"])
    same(e["edges"], edges, "complete duplicate edge graph")
    groups = []
    for members in components(graph):
        body = {"observation_ids": members,
            "edge_ids": [edge["edge_id"] for edge in edges if edge["a"] in members and edge["b"] in members],
            "source_line_id": line_by_observation[members[0]]}
        groups.append({"group_id": "A" + _alternative_digest(body), **body,
            "status": "connected_ambiguity", "pairwise_equivalence": False})
    groups.sort(key=lambda r: r["group_id"])
    same(e["ambiguity_groups"], groups, "connected ambiguity groups")
    blocks = {}
    for collection in ("text_blocks", "suppressed_text"):
        for block in array(inventory.get(collection, []), collection):
            if not isinstance(block, dict) or not isinstance(block.get("id"), str) or not block["id"] or block["id"] in blocks:
                raise ValueError("text alternative legacy block identity is invalid/ambiguous")
            blocks[block["id"]] = block
    assemblies = array(e["legacy_assemblies"], "legacy assemblies")
    seen_blocks, used = set(), {}
    for assembly in assemblies:
        exact(assembly, {"block_id", "block_sha256", "assembly_observation_ids", "source_line_ids",
            "ambiguity_group_ids", "status"}, "legacy assembly")
        block_id = assembly["block_id"]
        if not isinstance(block_id, str) or block_id not in blocks or block_id in seen_blocks:
            raise ValueError("text alternative assembly block identity mismatch/duplicate")
        seen_blocks.add(block_id)
        same(assembly["block_sha256"], _alternative_digest(blocks[block_id]), "legacy block digest")
        same(assembly["status"], "unresolved_legacy_assembly", "assembly status")
        members = array(assembly["assembly_observation_ids"], "assembly members")
        if not members or any(not isinstance(i, str) or i not in observations for i in members) or members != sorted(members):
            raise ValueError("text alternative assembly membership is invalid")
        for ident in members:
            used[ident] = used.get(ident, 0) + 1
            if used[ident] > observations[ident]["occurrences"]:
                raise ValueError("text alternative assembly multiplicity exceeds source occurrences")
        source_lines = sorted({line_by_observation[i] for i in members})
        same(assembly["source_line_ids"], source_lines, "assembly source lines")
        linked_groups = sorted(g["group_id"] for g in groups if g["source_line_id"] in source_lines)
        if not linked_groups:
            raise ValueError("text alternative assembly has no connected ambiguity")
        same(assembly["ambiguity_group_ids"], linked_groups, "assembly groups")
    same(assemblies, sorted(assemblies, key=lambda r: r["block_id"]), "assembly ordering")
    same(e["coverage"], {"observation_occurrences": sum(o["occurrences"] for o in observations.values()),
        "distinct_observations": len(ids), "source_lines": len(lines), "conflicting_observations": len(graph),
        "ambiguity_groups": len(groups), "unresolved_legacy_assemblies": len(assemblies)}, "coverage")


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
