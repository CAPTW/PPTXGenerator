from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from phase4_external_test_support import (
    load_external_execution_module,
    request_payload,
)


class PoisonTransport:
    def __init__(self) -> None:
        self.call_count = 0
        self.credential_lookup_count = 0
        self.output_write_count = 0

    def execute(self, request):  # pragma: no cover - any call is a test failure
        self.call_count += 1
        self.credential_lookup_count += 1
        self.output_write_count += 1
        raise AssertionError(f"disabled adapter called transport for {request.request_id}")


class Phase4OpenAIAdapterDisabledTests(unittest.TestCase):
    def test_openai_adapter_is_unconditionally_disabled_before_transport(self) -> None:
        contracts = load_external_execution_module("contracts")
        adapter_module = load_external_execution_module("openai_adapter")
        request = contracts.build_external_execution_request(request_payload())
        transport = PoisonTransport()

        with patch.dict(os.environ, {"OPENAI_API_KEY": "must-not-enable-adapter"}):
            adapter = adapter_module.OpenAIAdapterSkeleton()
            self.assertIsInstance(adapter, contracts.ExternalExecutableAdapter)
            self.assertFalse(adapter.enabled)
            self.assertEqual(adapter.external_executable_id, "openai")
            with self.assertRaises(adapter_module.ExternalExecutionDisabledError) as caught:
                adapter.execute(request, transport)

        self.assertEqual(caught.exception.code, "DC_IMAGE_GENERATION_ADAPTER_DISABLED")
        self.assertEqual(caught.exception.stage, "external_execution_contract")
        self.assertEqual(
            caught.exception.reason,
            "external_transport_disabled_contract_only",
        )
        self.assertEqual(transport.call_count, 0)
        self.assertEqual(transport.credential_lookup_count, 0)
        self.assertEqual(transport.output_write_count, 0)

    def test_unauthorized_raw_provider_is_rejected_before_transport(self) -> None:
        contracts = load_external_execution_module("contracts")
        adapter_module = load_external_execution_module("openai_adapter")
        transport = PoisonTransport()

        with self.assertRaises(contracts.ExternalExecutableAuthorizationError):
            adapter_module.OpenAIAdapterSkeleton().execute(
                {"external_executable_id": "OpenAI"}, transport
            )

        self.assertEqual(transport.call_count, 0)
        self.assertEqual(transport.credential_lookup_count, 0)
        self.assertEqual(transport.output_write_count, 0)

    def test_openai_adapter_has_no_runtime_enable_or_endpoint_configuration(self) -> None:
        adapter_module = load_external_execution_module("openai_adapter")
        adapter = adapter_module.OpenAIAdapterSkeleton()

        for forbidden in (
            "api_key",
            "endpoint",
            "headers",
            "allow_network_calls",
            "enable",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertFalse(hasattr(adapter, forbidden))

        with self.assertRaises(TypeError):
            adapter_module.OpenAIAdapterSkeleton(enabled=True)


if __name__ == "__main__":
    unittest.main()
