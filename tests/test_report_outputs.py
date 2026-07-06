from cm_test_chamber.runner.probe_runner import ProbeRunner
from cm_test_chamber.runner.run_config import load_host_profile, load_model_config, load_task_pack


def test_run_writes_required_outputs(repo_root, tmp_path):
    runner = ProbeRunner(
        repo_root=repo_root,
        model=load_model_config(repo_root / "configs" / "models" / "mock_model.json"),
        host=load_host_profile(repo_root / "configs" / "hosts" / "schema_locked_no_tools.json"),
        task_pack=load_task_pack(repo_root / "configs" / "task_profiles" / "mvp_probe_pack.json"),
        out_dir=tmp_path / "demo_mock",
    )
    runner.run()
    required = [
        "run_config_snapshot.json",
        "probe_results.jsonl",
        "failure_log.jsonl",
        "negative_lane_suggestions.json",
        "cognitive_fingerprint.json",
        "report.md",
    ]
    for filename in required:
        assert (tmp_path / "demo_mock" / filename).exists()
