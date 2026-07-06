from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any


def to_plain_data(value: Any) -> Any:
    if is_dataclass(value):
        return {key: to_plain_data(val) for key, val in asdict(value).items()}
    if isinstance(value, dict):
        return {key: to_plain_data(val) for key, val in value.items()}
    if isinstance(value, list):
        return [to_plain_data(item) for item in value]
    return value


@dataclass(slots=True)
class ModelResponse:
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ProbeResult:
    probe_id: str
    category: str
    status: str
    raw_model_output: Any
    parsed_output: dict[str, Any]
    evaluator_notes: list[str]
    failure_events: list[dict[str, Any]]
    duration_ms: int
    task_shape: dict[str, Any]
    main_finding: str


@dataclass(slots=True)
class FailureEvent:
    failure_id: str
    probe_id: str
    severity: str
    failure_family: str
    description: str
    evidence: str
    suggested_negative_lane: str


@dataclass(slots=True)
class NegativeLaneSuggestion:
    lane_id: str
    source_failure_ids: list[str]
    rule_type: str
    plain_language_rule: str
    machine_rule_hint: dict[str, Any]
    recommended_for: list[str]


@dataclass(slots=True)
class CognitiveFingerprint:
    model_name: str
    deployment_class: str
    task_fit: dict[str, str]
    strengths: list[str]
    weaknesses: list[str]
    failure_attractors: list[str]
    required_host_constraints: list[str]
    operator_review_burden: str
    notes: list[str]
