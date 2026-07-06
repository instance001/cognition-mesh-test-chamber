from cm_test_chamber.dashboard import (
    JobManager,
    build_assistant_fit_aggregate,
    build_dashboard_status,
    build_mock_preset_runner,
    compare_assistant_reviews_within_run,
    compare_runs,
    list_run_directories,
    rebuild_assistant_fit_summary_index,
    read_run_details,
)


def test_dashboard_status_includes_catalogs_and_configs(repo_root):
    status = build_dashboard_status(repo_root)
    assert status["model_under_test"]
    assert status["assistants"]
    assert "configs/models/mock_model.json" in status["model_configs"]
    assert "runs" in status
    assert "gauntlet_history_index" in status
    assert "assistant_fit_index" in status
    assert "aggregate" in status["assistant_fit_index"]


def test_list_run_directories_detects_demo_run(repo_root):
    runs = list_run_directories(repo_root)
    names = {item["name"] for item in runs}
    assert "demo_mock" in names


def test_list_run_directories_detects_gauntlet_run(tmp_path):
    run_dir = tmp_path / "runs" / "demo_gauntlet"
    run_dir.mkdir(parents=True)
    (run_dir / "gauntlet_summary.md").write_text("# Summary\n", encoding="utf-8")
    (run_dir / "gauntlet_scores.json").write_text('{"overall_score": 0.72}\n', encoding="utf-8")
    (run_dir / "gauntlet_fingerprint.json").write_text(
        '{"systemic_failures": 1, "soft_failures": 2}\n',
        encoding="utf-8",
    )
    runs = list_run_directories(tmp_path)
    assert runs[0]["run_type"] == "gauntlet"
    assert runs[0]["has_gauntlet_summary"] is True
    assert runs[0]["gauntlet_overall_score"] == 0.72


def test_job_manager_tracks_completed_job():
    manager = JobManager()
    job = manager.enqueue("test", {"a": 1}, lambda: "done")
    current = None
    for _ in range(50):
        jobs = manager.list_jobs()
        current = next(item for item in jobs if item["job_id"] == job["job_id"])
        if current["status"] == "completed":
            break
    else:
        raise AssertionError("job did not complete in time")
    assert current is not None
    assert current["result"] == "done"


def test_read_run_details_returns_demo_artifacts(repo_root):
    details = read_run_details(repo_root, "runs/demo_mock")
    assert details["fingerprint"] is not None
    assert details["report_markdown"] is not None
    assert details["probe_results"] is not None


def test_read_run_details_returns_gauntlet_artifacts(tmp_path):
    run_dir = tmp_path / "runs" / "demo_gauntlet"
    run_dir.mkdir(parents=True)
    (run_dir / "gauntlet_summary.md").write_text("# Summary\n", encoding="utf-8")
    (run_dir / "gauntlet_scores.json").write_text('{"overall_score": 0.72, "turns": []}\n', encoding="utf-8")
    (run_dir / "gauntlet_fingerprint.json").write_text('{"weakest_lane": "role_boundary"}\n', encoding="utf-8")
    (run_dir / "gauntlet_candidate_probe_requests.json").write_text(
        '[{"failure_family": "role_boundary"}]\n',
        encoding="utf-8",
    )
    (run_dir / "gauntlet_failure_log.jsonl").write_text(
        '{"turn_id": "turn_01", "classification": "soft"}\n',
        encoding="utf-8",
    )
    (run_dir / "gauntlet_transcript.jsonl").write_text(
        '{"turn_id": "turn_01", "user_input": "hi", "raw_model_output": "{}"}\n',
        encoding="utf-8",
    )
    details = read_run_details(tmp_path, "runs/demo_gauntlet")
    assert details["run_type"] == "gauntlet"
    assert details["gauntlet_summary_markdown"] is not None
    assert details["gauntlet_scores"]["overall_score"] == 0.72
    assert details["gauntlet_candidate_probe_requests"][0]["failure_family"] == "role_boundary"
    assert details["gauntlet_transcript"][0]["turn_id"] == "turn_01"


def test_read_run_details_returns_assistant_telemetry_when_present(repo_root):
    details = read_run_details(repo_root, "runs/qwen3_local_first_pass")
    assert details["assistant_review_telemetry"] is not None
    assert details["assistant_evaluator_fitness"] is not None
    assert isinstance(details["assistant_reviews"], list)
    assert len(details["assistant_reviews"]) >= 2


def test_compare_runs_returns_artifact_diff_shape(repo_root):
    comparison = compare_runs(repo_root, "runs/demo_mock", "runs/demo_mock")
    assert comparison["deployment_class"]["left"] == comparison["deployment_class"]["right"]
    assert "task_fit" in comparison
    assert "failure_families" in comparison
    assert "assistant_review_cleanup" in comparison
    assert "assistant_review_cleanup_by_id" in comparison


def test_compare_assistant_reviews_within_run_returns_profile_diff(repo_root):
    comparison = compare_assistant_reviews_within_run(
        repo_root,
        "runs/qwen3_local_first_pass",
        "qwen3-8b-abliterated-q8_0-assistant",
        "qwen3-8b-abliterated-q8_0-assistant-alt",
    )
    assert comparison["left"]["assistant_id"] == "qwen3-8b-abliterated-q8_0-assistant"
    assert comparison["right"]["assistant_id"] == "qwen3-8b-abliterated-q8_0-assistant-alt"
    assert comparison["fit_summary"]["winner"] == "qwen3-8b-abliterated-q8_0-assistant"
    assert comparison["left"]["evaluator_fitness"]["score"] >= comparison["right"]["evaluator_fitness"]["score"]
    assert (repo_root / "runs" / "qwen3_local_first_pass" / "assistant_reviews" / "assistant_fit_summary.json").exists()


def test_rebuild_assistant_fit_summary_index_writes_index(repo_root):
    compare_assistant_reviews_within_run(
        repo_root,
        "runs/qwen3_local_first_pass",
        "qwen3-8b-abliterated-q8_0-assistant",
        "qwen3-8b-abliterated-q8_0-assistant-alt",
    )
    index_path = rebuild_assistant_fit_summary_index(repo_root)
    assert index_path.exists()
    payload = index_path.read_text(encoding="utf-8")
    assert "left_validation_passed" in payload
    assert "right_attempt_count" in payload
    assert "left_fitness_score" in payload


def test_build_assistant_fit_aggregate_counts_metrics():
    aggregate = build_assistant_fit_aggregate(
        {
            "entries": [
                {
                    "winner": "a",
                    "loser": "b",
                    "left_assistant_id": "a",
                    "right_assistant_id": "b",
                    "left_validation_passed": True,
                    "right_validation_passed": False,
                    "left_had_salvage": True,
                    "right_had_salvage": False,
                    "left_fitness_score": 82,
                    "right_fitness_score": 38,
                    "left_fitness_suitability": "usable with monitoring",
                    "right_fitness_suitability": "containment-only",
                }
            ]
        }
    )
    assert aggregate["a"]["wins"] == 1
    assert aggregate["b"]["losses"] == 1
    assert aggregate["b"]["validation_failures"] == 1
    assert aggregate["a"]["fitness_score_average"] == 82
    assert aggregate["b"]["containment_only_count"] == 1
    assert "rationale" in aggregate["a"]
    assert "readiness" in aggregate["a"]


def test_build_mock_preset_runner_sets_mode_and_output(repo_root):
    runner = build_mock_preset_runner(repo_root, "mixed")
    assert runner.model.mode == "mixed"
    assert runner.out_dir.name == "mock_mixed"
