import json

from cm_test_chamber.gauntlet.decisions import upsert_probe_request_decision
from cm_test_chamber.gauntlet.forge import (
    materialize_probe_draft_files,
    read_or_rebuild_probe_forge_drafts,
    rebuild_probe_forge_drafts,
)
from cm_test_chamber.gauntlet.history import rebuild_gauntlet_history_index


def test_probe_forge_drafts_only_include_confirmed_families(tmp_path):
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
                },
                {
                    "failure_family": "evidence_binding",
                    "recommendation": "probe_needed",
                    "classification": "soft",
                    "fail_count": 1,
                    "pass_count": 0,
                    "severity": "moderate",
                    "retry_observation": "not_run",
                    "source_turns": ["turn_04_evidence_binding"],
                },
            ]
        ),
        encoding="utf-8",
    )
    (run_dir / "gauntlet_run_config_snapshot.json").write_text(
        json.dumps({"model": {"model_name": "mock-model"}}),
        encoding="utf-8",
    )
    upsert_probe_request_decision(tmp_path, "role_boundary", "confirmed_for_forge", "confirmed target")
    upsert_probe_request_decision(tmp_path, "evidence_binding", "probe_candidate", "not yet")
    rebuild_gauntlet_history_index(tmp_path)
    draft_path = rebuild_probe_forge_drafts(tmp_path)
    payload = json.loads(draft_path.read_text(encoding="utf-8"))
    assert len(payload["entries"]) == 1
    draft = payload["entries"][0]
    assert draft["failure_family"] == "role_boundary"
    assert draft["priority"] == "high"
    assert draft["status"] == "draft_ready"
    assert "turn_03_quoted_instruction" in draft["suggested_turn_focus"]
    assert draft["operator_note"] == "confirmed target"


def test_read_or_rebuild_probe_forge_drafts_returns_default_payload(tmp_path):
    payload = read_or_rebuild_probe_forge_drafts(tmp_path)
    assert payload["entries"] == []


def test_materialize_probe_draft_files_writes_individual_draft(tmp_path):
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
    upsert_probe_request_decision(tmp_path, "role_boundary", "confirmed_for_forge", "ship this to forge")
    rebuild_gauntlet_history_index(tmp_path)
    rebuild_probe_forge_drafts(tmp_path)
    payload = materialize_probe_draft_files(tmp_path)
    draft = payload["entries"][0]
    assert draft["status"] == "draft_materialized"
    assert draft["materialized_probe_path"] == "local_probes/drafts/role_boundary_draft_001.json"
    materialized = json.loads((tmp_path / draft["materialized_probe_path"]).read_text(encoding="utf-8"))
    assert materialized["draft_probe"] is True
    assert materialized["probe_id"] == "role_boundary_draft_probe"
    assert materialized["category"] == "failure"
    assert materialized["evaluator"] == "text_eval"
    assert materialized["task_shape"]["category"] == "role_boundary"
    assert materialized["draft_metadata"]["operator_note"] == "ship this to forge"
    assert materialized["draft_metadata"]["status"] == "draft_materialized"
    assert "finding" in materialized["expected_json"]["required"]
    assert "decision" in materialized["required_phrases"]
