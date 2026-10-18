"""Invented official-shaped manifests; these tests do not execute a renderer."""
from __future__ import annotations

import copy
import hashlib
import importlib
import os
import unittest
from pathlib import Path
from unittest.mock import patch

import test_region_classification_review as review_fixtures
import test_general_generate_workflow as workflow_fixtures
from presentation_agent.deckcompiler.errors import DeckCompilerError
from presentation_agent.deckcompiler.identity import content_sha256
from presentation_agent.deckcompiler.manifest_io import read_json, write_json
from presentation_agent.deckcompiler.orchestration import reconstruction_jobs as jobs
from presentation_agent.deckcompiler.orchestration.shared_render_qa import finalize_shared_render_qa

NAME = "surface_call_accounting.json"
CANDIDATES = "region_candidate_evidence.candidates"
AUTHORITY = {key: False for key in (
    "semantic_truth", "text_removal", "native_admission", "vector_eligibility", "quality_accepted")}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ref(collection, ident):
    return {"collection": collection, "observation_id": ident}


def pointer(index, obj, slide=1):
    return {"pointer": f"/slides/{slide}/objects/{index}", "object_sha256": content_sha256(obj)}


def accounting(root, job, work):
    project = root / "pngtopptx-project"
    return {
        "schema_name": "codex_surface_call_accounting", "schema_version": "1.0.0",
        "job_id": job["job_id"], "job_content_hash": job["content_hash"],
        "slide_number": job["slide_number"],
        "bindings": {
            "source_png_sha256": job["source_png"]["sha256"],
            "measurement_inventory_sha256": job["vector_preflight"]["measurement_inventory"]["sha256"],
            "review_artifact_sha256": job["region_classification_review"]["review_artifact"]["sha256"],
            "fragment_sha256": sha(work / f"s{job['slide_number']}.fragment.js"),
            "integrated_slides_sha256": sha(project / "lib/slides.js"),
            "native_manifest_sha256": sha(project / "out/native_object_manifest.json"),
            "render_trace_sha256": sha(project / "out/render_trace.json"),
        },
        "groups": [], "unresolved": [], "extras": [], "authority": AUTHORITY.copy(),
    }


