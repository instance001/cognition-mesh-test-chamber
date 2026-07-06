from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REQUIRED_TOP_LEVEL_FIELDS = [
    "draft_probe",
    "draft_id",
    "probe_id",
    "title",
    "category",
    "evaluator",
    "task_shape",
    "prompt",
    "required_phrases",
    "forbidden_phrases",
    "expected_json",
    "draft_metadata",
]

REQUIRED_TASK_SHAPE_FIELDS = [
    "task_id",
    "category",
    "requires_precision",
    "requires_creativity",
    "requires_source_fidelity",
    "requires_tool_use",
    "failure_cost",
    "ambiguity_load",
    "allowed_retries",
]

REQUIRED_DRAFT_METADATA_FIELDS = [
    "status",
    "priority",
    "operator_decision",
    "target_probe_goal",
    "suggested_turn_focus",
    "suggested_assertions",
    "source_models",
    "source_run_count",
    "source_draft_id",
]


def validate_probe_draft_payload(payload: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    for field in REQUIRED_TOP_LEVEL_FIELDS:
        if field not in payload:
            issues.append(f"missing top-level field: {field}")
    if issues:
        return issues

    if payload.get("draft_probe") is not True:
        issues.append("draft_probe must be true")
    if not isinstance(payload.get("prompt"), str) or not payload["prompt"].strip():
        issues.append("prompt must be a non-empty string")
    if not isinstance(payload.get("required_phrases"), list) or not payload["required_phrases"]:
        issues.append("required_phrases must be a non-empty list")
    if not isinstance(payload.get("forbidden_phrases"), list):
        issues.append("forbidden_phrases must be a list")

    task_shape = payload.get("task_shape")
    if not isinstance(task_shape, dict):
        issues.append("task_shape must be an object")
    else:
        for field in REQUIRED_TASK_SHAPE_FIELDS:
            if field not in task_shape:
                issues.append(f"missing task_shape field: {field}")
        if task_shape.get("task_id") != payload.get("probe_id"):
            issues.append("task_shape.task_id must match probe_id")
        if task_shape.get("category") != payload.get("draft_metadata", {}).get("source_draft_id", "").replace("_draft_001", ""):
            pass

    expected_json = payload.get("expected_json")
    if not isinstance(expected_json, dict):
        issues.append("expected_json must be an object")
    else:
        if expected_json.get("type") != "object":
            issues.append("expected_json.type must be 'object'")
        required = expected_json.get("required")
        if not isinstance(required, list) or not {"finding", "evidence", "decision"}.issubset(set(required)):
            issues.append("expected_json.required must include finding, evidence, and decision")

    draft_metadata = payload.get("draft_metadata")
    if not isinstance(draft_metadata, dict):
        issues.append("draft_metadata must be an object")
    else:
        for field in REQUIRED_DRAFT_METADATA_FIELDS:
            if field not in draft_metadata:
                issues.append(f"missing draft_metadata field: {field}")
        if draft_metadata.get("status") != "draft_materialized":
            issues.append("draft_metadata.status must be 'draft_materialized'")
        if draft_metadata.get("source_draft_id") != payload.get("draft_id"):
            issues.append("draft_metadata.source_draft_id must match draft_id")
        if draft_metadata.get("operator_decision") != "confirmed_for_forge":
            issues.append("draft_metadata.operator_decision must be 'confirmed_for_forge'")

    return issues


def validate_probe_draft_file(path: Path) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return validate_probe_draft_payload(payload)
