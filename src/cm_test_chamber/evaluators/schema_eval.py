from __future__ import annotations

import json
from typing import Any

from ..runner.run_config import ProbeSpec


def evaluate_schema(raw_output: str, probe: ProbeSpec) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    notes: list[str] = []
    parsed: dict[str, Any] = {}
    try:
        parsed = json.loads(raw_output)
        if not isinstance(parsed, dict):
            issues.append({"family": "schema_drift", "message": "Output was JSON but not an object."})
    except json.JSONDecodeError:
        issues.append({"family": "schema_drift", "message": "Output was not valid JSON."})
        if "{" in raw_output and raw_output.strip().split("{", 1)[0].strip():
            issues.append({"family": "extra_text", "message": "Output contained prose outside JSON."})
        return {"status": "fail", "notes": notes, "parsed_output": {}, "issues": issues}

    required_keys = probe.required_keys or []
    for key in required_keys:
        if key not in parsed:
            issues.append({"family": "missing_required_field", "message": f"Missing required key: {key}"})
    for key, expected in (probe.expected_json or {}).items():
        if parsed.get(key) != expected:
            issues.append({"family": "value_mismatch", "message": f"Expected {key}={expected!r}."})
    if raw_output.strip() != json.dumps(parsed):
        notes.append("Output included formatting or spacing differences but remained parseable.")
    return {
        "status": "pass" if not issues else "fail",
        "notes": notes,
        "parsed_output": parsed,
        "issues": issues,
    }
