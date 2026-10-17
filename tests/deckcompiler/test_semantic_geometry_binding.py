from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image
from presentation_agent.deckcompiler.errors import DeckCompilerError
from presentation_agent.deckcompiler.identity import content_sha256
from presentation_agent.deckcompiler.manifest_io import read_json, write_json
from presentation_agent.deckcompiler.orchestration.image_requests import prepare_image_requests
from presentation_agent.deckcompiler.orchestration.reconstruction_jobs import _build_job_row


class SemanticGeometryBindingTests(unittest.TestCase):
    """Contract fixtures, not detector, model, renderer, or quality evaluation."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        write_json(self.root / "generate_workflow_manifest.json", {
            "workflow_id": "binding-fixture", "input_contract": {"presentation": {"title": "Two slides"}},
        })
        write_json(self.root / "skillset_execution_plan.json", {"execution_profile": {"profile_name": "fixture"}})
        write_json(self.root / "architect/workflow_design.json", {})
        write_json(self.root / "architect/approval_record.json", {
            gate: {"status": "APPROVED", "approved_by": "user"} for gate in ("gate1", "gate2")
        })
        write_json(self.root / "architect/design_system.json", {
            "global_prompt_cues": ["precise"],
            "visual_routes": [{"route_id": "route", "prompt_cues": ["clean"]}],
            "layouts": [{"layout_id": "layout", "prompt_cues": ["two objects"]}],
        })
        write_json(self.root / "architect/blueprint.json", {
            "approved_visual_route_id": "route",
            "slides": [{
                "slide_number": number, "slide_id": f"slide-{number}", "purpose": "contract test",
                "title": f"Approved title {number}",
                "on_slide_copy": {"cards": [{"object_id": f"card-{number}", "text": "한글  exact\ncopy", "values": [1, 2.5, False]}]},
                "layout_id": "layout", "visual_direction": "Keep native text", "presenter_notes": "Private speaker note",
            } for number in (1, 2)],
        })
        prepared = prepare_image_requests(self.root)
        self.requests = read_json(prepared.request_manifest_path)["slides"]
        self.args = {}
        self.maps = {}
        for row in self.requests:
            n = row["slide_number"]
            source = self.root / f"pngtopptx-project/src/slide{n}.png"
            source.parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (320, 180), (n * 10, 20, 30)).save(source)
            work = self.root / f"pngtopptx-project/work/slide{n:02d}"
            inventory = write_json(work / "vector_preflight/measurements.json", {
                "canvas_px": {"w": 320, "h": 180},
                "text_blocks": [
                    {"id": "T1", "text": "OCR has a typ0", "bbox_px": {"x": 12, "y": 10, "w": 280, "h": 28}},
                    {"id": "T2", "text": "OCR differs", "bbox_px": {"x": 12, "y": 52, "w": 280, "h": 90}, "raw_polygon": [[12,52],[292,52],[292,142],[12,142]]},
                ], "regions": [], "notes": ["Explicit synthetic contract fixture; no detector executed"],
            })
            detector = write_json(work / "vector_preflight/detector_record.json", {"fixture_only": True})
            icons = work / "vector_preflight/icons.py"
            icons.write_text("ICONS = {}\n")
            vector = {"pipeline_provenance": {"svg_icon_library": self.artifact(icons), "svg_icon_names": []}}
            vector_path = write_json(work / "vector_preflight/slide_vector_preflight.json", vector)
            self.args[n] = {
                "workflow_id": "binding-fixture", "request_row": row,
                "call": {"status": "ACCEPTED", "request_id": row["request_id"], "prompt_sha256": row["prompt"]["sha256"], "selected_png_sha256": self.sha(source)},
                "renderer": {"skill_path": "fixture/slide-image-dual-render/SKILL.md"},
                "execution_profile": {key: "fixture" for key in ("profile_name", "target_model", "target_reasoning_effort", "fallback_policy", "determinism_contract", "worker_context")},
                "vector_preflight_path": vector_path, "vector_preflight": vector,
                "vector_row": {"slide_content_hash": content_sha256({"synthetic_slide": n}), "measurement_inventory": self.artifact(inventory), "detector_record": self.artifact(detector), "regions": []},
                "lineage_path": self.root / "fixture-accepted-calls.json",
            }
            self.maps[n] = {
                "workflow_id": "binding-fixture", "slide_number": n, "slide_id": row["slide_id"], "request_id": row["request_id"],
                "source_png_sha256": self.sha(source), "semantic_sidecar_sha256": row["semantic_sidecar"]["sha256"], "measurement_inventory_sha256": self.sha(inventory),
                "bindings": [
                    {"content_pointer": "/exact_title", "measurement_collection": "text_blocks", "measurement_id": "T1"},
                    {"content_pointer": "/exact_on_slide_copy/cards/0", "content_identity_pointer": "/exact_on_slide_copy/cards/0/object_id", "measurement_collection": "text_blocks", "measurement_id": "T2"},
                ],
            }

    @staticmethod
    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def artifact(self, path):
        return {"path": path.relative_to(self.root).as_posix(), "sha256": self.sha(path)}

    def build(self, number=1, association=None):
        if association is not None:
            write_json(self.root / f"pngtopptx-project/work/slide{number:02d}/semantic_geometry_associations.json", association)
        return _build_job_row(self.root, **self.args[number])

    def assert_rejected(self, association, pattern):
        with self.assertRaisesRegex(DeckCompilerError, pattern):
            self.build(association=association)

    def test_missing_association_exposes_unresolved_without_changing_renderer(self):
        row = self.build()
        self.assertEqual(row["job"]["semantic_geometry_binding"]["status"], "UNRESOLVED")
        self.assertIn("UNRESOLVED", row["worker_prompt"])
        self.assertTrue(row["job"]["authoring_contract"]["backend_branching_forbidden"])
        self.assertIn("s1.fragment.js", row["job"]["authoring_outputs"])

    def test_two_slide_original_job_consumes_exact_content_and_measured_references(self):
        for n in (1, 2):
            with self.subTest(slide=n):
                sidecar_path = self.root / self.requests[n - 1]["semantic_sidecar"]["path"]
                inventory_path = self.root / self.args[n]["vector_row"]["measurement_inventory"]["path"]
                before = (sidecar_path.read_bytes(), inventory_path.read_bytes())
                result = self.build(n, self.maps[n])
                job = result["job"]
                bridge = job["semantic_geometry_binding"]
                self.assertEqual(bridge["status"], "EXPLICIT_ASSOCIATIONS_BOUND")
                self.assertEqual(bridge["bindings"][0]["content_value"], f"Approved title {n}")
                self.assertEqual(bridge["bindings"][1]["content_value"], read_json(sidecar_path)["exact_on_slide_copy"]["cards"][0])
                self.assertEqual(bridge["bindings"][1]["content_identity"]["value"], f"card-{n}")
                self.assertEqual(bridge["bindings"][1]["measurement_pointer"], "/text_blocks/1")
                self.assertEqual(bridge["measurement_inventory"], self.args[n]["vector_row"]["measurement_inventory"])
                self.assertEqual(before, (sidecar_path.read_bytes(), inventory_path.read_bytes()))
                self.assertEqual(job["authoring_contract"]["exact_text_source"], "semantic_sidecar")
                self.assertEqual(job["authoring_contract"]["measured_geometry_source"], "vector_preflight.measurement_inventory")
                self.assertIn("semantic_geometry_binding", result["worker_prompt"])
                self.assertEqual(job["content_hash"], content_sha256({k:v for k,v in job.items() if k != "content_hash"}))

    def test_rejects_cross_slide_association_even_when_inventory_ids_repeat(self):
        self.assert_rejected(self.maps[2], "slide_number")

    def test_rejects_missing_content_pointer(self):
        data = copy.deepcopy(self.maps[1]); data["bindings"][1]["content_pointer"] = "/exact_on_slide_copy/cards/9"
        self.assert_rejected(data, "content_pointer")

    def test_rejects_invented_object_identity(self):
        data = copy.deepcopy(self.maps[1]); data["bindings"][1]["content_identity_pointer"] = "/exact_on_slide_copy/cards/0/slot_id"
        self.assert_rejected(data, "content_identity_pointer")

    def test_rejects_missing_measurement_id(self):
        data = copy.deepcopy(self.maps[1]); data["bindings"][1]["measurement_id"] = "imagined-box"
        self.assert_rejected(data, "measurement_id")

    def test_rejects_identity_metadata_as_display_content(self):
        data = copy.deepcopy(self.maps[1]); data["bindings"][1]["content_pointer"] = "/exact_on_slide_copy/cards/0/object_id"
        self.assert_rejected(data, "identity field")

    def test_rejects_reusing_geometry_for_distinct_content(self):
        data = copy.deepcopy(self.maps[1]); data["bindings"][1]["measurement_id"] = "T1"
        self.assert_rejected(data, "duplicate measurement")

    def test_rejects_stale_inventory_binding(self):
        data = copy.deepcopy(self.maps[1]); data["measurement_inventory_sha256"] = "0" * 64
        self.assert_rejected(data, "measurement_inventory_sha256")

    def test_rejects_speaker_notes_as_on_slide_content(self):
        data = copy.deepcopy(self.maps[1]); data["bindings"][0]["content_pointer"] = "/presenter_notes"
        self.assert_rejected(data, "content_pointer")

    def test_rejects_empty_explicit_mapping(self):
        data = copy.deepcopy(self.maps[1]); data["bindings"] = []
        self.assert_rejected(data, "bindings")

    def test_rejects_inventory_changed_after_association(self):
        inventory_path = self.root / self.args[1]["vector_row"]["measurement_inventory"]["path"]
        inventory = read_json(inventory_path); inventory["text_blocks"][0]["bbox_px"]["x"] = 13
        write_json(inventory_path, inventory)
        self.assert_rejected(self.maps[1], "sha256")

    def test_rejects_unapproved_architect_changes(self):
        from presentation_agent.deckcompiler.orchestration.reconstruction_jobs import prepare_reconstruction_jobs
        approval_path = self.root / "architect/approval_record.json"
        approval = read_json(approval_path); approval["gate2"]["status"] = "PENDING"
        write_json(approval_path, approval)
        with self.assertRaisesRegex(DeckCompilerError, "APPROVED"):
            prepare_reconstruction_jobs(self.root)

    def test_public_two_slide_job_bundle_consumes_associations_and_invalidates_old_receipt(self):
        import test_general_generate_workflow as upstream
        from presentation_agent.deckcompiler.orchestration.reconstruction_jobs import prepare_reconstruction_jobs, validate_reconstruction_job_bundle

        class Fixture(upstream.GeneralGenerateWorkflowTests):
            @staticmethod
            def _make_raw_pipeline(root):
                path = upstream.GeneralGenerateWorkflowTests._make_raw_pipeline(root)
                detector = path / "scripts/detect_elements.py"
                code = detector.read_text()
                fixture_blocks = [{"id": "T1", "text": "synthetic OCR observation", "bbox_px": {"x": 12, "y": 10, "w": 280, "h": 28}}]
                detector.write_text(code.replace('"text_blocks": [],', '"text_blocks": ' + repr(fixture_blocks) + ','))
                return path

        fixture = Fixture()
        runtime = self.root / "public-flow"
        started = fixture._start(runtime)
        fixture._build_run_draft(runtime, workflow_id=started.workflow_id, slide_count=2, status="COMPLETED", qa_status="PASS", fail_count=0, blocking_count=0)
        original_bytes = {}
        for n in (1, 2):
            work = runtime / f"pngtopptx-project/work/slide{n:02d}"
            job = read_json(work / "reconstruction_job.json")
            for artifact in (job["semantic_sidecar"], job["vector_preflight"]["measurement_inventory"]):
                original_bytes[artifact["path"]] = (runtime / artifact["path"]).read_bytes()
            write_json(work / "semantic_geometry_associations.json", {
                "workflow_id": job["workflow_id"], "slide_number": n, "slide_id": job["slide_id"], "request_id": job["request_lineage"]["request_id"],
                "source_png_sha256": job["source_png"]["sha256"], "semantic_sidecar_sha256": job["semantic_sidecar"]["sha256"],
                "measurement_inventory_sha256": job["vector_preflight"]["measurement_inventory"]["sha256"],
                "bindings": [{"content_pointer": "/exact_title", "measurement_collection": "text_blocks", "measurement_id": "T1"}],
            })
        result = prepare_reconstruction_jobs(runtime)
        self.assertEqual(result.slide_count, 2)
        report = validate_reconstruction_job_bundle(runtime)
        self.assertTrue(report["valid"], report)
        for n in (1, 2):
            job = read_json(runtime / f"pngtopptx-project/work/slide{n:02d}/reconstruction_job.json")
            self.assertEqual(job["semantic_geometry_binding"]["bindings"][0]["content_value"], f"Readiness Topic {n}")
        self.assertTrue(all((runtime / path).read_bytes() == data for path, data in original_bytes.items()))
        old_receipt_report = validate_reconstruction_job_bundle(runtime, require_worker_outputs=True)
        self.assertFalse(old_receipt_report["valid"])
        self.assertTrue(any("jobContentHash" in issue for issue in old_receipt_report["issues"]), old_receipt_report)

    def test_legacy_default_job_requires_explicit_regeneration_and_worker_rerun(self):
        import test_general_generate_workflow as upstream
        from presentation_agent.deckcompiler.orchestration.reconstruction_jobs import validate_reconstruction_job_bundle

        fixture = upstream.GeneralGenerateWorkflowTests()
        runtime = self.root / "legacy-default-job"
        started = fixture._start(runtime)
        fixture._build_run_draft(runtime, workflow_id=started.workflow_id, slide_count=1, status="COMPLETED", qa_status="PASS", fail_count=0, blocking_count=0)
        self.assertTrue(validate_reconstruction_job_bundle(runtime)["valid"])
        work = runtime / "pngtopptx-project/work"
        job_path = work / "slide01/reconstruction_job.json"
        job = read_json(job_path)
        sidecar_path = runtime / job["semantic_sidecar"]["path"]
        sidecar_bytes = sidecar_path.read_bytes()
        self.assertEqual(job.pop("semantic_geometry_binding")["status"], "UNRESOLVED")
        job["content_hash"] = content_sha256({key:value for key,value in job.items() if key != "content_hash"})
        write_json(job_path, job)
        manifest_path = work / "reconstruction_job_manifest.json"
        manifest = read_json(manifest_path)
        manifest["jobs"][0]["job"]["sha256"] = self.sha(job_path)
        manifest["jobs"][0]["job_content_hash"] = job["content_hash"]
        manifest["content_hash"] = content_sha256({key:value for key,value in manifest.items() if key != "content_hash"})
        write_json(manifest_path, manifest)
        report = validate_reconstruction_job_bundle(runtime)
        self.assertFalse(report["valid"])
        self.assertTrue(any(
            "missing semantic_geometry_binding" in issue
            and "regenerate reconstruction jobs" in issue
            and "rerun affected workers" in issue
            and "old worker receipts cannot be reused" in issue
            for issue in report["issues"]
        ), report)
        self.assertTrue(any("not deterministically derived" in issue for issue in report["issues"]), report)
        self.assertEqual(sidecar_bytes, sidecar_path.read_bytes())


if __name__ == "__main__":
    unittest.main()
