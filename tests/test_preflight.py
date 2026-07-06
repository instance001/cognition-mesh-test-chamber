import json

from cm_test_chamber.preflight import (
    preflight_catalog_entry,
    preflight_model_config,
    preflight_run_folder,
    render_check_results,
)


def test_preflight_model_config_for_mock_passes(repo_root):
    results = preflight_model_config(repo_root, repo_root / "configs" / "models" / "mock_model.json", False)
    assert all(item.ok for item in results)


def test_preflight_run_folder_detects_missing_artifacts(tmp_path):
    run_dir = tmp_path / "missing_run"
    run_dir.mkdir()
    results = preflight_run_folder(run_dir)
    assert any(not item.ok for item in results if item.name.startswith("run_artifact:"))


def test_preflight_catalog_entry_finds_staged_model(repo_root):
    results = preflight_catalog_entry(repo_root, "assistant", "qwen3-8b-abliterated-q8_0-assistant", False)
    assert all(item.ok for item in results)


def test_render_check_results_reports_overall_status():
    rendered = render_check_results(
        [
            type("Result", (), {"name": "a", "ok": True, "detail": "fine"})(),
            type("Result", (), {"name": "b", "ok": False, "detail": "bad"})(),
        ]
    )
    assert "Overall: FAIL" in rendered
