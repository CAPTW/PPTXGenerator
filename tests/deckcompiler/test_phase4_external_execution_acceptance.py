from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

from phase4_external_test_support import (
    load_external_execution_module,
    request_payload,
)


class Phase4ExternalExecutionAcceptanceTests(unittest.TestCase):
    def _verified_blocked_evidence(self):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        contracts = load_external_execution_module("contracts")
        record_module = load_external_execution_module("record")
        verification = load_external_execution_module("verification")
        request = contracts.build_external_execution_request(request_payload())
        request_bytes = contracts.canonical_request_bytes(request)
        record = record_module.build_blocked_execution_record(
            request,
            request_artifact_path="requests/request.json",
            request_bytes=request_bytes,
            created_at="2026-07-17T00:00:00+09:00",
        )
        (root / "requests").mkdir()
        (root / "records").mkdir()
        (root / "requests" / "request.json").write_bytes(request_bytes)
        record_module.write_execution_record(
            root, "records/execution-record.json", record
        )
        report = verification.verify_external_execution_record(
            run_root=root,
            record_relative_path="records/execution-record.json",
            expected_record=record,
            expected_request=request,
            known_input_artifact_ids=request.upstream_artifact_ids,
            created_at="2026-07-17T00:00:01+09:00",
        )
        self.assertEqual(report.final_status, "PASS")
        return temporary, record, report

    def test_verified_contract_record_is_still_release_blocked_and_hash_bound(self) -> None:
        temporary, record, report = self._verified_blocked_evidence()
        self.addCleanup(temporary.cleanup)
        acceptance_module = load_external_execution_module("acceptance")

        acceptance = acceptance_module.evaluate_external_execution_acceptance(
            record,
            report,
            created_at="2026-07-17T00:00:02+09:00",
        )

        self.assertEqual(acceptance.status, "BLOCKED")
        self.assertFalse(acceptance.accepted)
        self.assertFalse(acceptance.release_eligible)
        self.assertIn("NO_ACTUAL_PROVIDER_RESPONSE", acceptance.reason_codes)
        self.assertIn("NO_ACTUAL_OUTPUT", acceptance.reason_codes)
        self.assertIn("ACCEPTANCE_NOT_ENABLED", acceptance.reason_codes)
        self.assertTrue(
            acceptance_module.verify_acceptance_record(
                acceptance,
                expected_hash=acceptance.acceptance_hash,
            )
        )
        with self.assertRaises(ValidationError):
            acceptance.accepted = True  # type: ignore[misc]

    def test_missing_or_unverified_report_fails_without_acceptance_artifact(self) -> None:
        temporary, record, report = self._verified_blocked_evidence()
        self.addCleanup(temporary.cleanup)
        acceptance_module = load_external_execution_module("acceptance")

        with self.assertRaises(acceptance_module.AcceptancePreconditionError):
            acceptance_module.evaluate_external_execution_acceptance(
                record,
                None,
                created_at="2026-07-17T00:00:02+09:00",
            )
        invalid_report = report.model_copy(update={"final_status": "FAIL"})
        with self.assertRaises(acceptance_module.AcceptancePreconditionError):
            acceptance_module.evaluate_external_execution_acceptance(
                record,
                invalid_report,
                created_at="2026-07-17T00:00:02+09:00",
            )

    def test_provider_payload_transport_success_and_output_flags_have_no_authority(self) -> None:
        temporary, record, report = self._verified_blocked_evidence()
        self.addCleanup(temporary.cleanup)
        acceptance_module = load_external_execution_module("acceptance")
        malicious_provider_payload = {
            "accepted": True,
            "release_eligible": True,
            "verdict": "PASS",
            "status": "accepted",
            "trusted": True,
            "http_status": 200,
            "output_exists": True,
        }

        acceptance = acceptance_module.evaluate_external_execution_acceptance(
            record,
            report,
            created_at="2026-07-17T00:00:02+09:00",
        )

        self.assertTrue(malicious_provider_payload["accepted"])
        self.assertEqual(acceptance.status, "BLOCKED")
        self.assertFalse(acceptance.accepted)
        self.assertFalse(acceptance.release_eligible)

    def test_altered_acceptance_record_fails_independent_hash_check(self) -> None:
        temporary, record, report = self._verified_blocked_evidence()
        self.addCleanup(temporary.cleanup)
        acceptance_module = load_external_execution_module("acceptance")
        acceptance = acceptance_module.evaluate_external_execution_acceptance(
            record,
            report,
            created_at="2026-07-17T00:00:02+09:00",
        )
        altered = acceptance.model_copy(
            update={"reason_codes": acceptance.reason_codes + ("ALTERED",)}
        )

        self.assertFalse(
            acceptance_module.verify_acceptance_record(
                altered,
                expected_hash=acceptance.acceptance_hash,
            )
        )


if __name__ == "__main__":
    unittest.main()
