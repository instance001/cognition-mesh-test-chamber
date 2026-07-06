from __future__ import annotations

from collections import Counter

from ..runner.result_types import CognitiveFingerprint, FailureEvent, ProbeResult
from ..runner.run_config import HostProfile, ModelConfig


def _task_status(result: ProbeResult) -> str:
    if result.status == "pass":
        if result.category == "coding":
            return "READY_WITH_GUARDRAILS"
        return "READY"
    if result.category == "failure":
        return "DO_NOT_USE_FOR_THIS_TASK"
    return "ASSISTED_ONLY"


def _deployment_class(results: list[ProbeResult], failures: list[FailureEvent]) -> str:
    if not failures:
        return "READY"
    high_failures = [failure for failure in failures if failure.severity == "high"]
    fail_count = sum(1 for result in results if result.status == "fail")
    if fail_count >= 5 or len(high_failures) >= 3:
        return "QUARANTINE"
    if high_failures:
        return "ASSISTED_ONLY"
    return "READY_WITH_GUARDRAILS"


def build_fingerprint(
    model: ModelConfig,
    host: HostProfile,
    results: list[ProbeResult],
    failures: list[FailureEvent],
    negative_lanes: list[str],
) -> CognitiveFingerprint:
    family_counts = Counter(failure.failure_family for failure in failures)
    task_fit = {
        "summarisation": "DO_NOT_USE_FOR_THIS_TASK",
        "structured_extraction": "DO_NOT_USE_FOR_THIS_TASK",
        "small_code_patch": "DO_NOT_USE_FOR_THIS_TASK",
        "autonomous_agent_use": "DO_NOT_USE_FOR_THIS_TASK",
    }
    for result in results:
        category = result.task_shape["category"]
        if category == "summarisation":
            task_fit["summarisation"] = _task_status(result)
        elif category == "structured_extraction":
            task_fit["structured_extraction"] = _task_status(result)
        elif category == "small_code_patch":
            task_fit["small_code_patch"] = _task_status(result)

    constraints = [
        "Schema-locked host output checks" if host.schema_lock else "Schema lock disabled",
        "No real tools enabled" if not host.real_tools_enabled else "Real tools enabled",
        "No external network" if not host.network_enabled else "Network enabled",
        "Patch preview required" if host.requires_patch_preview else "Patch preview optional",
        "Source lock required" if host.requires_source_lock else "Source lock optional",
    ]
    constraints.extend(negative_lanes)

    strengths = [result.main_finding for result in results if result.status == "pass"]
    weaknesses = sorted({failure.description for failure in failures})
    failure_attractors = [family for family, _count in family_counts.most_common(5)]
    review_burden = "medium"
    if len(failures) >= 5:
        review_burden = "high"
    elif not failures:
        review_burden = "low"

    return CognitiveFingerprint(
        model_name=model.model_name,
        deployment_class=_deployment_class(results, failures),
        task_fit=task_fit,
        strengths=strengths,
        weaknesses=weaknesses,
        failure_attractors=failure_attractors,
        required_host_constraints=constraints,
        operator_review_burden=review_burden,
        notes=[
            "This fingerprint applies only to the exact model intake, host profile, and probe pack used in this run.",
            "Do not generalise this result to other prompts, quantisations, hosts, or tool permissions.",
        ],
    )
