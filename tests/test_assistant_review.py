import json

import pytest

from cm_test_chamber.assistant_review import (
    AssistantReviewGuidance,
    build_assistant_review_prompt,
    compute_assistant_evaluator_fitness,
    get_assistant_review_paths,
    run_assistant_review,
    salvage_assistant_review,
    validate_assistant_review,
)


def test_assistant_review_prompt_includes_report_and_fingerprint(tmp_path):
    fingerprint = {"deployment_class": "READY_WITH_GUARDRAILS", "task_fit": {"summarisation": "READY"}}
    report = "# Cognitive Mesh Report\n\nExample report body."
    prompt = build_assistant_review_prompt(fingerprint, report, tmp_path / "demo_run")
    assert "Fingerprint JSON:" in prompt
    assert "Report Markdown:" in prompt
    assert "## Assistant View" in prompt
    assert "Do not reveal your planning" in prompt


def test_assistant_review_prompt_includes_guidance_when_present(tmp_path):
    prompt = build_assistant_review_prompt(
        {"deployment_class": "READY"},
        "# Cognitive Mesh Report\n\nExample report body.",
        tmp_path / "demo_run",
        AssistantReviewGuidance(
            required_phrases=["20 percent", "official result"],
            forbidden_phrases=["production-ready"],
            min_required_phrase_hits=2,
            avoidance_instruction="Avoid broad rollout claims.",
            response_example="## Assistant View\n- Example",
        ),
    )
    assert "Required anchors:" in prompt
    assert "20 percent" in prompt
    assert "Avoid broad rollout claims." in prompt
    assert "## Assistant View\n- Example" in prompt
    assert "production-ready" not in prompt


def test_validate_assistant_review_rejects_planning_text():
    issues = validate_assistant_review(
        "Okay, let's tackle this.\n\n## Assistant View\nA\n\n## Likely Risks\nB\n\n## Suggested Follow-ups\nC"
    )
    assert any("planning-style" in issue for issue in issues)
    assert any("must begin directly" in issue for issue in issues)


def test_validate_assistant_review_rejects_validation_meta_commentary():
    issues = validate_assistant_review(
        "## Assistant View\nThe response must include the exact anchors.\n\n## Likely Risks\nB\n\n## Suggested Follow-ups\nC"
    )
    assert any("planning-style" in issue for issue in issues)


def test_validate_assistant_review_rejects_leading_prose():
    issues = validate_assistant_review(
        "Based on the information below:\n\n## Assistant View\nA\n\n## Likely Risks\nB\n\n## Suggested Follow-ups\nC"
    )
    assert any("must begin directly" in issue for issue in issues)


def test_validate_assistant_review_enforces_guidance_anchors():
    issues = validate_assistant_review(
        "## Assistant View\nA\n\n## Likely Risks\nB\n\n## Suggested Follow-ups\nC",
        AssistantReviewGuidance(
            required_phrases=["20 percent", "small dataset"],
            forbidden_phrases=["production-wide success"],
            min_required_phrase_hits=2,
        ),
    )
    assert any("Insufficient required evidence anchors" in issue for issue in issues)


def test_validate_assistant_review_rejects_excessive_length():
    long_body = "word " * 230
    issues = validate_assistant_review(
        f"## Assistant View\n{long_body}\n\n## Likely Risks\nB\n\n## Suggested Follow-ups\nC"
    )
    assert any("maximum word-count envelope" in issue for issue in issues)


def test_salvage_assistant_review_trims_leading_prose():
    cleaned, telemetry = salvage_assistant_review(
        "Based on the information below:\n\n## Assistant View\nA\n\n## Likely Risks\nB\n\n## Suggested Follow-ups\nC"
    )
    assert cleaned.startswith("## Assistant View")
    assert telemetry["had_salvage"] is True
    assert telemetry["leading_prose"] == "Based on the information below:"


