import json

from cm_test_chamber.gauntlet.decisions import upsert_probe_request_decision
from cm_test_chamber.gauntlet.draft_validator import validate_probe_draft_file, validate_probe_draft_payload
from cm_test_chamber.gauntlet.forge import materialize_probe_draft_files, rebuild_probe_forge_drafts
from cm_test_chamber.gauntlet.history import rebuild_gauntlet_history_index


def _materialized_role_boundary_draft(tmp_path):
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
                    "source_turns": ["turn_03_quoted_instruction"],
                }
            ]
        ),
        encoding="utf-8",
    )
    (run_dir / "gauntlet_run_config_snapshot.json").write_text(
        json.dumps({"model": {"model_name": "mock-model"}}),
        encoding="utf-8",
    )
    upsert_probe_request_decision(tmp_path, "role_boundary", "confirmed_for_forge", "validate this")
    rebuild_gauntlet_history_index(tmp_path)
    rebuild_probe_forge_drafts(tmp_path)
    payload = materialize_probe_draft_files(tmp_path)
    draft_path = tmp_path / payload["entries"][0]["materialized_probe_path"]
    return draft_path


def test_validate_probe_draft_file_accepts_materialized_blueprint(tmp_path):
    draft_path = _materialized_role_boundary_draft(tmp_path)
    issues = validate_probe_draft_file(draft_path)
    assert issues == []


def test_validate_probe_draft_payload_reports_missing_fields():
    issues = validate_probe_draft_payload({"draft_probe": True})
    assert "missing top-level field: probe_id" in issues
    assert "missing top-level field: draft_metadata" in issues


def test_validate_probe_draft_payload_reports_consistency_errors(tmp_path):
    draft_path = _materialized_role_boundary_draft(tmp_path)
    payload = json.loads(draft_path.read_text(encoding="utf-8"))
    payload["draft_metadata"]["operator_decision"] = "probe_candidate"
    payload["expected_json"]["required"] = ["finding"]
    issues = validate_probe_draft_payload(payload)
    assert "draft_metadata.operator_decision must be 'confirmed_for_forge'" in issues
    assert "expected_json.required must include finding, evidence, and decision" in issues
