# Zero-Knowledge User Manual

This manual is written for someone who has never used this project before.

You do not need prior context about:

- LLM benchmarking
- GGUF files
- `llama.cpp`
- the repo layout
- the earlier design conversations

If you can open a terminal and run commands, this guide is enough to get you moving.

If you want the shortest possible path first, start with:

- [operator-quickstart.md](C:/Users/User/Desktop/github_portal/cognition-mesh-test-chamber/docs/operator-quickstart.md)

## What This Project Is

`cognition-mesh-test-chamber` is a local evaluation harness for language models.

It does not try to answer:

- "Which model is best in general?"
- "Who is number one on a leaderboard?"

It tries to answer:

- "Is this specific model suitable for this specific kind of work?"
- "What goes wrong when it fails?"
- "What containment or guardrails does it need?"

The project evaluates a specific mesh:

```text
model + host constraints + task pack = suitability profile
```

The output is a set of artifacts, especially:

- a cognitive fingerprint
- a Markdown report
- failure logs
- negative lane suggestions

## What You Can Do Here

You can use this repo in four main ways:

1. Run the deterministic mock harness.
2. Run the harness against a local real model endpoint.
3. Generate optional assistant reviews for completed runs.
4. Benchmark assistant/evaluator profiles against fixed review targets.

## What You Do Not Need To Worry About

By default, this project does not require:

- cloud accounts
- external APIs
- internet access for core use
- autonomous agent permissions
- real tool access inside the evaluated host

The deterministic mock path works without a live model.

## License

This repository is licensed under the GNU Affero General Public License v3.0.

See [LICENSE](C:/Users/User/Desktop/github_portal/cognition-mesh-test-chamber/LICENSE).

## Big Picture Workflow

The normal flow is:

1. Choose a model-under-test.
2. Choose a host profile.
3. Choose a task pack.
4. Run the harness.
5. Read the report and fingerprint.
6. Optionally generate assistant commentary.
7. Optionally compare evaluator profiles with the benchmark suite.

## Repo Map

These are the folders most people need:

- `src/cm_test_chamber/`
  Core Python implementation.
- `configs/`
  Model configs, host configs, task packs, and catalogs.
- `probes/`
  Fixed probe definitions used by the harness.
- `runs/`
  Run outputs and generated evaluation artifacts.
- `reports/`
  Copies of human-readable Markdown reports.
- `docs/`
  Explanatory documentation.
- `runtime/`
  Local `llama.cpp` runtime files if you are using local GGUFs.
- `model_under_test/`
  GGUFs for the model being fingerprinted.
- `assistant_models/`
  GGUFs for optional post-run assistant/evaluator profiles.
- `scripts/`
  Helper scripts to start the dashboard or local servers.

## Key Terms

`Model under test`

The model being judged by the harness.

`Assistant`

An optional second model used after the run to comment on results.
It is never the source of truth.

`Host profile`

A description of the execution environment and constraints, such as:

- schema lock
- tool access
- network access
- filesystem mode

`Task pack`

A set of probes grouped into a fixed evaluation run.

`Probe`

A single test prompt plus evaluation rules.

`Cognitive fingerprint`

A structured summary of what the model seems suitable for, weak at, and likely to fail on in this exact mesh.

`Negative lane`

A concrete guardrail suggestion generated from observed failures.

`Assistant review`

Optional post-run commentary written by an assistant profile after the official run is complete.

`Evaluator benchmark`

A fixed suite of targets used to judge how well assistant profiles perform the evaluator role itself.

## First-Time Setup

### 1. Install Python dependencies

From the repo root:

```powershell
python -m pip install -r requirements.txt
```

### 2. Sanity-check the install

Run the test suite:

```powershell
pytest
```

If tests pass, the Python side is wired correctly.

## Fastest Safe First Run

If you are new, start with the deterministic mock harness.

Run:

```powershell
python -m cm_test_chamber.cli run `
  --model configs/models/mock_model.json `
  --host configs/hosts/schema_locked_no_tools.json `
  --task-pack configs/task_profiles/mvp_probe_pack.json `
  --out runs/demo_mock
```

