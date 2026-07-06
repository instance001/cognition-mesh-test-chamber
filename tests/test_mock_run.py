import json
from pathlib import Path

from cm_test_chamber.runner.probe_runner import ProbeRunner
from cm_test_chamber.runner.run_config import load_host_profile, load_model_config, load_task_pack


def _run_mode(repo_root: Path, tmp_path: Path, mode: str):
    model_path = tmp_path / f"mock_model_{mode}.json"
    model_config = json.loads((repo_root / "configs" / "models" / "mock_model.json").read_text(encoding="utf-8"))
    model_config["mode"] = mode
    model_path.write_text(json.dumps(model_config), encoding="utf-8")
    runner = ProbeRunner(
        repo_root=repo_root,
        model=load_model_config(model_path),
        host=load_host_profile(repo_root / "configs" / "hosts" / "schema_locked_no_tools.json"),
        task_pack=load_task_pack(repo_root / "configs" / "task_profiles" / "mvp_probe_pack.json"),
        out_dir=tmp_path / f"run_{mode}",
    )
    return runner.run()


def test_mock_modes_behave_as_expected(repo_root, tmp_path):
    good = _run_mode(repo_root, tmp_path, "good")
    mixed = _run_mode(repo_root, tmp_path, "mixed")
    bad = _run_mode(repo_root, tmp_path, "bad")

    good_failures = sum(1 for result in good["results"] if result.status == "fail")
    mixed_failures = sum(1 for result in mixed["results"] if result.status == "fail")
    bad_failures = sum(1 for result in bad["results"] if result.status == "fail")

    assert good_failures <= 1
    assert mixed_failures >= 2
    assert bad_failures >= 4
    assert len(bad["suggestions"]) >= 2
