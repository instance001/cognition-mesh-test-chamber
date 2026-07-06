from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .schema import GauntletSpec, GauntletTurn


class GauntletConfigError(ValueError):
    pass


def _require_type(data: dict[str, Any], key: str, expected_type: type, context: str) -> Any:
    if key not in data:
        raise GauntletConfigError(f"Missing {context} field: {key}")
    value = data[key]
    if not isinstance(value, expected_type):
        raise GauntletConfigError(
            f"Invalid {context} field {key}: expected {expected_type.__name__}, got {type(value).__name__}"
        )
    return value


def _optional_list(data: dict[str, Any], key: str) -> list[Any]:
    value = data.get(key, [])
    if not isinstance(value, list):
        raise GauntletConfigError(f"Invalid turn field {key}: expected list, got {type(value).__name__}")
    return value


def _optional_dict(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key, {})
    if not isinstance(value, dict):
        raise GauntletConfigError(f"Invalid turn field {key}: expected dict, got {type(value).__name__}")
    return value


def _validate_turn(turn_data: dict[str, Any], index: int) -> GauntletTurn:
    context = f"turn[{index}]"
    turn_id = _require_type(turn_data, "turn_id", str, context)
    user_input = _require_type(turn_data, "user_input", str, context)
    expected_output_schema = _require_type(turn_data, "expected_output_schema", dict, context)
    scoring_weights = _optional_dict(turn_data, "scoring_weights")
    if not scoring_weights:
        raise GauntletConfigError(f"{context} must define at least one scoring weight")
    for key, value in scoring_weights.items():
        if not isinstance(value, (int, float)):
            raise GauntletConfigError(
                f"Invalid {context} scoring weight {key}: expected number, got {type(value).__name__}"
            )
    return GauntletTurn(
        turn_id=turn_id,
        user_input=user_input,
        expected_output_schema=expected_output_schema,
        required_content=_optional_list(turn_data, "required_content"),
        forbidden_content=_optional_list(turn_data, "forbidden_content"),
        tool_definitions=_optional_list(turn_data, "tool_definitions"),
        expected_tool_calls=_optional_list(turn_data, "expected_tool_calls"),
        style_rules=_optional_dict(turn_data, "style_rules"),
        carry_forward_constraints=_optional_list(turn_data, "carry_forward_constraints"),
        scoring_weights={key: float(value) for key, value in scoring_weights.items()},
    )


def load_gauntlet_spec(path: Path) -> GauntletSpec:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise GauntletConfigError("Gauntlet config root must be a JSON object")
    gauntlet_id = _require_type(payload, "id", str, "gauntlet")
    name = _require_type(payload, "name", str, "gauntlet")
    description = _require_type(payload, "description", str, "gauntlet")
    version = _require_type(payload, "version", str, "gauntlet")
    scoring_profile = _require_type(payload, "scoring_profile", dict, "gauntlet")
    failure_families = _require_type(payload, "failure_families", list, "gauntlet")
    turns_payload = _require_type(payload, "turns", list, "gauntlet")
    if not turns_payload:
        raise GauntletConfigError("Gauntlet config must contain at least one turn")
    turns = []
    for index, turn_data in enumerate(turns_payload):
        if not isinstance(turn_data, dict):
            raise GauntletConfigError(f"turn[{index}] must be a JSON object")
        turns.append(_validate_turn(turn_data, index))
    return GauntletSpec(
        gauntlet_id=gauntlet_id,
        name=name,
        description=description,
        version=version,
        scoring_profile=scoring_profile,
        failure_families=[str(item) for item in failure_families],
        turns=turns,
    )
