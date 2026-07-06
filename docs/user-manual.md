# Zero-Knowledge User Manual

This manual is for someone who has never touched this repo before.

You do not need prior context about:

- LLM benchmarking
- GGUF files
- `llama.cpp`
- the earlier design discussions
- why the project changed direction

If you can open a terminal and run commands, this guide is enough to get you moving.

If you want the shortest path first, start here:

- [operator-quickstart.md](C:/Users/User/Desktop/github_portal/cognition-mesh-test-chamber/docs/operator-quickstart.md)

If you want the big-picture doctrine, read this too:

- [negative-lane-engine.md](C:/Users/User/Desktop/github_portal/cognition-mesh-test-chamber/docs/negative-lane-engine.md)

## What This Project Is

`cognition-mesh-test-chamber` is a local suitability engine for language models.

It is designed to answer:

- is this specific model suitable for this specific kind of work?
- what breaks when it is pressured?
- which failures repeat?
- what containment should the host enforce?
- does the evidence justify a new probe?

It is not designed to answer:

- which model is best in general?
- who wins a public leaderboard?

## The Current Direction

This repo started with a fixed probe-pack harness.

That baseline still exists and still matters.

But the newer direction is a negative-lane constraints engine:

- run a dense stress lane
- surface failures loudly
- classify them into families
- track historical variance
- only create more probes when the signal justifies it

That keeps the project from becoming an endless pile of hand-authored positive cases.

## The Two Evaluation Lanes

### 1. Baseline lane

Command: `run`

Use this when you want:

- a stable deterministic path
- the original fixed seven-probe pack
- straightforward regression comparison
- the safest first run for a new operator

### 2. Gauntlet lane

Command: `gauntlet-run`

Use this when you want:

- a denser multi-turn stress test
- broader failure-family discovery
- historical atlas tracking
- operator decisions about whether signal deserves more probing

This is the newer strategic lane.

## Big Picture Workflow

The overall workflow now looks like this:

1. Choose the model under test.
2. Choose a host profile.
3. Run the baseline lane or gauntlet lane.
4. Read the official artifacts.
5. For gauntlet runs, inspect the historical atlas.
6. Decide whether a failure family is noise, monitor-only, or probe-worthy.
7. Let the forge create draft probes only when the evidence supports it.
8. Optionally run assistant-role and evaluator-fit experiments.

## Repo Map

These are the folders most people need:

- `src/cm_test_chamber/`
  Core Python implementation.
- `configs/`
  Model configs, host configs, task packs, catalogs, and gauntlets.
- `probes/`
  Fixed baseline probes.
- `local_probes/`
  Materialized local draft probe blueprints.
- `runs/`
  Run outputs, atlas indices, and decision artifacts.
- `reports/`
  Copies of human-readable Markdown reports.
- `docs/`
  Explanatory documentation.
- `runtime/`
  Local `llama.cpp` runtime files if you are using local GGUFs.
- `model_under_test/`
  GGUFs for the model being judged.
- `assistant_models/`
  GGUFs for optional assistant-role models.
- `scripts/`
  Helper scripts for dashboard and local server startup.

## Key Terms

`Model under test`

The model being judged by the harness.

`Assistant`

An optional second model used for post-run commentary or evaluator-role benchmarking. It is never the source of truth.

`Host profile`

A description of the execution environment and constraints, such as schema locking, tool access, network rules, or filesystem mode.

`Task pack`

The fixed set of baseline probes used by the original `run` lane.

`Gauntlet`

A dense multi-turn stress script used by the newer `gauntlet-run` lane.

`Failure family`

A recurring class of breakage, such as hierarchy drift or fabricated evidence.

`Cognitive fingerprint`

A structured summary of what the model appears suitable for, weak at, and likely to fail on in this exact mesh.

`Negative lane`

A concrete guardrail suggestion generated from observed failures.

`Gauntlet atlas`

The historical summary of gauntlet runs grouped by model and failure family.

