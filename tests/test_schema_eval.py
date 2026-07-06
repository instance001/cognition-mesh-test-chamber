import json

from cm_test_chamber.evaluators.schema_eval import evaluate_schema
from cm_test_chamber.runner.run_config import load_probe


def test_schema_eval_accepts_exact_json(repo_root):
    probe = load_probe(repo_root / "probes" / "capability" / "schema_following.json")
    payload = json.dumps(
        {"person": "Ada", "action": "built the relay", "day": "Tuesday", "version": "R7"}
    )
    result = evaluate_schema(payload, probe)
    assert result["status"] == "pass"
    assert result["issues"] == []


def test_schema_eval_flags_missing_fields(repo_root):
    probe = load_probe(repo_root / "probes" / "capability" / "schema_following.json")
    payload = json.dumps({"person": "Ada"})
    result = evaluate_schema(payload, probe)
    families = {issue["family"] for issue in result["issues"]}
    assert result["status"] == "fail"
    assert "missing_required_field" in families
