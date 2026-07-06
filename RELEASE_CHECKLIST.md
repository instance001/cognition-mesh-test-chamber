# Release Checklist

Use this before tagging or publishing a new release.

## v0.1 Baseline

- confirm [docs/v0_1_acceptance.md](C:/Users/User/Desktop/github_portal/cognition-mesh-test-chamber/docs/v0_1_acceptance.md) still matches the intended release scope
- run `pytest`
- run a fresh mock smoke test:

```powershell
python -m cm_test_chamber.cli run `
  --model configs/models/mock_model.json `
  --host configs/hosts/schema_locked_no_tools.json `
  --task-pack configs/task_profiles/mvp_probe_pack.json `
  --out runs/release_smoke
```

- confirm the smoke run writes:
  - `probe_results.jsonl`
  - `failure_log.jsonl`
  - `negative_lane_suggestions.json`
  - `cognitive_fingerprint.json`
  - `report.md`
  - `run_config_snapshot.json`
- verify [README.md](C:/Users/User/Desktop/github_portal/cognition-mesh-test-chamber/README.md) still gives a correct first-run path
- verify [docs/operator-quickstart.md](C:/Users/User/Desktop/github_portal/cognition-mesh-test-chamber/docs/operator-quickstart.md) and [docs/user-manual.md](C:/Users/User/Desktop/github_portal/cognition-mesh-test-chamber/docs/user-manual.md) still match the actual CLI
- verify the dashboard starts with:

```powershell
python scripts/start_dashboard.py
```

- verify licensing still points to AGPLv3 in `LICENSE`, `README.md`, and `pyproject.toml`
- confirm `.gitignore` still excludes local model weights, runtime binaries, caches, logs, and generated run artifacts
- decide which example artifacts, if any, are intentionally kept for documentation versus regenerated locally
- update [CHANGELOG.md](C:/Users/User/Desktop/github_portal/cognition-mesh-test-chamber/CHANGELOG.md)
- if releasing publicly, create the git tag and package snapshot from the validated state