`Operator decision`

A judgment attached to a failure family, such as `monitor_only`, `probe_candidate`, `probe_needed`, `confirmed_for_forge`, or `dismissed`.

`Probe forge draft`

A draft probe blueprint generated from recurring signal rather than from one-off intuition.

`Assistant review`

Optional post-run commentary written after the official run is complete.

`Evaluator benchmark`

A fixed suite used to judge how well assistant profiles perform the evaluator role itself.

## First-Time Setup

### 1. Install Python dependencies

```powershell
python -m pip install -r requirements.txt
```

### 2. Run the test suite

```powershell
pytest
```

If tests pass, the local Python side is ready.

## First Safe Run: Baseline Lane

If you are new, start here.

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

This is the easiest way to learn the artifact model.

## Second Safe Run: Gauntlet Lane

Once the baseline lane makes sense, run the newer stress lane.

```powershell
python -m cm_test_chamber.cli gauntlet-run `
  --model configs/models/mock_model.json `
  --host configs/hosts/schema_locked_no_tools.json `
  --gauntlet configs/gauntlets/mvp_general_gauntlet.json `
  --out runs/demo_gauntlet `
  --retry-policy auto
```

Then inspect the atlas:

```powershell
python -m cm_test_chamber.cli gauntlet-atlas
```

You can also filter the atlas:

```powershell
python -m cm_test_chamber.cli gauntlet-atlas --family instruction_hierarchy_break
python -m cm_test_chamber.cli gauntlet-atlas --model mock-model
```

## How To Read The Outputs

### Baseline artifacts

The baseline lane gives you:

- `report.md`
- `cognitive_fingerprint.json`
- `failure_log.jsonl`
- `negative_lane_suggestions.json`

Use the report first, then the fingerprint, then the failure log.

### Gauntlet artifacts

The gauntlet lane gives you:

- gauntlet turn-by-turn result artifacts
- classified failure-family summaries
- atlas history entries
- probe-request signals for operator review

Think of the gauntlet as discovery pressure rather than a replacement for the baseline report.

### Negative lanes

Negative lanes are evidence-based containment suggestions.

They turn observed failures into reusable host rules instead of vague safety language.

### Atlas summaries

Atlas summaries tell you whether failure families recur across models or across repeated runs of the same model.

That helps you decide whether a failure was random noise or a real pattern.

## Listing Available Models

There are two catalogs:

- `model_under_test`
- `assistant`

List them with:

```powershell
python -m cm_test_chamber.cli catalog --role model_under_test
python -m cm_test_chamber.cli catalog --role assistant
```

Important rule:

- the model under test is what gets judged
- the assistant is optional support only

Do not treat the assistant as authoritative scoring.

## Draft Probes And The Forge

The system can turn recurring gauntlet signal into draft probes.

That does not mean every failure becomes a permanent probe.

The point is to keep suite growth selective.

List draft probes:

```powershell
python -m cm_test_chamber.cli draft-probes
```

Materialize draft probe blueprints:

```powershell
python -m cm_test_chamber.cli draft-probes --materialize
```

Inspect a specific draft:

```powershell
python -m cm_test_chamber.cli draft-probes --draft-id your-draft-id
```

## Preflight Checks

Preflight is a quick way to catch obvious setup problems before you commit to a run.

### Run preflight

```powershell
python -m cm_test_chamber.cli preflight `
  --mode run `
  --model configs/models/local_qwen3_8b_vulkan.json `
  --check-endpoint
```

### Assistant review preflight

```powershell
python -m cm_test_chamber.cli preflight `
  --mode assistant-review `
  --run-dir runs/qwen3_local_first_pass `
  --model-id qwen3-8b-abliterated-q8_0-assistant `
  --check-endpoint
```

### Catalog entry preflight

```powershell
python -m cm_test_chamber.cli preflight `
  --mode catalog-model `
  --role model_under_test `
  --model-id qwen3-8b-abliterated-q8_0-mut
