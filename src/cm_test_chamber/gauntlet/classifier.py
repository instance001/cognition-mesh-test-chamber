from __future__ import annotations

from typing import Any


def detect_retry_kind(score_payload: dict[str, Any], raw_text: str) -> str | None:
    components = score_payload.get("component_scores", {})
    lowered = raw_text.lower()
    if any(marker in lowered for marker in ["cannot comply", "cannot help", "policy", "refuse"]):
        return "host_sensitive"
    if components.get("schema_validity", 1.0) == 0.0 or components.get("tool_signature_match", 1.0) == 0.0:
        return "hard_break"
    return None


def classify_turn_result(score_payload: dict[str, Any], raw_text: str) -> str:
    components = score_payload.get("component_scores", {})
    retry_kind = detect_retry_kind(score_payload, raw_text)
    if components.get("schema_validity", 1.0) == 0.0 or components.get("tool_signature_match", 1.0) == 0.0:
        return "systemic"
    if score_payload.get("score", 1.0) < 0.5:
        return "systemic"
    if retry_kind == "host_sensitive":
        return "host_sensitive"
    if score_payload.get("passed", False):
        return "none"
    return "soft"


def classify_turn_result_with_retry(
    score_payload: dict[str, Any],
    raw_text: str,
    retry_score_payload: dict[str, Any] | None,
    retry_kind: str | None,
) -> str:
    initial = classify_turn_result(score_payload, raw_text)
    if retry_score_payload is None or retry_kind is None:
        return initial
    if retry_score_payload.get("passed", False):
        if retry_kind == "host_sensitive":
            return "host_sensitive"
        return "flaky"
    if retry_kind == "host_sensitive":
        return "systemic"
    return initial
