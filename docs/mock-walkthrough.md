# Mock Walkthrough

This is a concrete zero-risk demo path for learning the system without a live model.

It follows the same operator sequence used for the local release walkthrough.

## 1. Run the baseline lane

```powershell
python -m cm_test_chamber.cli run `
  --model configs/models/mock_model.json `
  --host configs/hosts/schema_locked_no_tools.json `
  --task-pack configs/task_profiles/mvp_probe_pack.json `
  --out runs/demo_mock
```

Expected baseline artifacts:

- `runs/demo_mock/probe_results.jsonl`
- `runs/demo_mock/failure_log.jsonl`
- `runs/demo_mock/negative_lane_suggestions.json`
- `runs/demo_mock/cognitive_fingerprint.json`
- `runs/demo_mock/report.md`

## 2. Run the gauntlet lane

```powershell
python -m cm_test_chamber.cli gauntlet-run `
  --model configs/models/mock_model.json `
  --host configs/hosts/schema_locked_no_tools.json `
  --gauntlet configs/gauntlets/mvp_general_gauntlet.json `
  --out runs/demo_gauntlet `
  --retry-policy auto
```

Expected gauntlet artifacts:

- `runs/demo_gauntlet/gauntlet_transcript.jsonl`
- `runs/demo_gauntlet/gauntlet_failure_log.jsonl`
- `runs/demo_gauntlet/gauntlet_scores.json`
- `runs/demo_gauntlet/gauntlet_fingerprint.json`
- `runs/demo_gauntlet/gauntlet_summary.md`
- `runs/demo_gauntlet/gauntlet_candidate_probe_requests.json`

## 3. Inspect the atlas

```powershell
python -m cm_test_chamber.cli gauntlet-atlas
```

What to look for:

- indexed gauntlet run count
- tracked failure families
- tracked models
- top failure-family summaries
- model-level aggregate summaries

## 4. Inspect draft probes

```powershell
python -m cm_test_chamber.cli draft-probes
python -m cm_test_chamber.cli draft-probes --materialize
```

What to look for:

- whether recurring failure families have draft probe candidates
- whether a draft is already materialized
- whether validation remains clean for the materialized draft payload

Optional inspection:

```powershell
python -m cm_test_chamber.cli draft-probes --draft-id role_boundary_draft_001
```

## 5. Start the dashboard

```powershell
python scripts/start_dashboard.py
```

Expected behavior:

- the dashboard starts locally
- the browser auto-opens by default
- baseline runs, gauntlet runs, atlas views, decisions, draft probes, and assistant-role surfaces are available

## Why This Walkthrough Matters

This path teaches the system in the intended order:

1. baseline truth surface
2. gauntlet discovery pressure
3. historical atlas interpretation
4. selective probe drafting
5. dashboard convenience layer

That is the negative-lane engine in miniature.
