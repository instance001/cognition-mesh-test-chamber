from cm_test_chamber.negative_lanes.generator import generate_negative_lanes
from cm_test_chamber.runner.result_types import FailureEvent


def test_negative_lane_generation_deduplicates_lane_ids():
    failures = [
        FailureEvent(
            failure_id="a",
            probe_id="fake_repo_patch_basic",
            severity="medium",
            failure_family="invented_file_path",
            description="Invented file path.",
            evidence="src/missing.py",
            suggested_negative_lane="Reject missing files.",
        ),
        FailureEvent(
            failure_id="b",
            probe_id="fake_repo_patch_basic",
            severity="high",
            failure_family="broad_patch",
            description="Broad patch.",
            evidence="requirements.txt",
            suggested_negative_lane="Reject broad patches.",
        ),
    ]
    suggestions = generate_negative_lanes(failures)
    lane_ids = {item.lane_id for item in suggestions}
    assert "manifest_file_scope_guard" in lane_ids
    assert "task_scope_patch_guard" in lane_ids
