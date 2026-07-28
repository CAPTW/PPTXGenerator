from __future__ import annotations

import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from presentation_agent.deckcompiler.cli import build_parser  # noqa: E402
from presentation_agent.deckcompiler.release.demo import (  # noqa: E402
    DemoError,
    build_demo_run_manifest,
    compare_semantic_maps,
    format_success_markers,
    main as demo_main,
    resolve_output_root,
    validate_demo_gate,
    validate_demo_prerequisites,
    validate_visual_compatibility,
)
from presentation_agent.deckcompiler.schemas import validator_for  # noqa: E402


class Phase7DemoCLITests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.tmp = Path(self.temporary.name)
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        self.output = self.tmp / "output"
        self.contract = self.repo / "release_contract.json"
        self.external = self.repo / "external_prerequisite_manifest.json"
        self.pin = self.repo / "pin.json"
        self.phase4 = self.repo / "phase4"
        self.phase6 = self.repo / "phase6"
        self.phase4.mkdir()
        self.phase6.mkdir()
        self.contract.write_text("{}\n", encoding="utf-8")
        self.external.write_text("{}\n", encoding="utf-8")
        self.pin.write_text("{}\n", encoding="utf-8")
        self.prerequisites = {
            "release_contract": self.contract,
            "external_prerequisite_manifest": self.external,
            "external_pin": self.pin,
            "phase4_bundle": self.phase4,
            "phase6_evidence": self.phase6,
            "selected_route": "editable_pngtopptx",
            "legacy_fallback_used": False,
            "silent_fallback_used": False,
            "live_image_generation_reexecuted": False,
            "input_paths": ["examples/deckcompiler_demo/demo.yaml"],
        }
        self.gate = {
            "official_final_gate": "PASS",
            "renderer_identity": "Microsoft PowerPoint COM",
            "render_count": 6,
            "semantic_fidelity": 1.0,
            "native_editability": 1.0,
            "raster_violation_count": 0,
            "parity": 1.0,
            "composite_qa": "PASS",
            "phase6_repair_proof": "PASS",
            "package_validation": "PASS",
        }

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_01_canonical_command_parses(self) -> None:
        args = build_parser().parse_args(
            [
                "demo",
                "--config",
                "examples/deckcompiler_demo/demo.yaml",
                "--output-dir",
                str(self.output),
            ]
        )
        self.assertEqual(args.command, "demo")

    def test_02_output_dir_is_required(self) -> None:
        with self.assertRaises(SystemExit):
            build_parser().parse_args(
                ["demo", "--config", "examples/deckcompiler_demo/demo.yaml"]
            )

    def test_03_output_inside_repo_is_rejected(self) -> None:
        with self.assertRaisesRegex(DemoError, "DC_OUTPUT_INSIDE_REPO"):
            resolve_output_root(self.repo / "run", self.repo)

    def test_04_nonempty_output_is_rejected(self) -> None:
        self.output.mkdir()
        (self.output / "x").write_text("x", encoding="utf-8")
        with self.assertRaisesRegex(DemoError, "DC_OUTPUT_NOT_EMPTY"):
            resolve_output_root(self.output, self.repo)

    def test_05_protected_output_is_rejected(self) -> None:
        with self.assertRaisesRegex(DemoError, "DC_OUTPUT_PROTECTED"):
            resolve_output_root(
                self.repo / "outputs" / "golden_template_masters.pptx", self.repo
            )

    def _missing(self, key: str, code: str) -> None:
        payload = dict(self.prerequisites)
        payload[key] = self.tmp / "missing"
        with self.assertRaisesRegex(DemoError, code):
            validate_demo_prerequisites(payload)

    def test_06_missing_release_contract_is_rejected(self) -> None:
        self._missing("release_contract", "DC_RELEASE_CONTRACT_MISSING")

    def test_07_missing_external_prerequisite_is_rejected(self) -> None:
        self._missing(
            "external_prerequisite_manifest", "DC_EXTERNAL_PREREQUISITE_MISSING"
        )

    def test_08_external_pin_mismatch_is_rejected(self) -> None:
        payload = dict(self.prerequisites)
        payload["external_pin_valid"] = False
        with self.assertRaisesRegex(DemoError, "DC_EXTERNAL_PIN_MISMATCH"):
            validate_demo_prerequisites(payload)

    def test_09_phase3_semantic_mismatch_is_rejected(self) -> None:
        with self.assertRaisesRegex(DemoError, "DC_PHASE3_SEMANTIC_MISMATCH"):
            compare_semantic_maps({"a": "1"}, {"a": "2"})

    def test_10_phase4_bundle_mismatch_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            DemoError, "BLOCKED_FROZEN_VISUAL_BUNDLE_SEMANTIC_MISMATCH"
        ):
            validate_visual_compatibility({"bundle_hash_match": False})

    def test_11_sidecar_target_mismatch_is_rejected(self) -> None:
        with self.assertRaisesRegex(DemoError, "DC_VISUAL_COMPATIBILITY_MISMATCH"):
            validate_visual_compatibility(
                {"bundle_hash_match": True, "sidecar_target_match": False}
            )

    def test_12_legacy_fallback_is_rejected(self) -> None:
        payload = dict(self.prerequisites)
        payload["legacy_fallback_used"] = True
        with self.assertRaisesRegex(DemoError, "DC_FALLBACK_FORBIDDEN"):
            validate_demo_prerequisites(payload)

    def test_13_auto_route_is_rejected(self) -> None:
        payload = dict(self.prerequisites)
        payload["selected_route"] = "auto"
        with self.assertRaisesRegex(DemoError, "DC_STRICT_ROUTE_REQUIRED"):
            validate_demo_prerequisites(payload)

    def test_14_missing_crop_artifact_is_rejected(self) -> None:
        payload = dict(self.gate)
        payload["crop_contract"] = "BLOCKED"
        with self.assertRaisesRegex(DemoError, "DC_CROP_ARTIFACT_MISSING"):
            validate_demo_gate(payload)

    def _gate_invalid(self, key: str, value, code: str) -> None:
        payload = dict(self.gate)
        payload[key] = value
        with self.assertRaisesRegex(DemoError, code):
            validate_demo_gate(payload)

    def test_15_official_final_gate_failure_propagates(self) -> None:
        self._gate_invalid(
            "official_final_gate", "BLOCKED", "DC_OFFICIAL_FINAL_GATE_FAILED"
        )

    def test_16_real_renderer_is_required(self) -> None:
        self._gate_invalid("renderer_identity", "fixture", "DC_REAL_RENDERER_REQUIRED")

    def test_17_render_count_mismatch_is_rejected(self) -> None:
        self._gate_invalid("render_count", 5, "DC_RENDER_COUNT_MISMATCH")

    def test_18_semantic_fidelity_below_100_is_rejected(self) -> None:
        self._gate_invalid("semantic_fidelity", 0.99, "DC_SEMANTIC_FIDELITY_FAILED")

    def test_19_native_coverage_below_100_is_rejected(self) -> None:
        self._gate_invalid("native_editability", 0.99, "DC_NATIVE_EDITABILITY_FAILED")

    def test_20_raster_violation_is_rejected(self) -> None:
        self._gate_invalid("raster_violation_count", 1, "DC_RASTER_POLICY_FAILED")

    def test_21_parity_below_100_is_rejected(self) -> None:
        self._gate_invalid("parity", 0.99, "DC_PARITY_FAILED")

    def test_22_missing_phase6_evidence_is_rejected(self) -> None:
        self._missing("phase6_evidence", "DC_PHASE6_EVIDENCE_MISSING")

    def test_23_package_failure_propagates(self) -> None:
        self._gate_invalid("package_validation", "BLOCKED", "DC_PACKAGE_FAILED")

    def test_24_success_prints_required_paths(self) -> None:
        text = format_success_markers(
            {
                "delivery_package": "delivery",
                "pptx": "deck.pptx",
                "html": "index.html",
                "contact_sheet": "contact.png",
                "delivery_manifest": "manifest.json",
            }
        )
        for marker in (
            "DECKCOMPILER_DEMO_GO",
            "DELIVERY_PACKAGE=",
            "PPTX=",
            "HTML=",
            "CONTACT_SHEET=",
            "DELIVERY_MANIFEST=",
        ):
            self.assertIn(marker, text)

    def test_25_failed_command_exits_nonzero(self) -> None:
        with mock.patch(
            "presentation_agent.deckcompiler.release.demo.execute_demo",
            side_effect=DemoError("DC_TEST"),
        ):
            self.assertEqual(
                demo_main(
                    ["--config", str(self.contract), "--output-dir", str(self.output)]
                ),
                1,
            )

    def test_26_success_command_exits_zero(self) -> None:
        result = {
            "delivery_package": "delivery",
            "pptx": "deck.pptx",
            "html": "index.html",
            "contact_sheet": "contact.png",
            "delivery_manifest": "manifest.json",
        }
        with (
            mock.patch(
                "presentation_agent.deckcompiler.release.demo.execute_demo",
                return_value=result,
            ),
            redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(
                demo_main(
                    ["--config", str(self.contract), "--output-dir", str(self.output)]
                ),
                0,
            )

    def test_27_runtime_manifest_is_schema_valid(self) -> None:
        payload = build_demo_run_manifest(
            run_id="phase7run_" + "a" * 20, source_commit="b" * 40, stages=[]
        )
        self.assertEqual(
            list(validator_for("demo_run_manifest").iter_errors(payload)), []
        )

    def test_28_semantic_map_is_deterministic(self) -> None:
        payload = {"z": "2", "a": "1"}
        self.assertEqual(
            compare_semantic_maps(payload, dict(reversed(list(payload.items())))),
            payload,
        )

    def test_29_live_image_generation_is_forbidden(self) -> None:
        payload = dict(self.prerequisites)
        payload["live_image_generation_reexecuted"] = True
        with self.assertRaisesRegex(DemoError, "DC_LIVE_IMAGE_GENERATION_FORBIDDEN"):
            validate_demo_prerequisites(payload)

    def test_30_generated_outputs_dependency_is_forbidden(self) -> None:
        payload = dict(self.prerequisites)
        payload["input_paths"] = ["outputs/reused.pptx"]
        with self.assertRaisesRegex(DemoError, "DC_GENERATED_OUTPUT_INPUT"):
            validate_demo_prerequisites(payload)


if __name__ == "__main__":
    unittest.main()
