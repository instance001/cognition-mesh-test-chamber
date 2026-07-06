from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..runner.result_types import ModelResponse
from ..runner.run_config import ModelConfig, ProbeSpec


class ModelAdapter(ABC):
    def __init__(self, config: ModelConfig) -> None:
        self.config = config

    @abstractmethod
    def generate(self, probe: ProbeSpec, prompt: str, context: dict[str, Any]) -> ModelResponse:
        raise NotImplementedError
