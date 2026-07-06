# Cognition Mesh Test Chamber

`cognition-mesh-test-chamber` is a contained suitability, containment, and cognitive fingerprinting harness for LLMs, hosts, tools, and workflows.

Thesis:

> Cognition should be fingerprinted, not ranked. Suitability emerges from the mesh between engine, host, operator, and task.

## What This Is

This project is not a benchmark suite.

It does not try to produce a global leaderboard or a vanity winner.

It maps a specific mesh:

```text
engine shape + host constraints + task shape = suitability profile
```

The outcome is a cognitive fingerprint tied to:

- a model intake
- a host profile
- a probe pack
- the observed failure lanes

## Release Status

`v0.1` is the current baseline release.

The project is intended to answer:

- is this model suitable for this exact task shape?
- what does it fail on?
- what containment does it appear to need?

## What v0.1 Does

v0.1 runs a fixed seven-probe pack against either:

- a deterministic mock adapter for CI and local validation
- a local HTTP model endpoint for later experiments

The runner produces:

- per-probe JSONL results
- failure logs
- negative lane suggestions
- a cognitive fingerprint JSON artifact
- a human-readable Markdown report
- optional assistant-review artifacts
- evaluator-fit artifacts for assistant-role comparison

## What v0.1 Does Not Do

- no leaderboards by default
- no cloud services
- no real tool access
- no autonomous agent loops
- no writes outside the mock sandbox and chosen run output directory
- no requirement for a live LLM in tests

## Core Concepts

`Cognitive fingerprint`

A contextual deployment profile showing strengths, weaknesses, failure attractors, required containment, and task fit for this exact engine/host/task mesh.

`Negative lanes`

Reusable walls generated from observed failures. They turn specific failure evidence into concrete host rules instead of vague safety slogans.

## Quick Start

Create a virtual environment if you want one, then install test dependencies:

```bash
python -m pip install -r requirements.txt
```

Run the mock demo:

```bash
python -m cm_test_chamber.cli run ^
  --model configs/models/mock_model.json ^
  --host configs/hosts/schema_locked_no_tools.json ^
  --task-pack configs/task_profiles/mvp_probe_pack.json ^
  --out runs/demo_mock
```

Run tests:

```bash
pytest
```

For the shortest first-run path, use the operator quickstart:

- [docs/operator-quickstart.md](C:/Users/User/Desktop/github_portal/cognition-mesh-test-chamber/docs/operator-quickstart.md)

List registered model entries:

```bash
python -m cm_test_chamber.cli catalog --role model_under_test
python -m cm_test_chamber.cli catalog --role assistant
```

Start the local dashboard:

```bash
python scripts/start_dashboard.py
```

The dashboard auto-opens in the browser and provides:

- one-click mock runs
- run detail inspection
- side-by-side run compare
- assistant-review inspection
- evaluator-fit history

## Reading The Report

The primary human-facing report is written to the run directory and copied into `reports/`.

Look for:

- deployment class
- best-fit and poor-fit task claims
- observed strengths
- observed failure lanes
- required containment
- probe-by-probe evidence
- generated negative lanes

Optional assistant commentary can be generated after a run, but it does not replace the official harness outputs.

Assistant-role experiments are supported too. The project can benchmark evaluator-style assistant profiles, retain cleanup telemetry, and maintain a cross-run fit index so GGUF suitability for evaluator work can be inspected historically without turning the system into a leaderboard.

Every suitability claim in the report is specific to the exact model intake, host profile, and task pack that were run.

## Repo Layout

The package implementation lives under `src/cm_test_chamber/`.

Probe specs and configs live under:

- `configs/`
- `configs/catalogs/`
- `probes/`
- `sandbox/fake_filesystem/sample_repo/`

Run outputs are written under:

- `runs/`
- `reports/`

Local operator-provided assets live under:

- `runtime/`
- `model_under_test/`
- `assistant_models/`

Those folders are intended for local binaries and GGUF weights and should not be treated as release-managed source artifacts.

## Documentation

- [docs/operator-quickstart.md](C:/Users/User/Desktop/github_portal/cognition-mesh-test-chamber/docs/operator-quickstart.md)
- [docs/user-manual.md](C:/Users/User/Desktop/github_portal/cognition-mesh-test-chamber/docs/user-manual.md)
- [CHANGELOG.md](C:/Users/User/Desktop/github_portal/cognition-mesh-test-chamber/CHANGELOG.md)
- [RELEASE_CHECKLIST.md](C:/Users/User/Desktop/github_portal/cognition-mesh-test-chamber/RELEASE_CHECKLIST.md)
- [docs/philosophy.md](C:/Users/User/Desktop/github_portal/cognition-mesh-test-chamber/docs/philosophy.md)
- [docs/cognitive-fingerprint.md](C:/Users/User/Desktop/github_portal/cognition-mesh-test-chamber/docs/cognitive-fingerprint.md)
- [docs/negative-lanes.md](C:/Users/User/Desktop/github_portal/cognition-mesh-test-chamber/docs/negative-lanes.md)
- [docs/sandbox-model.md](C:/Users/User/Desktop/github_portal/cognition-mesh-test-chamber/docs/sandbox-model.md)
- [docs/task-shapes.md](C:/Users/User/Desktop/github_portal/cognition-mesh-test-chamber/docs/task-shapes.md)
- [docs/v0_1_acceptance.md](C:/Users/User/Desktop/github_portal/cognition-mesh-test-chamber/docs/v0_1_acceptance.md)
- [docs/local-model-run.md](C:/Users/User/Desktop/github_portal/cognition-mesh-test-chamber/docs/local-model-run.md)
- [docs/model-catalogs.md](C:/Users/User/Desktop/github_portal/cognition-mesh-test-chamber/docs/model-catalogs.md)
- [docs/preflight.md](C:/Users/User/Desktop/github_portal/cognition-mesh-test-chamber/docs/preflight.md)
- [docs/dashboard.md](C:/Users/User/Desktop/github_portal/cognition-mesh-test-chamber/docs/dashboard.md)

## License

This project is licensed under the GNU Affero General Public License v3.0.

See [LICENSE](C:/Users/User/Desktop/github_portal/cognition-mesh-test-chamber/LICENSE).
