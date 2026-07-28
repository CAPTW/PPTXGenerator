"""OpenAI GPT-Image provider for opt-in D07.2 visual-field assets."""

from __future__ import annotations

import base64
import json
import os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .image_generation_provider import ImageGenerationRequest, ImageGenerationResult, hash_text, sha256_file


class OpenAIGPTImageProvider:
    provider_name = "openai"

    def __init__(self, *, config: dict[str, Any], env: dict[str, str] | None = None) -> None:
        self.config = config
        self.env = env if env is not None else os.environ
        self.model = str(config.get("model") or "gpt-image-2")
        self.api_key_name = str(config.get("env_api_key_name") or "OPENAI_API_KEY")

    def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        api_key = self.env.get(self.api_key_name)
        if not api_key:
            return self._failed(request, "OPENAI_API_KEY missing from environment.")
        if self.config.get("image_generation_enabled") is not True or self.config.get("allow_network_calls") is not True:
            return self._failed(request, "Image generation config does not permit network calls.")
        request.output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "model": self.model,
            "prompt": request.prompt,
            "size": request.requested_size,
            "quality": self.config.get("quality", "high"),
            "n": 1,
            "response_format": "b64_json",
        }
        raw = json.dumps(payload).encode("utf-8")
        http_request = urllib.request.Request(
            "https://api.openai.com/v1/images/generations",
            data=raw,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(http_request, timeout=180) as response:  # noqa: S310 - explicit opt-in OpenAI API call.
                body = json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001 - provider result records failure without exposing secrets.
            return self._failed(request, f"OpenAI image generation request failed: {exc}")
        item = (body.get("data") or [{}])[0]
        b64 = item.get("b64_json")
        if not b64:
            return self._failed(request, "OpenAI response did not include b64_json output.")
        request.output_path.write_bytes(base64.b64decode(b64))
        return ImageGenerationResult(
            slot_id=request.slot_id,
            status="generated",
            output_path=request.output_path.as_posix(),
            provider=self.provider_name,
            model=self.model,
            requested_size=request.requested_size,
            prompt_hash=hash_text(request.prompt),
            sha256=sha256_file(request.output_path),
            created_at=datetime.now(timezone.utc).isoformat(),
            request_id=body.get("id") or item.get("id"),
        )

    def _failed(self, request: ImageGenerationRequest, error: str) -> ImageGenerationResult:
        return ImageGenerationResult(
            slot_id=request.slot_id,
            status="failed",
            output_path=None,
            provider=self.provider_name,
            model=self.model,
            requested_size=request.requested_size,
            prompt_hash=hash_text(request.prompt),
            sha256=None,
            created_at=datetime.now(timezone.utc).isoformat(),
            error=error,
        )
