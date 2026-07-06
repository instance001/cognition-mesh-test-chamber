# v0.2 Acceptance

The build is accepted when:

1. `python -m cm_test_chamber.cli gauntlet-run ...` works with the mock model config.
2. The gauntlet run creates the expected run folder and core gauntlet artifacts.
3. The original `python -m cm_test_chamber.cli run ...` baseline lane still works with the mock model config.
4. The baseline lane still creates the expected `report.md`, `cognitive_fingerprint.json`, `failure_log.jsonl`, and `negative_lane_suggestions.json` artifacts.
5. The gauntlet lane classifies failures into families instead of only emitting raw turn output.
6. The gauntlet lane persists history that can be read through `python -m cm_test_chamber.cli gauntlet-atlas`.
7. `python -m cm_test_chamber.cli gauntlet-atlas` returns a usable summary with indexed runs, tracked failure families, and tracked models.
8. Operator decisions can be persisted for recurring failure families without modifying the deterministic baseline truth surface.
9. The probe forge can rebuild draft state from historical gauntlet signal.
10. `python -m cm_test_chamber.cli draft-probes` lists materialized draft probes or cleanly reports that none exist.
11. `python -m cm_test_chamber.cli draft-probes --materialize` completes cleanly and writes valid blueprint-style draft probe payloads when draft candidates exist.
12. Draft probe payload validation catches malformed draft structures cleanly.
13. The dashboard starts successfully and exposes the negative-lane workflow surfaces: gauntlet launch, atlas visibility, operator decisions, and draft-probe visibility.
14. Assistant-review remains optional and separate from authoritative harness truth.
15. Evaluator benchmark artifacts still work so assistant-role suitability can be inspected without collapsing into a leaderboard.
16. Tests pass with `pytest`.
17. No test requires a live LLM.
18. No test requires internet access.
19. No code writes outside intended local output and operator-controlled asset areas.
20. The README and core docs explain the two-lane model, the gauntlet atlas flow, and the probe forge flow clearly enough for a zero-knowledge operator.