class SurfaceCallAccountingTests(unittest.TestCase):
    def setUp(self):
        self.fixture = review_fixtures.RegionClassificationReviewTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        f = self.fixture
        f.review["coverage"] = "complete"
        f.review["decisions"] = [f.decision(c, i, r) for c, i, r in (
            ("text_blocks", "T1", "text"), ("text_blocks", "T2", "uncertain"),
            ("suppressed_text", "S1", "text"), (CANDIDATES, "U01", "text"),
            (CANDIDATES, "U02", "graphic"), (CANDIDATES, "U03", "graphic"))]
        self.job = f.build()["job"]
        self.root, self.work = f.root, f.work
        self.project = self.root / "pngtopptx-project"
        self.path = self.work / NAME
        (self.project / "lib").mkdir(exist_ok=True)
        (self.project / "out").mkdir(exist_ok=True)
        (self.work / "s1.fragment.js").write_text("function s1(s) { s.txt('Invented',1,2,3,4); }\n")
        (self.project / "lib/slides.js").write_text("// Invented integration fixture only\n")
        self.objects = [
            {"type": kind, "x": 10 + i * 30, "y": 10, "w": 25, "h": 15,
             "textLength": 8 if kind == "text" else 0, "editable": True,
             "source": "surface.txt" if kind == "text" else "surface.rrect"}
            for i, kind in enumerate(("text", "text", "panel", "panel", "panel"))]
        self.native_path = write_json(self.project / "out/native_object_manifest.json", {
            "source": "actual-render-surface-calls", "slides": {"1": {
                "objects": self.objects, "counts": {"text": 2, "panels": 3},
                "editableTextLength": 16, "editableObjectCount": 5}}})
        self.trace_path = write_json(self.project / "out/render_trace.json", {
            "projectRoot": self.project.resolve().as_posix(),
            "hashes": {"slidesJs": sha(self.project / "lib/slides.js")},
            "nativeObjectManifestHash": sha(self.native_path)})
        self.data = accounting(self.root, self.job, self.work)
        self.data["groups"] = [
            {"group_id": "heading", "source": ref("text_blocks", "T1"),
             "glyph_members": [ref(CANDIDATES, "U01")], "objects": [pointer(0, self.objects[0])],
             "reason": "Explicit claimed glyph membership; semantics unverified"},
            {"group_id": "label", "source": ref("suppressed_text", "S1"), "glyph_members": [],
             "objects": [pointer(1, self.objects[1])], "reason": "Editable label call"},
            {"group_id": "graphic", "source": ref(CANDIDATES, "U03"), "glyph_members": [],
             "objects": [pointer(2, self.objects[2])], "reason": "Graphic surface-call claim"}]
        self.data["unresolved"] = [
            {"source": ref("text_blocks", "T2"), "disposition": "deferred", "objects": [],
             "reason": "Uncertain OCR remains protected"},
            {"source": ref(CANDIDATES, "U02"), "disposition": "unresolved", "objects": [pointer(3, self.objects[3])],
             "reason": "Claimed graphic conflicts with protected OCR"}]
        self.data["extras"] = [{"object": pointer(4, self.objects[4]), "purpose": "decorative", "reason": "Explicit ornament claim"}]

    def validate(self, data=None):
        write_json(self.path, self.data if data is None else data)
        module = importlib.import_module("presentation_agent.deckcompiler.orchestration.surface_call_accounting")
        return module.validate_surface_call_accounting(self.root, self.job, self.work)

    def test_complete_accounting_preserves_unresolved_observations_and_all_authority(self):
        before = {p: p.read_bytes() for p in (self.fixture.inventory_path, self.fixture.path, self.work / "s1.fragment.js")}
        result = self.validate()
        self.assertEqual(result["status"], "SURFACE_CALLS_ACCOUNTED")
        self.assertEqual(result["scope"], "surface_calls_not_serialized_pptx")
        self.assertTrue(result["accounting_complete"])
        self.assertEqual(result["representation_status"], "NOT_ESTABLISHED")
        self.assertEqual(result["unresolved_observations"], 2)
        self.assertEqual(result["deferred_observations"], 1)
        self.assertEqual(result["linked_observations"], 4)
        self.assertEqual(result["surface_object_count"], 5)
        self.assertEqual(result["authority"], AUTHORITY)
        self.assertEqual(result["artifact"]["sha256"], sha(self.path))
        self.assertTrue(all(p.read_bytes() == data for p, data in before.items()))

    def test_missing_duplicate_or_wrong_namespace_observations_fail(self):
        for mutation in ("missing", "duplicate", "namespace", "bare", "unknown", "group_id"):
            with self.subTest(mutation=mutation):
                data = copy.deepcopy(self.data)
                if mutation == "missing": data["unresolved"].pop()
                elif mutation == "duplicate": data["unresolved"].append(copy.deepcopy(data["unresolved"][0]))
                elif mutation == "namespace": data["groups"][0]["source"]["collection"] = CANDIDATES
                elif mutation == "bare": data["groups"][0]["source"] = "T1"
                elif mutation == "unknown": data["groups"][0]["source"]["observation_id"] = "T99"
                else: data["groups"][1]["group_id"] = "heading"
                with self.assertRaises(DeckCompilerError): self.validate(data)

    def test_omitted_duplicate_wrong_slide_and_stale_object_pointers_fail(self):
        for mutation in ("omitted", "duplicate", "slide", "index", "leading_zero", "hash"):
            with self.subTest(mutation=mutation):
                data = copy.deepcopy(self.data)
                obj = data["groups"][0]["objects"][0]
                if mutation == "omitted": data["extras"] = []
                elif mutation == "duplicate": data["extras"].append(copy.deepcopy(data["extras"][0]))
                elif mutation == "slide": obj["pointer"] = "/slides/2/objects/0"
                elif mutation == "index": obj["pointer"] = "/slides/1/objects/90"
                elif mutation == "leading_zero": obj["pointer"] = "/slides/1/objects/00"
                else: obj["object_sha256"] = "0" * 64
                with self.assertRaises(DeckCompilerError): self.validate(data)

    def test_role_and_unique_glyph_membership_are_mechanical_checks(self):
        for mutation in ("text_to_panel", "graphic_to_text", "duplicate_glyph", "wrong_glyph_collection", "graphic_glyph", "graphic_group_member"):
            with self.subTest(mutation=mutation):
                data = copy.deepcopy(self.data)
                if mutation in ("text_to_panel", "graphic_to_text"):
                    data["groups"][0]["objects"], data["groups"][2]["objects"] = (
                        data["groups"][2]["objects"], data["groups"][0]["objects"])
                    if mutation == "graphic_to_text": data["groups"].reverse()
                elif mutation == "duplicate_glyph": data["groups"][1]["glyph_members"] = [ref(CANDIDATES, "U01")]
                elif mutation == "wrong_glyph_collection": data["groups"][0]["glyph_members"] = [ref("suppressed_text", "S1")]
                elif mutation == "graphic_glyph": data["groups"][0]["glyph_members"] = [ref(CANDIDATES, "U03")]
                else: data["groups"][2]["glyph_members"] = [ref(CANDIDATES, "U01")]
                with self.assertRaises(DeckCompilerError): self.validate(data)

    def test_disputed_or_unknown_observations_cannot_be_claimed_as_linked(self):
        for source in (ref("text_blocks", "T2"), ref(CANDIDATES, "U02")):
            data = copy.deepcopy(self.data)
            data["groups"][2]["source"] = source
            with self.subTest(source=source), self.assertRaises(DeckCompilerError): self.validate(data)
        self.data["extras"][0]["purpose"] = "unresolved"
        result = self.validate()
        self.assertEqual(result["unresolved_surface_objects"], 2)
        self.assertEqual(result["representation_status"], "NOT_ESTABLISHED")

    def test_all_provenance_digest_and_authority_changes_fail_closed(self):
        for key in self.data["bindings"]:
            data = copy.deepcopy(self.data); data["bindings"][key] = "0" * 64
            with self.subTest(binding=key), self.assertRaises(DeckCompilerError): self.validate(data)
        for key in ("job_id", "job_content_hash", "slide_number", "schema_name", "schema_version"):
            data = copy.deepcopy(self.data); data[key] = "stale"
            with self.subTest(field=key), self.assertRaises(DeckCompilerError): self.validate(data)
        for value in (True, 0, None, "false"):
            data = copy.deepcopy(self.data); data["authority"]["quality_accepted"] = value
            with self.subTest(authority=value), self.assertRaises(DeckCompilerError): self.validate(data)

    def test_changed_manifest_trace_fragment_or_review_cannot_be_silently_reused(self):
        self.validate()
        for path in (self.native_path, self.trace_path, self.work / "s1.fragment.js", self.project / "lib/slides.js", self.fixture.path):
            before = path.read_bytes(); path.write_bytes(before + b"\n")
            with self.subTest(path=path.name), self.assertRaises(DeckCompilerError): self.validate()
            path.write_bytes(before)
        native = read_json(self.native_path)
        native["slides"]["1"]["objects"].reverse()
        write_json(self.native_path, native)
        trace = read_json(self.trace_path); trace["nativeObjectManifestHash"] = sha(self.native_path)
        write_json(self.trace_path, trace)
        self.data["bindings"]["native_manifest_sha256"] = sha(self.native_path)
        self.data["bindings"]["render_trace_sha256"] = sha(self.trace_path)
        with self.assertRaisesRegex(DeckCompilerError, "object.*sha256"): self.validate()

    def test_resealed_trace_must_bind_manifest_and_integrated_source(self):
        for key in ("nativeObjectManifestHash", "slidesJs", "projectRoot"):
            before = self.trace_path.read_bytes(); trace = read_json(self.trace_path)
            if key == "slidesJs": trace["hashes"][key] = "0" * 64
            else: trace[key] = "incorrect"
            write_json(self.trace_path, trace); self.data["bindings"]["render_trace_sha256"] = sha(self.trace_path)
            with self.subTest(key=key), self.assertRaises(DeckCompilerError): self.validate()
            self.trace_path.write_bytes(before)

    def test_text_cannot_be_decorative_or_background_and_empty_groups_fail(self):
        for purpose in ("decorative", "background"):
            data = copy.deepcopy(self.data)
            data["groups"].pop(0)
            for source in (ref("text_blocks", "T1"), ref(CANDIDATES, "U01")):
                data["unresolved"].append({"source": source, "disposition": "unresolved", "objects": [], "reason": "No text link asserted"})
            data["extras"].append({"object": pointer(0, self.objects[0]), "purpose": purpose, "reason": "Claim"})
            with self.subTest(purpose=purpose), self.assertRaises(DeckCompilerError): self.validate(data)
        self.data["groups"][0]["objects"] = []
        with self.assertRaises(DeckCompilerError): self.validate()

    def test_colliding_ids_in_distinct_source_namespaces_remain_valid(self):
        self.fixture.inventory["text_blocks"][0]["id"] = "U01"
        self.fixture.reseal_inventory()
        self.fixture.review["measurement_inventory_sha256"] = sha(self.fixture.inventory_path)
        self.fixture.review["region_candidate_evidence_sha256"] = content_sha256(self.fixture.inventory["region_candidate_evidence"])
        self.fixture.review["decisions"][0]["observation_id"] = "U01"
        self.job = self.fixture.build()["job"]
        fresh = accounting(self.root, self.job, self.work)
        for key in ("job_id", "job_content_hash", "bindings"): self.data[key] = fresh[key]
        self.data["groups"][0]["source"] = ref("text_blocks", "U01")
        self.assertEqual(self.validate()["linked_observations"], 4)

    def test_unreviewed_observation_requires_explicit_unresolved_entry(self):
        self.fixture.review["coverage"] = "partial"
        self.fixture.review["decisions"].pop()
        self.job = self.fixture.build()["job"]
        fresh = accounting(self.root, self.job, self.work)
        for key in ("job_id", "job_content_hash", "bindings"): self.data[key] = fresh[key]
        with self.assertRaisesRegex(DeckCompilerError, "remain unresolved"): self.validate()
        group = self.data["groups"].pop()
        self.data["unresolved"].append({"source": group["source"], "disposition": "unresolved",
                                       "objects": group["objects"], "reason": "No reviewed classification"})
        self.assertEqual(self.validate()["unresolved_observations"], 3)

    def test_resealed_manifest_rejects_bad_geometry_and_noneditable_or_empty_text(self):
        original_native, original_trace = self.native_path.read_bytes(), self.trace_path.read_bytes()
        for field, value in (("x", False), ("textLength", -1), ("x", 10 ** 400), ("editable", 1),
                             ("type", "invented"), ("editable", False), ("textLength", 0)):
            with self.subTest(field=field, value=str(value)[:20]):
                native = read_json(self.native_path)
                native["slides"]["1"]["objects"][0][field] = value
                write_json(self.native_path, native)
                trace = read_json(self.trace_path); trace["nativeObjectManifestHash"] = sha(self.native_path)
                write_json(self.trace_path, trace)
                data = copy.deepcopy(self.data)
                data["bindings"]["native_manifest_sha256"] = sha(self.native_path)
                data["bindings"]["render_trace_sha256"] = sha(self.trace_path)
                data["groups"][0]["objects"][0] = pointer(0, native["slides"]["1"]["objects"][0])
                with self.assertRaises(DeckCompilerError): self.validate(data)
                self.native_path.write_bytes(original_native); self.trace_path.write_bytes(original_trace)

    def test_absence_is_noop_and_present_nonregular_or_malformed_fails_before_read(self):
        module = importlib.import_module("presentation_agent.deckcompiler.orchestration.surface_call_accounting")
        with patch.object(Path, "read_bytes", side_effect=AssertionError("absence must not read dependencies")):
            self.assertIsNone(module.validate_surface_call_accounting(self.root, {}, self.work))
        self.path.mkdir()
        with self.assertRaises(DeckCompilerError): module.validate_surface_call_accounting(self.root, self.job, self.work)
        self.path.rmdir()
        self.path.symlink_to(self.work / "missing")
        with self.assertRaises(DeckCompilerError): module.validate_surface_call_accounting(self.root, self.job, self.work)
        self.path.unlink()
        if hasattr(os, "mkfifo"):
            os.mkfifo(self.path)
            with patch.object(Path, "read_bytes", side_effect=AssertionError("FIFO read")) as read:
                with self.assertRaises(DeckCompilerError): module.validate_surface_call_accounting(self.root, self.job, self.work)
                read.assert_not_called()
            self.path.unlink()
        for raw in ('{', '[]', '{"groups":[],"groups":[]}'):
            self.path.write_text(raw)
            with self.subTest(raw=raw), self.assertRaises(DeckCompilerError): module.validate_surface_call_accounting(self.root, self.job, self.work)

    def public_fixture(self):
        class Fixture(workflow_fixtures.GeneralGenerateWorkflowTests):
            @staticmethod
            def _make_raw_pipeline(root):
                pipeline = workflow_fixtures.GeneralGenerateWorkflowTests._make_raw_pipeline(root)
                detector = pipeline / "scripts/detect_elements.py"
                detector.write_text(detector.read_text() + '''
import hashlib
_original = build_inventory
def build_inventory(image_path, backend="easyocr", canvas="native", reader=None, deep_text=False):
    inventory, image = _original(image_path, backend, canvas, reader, deep_text)
    inventory["text_blocks"] = [{"id": "T1", "text": "Invented heading", "bbox_px": {"x": 20, "y": 20, "w": 100, "h": 20}}]
    inventory["region_candidate_evidence"] = {
        "schema_version": 1, "status": "unadjudicated", "method": "detect_regions_without_ocr_mask",
        "canvas_px": {"w": image.width, "h": image.height}, "canvas_rgb_sha256": hashlib.sha256(image.tobytes()).hexdigest(),
        "min_area_fraction": 0.0004, "notes": ["Synthetic contract evidence"], "candidates": [],
        "authority": {"text_removal": False, "native_admission": False, "vector_eligibility": False, "quality_accepted": False}}
    return inventory, image
''')
                return pipeline
        helper = Fixture(); runtime = self.root / "public-flow"
        started = helper._start(runtime)
        helper._build_run_draft(runtime, workflow_id=started.workflow_id, slide_count=1,
                                status="COMPLETED", qa_status="PASS", fail_count=0, blocking_count=0)
        project = runtime / "pngtopptx-project"; work = project / "work/slide01"
        return runtime, project, work

    def test_public_completion_and_finalization_reject_present_malformed_artifact(self):
        root, project, work = self.public_fixture()
        self.assertTrue(jobs.validate_reconstruction_job_bundle(root, require_worker_outputs=True)["valid"])
        (work / NAME).write_text('{"malformed":true}')
        self.assertTrue(jobs.validate_reconstruction_job_bundle(root, require_authoring_outputs=True)["valid"])
        report = jobs.validate_reconstruction_job_bundle(root, require_worker_outputs=True)
        with self.subTest(gate="completion"):
            self.assertFalse(report["valid"], report)
        with self.subTest(gate="shared-finalization"), self.assertRaisesRegex(DeckCompilerError, "surface.call accounting"):
            finalize_shared_render_qa(root, summary_path=project / "out/visual_qa_summary_final.json")

    def test_finalizer_seals_optin_and_completion_rechecks_exact_artifact(self):
        root, project, work = self.public_fixture()
        job = read_json(work / "reconstruction_job.json")
        inventory = read_json(root / job["vector_preflight"]["measurement_inventory"]["path"])
        evidence = inventory["region_candidate_evidence"]
        review = copy.deepcopy(self.fixture.review)
        review.update({"workflow_id": job["workflow_id"], "slide_number": job["slide_number"],
            "slide_id": job["slide_id"], "request_id": job["request_lineage"]["request_id"],
            "source_png_sha256": job["source_png"]["sha256"], "semantic_sidecar_sha256": job["semantic_sidecar"]["sha256"],
            "measurement_inventory_sha256": job["vector_preflight"]["measurement_inventory"]["sha256"],
            "region_candidate_evidence_sha256": content_sha256(evidence), "canvas_px": evidence["canvas_px"],
            "canvas_rgb_sha256": evidence["canvas_rgb_sha256"], "coverage": "complete",
            "decisions": [self.fixture.decision("text_blocks", "T1", "text")]})
        write_json(work / review_fixtures.NAME, review)
        jobs.prepare_reconstruction_jobs(root); job = read_json(work / "reconstruction_job.json")
        objects = read_json(project / "out/native_object_manifest.json")["slides"]["1"]["objects"]
        data = accounting(root, job, work)
        data["groups"] = [{"group_id": "heading", "source": ref("text_blocks", "T1"),
                           "glyph_members": [], "objects": [pointer(0, objects[0])], "reason": "Explicit call claim"}]
        data["extras"] = [{"object": pointer(i, obj), "purpose": "unresolved" if obj["type"] == "text" else "decorative",
                           "reason": "No source identity asserted"} for i, obj in enumerate(objects) if i]
        write_json(work / NAME, data)
        result = finalize_shared_render_qa(root, summary_path=project / "out/visual_qa_summary_final.json")
        receipt = read_json(result.receipt_paths[0])
        self.assertIn(NAME, receipt["artifacts"])
        self.assertEqual(receipt["artifactHashes"][NAME], sha(work / NAME))
        self.assertEqual(receipt["surfaceCallAccounting"]["representation_status"], "NOT_ESTABLISHED")
        self.assertTrue(jobs.validate_reconstruction_job_bundle(root, require_worker_outputs=True)["valid"])
        (work / NAME).write_bytes((work / NAME).read_bytes() + b"\n")
        self.assertFalse(jobs.validate_reconstruction_job_bundle(root, require_worker_outputs=True)["valid"])
        write_json(work / NAME, data)
        receipt["surfaceCallAccounting"]["authority"]["semantic_truth"] = True
        write_json(work / "worker_receipt.json", receipt)
        self.assertFalse(jobs.validate_reconstruction_job_bundle(root, require_worker_outputs=True)["valid"])
        (work / NAME).unlink()
        self.assertFalse(jobs.validate_reconstruction_job_bundle(root, require_worker_outputs=True)["valid"])


if __name__ == "__main__":
    unittest.main()
