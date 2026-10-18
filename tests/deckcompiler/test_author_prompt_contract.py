"""Synthetic prompt/validator contracts; no model or rendered-quality claims."""
from __future__ import annotations

import copy
import json
import re
import tempfile
import unittest
from pathlib import Path

from presentation_agent.deckcompiler.manifest_io import read_json, write_json
from presentation_agent.deckcompiler.orchestration.execution_profiles import execution_profile_payload
from presentation_agent.deckcompiler.orchestration.reconstruction_jobs import (
    AUTHORING_OUTPUT_NAMES, POST_RENDER_OUTPUT_NAMES,
    _validate_vector_usage, _worker_prompt, validate_reconstruction_job_bundle,
)


class AuthorPromptContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.inventory_path = write_json(self.root / "inventory.json", {})
        self.job = {
            "slide_number": 7,
            "execution_profile": execution_profile_payload("sol-medium"),
            "semantic_geometry_binding": {"status": "UNRESOLVED"},
            "authoring_outputs": [name.format(slide=7) for name in AUTHORING_OUTPUT_NAMES],
            "post_render_outputs": list(POST_RENDER_OUTPUT_NAMES),
            "vector_preflight": {
                "policy_id": "synthetic-policy",
                "measurement_inventory": {"path": "inventory.json", "sha256": "a" * 64},
                "regions": [],
                "available_parametric_icon_names": ["circle"],
            },
            "receipt_binding": {
                "vector_preflight_sha256": "b" * 64,
                "vector_slide_content_hash": "c" * 64,
            },
        }

    def prompt(self):
        return _worker_prompt(self.root, self.root / "work/slide07", self.job)

    def starter(self, prompt):
        block = re.search(r"```json\n(\{.*?\})\n```", prompt, re.DOTALL)
        self.assertIsNotNone(block, "worker prompt must include the vector_usage JSON starter")
        return json.loads(block.group(1))

    def validate(self, payload):
        issues = []
        _validate_vector_usage(payload, self.job, "synthetic slide", issues)
        return issues

    def add_regions(self):
        self.job["vector_preflight"]["regions"] = [
            {
                "region_id": region_id, "disposition": "bounded_svg_asset",
                "vector_svg": {"sha256": asset_hash}, "area_ratio": 0.02,
                "kind_hint": "icon", "semantic_text_overlap_ids": [],
            }
            for region_id, asset_hash in (("R1", "d" * 64), ("R2", "e" * 64))
        ] + [{"region_id": "R3", "disposition": "native_shape"}]

    def test_starter_uses_exact_job_values_for_cli_and_native_profiles(self):
        for profile, slide in (("sol-medium", 7), ("native-inherited-xhigh", 12)):
            with self.subTest(profile=profile):
                self.job["execution_profile"] = execution_profile_payload(profile)
                self.job["slide_number"] = slide
                self.job["receipt_binding"]["vector_preflight_sha256"] = str(slide % 10) * 64
                payload = self.starter(self.prompt())
                self.assertEqual(payload, {
                    "slide": slide,
                    "policyId": self.job["vector_preflight"]["policy_id"],
                    "vectorPreflightSha256": self.job["receipt_binding"]["vector_preflight_sha256"],
                    "vectorSlideContentHash": self.job["receipt_binding"]["vector_slide_content_hash"],
                    "measurementInventorySha256": self.job["vector_preflight"]["measurement_inventory"]["sha256"],
                    "measuredCoordinatesAuthoritative": True,
                    "usedRegions": [], "deferredRegions": [], "parametricIconUses": [],
                })
                self.assertEqual(self.validate(payload), [])

    def test_region_reporting_instructions_cover_exact_existing_row_contract(self):
        self.add_regions()
        prompt = self.prompt()
        for instruction in (
            "initial values", "exactly once", "bounded_svg_asset",
            "usedRegions", "regionId", "assetSha256", "vector_svg.sha256",
            "deferredRegions", "reason", "at least 8", "parametricIconUses",
            "name", "color", "#RRGGBB", "available_parametric_icon_names",
            "semantic_text_overlap_ids", "area_ratio", "0.35", "photo",
        ):
            self.assertIn(instruction, prompt)
        payload = self.starter(prompt)
        self.assertTrue(self.validate(payload), "empty starter cannot account for approved regions")
        payload["usedRegions"] = [{"regionId": "R1", "assetSha256": "d" * 64}]
        payload["deferredRegions"] = [{"regionId": "R2", "reason": "Rebuilt as native geometry"}]
        payload["parametricIconUses"] = [{"name": "circle", "regionId": "R2", "color": "#123456"}]
        self.assertEqual(self.validate(payload), [])
        for field, row, expected in (
            ("usedRegions", {"regionId": "R2", "assetSha256": "e" * 64}, "duplicate region decisions"),
            ("usedRegions", {"regionId": "R3", "assetSha256": "f" * 64}, "non-approved SVG region"),
            ("parametricIconUses", {"name": "circle", "regionId": "R2", "color": "#123456"}, "duplicates a parametric icon region"),
        ):
            with self.subTest(field=field, expected=expected):
                changed = copy.deepcopy(payload)
                changed[field].append(row)
                self.assertTrue(any(expected in issue for issue in self.validate(changed)))

    def test_missing_binding_fields_and_arrays_remain_rejected(self):
        payload = self.starter(self.prompt())
        for field in payload:
            with self.subTest(field=field):
                changed = dict(payload)
                del changed[field]
                self.assertTrue(any(field in issue for issue in self.validate(changed)))

    def test_fragment_guidance_names_shared_kit_no_require_and_exact_function(self):
        prompt = self.prompt()
        self.assertIn("function s7(s)", prompt)
        self.assertIn("shared kit", prompt)
        self.assertIn("Do not use `require(...)`", prompt)
        self.assertIn("profile_override.json", prompt)

    def test_prompt_does_not_change_inputs_or_make_region_decisions(self):
        self.add_regions()
        write_json(self.inventory_path, {"region_candidate_evidence": {"candidates": [{"id": "U01"}]}})
        original_job = copy.deepcopy(self.job)
        original_inventory = self.inventory_path.read_bytes()
        original_files = sorted(path.relative_to(self.root).as_posix() for path in self.root.rglob("*"))
        prompt = self.prompt()
        self.assertEqual(self.prompt(), prompt)
        self.assertEqual(self.job, original_job)
        self.assertEqual(self.inventory_path.read_bytes(), original_inventory)
        self.assertEqual(sorted(path.relative_to(self.root).as_posix() for path in self.root.rglob("*")), original_files)
        self.assertEqual(self.starter(prompt)["usedRegions"], [])
        self.assertEqual(self.starter(prompt)["deferredRegions"], [])
        self.assertIn("unadjudicated measurements", prompt)
        self.assertNotIn("U01", prompt)

    def test_public_generated_prompt_starter_passes_unchanged_gates(self):
        from test_general_generate_workflow import GeneralGenerateWorkflowTests

        fixture = GeneralGenerateWorkflowTests()
        runtime = self.root / "public-flow"
        started = fixture._start(runtime)
        fixture._build_run_draft(
            runtime, workflow_id=started.workflow_id, slide_count=1,
            status="COMPLETED", qa_status="PASS", fail_count=0, blocking_count=0,
        )
        work = runtime / "pngtopptx-project/work/slide01"
        payload = self.starter((work / "worker_prompt.md").read_text(encoding="utf-8"))
        write_json(work / "vector_usage.json", payload)
        receipt_path = work / "worker_receipt.json"
        receipt = read_json(receipt_path)
        receipt["artifactHashes"]["vector_usage.json"] = fixture._sha256(work / "vector_usage.json")
        write_json(receipt_path, receipt)
        for flag in ("require_authoring_outputs", "require_worker_outputs"):
            with self.subTest(gate=flag):
                report = validate_reconstruction_job_bundle(runtime, **{flag: True})
                self.assertTrue(report["valid"], report)
        fragment_path = work / "s1.fragment.js"
        fragment_path.write_text(
            "const profile = require('./profile_override.json');\nfunction s1(s) {}\n",
            encoding="utf-8",
        )
        receipt = read_json(receipt_path)
        receipt["artifactHashes"][fragment_path.name] = fixture._sha256(fragment_path)
        write_json(receipt_path, receipt)
        for flag in ("require_authoring_outputs", "require_worker_outputs"):
            with self.subTest(gate=flag):
                report = validate_reconstruction_job_bundle(runtime, **{flag: True})
                self.assertFalse(report["valid"])
                self.assertTrue(any("without require(...)" in issue for issue in report["issues"]), report)


if __name__ == "__main__":
    unittest.main()
