"""Synthetic OCR failure contracts only; no real OCR, tracing or visual QA."""
from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

import test_general_generate_workflow as fixtures
from presentation_agent.deckcompiler.errors import DeckCompilerError
from presentation_agent.deckcompiler.identity import content_sha256
from presentation_agent.deckcompiler.manifest_io import read_json, write_json
from presentation_agent.deckcompiler.orchestration import raw_measure_batch as batch
from presentation_agent.deckcompiler.orchestration import vector_preflight as vector


OCR_FAILURE = "OCR failed (synthetic image_to_data failure); falling back to region detection only"


class OcrFailurePropagationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "source.png"
        Image.new("RGB", (320, 180), (31, 45, 59)).save(self.source)
        self.inventory_path = self.root / "work/measurement_inventory.json"
        self.batch_path = write_json(self.root / "batch.json", {"fixture_only": True})

    @staticmethod
    def inventory(notes=None):
        return {
            "canvas_px": {"w": 320, "h": 180},
            "text_blocks": [], "suppressed_text": [],
            "regions": [{"id": "R1", "kind_hint": "flat_shape",
                         "bbox_px": {"x": 20, "y": 20, "w": 40, "h": 30}}],
            "notes": [] if notes is None else notes,
        }

    def build(self, inventory):
        write_json(self.inventory_path, inventory)
        return vector._build_slide_record(
            root=self.root, source=self.source, inventory_path=self.inventory_path,
            inventory=inventory, request_row={"slide_number": 1, "slide_id": "fixture",
                                               "request_id": "fixture-request"},
            backend="tesseract", deep=False, command=["synthetic-contract-fixture"],
            stdout="", stderr="", batch_job_path=self.batch_path,
        )

    def test_generation_rejects_runtime_ocr_failure_before_trace_or_success_record(self):
        for note in (OCR_FAILURE, OCR_FAILURE.upper(),
                     "OCR failed (outer (nested) error\nsecond line); falling back to region detection only"):
            with self.subTest(note=note):
                with patch.object(vector, "trace_png_to_svg", return_value={"status": "rejected"}) as trace:
                    with self.assertRaisesRegex(DeckCompilerError, "OCR|ocr"):
                        self.build(self.inventory([note]))
                    trace.assert_not_called()
                self.assertFalse((self.inventory_path.parent / "detector_record.json").exists())

    def test_failure_is_not_hidden_by_some_detected_text(self):
        inventory = self.inventory([OCR_FAILURE])
        inventory["text_blocks"] = [{"id": "T1", "bbox_px": {"x": 100, "y": 20, "w": 40, "h": 30}}]
        with patch.object(vector, "trace_png_to_svg", return_value={"status": "rejected"}) as trace:
            with self.assertRaisesRegex(DeckCompilerError, "OCR|ocr"):
                self.build(inventory)
            trace.assert_not_called()

    def test_existing_dependency_failures_still_reject(self):
        for note in ("pytesseract not installed — text boxes unavailable",
                     "pytesseract not installed", "text boxes unavailable"):
            with self.subTest(note=note):
                with self.assertRaisesRegex(DeckCompilerError, "OCR|ocr"):
                    self.build(self.inventory([note]))

    def test_successful_zero_text_still_preserves_nontext_regions(self):
        for notes in ([], ["deep-text: 0 rescan rect(s), 0 tile det(s) merged into 0 total"],
                      ["Regression history quotes: '" + OCR_FAILURE + "'"],
                      [OCR_FAILURE + " was a historical example"],
                      ["pytesseract not installed was a historical message; current OCR succeeded"],
                      ["pytesseract not installed — text boxes unavailable (quoted historical warning)"]):
            inventory = self.inventory(notes)
            inventory["regions"][0]["kind_hint"] = "photo"
            before = copy.deepcopy(inventory)
            with patch.object(vector, "trace_png_to_svg") as trace:
                result = self.build(inventory)
                trace.assert_not_called()
            self.assertEqual(inventory, before)
            self.assertEqual(result["text_block_count"], 0)
            self.assertEqual(result["regions"][0]["disposition"], "bounded_raster_candidate")

    def test_malformed_failure_notes_cannot_be_silently_ignored(self):
        for notes in (OCR_FAILURE, None, {"warning": OCR_FAILURE}, [None], [7]):
            with self.subTest(notes=notes):
                inventory = self.inventory(); inventory["notes"] = notes
                with self.assertRaisesRegex(DeckCompilerError, "notes|OCR|ocr"):
                    self.build(inventory)

    def run_adapter(self, inventory):
        # An isolated synthetic detector and dependency stub exercise the actual
        # standalone adapter subprocess. Neither invokes a real OCR provider.
        pipeline = self.root / "pipeline"
        scripts = pipeline / "scripts"
        scripts.mkdir(parents=True, exist_ok=True)
        (scripts / "detect_elements.py").write_text(
            "import json\n"
            f"INVENTORY = json.loads({json.dumps(inventory)!r})\n"
            "def build_inventory(*args, **kwargs):\n    return INVENTORY, None\n",
            encoding="utf-8",
        )
        (scripts / "pytesseract.py").write_text(
            "def get_tesseract_version(): return 'synthetic-runtime-check'\n"
            "def get_languages(config=''): return ['eng', 'kor']\n", encoding="utf-8",
        )
        marker = self.root / "deep_scan_called"
        (scripts / "deep_scan.py").write_text(
            "from pathlib import Path\n"
            "def scan_region(*args, **kwargs):\n"
            f"    Path({str(marker)!r}).write_text('synthetic deep scan called')\n"
            "    return {}\n", encoding="utf-8",
        )
        output = self.root / "adapter/measurement_inventory.json"
        write_json(output, {"stale_fixture_output": True})
        jobs = write_json(self.root / "adapter-jobs.json", {"jobs": [{
            "slide_number": 1, "source_png": str(self.source), "inventory_path": str(output),
        }]})
        completed = subprocess.run(
            [sys.executable, batch.__file__, "--pipeline-root", str(pipeline),
             "--job-file", str(jobs), "--backend", "tesseract", "--deep"],
            capture_output=True, text=True, timeout=10,
        )
        return completed, output, marker

    def test_standalone_adapter_fails_before_deep_scan_or_inventory_write(self):
        inventory = self.inventory([OCR_FAILURE])
        inventory["regions"][0].update(kind_hint="photo", bbox_px={"x": 20, "y": 20, "w": 120, "h": 60})
        completed, output, marker = self.run_adapter(inventory)
        self.assertNotEqual(completed.returncode, 0, completed.stdout)
        self.assertIn("OCR", completed.stderr)
        self.assertFalse(marker.exists())
        self.assertEqual(read_json(output), {"stale_fixture_output": True})

    def test_standalone_adapter_preserves_successful_zero_text(self):
        inventory = self.inventory([])
        inventory["regions"][0].update(kind_hint="photo", bbox_px={"x": 20, "y": 20, "w": 120, "h": 60})
        completed, output, marker = self.run_adapter(inventory)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertTrue(marker.exists())
        self.assertEqual(read_json(output), {**inventory, "deep": [{}]})

    def test_parent_batch_propagates_failure_even_when_stale_inventory_exists(self):
        self.run_adapter(self.inventory([OCR_FAILURE]))
        project = self.root / "pngtopptx-project"
        stale = project / "work/slide01/vector_preflight/measurement_inventory.json"
        write_json(stale, {"stale_fixture_output": True})
        with self.assertRaisesRegex(DeckCompilerError, "raw batch detector failed") as error:
            vector._run_measurement_batches(
                root=self.root, project=project, pipeline=self.root / "pipeline",
                rows=[{"slide_number": 1}], executable=sys.executable,
                backend="tesseract", deep=True, max_workers=1,
            )
        self.assertIn("OCR", str(error.exception))
        self.assertEqual(read_json(stale), {"stale_fixture_output": True})

    def public_runtime(self):
        fixture = fixtures.GeneralGenerateWorkflowTests()
        runtime = self.root / "runtime"
        started = fixture._start(runtime)
        fixture._build_run_draft(
            runtime, workflow_id=started.workflow_id, slide_count=1,
            status="COMPLETED", qa_status="PASS", fail_count=0, blocking_count=0,
        )
        return runtime

    def reseal_failed_inventory(self, runtime, note):
        slide_path = vector.slide_preflight_path(runtime, 1)
        slide = read_json(slide_path)
        inventory_path = runtime / slide["slide"]["measurement_inventory"]["path"]
        inventory = read_json(inventory_path)
        inventory["notes"] = [note]
        write_json(inventory_path, inventory)
        aggregate_path = runtime / vector.PROJECT_DIRECTORY / "work" / vector.MANIFEST_NAME
        aggregate = read_json(aggregate_path)
        for record in (slide["slide"], aggregate["slides"][0]):
            record["measurement_inventory"]["sha256"] = hashlib.sha256(inventory_path.read_bytes()).hexdigest()
            record["slide_content_hash"] = content_sha256({k: v for k, v in record.items() if k != "slide_content_hash"})
        for path, payload in ((slide_path, slide), (aggregate_path, aggregate)):
            payload["content_hash"] = content_sha256({k: v for k, v in payload.items() if k != "content_hash"})
            write_json(path, payload)

    def test_public_cached_slide_and_aggregate_reject_resealed_ocr_failure(self):
        runtime = self.public_runtime()
        for note in (OCR_FAILURE, "pytesseract not installed — text boxes unavailable"):
            self.reseal_failed_inventory(runtime, note)
            for name, report in (
                ("slide", vector.validate_vector_preflight_slide_bundle(runtime, 1)),
                ("aggregate", vector.validate_vector_preflight_bundle(runtime)),
            ):
                with self.subTest(note=note, validator=name):
                    self.assertFalse(report["valid"], report)
                    self.assertTrue(any("OCR" in issue or "ocr" in issue for issue in report["issues"]), report)


if __name__ == "__main__":
    unittest.main()
