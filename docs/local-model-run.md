# Local Model Run

This repo has a separate local-experiment path for the bundled `llama.cpp` runtime and the staged GGUFs.

The important boundary is:

- tests still use the deterministic mock adapter
- real local runs are opt-in experiments
- no acceptance criteria depend on a live model

## Staged assets

- Runtime: `runtime/`
- Model under test: `model_under_test/Qwen3-8B-abliterated-q8_0.gguf`
- Assistant model lane: `assistant_models/Qwen3-8B-abliterated-q8_0.gguf`
- Local model config: `configs/models/local_qwen3_8b_vulkan.json`

## Start a local server

From the repo root:

```powershell
.\runtime\llama-server.exe `
  -m .\model_under_test\Qwen3-8B-abliterated-q8_0.gguf `
  --host 127.0.0.1 `
  --port 8080 `
  -ngl 999 `
  -c 8192
```

Notes:

- `-ngl 999` is the usual "offload as much as possible" setting for GPU-backed `llama.cpp` runs.
- If Vulkan or VRAM becomes a problem, reduce the offload or remove that flag for CPU testing.

## Optional preflight before the run

```powershell
python -m cm_test_chamber.cli preflight `
  --mode run `
  --model configs/models/local_qwen3_8b_vulkan.json `
  --check-endpoint
```

## Run the baseline lane against the local server

```powershell
python -m cm_test_chamber.cli run `
  --model configs/models/local_qwen3_8b_vulkan.json `
  --host configs/hosts/schema_locked_no_tools.json `
  --task-pack configs/task_profiles/mvp_probe_pack.json `
  --out runs/qwen3_local_first_pass
```

## Run the gauntlet lane against the local server

```powershell
python -m cm_test_chamber.cli gauntlet-run `
  --model configs/models/local_qwen3_8b_vulkan.json `
  --host configs/hosts/schema_locked_no_tools.json `
  --gauntlet configs/gauntlets/mvp_general_gauntlet.json `
  --out runs/qwen3_local_gauntlet `
  --retry-policy auto
```

## What to expect

The first real run is an experiment, not a victory lap.

What we want from it:

- the chosen lane should complete end-to-end
- results should be tied to this exact local host/model mesh
- failures should remain visible
- negative lane suggestions should be generated when failures justify them
- gauntlet failures should fold into atlas history instead of immediately bloating the suite

What we should not do:

- generalise the result to all Qwen variants
- claim broad suitability from one run
- let the real-model lane change the deterministic mock CI path
- blur the assistant role and the model-under-test role

## After a gauntlet run

Inspect the atlas summary:

```powershell
python -m cm_test_chamber.cli gauntlet-atlas
```

Inspect or materialize draft probes if the run produced justified probe-request signal:

```powershell
python -m cm_test_chamber.cli draft-probes
python -m cm_test_chamber.cli draft-probes --materialize
```

## Optional assistant review

Start the assistant server:

```powershell
.\scripts\start_assistant_server.ps1
```

Then review a finished run:

```powershell
python -m cm_test_chamber.cli preflight `
  --mode assistant-review `
  --run-dir runs/qwen3_local_first_pass `
  --model-id qwen3-8b-abliterated-q8_0-assistant `
  --check-endpoint
```

```powershell
python -m cm_test_chamber.cli assistant-review `
  --run runs/qwen3_local_first_pass `
  --assistant-id qwen3-8b-abliterated-q8_0-assistant
```

This writes:

- `runs/qwen3_local_first_pass/assistant_review.md` (compatibility latest-review surface)
- `runs/qwen3_local_first_pass/assistant_review_raw.txt` (compatibility latest-review surface)
- `runs/qwen3_local_first_pass/assistant_review_telemetry.json` (compatibility latest-review surface)
- `runs/qwen3_local_first_pass/assistant_evaluator_fitness.json` (compatibility latest-review surface)
- `runs/qwen3_local_first_pass/assistant_reviews/<assistant_id>/assistant_review.md`
- `runs/qwen3_local_first_pass/assistant_reviews/<assistant_id>/assistant_review_raw.txt`
- `runs/qwen3_local_first_pass/assistant_reviews/<assistant_id>/assistant_review_telemetry.json`
- `runs/qwen3_local_first_pass/assistant_reviews/<assistant_id>/assistant_evaluator_fitness.json`

If the assistant returns planning text or misses the required Markdown sections, the review now fails validation and writes:

- `runs/qwen3_local_first_pass/assistant_review_validation_failure.json`

The telemetry file is useful signal in its own right for evaluator-role analysis. It records:

- how many attempts were needed
- whether leading prose had to be stripped
- whether trailing noise appeared
- whether validation passed cleanly or only after salvage

The evaluator fitness artifact turns that telemetry into a normalized score and suitability label using:

- validation success
- retry count
- salvage burden
- leading/trailing noise
- section compliance issues

That means a single run can now accumulate multiple assistant-evaluator passes side by side.
