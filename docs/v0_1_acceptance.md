# v0.1 Acceptance

The build is accepted when:

1. `python -m cm_test_chamber.cli run ...` works with the mock model config.
2. The run creates all required output files.
3. Mock `good` mode produces mostly passing probe results.
4. Mock `mixed` mode produces at least two failures.
5. Mock `bad` mode produces multiple failures and negative lane suggestions.
6. The fake repo patch probe detects invented file paths.
7. The prompt injection probe detects following malicious file-contained instructions.
8. The hallucination bait probe detects unsupported fabricated claims.
9. The report includes deployment class, strengths, weaknesses, failures, containment, and negative lanes.
10. Tests pass with `pytest`.
11. No test requires a live LLM.
12. No test requires internet access.
13. No code modifies files outside the sandbox or run output directories.
14. The README contains clear run instructions.
15. The docs explain philosophy, fingerprints, negative lanes, sandbox model, and task shapes.
