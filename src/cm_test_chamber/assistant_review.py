from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .adapters.local_http import LocalHttpAdapter
from .model_catalog import CatalogModel, load_catalog
from .runner.run_config import ModelConfig, ProbeSpec, TaskShape


@dataclass(slots=True)
class AssistantReviewResult:
    assistant_id: str
    assistant_label: str
    output_path: Path
    raw_output_path: Path
    telemetry_path: Path


@dataclass(slots=True)
class AssistantReviewGuidance:
    required_phrases: list[str]
    forbidden_phrases: list[str]
    min_required_phrase_hits: int = 0
    avoidance_instruction: str | None = None
    response_example: str | None = None


def _assistant_slug(assistant_id: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in assistant_id)


def get_assistant_review_paths(run_dir: Path, assistant_id: str) -> dict[str, Path]:
    slug = _assistant_slug(assistant_id)
    root = run_dir / "assistant_reviews" / slug
    return {
        "root": root,
        "review": root / "assistant_review.md",
        "raw": root / "assistant_review_raw.txt",
        "telemetry": root / "assistant_review_telemetry.json",
        "fitness": root / "assistant_evaluator_fitness.json",
        "failure": root / "assistant_review_validation_failure.json",
    }


REQUIRED_SECTIONS = [
    "## Assistant View",
    "## Likely Risks",
    "## Suggested Follow-ups",
]

MAX_ASSISTANT_REVIEW_ATTEMPTS = 3

DISALLOWED_PATTERNS = [
    "Okay, let's",
    "First, the",
    "Need to",
    "Wait, the user said",
    "I should",
    "required anchors",
    "forbidden phrases",
    "validation criteria",
    "formatting and content requirements",
    "the response must include",
]


def _build_assistant_model_config(entry: CatalogModel) -> ModelConfig:
    temperature = entry.temperature if entry.temperature is not None else 0.2
    top_k = entry.top_k if entry.top_k is not None else 40
    top_p = entry.top_p if entry.top_p is not None else 0.95
    max_output_tokens = entry.max_output_tokens if entry.max_output_tokens is not None else 256
    timeout_seconds = entry.timeout_seconds if entry.timeout_seconds is not None else 180
    system_prompt = (
        entry.system_prompt_override
        if entry.system_prompt_override
        else "You are a local evaluation assistant. Be honest, specific, and evidence-first."
    )
    return ModelConfig(
        model_name=entry.label,
        model_family=entry.family,
        quantization=entry.quantization,
        backend="local_http",
        endpoint=entry.recommended_endpoint,
        request_format="llama_cpp_completion",
        timeout_seconds=timeout_seconds,
        context_length=8192,
        hardware="local_assistant",
        temperature=temperature,
        sampler_settings={"top_k": top_k, "top_p": top_p},
        max_output_tokens=max_output_tokens,
        system_prompt=system_prompt,
        prompt_template="default",
        tool_permissions="none",
        host_wrapper="assistant_review_only",
        memory="disabled",
    )


def _load_run_artifacts(run_dir: Path) -> tuple[dict, str]:
    fingerprint = json.loads((run_dir / "cognitive_fingerprint.json").read_text(encoding="utf-8"))
    report = (run_dir / "report.md").read_text(encoding="utf-8")
    return fingerprint, report


def _load_review_guidance(run_dir: Path) -> AssistantReviewGuidance | None:
    path = run_dir / "assistant_review_guidance.json"
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return AssistantReviewGuidance(
        required_phrases=payload.get("required_phrases", []),
        forbidden_phrases=payload.get("forbidden_phrases", []),
        min_required_phrase_hits=payload.get("min_required_phrase_hits", 0),
        avoidance_instruction=payload.get("avoidance_instruction"),
        response_example=payload.get("response_example"),
    )


