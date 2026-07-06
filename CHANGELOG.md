# Changelog

## v0.2.0 - 2026-07-07

Negative-lane engine release.

Included in this release:

- retained `v0.1` baseline `run` lane for deterministic probe-pack comparison
- added `gauntlet-run` as the new dense multi-turn stress lane
- added gauntlet scoring, failure-family classification, and retry-policy support
- added historical gauntlet atlas aggregation and terminal inspection with `gauntlet-atlas`
- added operator decision tracking for recurring failure families
- added probe forge draft generation from justified gauntlet signal
- added materialized draft probe blueprints and draft payload validation
- extended the dashboard with gauntlet launch, atlas visibility, operator decisions, and draft-probe surfaces
- kept assistant-review separate from deterministic truth while preserving evaluator-fit benchmarking
- rewrote the documentation set around the two-lane model and the negative-lane entropy-folding workflow
- added [docs/v0_2_acceptance.md](C:/Users/User/Desktop/github_portal/cognition-mesh-test-chamber/docs/v0_2_acceptance.md) and updated the release checklist for the new release shape

## v0.1.0 - 2026-07-06

Initial release of `cognition-mesh-test-chamber`.

Included in this release:

- fixed seven-probe harness for contained suitability evaluation
- deterministic mock adapter for CI and local validation
- cognitive fingerprint, failure log, negative lane, and Markdown report outputs
- model and assistant catalogs
- preflight checks for run and assistant-review flows
- local dashboard with auto-open startup
- run detail and side-by-side compare views
- assistant-review generation and within-run assistant comparison
- evaluator-fit summaries and cross-run assistant fit index
- beginner-friendly operator quickstart and zero-knowledge manual
- AGPLv3 licensing
