from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

from phase4_external_test_support import (
    load_external_execution_module,
    request_payload,
)


class Phase4ExternalExecutionVerificationTests(unittest.TestCase):
    def _evidence(self, root: Path):
        contracts = load_external_execution_module("contracts")
        record_module = load_external_execution_module("record")
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
        request_path = root / "requests" / "request.json"
        request_path.write_bytes(request_bytes)
        record_path = record_module.write_execution_record(
            root, "records/execution-record.json", record
        )
        return contracts, record_module, request, record, request_path, record_path

    def _verify(self, root: Path, request, record):
        verification = load_external_execution_module("verification")
        return verification.verify_external_execution_record(
            run_root=root,
            record_relative_path="records/execution-record.json",
            expected_record=record,
            expected_request=request,
            known_input_artifact_ids=request.upstream_artifact_ids,
            created_at="2026-07-17T00:00:01+09:00",
        )

    def test_verifier_recomputes_actual_bytes_and_returns_hash_bound_report(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            _, _, request, record, _, _ = self._evidence(root)
            verification = load_external_execution_module("verification")

            report = self._verify(root, request, record)

            self.assertEqual(report.final_status, "PASS")
            self.assertEqual(report.errors, ())
            self.assertEqual(report.request_verification_status, "valid")
            self.assertEqual(report.response_verification_status, "absent_expected")
            self.assertEqual(report.output_verification_statuses, ())
            self.assertEqual(
                report.report_hash,
                verification.compute_verification_report_hash(report),
            )
            with self.assertRaises(ValidationError):
                report.final_status = "FAIL"  # type: ignore[misc]

    def test_request_record_and_length_mutations_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            _, record_module, request, record, request_path, record_path = (
                self._evidence(root)
            )

            request_path.write_bytes(request_path.read_bytes() + b" ")
            report = self._verify(root, request, record)
            self.assertEqual(report.final_status, "FAIL")
            self.assertIn("REQUEST_HASH_BYTE_COUNT_MISMATCH", report.errors)
            self.assertIn("REQUEST_HASH_DIGEST_MISMATCH", report.errors)

            request_path.write_bytes(
                load_external_execution_module("contracts").canonical_request_bytes(
                    request
                )
            )
            record_path.write_bytes(record_path.read_bytes()[:100])
            report = self._verify(root, request, record)
            self.assertEqual(report.final_status, "FAIL")
            self.assertIn("RECORD_ARTIFACT_INVALID", report.errors)

            record_path.write_bytes(
                record_module.canonical_execution_record_bytes(record)
            )
            tampered = json.loads(record_path.read_text(encoding="utf-8"))
            tampered["record_hash"]["digest"] = "0" * 64
            record_path.write_bytes(record_module.canonical_json_bytes(tampered))
            report = self._verify(root, request, record)
            self.assertEqual(report.final_status, "FAIL")
            self.assertIn("EXPECTED_RECORD_MISMATCH", report.errors)

    def test_declared_digest_cannot_force_pass_after_resealing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            _, record_module, request, record, _, record_path = self._evidence(root)
            payload = json.loads(record_path.read_text(encoding="utf-8"))
            payload["created_at"] = "2099-01-01T00:00:00Z"
            payload["record_hash"] = record_module.compute_execution_record_hash(
                payload
            ).model_dump(mode="json")
            record_path.write_bytes(record_module.canonical_json_bytes(payload))

            report = self._verify(root, request, record)

            self.assertEqual(report.final_status, "FAIL")
            self.assertIn("EXPECTED_RECORD_MISMATCH", report.errors)
            self.assertIn("EXPECTED_RECORD_HASH_MISMATCH", report.errors)

    def test_response_and_output_byte_domains_are_independent(self) -> None:
        record_module = load_external_execution_module("record")
        verification = load_external_execution_module("verification")
        response = b'{"synthetic":"repository-authored-response"}'
        output = b"repository-authored-synthetic-output"
        response_hash = record_module.build_hash_binding(
            response, record_module.RESPONSE_HASH_DOMAIN
        )
        output_hash = record_module.build_hash_binding(
            output, record_module.OUTPUT_HASH_DOMAIN
        )

        self.assertEqual(
            verification.verify_hash_binding(
                response,
                response_hash,
                expected_domain=record_module.RESPONSE_HASH_DOMAIN,
            ),
            (),
        )
        self.assertIn(
            "HASH_DIGEST_MISMATCH",
            verification.verify_hash_binding(
                response + b"!",
                response_hash,
                expected_domain=record_module.RESPONSE_HASH_DOMAIN,
            ),
        )
        self.assertIn(
            "HASH_BYTE_COUNT_MISMATCH",
            verification.verify_hash_binding(
                output,
                output_hash.model_copy(update={"byte_count": output_hash.byte_count + 1}),
                expected_domain=record_module.OUTPUT_HASH_DOMAIN,
            ),
        )
        self.assertIn(
            "HASH_DOMAIN_MISMATCH",
            verification.verify_hash_binding(
                output,
                output_hash,
                expected_domain=record_module.RESPONSE_HASH_DOMAIN,
            ),
        )

    def test_execution_provider_source_and_input_relations_are_verified(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            contracts, _, request, record, _, _ = self._evidence(root)
            changed_payload = request_payload("openai_api")
            changed_payload["source_commit"] = "f" * 40
            changed_request = contracts.build_external_execution_request(changed_payload)

            report = load_external_execution_module(
                "verification"
            ).verify_external_execution_record(
                run_root=root,
                record_relative_path="records/execution-record.json",
                expected_record=record,
                expected_request=changed_request,
                known_input_artifact_ids=(),
                created_at="2026-07-17T00:00:02+09:00",
            )

            self.assertEqual(report.final_status, "FAIL")
            self.assertIn("REQUEST_ARTIFACT_MISMATCH", report.errors)
            self.assertIn("INPUT_ARTIFACT_UNRESOLVED", report.errors)
            self.assertIn("SOURCE_COMMIT_MISMATCH", report.errors)


if __name__ == "__main__":
    unittest.main()
