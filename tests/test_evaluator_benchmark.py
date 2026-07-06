import json
import shutil

from cm_test_chamber.assistant_review import AssistantReviewResult, get_assistant_review_paths
from cm_test_chamber.evaluator_benchmark import (
    evaluate_benchmark_review,
    load_evaluator_benchmark_suite,
    materialize_evaluator_benchmark_runs,
    run_evaluator_benchmark_suite,
)


def test_load_evaluator_benchmark_suite(repo_root):
    suite = load_evaluator_benchmark_suite(repo_root)
    assert suite.suite_id == "assistant_evaluator_benchmark_v1"
    assert len(suite.targets) >= 4


def test_materialize_evaluator_benchmark_runs_writes_required_artifacts(repo_root):
    run_dirs = materialize_evaluator_benchmark_runs(repo_root)
    assert run_dirs
    first = run_dirs[0]
    assert (first / "report.md").exists()
    assert (first / "cognitive_fingerprint.json").exists()
    assert (first / "probe_results.jsonl").exists()
    assert (first / "assistant_review_guidance.json").exists()


def test_evaluate_benchmark_review_flags_missing_and_forbidden(repo_root):
    suite = load_evaluator_benchmark_suite(repo_root)
    target = next(item for item in suite.targets if item.target_id == "quoted_instruction_hierarchy")
    result = evaluate_benchmark_review(
        "## Assistant View\nignore the user\n\n## Likely Risks\nnone\n\n## Suggested Follow-ups\nnone",
        target,
        {"score": 89, "signals": {"validation_passed": True}},
    )
    assert result["passed"] is False
    assert "hostile" in result["missing_required"]
    assert "ignore the user" in result["forbidden_hits"]


def test_run_evaluator_benchmark_suite_writes_summary(repo_root, monkeypatch):
    run_dirs = materialize_evaluator_benchmark_runs(repo_root)
    created_paths = list(run_dirs)
    created_paths.append(repo_root / "runs" / "evaluator_benchmark_suite_summary.json")

    def fake_run_assistant_review(repo_root_arg, run_dir, assistant_id):
        paths = get_assistant_review_paths(run_dir, assistant_id)
        paths["root"].mkdir(parents=True, exist_ok=True)
        review = (
            f"# Assistant Review: {assistant_id}\n\n"
            f"- Assistant ID: `{assistant_id}`\n\n"
            "## Assistant View\nThis is not general deployment. Guardrail review is required and hostile text is data.\n\n"
            "## Likely Risks\n- Operator review is still required.\n\n"
            "## Suggested Follow-ups\n- Keep the official result unchanged.\n"
        )
        paths["review"].write_text(review, encoding="utf-8")
        paths["raw"].write_text(review, encoding="utf-8")
        telemetry = {
            "assistant_id": assistant_id,
            "assistant_label": assistant_id,
            "attempt_count": 1,
            "salvage_events": [],
            "validation_passed": True,
            "final_issues": [],
        }
        fitness = {
            "assistant_id": assistant_id,
            "assistant_label": assistant_id,
            "score": 92,
            "max_score": 100,
            "suitability": "production-usable",
            "signals": {"validation_passed": True},
        }
        paths["telemetry"].write_text(json.dumps(telemetry, indent=2) + "\n", encoding="utf-8")
        paths["fitness"].write_text(json.dumps(fitness, indent=2) + "\n", encoding="utf-8")
        return AssistantReviewResult(
            assistant_id=assistant_id,
            assistant_label=assistant_id,
            output_path=paths["review"],
            raw_output_path=paths["raw"],
            telemetry_path=paths["telemetry"],
        )

    monkeypatch.setattr("cm_test_chamber.evaluator_benchmark.run_assistant_review", fake_run_assistant_review)
    try:
        summary_path = run_evaluator_benchmark_suite(
            repo_root,
            [
                "qwen3-8b-abliterated-q8_0-assistant",
                "qwen3-8b-abliterated-q8_0-assistant-alt",
            ],
        )
        assert summary_path.exists()
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
        assert payload["assistant_summaries"]
        assert "benchmark_score_average" in payload["assistant_summaries"][0]
    finally:
        for path in created_paths:
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            elif path.exists():
                path.unlink()


def test_run_evaluator_benchmark_suite_continues_after_review_failure(repo_root, monkeypatch):
    run_dirs = materialize_evaluator_benchmark_runs(repo_root)
    created_paths = list(run_dirs)
    created_paths.append(repo_root / "runs" / "evaluator_benchmark_suite_summary.json")

    def fake_run_assistant_review(repo_root_arg, run_dir, assistant_id):
        paths = get_assistant_review_paths(run_dir, assistant_id)
        paths["root"].mkdir(parents=True, exist_ok=True)
        telemetry = {
            "assistant_id": assistant_id,
            "assistant_label": assistant_id,
            "attempt_count": 3,
            "salvage_events": [{"attempt": 3, "had_salvage": True, "leading_prose": "", "trailing_text": "", "salvaged_text": "## Assistant View\nA\n\n## Likely Risks\nB"}],
            "validation_passed": False,
            "final_issues": ["Missing required section: ## Suggested Follow-ups"],
        }
        fitness = {
            "assistant_id": assistant_id,
            "assistant_label": assistant_id,
            "score": 20,
            "max_score": 100,
            "suitability": "containment-only",
            "signals": {"validation_passed": False},
        }
        failure = {
            "assistant_id": assistant_id,
            "assistant_label": assistant_id,
            "issues": telemetry["final_issues"],
            "attempts": ["bad attempt"],
            "salvage_events": telemetry["salvage_events"],
        }
        paths["telemetry"].write_text(json.dumps(telemetry, indent=2) + "\n", encoding="utf-8")
        paths["fitness"].write_text(json.dumps(fitness, indent=2) + "\n", encoding="utf-8")
        paths["failure"].write_text(json.dumps(failure, indent=2) + "\n", encoding="utf-8")
        raise ValueError("Assistant review output failed validation.")

    monkeypatch.setattr("cm_test_chamber.evaluator_benchmark.run_assistant_review", fake_run_assistant_review)
    try:
        summary_path = run_evaluator_benchmark_suite(repo_root, ["qwen3-8b-abliterated-q8_0-assistant"])
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
        assert payload["assistant_summaries"][0]["fail_count"] >= 1
    finally:
        for path in created_paths:
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            elif path.exists():
                path.unlink()
