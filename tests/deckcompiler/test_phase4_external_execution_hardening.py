from __future__ import annotations

import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from pydantic import ValidationError

from phase4_external_test_support import (
    load_external_execution_module,
    request_payload,
)


NEAR_MATCH_PROVIDER_IDS: tuple[object, ...] = (
    "OpenAI",
    "OPENAI",
    " openai",
    "openai ",
    "openai/api",
    "openai_api_v2",
    "openai-api",
    "openai.",
    "scout",
    "scout_assist/",
    "../openai",
    "openai\\other",
    "openai\x00",
    "openai\x1f",
    "\u03bfpennai",
    "\u043epenai",
    "",
    "   ",
    None,
    1,
    1.0,
    True,
    [],
    {},
)


class Phase4ExternalExecutionHardeningTests(unittest.TestCase):
    def test_raw_provider_authorization_is_exact_and_precedes_schema_validation(self) -> None:
        contracts = load_external_execution_module("contracts")
        self.assertTrue(hasattr(contracts, "authorize_external_executable_id"))
        self.assertTrue(hasattr(contracts, "build_external_execution_request"))

        for provider_id in contracts.APPROVED_EXTERNAL_EXECUTABLE_IDS:
            self.assertEqual(
                contracts.authorize_external_executable_id(provider_id),
                provider_id,
            )

        for rejected in NEAR_MATCH_PROVIDER_IDS:
            with self.subTest(rejected=rejected), self.assertRaises(
                contracts.ExternalExecutableAuthorizationError
            ):
                contracts.authorize_external_executable_id(rejected)

        # The provider error must win even though every other request field is absent.
        with self.assertRaises(contracts.ExternalExecutableAuthorizationError):
            contracts.build_external_execution_request(
                {"external_executable_id": "OpenAI"}
            )

    def test_request_semantic_identity_and_hash_ignore_attempt_identity(self) -> None:
        contracts = load_external_execution_module("contracts")
        first_payload = request_payload()
        second_payload = deepcopy(first_payload)
        second_payload["execution_id"] = "exec_ffffffffffffffffffff"
        second_payload["attempt_number"] = 2

        first = contracts.build_external_execution_request(first_payload)
        second = contracts.build_external_execution_request(second_payload)

        self.assertEqual(first.request_id, second.request_id)
        self.assertEqual(
            contracts.compute_request_semantic_sha256(first),
            contracts.compute_request_semantic_sha256(second),
        )
        self.assertNotEqual(
            contracts.canonical_request_bytes(first),
            contracts.canonical_request_bytes(second),
        )

    def test_blocked_record_cannot_claim_transport_response_or_output(self) -> None:
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

        self.assertEqual(record.status, "blocked")
        self.assertFalse(record.transport_attempted)
        self.assertEqual(record.transport_call_count, 0)
        self.assertIsNone(record.response_artifact)
        self.assertIsNone(record.response_hash)
        self.assertEqual(record.outputs, ())
        self.assertEqual(
            record.blocked_reason,
            "external_transport_disabled_contract_only",
        )

        payload = record.model_dump(mode="json")
        payload["transport_attempted"] = True
        with self.assertRaises(ValidationError):
            record_module.ExternalExecutionRecord.model_validate(payload)

    def test_hash_domains_are_independent_and_mutations_fail(self) -> None:
        record_module = load_external_execution_module("record")
        verification = load_external_execution_module("verification")
        domains = {
            record_module.REQUEST_HASH_DOMAIN,
            record_module.RESPONSE_HASH_DOMAIN,
            record_module.OUTPUT_HASH_DOMAIN,
            record_module.EXECUTION_RECORD_HASH_DOMAIN,
            verification.VERIFICATION_REPORT_HASH_DOMAIN,
        }
        self.assertEqual(len(domains), 5)

        response = b'repository-authored synthetic provider response'
        output = b'repository-authored synthetic output bytes'
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
            "HASH_DOMAIN_MISMATCH",
            verification.verify_hash_binding(
                output,
                output_hash,
                expected_domain=record_module.RESPONSE_HASH_DOMAIN,
            ),
        )

    def test_writer_is_root_confined_write_once_and_read_back_verified(self) -> None:
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

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "records").mkdir()
            path = record_module.write_execution_record(
                root,
                "records/execution-record.json",
                record,
            )
            self.assertEqual(
                path.read_bytes(),
                record_module.canonical_execution_record_bytes(record),
            )
            with self.assertRaises(record_module.ExecutionRecordImmutableError):
                record_module.write_execution_record(
                    root,
                    "records/execution-record.json",
                    record,
                )
            for unsafe in (
                "../escape.json",
                str(root.parent / "absolute.json"),
                "records/stream.json:secret",
                "CON",
                ".",
            ):
                with self.subTest(unsafe=unsafe), self.assertRaises(
                    record_module.ExecutionRecordPathError
                ):
                    record_module.write_execution_record(root, unsafe, record)

    def test_verifier_reads_actual_bytes_and_rejects_declared_hash_resealing(self) -> None:
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

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "requests").mkdir()
            (root / "records").mkdir()
            (root / "requests" / "request.json").write_bytes(request_bytes)
            path = record_module.write_execution_record(
                root,
                "records/execution-record.json",
                record,
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

            tampered = json.loads(path.read_text(encoding="utf-8"))
            tampered["blocked_reason"] = "tampered-but-resealed"
            tampered["record_hash"] = record_module.compute_execution_record_hash(
                tampered
            ).model_dump(mode="json")
            path.write_bytes(record_module.canonical_json_bytes(tampered))
            report = verification.verify_external_execution_record(
                run_root=root,
                record_relative_path="records/execution-record.json",
                expected_record=record,
                expected_request=request,
                known_input_artifact_ids=request.upstream_artifact_ids,
                created_at="2026-07-17T00:00:02+09:00",
            )
            self.assertEqual(report.final_status, "FAIL")
            self.assertIn("EXPECTED_RECORD_MISMATCH", report.errors)

    def test_acceptance_requires_verified_report_and_remains_hash_bound_blocked(self) -> None:
        contracts = load_external_execution_module("contracts")
        record_module = load_external_execution_module("record")
        verification = load_external_execution_module("verification")
        acceptance_module = load_external_execution_module("acceptance")
        request = contracts.build_external_execution_request(request_payload())
        request_bytes = contracts.canonical_request_bytes(request)
        record = record_module.build_blocked_execution_record(
            request,
            request_artifact_path="requests/request.json",
            request_bytes=request_bytes,
            created_at="2026-07-17T00:00:00+09:00",
        )

        with self.assertRaises(acceptance_module.AcceptancePreconditionError):
            acceptance_module.evaluate_external_execution_acceptance(
                record,
                None,
                created_at="2026-07-17T00:00:03+09:00",
            )

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "requests").mkdir()
            (root / "records").mkdir()
            (root / "requests" / "request.json").write_bytes(request_bytes)
            record_module.write_execution_record(
                root,
                "records/execution-record.json",
                record,
            )
            report = verification.verify_external_execution_record(
                run_root=root,
                record_relative_path="records/execution-record.json",
                expected_record=record,
                expected_request=request,
                known_input_artifact_ids=request.upstream_artifact_ids,
                created_at="2026-07-17T00:00:01+09:00",
            )
            acceptance = acceptance_module.evaluate_external_execution_acceptance(
                record,
                report,
                created_at="2026-07-17T00:00:03+09:00",
            )
            self.assertEqual(acceptance.status, "BLOCKED")
            self.assertFalse(acceptance.accepted)
            self.assertFalse(acceptance.release_eligible)
            self.assertTrue(
                acceptance_module.verify_acceptance_record(
                    acceptance,
                    expected_hash=acceptance.acceptance_hash,
                )
            )


if __name__ == "__main__":
    unittest.main()
