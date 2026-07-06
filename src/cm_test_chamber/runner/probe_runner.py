from __future__ import annotations

import json
import shutil
import time
from dataclasses import asdict
from pathlib import Path

from ..adapters import LocalHttpAdapter, MockModelAdapter
from ..evaluators import evaluate_patch, evaluate_schema, evaluate_text, map_failures
from ..fingerprint import build_fingerprint
from ..negative_lanes import generate_negative_lanes
from ..report_writer import build_markdown_report, write_json_file
from .result_types import ProbeResult, to_plain_data
from .run_config import (
    HostProfile,
    ModelConfig,
    ProbeSpec,
    TaskPack,
    load_probe,
    snapshot_config,
)
from ..sandbox.mock_fs import MockSandbox


class ProbeRunner:
    def __init__(
        self,
        repo_root: Path,
        model: ModelConfig,
        host: HostProfile,
        task_pack: TaskPack,
        out_dir: Path,
    ) -> None:
        self.repo_root = repo_root
        self.model = model
        self.host = host
        self.task_pack = task_pack
        self.out_dir = out_dir
        self.probes = [load_probe(repo_root / relative_path) for relative_path in task_pack.probe_paths]
        self.adapter = self._build_adapter()

    def _build_adapter(self):
        if self.model.backend == "mock":
            return MockModelAdapter(self.model)
        if self.model.backend == "local_http":
            return LocalHttpAdapter(self.model)
        raise ValueError(f"Unsupported backend: {self.model.backend}")

    def _build_prompt(self, probe: ProbeSpec, source_text: str | None = None) -> str:
        pieces = [self.model.system_prompt, "", probe.prompt]
        if source_text:
            pieces.extend(["", "Source:", source_text])
        return "\n".join(pieces)

    def _run_single_probe(self, probe: ProbeSpec) -> ProbeResult:
        start = time.perf_counter()
        sandbox = None
        source_text = probe.source_text
        manifest: set[str] = set()
        if probe.sandbox_repo:
            fixture_root = self.repo_root / "sandbox" / "fake_filesystem" / probe.sandbox_repo
            sandbox = MockSandbox.from_fixture(fixture_root)
            manifest = sandbox.manifest
            if probe.source_file:
                source_text = sandbox.resolve_checked(probe.source_file).read_text(encoding="utf-8")

        try:
            if probe.mode == "correction":
                initial_prompt = self._build_prompt(probe, source_text)
                initial = self.adapter.generate(probe, initial_prompt, {"stage": "initial"})
                corrected_prompt = self._build_prompt(probe, source_text)
                corrected_prompt = "\n".join([corrected_prompt, "", probe.correction_prompt or ""])
                response = self.adapter.generate(probe, corrected_prompt, {"stage": "corrected"})
                raw_output = {
                    "initial": initial.text,
                    "corrected": response.text,
                }
                evaluation = evaluate_text(response.text, probe)
            else:
                prompt = self._build_prompt(probe, source_text)
                response = self.adapter.generate(probe, prompt, {"stage": "single"})
                raw_output = response.text
                if probe.evaluator == "schema_eval":
                    evaluation = evaluate_schema(response.text, probe)
                elif probe.evaluator == "text_eval":
                    evaluation = evaluate_text(response.text, probe)
                elif probe.evaluator == "patch_eval":
                    evaluation = evaluate_patch(response.text, probe, manifest)
                else:
                    raise ValueError(f"Unsupported evaluator: {probe.evaluator}")

            failure_events = map_failures(probe, evaluation["issues"])
            finding = evaluation["notes"][0] if evaluation["notes"] else (
                failure_events[0].description if failure_events else "No additional finding."
            )
            duration_ms = int((time.perf_counter() - start) * 1000)
            return ProbeResult(
                probe_id=probe.probe_id,
                category=probe.category,
                status=evaluation["status"],
                raw_model_output=raw_output,
                parsed_output=evaluation["parsed_output"],
                evaluator_notes=evaluation["notes"],
                failure_events=[asdict(event) for event in failure_events],
                duration_ms=duration_ms,
                task_shape=asdict(probe.task_shape),
                main_finding=finding,
            )
        finally:
            if sandbox is not None:
                sandbox.cleanup()

    def run(self) -> dict[str, object]:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        reports_dir = self.repo_root / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)

        snapshot = snapshot_config(self.model, self.host, self.task_pack, self.probes)
        write_json_file(self.out_dir / "run_config_snapshot.json", snapshot)

        results = [self._run_single_probe(probe) for probe in self.probes]
        failures = [
            failure
            for result in results
            for failure in result.failure_events
        ]
        failure_events = [
            type("FailureProxy", (), failure)()
            for failure in failures
        ]
        suggestions = generate_negative_lanes(failure_events)
        fingerprint = build_fingerprint(
            self.model,
            self.host,
            results,
            failure_events,
            [suggestion.plain_language_rule for suggestion in suggestions],
        )

        self._write_jsonl(self.out_dir / "probe_results.jsonl", [to_plain_data(result) for result in results])
        self._write_jsonl(self.out_dir / "failure_log.jsonl", failures)
        suggestions_payload = [to_plain_data(item) for item in suggestions]
        write_json_file(self.out_dir / "negative_lane_suggestions.json", suggestions_payload)
        write_json_file(
            self.repo_root / "negative_lanes" / "generated" / f"{self.out_dir.name}.json",
            suggestions_payload,
        )
        write_json_file(self.out_dir / "cognitive_fingerprint.json", to_plain_data(fingerprint))
        report = build_markdown_report(self.model, self.host, fingerprint, results, suggestions)
        (self.out_dir / "report.md").write_text(report, encoding="utf-8")
        shutil.copyfile(self.out_dir / "report.md", reports_dir / f"{self.out_dir.name}_report.md")

        return {
            "results": results,
            "failures": failures,
            "suggestions": suggestions,
            "fingerprint": fingerprint,
        }

    @staticmethod
    def _write_jsonl(path: Path, rows: list[object]) -> None:
        with path.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row) + "\n")
