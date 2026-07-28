"""A deliberately non-executable OpenAI adapter boundary for Phase 4."""

from __future__ import annotations

from typing import NoReturn

from .contracts import (
    ExternalExecutionRequest,
    ExternalTransport,
    authorize_external_executable_id,
    build_external_execution_request,
)
from .record import BLOCKED_REASON


class ExternalExecutionDisabledError(RuntimeError):
    """Stable fail-closed error raised before any transport can be called."""

    code = "DC_IMAGE_GENERATION_ADAPTER_DISABLED"
    reason = BLOCKED_REASON
    stage = "external_execution_contract"

    def __init__(self, request_id: str) -> None:
        self.request_id = request_id
        super().__init__(
            f"{self.code}: {self.reason} for request {request_id}."
        )


class OpenAIAdapterSkeleton:
    """Typed seam only; no credential, endpoint, SDK, or network surface exists."""

    enabled = False
    external_executable_id = "openai"
    adapter_id = "deckcompiler-openai-disabled-v1"

    def execute(
        self,
        request: ExternalExecutionRequest | object,
        transport: ExternalTransport,
    ) -> NoReturn:
        validated_request = (
            request
            if isinstance(request, ExternalExecutionRequest)
            else build_external_execution_request(request)
        )
        authorize_external_executable_id(validated_request.external_executable_id)
        del transport
        raise ExternalExecutionDisabledError(validated_request.request_id)


__all__ = ["ExternalExecutionDisabledError", "OpenAIAdapterSkeleton"]
