"""Invented review-boundary fixtures; no recognition, render or semantic-pass claim."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
import test_semantic_geometry_binding as fixtures
from presentation_agent.deckcompiler.errors import DeckCompilerError
from presentation_agent.deckcompiler.identity import content_sha256
from presentation_agent.deckcompiler.manifest_io import read_json, write_json
from presentation_agent.deckcompiler.orchestration import reconstruction_jobs as jobs


NAME = "region_classification_review.json"
CANDIDATES = "region_candidate_evidence.candidates"
AUTHORITY = {key: False for key in (
    "text_removal", "native_admission", "vector_eligibility", "quality_accepted")}


class RegionClassificationReviewTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.SemanticGeometryBindingTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        self.work = self.root / "pngtopptx-project/work/slide01"
        self.path = self.work / NAME
        self.inventory_path = self.root / self.fixture.args[1]["vector_row"]["measurement_inventory"]["path"]
        self.inventory = read_json(self.inventory_path)
        self.inventory["suppressed_text"] = [{
            "id": "S1", "text": "Genuine label", "bbox_px": {"x": 16, "y": 150, "w": 50, "h": 15}}]
        source = self.root / "pngtopptx-project/src/slide1.png"
        with Image.open(source) as image:
            rgb = hashlib.sha256(image.convert("RGB").tobytes()).hexdigest()
        boxes = [
            {"x": 20, "y": 12, "w": 8, "h": 16},  # a genuine glyph within T1
            {"x": 22, "y": 72, "w": 44, "h": 20}, # disputed geometry within T2
            {"x": 240, "y": 152, "w": 36, "h": 16}, # separate graphic proposal
        ]
        self.inventory["region_candidate_evidence"] = {
            "schema_version": 1, "status": "unadjudicated",
            "method": "detect_regions_without_ocr_mask", "canvas_px": {"w": 320, "h": 180},
            "canvas_rgb_sha256": rgb, "min_area_fraction": 0.0004,
            "notes": ["Invented contract evidence, not detector output"], "authority": AUTHORITY.copy(),
            "candidates": [{"candidate_id": f"U{i:02d}", "measurement": {
                "id": f"R{i:02d}", "kind_hint": "flat_shape", "confidence": 0.99,
                "bbox_px": box, "bbox_norm": {k: round(v / (320 if k in ("x", "w") else 180), 4) for k, v in box.items()}},
                "overlapping_ocr_mask_ids": [], "overlapping_masked_region_ids": []}
                for i, box in enumerate(boxes, 1)],
        }
        self.reseal_inventory()
        self.default = self.fixture.build()
        job = self.default["job"]
        self.review = {
            "schema_name": "codex_region_classification_review", "schema_version": "1.0.0",
            "workflow_id": job["workflow_id"], "slide_number": job["slide_number"], "slide_id": job["slide_id"],
            "request_id": job["request_lineage"]["request_id"],
            "source_png_sha256": job["source_png"]["sha256"],
            "semantic_sidecar_sha256": job["semantic_sidecar"]["sha256"],
            "measurement_inventory_sha256": job["vector_preflight"]["measurement_inventory"]["sha256"],
            "region_candidate_evidence_sha256": content_sha256(self.inventory["region_candidate_evidence"]),
            "canvas_px": {"w": 320, "h": 180}, "canvas_rgb_sha256": rgb,
            "origin": "assistant_mediated", "method": "assistant_visual_review",
            "reviewer": {"name": "Synthetic reviewer", "reviewed_at": "2026-08-12T09:10:11Z"},
            "coverage": "partial", "authority": AUTHORITY.copy(),
            "decisions": [self.decision("text_blocks", "T1", "text"), self.decision(CANDIDATES, "U01", "text")],
        }

    @staticmethod
    def decision(collection, ident, role):
        return {"collection": collection, "observation_id": ident, "role": role, "reason": "Invented visual-review claim"}

    def reseal_inventory(self):
        write_json(self.inventory_path, self.inventory)
        self.fixture.args[1]["vector_row"]["measurement_inventory"] = self.fixture.artifact(self.inventory_path)

    def build(self, review=None):
        write_json(self.path, self.review if review is None else review)
        return self.fixture.build()

    def test_absence_is_default_off_and_does_not_consume_author_claims(self):
        write_json(self.work / "measurements.json", {"authorClassification": [{"classification": "graphic"}]})
        self.assertEqual(self.fixture.build(), self.default)
        self.assertNotIn("region_classification_review", self.default["job"])
        self.build()
        self.path.unlink()
        self.assertEqual(self.fixture.build(), self.default)

    def test_review_is_bound_without_mutating_protected_inputs_or_admitting_assets(self):
        before = self.inventory_path.read_bytes()
        row = self.build()
        bound = row["job"]["region_classification_review"]
        self.assertEqual(bound["status"], "STRUCTURALLY_BOUND_REVIEW")
        self.assertEqual(bound["review_artifact"], self.fixture.artifact(self.path))
        self.assertEqual(bound["provenance_attestation"], "unverified_declarations")
        self.assertIs(bound["semantic_truth_verified"], False)
        self.assertEqual(bound["authority"], AUTHORITY)
        self.assertEqual(bound["coverage"]["observation_count"], 6)
        self.assertEqual(bound["coverage"]["reviewed_count"], 2)
        self.assertEqual(len(bound["coverage"]["unreviewed"]), 4)
        self.assertEqual(bound["conflicts"], [])
        self.assertEqual(self.inventory_path.read_bytes(), before)
        for field in ("vector_preflight", "semantic_geometry_binding", "authoring_contract", "required_outputs"):
            self.assertEqual(row["job"][field], self.default["job"][field])
        self.assertNotEqual(row["job"]["content_hash"], self.default["job"]["content_hash"])
        self.assertIn("unverified declarations", row["worker_prompt"])
        self.assertIn("Do not remove OCR protection", row["worker_prompt"])

    def test_genuine_text_and_glyph_graphic_claims_stay_explicitly_unresolved(self):
        self.review["decisions"] = [self.decision("text_blocks", "T1", "graphic"),
            self.decision(CANDIDATES, "U01", "graphic"), self.decision("suppressed_text", "S1", "mixed")]
        bound = self.build()["job"]["region_classification_review"]
        reasons = {row["reason"] for row in bound["conflicts"]}
        self.assertIn("protected_text_classified_nontext", reasons)
        self.assertIn("graphic_candidate_overlaps_protected_text", reasons)
        self.assertTrue(all(row["review_status"] == "needs_review" for row in bound["decisions"]))
        self.assertEqual(bound["authority"], AUTHORITY)

    def test_partial_complete_and_uncertain_coverage_are_not_semantic_acceptance(self):
        self.review["decisions"] = []
        self.assertEqual(len(self.build()["job"]["region_classification_review"]["coverage"]["unreviewed"]), 6)
        self.review["coverage"] = "complete"
        with self.assertRaisesRegex(DeckCompilerError, "complete coverage"):
            self.build()
        self.review["decisions"] = [self.decision(c, ident, "uncertain") for c, ids in (
            ("text_blocks", ["T1", "T2"]), ("suppressed_text", ["S1"]), (CANDIDATES, ["U01", "U02", "U03"])) for ident in ids]
        bound = self.build()["job"]["region_classification_review"]
        self.assertEqual(bound["coverage"]["unreviewed"], [])
        self.assertEqual(len(bound["coverage"]["needs_review"]), 6)
        self.assertIs(bound["semantic_truth_verified"], False)

    def test_rejects_digest_lineage_frame_and_provenance_mismatches(self):
        for key in ("workflow_id", "slide_number", "slide_id", "request_id", "source_png_sha256",
                    "semantic_sidecar_sha256", "measurement_inventory_sha256", "region_candidate_evidence_sha256",
                    "canvas_px", "canvas_rgb_sha256", "origin", "method", "reviewer", "coverage", "schema_version"):
            with self.subTest(field=key):
                review = copy.deepcopy(self.review)
                review[key] = {"w": 321, "h": 180} if key == "canvas_px" else "incorrect"
                with self.assertRaises(DeckCompilerError): self.build(review)
        for key in ("slide_number",):
            review = copy.deepcopy(self.review); review[key] = True
            with self.assertRaises(DeckCompilerError): self.build(review)

    def test_rejects_unknown_duplicate_or_malformed_decisions(self):
        for mutation in ("unknown_id", "wrong_collection", "duplicate", "bad_role", "empty_reason", "extra", "numeric_id", "nonobject"):
            with self.subTest(mutation=mutation):
                review = copy.deepcopy(self.review); first = review["decisions"][0]
                if mutation == "unknown_id": first["observation_id"] = "T99"
                elif mutation == "wrong_collection": first["collection"] = "regions"
                elif mutation == "duplicate": review["decisions"].append(copy.deepcopy(first))
                elif mutation == "bad_role": first["role"] = "accepted_vector"
                elif mutation == "empty_reason": first["reason"] = " "
                elif mutation == "extra": first["remove_text"] = True
                elif mutation == "numeric_id": first["observation_id"] = 1
                else: review["decisions"][0] = None
                with self.assertRaises(DeckCompilerError): self.build(review)

    def test_rejects_authority_escalation_and_ambiguous_json(self):
        for value in (True, 0, None, "false"):
            review = copy.deepcopy(self.review); review["authority"]["text_removal"] = value
            with self.subTest(value=value), self.assertRaises(DeckCompilerError): self.build(review)
        for raw in ('{', '[]', '{"coverage":"partial","coverage":"complete"}'):
            self.path.write_text(raw)
            with self.subTest(raw=raw), self.assertRaises(DeckCompilerError): self.fixture.build()

    def test_stale_source_or_inventory_is_not_resealed_by_review(self):
        self.build()
        source = self.root / "pngtopptx-project/src/slide1.png"
        original_source = source.read_bytes()
        Image.new("RGB", (320, 180), (49, 63, 75)).save(source)
        # Update the accepted-call input so the review's bound source hash is
        # tested, rather than the earlier image-intake check.
        self.fixture.args[1]["call"]["selected_png_sha256"] = self.fixture.sha(source)
        with self.assertRaises(DeckCompilerError): self.fixture.build()
        source.write_bytes(original_source)
        self.fixture.args[1]["call"]["selected_png_sha256"] = self.fixture.sha(source)
        self.inventory["text_blocks"][0]["text"] = "Changed genuine text"
        write_json(self.inventory_path, self.inventory)
        with self.assertRaisesRegex(DeckCompilerError, "sha256"):
            self.fixture.build()
        self.reseal_inventory()
        with self.assertRaisesRegex(DeckCompilerError, "measurement_inventory_sha256"):
            self.fixture.build()

    def test_resealed_evidence_with_bad_rgb_or_duplicate_source_ids_fails(self):
        for mutation in ("rgb", "duplicate_text", "missing_id", "missing_evidence"):
            with self.subTest(mutation=mutation):
                original = copy.deepcopy(self.inventory)
                if mutation == "rgb": self.inventory["region_candidate_evidence"]["canvas_rgb_sha256"] = "0" * 64
                elif mutation == "duplicate_text": self.inventory["text_blocks"].append(copy.deepcopy(self.inventory["text_blocks"][0]))
                elif mutation == "missing_id": del self.inventory["text_blocks"][0]["id"]
                else: self.inventory.pop("region_candidate_evidence")
                self.reseal_inventory()
                review = copy.deepcopy(self.review)
                review["measurement_inventory_sha256"] = self.fixture.sha(self.inventory_path)
                if "region_candidate_evidence" in self.inventory:
                    review["region_candidate_evidence_sha256"] = content_sha256(self.inventory["region_candidate_evidence"])
                with self.assertRaises(DeckCompilerError): self.build(review)
                self.inventory = original; self.reseal_inventory()

    def test_review_file_bytes_and_claims_change_job_binding(self):
        first = self.build()
        self.path.write_text(json.dumps(self.review, separators=(",", ":")))
        second = self.fixture.build()
        self.assertNotEqual(first["job"]["content_hash"], second["job"]["content_hash"])
        self.assertEqual(first["job"]["region_classification_review"]["decisions"], second["job"]["region_classification_review"]["decisions"])
        self.review["origin"] = "user_review"; self.review["method"] = "user_visual_region_review"
        third = self.build()
        self.assertEqual(third["job"]["region_classification_review"]["provenance_attestation"], "unverified_declarations")

    def test_inconsistent_candidate_roles_remain_conflicts_without_trusting_links(self):
        self.inventory["region_candidate_evidence"]["candidates"][2]["measurement"] = copy.deepcopy(
            self.inventory["region_candidate_evidence"]["candidates"][1]["measurement"])
        self.reseal_inventory()
        self.review["measurement_inventory_sha256"] = self.fixture.sha(self.inventory_path)
        self.review["region_candidate_evidence_sha256"] = content_sha256(self.inventory["region_candidate_evidence"])
        self.review["decisions"] = [self.decision(CANDIDATES, "U02", "text"), self.decision(CANDIDATES, "U03", "graphic")]
        bound = self.build()["job"]["region_classification_review"]
        self.assertIn("inconsistent_overlap_roles", [r["reason"] for r in bound["conflicts"]])
        self.assertTrue(all(r["review_status"] == "needs_review" for r in bound["decisions"]))

    def test_separate_graphic_claim_does_not_change_vector_admission_or_text_protection(self):
        from presentation_agent.deckcompiler.orchestration.vector_preflight import _semantic_boxes
        protected = _semantic_boxes(self.inventory, 320, 180)
        self.review["decisions"] = [self.decision(CANDIDATES, "U03", "graphic")]
        job = self.build()["job"]
        bound = job["region_classification_review"]
        self.assertEqual(bound["conflicts"], [])
        self.assertEqual(bound["decisions"][0]["review_status"], "recorded")
        self.assertEqual(_semantic_boxes(read_json(self.inventory_path), 320, 180), protected)
        self.assertEqual(job["vector_preflight"]["regions"], [])
        usage = {"slide": 1, "policyId": job["vector_preflight"]["policy_id"],
            "vectorPreflightSha256": job["receipt_binding"]["vector_preflight_sha256"],
            "vectorSlideContentHash": job["receipt_binding"]["vector_slide_content_hash"],
            "measurementInventorySha256": job["vector_preflight"]["measurement_inventory"]["sha256"],
            "measuredCoordinatesAuthoritative": True, "usedRegions": [{"regionId": "U03", "assetSha256": "0" * 64}],
            "deferredRegions": [], "parametricIconUses": []}
        issues = []
        jobs._validate_vector_usage(usage, job, "synthetic", issues)
        self.assertTrue(any("non-approved SVG region" in issue for issue in issues), issues)

    def test_present_nonfile_and_broken_symlink_fail_closed(self):
        self.path.mkdir()
        with self.assertRaises(DeckCompilerError): self.fixture.build()
        self.path.rmdir()
        self.path.symlink_to(self.work / "missing-review.json")
        with self.assertRaises(DeckCompilerError): self.fixture.build()

    @unittest.skipUnless(hasattr(os, "mkfifo"), "POSIX named pipe required")
    def test_named_pipe_is_rejected_before_any_read(self):
        from presentation_agent.deckcompiler.orchestration.region_classification_review import bind_region_classification_review
        os.mkfifo(self.path)
        # A read tripwire makes this regression fail immediately instead of
        # hanging the test runner while a FIFO waits indefinitely for a writer.
        with patch.object(Path, "read_bytes", side_effect=AssertionError("attempted FIFO read")) as read:
            with self.assertRaisesRegex(DeckCompilerError, "regular file"):
                bind_region_classification_review(self.root, self.default["job"], self.work)
            read.assert_not_called()

    def test_public_job_validation_binds_review_and_rejects_stale_worker_receipts(self):
        import test_general_generate_workflow as upstream

        class Fixture(upstream.GeneralGenerateWorkflowTests):
            @staticmethod
            def _make_raw_pipeline(root):
                pipeline = upstream.GeneralGenerateWorkflowTests._make_raw_pipeline(root)
                detector = pipeline / "scripts/detect_elements.py"
                # Synthetic adapter contract only; no OCR or renderer runs.
                detector.write_text(detector.read_text() + '''
import hashlib
_original = build_inventory
def build_inventory(image_path, backend="easyocr", canvas="native", reader=None, deep_text=False):
    inventory, image = _original(image_path, backend, canvas, reader, deep_text)
    inventory["text_blocks"] = [{"id": "T1", "text": "Synthetic heading", "bbox_px": {"x": 20, "y": 20, "w": 100, "h": 20}}]
    inventory["region_candidate_evidence"] = {
        "schema_version": 1, "status": "unadjudicated", "method": "detect_regions_without_ocr_mask",
        "canvas_px": {"w": image.width, "h": image.height}, "canvas_rgb_sha256": hashlib.sha256(image.tobytes()).hexdigest(),
        "min_area_fraction": 0.0004, "notes": ["Synthetic contract evidence"], "candidates": [],
        "authority": {"text_removal": False, "native_admission": False, "vector_eligibility": False, "quality_accepted": False}}
    return inventory, image
''')
                return pipeline

        helper = Fixture()
        runtime = self.root / "public-flow"
        started = helper._start(runtime)
        helper._build_run_draft(runtime, workflow_id=started.workflow_id, slide_count=1,
                                status="COMPLETED", qa_status="PASS", fail_count=0, blocking_count=0)
        self.assertTrue(jobs.validate_reconstruction_job_bundle(runtime, require_worker_outputs=True)["valid"])
        work = runtime / "pngtopptx-project/work/slide01"
        job = read_json(work / "reconstruction_job.json")
        original_job = (work / "reconstruction_job.json").read_bytes()
        original_prompt = (work / "worker_prompt.md").read_bytes()
        original_inputs = {r["path"]: (runtime / r["path"]).read_bytes() for r in (
            job["source_png"], job["semantic_sidecar"], job["vector_preflight"]["measurement_inventory"])}
        inventory = read_json(runtime / job["vector_preflight"]["measurement_inventory"]["path"])
        evidence = inventory["region_candidate_evidence"]
        review = {**self.review, "workflow_id": job["workflow_id"], "slide_number": job["slide_number"],
            "slide_id": job["slide_id"], "request_id": job["request_lineage"]["request_id"],
            "source_png_sha256": job["source_png"]["sha256"], "semantic_sidecar_sha256": job["semantic_sidecar"]["sha256"],
            "measurement_inventory_sha256": job["vector_preflight"]["measurement_inventory"]["sha256"],
            "region_candidate_evidence_sha256": content_sha256(evidence), "canvas_px": evidence["canvas_px"],
            "canvas_rgb_sha256": evidence["canvas_rgb_sha256"], "coverage": "complete",
            "decisions": [self.decision("text_blocks", "T1", "text")]}
        review_path = write_json(work / NAME, review)
        self.assertFalse(jobs.validate_reconstruction_job_bundle(runtime)["valid"])
        jobs.prepare_reconstruction_jobs(runtime)
        self.assertTrue(jobs.validate_reconstruction_job_bundle(runtime)["valid"])
        stale = jobs.validate_reconstruction_job_bundle(runtime, require_worker_outputs=True)
        self.assertFalse(stale["valid"])
        self.assertTrue(any("jobContentHash" in issue for issue in stale["issues"]), stale)
        # Even whitespace-only review edits invalidate the exact artifact binding.
        review_path.write_text(json.dumps(review))
        self.assertFalse(jobs.validate_reconstruction_job_bundle(runtime)["valid"])
        review["decisions"][0]["observation_id"] = "missing"
        write_json(review_path, review)
        self.assertFalse(jobs.validate_reconstruction_job_bundle(runtime)["valid"])
        with self.assertRaises(DeckCompilerError): jobs.prepare_reconstruction_jobs(runtime)
        review_path.unlink()
        jobs.prepare_reconstruction_jobs(runtime)
        self.assertEqual((work / "reconstruction_job.json").read_bytes(), original_job)
        self.assertEqual((work / "worker_prompt.md").read_bytes(), original_prompt)
        self.assertTrue(all((runtime / p).read_bytes() == data for p, data in original_inputs.items()))


if __name__ == "__main__":
    unittest.main()
