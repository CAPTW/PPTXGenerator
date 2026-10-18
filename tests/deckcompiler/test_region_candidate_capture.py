"""Invented capture-option contracts; synthetic detector, no OCR/render claims."""
from __future__ import annotations

import copy
import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
import test_general_generate_workflow as fixtures
from presentation_agent.deckcompiler import cli
from presentation_agent.deckcompiler.errors import DeckCompilerError
from presentation_agent.deckcompiler.identity import content_sha256
from presentation_agent.deckcompiler.manifest_io import read_json, write_json
from presentation_agent.deckcompiler.orchestration import raw_measure_batch as raw
from presentation_agent.deckcompiler.orchestration import vector_preflight as vector
from presentation_agent.deckcompiler.orchestration.reconstruction_jobs import prepare_reconstruction_jobs
from presentation_agent.deckcompiler.orchestration.streaming_execution import (
    accept_streaming_image, finalize_streaming_images, prepare_streaming_execution,
)


def evidence_for(source):
    with Image.open(source) as opened:
        image = opened.convert("RGB")
    width, height = image.size
    box = {"x": 20, "y": 30, "w": 12, "h": 14}
    return {"schema_version": 1, "status": "unadjudicated",
            "method": "detect_regions_without_ocr_mask",
            "canvas_px": {"w": width, "h": height},
            "canvas_rgb_sha256": hashlib.sha256(image.tobytes()).hexdigest(),
            "min_area_fraction": 0.001, "notes": ["Invented capture evidence"],
            "authority": {"text_removal": False, "native_admission": False,
                          "vector_eligibility": False, "quality_accepted": False},
            "candidates": [{"candidate_id": "U01", "measurement": {
                "id": "R01", "kind_hint": "flat_shape", "bbox_px": box,
                "bbox_norm": {k: round(v / (width if k in ("x", "w") else height), 4) for k, v in box.items()},
                "confidence": 0.9}, "overlapping_ocr_mask_ids": [],
                "overlapping_masked_region_ids": []}]}


class RegionCandidateCaptureTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.runtime = self.root / "runtime"
        self.helper = fixtures.GeneralGenerateWorkflowTests()
        started = self.helper._start(self.runtime)
        self.helper._build_run_draft(self.runtime, workflow_id=started.workflow_id, slide_count=2,
                                    status="COMPLETED", qa_status="PASS", fail_count=0, blocking_count=0)
        self.pipeline = self.helper._make_raw_pipeline(self.root / "capture-pipeline")
        self.marker = self.pipeline / "calls.jsonl"
        detector = self.pipeline / "scripts/detect_elements.py"
        # Explicit API-compatible wrapper, with invented evidence and no OCR.
        import inspect
        detector.write_text(detector.read_text() + "\nimport hashlib\n" + inspect.getsource(evidence_for) +
            "\n_original_build_inventory = build_inventory\n"
            "def build_inventory(image_path, backend='easyocr', canvas='native', reader=None, deep_text=False, *, preserve_region_candidates=False):\n"
            f"    with Path({str(self.marker)!r}).open('a') as log: log.write(json.dumps(preserve_region_candidates) + '\\n')\n"
            "    inventory, image = _original_build_inventory(image_path, backend, canvas, reader, deep_text)\n"
            "    if preserve_region_candidates: inventory['region_candidate_evidence'] = evidence_for(image_path)\n"
            "    return inventory, image\n")
        self.configuration = {"pipeline_root": self.pipeline, "python_executable": sys.executable,
                              "backend": "easyocr", "deep": False}

    def calls(self):
        return [json.loads(line) for line in self.marker.read_text().splitlines()] if self.marker.exists() else []

    def prepare(self, enabled=False, **extra):
        return vector.prepare_vector_preflight(self.runtime, preserve_region_candidates=enabled,
                                               **self.configuration, **extra)

    def inventory(self, slide=1):
        receipt = read_json(vector.slide_preflight_path(self.runtime, slide))
        return read_json(self.runtime / receipt["slide"]["measurement_inventory"]["path"])

    @staticmethod
    def seal(path, payload):
        payload["content_hash"] = content_sha256({k: v for k, v in payload.items() if k != "content_hash"})
        write_json(path, payload)

    def test_bulk_mode_reaches_detector_and_cache_matches_both_directions(self):
        self.prepare(False)
        default = self.inventory()
        self.assertNotIn("region_candidate_evidence", default)
        self.prepare(True)
        captured = self.inventory()
        self.assertEqual(captured.pop("region_candidate_evidence"), evidence_for(self.runtime / "pngtopptx-project/src/slide1.png"))
        self.assertEqual(captured, default)
        self.assertEqual(self.calls(), [False, False, True, True])
        self.prepare(True, require_cached=True)
        self.assertEqual(self.calls(), [False, False, True, True])
        self.prepare(False)
        self.assertEqual(self.calls(), [False, False, True, True, False, False])

    def test_single_slide_true_never_reuses_omitted_false_cache(self):
        vector.prepare_vector_preflight_slide(self.runtime, slide_number=1, **self.configuration)
        vector.prepare_vector_preflight_slide(self.runtime, slide_number=1,
                                             preserve_region_candidates=True, **self.configuration)
        vector.prepare_vector_preflight_slide(self.runtime, slide_number=1,
                                             preserve_region_candidates=True, **self.configuration)
        self.assertEqual(self.calls(), [False, True])
        self.assertIs(read_json(vector.slide_preflight_path(self.runtime, 1))["execution"]["preserve_region_candidates"], True)

    def test_required_capture_cannot_reuse_false_receipts(self):
        self.prepare(False)
        before = vector.slide_preflight_path(self.runtime, 1).read_bytes()
        with self.assertRaises(DeckCompilerError): self.prepare(True, require_cached=True)
        self.assertEqual(vector.slide_preflight_path(self.runtime, 1).read_bytes(), before)
        self.assertEqual(self.calls(), [False, False])

    def test_unsupported_detector_fails_explicit_true_but_default_still_works(self):
        legacy = self.helper._make_raw_pipeline(self.root / "legacy-pipeline")
        configuration = {**self.configuration, "pipeline_root": legacy}
        vector.prepare_vector_preflight(self.runtime, **configuration)
        with self.assertRaisesRegex(DeckCompilerError, "preserve_region_candidates"):
            vector.prepare_vector_preflight(self.runtime, preserve_region_candidates=True, **configuration)

    def test_supported_but_missing_evidence_fails_closed(self):
        path = self.pipeline / "scripts/detect_elements.py"
        path.write_text(path.read_text().replace("if preserve_region_candidates:", "if False:"))
        with self.assertRaisesRegex(DeckCompilerError, "region_candidate_evidence"):
            self.prepare(True)

    def test_evidence_validator_binds_frame_pixels_status_and_authority(self):
        source = self.runtime / "pngtopptx-project/src/slide1.png"
        valid = {"region_candidate_evidence": evidence_for(source)}
        raw.validate_region_candidate_evidence(valid, source, required=True)
        for mutation in ("missing", "frame", "frame_bool", "pixels", "status", "authority_true", "authority_zero", "authority_null", "method", "schema_bool", "outside", "nan"):
            with self.subTest(mutation=mutation):
                inventory = copy.deepcopy(valid); evidence = inventory["region_candidate_evidence"]
                if mutation == "missing": inventory.clear()
                elif mutation == "frame": evidence["canvas_px"]["w"] += 1
                elif mutation == "frame_bool": evidence["canvas_px"]["w"] = True
                elif mutation == "pixels": evidence["canvas_rgb_sha256"] = "0" * 64
                elif mutation == "status": evidence["status"] = "accepted"
                elif mutation.startswith("authority_"): evidence["authority"]["native_admission"] = {"authority_true": True, "authority_zero": 0, "authority_null": None}[mutation]
                elif mutation == "method": evidence["method"] = "adjudicated"
                elif mutation == "schema_bool": evidence["schema_version"] = True
                elif mutation == "outside": evidence["candidates"][0]["measurement"]["bbox_px"]["x"] = 1601
                else: evidence["candidates"][0]["measurement"]["bbox_px"]["x"] = float("nan")
                with self.assertRaises(ValueError): raw.validate_region_candidate_evidence(inventory, source, required=True)

    def test_cli_flags_reach_bulk_and_streaming_apis(self):
        parser = cli.build_parser()
        self.assertTrue(parser.parse_args(["prepare-vector-preflight", "--runtime", "x", "--preserve-region-candidates"]).preserve_region_candidates)
        args = ["accept-streaming-image", "--runtime", "x", "--slide", "1", "--tool-call-id", "invented",
                "--queued-at", "x", "--started-at", "x", "--completed-at", "x", "--preserve-region-candidates"]
        self.assertTrue(parser.parse_args(args).preserve_region_candidates)
        self.assertFalse(parser.parse_args(["prepare-vector-preflight", "--runtime", "x"]).preserve_region_candidates)
        with patch.object(cli, "prepare_vector_preflight", side_effect=ValueError("sentinel")) as prepare:
            self.assertEqual(cli.main(["prepare-vector-preflight", "--runtime", "x", "--preserve-region-candidates"]), 1)
            self.assertIs(prepare.call_args.kwargs["preserve_region_candidates"], True)
        with patch.object(cli, "accept_streaming_image", side_effect=ValueError("sentinel")) as accept:
            self.assertEqual(cli.main(args), 1)
            self.assertIs(accept.call_args.kwargs["preserve_region_candidates"], True)

    def streaming(self, modes=(True, True)):
        (self.runtime / "image_batches/image_generation_batch_manifest.json").unlink()
        work = self.runtime / "pngtopptx-project/work"
        (work / "reconstruction_job_manifest.json").unlink()
        (work / vector.MANIFEST_NAME).unlink()
        for path in work.glob("slide[0-9][0-9]"): shutil.rmtree(path)
        prepare_streaming_execution(self.runtime)
        for slide, mode in enumerate(modes, 1):
            accept_streaming_image(self.runtime, slide_number=slide,
                tool_call_id=f"invented-call-{slide}", queued_at="2026-08-11T00:00:00Z",
                started_at="2026-08-11T00:00:01Z", completed_at=f"2026-08-11T00:0{slide}:00Z",
                pipeline_root=self.pipeline, python_executable=sys.executable,
                vector_backend="easyocr", vector_deep=False, preserve_region_candidates=mode)

    def test_streaming_finalization_keeps_capture_without_remeasurement(self):
        self.streaming()
        before = {p: p.read_bytes() for p in (self.runtime / "pngtopptx-project/work").glob("slide*/**/*") if p.is_file()}
        with patch.object(vector, "_run_measurement_batches", side_effect=AssertionError("accepted inputs cannot remeasure")):
            finalize_streaming_images(self.runtime)
            finalize_streaming_images(self.runtime)
        self.assertEqual(self.calls(), [True, True])
        for path, data in before.items(): self.assertEqual(path.read_bytes(), data)
        aggregate = read_json(self.runtime / "pngtopptx-project/work" / vector.MANIFEST_NAME)
        self.assertIs(aggregate["execution"]["preserve_region_candidates"], True)

    def test_streaming_rejects_mixed_modes_before_finalization_writes(self):
        self.streaming((False, True))
        with self.assertRaises(DeckCompilerError): finalize_streaming_images(self.runtime)
        self.assertFalse((self.runtime / "image_batches/image_generation_batch_manifest.json").exists())

    def test_candidates_reach_worker_reference_without_semantic_or_vector_admission(self):
        self.prepare(True)
        prepare_reconstruction_jobs(self.runtime)
        work = self.runtime / "pngtopptx-project/work/slide01"
        job = read_json(work / "reconstruction_job.json")
        inventory = read_json(self.runtime / job["vector_preflight"]["measurement_inventory"]["path"])
        self.assertEqual(inventory["regions"], [])
        self.assertEqual(len(inventory["region_candidate_evidence"]["candidates"]), 1)
        self.assertNotIn("U01", json.dumps(job["semantic_geometry_binding"]))
        prompt = (work / "worker_prompt.md").read_text()
        self.assertIn("region_candidate_evidence", prompt)
        self.assertIn("unadjudicated", prompt)
        self.assertIn("no text-removal", prompt)
        report = vector.validate_vector_preflight_bundle(self.runtime)
        self.assertTrue(report["valid"], report)
        self.assertEqual(report["passed_vector_count"], 0)

    def mutate_bound_capture(self, mutation):
        slide_path = vector.slide_preflight_path(self.runtime, 1)
        slide = read_json(slide_path)
        record = slide["slide"]
        inventory_path = self.runtime / record["measurement_inventory"]["path"]
        inventory = read_json(inventory_path)
        if mutation == "missing": del inventory["region_candidate_evidence"]
        elif mutation == "rgb": inventory["region_candidate_evidence"]["canvas_rgb_sha256"] = "0" * 64
        elif mutation == "frame": inventory["region_candidate_evidence"]["canvas_px"]["h"] += 1
        elif mutation == "authority": inventory["region_candidate_evidence"]["authority"]["text_removal"] = 0
        elif mutation == "mode": slide["execution"]["preserve_region_candidates"] = False
        elif mutation == "mode_type": slide["execution"]["preserve_region_candidates"] = 1
        write_json(inventory_path, inventory)
        record["measurement_inventory"]["sha256"] = hashlib.sha256(inventory_path.read_bytes()).hexdigest()
        record["slide_content_hash"] = content_sha256({k: v for k, v in record.items() if k != "slide_content_hash"})
        self.seal(slide_path, slide)
        aggregate_path = self.runtime / "pngtopptx-project/work" / vector.MANIFEST_NAME
        aggregate = read_json(aggregate_path)
        aggregate["slides"][0] = record
        if mutation in ("mode", "mode_type"):
            aggregate["execution"]["preserve_region_candidates"] = slide["execution"]["preserve_region_candidates"]
        self.seal(aggregate_path, aggregate)

    def test_public_validators_reject_resealed_evidence_and_mode_tampering(self):
        for mutation in ("missing", "rgb", "frame", "authority", "mode", "mode_type"):
            with self.subTest(mutation=mutation):
                self.prepare(True)
                self.mutate_bound_capture(mutation)
                for report in (vector.validate_vector_preflight_slide_bundle(self.runtime, 1),
                               vector.validate_vector_preflight_bundle(self.runtime)):
                    self.assertFalse(report["valid"], report)

    def test_optional_present_evidence_is_checked_even_with_capture_off(self):
        source = self.runtime / "pngtopptx-project/src/slide1.png"
        raw.validate_region_candidate_evidence({}, source)
        evidence = evidence_for(source); evidence["status"] = "accepted"
        with self.assertRaises(ValueError):
            raw.validate_region_candidate_evidence({"region_candidate_evidence": evidence}, source)

    def test_default_prompt_contains_no_candidate_instruction(self):
        self.prepare(False)
        prepare_reconstruction_jobs(self.runtime)
        self.assertNotIn("region_candidate_evidence", (self.runtime / "pngtopptx-project/work/slide01/worker_prompt.md").read_text())


if __name__ == "__main__":
    unittest.main()
