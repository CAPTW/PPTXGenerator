from __future__ import annotations

import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from jsonschema import Draft202012Validator

from phase4_external_test_support import (
    load_deckcompiler_module,
    load_external_execution_module,
    request_payload,
)


EXPECTED_SCHEMA_BINDINGS = {
    "external_execution_request": "external-execution-request.schema.json",
    "external_execution_record": "external-execution-record.schema.json",
    "external_execution_verification_report": "external-execution-verification-report.schema.json",
    "external_execution_acceptance": "external-execution-acceptance.schema.json",
}
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "phase4_external"


class Phase4ExternalExecutionSchemaTests(unittest.TestCase):
    def _artifacts(self):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
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
        acceptance = acceptance_module.evaluate_external_execution_acceptance(
            record,
            report,
            created_at="2026-07-17T00:00:02+09:00",
        )
        return temporary, request, record, report, acceptance

    def test_four_schemas_are_registered_meta_valid_unique_and_accept_typed_artifacts(self) -> None:
        schemas = load_deckcompiler_module("schemas")
        temporary, request, record, report, acceptance = self._artifacts()
        self.addCleanup(temporary.cleanup)
        schema_ids: list[str] = []
        for schema_name, filename in EXPECTED_SCHEMA_BINDINGS.items():
            self.assertEqual(schemas.SCHEMA_FILES.get(schema_name), filename)
            schema = schemas.load_schema(schema_name)
            Draft202012Validator.check_schema(schema)
            schema_ids.append(schema["$id"])
        self.assertEqual(len(schema_ids), len(set(schema_ids)))
        contracts = load_external_execution_module("contracts")
        self.assertEqual(
            tuple(
                schemas.load_schema("external_execution_request")["$defs"][
                    "externalExecutableId"
                ]["enum"]
            ),
            contracts.APPROVED_EXTERNAL_EXECUTABLE_IDS,
        )

        cases = {
            "external_execution_request": request.model_dump(mode="json"),
            "external_execution_record": record.model_dump(mode="json"),
            "external_execution_verification_report": report.model_dump(mode="json"),
            "external_execution_acceptance": acceptance.model_dump(mode="json"),
        }
        for schema_name, payload in cases.items():
            with self.subTest(schema_name=schema_name):
                errors = list(schemas.validator_for(schema_name).iter_errors(payload))
                self.assertEqual(errors, [], errors)

    def test_request_schema_rejects_near_match_nonstring_secret_and_unknown_fields(self) -> None:
        schemas = load_deckcompiler_module("schemas")
        temporary, request, _, _, _ = self._artifacts()
        self.addCleanup(temporary.cleanup)
        validator = schemas.validator_for("external_execution_request")
        for rejected in (
            "OpenAI",
            " openai",
            "openai ",
            "openai-api",
            "openai_api_v2",
            "../openai",
            "openai\x00",
            "\u043epenai",
            "",
            None,
            1,
            True,
            [],
            {},
        ):
            payload = request.model_dump(mode="json")
            payload["external_executable_id"] = rejected
            with self.subTest(rejected=rejected):
                self.assertTrue(list(validator.iter_errors(payload)))

        for forbidden in ("api_key", "token", "authorization", "secret"):
            payload = request.model_dump(mode="json")
            payload[forbidden] = "forbidden"
            with self.subTest(forbidden=forbidden):
                self.assertTrue(list(validator.iter_errors(payload)))

    def test_record_schema_rejects_transport_output_hash_domain_and_unknown_fields(self) -> None:
        schemas = load_deckcompiler_module("schemas")
        temporary, _, record, _, _ = self._artifacts()
        self.addCleanup(temporary.cleanup)
        validator = schemas.validator_for("external_execution_record")
        base = record.model_dump(mode="json")
        mutations = (
            {"transport_attempted": True},
            {"transport_call_count": 1},
            {"status": "succeeded"},
            {"response_artifact": {"relative_path": "response.json"}},
            {"outputs": [{"path": "output.png"}]},
            {"api_key": "forbidden"},
        )
        for mutation in mutations:
            payload = deepcopy(base)
            payload.update(mutation)
            with self.subTest(mutation=mutation):
                self.assertTrue(list(validator.iter_errors(payload)))

        payload = deepcopy(base)
        payload["request_artifact"]["hash"]["hash_domain"] = (
            "deckcompiler.external_execution.output.v1"
        )
        self.assertTrue(list(validator.iter_errors(payload)))

    def test_acceptance_and_verification_schemas_cannot_be_promoted_or_extended(self) -> None:
        schemas = load_deckcompiler_module("schemas")
        temporary, _, _, report, acceptance = self._artifacts()
        self.addCleanup(temporary.cleanup)

        payload = acceptance.model_dump(mode="json")
        payload.update(
            {"status": "ACCEPTED", "accepted": True, "release_eligible": True}
        )
        errors = list(
            schemas.validator_for("external_execution_acceptance").iter_errors(
                payload
            )
        )
        self.assertGreaterEqual(len(errors), 3)

        proof_payload = report.model_dump(mode="json")
        proof_payload["accepted"] = False
        self.assertTrue(
            list(
                schemas.validator_for(
                    "external_execution_verification_report"
                ).iter_errors(proof_payload)
            )
        )

    def test_repository_authored_positive_and_negative_fixtures(self) -> None:
        schemas = load_deckcompiler_module("schemas")
        valid_bindings = {
            "external-execution-request.json": "external_execution_request",
            "external-execution-record.json": "external_execution_record",
            "external-execution-verification-report.json": (
                "external_execution_verification_report"
            ),
            "external-execution-acceptance.json": "external_execution_acceptance",
        }
        for filename, schema_name in valid_bindings.items():
            payload = json.loads((FIXTURES / "valid" / filename).read_text(encoding="utf-8"))
            with self.subTest(valid=filename):
                self.assertEqual(
                    list(schemas.validator_for(schema_name).iter_errors(payload)),
                    [],
                )

        invalid_bindings = {
            "external-execution-request-near-match-provider.json": (
                "external_execution_request"
            ),
            "external-execution-request-secret-field.json": (
                "external_execution_request"
            ),
            "external-execution-record-transport-output.json": (
                "external_execution_record"
            ),
            "external-execution-acceptance-promoted.json": (
                "external_execution_acceptance"
            ),
        }
        for filename, schema_name in invalid_bindings.items():
            payload = json.loads((FIXTURES / "invalid" / filename).read_text(encoding="utf-8"))
            with self.subTest(invalid=filename):
                self.assertTrue(
                    list(schemas.validator_for(schema_name).iter_errors(payload))
                )


if __name__ == "__main__":
    unittest.main()