def test_get_assistant_review_paths_are_assistant_specific(tmp_path):
    first = get_assistant_review_paths(tmp_path, "assistant-a")
    second = get_assistant_review_paths(tmp_path, "assistant-b")
    assert first["review"] != second["review"]
    assert "assistant_reviews" in str(first["review"])
    assert first["fitness"].name == "assistant_evaluator_fitness.json"


def test_compute_assistant_evaluator_fitness_penalizes_noise_and_failure():
    fitness = compute_assistant_evaluator_fitness(
        {
            "assistant_id": "assistant-a",
            "assistant_label": "Assistant A",
            "attempt_count": 3,
            "validation_passed": False,
            "final_issues": [
                "Missing required section: ## Suggested Follow-ups",
                "Detected planning-style text: Okay, let's",
                "Review must begin directly with `## Assistant View` and contain no leading prose.",
            ],
            "salvage_events": [
                {"had_salvage": True, "leading_prose": "thinking...", "trailing_text": ""},
                {"had_salvage": True, "leading_prose": "", "trailing_text": "extra"},
                {"had_salvage": False, "leading_prose": "", "trailing_text": ""},
            ],
        }
    )
    assert fitness["score"] < 55
    assert fitness["suitability"] == "containment-only"
    assert fitness["signals"]["leading_prose_events"] == 1
    assert fitness["signals"]["trailing_noise_events"] == 1
    assert fitness["penalties"]["validation_failure"] > 0


def test_assistant_review_writes_artifacts(repo_root, tmp_path, monkeypatch):
    run_dir = tmp_path / "demo_run"
    run_dir.mkdir()
    (run_dir / "cognitive_fingerprint.json").write_text(
        json.dumps({"deployment_class": "READY", "task_fit": {"summarisation": "READY"}}),
        encoding="utf-8",
    )
    (run_dir / "report.md").write_text("# Cognitive Mesh Report\n\nHello.", encoding="utf-8")

    class FakeAdapter:
        def __init__(self, _config):
            pass

        def generate(self, probe, prompt, context):
            class Response:
                text = "## Assistant View\n\nLooks solid.\n\n## Likely Risks\n\n- Drift.\n\n## Suggested Follow-ups\n\n- Re-run."

            return Response()

    monkeypatch.setattr("cm_test_chamber.assistant_review.LocalHttpAdapter", FakeAdapter)
    result = run_assistant_review(repo_root, run_dir, "qwen3-8b-abliterated-q8_0-assistant")
    assert result.output_path.exists()
    assert result.raw_output_path.exists()
    assert result.telemetry_path.exists()
    assert get_assistant_review_paths(run_dir, "qwen3-8b-abliterated-q8_0-assistant")["fitness"].exists()
    assert "assistant_reviews" in str(result.output_path)
    rendered = result.output_path.read_text(encoding="utf-8")
    assert "Assistant Review" in rendered
    assert "## Assistant View" in rendered


def test_assistant_review_retries_then_succeeds(repo_root, tmp_path, monkeypatch):
    run_dir = tmp_path / "demo_run_retry"
    run_dir.mkdir()
    (run_dir / "cognitive_fingerprint.json").write_text(
        json.dumps({"deployment_class": "READY", "task_fit": {"summarisation": "READY"}}),
        encoding="utf-8",
    )
    (run_dir / "report.md").write_text("# Cognitive Mesh Report\n\nHello.", encoding="utf-8")

    class FakeAdapter:
        call_count = 0

        def __init__(self, _config):
            pass

        def generate(self, probe, prompt, context):
            FakeAdapter.call_count += 1

            class Response:
                text = (
                    "Okay, let's think.\n\n## Assistant View\nBad format."
                    if FakeAdapter.call_count == 1
                    else "## Assistant View\n\nStable enough for inspection only.\n\n## Likely Risks\n\n- Drift.\n\n## Suggested Follow-ups\n\n- Re-run."
                )

            return Response()

    monkeypatch.setattr("cm_test_chamber.assistant_review.LocalHttpAdapter", FakeAdapter)
    result = run_assistant_review(repo_root, run_dir, "qwen3-8b-abliterated-q8_0-assistant")
    assert result.output_path.exists()
    raw = result.raw_output_path.read_text(encoding="utf-8")
    assert "--- attempt boundary ---" in raw


