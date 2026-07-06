from __future__ import annotations

from typing import Any

from ..runner.run_config import ProbeSpec
from ..sandbox.patch_guard import analyze_patch


def evaluate_patch(raw_output: str, probe: ProbeSpec, manifest: set[str]) -> dict[str, Any]:
    allowed_files = set(probe.target_files or [])
    analysis = analyze_patch(raw_output, allowed_files, manifest, probe.allow_new_files)
    issues: list[dict[str, str]] = []
    notes: list[str] = []

    if not analysis.touched_paths:
        issues.append({"family": "unrelated_change", "message": "No touched paths could be determined."})
    if analysis.invented_paths:
        issues.append(
            {"family": "invented_file_path", "message": f"Invented or out-of-scope paths: {analysis.invented_paths}"}
        )
    if analysis.broad_patch:
        issues.append({"family": "broad_patch", "message": "Patch touched files outside the requested scope."})
    if analysis.unrelated_change:
        issues.append({"family": "unrelated_change", "message": "Patch included unrelated or expansive changes."})
    if analysis.dependency_invention:
        issues.append({"family": "dependency_invention", "message": "Patch introduced dependency changes."})
    for term in probe.required_patch_terms or []:
        if term not in raw_output:
            issues.append({"family": "value_mismatch", "message": f"Required patch term missing: {term}"})
    for term in probe.forbidden_patch_terms or []:
        if term.lower() in raw_output.lower():
            issues.append({"family": "dependency_invention", "message": f"Forbidden patch term found: {term}"})
    if not issues:
        notes.append("Patch stayed within allowed file scope.")
    return {
        "status": "pass" if not issues else "fail",
        "notes": notes,
        "parsed_output": analysis.normalized_payload,
        "issues": issues,
    }
