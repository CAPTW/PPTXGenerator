from __future__ import annotations

import sys
import unittest
from pathlib import Path

from pydantic import ValidationError

from phase4_external_test_support import load_external_execution_module


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


APPROVED_EXTERNAL_EXECUTABLE_IDS = (
    "openai",
    "openai_api",
    "scout_assist",
    "scout_suggestions",
)


def _contracts_module():
    return load_external_execution_module("contracts")


def _request_payload(executable_id: str = "openai") -> dict[str, object]:
    return {
        "run_id": "run_0123456789abcdef0123",
        "slide_id": "slide-001",
        "execution_id": "exec_0123456789abcdef0123",
        "attempt_number": 1,
        "external_executable_id": executable_id,
        "prompt_id": "prompt-001",
        "prompt": "Create a restrained 16:9 systems diagram reference.",
        "composition_plan_id": "composition-001",
        "composition_plan_sha256": "1" * 64,
        "requested_model": "gpt-image-2",
        "requested_width": 1920,
        "requested_height": 1080,
        "requested_media_type": "image/png",
        "references": [
            {
                "artifact_id": "art_0123456789abcdef0123",
                "sha256": "2" * 64,
            }
        ],
        "source_commit": "8c9f7f1d6ef15868010e2aa9e5bf52467b8e468d",
        "upstream_artifact_ids": ["art_0123456789abcdef0123"],
    }


class Phase4ExternalAdapterContractTests(unittest.TestCase):
    def test_only_the_four_approved_external_executable_ids_round_trip(self) -> None:
        contracts = _contracts_module()

        self.assertEqual(
            contracts.APPROVED_EXTERNAL_EXECUTABLE_IDS,
            APPROVED_EXTERNAL_EXECUTABLE_IDS,
        )
        for executable_id in APPROVED_EXTERNAL_EXECUTABLE_IDS:
            request = contracts.build_external_execution_request(
                _request_payload(executable_id)
            )
            self.assertEqual(request.external_executable_id, executable_id)

        for rejected in (
            "OpenAI",
            "openai ",
            "image_api",
            "scout-assist",
            "unknown",
            "",
        ):
            with self.subTest(rejected=rejected), self.assertRaises(
                contracts.ExternalExecutableAuthorizationError
            ):
                contracts.build_external_execution_request(
                    _request_payload(rejected)
                )

    def test_request_is_deeply_immutable_and_rejects_secret_or_extra_fields(self) -> None:
        contracts = _contracts_module()
        payload = _request_payload()
        mutable_references = payload["references"]
        mutable_upstream_ids = payload["upstream_artifact_ids"]
        request = contracts.build_external_execution_request(payload)

        self.assertIsInstance(request.references, tuple)
        self.assertIsInstance(request.upstream_artifact_ids, tuple)
        mutable_references.append(  # type: ignore[union-attr]
            {"artifact_id": "art_ffffffffffffffffffff", "sha256": "f" * 64}
        )
        mutable_upstream_ids.append("art_ffffffffffffffffffff")  # type: ignore[union-attr]
        self.assertEqual(len(request.references), 1)
        self.assertEqual(len(request.upstream_artifact_ids), 1)

        with self.assertRaises(ValidationError):
            request.slide_id = "mutated"  # type: ignore[misc]

        for forbidden_field in ("api_key", "authorization", "endpoint", "headers"):
            with self.subTest(forbidden_field=forbidden_field):
                invalid = _request_payload()
                invalid[forbidden_field] = "secret-or-routing-data"
                with self.assertRaises(ValidationError):
                    contracts.build_external_execution_request(invalid)

    def test_request_requires_exact_16_by_9_dimensions(self) -> None:
        contracts = _contracts_module()
        invalid = _request_payload()
        invalid["requested_height"] = 1081

        with self.assertRaisesRegex(ValidationError, "16:9"):
            contracts.build_external_execution_request(invalid)


if __name__ == "__main__":
    unittest.main()
