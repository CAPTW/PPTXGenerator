"""Invented legacy-cache migration contracts; no OCR or render-quality claims."""
from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import test_general_generate_workflow as fixtures
from presentation_agent.deckcompiler.errors import DeckCompilerError
from presentation_agent.deckcompiler.identity import content_sha256
from presentation_agent.deckcompiler.manifest_io import read_json, write_json
from presentation_agent.deckcompiler.orchestration import vector_preflight as vector
from presentation_agent.deckcompiler.schemas import validator_for


class VectorReceiptVersionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "invented-runtime"
        helper = fixtures.GeneralGenerateWorkflowTests()
        started = helper._start(self.root)
        helper._build_run_draft(self.root, workflow_id=started.workflow_id, slide_count=1,
                                status="COMPLETED", qa_status="PASS", fail_count=0, blocking_count=0)
        self.slide_path = vector.slide_preflight_path(self.root, 1)
        self.aggregate_path = self.root / vector.PROJECT_DIRECTORY / "work" / vector.MANIFEST_NAME
        self.initial_slide = read_json(self.slide_path)
        self.initial_aggregate = read_json(self.aggregate_path)
        self.inputs = vector._load_inputs(self.root)
        self.pipeline = Path(self.initial_slide["pipeline_provenance"]["root"])
        self.configuration = {"pipeline_root": self.pipeline,
                              "python_executable": self.initial_slide["execution"]["python_executable"],
                              "backend": self.initial_slide["execution"]["backend"],
                              "deep": self.initial_slide["execution"]["deep_scan"]}

    @staticmethod
    def seal(path, payload):
        payload["content_hash"] = content_sha256({k: v for k, v in payload.items() if k != "content_hash"})
        write_json(path, payload)

    def install_receipts(self, *, legacy, fractional=True, builder=None):
        """The old-format fixture reproduces former int-per-field box storage.

        A test-only builder may supply the actual retained old module during a
        private reproduction. Public tests depend only on current repository code.
        """
        source_record = self.initial_slide["slide"]
        source = self.root / source_record["source_png"]["path"]
        inventory_path = self.root / source_record["measurement_inventory"]["path"]
        batch_path = self.root / source_record["measurement_batch_job"]["path"]
        box = {"x": 10.9, "y": 20.4, "w": 9.2, "h": 7.1} if fractional else {"x": 10, "y": 20, "w": 9, "h": 7}
        inventory = {"canvas_px": {"w": 1600, "h": 900},
                     "text_blocks": [{"id": "invented-text", "bbox_px": {"x": 19.5, "y": 22, "w": 2, "h": 2}}],
                     "suppressed_text": [], "notes": ["Invented cache migration fixture"],
                     "regions": [{"id": "invented-region", "kind_hint": "flat_shape", "bbox_px": box}]}
        write_json(inventory_path, inventory)
        self.measurement = {1: {"inventory_path": inventory_path, "batch_job_path": batch_path,
                                "command": ["invented-contract-detector"], "stdout": "", "stderr": ""}}
        kwargs = dict(root=self.root, source=source, inventory_path=inventory_path, inventory=inventory,
                      request_row=self.inputs["slides"][0], backend=self.configuration["backend"],
                      deep=self.configuration["deep"], command=["invented-contract-detector"],
                      stdout="", stderr="", batch_job_path=batch_path)
        owner = vector if builder is None else builder
        # Trace is explicitly a rejected sentinel. The regression concerns cached
        # geometry and protection decisions, never successful SVG fidelity.
        with patch.object(owner, "trace_png_to_svg", return_value={"status": "rejected", "reason": "contract-only"}):
            if legacy and builder is None:
                with patch.object(vector, "_validated_bbox", side_effect=lambda value, *_: {k: int(value[k]) for k in ("x", "y", "w", "h")}):
                    record = owner._build_slide_record(**kwargs)
            else:
                record = owner._build_slide_record(**kwargs)
        if legacy:
            with patch.object(vector, "SLIDE_MANIFEST_VERSION", "1.0.0"):
                vector._write_slide_preflight_receipt(root=self.root, inputs=self.inputs, pipeline=self.pipeline,
                    executable=self.configuration["python_executable"], backend=self.configuration["backend"],
                    deep=self.configuration["deep"], record=record)
        else:
            vector._write_slide_preflight_receipt(root=self.root, inputs=self.inputs, pipeline=self.pipeline,
                executable=self.configuration["python_executable"], backend=self.configuration["backend"],
                deep=self.configuration["deep"], record=record)
        aggregate = copy.deepcopy(self.initial_aggregate)
        aggregate.update(schema_version="1.0.0" if legacy else vector.MANIFEST_VERSION,
                         slides=[record], measured_region_count=1, passed_vector_count=0)
        self.seal(self.aggregate_path, aggregate)
        return record

    def assert_protected_current(self):
        payload = read_json(self.slide_path)
        self.assertEqual(payload["schema_version"], "1.1.0")
        row = payload["slide"]["regions"][0]
        self.assertEqual(row["bbox_px"], {"x": 10, "y": 20, "w": 11, "h": 8})
        self.assertEqual(row["semantic_text_overlap_ids"], ["invented-text"])
        self.assertEqual(row["disposition"], "native_rebuild_text_protected")
        self.assertTrue(vector.validate_vector_preflight_slide_bundle(self.root, 1)["valid"])

    def test_legacy_fractional_slide_and_aggregate_are_stale(self):
        record = self.install_receipts(legacy=True)
        self.assertEqual(record["regions"][0]["bbox_px"], {"x": 10, "y": 20, "w": 9, "h": 7})
        self.assertEqual(record["regions"][0]["semantic_text_overlap_ids"], [])
        for report in (vector.validate_vector_preflight_slide_bundle(self.root, 1),
                       vector.validate_vector_preflight_bundle(self.root)):
            with self.subTest(report=report):
                self.assertFalse(report["valid"], report)
                self.assertTrue(any("schema_version" in issue for issue in report["issues"]), report)

    def test_single_slide_prepare_rebuilds_legacy_geometry_and_protection(self):
        self.install_receipts(legacy=True)
        with patch.object(vector, "_run_measurement_batches", return_value=self.measurement) as measure, patch.object(vector, "trace_png_to_svg") as trace:
            vector.prepare_vector_preflight_slide(self.root, slide_number=1, **self.configuration)
            measure.assert_called_once()
            trace.assert_not_called()
        self.assert_protected_current()

    def test_require_cached_rejects_legacy_without_writing_or_measuring(self):
        self.install_receipts(legacy=True)
        before = (self.slide_path.read_bytes(), self.aggregate_path.read_bytes())
        with patch.object(vector, "_run_measurement_batches") as measure:
            with self.assertRaisesRegex(DeckCompilerError, "missing, stale"):
                vector.prepare_vector_preflight(self.root, require_cached=True, **self.configuration)
            measure.assert_not_called()
        self.assertEqual(before, (self.slide_path.read_bytes(), self.aggregate_path.read_bytes()))

    def test_ordinary_aggregate_prepare_rebuilds_and_emits_current_versions(self):
        self.install_receipts(legacy=True)
        with patch.object(vector, "_run_measurement_batches", return_value=self.measurement) as measure, patch.object(vector, "trace_png_to_svg") as trace:
            vector.prepare_vector_preflight(self.root, **self.configuration)
            measure.assert_called_once()
            trace.assert_not_called()
        self.assert_protected_current()
        self.assertEqual(read_json(self.aggregate_path)["schema_version"], "1.1.0")
        self.assertTrue(vector.validate_vector_preflight_bundle(self.root)["valid"])

    def test_current_integer_and_fractional_receipts_reuse_without_measurement(self):
        for fractional in (False, True):
            with self.subTest(fractional=fractional):
                self.install_receipts(legacy=False, fractional=fractional)
                self.assertTrue(vector.validate_vector_preflight_slide_bundle(self.root, 1)["valid"])
                self.assertTrue(vector.validate_vector_preflight_bundle(self.root)["valid"])
                before = self.slide_path.read_bytes()
                record = read_json(self.slide_path)["slide"]
                with patch.object(vector, "_run_measurement_batches", side_effect=AssertionError("cache must not measure")) as measure:
                    vector.prepare_vector_preflight_slide(self.root, slide_number=1, **self.configuration)
                    vector.prepare_vector_preflight(self.root, require_cached=True, **self.configuration)
                    measure.assert_not_called()
                self.assertEqual(self.slide_path.read_bytes(), before)
                self.assertEqual(read_json(self.aggregate_path)["slides"], [record])
                self.assertTrue(vector.validate_vector_preflight_bundle(self.root)["valid"])

    def test_old_integer_receipts_also_require_one_time_migration(self):
        self.install_receipts(legacy=True, fractional=False)
        for report in (vector.validate_vector_preflight_slide_bundle(self.root, 1),
                       vector.validate_vector_preflight_bundle(self.root)):
            self.assertFalse(report["valid"], report)
        with patch.object(vector, "_run_measurement_batches") as measure:
            with self.assertRaises(DeckCompilerError):
                vector.prepare_vector_preflight(self.root, require_cached=True, **self.configuration)
            measure.assert_not_called()

    def test_current_aggregate_cannot_make_old_child_reusable(self):
        self.install_receipts(legacy=False)
        current_aggregate = self.aggregate_path.read_bytes()
        slide = read_json(self.slide_path); slide["schema_version"] = "1.0.0"; self.seal(self.slide_path, slide)
        with patch.object(vector, "_run_measurement_batches") as measure:
            with self.assertRaisesRegex(DeckCompilerError, "missing, stale"):
                vector.prepare_vector_preflight(self.root, require_cached=True, **self.configuration)
            measure.assert_not_called()
        self.assertEqual(self.aggregate_path.read_bytes(), current_aggregate)

    def test_schema_and_both_producers_use_current_receipt_version(self):
        self.assertEqual(vector.SLIDE_MANIFEST_VERSION, "1.1.0")
        self.assertEqual(vector.MANIFEST_VERSION, "1.1.0")
        self.assertEqual(validator_for(vector.MANIFEST_SCHEMA).schema["properties"]["schema_version"], {"const": "1.1.0"})
        self.assertEqual(self.initial_slide["schema_version"], "1.1.0")
        self.assertEqual(self.initial_aggregate["schema_version"], "1.1.0")


if __name__ == "__main__":
    unittest.main()
