import json

from cm_test_chamber.cli import main
from cm_test_chamber.gauntlet.decisions import upsert_probe_request_decision
from cm_test_chamber.gauntlet.history import rebuild_gauntlet_history_index


def _seed_gauntlet_atlas(repo_root):
    run_dir = repo_root / "runs" / "cli_atlas_demo"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "gauntlet_scores.json").write_text(
        json.dumps({"gauntlet_id": "mvp_general_gauntlet", "overall_score": 0.61, "turns": []}),
        encoding="utf-8",
    )
    (run_dir / "gauntlet_fingerprint.json").write_text(
        json.dumps(
            {
                "weakest_lane": "quoted_instruction_hierarchy",
                "most_repeated_failure_family": "quoted_instruction_hierarchy",
                "systemic_failures": 1,
                "flaky_failures": 1,
                "host_sensitive_failures": 0,
                "soft_failures": 2,
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "gauntlet_candidate_probe_requests.json").write_text(
        json.dumps(
            [
                {
                    "failure_family": "quoted_instruction_hierarchy",
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
        json.dumps({"model": {"model_name": "atlas-model"}}),
        encoding="utf-8",
    )
    upsert_probe_request_decision(repo_root, "quoted_instruction_hierarchy", "probe_needed", "watch closely")
    rebuild_gauntlet_history_index(repo_root)


def test_cli_gauntlet_atlas_lists_summary(repo_root, capsys):
    _seed_gauntlet_atlas(repo_root)
    exit_code = main(["gauntlet-atlas"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Gauntlet runs indexed:" in captured.out
    assert "quoted_instruction_hierarchy" in captured.out
    assert "atlas-model" in captured.out


def test_cli_gauntlet_atlas_inspects_family(repo_root, capsys):
    _seed_gauntlet_atlas(repo_root)
    exit_code = main(["gauntlet-atlas", "--family", "quoted_instruction_hierarchy"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"failure_family": "quoted_instruction_hierarchy"' in captured.out
    assert '"systemic_count"' in captured.out


def test_cli_gauntlet_atlas_inspects_model(repo_root, capsys):
    _seed_gauntlet_atlas(repo_root)
    exit_code = main(["gauntlet-atlas", "--model", "atlas-model"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"model": "atlas-model"' in captured.out
    assert '"average_score"' in captured.out


def test_cli_gauntlet_atlas_refreshes_index(repo_root, capsys):
    _seed_gauntlet_atlas(repo_root)
    exit_code = main(["gauntlet-atlas", "--refresh"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Gauntlet runs indexed:" in captured.out
