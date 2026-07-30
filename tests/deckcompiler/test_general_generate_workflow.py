from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import yaml

from presentation_agent.deckcompiler.intake.config import load_phase3_config
from presentation_agent.deckcompiler.intake.multi_source import build_intake_artifacts
from presentation_agent.deckcompiler.orchestration.generate import (
    resume_generate_workflow,
    start_generate_workflow,
    validate_generate_workflow,
)
from presentation_agent.deckcompiler.planning.strict_adapter import build_strict_planning


ROOT = Path(__file__).resolve().parents[2]
DEMO = ROOT / "examples" / "deckcompiler_demo"


class GeneralGenerateWorkflowTests(unittest.TestCase):
    def test_prompt_only_start_runs_phase3_and_phase4_preparation_then_waits(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = Path(tmpdir) / "run"
            result = start_generate_workflow(
                output_dir=runtime,
                prompt="Create a decision brief about resilient urban microgrids.",
                prompt_file=None,
                pdf_paths=(),
                audience="city leaders",
                purpose="investment decision",
                language="English",
                tone=("professional", "clear"),
                workflow="decision_brief",
            )

            self.assertEqual(result.exit_code, 2)
            self.assertEqual(result.status, "AWAITING_PHASE4_VISUALS")
            self.assertEqual(result.required_action["code"], "PROVIDE_PHASE4_BUNDLE")
            report = validate_generate_workflow(runtime)
            self.assertTrue(report["valid"], report)
            manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
            stages = {stage["phase"]: stage for stage in manifest["stages"]}
            self.assertEqual(stages["phase3"]["status"], "COMPLETED")
            self.assertEqual(stages["phase4"]["status"], "AWAITING_EXTERNAL")
            self.assertEqual(stages["phase5"]["status"], "PENDING")
            self.assertEqual(stages["phase6"]["status"], "PENDING")
            self.assertEqual(len(list((runtime / "phase4_preparation" / "preparation" / "prompts").glob("*.json"))), 13)
            self.assertEqual(len(list((runtime / "phase4_preparation" / "preparation" / "semantic_sidecars").glob("*.json"))), 6)
            self.assertFalse(any(path.suffix.lower() in {".pptx", ".html"} for path in runtime.rglob("*")))

    def test_prompt_with_three_pdfs_represents_every_documentary_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            shutil.copy2(DEMO / "inputs" / "prompt.txt", root / "prompt.txt")
            shutil.copy2(DEMO / "inputs" / "cooling_system_overview.pdf", root / "first.pdf")
            shutil.copy2(DEMO / "inputs" / "cooling_risk_decision_report.pdf", root / "second.pdf")
            third = root / "third.pdf"
            third.write_bytes(
                (DEMO / "inputs" / "cooling_system_overview.pdf").read_bytes()
                + b"\n% distinct user copy\n"
            )
            config = yaml.safe_load((DEMO / "demo.yaml").read_text(encoding="utf-8"))
            config["mode"] = "prompt_with_pdfs"
            config["inputs"] = {
                "prompt": "prompt.txt",
                "pdfs": ["first.pdf", "second.pdf", "third.pdf"],
            }
            config_path = root / "config.yaml"
            config_path.write_text(
                yaml.safe_dump(config, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )

            loaded = load_phase3_config(config_path)
            intake = build_intake_artifacts(loaded)
            planning = build_strict_planning(loaded, intake)
            expected = {
                source["source_id"]
                for source in intake.source_corpus["sources"]
                if source["source_type"] == "pdf"
            }

            self.assertEqual(intake.source_coverage_report["source_count"], 4)
            self.assertEqual(
                set(planning.evidence_allocation_report["represented_documentary_source_ids"]),
                expected,
            )
            pdf_sources = [
                source
                for source in intake.source_corpus["sources"]
                if source["source_type"] == "pdf"
            ]
            self.assertTrue(
                all("User-provided local PDF" in source["rights_privacy_note"] for source in pdf_sources)
            )

    def test_resume_routes_phase4_handoff_and_runtime_phase6_without_claiming_inline_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            runtime = base / "run"
            started = start_generate_workflow(
                output_dir=runtime,
                prompt="Create a technical explainer about a local energy system.",
                prompt_file=None,
                pdf_paths=(),
                audience="engineering leaders",
                purpose="architecture review",
                language="English",
                tone=("technical", "clear"),
                workflow="technical_explainer",
            )
            self.assertEqual(started.status, "AWAITING_PHASE4_VISUALS")

            phase4 = base / "phase4"
            phase4.mkdir()
            handoff_root = runtime / "phase5_handoff" / "handoff"
            project_root = runtime / "phase5_handoff" / "project"
            handoff_root.mkdir(parents=True)
            project_root.mkdir()
            handoff_manifest = handoff_root / "pngtopptx_handoff_manifest.json"
            handoff_manifest.write_text('{"handoff_id":"handoff_test"}\n', encoding="utf-8")
            invocation_plan = handoff_root / "pngtopptx_invocation_plan.json"
            invocation_plan.write_text("{}\n", encoding="utf-8")
            fake_handoff = SimpleNamespace(
                handoff_root=handoff_root,
                project_root=project_root,
                handoff_manifest=handoff_manifest,
                invocation_plan=invocation_plan,
            )
            with (
                mock.patch(
                    "presentation_agent.deckcompiler.orchestration.generate.validate_phase4_bundle",
                    return_value={
                        "valid": True,
                        "manifest_id": "phase4targets_test",
                        "selected_target_count": 6,
                    },
                ),
                mock.patch(
                    "presentation_agent.deckcompiler.orchestration.generate._validate_phase4_link"
                ),
                mock.patch(
                    "presentation_agent.deckcompiler.orchestration.generate.export_phase4_handoff",
                    return_value=fake_handoff,
                ),
            ):
                waiting = resume_generate_workflow(
                    resume=runtime,
                    phase4_bundle=phase4,
                    external_skillset_pin=base / "pin.json",
                    external_skill_root=base / "skills",
                    profile=base / "profile.json",
                    node_path=base / "node_modules",
                )
            self.assertEqual(waiting.status, "AWAITING_PHASE5_RECONSTRUCTION")
            self.assertEqual(waiting.required_action["code"], "EXECUTE_PHASE5_RECONSTRUCTION")

            phase5 = base / "phase5"
            phase5.mkdir()
            external_summary = base / "external-summary.json"
            external_summary.write_text("{}\n", encoding="utf-8")
            qa_output = runtime / "phase6"
            qa_output.mkdir()
            fake_qa = SimpleNamespace(
                run_id="phase6qa_test",
                output_dir=qa_output,
                status="PASS",
                renderer_version="16.0",
            )
            with (
                mock.patch(
                    "presentation_agent.deckcompiler.orchestration.generate._validate_phase5_link"
                ),
                mock.patch(
                    "presentation_agent.deckcompiler.orchestration.generate.run_composite_qa",
                    return_value=fake_qa,
                ) as composite,
            ):
                completed = resume_generate_workflow(
                    resume=runtime,
                    phase5_bundle=phase5,
                    external_visual_summary=external_summary,
                    external_visual_exit_code=0,
                )
            self.assertEqual(completed.status, "COMPLETED")
            self.assertEqual(completed.exit_code, 0)
            self.assertEqual(composite.call_args.kwargs["authority_mode"], "runtime")
            self.assertFalse(composite.call_args.kwargs["baseline"])


if __name__ == "__main__":
    unittest.main()
