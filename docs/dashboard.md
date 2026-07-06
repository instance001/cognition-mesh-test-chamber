# Dashboard

The dashboard is a thin local control surface layered on top of the CLI and artifact model.

It is intentionally small and negative-lane-first.

It can:

- read model catalogs
- show available configs
- list run folders
- support run preflight
- support assistant-review preflight
- trigger a baseline `run`
- trigger a `gauntlet-run`
- trigger assistant review
- show in-session background job history for queued, running, completed, and failed actions
- show a read-only run detail view for fingerprint, report, failure log, gauntlet artifacts, and assistant review artifacts
- show a side-by-side compare view for two runs using recorded artifacts only
- include one-click `mock good`, `mock mixed`, and `mock bad` preset runs to quickly generate baseline comparison material
- include gauntlet atlas visibility so recurring failure families can be inspected historically
- include operator-decision controls for probe-request handling
- include probe forge and materialized draft visibility
- surface assistant-review telemetry so evaluator-role cleanup burden is visible too
- compute a per-review evaluator fitness score so cleanup burden, retries, and format compliance become a first-class signal
- support multiple assistant-review artifact sets per run so evaluator comparisons can accumulate over time
- include a direct within-run assistant compare panel for evaluator-vs-evaluator inspection
- include a cross-run assistant fit index for quick historical evaluator reliability reads

The dashboard does not replace the CLI. It is a convenience shell over the same underlying functions.

By default, it auto-opens in the system browser when started from the CLI or the helper script.

## Start it

```powershell
.\scripts\start_dashboard.ps1
```

Or:

```powershell
python -m cm_test_chamber.cli dashboard --host 127.0.0.1 --port 8765
```

Then open:

`http://127.0.0.1:8765`

If you want to suppress auto-open:

```powershell
python -m cm_test_chamber.cli dashboard --host 127.0.0.1 --port 8765 --no-open
```

## Design rule

The dashboard is allowed to orchestrate.

It is not allowed to become the source of truth.

Official evidence still lives in:

- run artifacts
- deterministic probe results
- gauntlet turn results
- failure logs
- atlas summaries
- operator decision records
- draft probe blueprints
- generated fingerprints
- generated reports

The run detail panel is a convenience reader for those artifacts. It is not a separate evaluation layer.

The compare panel is also read-only. It compares:

- run lane
- deployment class
- task fit
- failure families
- negative lane ids
- gauntlet score and classification when present
- operator review burden
- strengths and weaknesses
- whether assistant commentary exists
- whether assistant commentary needed salvage, how many attempts it took, and what leading prose had to be stripped
- assistant cleanup signals both as a current compatibility surface and grouped by assistant id

The gauntlet atlas views are there to help fold repeated signal into action rather than endlessly creating new tests.

They highlight:

- model-level aggregates
- failure-family aggregates
- operator decision state
- confirmed-for-forge items
- materialized draft probes when available

The assistant compare panel stays within one run and compares two evaluator profiles directly. It highlights:

- a fast evaluator-fit summary
- explicit evaluator fitness score and suitability label
- validation pass/fail
- attempt count
- whether salvage was needed
- stripped leading prose
- final validation issues
- full validation failure payloads when present

It also acts as a generation surface:

- shows which assistant profiles already have artifacts for the selected run
- shows which profiles are still missing
- lets you generate or regenerate assistant reviews directly from the panel
- lets you seed the left/right compare selectors from the available review set

The evaluator-fit summary uses a simple deterministic ordering:

1. higher evaluator fitness score wins
2. validation pass beats validation fail
3. fewer attempts beats more attempts
4. no salvage beats salvage

The fitness score itself is still artifact-grounded. It rolls up:

- validation pass/fail
- retry count
- salvage burden
- leading prose noise
- trailing noise
- section compliance issues
- planning-style leakage

When the assistant compare view runs, it also persists the latest within-run evaluator-fit summary to:

- `runs/<run_id>/assistant_reviews/assistant_fit_summary.json`

Those per-run summaries are also rolled into:

- `runs/assistant_fit_summary_index.json`

The index now carries normalized historical fields such as:

- winning and losing assistant ids
- evaluator fitness scores and suitability labels for both compared assistants
- validation pass/fail for both compared assistants
- attempt counts
- salvage flags
- last-updated timestamp

The dashboard also computes a simple aggregate reliability summary from that index, including:

- average evaluator fitness score
- best/worst observed evaluator fitness score
- wins
- losses
- validation failures
- salvage count
- total appearances
- suitability mix counts
- a short rationale string derived from those metrics
- a conservative readiness label

The historical assistant-fit panel can be sorted client-side by:

- average evaluator fitness score
- wins
- validation failures
- salvage count
- appearances

Current readiness labels are intentionally simple:

- `insufficient data`
- `needs containment`
- `unstable`
- `promising but early`
- `mixed signal`

## Quick compare fuel

The dashboard includes one-click mock preset buttons:

- `Mock Good`
- `Mock Mixed`
- `Mock Bad`

These write predictable run folders:

- `runs/mock_good`
- `runs/mock_mixed`
- `runs/mock_bad`

That makes it easy to bootstrap the compare view before a real local model run is available.

For the broader system story, also read:

- [negative-lane-engine.md](C:/Users/User/Desktop/github_portal/cognition-mesh-test-chamber/docs/negative-lane-engine.md)
