import json

from cm_test_chamber.gauntlet import load_gauntlet_spec
from cm_test_chamber.gauntlet.runner import GauntletRunner
from cm_test_chamber.runner.run_config import load_host_profile, load_model_config


def _gauntlet_run(repo_root, tmp_path, mode: str, retry_policy: str = "none"):
    model_path = tmp_path / f"mock_model_gauntlet_{mode}.json"
    model_config = json.loads((repo_root / "configs" / "models" / "mock_model.json").read_text(encoding="utf-8"))
    model_config["mode"] = mode
    model_path.write_text(json.dumps(model_config), encoding="utf-8")
    runner = GauntletRunner(
        repo_root=repo_root,
        model=load_model_config(model_path),
        host=load_host_profile(repo_root / "configs" / "hosts" / "schema_locked_no_tools.json"),
        gauntlet=load_gauntlet_spec(repo_root / "configs" / "gauntlets" / "mvp_general_gauntlet.json"),
        out_dir=tmp_path / f"gauntlet_{mode}",
        retry_policy=retry_policy,
    )
    return runner.run(), runner.out_dir


def test_mock_gauntlet_modes_degrade_as_expected(repo_root, tmp_path):
    good, _ = _gauntlet_run(repo_root, tmp_path, "good")
    mixed, _ = _gauntlet_run(repo_root, tmp_path, "mixed")
    bad, _ = _gauntlet_run(repo_root, tmp_path, "bad")

    assert good["overall_score"] > mixed["overall_score"] > bad["overall_score"]
    assert len(bad["candidate_probe_requests"]) >= 3
    assert any(item["classification"] == "systemic" for item in bad["failures"])


def test_gauntlet_run_writes_expected_artifacts(repo_root, tmp_path):
    result, out_dir = _gauntlet_run(repo_root, tmp_path, "good")
    assert result["overall_score"] > 0
    assert (out_dir / "gauntlet_transcript.jsonl").exists()
    assert (out_dir / "gauntlet_scores.json").exists()
    assert (out_dir / "gauntlet_failure_log.jsonl").exists()
    assert (out_dir / "gauntlet_summary.md").exists()
    assert (out_dir / "gauntlet_fingerprint.json").exists()
    assert (out_dir / "gauntlet_candidate_probe_requests.json").exists()
    assert (out_dir / "gauntlet_run_config_snapshot.json").exists()


def test_gauntlet_retry_policy_records_retry_without_overwriting_original(repo_root, tmp_path):
    result, out_dir = _gauntlet_run(repo_root, tmp_path, "mixed", retry_policy="auto")
    turn_map = {item.turn_id: item for item in result["turns"]}
    tool_turn = turn_map["turn_06_tool_signature"]
    assert tool_turn.retry is not None
    assert tool_turn.retry["attempted"] is True
    assert tool_turn.retry["passed"] is True
    assert tool_turn.classification == "flaky"
    transcript_payload = (out_dir / "gauntlet_scores.json").read_text(encoding="utf-8")
    assert '"retry_policy": "auto"' in transcript_payload
    assert '"raw_model_output"' in transcript_payload


def test_gauntlet_retry_policy_marks_host_sensitive_when_retry_passes(repo_root, tmp_path):
    result, _ = _gauntlet_run(repo_root, tmp_path, "mixed", retry_policy="auto")
    turn_map = {item.turn_id: item for item in result["turns"]}
    uncertainty_turn = turn_map["turn_08_uncertainty"]
    assert uncertainty_turn.retry is not None
    assert uncertainty_turn.retry["kind"] == "host_sensitive"
    assert uncertainty_turn.retry["passed"] is True
    assert uncertainty_turn.classification == "host_sensitive"


def test_candidate_probe_requests_capture_richer_evidence(repo_root, tmp_path):
    result, _ = _gauntlet_run(repo_root, tmp_path, "mixed", retry_policy="auto")
    requests = {item["failure_family"]: item for item in result["candidate_probe_requests"]}
    tool_request = requests["tool_signature_discipline"]
    assert tool_request["classification"] == "flaky"
    assert tool_request["retry_observation"] == "passed_on_retry"
    assert tool_request["recommendation"] == "probe_needed"
    assert tool_request["severity"] == "high"
    assert tool_request["fail_count"] >= 1
    assert "turn_06_tool_signature" in tool_request["source_turns"]
    assert "evidence_summary" in tool_request

    role_request = requests["role_boundary"]
    assert role_request["classification"] == "systemic"
    assert role_request["recommendation"] == "probe_needed"
    assert role_request["fail_count"] >= 1

    good_result, _ = _gauntlet_run(repo_root, tmp_path, "good")
    good_requests = {item["failure_family"]: item for item in good_result["candidate_probe_requests"]}
    observed_request = good_requests["role_boundary"]
    assert observed_request["classification"] == "observed_only"
    assert observed_request["recommendation"] == "probe_candidate"
    assert observed_request["pass_count"] >= 1
