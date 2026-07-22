# Cognition Mesh Test Chamber

`cognition-mesh-test-chamber` is a local negative-lane constraints engine for LLM suitability work.

It fingerprints how a model behaves inside a specific host and task mesh, then folds failure signal into reusable constraints instead of endlessly expanding hand-authored positive cases.

Thesis:

> Cognition should be fingerprinted, not ranked. Failures should collapse into containment, not explode into benchmark sprawl.

## What This Is

This project is not a public leaderboard.

It is also not a giant benchmark museum that grows forever through positive-lane additions.

It maps a specific mesh:

```text
engine shape + host constraints + task shape + observed failures = suitability profile
```

The output is evidence tied to:

- a model under test
- a host profile
- a fixed probe pack or gauntlet
- observed failure families
- generated negative lanes
- operator decisions about what deserves more scrutiny

## Release Shape

The repo now has two evaluation lanes:

- `v0.1 baseline lane`
  The original fixed seven-probe pack, kept for deterministic comparison and regression checks.
- `v0.2 gauntlet lane`
  A dense multi-turn stress test that surfaces broad failure signal, classifies it, tracks variance over time, and only recommends new probes when the evidence justifies it.

The gauntlet lane is the current strategic direction.

The fixed probe pack still matters because it gives us a stable baseline and a safe deterministic path for CI and local validation.

## Core Doctrine

- no general-purpose winner claims
- no benchmark sprawl by default
- no assistant model replacing deterministic truth
- no autonomous tool chaos
- no cloud dependency for core local use; hosted/model-provider comparisons can be treated as explicit future lanes rather than hidden defaults

The intended questions are:

- is this model suitable for this exact task shape?
- where does it break under constraint?
- which failure families recur?
- what containment should the host enforce?
- does the signal justify drafting new probes?

## What The System Produces

Depending on lane and options, the system can produce:

- per-probe or per-turn result artifacts
- failure logs
- negative lane suggestions
- cognitive fingerprint JSON artifacts
- Markdown reports
- gauntlet history and variance atlas summaries
- operator probe-request decisions
- probe forge drafts
- materialized draft probe blueprints
- optional assistant-review artifacts
- evaluator-fit artifacts for assistant-role comparison

## Main Workflows

### 1. Baseline probe pack

Use this when you want the original deterministic path.

```powershell
python -m cm_test_chamber.cli run `
  --model configs/models/mock_model.json `
  --host configs/hosts/schema_locked_no_tools.json `
  --task-pack configs/task_profiles/mvp_probe_pack.json `
  --out runs/demo_mock
```

### 2. Negative-lane gauntlet

Use this when you want the newer entropy-folding lane.

```powershell
python -m cm_test_chamber.cli gauntlet-run `
  --model configs/models/mock_model.json `
  --host configs/hosts/schema_locked_no_tools.json `
  --gauntlet configs/gauntlets/mvp_general_gauntlet.json `
  --out runs/demo_gauntlet `
  --retry-policy auto
