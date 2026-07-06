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

## v0.2 Negative-Lane Engine

- confirm [docs/v0_2_acceptance.md](C:/Users/User/Desktop/github_portal/cognition-mesh-test-chamber/docs/v0_2_acceptance.md) still matches the intended release scope
- run `pytest`
- run a fresh baseline smoke test:

```powershell
python -m cm_test_chamber.cli run `
  --model configs/models/mock_model.json `
  --host configs/hosts/schema_locked_no_tools.json `
  --task-pack configs/task_profiles/mvp_probe_pack.json `
  --out runs/release_smoke_baseline
```

- run a fresh gauntlet smoke test:

```powershell
python -m cm_test_chamber.cli gauntlet-run `
  --model configs/models/mock_model.json `
  --host configs/hosts/schema_locked_no_tools.json `
  --gauntlet configs/gauntlets/mvp_general_gauntlet.json `
  --out runs/release_smoke_gauntlet `
  --retry-policy auto
```

- confirm the baseline smoke run writes:
  - `probe_results.jsonl`
  - `failure_log.jsonl`
  - `negative_lane_suggestions.json`
  - `cognitive_fingerprint.json`
  - `report.md`
  - `run_config_snapshot.json`
- confirm the gauntlet smoke run writes the expected gauntlet result artifacts and updates historical atlas state
- verify `python -m cm_test_chamber.cli gauntlet-atlas` returns a sane summary after the smoke gauntlet run
- verify `python -m cm_test_chamber.cli draft-probes` and `python -m cm_test_chamber.cli draft-probes --materialize` complete cleanly
- verify [README.md](C:/Users/User/Desktop/github_portal/cognition-mesh-test-chamber/README.md), [docs/operator-quickstart.md](C:/Users/User/Desktop/github_portal/cognition-mesh-test-chamber/docs/operator-quickstart.md), [docs/user-manual.md](C:/Users/User/Desktop/github_portal/cognition-mesh-test-chamber/docs/user-manual.md), and [docs/negative-lane-engine.md](C:/Users/User/Desktop/github_portal/cognition-mesh-test-chamber/docs/negative-lane-engine.md) still match the actual CLI and workflow
- verify the dashboard starts with:

```powershell
python scripts/start_dashboard.py
```

- verify the dashboard still auto-opens unless intentionally suppressed
- verify licensing still points to AGPLv3 in `LICENSE`, `README.md`, and `pyproject.toml`
- confirm `.gitignore` still excludes local model weights, runtime binaries, caches, logs, and generated run artifacts
- decide which example artifacts, if any, are intentionally kept for documentation versus regenerated locally
- update [CHANGELOG.md](C:/Users/User/Desktop/github_portal/cognition-mesh-test-chamber/CHANGELOG.md)
- if releasing publicly, create the git tag and package snapshot from the validated state
