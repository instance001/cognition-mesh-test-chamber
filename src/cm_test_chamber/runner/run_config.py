from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class ModelConfig:
    model_name: str
    model_family: str
    quantization: str
    backend: str
    context_length: int
    hardware: str
    temperature: float
    sampler_settings: dict[str, Any]
    system_prompt: str
    prompt_template: str
    tool_permissions: str
    host_wrapper: str
    memory: str
    mode: str = "good"
    endpoint: str | None = None
    request_format: str | None = None
    timeout_seconds: int = 120
    max_output_tokens: int = 512


@dataclass(slots=True)
class HostProfile:
    host_name: str
    schema_lock: bool
    real_tools_enabled: bool
    network_enabled: bool
    filesystem_mode: str
    requires_patch_preview: bool
    requires_source_lock: bool
    operator_confirmation_required: bool


@dataclass(slots=True)
class TaskShape:
    task_id: str
    category: str
    requires_precision: str
    requires_creativity: str
    requires_source_fidelity: str
    requires_tool_use: bool
    failure_cost: str
    ambiguity_load: str
    allowed_retries: int


@dataclass(slots=True)
class ProbeSpec:
    probe_id: str
    title: str
    category: str
    evaluator: str
    task_shape: TaskShape
    prompt: str
    source_text: str | None = None
    source_file: str | None = None
    sandbox_repo: str | None = None
    expected_json: dict[str, Any] | None = None
    required_keys: list[str] | None = None
    required_phrases: list[str] | None = None
    forbidden_phrases: list[str] | None = None
    required_patch_terms: list[str] | None = None
    forbidden_patch_terms: list[str] | None = None
    target_files: list[str] | None = None
    allow_new_files: bool = False
    mode: str | None = None
    max_sentences: int | None = None
    initial_prompt: str | None = None
    correction_prompt: str | None = None
    must_acknowledge_correction: bool = False


@dataclass(slots=True)
class TaskPack:
    pack_id: str
    title: str
    probe_paths: list[str]


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_model_config(path: Path) -> ModelConfig:
    return ModelConfig(**_load_json(path))


def load_host_profile(path: Path) -> HostProfile:
    return HostProfile(**_load_json(path))


def load_task_pack(path: Path) -> TaskPack:
    return TaskPack(**_load_json(path))


def load_probe(path: Path) -> ProbeSpec:
    data = _load_json(path)
    data["task_shape"] = TaskShape(**data["task_shape"])
    return ProbeSpec(**data)


def snapshot_config(
    model: ModelConfig,
    host: HostProfile,
    task_pack: TaskPack,
    probes: list[ProbeSpec],
) -> dict[str, Any]:
    return {
        "model": asdict(model),
        "host": asdict(host),
        "task_pack": asdict(task_pack),
        "probes": [asdict(probe) for probe in probes],
    }
