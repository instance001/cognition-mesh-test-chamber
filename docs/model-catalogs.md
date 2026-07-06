# Model Catalogs

This repo keeps two distinct model roles:

- `model_under_test`
  The engine being fingerprinted by the baseline or gauntlet lane.
- `assistant`
  An optional helper used later for operator-side review, comparison, or commentary.

Those roles should stay separate.

Why:

- the model under test generates the behavior being judged
- the assistant may help interpret results later
- deterministic evaluators still own the authoritative pass/fail surface

## Catalog files

- `configs/catalogs/models_under_test.json`
- `configs/catalogs/assistant_models.json`

Each catalog entry is meant to be friendly to both CLI and future GUI use. It carries:

- a stable `id`
- a human-facing `label`
- model family and quantization
- the GGUF `file_path`
- the intended runtime
- a recommended local endpoint
- notes

## Current intended flow

1. Pick a model-under-test entry.
2. Start a local server for that model.
3. Run the baseline lane or gauntlet lane against that endpoint.
4. Optionally pick an assistant entry later for post-run interpretation.

The assistant should never replace deterministic evaluator truth. It can help explain, compare, cluster, or summarize results, but the harness evidence remains the ground truth.

## Assistant review lane

The repo also supports an optional assistant commentary step after a run is complete.

Flow:

1. Complete a baseline or gauntlet run.
2. Start an assistant model server from `assistant_models/`.
3. Run `assistant-review` against the finished run folder.
4. Read `assistant_review.md` as commentary, not as authoritative scoring.

## Why Separate Catalogs Matter

This separation helps preserve the project doctrine:

- the model under test creates the behavior being judged
- the assistant creates optional secondary interpretation
- evaluator telemetry can be useful signal, but it is still not primary truth
