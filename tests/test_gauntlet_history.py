import json

from cm_test_chamber.gauntlet.history import (
    build_gauntlet_history_aggregate,
    read_or_rebuild_gauntlet_history_index,
    rebuild_gauntlet_history_index,
)


def test_build_gauntlet_history_aggregate_summarizes_models_and_families():
    aggregate = build_gauntlet_history_aggregate(
        {
            "entries": [
                {
                    "model_name": "mock-a",
                    "overall_score": 0.6,
                    "systemic_failures": 1,
                    "flaky_failures": 1,
                    "host_sensitive_failures": 0,
                    "soft_failures": 2,
                    "candidate_probe_requests": [
                        {
                            "failure_family": "quoted_instruction_hierarchy",
                            "recommendation": "probe_needed",
                            "classification": "systemic",
                            "fail_count": 2,
                            "pass_count": 0,
                            "severity": "critical",
                            "retry_observation": "failed_on_retry",
                        }
                    ],
                },
                {
                    "model_name": "mock-a",
                    "overall_score": 0.8,
                    "systemic_failures": 0,
                    "flaky_failures": 0,
                    "host_sensitive_failures": 1,
                    "soft_failures": 1,
                    "candidate_probe_requests": [
                        {
                            "failure_family": "quoted_instruction_hierarchy",
                            "recommendation": "probe_candidate",
                            "classification": "host_sensitive",
                            "fail_count": 1,
                            "pass_count": 1,
                            "severity": "high",
                            "retry_observation": "passed_on_retry",
                        }
                    ],
                },
            ]
        }
    )
    assert aggregate["models"]["mock-a"]["runs"] == 2
    assert aggregate["models"]["mock-a"]["average_score"] == 0.7
    family = aggregate["failure_families"]["quoted_instruction_hierarchy"]
    assert family["appearances"] == 2
    assert family["probe_needed_count"] == 1
    assert family["systemic_count"] == 1
    assert family["host_sensitive_count"] == 1


def test_rebuild_gauntlet_history_index_collects_run_artifacts(tmp_path):
    run_dir = tmp_path / "runs" / "demo_gauntlet"
    run_dir.mkdir(parents=True)
    (run_dir / "gauntlet_scores.json").write_text(
        json.dumps(
            {
                "gauntlet_id": "mvp_general_gauntlet",
                "retry_policy": "auto",
                "overall_score": 0.72,
                "turns": [{"turn_id": "turn_01"}],
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "gauntlet_fingerprint.json").write_text(
        json.dumps(
            {
                "weakest_lane": "role_boundary",
                "most_repeated_failure_family": "role_boundary",
                "systemic_failures": 1,
                "flaky_failures": 0,
                "host_sensitive_failures": 1,
                "soft_failures": 2,
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
    (run_dir / "gauntlet_summary.md").write_text("# Summary\n", encoding="utf-8")
    (run_dir / "gauntlet_run_config_snapshot.json").write_text(
        json.dumps({"model": {"model_name": "mock-model"}, "retry_policy": "auto"}),
        encoding="utf-8",
    )

    index_path = rebuild_gauntlet_history_index(tmp_path)
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    assert payload["entries"][0]["run_name"] == "demo_gauntlet"
    assert payload["entries"][0]["model_name"] == "mock-model"
    assert payload["entries"][0]["retry_policy"] == "auto"
    assert payload["aggregate"]["failure_families"]["role_boundary"]["probe_needed_count"] == 1


def test_read_or_rebuild_gauntlet_history_index_creates_default_index(tmp_path):
    payload = read_or_rebuild_gauntlet_history_index(tmp_path)
    assert payload["entries"] == []
    assert "aggregate" in payload