When it finishes, inspect:

- `runs/demo_mock/report.md`
- `runs/demo_mock/cognitive_fingerprint.json`
- `runs/demo_mock/failure_log.jsonl`
- `runs/demo_mock/negative_lane_suggestions.json`

This is the best way to learn the system without involving a real model.

## How To Read The Output

### The report

The Markdown report is the easiest first read.

It tells you:

- deployment class
- task fit
- strengths
- weaknesses
- failure families
- negative lanes
- probe-by-probe findings

### The fingerprint

The fingerprint is the structured JSON version of the evaluation summary.

Use it if you want something machine-readable or easier to compare later.

### The failure log

The failure log gives you the probe failures and the mapped failure families.

Use it when you want to understand exactly what went wrong.

### The negative lanes

These are actionable containment suggestions derived from observed failures.

Use them when you want to turn evidence into rules.

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
- the assistant is optional post-run commentary only

Do not treat the assistant as authoritative scoring.

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

## Running a Real Local Model

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

### Run the harness

```powershell
python -m cm_test_chamber.cli run `
  --model configs/models/local_qwen3_8b_vulkan.json `
  --host configs/hosts/schema_locked_no_tools.json `
  --task-pack configs/task_profiles/mvp_probe_pack.json `
  --out runs/qwen3_local_first_pass
```

### Important expectation

A real local run is an experiment, not proof of broad quality.

Do not generalize a single run to:

- all prompts
- all host setups
- all Qwen variants
- all deployment contexts

## Generating an Assistant Review

Assistant reviews are optional commentary written after the main run is complete.

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

### What this writes

Compatibility surface:

- `runs/<run>/assistant_review.md`
- `runs/<run>/assistant_review_raw.txt`
- `runs/<run>/assistant_review_telemetry.json`
- `runs/<run>/assistant_evaluator_fitness.json`

Assistant-specific surface:

- `runs/<run>/assistant_reviews/<assistant_id>/assistant_review.md`
- `runs/<run>/assistant_reviews/<assistant_id>/assistant_review_raw.txt`
- `runs/<run>/assistant_reviews/<assistant_id>/assistant_review_telemetry.json`
- `runs/<run>/assistant_reviews/<assistant_id>/assistant_evaluator_fitness.json`

Possible failure artifact:

- `runs/<run>/assistant_review_validation_failure.json`
- or the assistant-specific equivalent inside `assistant_reviews/<assistant_id>/`

### What the telemetry means

Telemetry records things like:

- how many attempts were needed
- whether salvage was required
- whether leading prose had to be stripped
- whether trailing noise appeared
- whether final validation passed

### What the evaluator fitness score means

The evaluator fitness artifact turns the review telemetry into a normalized score.

It rolls up:

- validation success
- retry burden
- salvage burden
- leading and trailing noise
- section compliance
- planning-style leakage

This is useful when comparing assistant profiles for evaluator work.

## Running the Evaluator Benchmark

The evaluator benchmark measures how good assistant profiles are at being evaluators.

This is separate from fingerprinting the model under test.

### Materialize the fixed benchmark targets

```powershell
python -m cm_test_chamber.cli evaluator-benchmark --materialize-only
```

This writes deterministic run folders under `runs/` for benchmark review targets.

### Run the full benchmark

```powershell
python -m cm_test_chamber.cli evaluator-benchmark `
  --assistant-id qwen3-8b-abliterated-q8_0-assistant `
  --assistant-id qwen3-8b-abliterated-q8_0-assistant-alt
```

### Main benchmark artifact

- `runs/evaluator_benchmark_suite_summary.json`

This tells you:

- which benchmark targets each assistant passed
- which ones it failed
- average benchmark score
- average evaluator fitness score
- per-target rationale

### How to interpret benchmark results

The benchmark is not telling you which model is best at everything.

It is telling you which assistant profile is currently better at:

- evidence binding
- role discipline
- quoted hostile text handling
- readiness overclaim control

## Using the Dashboard

The dashboard is a convenience layer over the same CLI and artifacts.

Start it with:

```powershell
.\scripts\start_dashboard.ps1
```

