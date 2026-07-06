# Preflight

Preflight checks help catch obvious local setup problems before a baseline run, gauntlet run, or assistant review starts.

Current checks include:

- model config exists
- backend is recognized
- optional endpoint reachability
- catalog entry exists
- referenced GGUF file exists
- run folder exists
- required run artifacts exist

Preflight is intentionally simple.

It is there to catch obvious operator mistakes before you spend time on a run, not to replace the run itself.

## Run preflight

Use this before either evaluation lane when you are pointing at a local model config.

```powershell
python -m cm_test_chamber.cli preflight `
  --mode run `
  --model configs/models/local_qwen3_8b_vulkan.json `
  --check-endpoint
```

This validates the model config used by both:

- `python -m cm_test_chamber.cli run`
- `python -m cm_test_chamber.cli gauntlet-run`

## Assistant review preflight

```powershell
python -m cm_test_chamber.cli preflight `
  --mode assistant-review `
  --run-dir runs/qwen3_local_first_pass `
  --model-id qwen3-8b-abliterated-q8_0-assistant `
  --check-endpoint
```

## Catalog entry preflight

```powershell
python -m cm_test_chamber.cli preflight `
  --mode catalog-model `
  --role model_under_test `
  --model-id qwen3-8b-abliterated-q8_0-mut
```

The command exits with a non-zero status if any required check fails, which makes it useful for future GUI status surfaces and scripted local workflows.

Recommended order:

1. preflight the model config
2. run the baseline lane or gauntlet lane
3. if you want assistant commentary, preflight the finished run folder
4. run `assistant-review`
