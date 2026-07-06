import json

from cm_test_chamber.gauntlet.decisions import read_probe_request_decisions, upsert_probe_request_decision
from cm_test_chamber.gauntlet.history import rebuild_gauntlet_history_index


def test_upsert_probe_request_decision_writes_and_updates(tmp_path):
    path = upsert_probe_request_decision(tmp_path, "role_boundary", "probe_candidate", "watch this family")
    assert path.exists()
    payload = read_probe_request_decisions(tmp_path)
    assert payload["entries"][0]["failure_family"] == "role_boundary"
    assert payload["entries"][0]["decision"] == "probe_candidate"

    upsert_probe_request_decision(tmp_path, "role_boundary", "confirmed_for_forge", "confirmed")
    payload = read_probe_request_decisions(tmp_path)
    assert len(payload["entries"]) == 1
    assert payload["entries"][0]["decision"] == "confirmed_for_forge"


def test_gauntlet_history_includes_operator_decision(tmp_path):
    run_dir = tmp_path / "runs" / "demo_gauntlet"
    run_dir.mkdir(parents=True)
    (run_dir / "gauntlet_scores.json").write_text(
        json.dumps({"gauntlet_id": "mvp_general_gauntlet", "overall_score": 0.72, "turns": []}),
        encoding="utf-8",
    )
    (run_dir / "gauntlet_fingerprint.json").write_text(
        json.dumps(
            {
                "weakest_lane": "role_boundary",
                "most_repeated_failure_family": "role_boundary",
                "systemic_failures": 1,
                "flaky_failures": 0,
                "host_sensitive_failures": 0,
                "soft_failures": 0,
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "gauntlet_candidate_probe_requests.json").write_text(
        json.dumps(
            [
                {
                    "failure_family": "role_boundary",
                    "recommendation": "probe_needed",
                    "classification": "systemic",
                    "fail_count": 1,
                    "pass_count": 0,
                    "severity": "critical",
                    "retry_observation": "failed_on_retry",
                }
            ]
        ),
        encoding="utf-8",
    )
    (run_dir / "gauntlet_run_config_snapshot.json").write_text(
        json.dumps({"model": {"model_name": "mock-model"}}),
        encoding="utf-8",
    )
    upsert_probe_request_decision(tmp_path, "role_boundary", "confirmed_for_forge", "good candidate")
    index_path = rebuild_gauntlet_history_index(tmp_path)
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    family = payload["aggregate"]["failure_families"]["role_boundary"]
    assert family["operator_decision"] == "confirmed_for_forge"
    assert family["operator_note"] == "good candidate"