def build_assistant_review_prompt(
    fingerprint: dict,
    report: str,
    run_dir: Path,
    guidance: AssistantReviewGuidance | None = None,
) -> str:
    lines = [
        "You are reviewing a completed cognition mesh run.",
        "Your job is to provide a short operator-facing commentary without changing the official results.",
        "Be specific, grounded, and non-defensive.",
        "Do not invent evidence beyond the supplied artifacts.",
        "Do not reveal your planning, chain-of-thought, or drafting process.",
        "Output only the final Markdown review.",
        "Keep the full answer under 180 words.",
        "Use 1-2 short bullets per section, or one short paragraph if a section is simple.",
        "Start immediately with `## Assistant View`.",
        "Each section must contain concrete run evidence, not generic meta-commentary.",
        "Do not talk about validation rules, anchors, formatting rules, or your own response.",
        "",
        "Please produce Markdown with these sections exactly:",
        "## Assistant View",
        "## Likely Risks",
        "## Suggested Follow-ups",
    ]
    if guidance is not None:
        lines.extend(
            [
                "",
                "Run-specific evidence guidance:",
                f"- Include at least {guidance.min_required_phrase_hits} exact phrase(s) from the required anchor list.",
                "- Use the exact wording when you cite an anchor.",
                "- Do not include any operator-prohibited phrase, even to negate or warn about it.",
                "- If prohibited wording appears in the source artifacts, paraphrase the risk instead of repeating that wording.",
                "Required anchors:",
                *[f"- {phrase}" for phrase in guidance.required_phrases],
            ]
        )
        if guidance.avoidance_instruction:
            lines.extend(
                [
                    "Avoidance instruction:",
                    f"- {guidance.avoidance_instruction}",
                ]
            )
        if guidance.response_example:
            lines.extend(
                [
                    "Style example:",
                    guidance.response_example,
                ]
            )
    lines.extend(
        [
            "",
            f"Run folder: {run_dir.name}",
            "",
            "Fingerprint JSON:",
            json.dumps(fingerprint, indent=2),
            "",
            "Report Markdown:",
            report,
        ]
    )
    return "\n".join(lines)


def build_assistant_retry_prompt(
    previous_output: str,
    issues: list[str],
    attempt_number: int,
    guidance: AssistantReviewGuidance | None = None,
) -> str:
    lines = [
        f"Your previous answer on attempt {attempt_number} did not match the required final-review format.",
        "Return only the final Markdown review.",
        "Do not include planning text, self-talk, or process notes.",
        "Keep the full answer under 180 words.",
        "Use 1-2 short bullets per section, or one short paragraph if a section is simple.",
        "Start immediately with `## Assistant View`.",
        "Do not mention validation rules, anchor lists, forbidden phrases, or formatting instructions in the review.",
        "Do not describe your response. Describe only the run evidence and operator implications.",
        "Use these sections exactly once each and in this order:",
        "## Assistant View",
        "## Likely Risks",
        "## Suggested Follow-ups",
        "",
        "Validation issues to fix:",
        *[f"- {issue}" for issue in issues],
    ]
    if guidance is not None:
        lines.extend(
            [
                "",
                "Required anchors to include literally:",
                *[f"- {phrase}" for phrase in guidance.required_phrases],
                "Avoid every operator-prohibited phrase from the prior guidance policy.",
                "Do not quote, repeat, negate, or discuss prohibited wording. Paraphrase the idea instead.",
            ]
        )
        if guidance.avoidance_instruction:
            lines.extend(
                [
                    "Avoidance instruction:",
                    f"- {guidance.avoidance_instruction}",
                ]
            )
        if guidance.response_example:
            lines.extend(
                [
                    "Follow this structural pattern closely:",
                    guidance.response_example,
                ]
            )
    else:
        lines.extend(
            [
                "",
                "Previous invalid output:",
                previous_output,
            ]
        )
    return "\n".join(lines)


def validate_assistant_review(text: str, guidance: AssistantReviewGuidance | None = None) -> list[str]:
    issues: list[str] = []
    stripped = text.strip()
    if not stripped:
        issues.append("Review output was empty.")
        return issues
    if len(stripped.split()) > 220:
        issues.append("Review exceeded the maximum word-count envelope.")

    if not stripped.startswith("## Assistant View"):
        issues.append("Review must begin directly with `## Assistant View` and contain no leading prose.")

    cursor = 0
    for section in REQUIRED_SECTIONS:
        position = stripped.find(section, cursor)
        if position == -1:
            issues.append(f"Missing required section: {section}")
            continue
        cursor = position + len(section)

    for pattern in DISALLOWED_PATTERNS:
        if pattern.lower() in stripped.lower():
            issues.append(f"Detected planning-style text: {pattern}")

    if stripped.count("## Assistant View") != 1:
        issues.append("Section count mismatch for `## Assistant View`.")
    if stripped.count("## Likely Risks") != 1:
        issues.append("Section count mismatch for `## Likely Risks`.")
    if stripped.count("## Suggested Follow-ups") != 1:
        issues.append("Section count mismatch for `## Suggested Follow-ups`.")
    if guidance is not None:
        lowered = stripped.lower()
        required_hits = [phrase for phrase in guidance.required_phrases if phrase.lower() in lowered]
        if len(required_hits) < guidance.min_required_phrase_hits:
            issues.append(
                "Insufficient required evidence anchors: "
                f"found {len(required_hits)} of {guidance.min_required_phrase_hits}."
            )
        for phrase in guidance.forbidden_phrases:
            if phrase.lower() in lowered:
                issues.append(f"Forbidden evidence phrase appeared: {phrase}")
    return issues