```

### 3. Inspect historical gauntlet signal

```powershell
python -m cm_test_chamber.cli gauntlet-atlas
python -m cm_test_chamber.cli gauntlet-atlas --family instruction_hierarchy_break
python -m cm_test_chamber.cli gauntlet-atlas --model mock-model
```

### 4. Inspect or materialize draft probes

```powershell
python -m cm_test_chamber.cli draft-probes
python -m cm_test_chamber.cli draft-probes --materialize
```

### 5. Optional assistant-role work

```powershell
python -m cm_test_chamber.cli assistant-review --run runs/demo_mock --assistant-id your-assistant-id
python -m cm_test_chamber.cli evaluator-benchmark --assistant-id your-assistant-id
```

## Quick Start

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

Run tests:

```powershell
pytest
```

For the shortest first-run path, use:

- [docs/operator-quickstart.md](C:/Users/User/Desktop/github_portal/cognition-mesh-test-chamber/docs/operator-quickstart.md)

If you want the full system story first, read:

- [docs/negative-lane-engine.md](C:/Users/User/Desktop/github_portal/cognition-mesh-test-chamber/docs/negative-lane-engine.md)

## Dashboard

Start the local dashboard:

```powershell
python scripts/start_dashboard.py
```

The dashboard auto-opens in the browser and provides:

- one-click mock runs
- gauntlet run launch
- run detail inspection
- side-by-side compare
- gauntlet variance atlas views
- operator decision controls
- draft probe visibility
- assistant-review inspection
- evaluator-fit history

## Reading Results

The core idea is simple:

- baseline runs tell you whether known failure surfaces are stable
- gauntlet runs tell you where broad pressure creates failure signal
- atlas summaries tell you whether those failures repeat
- operator decisions tell you whether a family should be monitored, drafted, or dismissed
- forge drafts turn justified signal into candidate probes without instantly bloating the suite

Optional assistant commentary can be useful, but it does not replace official artifacts.

Every suitability claim remains specific to the exact model, host, and evaluation lane that produced it.

## Repo Layout

The package implementation lives under `src/cm_test_chamber/`.

Important areas:

- `configs/`
- `configs/catalogs/`
- `configs/gauntlets/`
- `probes/`
- `local_probes/`
- `sandbox/fake_filesystem/sample_repo/`
- `runs/`
- `reports/`
- `runtime/`
- `model_under_test/`
- `assistant_models/`

`runtime/`, `model_under_test/`, and `assistant_models/` are for local operator assets such as binaries and GGUF files. They are not release-managed source artifacts.

## Documentation

- [docs/operator-quickstart.md](C:/Users/User/Desktop/github_portal/cognition-mesh-test-chamber/docs/operator-quickstart.md)
- [docs/user-manual.md](C:/Users/User/Desktop/github_portal/cognition-mesh-test-chamber/docs/user-manual.md)
- [docs/negative-lane-engine.md](C:/Users/User/Desktop/github_portal/cognition-mesh-test-chamber/docs/negative-lane-engine.md)
- [docs/mock-walkthrough.md](C:/Users/User/Desktop/github_portal/cognition-mesh-test-chamber/docs/mock-walkthrough.md)
- [docs/dashboard.md](C:/Users/User/Desktop/github_portal/cognition-mesh-test-chamber/docs/dashboard.md)
- [docs/preflight.md](C:/Users/User/Desktop/github_portal/cognition-mesh-test-chamber/docs/preflight.md)
- [docs/model-catalogs.md](C:/Users/User/Desktop/github_portal/cognition-mesh-test-chamber/docs/model-catalogs.md)
- [docs/local-model-run.md](C:/Users/User/Desktop/github_portal/cognition-mesh-test-chamber/docs/local-model-run.md)
- [docs/philosophy.md](C:/Users/User/Desktop/github_portal/cognition-mesh-test-chamber/docs/philosophy.md)
- [docs/cognitive-fingerprint.md](C:/Users/User/Desktop/github_portal/cognition-mesh-test-chamber/docs/cognitive-fingerprint.md)
- [docs/negative-lanes.md](C:/Users/User/Desktop/github_portal/cognition-mesh-test-chamber/docs/negative-lanes.md)
- [docs/sandbox-model.md](C:/Users/User/Desktop/github_portal/cognition-mesh-test-chamber/docs/sandbox-model.md)
- [docs/task-shapes.md](C:/Users/User/Desktop/github_portal/cognition-mesh-test-chamber/docs/task-shapes.md)
- [docs/v0_1_acceptance.md](C:/Users/User/Desktop/github_portal/cognition-mesh-test-chamber/docs/v0_1_acceptance.md)
- [CHANGELOG.md](C:/Users/User/Desktop/github_portal/cognition-mesh-test-chamber/CHANGELOG.md)
- [RELEASE_CHECKLIST.md](C:/Users/User/Desktop/github_portal/cognition-mesh-test-chamber/RELEASE_CHECKLIST.md)
- [GLOSSARY.md](GLOSSARY.md)

## License

This project is licensed under the GNU Affero General Public License v3.0.

See [LICENSE](C:/Users/User/Desktop/github_portal/cognition-mesh-test-chamber/LICENSE).