Or:

```powershell
python -m cm_test_chamber.cli dashboard --host 127.0.0.1 --port 8765
```

It auto-opens by default.

### What the dashboard can do

- list configs and runs
- launch runs
- run preflight
- generate assistant reviews
- inspect run detail
- compare two runs
- compare two assistant profiles within one run
- show evaluator fitness history

### What the dashboard should not be used for

It is not the source of truth.

The source of truth remains:

- run artifacts
- report files
- fingerprints
- failure logs
- deterministic evaluator outputs

## Recommended Learning Order

If you are brand new, use this order:

1. Run `pytest`
2. Run `demo_mock`
3. Read `report.md`
4. Open the dashboard
5. Run `mock_good`, `mock_mixed`, and `mock_bad`
6. Compare those runs
7. Start a local real-model run
8. Add assistant reviews
9. Run the evaluator benchmark

This gives you the safest ramp from simple to advanced.

## Common Tasks

### I just want to see if the repo works

Run:

```powershell
pytest
python -m cm_test_chamber.cli run `
  --model configs/models/mock_model.json `
  --host configs/hosts/schema_locked_no_tools.json `
  --task-pack configs/task_profiles/mvp_probe_pack.json `
  --out runs/demo_mock
```

### I want a browser UI

Run:

```powershell
.\scripts\start_dashboard.ps1
```

### I want to test a local GGUF

1. Start the model server on port `8080`
2. Run preflight
3. Run the harness

### I want to compare assistant evaluator profiles

1. Start the assistant server on port `8081`
2. Generate assistant reviews for the same run with different assistant ids
3. Compare them in the dashboard or via the persisted artifacts

### I want to evaluate the evaluator

Run the benchmark suite:

```powershell
python -m cm_test_chamber.cli evaluator-benchmark `
  --assistant-id qwen3-8b-abliterated-q8_0-assistant `
  --assistant-id qwen3-8b-abliterated-q8_0-assistant-alt
```

## Troubleshooting

### `pytest` fails

Start with the first failing test, not all possible fixes at once.

Common causes:

- dependencies missing
- edited config mismatch
- stale generated benchmark folders

### Run preflight says endpoint is unreachable

Check:

- the server process is actually running
- the port matches the config
- Windows is not blocking the process
- you started the correct server for the correct role

Expected ports in this repo:

- model under test: `8080`
- assistant: `8081`

### Assistant review fails validation

Look at:

- `assistant_review_validation_failure.json`
- `assistant_review_raw.txt`
- `assistant_review_telemetry.json`

These usually show:

- planning leakage
- wrong section structure
- forbidden phrase echoes
- missing evidence anchors

### Benchmark results disappear

The benchmark tests intentionally clean up generated benchmark folders during test runs.

If you want the benchmark artifacts present on disk right now, regenerate them:

```powershell
python -m cm_test_chamber.cli evaluator-benchmark `
  --assistant-id qwen3-8b-abliterated-q8_0-assistant `
  --assistant-id qwen3-8b-abliterated-q8_0-assistant-alt
```

### Assistant server will not start

Check:

- `runtime/llama-server.exe` exists
- the assistant model file exists
- another process is not already using `8081`
- the GPU/runtime stack is healthy

You can inspect:

- `runs/assistant_server_stdout.log`
- `runs/assistant_server_stderr.log`

### Real model run is too slow

Possible causes:

- VRAM pressure
- too much prompt cache buildup
- too much GPU offload for the current hardware
- model too large for the current machine

## Ground Rules For Interpreting Results

Keep these in mind:

1. A result is always tied to a specific mesh.
2. Assistant commentary is not authoritative scoring.
3. A benchmark pass does not mean broad model excellence.
4. A failure is useful evidence, not project damage.
5. This repo is for suitability mapping and containment, not vanity ranking.

## If You Only Remember Three Things

1. Start with the mock path before touching the real-model path.
2. Read `report.md` and `cognitive_fingerprint.json` first; everything else is secondary.
3. Treat assistant reviews and evaluator benchmarks as optional interpretation layers, not ground truth.
