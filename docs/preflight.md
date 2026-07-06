# Preflight

Preflight checks help catch obvious local setup problems before a run or assistant review starts.

Current checks include:

- model config exists
- backend is recognized
- optional endpoint reachability
- catalog entry exists
- referenced GGUF file exists
- run folder exists
- required run artifacts exist

## Run preflight

```powershell
python -m cm_test_chamber.cli preflight `
  --mode run `
  --model configs/models/local_qwen3_8b_vulkan.json `
  --check-endpoint
```

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
