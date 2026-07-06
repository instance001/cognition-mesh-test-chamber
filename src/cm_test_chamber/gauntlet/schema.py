from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class GauntletTurn:
    turn_id: str
    user_input: str
    expected_output_schema: dict[str, Any]
    required_content: list[str] = field(default_factory=list)
    forbidden_content: list[str] = field(default_factory=list)
    tool_definitions: list[dict[str, Any]] = field(default_factory=list)
    expected_tool_calls: list[dict[str, Any]] = field(default_factory=list)
    style_rules: dict[str, Any] = field(default_factory=dict)
    carry_forward_constraints: list[str] = field(default_factory=list)
    scoring_weights: dict[str, float] = field(default_factory=dict)


@dataclass(slots=True)
class GauntletSpec:
    gauntlet_id: str
    name: str
    description: str
    version: str
    scoring_profile: dict[str, Any]
    failure_families: list[str]
    turns: list[GauntletTurn]