def test_assistant_review_can_succeed_on_third_attempt(repo_root, tmp_path, monkeypatch):
    run_dir = tmp_path / "demo_run_third_try"
    run_dir.mkdir()
    (run_dir / "cognitive_fingerprint.json").write_text(
        json.dumps({"deployment_class": "READY", "task_fit": {"summarisation": "READY"}}),
        encoding="utf-8",
    )
    (run_dir / "report.md").write_text("# Cognitive Mesh Report\n\nHello.", encoding="utf-8")

    class FakeAdapter:
        call_count = 0

        def __init__(self, _config):
            pass

        def generate(self, probe, prompt, context):
            FakeAdapter.call_count += 1

            class Response:
                text = (
                    "Okay, let's think.\n\n## Assistant View\nBad format."
                    if FakeAdapter.call_count == 1
                    else "## Assistant View\n\nAlmost there.\n\n## Likely Risks\n\n- Drift."
                    if FakeAdapter.call_count == 2
                    else "## Assistant View\n\nStable enough for inspection only.\n\n## Likely Risks\n\n- Drift.\n\n## Suggested Follow-ups\n\n- Re-run."
                )

            return Response()

    monkeypatch.setattr("cm_test_chamber.assistant_review.LocalHttpAdapter", FakeAdapter)
    result = run_assistant_review(repo_root, run_dir, "qwen3-8b-abliterated-q8_0-assistant")
    telemetry = json.loads(result.telemetry_path.read_text(encoding="utf-8"))
    assert telemetry["attempt_count"] == 3


def test_assistant_review_salvages_leading_prose_without_retry(repo_root, tmp_path, monkeypatch):
    run_dir = tmp_path / "demo_run_salvage"
    run_dir.mkdir()
    (run_dir / "cognitive_fingerprint.json").write_text(
        json.dumps({"deployment_class": "READY", "task_fit": {"summarisation": "READY"}}),
        encoding="utf-8",
    )
    (run_dir / "report.md").write_text("# Cognitive Mesh Report\n\nHello.", encoding="utf-8")

    class FakeAdapter:
        def __init__(self, _config):
            pass

        def generate(self, probe, prompt, context):
            class Response:
                text = "Based on the provided information:\n\n## Assistant View\nA\n\n## Likely Risks\nB\n\n## Suggested Follow-ups\nC"

            return Response()

    monkeypatch.setattr("cm_test_chamber.assistant_review.LocalHttpAdapter", FakeAdapter)
    result = run_assistant_review(repo_root, run_dir, "qwen3-8b-abliterated-q8_0-assistant")
    rendered = result.output_path.read_text(encoding="utf-8")
    assert "Based on the provided information" not in rendered
    telemetry = json.loads(result.telemetry_path.read_text(encoding="utf-8"))
    assert telemetry["salvage_events"][0]["had_salvage"] is True


def test_assistant_review_fails_validation_after_retry(repo_root, tmp_path, monkeypatch):
    run_dir = tmp_path / "demo_run_fail"
    run_dir.mkdir()
    (run_dir / "cognitive_fingerprint.json").write_text(
        json.dumps({"deployment_class": "READY", "task_fit": {"summarisation": "READY"}}),
        encoding="utf-8",
    )
    (run_dir / "report.md").write_text("# Cognitive Mesh Report\n\nHello.", encoding="utf-8")

    class FakeAdapter:
        def __init__(self, _config):
            pass

        def generate(self, probe, prompt, context):
            class Response:
                text = "Okay, let's tackle this.\nNeed to think more."

            return Response()

    monkeypatch.setattr("cm_test_chamber.assistant_review.LocalHttpAdapter", FakeAdapter)
    with pytest.raises(ValueError):
        run_assistant_review(repo_root, run_dir, "qwen3-8b-abliterated-q8_0-assistant")
    assert (run_dir / "assistant_review_validation_failure.json").exists()
    assert (run_dir / "assistant_review_telemetry.json").exists()
