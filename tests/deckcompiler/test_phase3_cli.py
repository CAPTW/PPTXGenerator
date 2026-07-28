from __future__ import annotations

import json
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
DEMO = ROOT / "examples" / "deckcompiler_demo"


class Phase3CliTests(unittest.TestCase):
    def _run(self, config: Path, output: Path) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(SRC)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        return subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "presentation_agent.deckcompiler",
                "build-architecture",
                "--config",
                str(config),
                "--output-dir",
                str(output),
            ],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_canonical_and_prompt_only_cli_runs_emit_phase3_artifacts_only(self) -> None:
        source_paths = [
            DEMO / "inputs" / "prompt.txt",
            DEMO / "inputs" / "cooling_system_overview.pdf",
            DEMO / "inputs" / "cooling_risk_decision_report.pdf",
        ]
        before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in source_paths}
        for config_name in ("demo.yaml", "prompt_only.yaml"):
            with self.subTest(config=config_name), tempfile.TemporaryDirectory() as tmpdir:
                output = Path(tmpdir) / "run"
                result = self._run(DEMO / config_name, output)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("DECKCOMPILER_PHASE3_GO", result.stdout)
                expected = {
                    "input_request.json",
                    "source_corpus.json",
                    "source_locators.json",
                    "evidence_unit_registry.json",
                    "source_coverage_report.json",
                    "workflow_resolution.json",
                    "source_gap_report.json",
                    "presentation_plan.json",
                    "slide_blueprint_collection.json",
                    "evidence_allocation_report.json",
                    "presentation_architecture.json",
                    "design_invariants.json",
                    "module_art_directions.json",
                    "creative_template_architecture.json",
                    "creative_fit_report.json",
                    "architecture_validation_report.json",
                    "deckcompiler_run_manifest.json",
                    "artifact_graph.json",
                    "phase3_validation_report.json",
                }
                self.assertEqual({path.name for path in output.iterdir()}, expected)
                forbidden_suffixes = {".pptx", ".html", ".png"}
                self.assertFalse(any(path.suffix.lower() in forbidden_suffixes for path in output.rglob("*")))
                self.assertFalse((output / "semantic_sidecars").exists())
                manifest = json.loads((output / "deckcompiler_run_manifest.json").read_text(encoding="utf-8"))
                passed = {item["stage"] for item in manifest["stages"] if item["status"] == "passed"}
                skipped = {item["stage"] for item in manifest["stages"] if item["status"] == "skipped_by_phase"}
                self.assertIn("artifact_graph_validation", passed)
                self.assertIn("live_image_generation", skipped)
                self.assertIn("pngtopptx_reconstruction", skipped)
                self.assertNotIn("live_image_generation", passed)
                self.assertEqual(manifest["passed_stage_count"], len(passed))
        after = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in source_paths}
        self.assertEqual(after, before)

    def test_repeated_canonical_runs_have_identical_semantic_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            first = Path(tmpdir) / "first"
            second = Path(tmpdir) / "second"
            self.assertEqual(self._run(DEMO / "demo.yaml", first).returncode, 0)
            self.assertEqual(self._run(DEMO / "demo.yaml", second).returncode, 0)
            first_report = json.loads((first / "phase3_validation_report.json").read_text(encoding="utf-8"))
            second_report = json.loads((second / "phase3_validation_report.json").read_text(encoding="utf-8"))
            self.assertEqual(first_report["deterministic_artifact_hashes"], second_report["deterministic_artifact_hashes"])
            self.assertTrue(first_report["determinism_ready"])

    def test_scanned_malformed_and_incompatible_inputs_fail_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            for name, source, expected_code in (
                ("scanned", DEMO / "negative_inputs" / "scanned_image_only.pdf", "DC_PDF_SCANNED_UNSUPPORTED"),
                ("malformed", DEMO / "negative_inputs" / "malformed.pdf", "DC_PDF_INVALID"),
            ):
                case = root / name
                case.mkdir()
                shutil.copy2(DEMO / "inputs" / "prompt.txt", case / "prompt.txt")
                shutil.copy2(source, case / "first.pdf")
                shutil.copy2(DEMO / "inputs" / "cooling_system_overview.pdf", case / "second.pdf")
                config = yaml.safe_load((DEMO / "demo.yaml").read_text(encoding="utf-8"))
                config["inputs"] = {"prompt": "prompt.txt", "pdfs": ["first.pdf", "second.pdf"]}
                (case / "config.yaml").write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
                result = self._run(case / "config.yaml", case / "out")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(expected_code, result.stdout)
                self.assertNotIn("Traceback", result.stdout + result.stderr)
                manifest = json.loads((case / "out" / "deckcompiler_run_manifest.json").read_text(encoding="utf-8"))
                self.assertEqual(manifest["run_status"], "failed")
                self.assertNotIn("strict_planning", {item["stage"] for item in manifest["stages"] if item["status"] == "passed"})

            incompatible = root / "incompatible"
            incompatible.mkdir()
            shutil.copy2(DEMO / "inputs" / "prompt.txt", incompatible / "prompt.txt")
            shutil.copy2(DEMO / "inputs" / "cooling_system_overview.pdf", incompatible / "first.pdf")
            shutil.copy2(DEMO / "inputs" / "cooling_risk_decision_report.pdf", incompatible / "second.pdf")
            config = yaml.safe_load((DEMO / "demo.yaml").read_text(encoding="utf-8"))
            config["inputs"] = {"prompt": "prompt.txt", "pdfs": ["first.pdf", "second.pdf"]}
            config["presentation"]["workflow"] = "modular_briefing"
            (incompatible / "config.yaml").write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
            result = self._run(incompatible / "config.yaml", incompatible / "out")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("DC_WORKFLOW_INCOMPATIBLE", result.stdout)
            self.assertNotIn("Traceback", result.stdout + result.stderr)

    def test_protected_output_directory_is_rejected(self) -> None:
        result = self._run(DEMO / "demo.yaml", ROOT / "outputs")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DC_OUTPUT_PROTECTED", result.stdout)
        self.assertNotIn("Traceback", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
