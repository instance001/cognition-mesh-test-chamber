import json

from cm_test_chamber.cli import main
from cm_test_chamber.gauntlet.decisions import upsert_probe_request_decision
from cm_test_chamber.gauntlet.forge import materialize_probe_draft_files, rebuild_probe_forge_drafts
from cm_test_chamber.gauntlet.history import rebuild_gauntlet_history_index


def _seed_materialized_draft(repo_root):
    run_dir = repo_root / "runs" / "cli_draft_demo"
    run_dir.mkdir(parents=True, exist_ok=True)
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
    upsert_probe_request_decision(repo_root, "role_boundary", "confirmed_for_forge", "cli check")
    rebuild_gauntlet_history_index(repo_root)
    rebuild_probe_forge_drafts(repo_root)
    payload = materialize_probe_draft_files(repo_root)
    return payload["entries"][0]["draft_id"]


def test_cli_draft_probes_lists_materialized_drafts(repo_root, capsys):
    draft_id = _seed_materialized_draft(repo_root)
    exit_code = main(["draft-probes"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert draft_id in captured.out
    assert "role_boundary" in captured.out


def test_cli_draft_probes_inspects_and_validates_draft(repo_root, capsys):
    draft_id = _seed_materialized_draft(repo_root)
    exit_code = main(["draft-probes", "--draft-id", draft_id])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"validation_issues": []' in captured.out
    assert '"probe_id": "role_boundary_draft_probe"' in captured.out


def test_cli_draft_probes_materialize_refreshes_files(repo_root, capsys):
    _seed_materialized_draft(repo_root)
    exit_code = main(["draft-probes", "--materialize"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Materialized" in captured.out