```

Preflight checks things like:

- files exist
- endpoints are reachable
- run artifacts are present
- catalog ids resolve correctly

## Running A Real Local Model

Use this only after you are comfortable with the mock path.

### Start the model-under-test server

```powershell
.\runtime\llama-server.exe `
  -m .\model_under_test\Qwen3-8B-abliterated-q8_0.gguf `
  --host 127.0.0.1 `
  --port 8080 `
  -ngl 999 `
  -c 8192
```

### Optional preflight

```powershell
python -m cm_test_chamber.cli preflight `
  --mode run `
  --model configs/models/local_qwen3_8b_vulkan.json `
  --check-endpoint
```

### Run the baseline lane

```powershell
python -m cm_test_chamber.cli run `
  --model configs/models/local_qwen3_8b_vulkan.json `
  --host configs/hosts/schema_locked_no_tools.json `
  --task-pack configs/task_profiles/mvp_probe_pack.json `
  --out runs/qwen3_local_first_pass
```

### Run the gauntlet lane

```powershell
python -m cm_test_chamber.cli gauntlet-run `
  --model configs/models/local_qwen3_8b_vulkan.json `
  --host configs/hosts/schema_locked_no_tools.json `
  --gauntlet configs/gauntlets/mvp_general_gauntlet.json `
  --out runs/qwen3_local_gauntlet `
  --retry-policy auto
```

### Important expectation

A real local run is an experiment, not proof of broad quality.

Do not generalize a single run to:

- all prompts
- all host setups
- all model variants
- all deployment contexts

## Assistant Reviews

Assistant reviews are optional commentary written after the official run is complete.

They are useful for:

- extra human-readable commentary
- comparing evaluator-style assistant profiles
- collecting telemetry about cleanup burden, retries, and format drift

They are not the source of truth.

### Start the assistant server

```powershell
.\scripts\start_assistant_server.ps1
```

If that does not work, make sure:

- `runtime/llama-server.exe` exists
- the assistant GGUF exists in `assistant_models/`
- port `8081` is free

### Run assistant preflight

```powershell
python -m cm_test_chamber.cli preflight `
  --mode assistant-review `
  --run-dir runs/qwen3_local_first_pass `
  --model-id qwen3-8b-abliterated-q8_0-assistant `
  --check-endpoint
```

### Generate the review

```powershell
python -m cm_test_chamber.cli assistant-review `
  --run runs/qwen3_local_first_pass `
  --assistant-id qwen3-8b-abliterated-q8_0-assistant
```

## Evaluator Benchmark

This suite is for judging how suitable assistant models are for evaluator-style work.

That matters because assistant-role telemetry can become signal in its own right.

Materialize the deterministic benchmark runs:

```powershell
python -m cm_test_chamber.cli evaluator-benchmark --materialize-only
```

Run the benchmark for a specific assistant:

```powershell
python -m cm_test_chamber.cli evaluator-benchmark `
  --assistant-id qwen3-8b-abliterated-q8_0-assistant
```

## Dashboard

Start the dashboard:

```powershell
python scripts/start_dashboard.py
```

It auto-opens by default.

Use it to:

- launch mock baseline runs
- launch gauntlet runs
- inspect run artifacts
- compare runs
- inspect gauntlet atlas summaries
- review operator decisions
- inspect draft probe state
- inspect assistant-review telemetry
- inspect evaluator-fit history

## Recommended First Learning Order

If you want the smoothest introduction, do this:

1. Run `pytest`.
2. Run the baseline mock lane.
3. Read the report and fingerprint.
4. Run the gauntlet mock lane.
5. Inspect `gauntlet-atlas`.
6. Open the dashboard.
7. Only then move on to a real local model.

## License

This repository is licensed under the GNU Affero General Public License v3.0.

See [LICENSE](C:/Users/User/Desktop/github_portal/cognition-mesh-test-chamber/LICENSE).
