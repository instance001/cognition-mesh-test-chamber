from __future__ import annotations

from ..runner.result_types import CognitiveFingerprint, NegativeLaneSuggestion, ProbeResult
from ..runner.run_config import HostProfile, ModelConfig


def build_markdown_report(
    model: ModelConfig,
    host: HostProfile,
    fingerprint: CognitiveFingerprint,
    results: list[ProbeResult],
    suggestions: list[NegativeLaneSuggestion],
) -> str:
    best_fit = [task for task, status in fingerprint.task_fit.items() if status in {"READY", "READY_WITH_GUARDRAILS"}]
    poor_fit = [task for task, status in fingerprint.task_fit.items() if status == "DO_NOT_USE_FOR_THIS_TASK"]
    lines = [
        "# Cognitive Mesh Report",
        "",
        "## Engine",
        "",
        f"- Model: {model.model_name}",
        f"- Family: {model.model_family}",
        f"- Backend: {model.backend}",
        f"- Quantization: {model.quantization}",
        f"- Context: {model.context_length}",
        f"- Temperature: {model.temperature}",
        f"- Host: {host.host_name}",
        f"- Memory: {model.memory}",
        f"- Tool permissions: {model.tool_permissions}",
        "",
        "## Overall deployment class",
        "",
        fingerprint.deployment_class,
        "",
        "## Best-fit tasks",
        "",
    ]
    lines.extend(f"- {item}" for item in best_fit or ["None observed"])
    lines.extend(
        [
            "",
            "## Poor-fit tasks",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in poor_fit or ["None observed"])
    lines.extend(
        [
            "",
            "## Observed strengths",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in fingerprint.strengths or ["None recorded"])
    lines.extend(
        [
            "",
            "## Observed failure lanes",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in fingerprint.failure_attractors or ["No recurring failure families observed"])
    lines.extend(
        [
            "",
            "## Required containment",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in fingerprint.required_host_constraints)
    lines.extend(
        [
            "",
            "## Operator review burden",
            "",
            fingerprint.operator_review_burden.capitalize(),
            "",
            "## Probe results",
            "",
            "| Probe | Category | Status | Main finding |",
            "|---|---|---|---|",
        ]
    )
    for result in results:
        lines.append(f"| {result.probe_id} | {result.category} | {result.status} | {result.main_finding} |")
    lines.extend(["", "## Negative lane suggestions", ""])
    if suggestions:
        for suggestion in suggestions:
            lines.extend(
                [
                    f"### {suggestion.lane_id}",
                    "",
                    "Plain-language rule:",
                    "",
                    suggestion.plain_language_rule,
                    "",
                    "Recommended for:",
                    "",
                    f"- {', '.join(suggestion.recommended_for)}",
                    "",
                ]
            )
    else:
        lines.append("No negative lane suggestions were generated.")
    lines.extend(
        [
            "## Notes",
            "",
            "This report describes this exact engine/host/task mesh only. Do not generalise it to other quantisations, prompts, hosts, or tool permissions.",
            "",
        ]
    )
    return "\n".join(lines)
