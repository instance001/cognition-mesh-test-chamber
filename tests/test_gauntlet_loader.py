from cm_test_chamber.gauntlet import GauntletConfigError, load_gauntlet_spec


def test_gauntlet_spec_loads(repo_root):
    spec = load_gauntlet_spec(repo_root / "configs" / "gauntlets" / "mvp_general_gauntlet.json")
    assert spec.gauntlet_id == "mvp_general_gauntlet"
    assert spec.version == "0.2.0-draft1"
    assert len(spec.turns) >= 10
    assert "quoted_instruction_hierarchy" in spec.failure_families
    assert spec.turns[0].scoring_weights["schema_validity"] > 0


def test_gauntlet_spec_rejects_missing_required_field(tmp_path):
    broken = tmp_path / "broken_gauntlet.json"
    broken.write_text(
        """
{
  "id": "broken",
  "name": "Broken",
  "description": "Missing turns",
  "version": "0.2",
  "scoring_profile": {},
  "failure_families": []
}
""".strip(),
        encoding="utf-8",
    )
    try:
        load_gauntlet_spec(broken)
    except GauntletConfigError as exc:
        assert "Missing gauntlet field: turns" in str(exc)
    else:
        raise AssertionError("Expected GauntletConfigError")


def test_gauntlet_spec_rejects_invalid_turn_scoring_weights(tmp_path):
    broken = tmp_path / "broken_turn_gauntlet.json"
    broken.write_text(
        """
{
  "id": "broken_turn",
  "name": "Broken Turn",
  "description": "Invalid scoring weights",
  "version": "0.2",
  "scoring_profile": {},
  "failure_families": ["evidence_binding"],
  "turns": [
    {
      "turn_id": "turn_01",
      "user_input": "Hello",
      "expected_output_schema": {},
      "scoring_weights": {
        "schema_validity": "high"
      }
    }
  ]
}
""".strip(),
        encoding="utf-8",
    )
    try:
        load_gauntlet_spec(broken)
    except GauntletConfigError as exc:
        assert "expected number" in str(exc)
    else:
        raise AssertionError("Expected GauntletConfigError")
