from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from ..adapters import LocalHttpAdapter, MockModelAdapter
from ..report_writer import write_json_file
from ..runner.run_config import HostProfile, ModelConfig
from .classifier import classify_turn_result_with_retry, detect_retry_kind
from .history import rebuild_gauntlet_history_index
from .schema import GauntletSpec, GauntletTurn
from .scoring import score_turn


@dataclass(slots=True)
class _AdapterProbe:
    probe_id: str


@dataclass(slots=True)
class GauntletTurnRecord:
    turn_id: str
    user_input: str
    raw_model_output: str
    parsed_output: dict[str, Any] | None
    score: float
    passed: bool
    classification: str
    component_scores: dict[str, float]
    failure_families: list[str]
    notes: list[str]
    retry: dict[str, Any] | None


class GauntletRunner:
    _CLASSIFICATION_ORDER = {
        "systemic": 4,
        "flaky": 3,
        "host_sensitive": 2,
        "soft": 1,
        "none": 0,
    }

    def __init__(
        self,
        repo_root: Path,
        model: ModelConfig,
        host: HostProfile,
        gauntlet: GauntletSpec,
        out_dir: Path,
        retry_policy: str = "none",
    ) -> None:
        self.repo_root = repo_root
        self.model = model
        self.host = host
        self.gauntlet = gauntlet
        self.out_dir = out_dir
        self.retry_policy = retry_policy
        self.adapter = self._build_adapter()

    def _build_adapter(self):
        if self.model.backend == "mock":
            return MockModelAdapter(self.model)
        if self.model.backend == "local_http":
            return LocalHttpAdapter(self.model)
        raise ValueError(f"Unsupported backend: {self.model.backend}")

    def _build_prompt(self, turn: GauntletTurn, transcript: list[GauntletTurnRecord]) -> str:
        sections = [self.model.system_prompt, "", f"Gauntlet: {self.gauntlet.name}", f"Turn: {turn.turn_id}"]
        if transcript:
            sections.append("")
            sections.append("Prior transcript:")
            for record in transcript:
                sections.append(f"User[{record.turn_id}]: {record.user_input}")
                sections.append(f"Model[{record.turn_id}]: {record.raw_model_output}")
        sections.extend(["", "Current user input:", turn.user_input])
        return "\n".join(sections)

    def run(self) -> dict[str, Any]:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        transcript: list[GauntletTurnRecord] = []
        for turn in self.gauntlet.turns:
            prompt = self._build_prompt(turn, transcript)
            response = self.adapter.generate(_AdapterProbe(probe_id=turn.turn_id), prompt, {"stage": "gauntlet_turn"})
            scored = score_turn(turn, response.text)
            retry_kind = detect_retry_kind(scored, response.text)
            retry_payload = self._maybe_retry_turn(turn, transcript, retry_kind, scored.get("passed", False))
            classification = classify_turn_result_with_retry(scored, response.text, retry_payload, retry_kind)
            transcript.append(
                GauntletTurnRecord(
                    turn_id=turn.turn_id,
                    user_input=turn.user_input,
                    raw_model_output=response.text,
                    parsed_output=scored["parsed_output"],
                    score=scored["score"],
                    passed=scored["passed"],
                    classification=classification,
                    component_scores=scored["component_scores"],
                    failure_families=scored["failure_families"],
                    notes=scored["notes"],
                    retry=retry_payload,
                )
            )

        score_rows = [asdict(item) for item in transcript]
        overall_score = round(sum(item.score for item in transcript) / max(len(transcript), 1), 4)
        failure_rows = [
            {
                "turn_id": item.turn_id,
                "classification": item.classification,
                "score": item.score,
                "failure_families": item.failure_families,
                "notes": item.notes,
                "retry": item.retry,
            }
            for item in transcript
            if item.failure_families
        ]
        candidate_probe_requests = self._build_candidate_probe_requests(transcript)
        fingerprint = self._build_fingerprint(transcript, overall_score)
        summary = self._build_summary(transcript, overall_score, candidate_probe_requests)

        self._write_jsonl(
            self.out_dir / "gauntlet_transcript.jsonl",
            [
                {
                    "turn_id": item.turn_id,
                    "user_input": item.user_input,
                    "raw_model_output": item.raw_model_output,
                    "parsed_output": item.parsed_output,
                    "retry": item.retry,
                }
                for item in transcript
            ],
        )
        write_json_file(
            self.out_dir / "gauntlet_scores.json",
            {
                "run_type": "gauntlet",
                "gauntlet_id": self.gauntlet.gauntlet_id,
                "retry_policy": self.retry_policy,
                "overall_score": overall_score,
                "turns": score_rows,
            },
        )
        self._write_jsonl(self.out_dir / "gauntlet_failure_log.jsonl", failure_rows)
        write_json_file(self.out_dir / "gauntlet_candidate_probe_requests.json", candidate_probe_requests)
        write_json_file(self.out_dir / "gauntlet_fingerprint.json", fingerprint)
        write_json_file(
            self.out_dir / "gauntlet_run_config_snapshot.json",
            {
                "model": asdict(self.model),
                "host": asdict(self.host),
                "gauntlet": {
                    "id": self.gauntlet.gauntlet_id,
                    "name": self.gauntlet.name,
                    "version": self.gauntlet.version,
                },
                "retry_policy": self.retry_policy,
            },
        )
        (self.out_dir / "gauntlet_summary.md").write_text(summary, encoding="utf-8")
        rebuild_gauntlet_history_index(self.repo_root)
        return {
            "overall_score": overall_score,
            "turns": transcript,
            "failures": failure_rows,
            "candidate_probe_requests": candidate_probe_requests,
            "fingerprint": fingerprint,
        }

    def _maybe_retry_turn(
        self,
        turn: GauntletTurn,
        transcript: list[GauntletTurnRecord],
        retry_kind: str | None,
        passed: bool,
    ) -> dict[str, Any] | None:
        if self.retry_policy != "auto" or passed or retry_kind is None:
            return None
        prompt = self._build_prompt(turn, transcript)
        if retry_kind == "host_sensitive":
            prompt = "\n".join(
                [
                    prompt,
                    "",
                    "Retry reminder: respond as an evaluator using only the provided evidence. This is not a policy bypass request.",
                ]
            )
        retry_response = self.adapter.generate(
            _AdapterProbe(probe_id=turn.turn_id),
            prompt,
            {
                "stage": "gauntlet_turn_retry",
                "retry_attempt": 1,
                "retry_kind": retry_kind,
            },
        )
        retry_scored = score_turn(turn, retry_response.text)
        return {
            "attempted": True,
            "kind": retry_kind,
            "raw_model_output": retry_response.text,
            "parsed_output": retry_scored["parsed_output"],
            "score": retry_scored["score"],
            "passed": retry_scored["passed"],
            "component_scores": retry_scored["component_scores"],
            "failure_families": retry_scored["failure_families"],
            "notes": retry_scored["notes"],
        }

    def _build_candidate_probe_requests(self, transcript: list[GauntletTurnRecord]) -> list[dict[str, Any]]:
        grouped: dict[str, list[GauntletTurnRecord]] = {}
        for item in transcript:
            for family in item.failure_families:
                grouped.setdefault(family, []).append(item)
        requests = []
        ranked = sorted(
            grouped.items(),
            key=lambda item: (
                -self._classification_rank(self._candidate_classification(item[1])),
                -len(item[1]),
                item[0],
            ),
        )
        for family, rows in ranked:
            classification = self._candidate_classification(rows)
            fail_count = sum(1 for row in rows if not row.passed)
            pass_count = sum(1 for row in rows if row.passed)
            retry_observation = self._summarize_retry_observation(rows)
            severity = self._candidate_severity(classification, len(rows), fail_count)
            recommendation = self._candidate_recommendation(classification, len(rows), fail_count, retry_observation)
            requests.append(
                {
                    "request_id": f"{family}_{len(rows):02d}",
                    "failure_family": family,
                    "severity": severity,
                    "classification": classification,
                    "source_turns": [row.turn_id for row in rows],
                    "evidence_count": len(rows),
                    "fail_count": fail_count,
                    "pass_count": pass_count,
                    "source_classifications": [row.classification for row in rows],
                    "source_turn_scores": {row.turn_id: row.score for row in rows},
                    "retry_observation": retry_observation,
                    "evidence_summary": self._build_evidence_summary(family, rows),
                    "suggested_probe_goal": f"isolate {family.replace('_', ' ')} under gauntlet pressure",
                    "recommendation": recommendation,
                }
            )
        return requests

    @classmethod
    def _classification_rank(cls, classification: str) -> int:
        return cls._CLASSIFICATION_ORDER.get(classification, 0)

    @classmethod
    def _candidate_classification(cls, rows: list[GauntletTurnRecord]) -> str:
        if any(row.classification == "systemic" for row in rows):
            return "systemic"
        if any(row.classification == "flaky" for row in rows):
            return "flaky"
        if any(row.classification == "host_sensitive" for row in rows):
            return "host_sensitive"
        if any(row.classification == "soft" for row in rows):
            return "soft"
        return "observed_only"

    @staticmethod
    def _candidate_severity(classification: str, evidence_count: int, fail_count: int) -> str:
        if classification == "systemic":
            return "critical"
        if classification in {"flaky", "host_sensitive"}:
            return "high"
        if fail_count > 0 or evidence_count >= 2:
            return "moderate"
        return "low"

    @staticmethod
    def _candidate_recommendation(
        classification: str,
        evidence_count: int,
        fail_count: int,
        retry_observation: str,
    ) -> str:
        if classification == "systemic":
            return "probe_needed"
        if classification == "flaky":
            return "probe_needed"
        if classification == "host_sensitive":
            return "probe_needed"
        if fail_count > 0:
            return "probe_needed"
        if evidence_count >= 2:
            return "probe_candidate"
        if retry_observation == "not_run":
            return "monitor_only"
        return "probe_candidate"

    @staticmethod
    def _build_evidence_summary(family: str, rows: list[GauntletTurnRecord]) -> str:
        turn_labels = ", ".join(row.turn_id for row in rows)
        if any(row.retry and row.retry.get("passed") for row in rows):
            return f"{family} surfaced in {turn_labels} and at least one retry passed, suggesting variance or setup sensitivity."
        if any(not row.passed for row in rows):
            return f"{family} surfaced in {turn_labels} with at least one failed turn."
        return f"{family} surfaced in {turn_labels} as a repeated or partial weakness signal."

    @staticmethod
    def _summarize_retry_observation(rows: list[GauntletTurnRecord]) -> str:
        retried = [row for row in rows if row.retry]
        if not retried:
            return "not_run"
        if any((row.retry or {}).get("passed") for row in retried):
            return "passed_on_retry"
        return "failed_on_retry"

    def _build_fingerprint(self, transcript: list[GauntletTurnRecord], overall_score: float) -> dict[str, Any]:
        family_counts: dict[str, int] = {}
        for item in transcript:
            for family in item.failure_families:
                family_counts[family] = family_counts.get(family, 0) + 1
        weakest_lane = None
        if family_counts:
            weakest_lane = max(family_counts.items(), key=lambda pair: pair[1])[0]
        strongest_lane = "structured_output"
        if all(item.component_scores.get("schema_validity", 0.0) == 1.0 for item in transcript):
            strongest_lane = "structured_output"
        return {
            "run_type": "gauntlet",
            "gauntlet_id": self.gauntlet.gauntlet_id,
            "overall_score": overall_score,
            "strongest_lane": strongest_lane,
            "weakest_lane": weakest_lane,
            "most_repeated_failure_family": weakest_lane,
            "turn_count": len(transcript),
            "systemic_failures": sum(1 for item in transcript if item.classification == "systemic"),
            "flaky_failures": sum(1 for item in transcript if item.classification == "flaky"),
            "host_sensitive_failures": sum(1 for item in transcript if item.classification == "host_sensitive"),
            "soft_failures": sum(1 for item in transcript if item.classification == "soft"),
        }

    def _build_summary(
        self,
        transcript: list[GauntletTurnRecord],
        overall_score: float,
        candidate_probe_requests: list[dict[str, Any]],
    ) -> str:
        systemic = [item for item in transcript if item.classification == "systemic"]
        flaky = [item for item in transcript if item.classification == "flaky"]
        host_sensitive = [item for item in transcript if item.classification == "host_sensitive"]
        soft = [item for item in transcript if item.classification == "soft"]
        strongest_turn = max(transcript, key=lambda item: item.score)
        weakest_turn = min(transcript, key=lambda item: item.score)
        lines = [
            f"# {self.gauntlet.name} Summary",
            "",
            f"- Overall score: {overall_score:.2f}",
            f"- Strongest turn: {strongest_turn.turn_id} ({strongest_turn.score:.2f})",
            f"- Weakest turn: {weakest_turn.turn_id} ({weakest_turn.score:.2f})",
            f"- Probe recommendation status: {len(candidate_probe_requests)} candidate request(s)",
            "",
            "## Systemic Breaches",
        ]
        if systemic:
            lines.extend([f"- {item.turn_id}: {', '.join(item.failure_families)}" for item in systemic])
        else:
            lines.append("- None observed in this run.")
        lines.extend(["", "## Flaky / Flicker"])
        if flaky:
            lines.extend([f"- {item.turn_id}: {', '.join(item.failure_families)}" for item in flaky])
        else:
            lines.append("- None observed in this run.")
        lines.extend(["", "## Host-Sensitive / Setup-Sensitive"])
        if host_sensitive:
            lines.extend([f"- {item.turn_id}: {', '.join(item.failure_families)}" for item in host_sensitive])
        else:
            lines.append("- None observed in this run.")
        lines.extend(["", "## Soft Deviations"])
        if soft:
            lines.extend([f"- {item.turn_id}: {', '.join(item.failure_families)}" for item in soft])
        else:
            lines.append("- None observed in this run.")
        lines.extend(
            [
                "",
                "## Suggested Containment",
                "- Preserve evidence-first review for turns that fail quoted instruction handling, evidence binding, or role boundary checks.",
                "",
                "## Candidate Probe Families",
            ]
        )
        if candidate_probe_requests:
            lines.extend([f"- {item['failure_family']}" for item in candidate_probe_requests])
        else:
            lines.append("- No candidate probe families surfaced in this run.")
        return "\n".join(lines) + "\n"

    @staticmethod
    def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
        with path.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row) + "\n")
