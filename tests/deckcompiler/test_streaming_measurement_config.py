"""Public acceptance/finalization regressions using a synthetic detector fixture.

The workflow code and subprocess adapter are real; no ImageGen, author model,
renderer, or visual-quality evidence is exercised or claimed by these tests.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
import venv
from unittest.mock import patch

import test_general_generate_workflow as fixtures
from presentation_agent.deckcompiler.errors import DeckCompilerError
from presentation_agent.deckcompiler.identity import content_sha256
from presentation_agent.deckcompiler.orchestration import vector_preflight as vector
from presentation_agent.deckcompiler.orchestration.reconstruction_jobs import validate_reconstruction_job_bundle
from presentation_agent.deckcompiler.orchestration.streaming_execution import (
    accept_streaming_image, finalize_streaming_images, prepare_streaming_execution,
    validate_streaming_execution,
)


class StreamingMeasurementConfigTests(unittest.TestCase):
    def _accepted(self, root: Path, *, second: dict | None = None) -> tuple[Path, Path, str]:
        helper = fixtures.GeneralGenerateWorkflowTests()
        runtime = root / "runtime"
        started = helper._start(runtime)
        helper._build_run_draft(runtime, workflow_id=started.workflow_id, slide_count=2,
                                status="COMPLETED", qa_status="PASS", fail_count=0, blocking_count=0)
        (runtime / "image_batches/image_generation_batch_manifest.json").unlink()
        work = runtime / "pngtopptx-project/work"
        (work / "reconstruction_job_manifest.json").unlink()
        (work / vector.MANIFEST_NAME).unlink()
        for slide_dir in work.glob("slide[0-9][0-9]"):
            shutil.rmtree(slide_dir)
        prepare_streaming_execution(runtime)
        pipeline = helper._make_raw_pipeline(root / "selected-pipeline")
        selected_venv = root / "selected-venv"
        venv.EnvBuilder(system_site_packages=True, with_pip=False, symlinks=True).create(selected_venv)
        executable = selected_venv / "bin/python"
        for slide in (1, 2):
            config = {"pipeline_root": pipeline, "python_executable": str(executable),
                      "vector_backend": "tesseract", "vector_deep": False}
            if slide == 2:
                config.update(second or {})
            accept_streaming_image(runtime, slide_number=slide,
                tool_call_id=f"synthetic-imagegen-{slide}", queued_at="2026-08-11T00:00:00Z",
                started_at="2026-08-11T00:00:01Z", completed_at=f"2026-08-11T00:0{slide}:00Z", **config)
        return runtime, pipeline, str(executable)

    @staticmethod
    def _read(path: Path) -> dict:
        return json.loads(path.read_text())

    @staticmethod
    def _write_sealed(path: Path, payload: dict) -> None:
        payload["content_hash"] = content_sha256({k: v for k, v in payload.items() if k != "content_hash"})
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")

    def _reject_without_measurement(self, runtime: Path) -> None:
        state = (runtime / "streaming_execution.json").read_bytes()
        jobs = {p: p.read_bytes() for p in (runtime / "pngtopptx-project/work").glob("slide*/reconstruction_job.json")}
        with patch.object(vector, "_run_measurement_batches", side_effect=AssertionError("detector must not rerun")) as run:
            with self.assertRaises(DeckCompilerError):
                finalize_streaming_images(runtime)
            run.assert_not_called()
        self.assertEqual((runtime / "streaming_execution.json").read_bytes(), state)
        self.assertFalse((runtime / "image_batches/image_generation_batch_manifest.json").exists())
        for path, data in jobs.items():
            self.assertEqual(path.read_bytes(), data)

    def test_public_tesseract_acceptance_finalizes_without_detector_rerun(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime, pipeline, executable = self._accepted(Path(tmp))
            work = runtime / "pngtopptx-project/work"
            accepted_bytes = {p: p.read_bytes() for p in work.glob("slide*/**/*") if p.is_file()}
            with patch.object(vector, "_run_measurement_batches", side_effect=AssertionError("detector must not rerun")) as run:
                with patch.dict(os.environ, {vector.PIPELINE_ENVIRONMENT_VARIABLE: "/missing/pipeline",
                                             vector.PYTHON_ENVIRONMENT_VARIABLE: "/missing/python"}):
                    finalize_streaming_images(runtime)
                    finalize_streaming_images(runtime)
                run.assert_not_called()
            manifest = self._read(work / vector.MANIFEST_NAME)
            self.assertEqual(manifest["execution"]["backend"], "tesseract")
            self.assertIs(manifest["execution"]["deep_scan"], False)
            self.assertEqual(manifest["execution"]["python_executable"], executable)
            self.assertNotEqual(executable, Path(executable).resolve().as_posix())
            self.assertEqual(manifest["pipeline_provenance"]["root"], str(pipeline))
            for path, data in accepted_bytes.items():
                self.assertEqual(path.read_bytes(), data, str(path))
            self.assertTrue(validate_streaming_execution(runtime, require_complete=True)["valid"])
            report = validate_reconstruction_job_bundle(runtime)
            self.assertTrue(report["valid"], report)

    def test_mixed_accepted_configuration_is_rejected_before_batch_write(self) -> None:
        for key, value in (("vector_backend", "easyocr"), ("vector_deep", True),
                           ("python_executable", sys.executable), ("pipeline_root", "other")):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                if key == "pipeline_root":
                    value = fixtures.GeneralGenerateWorkflowTests._make_raw_pipeline(root / "other")
                runtime, _, _ = self._accepted(root, second={key: value})
                self._reject_without_measurement(runtime)

    def test_missing_or_stale_accepted_lineage_is_rejected(self) -> None:
        for target in ("acceptance", "job", "receipt", "batch", "detector", "source"):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as tmp:
                runtime, _, _ = self._accepted(Path(tmp))
                receipt_path = vector.slide_preflight_path(runtime, 1)
                receipt = self._read(receipt_path)
                paths = {"acceptance": runtime / "image_batches/accepted/slide-001.json",
                         "job": runtime / "pngtopptx-project/work/slide01/reconstruction_job.json",
                         "receipt": receipt_path,
                         "batch": runtime / receipt["slide"]["measurement_batch_job"]["path"],
                         "detector": Path(receipt["pipeline_provenance"]["detector"]["path"]),
                         "source": runtime / receipt["slide"]["source_png"]["path"]}
                paths[target].write_bytes(paths[target].read_bytes() + b"\n")
                self._reject_without_measurement(runtime)

    def test_resealed_state_cannot_substitute_a_different_accepted_call(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime, _, _ = self._accepted(Path(tmp))
            path = runtime / "streaming_execution.json"
            state = self._read(path)
            state["slides"][0]["image_call"]["tool_call_id"] = "substituted-call"
            self._write_sealed(path, state)
            self._reject_without_measurement(runtime)

    def test_missing_or_inconsistent_persisted_configuration_is_rejected(self) -> None:
        for key, value in (("backend", None), ("deep_scan", "false"),
                           ("python_executable", "python"), ("backend", "easyocr")):
            with self.subTest(key=key, value=value), tempfile.TemporaryDirectory() as tmp:
                runtime, _, _ = self._accepted(Path(tmp))
                preflight_path = vector.slide_preflight_path(runtime, 1)
                preflight = self._read(preflight_path)
                if value is None:
                    del preflight["execution"][key]
                else:
                    preflight["execution"][key] = value
                self._write_sealed(preflight_path, preflight)
                # Rebind the outer hashes to exercise configuration validation itself,
                # rather than merely stopping at the stale accepted artifact hash.
                sha = fixtures.GeneralGenerateWorkflowTests._sha256
                job_path = runtime / "pngtopptx-project/work/slide01/reconstruction_job.json"
                job = self._read(job_path)
                job["vector_preflight"]["manifest"]["sha256"] = sha(preflight_path)
                job["receipt_binding"]["vector_preflight_sha256"] = sha(preflight_path)
                self._write_sealed(job_path, job)
                acceptance_path = runtime / "image_batches/accepted/slide-001.json"
                acceptance = self._read(acceptance_path)
                acceptance["reconstruction_job"]["sha256"] = sha(job_path)
                self._write_sealed(acceptance_path, acceptance)
                state_path = runtime / "streaming_execution.json"
                state = self._read(state_path)
                state["slides"][0]["reconstruction_job"]["sha256"] = sha(job_path)
                state["slides"][0]["accepted_receipt"]["sha256"] = sha(acceptance_path)
                self._write_sealed(state_path, state)
                self._reject_without_measurement(runtime)

    def test_standalone_default_preflight_keeps_easyocr_deep_measurement_behavior(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime, _, _ = self._accepted(Path(tmp))
            finalize_streaming_images(runtime)
            with patch.object(vector, "_run_measurement_batches", wraps=vector._run_measurement_batches) as run:
                vector.prepare_vector_preflight(runtime)
                run.assert_called_once()
                self.assertEqual(run.call_args.kwargs["backend"], "easyocr")
                self.assertIs(run.call_args.kwargs["deep"], True)
                self.assertEqual(run.call_args.kwargs["executable"], sys.executable)

    def test_cache_only_consolidation_rejects_configuration_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime, pipeline, executable = self._accepted(Path(tmp))
            finalize_streaming_images(runtime)
            with patch.object(vector, "_run_measurement_batches", side_effect=AssertionError("detector must not rerun")) as run:
                with self.assertRaises(DeckCompilerError):
                    vector.prepare_vector_preflight(runtime, pipeline_root=pipeline,
                        python_executable=executable, backend="easyocr", deep=False, require_cached=True)
                run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
