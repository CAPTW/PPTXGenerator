"""Synthetic source-reference derivation; no renderer or semantic acceptance."""
from __future__ import annotations

import copy
import importlib
import os
import unittest
from unittest.mock import patch

import test_surface_call_accounting as fixtures
from presentation_agent.deckcompiler.errors import DeckCompilerError
from presentation_agent.deckcompiler.manifest_io import read_json, write_json
from presentation_agent.deckcompiler.orchestration import reconstruction_jobs as jobs
from presentation_agent.deckcompiler.orchestration import shared_render_qa as shared


class SourceRefDerivationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.SurfaceCallAccountingTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        f = self.fixture
        self.root, self.work, self.job = f.root, f.work, f.job
        self.objects = copy.deepcopy(f.objects)
        claims = [
            self.claim("heading", "text_blocks", "T1", members=[fixtures.ref(fixtures.CANDIDATES, "U01")]),
            self.claim("label", "suppressed_text", "S1"),
            self.claim("graphic", fixtures.CANDIDATES, "U03"),
            self.claim("pending", fixtures.CANDIDATES, "U02", disposition="unresolved"),
            {"kind": "extra", "groupId": "ornament", "purpose": "decorative"},
        ]
        for obj, claim in zip(self.objects, claims):
            obj["sourceRefs"] = self.tag(claim)
        self.seal()

    def api(self):
        return importlib.import_module("presentation_agent.deckcompiler.orchestration.source_ref_derivation")

    @staticmethod
    def claim(group, collection, ident, members=None, disposition="linked"):
        return {"kind": "observation", "groupId": group, "source": fixtures.ref(collection, ident),
                "glyphMembers": members or [], "disposition": disposition}

    def tag(self, claim):
        return {"schemaVersion": "slide-image-dual-render.source-refs.v1", "slide": 1,
                "bindings": {"jobContentHash": self.job["content_hash"],
                    "sourcePngSha256": self.job["source_png"]["sha256"],
                    "measurementInventorySha256": self.job["vector_preflight"]["measurement_inventory"]["sha256"],
                    "reviewArtifactSha256": self.job["region_classification_review"]["review_artifact"]["sha256"]},
                "claim": claim, "authority": fixtures.AUTHORITY.copy()}

    def seal(self):
        f = self.fixture
        native = read_json(f.native_path)
        native["slides"]["1"]["objects"] = self.objects
        write_json(f.native_path, native)
        trace = read_json(f.trace_path)
        trace["nativeObjectManifestHash"] = fixtures.sha(f.native_path)
        write_json(f.trace_path, trace)

    def derive(self):
        return self.api().derive_surface_call_accounting(self.root, self.job, self.work)

    def prepare(self):
        return self.api().prepare_surface_call_accounting(self.root, self.job, self.work)

    def validate(self):
        return self.api().validate_source_ref_accounting(self.root, self.job, self.work)

    def test_derivation_is_pure_and_existing_consumer_accepts_every_row(self):
        before = {p: p.read_bytes() for p in (self.fixture.fixture.inventory_path,
            self.fixture.fixture.path, self.work / "s1.fragment.js", self.fixture.native_path)}
        data = self.derive()
        self.assertFalse(self.fixture.path.exists())
        self.assertEqual([len(g["objects"]) for g in data["groups"]], [1, 1, 1])
        self.assertEqual(len(data["unresolved"]), 2)
        self.assertEqual(data["authority"], fixtures.AUTHORITY)
        result = self.prepare()
        self.assertEqual(result["representation_status"], "NOT_ESTABLISHED")
        self.assertEqual(result["unresolved_observations"], 2)
        self.assertEqual(result["surface_object_count"], 5)
        self.assertEqual(result, self.validate())
        self.assertEqual(result, self.fixture.validate(data))
        self.assertTrue(all(p.read_bytes() == raw for p, raw in before.items()))

    def test_repeated_group_calls_expand_and_unannotated_rows_stay_unresolved(self):
        self.objects.append(copy.deepcopy(self.objects[2]))
        del self.objects[1]["sourceRefs"]
        self.seal()
        data = self.derive()
        graphic = next(g for g in data["groups"] if g["group_id"] == "graphic")
        self.assertEqual([r["pointer"] for r in graphic["objects"]], ["/slides/1/objects/2", "/slides/1/objects/5"])
        label = next(r for r in data["unresolved"] if r["source"] == fixtures.ref("suppressed_text", "S1"))
        self.assertEqual(label["objects"], [])
        self.assertEqual(next(r for r in data["extras"] if r["object"]["pointer"].endswith("/1"))["purpose"], "unresolved")
        self.assertEqual(self.prepare()["representation_status"], "NOT_ESTABLISHED")

    def test_no_tags_preserves_absence_and_existing_manual_ledger_bytes(self):
        for obj in self.objects: obj.pop("sourceRefs")
        self.seal()
        self.assertIsNone(self.derive())
        self.assertIsNone(self.prepare())
        self.assertIsNone(self.validate())
        self.assertFalse(self.fixture.path.exists())
        # Rebuild only the old fixture ledger's file bindings after the synthetic reseal.
        self.fixture.data["bindings"] = fixtures.accounting(self.root, self.job, self.work)["bindings"]
        expected = self.fixture.validate()
        old = self.fixture.path.read_bytes()
        self.assertEqual(expected, self.prepare())
        self.assertEqual(expected, self.validate())
        self.assertEqual(old, self.fixture.path.read_bytes())

    def test_present_null_empty_or_malformed_tags_never_disable_optin(self):
        self.api()
        for value in (None, {}, [], "", False, {"schemaVersion": "unknown"}):
            with self.subTest(value=value):
                self.objects[0]["sourceRefs"] = value; self.seal()
                with self.assertRaises(DeckCompilerError): self.prepare()
                with self.assertRaises(DeckCompilerError): self.validate()
                self.assertFalse(self.fixture.path.exists())

    def test_tag_bindings_slide_authority_and_transport_shape_fail_closed(self):
        self.api()
        original = copy.deepcopy(self.objects[0]["sourceRefs"])
        cases = [("bindings", key, "0" * 64) for key in original["bindings"]]
        cases += [("top", "slide", x) for x in (True, 1.0, 2, "1")]
        cases += [("authority", "text_removal", x) for x in (True, 0, None)]
        cases += [("top", "unknown", False), ("top", "schemaVersion", "wrong"),
                  ("claim", "groupId", "x" * 66000)]
        for section, key, value in cases:
            with self.subTest(section=section, key=key, value=str(value)[:30]):
                tag = copy.deepcopy(original)
                (tag if section == "top" else tag[section])[key] = value
                self.objects[0]["sourceRefs"] = tag; self.seal()
                with self.assertRaises(DeckCompilerError): self.prepare()
                self.assertFalse(self.fixture.path.exists())

    def test_namespace_identity_group_and_glyph_ownership_are_unique(self):
        self.api()
        original = copy.deepcopy(self.objects)
        for mode in ("unknown", "namespace", "bare", "group_conflict", "duplicate_owner", "duplicate_glyph", "unresolved_glyph"):
            with self.subTest(mode=mode):
                self.objects = copy.deepcopy(original)
                claim = self.objects[0]["sourceRefs"]["claim"]
                if mode == "unknown": claim["source"]["observation_id"] = "T99"
                elif mode == "namespace": claim["source"]["collection"] = fixtures.CANDIDATES
                elif mode == "bare": claim["source"] = "T1"
                elif mode == "group_conflict": self.objects[1]["sourceRefs"]["claim"]["groupId"] = "heading"
                elif mode == "duplicate_owner": self.objects[1]["sourceRefs"]["claim"]["source"] = claim["source"]
                elif mode == "duplicate_glyph": claim["glyphMembers"] *= 2
                else: claim["disposition"] = "unresolved"
                self.seal()
                with self.assertRaises(DeckCompilerError): self.prepare()
                self.assertFalse(self.fixture.path.exists())

    def test_disputed_or_role_incompatible_links_fail_without_downgrade(self):
        self.api()
        original = copy.deepcopy(self.objects)
        for mode in ("disputed", "text_shape", "graphic_text", "text_decoration"):
            with self.subTest(mode=mode):
                self.objects = copy.deepcopy(original)
                if mode == "disputed": self.objects[3]["sourceRefs"]["claim"]["disposition"] = "linked"
                elif mode == "text_shape": self.objects[0]["type"] = "panel"
                elif mode == "graphic_text": self.objects[2]["type"] = "text"
                else: self.objects[4]["type"] = "text"
                self.seal()
                with self.assertRaises(DeckCompilerError): self.prepare()
                self.assertFalse(self.fixture.path.exists())

    def test_deterministic_idempotence_and_no_overwrite_on_disagreement(self):
        first = self.derive()
        self.assertEqual(first, self.derive())
        result = self.prepare(); raw = self.fixture.path.read_bytes()
        self.assertEqual(result, self.prepare())
        self.assertEqual(raw, self.fixture.path.read_bytes())
        ledger = read_json(self.fixture.path)
        ledger["groups"][0]["reason"] = "User-authored disagreement must remain untouched"
        write_json(self.fixture.path, ledger)
        disagreeing = self.fixture.path.read_bytes()
        with self.assertRaises(DeckCompilerError): self.prepare()
        with self.assertRaises(DeckCompilerError): self.validate()
        self.assertEqual(disagreeing, self.fixture.path.read_bytes())

    def test_missing_prepared_ledger_is_not_completion(self):
        self.api()
        with self.assertRaisesRegex(DeckCompilerError, "ledger"):
            self.validate()
        self.prepare()
        self.fixture.path.unlink()
        with self.assertRaises(DeckCompilerError): self.validate()

    def test_changed_bound_dependencies_cannot_be_resealed_by_tags(self):
        self.api()
        for path in (self.fixture.fixture.inventory_path, self.fixture.fixture.path,
                     self.root / self.job["source_png"]["path"],
                     self.fixture.project / "lib/slides.js", self.fixture.trace_path):
            before = path.read_bytes()
            with self.subTest(path=path.name):
                path.write_bytes(before + b"\n")
                # Whitespace is equivalent trace content; use an actual stale trace binding.
                if path == self.fixture.trace_path:
                    trace = read_json(path); trace["hashes"]["slidesJs"] = "0" * 64; write_json(path, trace)
                with self.assertRaises(DeckCompilerError): self.prepare()
                self.assertFalse(self.fixture.path.exists())
                path.write_bytes(before)
        self.job["job_id"] += "_stale"
        with self.assertRaisesRegex(DeckCompilerError, "content_hash"):
            self.prepare()

    def test_nonregular_target_and_failed_write_preserve_existing_state(self):
        self.api()
        self.fixture.path.mkdir()
        with self.assertRaises(DeckCompilerError): self.prepare()
        self.fixture.path.rmdir()
        self.fixture.path.symlink_to(self.work / "missing")
        with self.assertRaises(DeckCompilerError): self.prepare()
        self.fixture.path.unlink()
        if hasattr(os, "mkfifo"):
            os.mkfifo(self.fixture.path)
            with self.assertRaises(DeckCompilerError): self.prepare()
            self.fixture.path.unlink()
        with patch.object(self.api(), "write_json", side_effect=OSError("synthetic write failure")):
            with self.assertRaises(DeckCompilerError): self.prepare()
        self.assertFalse(self.fixture.path.exists())
        with patch.object(self.api(), "validate_source_ref_accounting", side_effect=ValueError("synthetic postwrite failure")):
            with self.assertRaises(DeckCompilerError): self.prepare()
        self.assertFalse(self.fixture.path.exists())
        def racing_ledger(*args):
            self.fixture.path.write_text("Existing concurrent ledger bytes")
            raise FileExistsError("synthetic competing writer")
        with patch.object(self.api().os, "link", side_effect=racing_ledger):
            with self.assertRaises(DeckCompilerError): self.prepare()
        self.assertEqual(self.fixture.path.read_text(), "Existing concurrent ledger bytes")

    def test_colliding_bare_ids_in_distinct_namespaces_remain_independent(self):
        f = self.fixture.fixture
        f.inventory["text_blocks"][0]["id"] = "U01"
        f.reseal_inventory()
        f.review["measurement_inventory_sha256"] = fixtures.sha(f.inventory_path)
        f.review["region_candidate_evidence_sha256"] = fixtures.content_sha256(f.inventory["region_candidate_evidence"])
        f.review["decisions"][0]["observation_id"] = "U01"
        self.job = f.build()["job"]
        self.objects[0]["sourceRefs"]["claim"]["source"]["observation_id"] = "U01"
        for obj in self.objects:
            obj["sourceRefs"] = self.tag(obj["sourceRefs"]["claim"])
        self.seal()
        self.assertEqual(self.prepare()["linked_observations"], 4)

    def public_fixture(self, *, review=True):
        root, project, work = self.fixture.public_fixture()
        job = read_json(work / "reconstruction_job.json")
        if review:
            inventory = read_json(root / job["vector_preflight"]["measurement_inventory"]["path"])
            evidence = inventory["region_candidate_evidence"]
            data = copy.deepcopy(self.fixture.fixture.review)
            data.update({"workflow_id": job["workflow_id"], "slide_number": job["slide_number"],
                "slide_id": job["slide_id"], "request_id": job["request_lineage"]["request_id"],
                "source_png_sha256": job["source_png"]["sha256"], "semantic_sidecar_sha256": job["semantic_sidecar"]["sha256"],
                "measurement_inventory_sha256": job["vector_preflight"]["measurement_inventory"]["sha256"],
                "region_candidate_evidence_sha256": fixtures.content_sha256(evidence), "canvas_px": evidence["canvas_px"],
                "canvas_rgb_sha256": evidence["canvas_rgb_sha256"], "coverage": "complete",
                "decisions": [self.fixture.fixture.decision("text_blocks", "T1", "text")]})
            write_json(work / "region_classification_review.json", data)
            jobs.prepare_reconstruction_jobs(root)
            job = read_json(work / "reconstruction_job.json")
        native_path = project / "out/native_object_manifest.json"
        native = read_json(native_path)
        if review:
            old_job = self.job; self.job = job
            tag = self.tag(self.claim("heading", "text_blocks", "T1"))
            self.job = old_job
        else:
            tag = None
        native["slides"]["1"]["objects"][0]["sourceRefs"] = tag
        write_json(native_path, native)
        trace_path = project / "out/render_trace.json"
        trace = read_json(trace_path); trace["nativeObjectManifestHash"] = fixtures.sha(native_path)
        write_json(trace_path, trace)
        return root, project, work, job

    def test_public_gates_reject_null_tags_instead_of_legacy_silent_acceptance(self):
        root, project, work, _ = self.public_fixture(review=False)
        before = (work / "worker_receipt.json").read_bytes()
        report = jobs.validate_reconstruction_job_bundle(root, require_worker_outputs=True)
        with self.subTest(gate="completion"):
            self.assertFalse(report["valid"], report)
        with self.subTest(gate="shared-finalization"), self.assertRaises(DeckCompilerError):
            shared.finalize_shared_render_qa(root, summary_path=project / "out/visual_qa_summary_final.json")
        self.assertEqual(before, (work / "worker_receipt.json").read_bytes())
        self.assertFalse((work / fixtures.NAME).exists())

    def test_public_finalization_derives_and_seals_then_completion_rechecks(self):
        self.api()
        root, project, work, job = self.public_fixture()
        self.assertFalse((work / fixtures.NAME).exists())
        result = shared.finalize_shared_render_qa(root, summary_path=project / "out/visual_qa_summary_final.json")
        receipt = read_json(result.receipt_paths[0])
        self.assertIn(fixtures.NAME, receipt["artifacts"])
        self.assertEqual(receipt["surfaceCallAccounting"]["representation_status"], "NOT_ESTABLISHED")
        self.assertTrue(jobs.validate_reconstruction_job_bundle(root, require_worker_outputs=True)["valid"])
        before = {p: p.read_bytes() for p in (work / fixtures.NAME, result.receipt_paths[0])}
        shared.finalize_shared_render_qa(root, summary_path=project / "out/visual_qa_summary_final.json")
        self.assertTrue(all(p.read_bytes() == data for p, data in before.items()))
        (work / fixtures.NAME).unlink()
        self.assertFalse(jobs.validate_reconstruction_job_bundle(root, require_worker_outputs=True)["valid"])

    def test_late_finalization_failure_restores_new_and_existing_ledger_receipt_bytes(self):
        self.api()
        root, project, work, job = self.public_fixture()
        receipt_path, ledger_path = work / "worker_receipt.json", work / fixtures.NAME
        original_validate = shared.validate_reconstruction_job_bundle
        def reject_completion(*args, **kwargs):
            if kwargs.get("require_worker_outputs"):
                return {"valid": False, "issues": ["Synthetic late completion failure"]}
            return original_validate(*args, **kwargs)
        for existing in (False, True):
            if existing:
                shared.finalize_shared_render_qa(root, summary_path=project / "out/visual_qa_summary_final.json")
            before_receipt = receipt_path.read_bytes()
            before_ledger = ledger_path.read_bytes() if existing else None
            with self.subTest(existing=existing), patch.object(shared, "validate_reconstruction_job_bundle", side_effect=reject_completion):
                with self.assertRaisesRegex(DeckCompilerError, "Synthetic late completion"):
                    shared.finalize_shared_render_qa(root, summary_path=project / "out/visual_qa_summary_final.json")
            self.assertEqual(receipt_path.read_bytes(), before_receipt)
            self.assertEqual(ledger_path.read_bytes() if ledger_path.exists() else None, before_ledger)

    def test_public_rollback_does_not_delete_competing_ledger_after_link_rejection(self):
        root, project, work, _ = self.public_fixture()
        path = work / fixtures.NAME
        receipt = (work / "worker_receipt.json").read_bytes()
        foreign = b"Another writer owns this ledger\n"
        def competing_link(*args):
            path.write_bytes(foreign)
            raise FileExistsError("Synthetic competing writer")
        with patch.object(self.api().os, "link", side_effect=competing_link):
            with self.assertRaises(DeckCompilerError):
                shared.finalize_shared_render_qa(root, summary_path=project / "out/visual_qa_summary_final.json")
        self.assertTrue(path.exists(), "rollback deleted another writer's ledger")
        self.assertEqual(path.read_bytes(), foreign)
        self.assertEqual((work / "worker_receipt.json").read_bytes(), receipt)

    def test_public_rollback_leaves_replacement_ledger_and_receipt_untouched(self):
        root, project, work, _ = self.public_fixture()
        original_validate = shared.validate_reconstruction_job_bundle
        replacements = {}
        def replace_then_reject(*args, **kwargs):
            if kwargs.get("require_worker_outputs"):
                for name in (fixtures.NAME, "worker_receipt.json"):
                    path = work / name
                    # Same ledger bytes but a different inode also belong to
                    # the competing writer; byte equality alone is insufficient.
                    data = path.read_bytes() if name == fixtures.NAME else b"Competing receipt bytes\n"
                    temporary = work / (name + ".competing")
                    temporary.write_bytes(data); temporary.replace(path)
                    replacements[path] = (data, path.stat().st_ino)
                return {"valid": False, "issues": ["Synthetic replacement race"]}
            return original_validate(*args, **kwargs)
        with patch.object(shared, "validate_reconstruction_job_bundle", side_effect=replace_then_reject):
            with self.assertRaisesRegex(DeckCompilerError, "Synthetic replacement race"):
                shared.finalize_shared_render_qa(root, summary_path=project / "out/visual_qa_summary_final.json")
        for path, (data, inode) in replacements.items():
            self.assertTrue(path.exists(), "rollback deleted a replacement")
            self.assertEqual(path.read_bytes(), data)
            self.assertEqual(path.stat().st_ino, inode)

    def test_replacement_immediately_after_link_is_never_mistaken_for_our_inode(self):
        root, project, work, _ = self.public_fixture()
        path = work / fixtures.NAME
        receipt = (work / "worker_receipt.json").read_bytes()
        foreign = b"Competing replacement immediately after successful link\n"
        link = self.api().os.link
        def link_then_replace(source, target):
            link(source, target)
            replacement = work / "post-link-replacement"
            replacement.write_bytes(foreign); replacement.replace(target)
        with patch.object(self.api().os, "link", side_effect=link_then_replace):
            with self.assertRaises(DeckCompilerError):
                shared.finalize_shared_render_qa(root, summary_path=project / "out/visual_qa_summary_final.json")
        self.assertTrue(path.exists())
        self.assertEqual(path.read_bytes(), foreign)
        self.assertEqual((work / "worker_receipt.json").read_bytes(), receipt)

    def test_competing_receipt_before_commit_is_not_overwritten_or_restored(self):
        root, project, work, _ = self.public_fixture()
        path = work / "worker_receipt.json"
        original = shared._validate_render_metadata
        foreign = b"Competing receipt before commit\n"
        def replace_receipt(*args, **kwargs):
            result = original(*args, **kwargs)
            temporary = work / "competing-receipt"
            temporary.write_bytes(foreign); temporary.replace(path)
            return result
        with patch.object(shared, "_validate_render_metadata", side_effect=replace_receipt):
            with self.assertRaisesRegex(DeckCompilerError, "receipt.*changed"):
                shared.finalize_shared_render_qa(root, summary_path=project / "out/visual_qa_summary_final.json")
        self.assertEqual(path.read_bytes(), foreign)
        self.assertFalse((work / fixtures.NAME).exists())


if __name__ == "__main__":
    unittest.main()