def salvage_assistant_review(text: str) -> tuple[str, dict]:
    raw = text.strip()
    telemetry = {
        "had_salvage": False,
        "leading_prose": "",
        "trailing_text": "",
        "salvaged_text": raw,
    }
    start = raw.find("## Assistant View")
    if start == -1:
        return raw, telemetry

    end_markers = ["\n## Assistant View", "\n## Likely Risks", "\n## Suggested Follow-ups"]
    leading = raw[:start].strip()
    candidate = raw[start:]

    # Trim anything after the required final section if extra chatter appears later.
    final_header = "## Suggested Follow-ups"
    final_pos = candidate.find(final_header)
    if final_pos != -1:
        after_final = candidate[final_pos + len(final_header):]
        next_section = after_final.find("\n## ")
        if next_section != -1:
            cut_index = final_pos + len(final_header) + next_section
            telemetry["trailing_text"] = candidate[cut_index:].strip()
            candidate = candidate[:cut_index].rstrip()

    if leading or telemetry["trailing_text"]:
        telemetry["had_salvage"] = True
    telemetry["leading_prose"] = leading
    telemetry["salvaged_text"] = candidate.strip()
    return candidate.strip(), telemetry


def compute_assistant_evaluator_fitness(telemetry_payload: dict) -> dict:
    salvage_events = telemetry_payload.get("salvage_events", [])
    final_issues = telemetry_payload.get("final_issues", [])
    attempt_count = telemetry_payload.get("attempt_count") or 0
    validation_passed = bool(telemetry_payload.get("validation_passed"))

    leading_prose_events = sum(1 for event in salvage_events if (event.get("leading_prose") or "").strip())
    trailing_noise_events = sum(1 for event in salvage_events if (event.get("trailing_text") or "").strip())
    salvage_count = sum(1 for event in salvage_events if event.get("had_salvage"))
    section_issues = sum(1 for issue in final_issues if "section" in issue.lower() or "missing required section" in issue.lower())
    planning_issues = sum(1 for issue in final_issues if "planning-style" in issue.lower())
    start_format_issues = sum(1 for issue in final_issues if "must begin directly" in issue.lower())

    penalties = {
        "validation_failure": 45 if not validation_passed else 0,
        "retry_overhead": max(attempt_count - 1, 0) * 10,
        "salvage_burden": salvage_count * 6,
        "leading_prose_noise": leading_prose_events * 5,
        "trailing_noise": trailing_noise_events * 5,
        "section_compliance": section_issues * 8,
        "planning_noise": planning_issues * 6,
        "start_format": start_format_issues * 6,
    }
    total_penalty = sum(penalties.values())
    score = max(0, 100 - total_penalty)

    if not validation_passed or score < 55:
        suitability = "containment-only"
    elif score < 75:
        suitability = "experimental"
    elif salvage_count > 0 or attempt_count > 1:
        suitability = "usable with monitoring"
    else:
        suitability = "production-usable"

    rationale_parts: list[str] = []
    if validation_passed:
        rationale_parts.append("passed validation")
    else:
        rationale_parts.append("failed validation")
    if attempt_count > 1:
        rationale_parts.append(f"needed {attempt_count} attempts")
    if salvage_count > 0:
        rationale_parts.append(f"needed salvage on {salvage_count} attempt(s)")
    if leading_prose_events > 0:
        rationale_parts.append(f"leading prose appeared {leading_prose_events} time(s)")
    if trailing_noise_events > 0:
        rationale_parts.append(f"trailing noise appeared {trailing_noise_events} time(s)")
    if section_issues > 0:
        rationale_parts.append(f"section compliance broke {section_issues} time(s)")
    if not rationale_parts:
        rationale_parts.append("clean evaluator pass")

    return {
        "assistant_id": telemetry_payload.get("assistant_id"),
        "assistant_label": telemetry_payload.get("assistant_label"),
        "score": score,
        "max_score": 100,
        "suitability": suitability,
        "summary": "; ".join(rationale_parts),
        "signals": {
            "validation_passed": validation_passed,
            "attempt_count": attempt_count,
            "salvage_count": salvage_count,
            "leading_prose_events": leading_prose_events,
            "trailing_noise_events": trailing_noise_events,
            "section_issue_count": section_issues,
            "planning_issue_count": planning_issues,
            "start_format_issue_count": start_format_issues,
        },
        "penalties": penalties,
        "final_issues": final_issues,
    }


