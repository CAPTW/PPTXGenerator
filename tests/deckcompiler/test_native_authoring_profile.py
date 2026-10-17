"""Routing/receipt fixtures only; no model invocation or rendered quality proof."""
from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from presentation_agent.deckcompiler.manifest_io import read_json, write_json
from presentation_agent.deckcompiler.identity import content_sha256
from presentation_agent.deckcompiler.orchestration.execution_profiles import execution_profile_payload
from presentation_agent.deckcompiler.orchestration.generate import start_generate_workflow
from presentation_agent.deckcompiler.orchestration.reconstruction_jobs import (
    prepare_reconstruction_jobs, validate_reconstruction_job_bundle,
)
from presentation_agent.deckcompiler.orchestration.skillset_plan import validate_skillset_execution_plan
from presentation_agent.deckcompiler.orchestration.shared_render_qa import finalize_shared_render_qa
from presentation_agent.deckcompiler.orchestration.streaming_execution import _runtime_profile
from presentation_agent.deckcompiler.schemas import validator_for
import test_general_generate_workflow as upstream


PROFILE = "native-inherited-xhigh"


def execution_record(job):
    return {
        "job_id": job["job_id"],
        "job_content_hash": job["content_hash"],
        "executor": "collaboration.spawn_agent",
        "requested_model": None,
        "requested_reasoning_effort": "xhigh",
        "fork_turns": "none",
        "actual_model": None,
        "actual_reasoning_effort": None,
        "model_attestation": "unavailable",
        "launch_agent_id": "/fixture/native-author",
    }


class NativeAuthoringProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "runtime"
        self.fixture = upstream.GeneralGenerateWorkflowTests()

    def start(self):
        return start_generate_workflow(
            output_dir=self.root, prompt="Native routing contract fixture.",
            prompt_file=None, pdf_paths=(), audience="operators", purpose="test",
            language="English", tone=("clear",), workflow="auto",
            skill_root=self.fixture._make_skill_root(self.root.parent / "skills"),
            execution_profile=PROFILE,
        )

    def build_job(self):
        started = self.start()
        original_writer = self.fixture._write_reconstruction_worker_outputs
        def write_native_fixture(root, slide_count):
            for slide in range(1, slide_count + 1):
                work = root / "pngtopptx-project/work" / f"slide{slide:02d}"
                job = read_json(work / "reconstruction_job.json")
                write_json(work / "worker_execution.json", execution_record(job))
            original_writer(root, slide_count)
        self.fixture._write_reconstruction_worker_outputs = write_native_fixture
        self.fixture._build_run_draft(
            self.root, workflow_id=started.workflow_id, slide_count=1,
            status="COMPLETED", qa_status="PASS", fail_count=0, blocking_count=0,
        )
        prepare_reconstruction_jobs(self.root)
        self.fixture._write_reconstruction_worker_outputs(self.root, 1)
        self.work = self.root / "pngtopptx-project/work/slide01"
        self.job = read_json(self.work / "reconstruction_job.json")
        return self.job

    def receipt_report(self, record):
        path = self.work / "worker_receipt.json"
        receipt = read_json(path)
        if record is not None:
            receipt["workerExecution"] = record
        write_json(path, receipt)
        return validate_reconstruction_job_bundle(self.root, require_worker_outputs=True)

    def test_legacy_default_and_context_remain_unchanged(self):
        default = execution_profile_payload(None)
        self.assertEqual(default["profile_name"], "terra-max")
        self.assertEqual(default["target_model"], "gpt-5.6-terra")
        self.assertEqual(default["worker_context"]["mode"], "minimal_locked")
        self.assertIn("--ignore-user-config", default["worker_context"]["codex_argv"])

    def test_native_profile_is_explicit_and_has_no_cli_claim(self):
        profile = execution_profile_payload(PROFILE)
        self.assertEqual(profile["target_model"], "inherited")
        self.assertEqual(profile["target_reasoning_effort"], "xhigh")
        context = profile["worker_context"]
        self.assertEqual(context["mode"], "native_fresh_context")
        self.assertEqual(context["executor"], "collaboration.spawn_agent")
        self.assertEqual(context["fork_turns"], "none")
        self.assertEqual(context["isolation_scope"], "conversation_history_only")
        self.assertNotIn("codex_argv", context)

    def test_native_plan_passes_schema_and_file_validation(self):
        self.start()
        path = self.root / "skillset_execution_plan.json"
        self.assertEqual(validate_skillset_execution_plan(path), [])
        plan = read_json(path)
        self.assertEqual(plan["command_templates"]["codex_execute_reconstruction_jobs"][0], "NATIVE_AGENT_ACTION")
        self.assertEqual(_runtime_profile(self.root).name, PROFILE)

    def test_schema_rejects_native_cli_claim_and_wrong_fork(self):
        self.start()
        plan = read_json(self.root / "skillset_execution_plan.json")
        for key, value in (("codex_argv", ["--ephemeral"]), ("fork_turns", "all")):
            changed = copy.deepcopy(plan)
            changed["execution_profile"]["worker_context"][key] = value
            self.assertTrue(list(validator_for("codex_skillset_execution_plan").iter_errors(changed)))

    def test_schema_rejects_cross_profile_context_and_model(self):
        self.start()
        plan = read_json(self.root / "skillset_execution_plan.json")
        for key, value in (("profile_name", "terra-max"), ("target_model", "gpt-5.6-terra"), ("target_reasoning_effort", "max")):
            changed = copy.deepcopy(plan)
            changed["execution_profile"][key] = value
            self.assertTrue(list(validator_for("codex_skillset_execution_plan").iter_errors(changed)))

    def test_streaming_rejects_misreported_model(self):
        self.start()
        path = self.root / "skillset_execution_plan.json"
        plan = read_json(path)
        plan["execution_profile"]["target_model"] = "gpt-5.6-terra"
        write_json(path, plan)
        with self.assertRaises(Exception) as raised:
            _runtime_profile(self.root)
        self.assertIn("target_model", str(raised.exception))

    def test_plan_rejects_rehashed_cli_dispatch_for_native_context(self):
        self.start()
        path = self.root / "skillset_execution_plan.json"
        plan = read_json(path)
        plan["command_templates"]["codex_execute_reconstruction_jobs"][0] = "CODEX_AGENT_ACTION"
        plan["content_hash"] = content_sha256({key: value for key, value in plan.items() if key != "content_hash"})
        write_json(path, plan)
        issues = validate_skillset_execution_plan(path)
        self.assertTrue(any("dispatch action" in issue for issue in issues), issues)

    def test_public_job_carries_native_contract_and_prompt(self):
        job = self.build_job()
        self.assertEqual(job["execution_profile"]["profile_name"], PROFILE)
        prompt = (self.work / "worker_prompt.md").read_text()
        self.assertIn("collaboration.spawn_agent", prompt)
        self.assertIn("actual_model", prompt)
        self.assertNotIn("Launch this fresh worker with the exact", prompt)
        self.assertEqual(job["authoring_contract"]["exact_text_source"], "semantic_sidecar")
        self.assertEqual(job["authoring_contract"]["measured_geometry_source"], "vector_preflight.measurement_inventory")

    def test_native_worker_receipt_requires_execution_metadata(self):
        self.build_job()
        report = self.receipt_report(None)
        self.assertFalse(report["valid"])
        self.assertTrue(any("workerExecution" in issue for issue in report["issues"]), report)

    def test_unreported_actual_model_receipt_passes_contract_only(self):
        self.build_job()
        report = self.receipt_report(execution_record(self.job))
        self.assertTrue(report["valid"], report)

    def test_run_schema_preserves_requested_native_route_without_model_attestation(self):
        self.build_job()
        draft = read_json(self.root / "codex_run.draft.json")
        draft["performance"].update(profile_name=PROFILE, target_model="inherited", target_reasoning_effort="xhigh")
        validator = validator_for("codex_pptx_generation_run")
        self.assertEqual(list(validator.iter_errors(draft)), [])
        draft["performance"]["target_model"] = "gpt-5.6-terra"
        self.assertTrue(list(validator.iter_errors(draft)))

    def test_receipt_rejects_false_attestation_and_effort(self):
        self.build_job()
        for key, value in (("actual_model", "gpt-5.6-terra"), ("actual_reasoning_effort", "xhigh"), ("requested_reasoning_effort", "medium"), ("model_attestation", "verified"), ("launch_agent_id", "")):
            record = execution_record(self.job)
            record[key] = value
            report = self.receipt_report(record)
            self.assertFalse(report["valid"], key)
            self.assertTrue(any("workerExecution" in issue for issue in report["issues"]), report)

    def test_shared_qa_finalizer_consumes_native_launch_input(self):
        self.build_job()
        result = finalize_shared_render_qa(
            self.root,
            summary_path=self.root / "pngtopptx-project/out/visual_qa_summary_final.json",
        )
        receipt = read_json(result.receipt_paths[0])
        self.assertEqual(receipt["workerExecution"], execution_record(self.job))
        self.assertIn("worker_execution.json", receipt["artifactHashes"])

    def test_authoring_rejects_stale_job_launch_input(self):
        self.build_job()
        record = execution_record(self.job)
        record["job_content_hash"] = "0" * 64
        write_json(self.work / "worker_execution.json", record)
        report = validate_reconstruction_job_bundle(self.root, require_authoring_outputs=True)
        self.assertFalse(report["valid"])
        self.assertTrue(any("job_content_hash" in issue for issue in report["issues"]), report)


if __name__ == "__main__":
    unittest.main()
