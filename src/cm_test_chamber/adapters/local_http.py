from __future__ import annotations

import json
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from .base import ModelAdapter
from ..runner.result_types import ModelResponse
from ..runner.run_config import ProbeSpec


class LocalHttpAdapter(ModelAdapter):
    def generate(self, probe: ProbeSpec, prompt: str, context: dict[str, Any]) -> ModelResponse:
        if self.config.request_format == "ollama_generate":
            payload = {
                "model": self.config.model_name,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": self.config.temperature, **self.config.sampler_settings},
            }
        elif self.config.request_format == "llama_cpp_completion":
            payload = {
                "prompt": prompt,
                "temperature": self.config.temperature,
                "n_predict": self.config.max_output_tokens,
                "samplers": ["top_k", "top_p", "temperature"],
                **self.config.sampler_settings,
            }
        else:
            raise ValueError(f"Unsupported request_format: {self.config.request_format}")
        request = Request(
            self.config.endpoint or "",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.config.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except URLError as exc:
            raise RuntimeError(f"Local HTTP adapter request failed: {exc}") from exc
        body = json.loads(raw)
        text = body.get("response") or body.get("content") or body.get("generated_text") or body.get("text") or ""
        return ModelResponse(text=text, metadata={"raw_response": body})