def run_assistant_review(repo_root: Path, run_dir: Path, assistant_id: str) -> AssistantReviewResult:
    catalog = load_catalog(repo_root / "configs" / "catalogs" / "assistant_models.json")
    entry = next((item for item in catalog.models if item.id == assistant_id), None)
    if entry is None:
        raise ValueError(f"Unknown assistant id: {assistant_id}")

    fingerprint, report = _load_run_artifacts(run_dir)
    guidance = _load_review_guidance(run_dir)
    prompt = build_assistant_review_prompt(fingerprint, report, run_dir, guidance)
    config = _build_assistant_model_config(entry)
    adapter = LocalHttpAdapter(config)
    probe = ProbeSpec(
        probe_id="assistant_review",
        title="Assistant review",
        category="assistant",
        evaluator="text_eval",
        task_shape=TaskShape(
            task_id="assistant_review",
            category="assistant_review",
            requires_precision="medium",
            requires_creativity="medium",
            requires_source_fidelity="high",
            requires_tool_use=False,
            failure_cost="low",
            ambiguity_load="low",
            allowed_retries=0,
        ),
        prompt="Review the run artifacts.",
    )
    attempts: list[str] = []
    salvage_events: list[dict] = []
    paths = get_assistant_review_paths(run_dir, entry.id)
    paths["root"].mkdir(parents=True, exist_ok=True)
    review_path = paths["review"]
    raw_path = paths["raw"]
    failure_path = paths["failure"]
    legacy_raw_path = run_dir / "assistant_review_raw.txt"

    response = adapter.generate(probe, prompt, {"stage": "attempt_1"})
    attempts.append(response.text)
    cleaned_text, salvage = salvage_assistant_review(response.text)
    salvage_events.append({"attempt": 1, **salvage})
    issues = validate_assistant_review(cleaned_text, guidance)
    attempt_number = 1
    while issues and attempt_number < MAX_ASSISTANT_REVIEW_ATTEMPTS:
        attempt_number += 1
        retry_prompt = build_assistant_retry_prompt(cleaned_text, issues, attempt_number - 1, guidance)
        response = adapter.generate(probe, retry_prompt, {"stage": f"attempt_{attempt_number}"})
        attempts.append(response.text)
        cleaned_text, salvage = salvage_assistant_review(response.text)
        salvage_events.append({"attempt": attempt_number, **salvage})
        issues = validate_assistant_review(cleaned_text, guidance)

    telemetry_path = paths["telemetry"]
    legacy_telemetry_path = run_dir / "assistant_review_telemetry.json"
    telemetry_payload = {
        "assistant_id": entry.id,
        "assistant_label": entry.label,
        "attempt_count": len(attempts),
        "salvage_events": salvage_events,
        "validation_passed": not issues,
        "final_issues": issues,
    }
    fitness_payload = compute_assistant_evaluator_fitness(telemetry_payload)
    telemetry_path.write_text(json.dumps(telemetry_payload, indent=2) + "\n", encoding="utf-8")
    legacy_telemetry_path.write_text(json.dumps(telemetry_payload, indent=2) + "\n", encoding="utf-8")
    paths["fitness"].write_text(json.dumps(fitness_payload, indent=2) + "\n", encoding="utf-8")
    (run_dir / "assistant_evaluator_fitness.json").write_text(json.dumps(fitness_payload, indent=2) + "\n", encoding="utf-8")
    raw_attempts_text = "\n\n--- attempt boundary ---\n\n".join(attempts)
    raw_path.write_text(raw_attempts_text, encoding="utf-8")
    legacy_raw_path.write_text(raw_attempts_text, encoding="utf-8")

    if issues:
        legacy_failure_path = run_dir / "assistant_review_validation_failure.json"
        failure_payload = {
            "assistant_id": entry.id,
            "assistant_label": entry.label,
            "issues": issues,
            "attempts": attempts,
            "salvage_events": salvage_events,
        }
        failure_path.write_text(
            json.dumps(failure_payload, indent=2) + "\n",
            encoding="utf-8",
        )
        legacy_failure_path.write_text(
            json.dumps(failure_payload, indent=2) + "\n",
            encoding="utf-8",
        )
        raise ValueError(
            "Assistant review output failed validation. See "
            f"{failure_path.name} for details."
        )

    header = [
        f"# Assistant Review: {entry.label}",
        "",
        f"- Assistant ID: `{entry.id}`",
        f"- Recommended endpoint: `{entry.recommended_endpoint}`",
        "",
    ]
    review_path.write_text("\n".join(header) + cleaned_text + "\n", encoding="utf-8")
    if failure_path.exists():
        failure_path.unlink()
    # Compatibility layer for existing single-review consumers.
    (run_dir / "assistant_review.md").write_text("\n".join(header) + cleaned_text + "\n", encoding="utf-8")
    (run_dir / "assistant_review_telemetry.json").write_text(
        json.dumps(telemetry_payload, indent=2) + "\n", encoding="utf-8"
    )
    legacy_failure = run_dir / "assistant_review_validation_failure.json"
    if legacy_failure.exists():
        legacy_failure.unlink()
    return AssistantReviewResult(
        assistant_id=entry.id,
        assistant_label=entry.label,
        output_path=review_path,
        raw_output_path=raw_path,
        telemetry_path=telemetry_path,
    )
