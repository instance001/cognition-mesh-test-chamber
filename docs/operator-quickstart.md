# Operator Quickstart

This is the shortest path from zero to a working run.

## 1. Install dependencies

From the repo root:

```powershell
python -m pip install -r requirements.txt
```

## 2. Verify the harness

Run the test suite:

```powershell
pytest
```

If tests pass, the local Python side is ready.

## 3. Run the safe mock demo

This does not require a live model.

```powershell
python -m cm_test_chamber.cli run `
  --model configs/models/mock_model.json `
  --host configs/hosts/schema_locked_no_tools.json `
  --task-pack configs/task_profiles/mvp_probe_pack.json `
  --out runs/demo_mock
```

Read these outputs first:

- `runs/demo_mock/report.md`
- `runs/demo_mock/cognitive_fingerprint.json`
- `runs/demo_mock/failure_log.jsonl`
- `runs/demo_mock/negative_lane_suggestions.json`

## 4. List available model profiles

```powershell
python -m cm_test_chamber.cli catalog --role model_under_test
python -m cm_test_chamber.cli catalog --role assistant
```

Use `model_under_test` for the model being judged.

Use `assistant` only for optional post-run commentary and evaluator-role experiments.

## 5. Run preflight before a local real-model run

```powershell
python -m cm_test_chamber.cli preflight `
  --mode run `
  --model configs/models/local_qwen3_8b_vulkan.json `
  --check-endpoint
```

## 6. Start the dashboard

```powershell
python scripts/start_dashboard.py
```

The dashboard auto-opens when started.

Use it to:

- launch mock runs
- inspect reports and fingerprints
- compare two runs side by side
- inspect assistant-review cleanup telemetry
- review evaluator-fit and assistant-role comparison data

## 7. Learn the system without guessing

If you want the complete beginner-friendly guide, read:

- [user-manual.md](C:/Users/User/Desktop/github_portal/cognition-mesh-test-chamber/docs/user-manual.md)

## License

This repository is licensed under the GNU Affero General Public License v3.0.

See [LICENSE](C:/Users/User/Desktop/github_portal/cognition-mesh-test-chamber/LICENSE).
