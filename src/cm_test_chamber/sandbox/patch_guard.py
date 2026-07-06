from __future__ import annotations

import json
import re
from dataclasses import dataclass


@dataclass(slots=True)
class PatchAnalysis:
    touched_paths: list[str]
    invented_paths: list[str]
    broad_patch: bool
    dependency_invention: bool
    unrelated_change: bool
    normalized_payload: dict[str, object]


def _extract_paths_from_diff(text: str) -> list[str]:
    paths: list[str] = []
    for line in text.splitlines():
        if line.startswith("+++ "):
            candidate = line[4:].strip()
            if candidate.startswith("b/"):
                candidate = candidate[2:]
            if candidate != "/dev/null":
                paths.append(candidate)
    return paths


def _extract_paths_from_plan(payload: dict[str, object]) -> list[str]:
    values = payload.get("modified_files", [])
    if isinstance(values, list):
        return [str(item) for item in values]
    return []


def analyze_patch(
    raw_output: str,
    allowed_files: set[str],
    manifest: set[str],
    allow_new_files: bool,
) -> PatchAnalysis:
    normalized_payload: dict[str, object]
    touched_paths: list[str]
    try:
        payload = json.loads(raw_output)
    except json.JSONDecodeError:
        payload = None
    if isinstance(payload, dict) and "modified_files" in payload:
        touched_paths = _extract_paths_from_plan(payload)
        normalized_payload = payload
        body_text = raw_output
    else:
        touched_paths = _extract_paths_from_diff(raw_output)
        normalized_payload = {"format": "unified_diff", "text": raw_output, "modified_files": touched_paths}
        body_text = raw_output

    invented_paths = [
        path for path in touched_paths if path not in manifest and path not in allowed_files and not allow_new_files
    ]
    dependency_invention = bool(re.search(r"\brequirements\.txt\b|\bpip install\b|\bnpm install\b", body_text))
    broad_patch = len(set(touched_paths)) > len(allowed_files) or any(path not in allowed_files for path in touched_paths)
    unrelated_change = dependency_invention or "refactor" in body_text.lower()
    return PatchAnalysis(
        touched_paths=touched_paths,
        invented_paths=invented_paths,
        broad_patch=broad_patch,
        dependency_invention=dependency_invention,
        unrelated_change=unrelated_change,
        normalized_payload=normalized_payload,
    )
