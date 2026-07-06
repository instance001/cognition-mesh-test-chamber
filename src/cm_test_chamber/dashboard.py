from __future__ import annotations

import json
import threading
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .assistant_review import compute_assistant_evaluator_fitness, run_assistant_review
from .gauntlet import (
    materialize_probe_draft_files,
    read_or_rebuild_gauntlet_history_index,
    read_or_rebuild_probe_forge_drafts,
    rebuild_gauntlet_history_index,
    rebuild_probe_forge_drafts,
    upsert_probe_request_decision,
)
from .model_catalog import CatalogModel, load_catalog
from .preflight import preflight_catalog_entry, preflight_run_folder
from .runner.probe_runner import ProbeRunner
from .runner.run_config import load_host_profile, load_model_config, load_task_pack, ModelConfig


def _catalog_to_rows(models: list[CatalogModel]) -> list[dict[str, Any]]:
    return [asdict(model) for model in models]


def list_run_directories(repo_root: Path) -> list[dict[str, Any]]:
    runs_root = repo_root / "runs"
    rows: list[dict[str, Any]] = []
    if not runs_root.exists():
        return rows
    for child in sorted(runs_root.iterdir(), key=lambda item: item.name):
        if not child.is_dir():
            continue
        run_type = "gauntlet" if (child / "gauntlet_scores.json").exists() else "normal"
        gauntlet_scores = (
            json.loads((child / "gauntlet_scores.json").read_text(encoding="utf-8"))
            if (child / "gauntlet_scores.json").exists()
            else None
        )
        gauntlet_fingerprint = (
            json.loads((child / "gauntlet_fingerprint.json").read_text(encoding="utf-8"))
            if (child / "gauntlet_fingerprint.json").exists()
            else None
        )
        rows.append(
            {
                "name": child.name,
                "path": child.relative_to(repo_root).as_posix(),
                "run_type": run_type,
                "has_report": (child / "report.md").exists(),
                "has_fingerprint": (child / "cognitive_fingerprint.json").exists(),
                "has_gauntlet_summary": (child / "gauntlet_summary.md").exists(),
                "has_gauntlet_fingerprint": (child / "gauntlet_fingerprint.json").exists(),
                "has_assistant_review": (child / "assistant_review.md").exists()
                or ((child / "assistant_reviews").exists() and any((child / "assistant_reviews").iterdir())),
                "gauntlet_overall_score": (gauntlet_scores or {}).get("overall_score"),
                "gauntlet_failure_bucket_counts": {
                    "systemic": (gauntlet_fingerprint or {}).get("systemic_failures", 0),
                    "soft": (gauntlet_fingerprint or {}).get("soft_failures", 0),
                }
                if gauntlet_fingerprint is not None
                else None,
            }
        )
    return rows


def list_assistant_review_artifacts(run_dir: Path) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    root = run_dir / "assistant_reviews"
    if not root.exists():
        return artifacts
    for child in sorted(root.iterdir(), key=lambda item: item.name):
        if not child.is_dir():
            continue
        review_path = child / "assistant_review.md"
        telemetry_path = child / "assistant_review_telemetry.json"
        fitness_path = child / "assistant_evaluator_fitness.json"
        raw_path = child / "assistant_review_raw.txt"
        failure_path = child / "assistant_review_validation_failure.json"
        telemetry = None
        fitness = None
        if telemetry_path.exists():
            telemetry = json.loads(telemetry_path.read_text(encoding="utf-8"))
        if fitness_path.exists():
            fitness = json.loads(fitness_path.read_text(encoding="utf-8"))
        elif telemetry is not None:
            fitness = compute_assistant_evaluator_fitness(telemetry)
        artifacts.append(
            {
                "assistant_slug": child.name,
                "assistant_id": (telemetry or {}).get("assistant_id", child.name),
                "assistant_label": (telemetry or {}).get("assistant_label"),
                "review_markdown": review_path.read_text(encoding="utf-8") if review_path.exists() else None,
                "raw_text": raw_path.read_text(encoding="utf-8") if raw_path.exists() else None,
                "telemetry": telemetry,
                "evaluator_fitness": fitness,
                "validation_failure": (
                    json.loads(failure_path.read_text(encoding="utf-8")) if failure_path.exists() else None
                ),
            }
        )
    return artifacts


def _assistant_fit_summary_artifact_path(run_dir: Path) -> Path:
    return run_dir / "assistant_reviews" / "assistant_fit_summary.json"


def write_assistant_fit_summary_artifact(run_dir: Path, payload: dict[str, Any]) -> Path:
    artifact_path = _assistant_fit_summary_artifact_path(run_dir)
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return artifact_path


def _assistant_fit_summary_index_path(repo_root: Path) -> Path:
    return repo_root / "runs" / "assistant_fit_summary_index.json"


def build_assistant_fit_aggregate(index_payload: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, dict[str, Any]] = {}
    for entry in index_payload.get("entries", []):
        left_id = entry.get("left_assistant_id")
        right_id = entry.get("right_assistant_id")
        winner = entry.get("winner")
        loser = entry.get("loser")
        for assistant_id in [left_id, right_id]:
            if not assistant_id:
                continue
            summary.setdefault(
                assistant_id,
                {
                    "wins": 0,
                    "losses": 0,
                    "validation_failures": 0,
                    "salvage_count": 0,
                    "appearances": 0,
                    "fitness_score_total": 0,
                    "fitness_score_average": 0,
                    "best_fitness_score": 0,
                    "worst_fitness_score": 0,
                    "production_usable_count": 0,
                    "monitoring_count": 0,
                    "experimental_count": 0,
                    "containment_only_count": 0,
                },
            )
            summary[assistant_id]["appearances"] += 1
        if winner in summary:
            summary[winner]["wins"] += 1
        if loser in summary:
            summary[loser]["losses"] += 1
        if left_id in summary:
            if entry.get("left_validation_passed") is False:
                summary[left_id]["validation_failures"] += 1
            if entry.get("left_had_salvage"):
                summary[left_id]["salvage_count"] += 1
            left_score = entry.get("left_fitness_score")
            if isinstance(left_score, (int, float)):
                summary[left_id]["fitness_score_total"] += left_score
                summary[left_id]["best_fitness_score"] = max(summary[left_id]["best_fitness_score"], left_score)
                if summary[left_id]["worst_fitness_score"] == 0:
                    summary[left_id]["worst_fitness_score"] = left_score
                else:
                    summary[left_id]["worst_fitness_score"] = min(summary[left_id]["worst_fitness_score"], left_score)
            left_suitability = entry.get("left_fitness_suitability")
            if left_suitability == "production-usable":
                summary[left_id]["production_usable_count"] += 1
            elif left_suitability == "usable with monitoring":
                summary[left_id]["monitoring_count"] += 1
            elif left_suitability == "experimental":
                summary[left_id]["experimental_count"] += 1
            elif left_suitability == "containment-only":
                summary[left_id]["containment_only_count"] += 1
        if right_id in summary:
            if entry.get("right_validation_passed") is False:
                summary[right_id]["validation_failures"] += 1
            if entry.get("right_had_salvage"):
                summary[right_id]["salvage_count"] += 1
            right_score = entry.get("right_fitness_score")
            if isinstance(right_score, (int, float)):
                summary[right_id]["fitness_score_total"] += right_score
                summary[right_id]["best_fitness_score"] = max(summary[right_id]["best_fitness_score"], right_score)
                if summary[right_id]["worst_fitness_score"] == 0:
                    summary[right_id]["worst_fitness_score"] = right_score
                else:
                    summary[right_id]["worst_fitness_score"] = min(summary[right_id]["worst_fitness_score"], right_score)
            right_suitability = entry.get("right_fitness_suitability")
            if right_suitability == "production-usable":
                summary[right_id]["production_usable_count"] += 1
            elif right_suitability == "usable with monitoring":
                summary[right_id]["monitoring_count"] += 1
            elif right_suitability == "experimental":
                summary[right_id]["experimental_count"] += 1
            elif right_suitability == "containment-only":
                summary[right_id]["containment_only_count"] += 1
    for assistant_id, metrics in summary.items():
        if metrics["appearances"] > 0:
            metrics["fitness_score_average"] = round(metrics["fitness_score_total"] / metrics["appearances"], 2)
        reasons: list[str] = []
        if metrics["wins"] > metrics["losses"]:
            reasons.append("wins more evaluator matchups than it loses")
        elif metrics["losses"] > metrics["wins"]:
            reasons.append("loses more evaluator matchups than it wins")
        if metrics["fitness_score_average"] > 0:
            reasons.append(f"average evaluator score {metrics['fitness_score_average']}/100")
        if metrics["validation_failures"] > 0:
            reasons.append(f"has {metrics['validation_failures']} validation failure(s)")
        if metrics["salvage_count"] > 0:
            reasons.append(f"needed salvage in {metrics['salvage_count']} run(s)")
        if metrics["appearances"] == 1:
            reasons.append("has only one indexed appearance so far")
        if metrics["appearances"] < 2:
            readiness = "insufficient data"
        elif metrics["validation_failures"] > 0 and metrics["losses"] >= metrics["wins"]:
            readiness = "needs containment"
        elif metrics["fitness_score_average"] < 70 or metrics["salvage_count"] >= metrics["appearances"]:
            readiness = "unstable"
        elif metrics["fitness_score_average"] >= 85 and metrics["wins"] >= metrics["losses"]:
            readiness = "promising but early"
        elif metrics["wins"] > metrics["losses"]:
            readiness = "promising but early"
        else:
            readiness = "mixed signal"
        metrics["readiness"] = readiness
        metrics["rationale"] = "; ".join(reasons) if reasons else "no strong historical signal yet"
    return summary


def rebuild_assistant_fit_summary_index(repo_root: Path) -> Path:
    runs_root = repo_root / "runs"
    entries: list[dict[str, Any]] = []
    if runs_root.exists():
        for child in sorted(runs_root.iterdir(), key=lambda item: item.name):
            if not child.is_dir():
                continue
            summary_path = _assistant_fit_summary_artifact_path(child)
            if not summary_path.exists():
                continue
            payload = json.loads(summary_path.read_text(encoding="utf-8"))
            fit_summary = payload.get("fit_summary", {})
            left = payload.get("left", {})
            right = payload.get("right", {})
            entries.append(
                {
                    "run_name": child.name,
                    "run_path": child.relative_to(repo_root).as_posix(),
                    "winner": fit_summary.get("winner"),
                    "loser": fit_summary.get("loser"),
                    "reason": fit_summary.get("reason"),
                    "left_validation_passed": left.get("validation_passed"),
                    "right_validation_passed": right.get("validation_passed"),
                    "left_attempt_count": left.get("attempt_count"),
                    "right_attempt_count": right.get("attempt_count"),
                    "left_had_salvage": left.get("had_salvage"),
                    "right_had_salvage": right.get("had_salvage"),
                    "left_assistant_id": left.get("assistant_id"),
                    "right_assistant_id": right.get("assistant_id"),
                    "left_fitness_score": (left.get("evaluator_fitness") or {}).get("score"),
                    "right_fitness_score": (right.get("evaluator_fitness") or {}).get("score"),
                    "left_fitness_suitability": (left.get("evaluator_fitness") or {}).get("suitability"),
                    "right_fitness_suitability": (right.get("evaluator_fitness") or {}).get("suitability"),
                    "updated_at": summary_path.stat().st_mtime,
                }
            )
    index_payload = {"entries": entries}
    index_payload["aggregate"] = build_assistant_fit_aggregate(index_payload)
    index_path = _assistant_fit_summary_index_path(repo_root)
    index_path.write_text(json.dumps(index_payload, indent=2) + "\n", encoding="utf-8")
    return index_path


def read_run_details(repo_root: Path, run_path: str) -> dict[str, Any]:
    run_dir = (repo_root / run_path).resolve()
    runs_root = (repo_root / "runs").resolve()
    if runs_root not in run_dir.parents and run_dir != runs_root:
        raise ValueError(f"Run path escapes runs root: {run_path}")
    if not run_dir.exists() or not run_dir.is_dir():
        raise ValueError(f"Run directory not found: {run_path}")

    def read_text(name: str) -> str | None:
        path = run_dir / name
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")

    def read_json(name: str) -> Any | None:
        text = read_text(name)
        if text is None:
            return None
        return json.loads(text)

    def read_jsonl(name: str) -> list[Any] | None:
        text = read_text(name)
        if text is None:
            return None
        rows = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
        return rows

    return {
        "run_path": run_path,
        "run_type": "gauntlet" if (run_dir / "gauntlet_scores.json").exists() else "normal",
        "fingerprint": read_json("cognitive_fingerprint.json"),
        "report_markdown": read_text("report.md"),
        "gauntlet_fingerprint": read_json("gauntlet_fingerprint.json"),
        "gauntlet_summary_markdown": read_text("gauntlet_summary.md"),
        "gauntlet_scores": read_json("gauntlet_scores.json"),
        "gauntlet_transcript": read_jsonl("gauntlet_transcript.jsonl"),
        "gauntlet_failure_log": read_jsonl("gauntlet_failure_log.jsonl"),
        "gauntlet_candidate_probe_requests": read_json("gauntlet_candidate_probe_requests.json"),
        "assistant_review_markdown": read_text("assistant_review.md"),
        "assistant_review_telemetry": read_json("assistant_review_telemetry.json"),
        "assistant_evaluator_fitness": (
            read_json("assistant_evaluator_fitness.json")
            or (
                compute_assistant_evaluator_fitness(read_json("assistant_review_telemetry.json"))
                if read_json("assistant_review_telemetry.json") is not None
                else None
            )
        ),
        "assistant_reviews": list_assistant_review_artifacts(run_dir),
        "assistant_fit_summary": read_json("assistant_reviews/assistant_fit_summary.json"),
        "failure_log": read_jsonl("failure_log.jsonl"),
        "negative_lanes": read_json("negative_lane_suggestions.json"),
        "probe_results": read_jsonl("probe_results.jsonl"),
    }


def compare_runs(repo_root: Path, left_run_path: str, right_run_path: str) -> dict[str, Any]:
    left = read_run_details(repo_root, left_run_path)
    right = read_run_details(repo_root, right_run_path)

    left_fp = left.get("fingerprint") or {}
    right_fp = right.get("fingerprint") or {}

    left_failures = left.get("failure_log") or []
    right_failures = right.get("failure_log") or []

    left_failure_families = sorted({item.get("failure_family", "unknown") for item in left_failures})
    right_failure_families = sorted({item.get("failure_family", "unknown") for item in right_failures})

    left_lanes = left.get("negative_lanes") or []
    right_lanes = right.get("negative_lanes") or []
    left_assistant_telemetry = left.get("assistant_review_telemetry") or {}
    right_assistant_telemetry = right.get("assistant_review_telemetry") or {}

    def _assistant_cleanup_map(details: dict[str, Any]) -> dict[str, Any]:
        reviews = details.get("assistant_reviews") or []
        result: dict[str, Any] = {}
        for review in reviews:
            telemetry = review.get("telemetry") or {}
            assistant_id = review.get("assistant_id") or "unknown"
            result[assistant_id] = {
                "assistant_label": review.get("assistant_label"),
                "attempt_count": telemetry.get("attempt_count"),
                "validation_passed": telemetry.get("validation_passed"),
                "evaluator_fitness": review.get("evaluator_fitness"),
                "had_salvage": any(
                    event.get("had_salvage")
                    for event in telemetry.get("salvage_events", [])
                ),
                "leading_prose": [
                    event.get("leading_prose", "")
                    for event in telemetry.get("salvage_events", [])
                    if event.get("leading_prose")
                ],
            }
        return result

    return {
        "left_run_path": left_run_path,
        "right_run_path": right_run_path,
        "deployment_class": {
            "left": left_fp.get("deployment_class"),
            "right": right_fp.get("deployment_class"),
        },
        "task_fit": {
            "left": left_fp.get("task_fit", {}),
            "right": right_fp.get("task_fit", {}),
        },
        "failure_families": {
            "left": left_failure_families,
            "right": right_failure_families,
        },
        "negative_lane_ids": {
            "left": sorted({item.get("lane_id", "unknown") for item in left_lanes}),
            "right": sorted({item.get("lane_id", "unknown") for item in right_lanes}),
        },
        "assistant_review_present": {
            "left": left.get("assistant_review_markdown") is not None,
            "right": right.get("assistant_review_markdown") is not None,
        },
        "assistant_review_cleanup": {
            "left": {
                "attempt_count": left_assistant_telemetry.get("attempt_count"),
                "validation_passed": left_assistant_telemetry.get("validation_passed"),
                "had_salvage": any(
                    event.get("had_salvage")
                    for event in left_assistant_telemetry.get("salvage_events", [])
                ),
                "leading_prose": [
                    event.get("leading_prose", "")
                    for event in left_assistant_telemetry.get("salvage_events", [])
                    if event.get("leading_prose")
                ],
            },
            "right": {
                "attempt_count": right_assistant_telemetry.get("attempt_count"),
                "validation_passed": right_assistant_telemetry.get("validation_passed"),
                "had_salvage": any(
                    event.get("had_salvage")
                    for event in right_assistant_telemetry.get("salvage_events", [])
                ),
                "leading_prose": [
                    event.get("leading_prose", "")
                    for event in right_assistant_telemetry.get("salvage_events", [])
                    if event.get("leading_prose")
                ],
            },
        },
        "assistant_review_cleanup_by_id": {
            "left": _assistant_cleanup_map(left),
            "right": _assistant_cleanup_map(right),
        },
        "operator_review_burden": {
            "left": left_fp.get("operator_review_burden"),
            "right": right_fp.get("operator_review_burden"),
        },
        "strengths": {
            "left": left_fp.get("strengths", []),
            "right": right_fp.get("strengths", []),
        },
        "weaknesses": {
            "left": left_fp.get("weaknesses", []),
            "right": right_fp.get("weaknesses", []),
        },
    }


def compare_assistant_reviews_within_run(
    repo_root: Path,
    run_path: str,
    left_assistant_id: str,
    right_assistant_id: str,
) -> dict[str, Any]:
    details = read_run_details(repo_root, run_path)
    reviews = details.get("assistant_reviews") or []
    review_map = {item.get("assistant_id"): item for item in reviews}
    if left_assistant_id not in review_map:
        raise ValueError(f"Assistant review not found in run: {left_assistant_id}")
    if right_assistant_id not in review_map:
        raise ValueError(f"Assistant review not found in run: {right_assistant_id}")

    def summarize(review: dict[str, Any]) -> dict[str, Any]:
        telemetry = review.get("telemetry") or {}
        failure = review.get("validation_failure") or {}
        return {
            "assistant_id": review.get("assistant_id"),
            "assistant_label": review.get("assistant_label"),
            "attempt_count": telemetry.get("attempt_count"),
            "validation_passed": telemetry.get("validation_passed"),
            "evaluator_fitness": review.get("evaluator_fitness"),
            "had_salvage": any(
                event.get("had_salvage")
                for event in telemetry.get("salvage_events", [])
            ),
            "leading_prose": [
                event.get("leading_prose", "")
                for event in telemetry.get("salvage_events", [])
                if event.get("leading_prose")
            ],
            "trailing_text": [
                event.get("trailing_text", "")
                for event in telemetry.get("salvage_events", [])
                if event.get("trailing_text")
            ],
            "final_issues": telemetry.get("final_issues", []),
            "validation_failure": failure,
        }

    left_summary = summarize(review_map[left_assistant_id])
    right_summary = summarize(review_map[right_assistant_id])

    def score(summary: dict[str, Any]) -> tuple[int, int, int, int]:
        fitness = summary.get("evaluator_fitness") or {}
        fitness_score = fitness.get("score")
        if not isinstance(fitness_score, (int, float)):
            fitness_score = -1
        validation_penalty = 0 if summary["validation_passed"] else 1
        attempt_penalty = summary["attempt_count"] or 99
        salvage_penalty = 1 if summary["had_salvage"] else 0
        return (-int(fitness_score), validation_penalty, attempt_penalty, salvage_penalty)

    left_score = score(left_summary)
    right_score = score(right_summary)
    if left_score < right_score:
        fit_summary = {
            "winner": left_summary["assistant_id"],
            "loser": right_summary["assistant_id"],
            "reason": "Left assistant showed stronger evaluator-role fit on this run.",
            "winning_score": (left_summary.get("evaluator_fitness") or {}).get("score"),
            "losing_score": (right_summary.get("evaluator_fitness") or {}).get("score"),
        }
    elif right_score < left_score:
        fit_summary = {
            "winner": right_summary["assistant_id"],
            "loser": left_summary["assistant_id"],
            "reason": "Right assistant showed stronger evaluator-role fit on this run.",
            "winning_score": (right_summary.get("evaluator_fitness") or {}).get("score"),
            "losing_score": (left_summary.get("evaluator_fitness") or {}).get("score"),
        }
    else:
        fit_summary = {
            "winner": None,
            "loser": None,
            "reason": "The two assistant profiles are tied on the current evaluator-fit heuristic.",
            "winning_score": (left_summary.get("evaluator_fitness") or {}).get("score"),
            "losing_score": (right_summary.get("evaluator_fitness") or {}).get("score"),
        }

    payload = {
        "run_path": run_path,
        "left": left_summary,
        "right": right_summary,
        "fit_summary": fit_summary,
    }
    run_dir = (repo_root / run_path).resolve()
    write_assistant_fit_summary_artifact(run_dir, payload)
    rebuild_assistant_fit_summary_index(repo_root)
    return payload


def build_dashboard_status(repo_root: Path) -> dict[str, Any]:
    assistant_catalog = load_catalog(repo_root / "configs" / "catalogs" / "assistant_models.json")
    mut_catalog = load_catalog(repo_root / "configs" / "catalogs" / "models_under_test.json")
    return {
        "model_under_test": _catalog_to_rows(mut_catalog.models),
        "assistants": _catalog_to_rows(assistant_catalog.models),
        "model_configs": [
            path.relative_to(repo_root).as_posix()
            for path in sorted((repo_root / "configs" / "models").glob("*.json"))
        ],
        "host_configs": [
            path.relative_to(repo_root).as_posix()
            for path in sorted((repo_root / "configs" / "hosts").glob("*.json"))
        ],
        "task_packs": [
            path.relative_to(repo_root).as_posix()
            for path in sorted((repo_root / "configs" / "task_profiles").glob("*.json"))
        ],
        "runs": list_run_directories(repo_root),
        "gauntlet_history_index": read_or_rebuild_gauntlet_history_index(repo_root),
        "probe_forge_drafts": read_or_rebuild_probe_forge_drafts(repo_root),
        "assistant_fit_index": (
            json.loads(_assistant_fit_summary_index_path(repo_root).read_text(encoding="utf-8"))
            if _assistant_fit_summary_index_path(repo_root).exists()
            else {"entries": []}
        ),
    }


def build_mock_preset_runner(repo_root: Path, mode: str, out_path: str | None = None) -> ProbeRunner:
    if mode not in {"good", "mixed", "bad"}:
        raise ValueError(f"Unsupported mock preset mode: {mode}")
    model = load_model_config(repo_root / "configs" / "models" / "mock_model.json")
    model = ModelConfig(**{**asdict(model), "mode": mode})
    host = load_host_profile(repo_root / "configs" / "hosts" / "schema_locked_no_tools.json")
    task_pack = load_task_pack(repo_root / "configs" / "task_profiles" / "mvp_probe_pack.json")
    out_dir = repo_root / (out_path or f"runs/mock_{mode}")
    return ProbeRunner(repo_root, model, host, task_pack, out_dir)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: list[dict[str, Any]] = []

    def list_jobs(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(job) for job in sorted(self._jobs, key=lambda item: item["created_at"], reverse=True)]

    def enqueue(self, job_type: str, payload: dict[str, Any], action) -> dict[str, Any]:
        job = {
            "job_id": uuid.uuid4().hex[:12],
            "job_type": job_type,
            "status": "queued",
            "payload": payload,
            "created_at": _utc_now(),
            "started_at": None,
            "finished_at": None,
            "message": "Queued.",
            "result": None,
            "error": None,
        }
        with self._lock:
            self._jobs.append(job)

        def runner() -> None:
            self._update(job["job_id"], status="running", started_at=_utc_now(), message="Running...")
            try:
                result = action()
            except Exception as exc:  # noqa: BLE001
                self._update(
                    job["job_id"],
                    status="failed",
                    finished_at=_utc_now(),
                    message=f"Failed: {exc}",
                    error=str(exc),
                )
                return
            self._update(
                job["job_id"],
                status="completed",
                finished_at=_utc_now(),
                message="Completed.",
                result=result,
            )

        threading.Thread(target=runner, daemon=True).start()
        return dict(job)

    def _update(self, job_id: str, **changes: Any) -> None:
        with self._lock:
            for job in self._jobs:
                if job["job_id"] == job_id:
                    job.update(changes)
                    return


DASHBOARD_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Cognition Mesh Dashboard</title>
  <style>
    :root {
      --bg: #f4efe7;
      --panel: #fffaf2;
      --ink: #1d1b18;
      --muted: #6b6258;
      --accent: #0f766e;
      --accent-2: #c2410c;
      --line: #d9cdbd;
      --good: #166534;
      --bad: #991b1b;
      --shadow: 0 18px 40px rgba(68, 51, 27, 0.12);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(15,118,110,0.12), transparent 30%),
        radial-gradient(circle at bottom right, rgba(194,65,12,0.12), transparent 25%),
        var(--bg);
    }
    .wrap {
      max-width: 1200px;
      margin: 0 auto;
      padding: 32px 20px 48px;
    }
    h1, h2 { margin: 0 0 12px; line-height: 1.1; }
    p { color: var(--muted); }
    .hero {
      background: linear-gradient(135deg, rgba(255,250,242,0.96), rgba(244,239,231,0.96));
      border: 1px solid var(--line);
      border-radius: 24px;
      padding: 28px;
      box-shadow: var(--shadow);
      margin-bottom: 24px;
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      gap: 20px;
    }
    .button-row {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
      margin-top: 12px;
    }
    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 22px;
      padding: 20px;
      box-shadow: var(--shadow);
    }
    label, select, input, button, textarea {
      display: block;
      width: 100%;
      font: inherit;
    }
    label {
      margin-top: 12px;
      margin-bottom: 6px;
      color: var(--muted);
      font-size: 0.95rem;
    }
    select, input, textarea {
      padding: 10px 12px;
      border-radius: 12px;
      border: 1px solid var(--line);
      background: #fffdf9;
      color: var(--ink);
    }
    button {
      margin-top: 14px;
      padding: 11px 14px;
      border: none;
      border-radius: 999px;
      background: var(--accent);
      color: white;
      cursor: pointer;
      transition: transform 140ms ease, opacity 140ms ease;
    }
    button.alt { background: var(--accent-2); }
    button:hover { transform: translateY(-1px); }
    .status-box, .runs-box {
      margin-top: 14px;
      padding: 14px;
      min-height: 140px;
      border-radius: 16px;
      background: #fffdf9;
      border: 1px solid var(--line);
      white-space: pre-wrap;
      font-family: Consolas, monospace;
      font-size: 0.9rem;
      overflow-wrap: anywhere;
    }
    .run-item {
      padding: 12px 0;
      border-top: 1px solid var(--line);
    }
    .run-item:first-child { border-top: none; }
    .badge {
      display: inline-block;
      margin-right: 8px;
      margin-top: 6px;
      padding: 3px 8px;
      border-radius: 999px;
      font-size: 0.8rem;
      background: #efe4d4;
      color: var(--ink);
    }
    .ok { color: var(--good); }
    .fail { color: var(--bad); }
    .jobs-box {
      margin-top: 14px;
      display: grid;
      gap: 12px;
    }
    .job-card {
      padding: 14px;
      border-radius: 16px;
      border: 1px solid var(--line);
      background: #fffdf9;
    }
    .job-meta {
      color: var(--muted);
      font-size: 0.9rem;
      margin-top: 6px;
    }
    .detail-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 16px;
      margin-top: 14px;
    }
    .detail-card {
      padding: 14px;
      border-radius: 16px;
      border: 1px solid var(--line);
      background: #fffdf9;
    }
    .detail-card h3 {
      margin: 0 0 10px;
      font-size: 1rem;
    }
    .detail-pre {
      white-space: pre-wrap;
      font-family: Consolas, monospace;
      font-size: 0.9rem;
      max-height: 420px;
      overflow: auto;
    }
    .compare-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 16px;
      margin-top: 14px;
    }
    .assistant-list {
      margin-top: 14px;
      display: grid;
      gap: 10px;
    }
    .assistant-row {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto auto;
      gap: 10px;
      align-items: center;
      padding: 12px;
      border-radius: 14px;
      border: 1px solid var(--line);
      background: #fffdf9;
    }
    .assistant-meta {
      color: var(--muted);
      font-size: 0.9rem;
    }
    .assistant-row button {
      margin-top: 0;
      width: auto;
      min-width: 120px;
    }
    .index-list {
      margin-top: 14px;
      display: grid;
      gap: 10px;
    }
    .aggregate-grid {
      margin-top: 14px;
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 10px;
    }
    .toolbar {
      display: grid;
      grid-template-columns: minmax(0, 220px);
      gap: 10px;
      margin-top: 12px;
    }
  </style>
</head>
<body>
  <div class="wrap">
    <section class="hero">
      <h1>Cognition Mesh Dashboard</h1>
      <p>Thin local control surface for catalogs, preflight, runs, and optional assistant review. Deterministic harness outputs remain the source of truth.</p>
    </section>
    <section class="grid">
      <div class="panel">
        <h2>Run Harness</h2>
        <label for="modelConfig">Model config</label>
        <select id="modelConfig"></select>
        <label for="hostConfig">Host config</label>
        <select id="hostConfig"></select>
        <label for="taskPack">Task pack</label>
        <select id="taskPack"></select>
        <label for="outDir">Run output folder</label>
        <input id="outDir" value="runs/dashboard_run" />
        <div class="button-row">
          <button id="runMockGood">Mock Good</button>
          <button id="runMockMixed">Mock Mixed</button>
          <button id="runMockBad">Mock Bad</button>
        </div>
        <button id="preflightRun">Preflight Run</button>
        <button id="startRun">Start Run</button>
        <div id="runStatus" class="status-box">Waiting for action.</div>
      </div>
      <div class="panel">
        <h2>Assistant Review</h2>
        <label for="assistantSelect">Assistant</label>
        <select id="assistantSelect"></select>
        <label for="runSelect">Completed run</label>
        <select id="runSelect"></select>
        <button id="preflightReview" class="alt">Preflight Review</button>
        <button id="startReview" class="alt">Generate Assistant Review</button>
        <div id="reviewStatus" class="status-box">Waiting for action.</div>
      </div>
    </section>
    <section class="panel" style="margin-top: 20px;">
      <h2>Run Ledger</h2>
      <div id="runLedger" class="runs-box">Loading runs...</div>
    </section>
    <section class="panel" style="margin-top: 20px;">
      <h2>Job History</h2>
      <div id="jobHistory" class="jobs-box">No jobs yet.</div>
    </section>
    <section class="panel" style="margin-top: 20px;">
      <h2>Assistant Fit Index</h2>
      <div class="toolbar">
        <div>
          <label for="assistantFitSort">Sort assistant reliability by</label>
          <select id="assistantFitSort">
            <option value="fitness_score_average">Avg Score</option>
            <option value="wins">Wins</option>
            <option value="validation_failures">Validation Failures</option>
            <option value="salvage_count">Salvage Count</option>
            <option value="appearances">Appearances</option>
          </select>
        </div>
      </div>
      <div id="assistantFitAggregate" class="aggregate-grid">No assistant reliability summary yet.</div>
      <div id="assistantFitIndex" class="index-list">No assistant fit summaries yet.</div>
    </section>
    <section class="panel" style="margin-top: 20px;">
      <h2>Gauntlet Variance Atlas</h2>
      <div class="toolbar">
        <div>
          <label for="gauntletFamilySort">Sort failure families by</label>
          <select id="gauntletFamilySort">
            <option value="appearances">Appearances</option>
            <option value="probe_needed_count">Probe Needed</option>
            <option value="systemic_count">Systemic</option>
            <option value="flaky_count">Flaky</option>
            <option value="host_sensitive_count">Host-Sensitive</option>
          </select>
        </div>
      </div>
      <div id="gauntletModelAggregate" class="aggregate-grid">No gauntlet model history yet.</div>
      <div id="gauntletFamilyAggregate" class="aggregate-grid">No gauntlet failure-family history yet.</div>
      <div id="gauntletHistoryIndex" class="index-list">No gauntlet history entries yet.</div>
      <div id="probeForgeDrafts" class="index-list">No forge drafts yet.</div>
    </section>
    <section class="panel" style="margin-top: 20px;">
      <h2>Run Detail</h2>
      <label for="detailRunSelect">Inspect run</label>
      <select id="detailRunSelect"></select>
      <div id="runDetail" class="detail-grid">
        <div class="detail-card"><h3>Fingerprint</h3><div class="detail-pre">Select a run.</div></div>
      </div>
    </section>
    <section class="panel" style="margin-top: 20px;">
      <h2>Run Compare</h2>
      <div class="grid">
        <div>
          <label for="compareLeftRun">Left run</label>
          <select id="compareLeftRun"></select>
        </div>
        <div>
          <label for="compareRightRun">Right run</label>
          <select id="compareRightRun"></select>
        </div>
      </div>
      <div id="runCompare" class="compare-grid">
        <div class="detail-card"><h3>Comparison</h3><div class="detail-pre">Select two runs.</div></div>
      </div>
    </section>
    <section class="panel" style="margin-top: 20px;">
      <h2>Assistant Compare</h2>
      <label for="assistantCompareRun">Run</label>
      <select id="assistantCompareRun"></select>
      <div id="assistantCompareCatalog" class="assistant-list">
        <div class="assistant-row">
          <div class="assistant-meta">Select a run to inspect assistant coverage.</div>
        </div>
      </div>
      <div class="grid">
        <div>
          <label for="assistantCompareLeft">Left assistant</label>
          <select id="assistantCompareLeft"></select>
        </div>
        <div>
          <label for="assistantCompareRight">Right assistant</label>
          <select id="assistantCompareRight"></select>
        </div>
      </div>
      <div id="assistantCompare" class="compare-grid">
        <div class="detail-card"><h3>Assistant Comparison</h3><div class="detail-pre">Select a run with two assistant reviews.</div></div>
      </div>
    </section>
  </div>
  <script>
    async function loadStatus() {
      const response = await fetch("/api/status");
      const data = await response.json();
      fillSelect("modelConfig", data.model_configs);
      fillSelect("hostConfig", data.host_configs);
      fillSelect("taskPack", data.task_packs);
      fillSelect("assistantSelect", data.assistants.map(item => item.id), item => item);
      fillSelect("runSelect", data.runs.map(item => item.path), item => item);
      fillSelect("detailRunSelect", data.runs.map(item => item.path), item => item);
      fillSelect("compareLeftRun", data.runs.map(item => item.path), item => item);
      fillSelect("compareRightRun", data.runs.map(item => item.path), item => item);
      fillSelect("assistantCompareRun", data.runs.map(item => item.path), item => item);
      renderRuns(data.runs);
      renderJobs(data.jobs || []);
      renderAssistantFitIndex(data.assistant_fit_index || {entries: []});
      renderAssistantFitAggregate(data.assistant_fit_index || {aggregate: {}});
      renderGauntletModelAggregate(data.gauntlet_history_index || {aggregate: {models: {}}});
      renderGauntletFamilyAggregate(data.gauntlet_history_index || {aggregate: {failure_families: {}}});
      renderGauntletHistoryIndex(data.gauntlet_history_index || {entries: []});
      renderProbeForgeDrafts(data.probe_forge_drafts || {entries: []});
      const detailSelect = document.getElementById("detailRunSelect");
      if (detailSelect.value) {
        await loadRunDetail(detailSelect.value);
      }
      const leftCompare = document.getElementById("compareLeftRun");
      const rightCompare = document.getElementById("compareRightRun");
      if (leftCompare.options.length > 1 && !rightCompare.value) {
        rightCompare.selectedIndex = Math.min(1, rightCompare.options.length - 1);
      }
      if (leftCompare.value && rightCompare.value) {
        await loadRunCompare(leftCompare.value, rightCompare.value);
      }
      const assistantCompareRun = document.getElementById("assistantCompareRun");
      if (assistantCompareRun.value) {
        await syncAssistantCompareOptions(assistantCompareRun.value, data.assistants || []);
      }
    }

    function fillSelect(id, items, labelFn) {
      const select = document.getElementById(id);
      select.innerHTML = "";
      for (const item of items) {
        const option = document.createElement("option");
        option.value = item;
        option.textContent = labelFn ? labelFn(item) : item;
        select.appendChild(option);
      }
    }

    function renderRuns(runs) {
      const target = document.getElementById("runLedger");
      if (!runs.length) {
        target.textContent = "No run folders found yet.";
        return;
      }
      target.innerHTML = runs.map(run => `
        <div class="run-item">
          <strong>${run.name}</strong><br>
          <span class="badge">${run.path}</span>
          <span class="badge">${run.run_type}</span>
          <span class="badge">${run.has_report ? "report" : "no report"}</span>
          <span class="badge">${run.has_fingerprint ? "fingerprint" : "no fingerprint"}</span>
          <span class="badge">${run.has_gauntlet_summary ? "gauntlet summary" : "no gauntlet summary"}</span>
          <span class="badge">${run.has_assistant_review ? "assistant review" : "no assistant review"}</span>
          ${run.gauntlet_overall_score !== null && run.gauntlet_overall_score !== undefined
            ? `<span class="badge">gauntlet score ${escapeHtml(String(run.gauntlet_overall_score))}</span>`
            : ""}
        </div>
      `).join("");
    }

    function renderJobs(jobs) {
      const target = document.getElementById("jobHistory");
      if (!jobs.length) {
        target.textContent = "No jobs yet.";
        return;
      }
      target.innerHTML = jobs.map(job => `
        <div class="job-card">
          <strong>${job.job_type}</strong> <span class="${job.status === "completed" ? "ok" : job.status === "failed" ? "fail" : ""}">${job.status}</span>
          <div class="job-meta">Job: ${job.job_id} | Created: ${job.created_at}</div>
          <div class="job-meta">${job.message || ""}</div>
          ${job.error ? `<div class="job-meta fail">${job.error}</div>` : ""}
          ${job.result ? `<div class="job-meta">${job.result}</div>` : ""}
        </div>
      `).join("");
    }

    function renderAssistantFitIndex(indexPayload) {
      const target = document.getElementById("assistantFitIndex");
      const entries = indexPayload.entries || [];
      if (!entries.length) {
        target.textContent = "No assistant fit summaries yet.";
        return;
      }
      target.innerHTML = entries.map(entry => `
        <div class="assistant-row">
            <div>
              <strong>${escapeHtml(entry.run_name)}</strong>
              <div class="assistant-meta">${escapeHtml(entry.run_path)} | winner: ${escapeHtml(String(entry.winner))}</div>
              <div class="assistant-meta">${escapeHtml(entry.reason || "")}</div>
              <div class="assistant-meta">
                L: ${escapeHtml(String(entry.left_assistant_id))} | score=${escapeHtml(String(entry.left_fitness_score))} | suitability=${escapeHtml(String(entry.left_fitness_suitability))} | pass=${escapeHtml(String(entry.left_validation_passed))} | attempts=${escapeHtml(String(entry.left_attempt_count))} | salvage=${escapeHtml(String(entry.left_had_salvage))}
              </div>
              <div class="assistant-meta">
                R: ${escapeHtml(String(entry.right_assistant_id))} | score=${escapeHtml(String(entry.right_fitness_score))} | suitability=${escapeHtml(String(entry.right_fitness_suitability))} | pass=${escapeHtml(String(entry.right_validation_passed))} | attempts=${escapeHtml(String(entry.right_attempt_count))} | salvage=${escapeHtml(String(entry.right_had_salvage))}
              </div>
            </div>
          <button class="alt" onclick="jumpToRun('${escapeJs(entry.run_path)}')">Open Run</button>
          <button onclick="jumpToAssistantCompare('${escapeJs(entry.run_path)}')">Compare</button>
        </div>
      `).join("");
    }

    function renderAssistantFitAggregate(indexPayload) {
      const target = document.getElementById("assistantFitAggregate");
      const aggregate = indexPayload.aggregate || {};
      const sortKey = document.getElementById("assistantFitSort").value;
      const ids = Object.keys(aggregate).sort((a, b) => {
        const av = aggregate[a][sortKey] ?? 0;
        const bv = aggregate[b][sortKey] ?? 0;
        if (bv !== av) {
          return bv - av;
        }
        return a.localeCompare(b);
      });
      if (!ids.length) {
        target.textContent = "No assistant reliability summary yet.";
        return;
      }
      target.innerHTML = ids.map(id => {
        const item = aggregate[id];
        return `
          <div class="detail-card">
            <h3>${escapeHtml(id)}</h3>
            <div class="assistant-meta">Avg Score: ${escapeHtml(String(item.fitness_score_average ?? ""))}/100</div>
            <div class="assistant-meta">Readiness: ${escapeHtml(item.readiness || "")}</div>
            <div class="assistant-meta">Suitability mix: prod=${escapeHtml(String(item.production_usable_count ?? 0))}, monitor=${escapeHtml(String(item.monitoring_count ?? 0))}, experimental=${escapeHtml(String(item.experimental_count ?? 0))}, containment=${escapeHtml(String(item.containment_only_count ?? 0))}</div>
            <div class="detail-pre">${escapeHtml(JSON.stringify(item, null, 2))}</div>
            <div class="assistant-meta">${escapeHtml(item.rationale || "")}</div>
          </div>
        `;
      }).join("");
    }

    function renderGauntletModelAggregate(indexPayload) {
      const target = document.getElementById("gauntletModelAggregate");
      const aggregate = (indexPayload.aggregate || {}).models || {};
      const ids = Object.keys(aggregate).sort((a, b) => {
        const av = aggregate[a].average_score ?? 0;
        const bv = aggregate[b].average_score ?? 0;
        if (bv !== av) {
          return bv - av;
        }
        return a.localeCompare(b);
      });
      if (!ids.length) {
        target.textContent = "No gauntlet model history yet.";
        return;
      }
      target.innerHTML = ids.map(id => {
        const item = aggregate[id];
        return `
          <div class="detail-card">
            <h3>${escapeHtml(id)}</h3>
            <div class="assistant-meta">Runs: ${escapeHtml(String(item.runs ?? 0))}</div>
            <div class="assistant-meta">Avg Score: ${escapeHtml(String(item.average_score ?? 0))}</div>
            <div class="assistant-meta">Systemic=${escapeHtml(String(item.systemic_failures ?? 0))} | Flaky=${escapeHtml(String(item.flaky_failures ?? 0))} | Host=${escapeHtml(String(item.host_sensitive_failures ?? 0))} | Soft=${escapeHtml(String(item.soft_failures ?? 0))}</div>
            <div class="assistant-meta">Probe Needed: ${escapeHtml(String(item.probe_needed_count ?? 0))}</div>
            <div class="assistant-meta">${escapeHtml(item.rationale || "")}</div>
          </div>
        `;
      }).join("");
    }

    function renderGauntletFamilyAggregate(indexPayload) {
      const target = document.getElementById("gauntletFamilyAggregate");
      const aggregate = (indexPayload.aggregate || {}).failure_families || {};
      const sortKey = document.getElementById("gauntletFamilySort").value;
      const ids = Object.keys(aggregate).sort((a, b) => {
        const av = aggregate[a][sortKey] ?? 0;
        const bv = aggregate[b][sortKey] ?? 0;
        if (bv !== av) {
          return bv - av;
        }
        return a.localeCompare(b);
      });
      if (!ids.length) {
        target.textContent = "No gauntlet failure-family history yet.";
        return;
      }
      target.innerHTML = ids.map(id => {
        const item = aggregate[id];
        return `
          <div class="detail-card">
            <h3>${escapeHtml(id)}</h3>
            <div class="assistant-meta">Appearances: ${escapeHtml(String(item.appearances ?? 0))}</div>
            <div class="assistant-meta">Highest Severity: ${escapeHtml(String(item.highest_severity ?? "low"))}</div>
            <div class="assistant-meta">Systemic=${escapeHtml(String(item.systemic_count ?? 0))} | Flaky=${escapeHtml(String(item.flaky_count ?? 0))} | Host=${escapeHtml(String(item.host_sensitive_count ?? 0))} | Soft=${escapeHtml(String(item.soft_count ?? 0))} | Observed=${escapeHtml(String(item.observed_only_count ?? 0))}</div>
            <div class="assistant-meta">Probe Needed: ${escapeHtml(String(item.probe_needed_count ?? 0))} | Retry: ${escapeHtml(String(item.latest_retry_observation ?? "not_run"))}</div>
            <div class="assistant-meta">Decision: ${escapeHtml(String(item.operator_decision ?? "unreviewed"))}</div>
            <div class="assistant-meta">Models: ${escapeHtml((item.models_seen || []).join(", "))}</div>
            <div class="assistant-meta">${escapeHtml(item.rationale || "")}</div>
            <div class="assistant-meta">${escapeHtml(item.operator_note || "")}</div>
            <div class="button-row">
              <button onclick="setProbeRequestDecision('${escapeJs(id)}','monitor_only')">Monitor</button>
              <button onclick="setProbeRequestDecision('${escapeJs(id)}','probe_candidate')">Candidate</button>
              <button class="alt" onclick="setProbeRequestDecision('${escapeJs(id)}','confirmed_for_forge')">Confirm</button>
            </div>
          </div>
        `;
      }).join("");
    }

    function renderGauntletHistoryIndex(indexPayload) {
      const target = document.getElementById("gauntletHistoryIndex");
      const entries = indexPayload.entries || [];
      if (!entries.length) {
        target.textContent = "No gauntlet history entries yet.";
        return;
      }
      target.innerHTML = entries.map(entry => `
        <div class="assistant-row">
          <div>
            <strong>${escapeHtml(entry.run_name)}</strong>
            <div class="assistant-meta">${escapeHtml(entry.run_path)} | model=${escapeHtml(String(entry.model_name || "unknown"))} | gauntlet=${escapeHtml(String(entry.gauntlet_id || "unknown"))}</div>
            <div class="assistant-meta">score=${escapeHtml(String(entry.overall_score ?? ""))} | weakest=${escapeHtml(String(entry.weakest_lane || "none"))} | repeated=${escapeHtml(String(entry.most_repeated_failure_family || "none"))}</div>
            <div class="assistant-meta">retry=${escapeHtml(String(entry.retry_policy || "none"))} | systemic=${escapeHtml(String(entry.systemic_failures || 0))} | flaky=${escapeHtml(String(entry.flaky_failures || 0))} | host=${escapeHtml(String(entry.host_sensitive_failures || 0))} | soft=${escapeHtml(String(entry.soft_failures || 0))}</div>
            <div class="assistant-meta">probe requests=${escapeHtml(String((entry.candidate_probe_requests || []).length))}</div>
          </div>
          <button class="alt" onclick="jumpToRun('${escapeJs(entry.run_path)}')">Open Run</button>
        </div>
      `).join("");
    }

    function renderProbeForgeDrafts(payload) {
      const target = document.getElementById("probeForgeDrafts");
      const entries = payload.entries || [];
      if (!entries.length) {
        target.textContent = "No forge drafts yet.";
        return;
      }
      target.innerHTML = entries.map(entry => `
        <div class="assistant-row">
          <div>
            <strong>${escapeHtml(entry.failure_family)}</strong>
            <div class="assistant-meta">draft=${escapeHtml(entry.draft_id)} | priority=${escapeHtml(String(entry.priority))} | status=${escapeHtml(String(entry.status))}</div>
            <div class="assistant-meta">runs=${escapeHtml(String(entry.source_run_count ?? 0))} | models=${escapeHtml((entry.source_models || []).join(", "))}</div>
            <div class="assistant-meta">path=${escapeHtml(String(entry.materialized_probe_path || "not materialized"))}</div>
            <div class="assistant-meta">${escapeHtml(entry.evidence_summary || "")}</div>
            <div class="assistant-meta">turn focus: ${escapeHtml((entry.suggested_turn_focus || []).join(", "))}</div>
            <div class="assistant-meta">${escapeHtml((entry.suggested_assertions || []).join(" | "))}</div>
          </div>
        </div>
      `).join("");
    }

    async function loadRunDetail(runPath) {
      const target = document.getElementById("runDetail");
      if (!runPath) {
        target.innerHTML = `<div class="detail-card"><h3>Run Detail</h3><div class="detail-pre">No run selected.</div></div>`;
        return;
      }
      const response = await fetch("/api/run-detail?run=" + encodeURIComponent(runPath));
      const data = await response.json();
      if (data.error) {
        target.innerHTML = `<div class="detail-card"><h3>Error</h3><div class="detail-pre">${data.error}</div></div>`;
        return;
      }
      const runType = data.run_type || "normal";
      const fingerprint = data.fingerprint ? JSON.stringify(data.fingerprint, null, 2) : "No fingerprint found.";
      const failures = data.failure_log && data.failure_log.length ? JSON.stringify(data.failure_log, null, 2) : "No failure log entries.";
      const report = data.report_markdown || "No report found.";
      const gauntletFingerprint = data.gauntlet_fingerprint
        ? JSON.stringify(data.gauntlet_fingerprint, null, 2)
        : "No gauntlet fingerprint found.";
      const gauntletSummary = data.gauntlet_summary_markdown || "No gauntlet summary found.";
      const gauntletScores = data.gauntlet_scores
        ? JSON.stringify(data.gauntlet_scores, null, 2)
        : "No gauntlet scores found.";
      const gauntletFailures = data.gauntlet_failure_log && data.gauntlet_failure_log.length
        ? JSON.stringify(data.gauntlet_failure_log, null, 2)
        : "No gauntlet failure log entries.";
      const gauntletTranscript = data.gauntlet_transcript && data.gauntlet_transcript.length
        ? JSON.stringify(data.gauntlet_transcript, null, 2)
        : "No gauntlet transcript found.";
      const gauntletProbeRequests = data.gauntlet_candidate_probe_requests
        ? JSON.stringify(data.gauntlet_candidate_probe_requests, null, 2)
        : "No candidate probe requests found.";
      const assistantReview = data.assistant_review_markdown || "No assistant review found.";
      const assistantTelemetry = data.assistant_review_telemetry
        ? JSON.stringify(data.assistant_review_telemetry, null, 2)
        : "No assistant telemetry found.";
      const assistantFitness = data.assistant_evaluator_fitness
        ? JSON.stringify(data.assistant_evaluator_fitness, null, 2)
        : "No assistant evaluator fitness found.";
      const assistantReviews = data.assistant_reviews && data.assistant_reviews.length
        ? JSON.stringify(data.assistant_reviews.map(item => ({
            assistant_id: item.assistant_id,
            assistant_label: item.assistant_label,
            telemetry: item.telemetry,
            evaluator_fitness: item.evaluator_fitness
          })), null, 2)
        : "No assistant review set found.";
      const assistantFitSummary = data.assistant_fit_summary
        ? JSON.stringify(data.assistant_fit_summary, null, 2)
        : "No persisted assistant fit summary found yet.";
      target.innerHTML = `
        <div class="detail-card"><h3>Run Type</h3><div class="detail-pre">${escapeHtml(runType)}</div></div>
        <div class="detail-card"><h3>Fingerprint</h3><div class="detail-pre">${escapeHtml(fingerprint)}</div></div>
        <div class="detail-card"><h3>Failure Log</h3><div class="detail-pre">${escapeHtml(failures)}</div></div>
        <div class="detail-card"><h3>Report</h3><div class="detail-pre">${escapeHtml(report)}</div></div>
        <div class="detail-card"><h3>Gauntlet Fingerprint</h3><div class="detail-pre">${escapeHtml(gauntletFingerprint)}</div></div>
        <div class="detail-card"><h3>Gauntlet Summary</h3><div class="detail-pre">${escapeHtml(gauntletSummary)}</div></div>
        <div class="detail-card"><h3>Gauntlet Scores</h3><div class="detail-pre">${escapeHtml(gauntletScores)}</div></div>
        <div class="detail-card"><h3>Gauntlet Failure Log</h3><div class="detail-pre">${escapeHtml(gauntletFailures)}</div></div>
        <div class="detail-card"><h3>Gauntlet Transcript</h3><div class="detail-pre">${escapeHtml(gauntletTranscript)}</div></div>
        <div class="detail-card"><h3>Candidate Probe Requests</h3><div class="detail-pre">${escapeHtml(gauntletProbeRequests)}</div></div>
        <div class="detail-card"><h3>Assistant Review</h3><div class="detail-pre">${escapeHtml(assistantReview)}</div></div>
        <div class="detail-card"><h3>Assistant Telemetry</h3><div class="detail-pre">${escapeHtml(assistantTelemetry)}</div></div>
        <div class="detail-card"><h3>Evaluator Fitness</h3><div class="detail-pre">${escapeHtml(assistantFitness)}</div></div>
        <div class="detail-card"><h3>Assistant Review Set</h3><div class="detail-pre">${escapeHtml(assistantReviews)}</div></div>
        <div class="detail-card"><h3>Assistant Fit Summary</h3><div class="detail-pre">${escapeHtml(assistantFitSummary)}</div></div>
      `;
    }

    function renderAssistantCoverage(runPath, catalog, reviews) {
      const target = document.getElementById("assistantCompareCatalog");
      const existing = new Map(reviews.map(item => [item.assistant_id, item]));
      target.innerHTML = catalog.map(item => {
        const present = existing.has(item.id);
        const review = existing.get(item.id);
        const telemetry = review && review.telemetry ? review.telemetry : null;
        const status = !present
          ? "missing"
          : telemetry && telemetry.validation_passed
            ? "ready"
            : "needs attention";
        return `
          <div class="assistant-row">
            <div>
              <strong>${escapeHtml(item.label || item.id)}</strong>
              <div class="assistant-meta">${escapeHtml(item.id)} | ${escapeHtml(status)}</div>
            </div>
            <button class="alt" onclick="triggerAssistantReview('${escapeJs(runPath)}','${escapeJs(item.id)}')">${present ? "Regenerate" : "Generate"}</button>
            <button onclick="seedAssistantCompare('${escapeJs(item.id)}')">Use</button>
          </div>
        `;
      }).join("");
    }

    async function syncAssistantCompareOptions(runPath, catalog) {
      const response = await fetch("/api/run-detail?run=" + encodeURIComponent(runPath));
      const data = await response.json();
      const reviews = data.assistant_reviews || [];
      const ids = reviews.map(item => item.assistant_id);
      renderAssistantCoverage(runPath, catalog, reviews);
      fillSelect("assistantCompareLeft", ids, item => item);
      fillSelect("assistantCompareRight", ids, item => item);
      const right = document.getElementById("assistantCompareRight");
      if (right.options.length > 1) {
        right.selectedIndex = 1;
      }
      if (ids.length >= 2) {
        await loadAssistantCompare(runPath, ids[0], ids[Math.min(1, ids.length - 1)]);
      } else {
        const target = document.getElementById("assistantCompare");
        target.innerHTML = `<div class="detail-card"><h3>Assistant Comparison</h3><div class="detail-pre">This run does not yet have two assistant reviews.</div></div>`;
      }
    }

    async function triggerAssistantReview(runPath, assistantId) {
      await postJson("/api/assistant-review", {
        run_dir: runPath,
        assistant_id: assistantId
      }, "reviewStatus");
      const response = await fetch("/api/status");
      const data = await response.json();
      await syncAssistantCompareOptions(runPath, data.assistants || []);
    }

    function jumpToRun(runPath) {
      document.getElementById("detailRunSelect").value = runPath;
      loadRunDetail(runPath);
    }

    function jumpToAssistantCompare(runPath) {
      document.getElementById("assistantCompareRun").value = runPath;
      fetch("/api/status")
        .then(response => response.json())
        .then(data => syncAssistantCompareOptions(runPath, data.assistants || []));
    }

    function seedAssistantCompare(assistantId) {
      const left = document.getElementById("assistantCompareLeft");
      const right = document.getElementById("assistantCompareRight");
      const leftValues = Array.from(left.options).map(option => option.value);
      const rightValues = Array.from(right.options).map(option => option.value);
      if (leftValues.includes(assistantId) && left.value !== assistantId) {
        left.value = assistantId;
      } else if (rightValues.includes(assistantId)) {
        right.value = assistantId;
      }
      loadAssistantCompare(
        document.getElementById("assistantCompareRun").value,
        left.value,
        right.value
      );
    }

    async function loadRunCompare(leftRun, rightRun) {
      const target = document.getElementById("runCompare");
      if (!leftRun || !rightRun) {
        target.innerHTML = `<div class="detail-card"><h3>Comparison</h3><div class="detail-pre">Select two runs.</div></div>`;
        return;
      }
      const response = await fetch("/api/run-compare?left=" + encodeURIComponent(leftRun) + "&right=" + encodeURIComponent(rightRun));
      const data = await response.json();
      if (data.error) {
        target.innerHTML = `<div class="detail-card"><h3>Error</h3><div class="detail-pre">${escapeHtml(data.error)}</div></div>`;
        return;
      }
      target.innerHTML = `
        <div class="detail-card"><h3>Deployment Class</h3><div class="detail-pre">Left: ${escapeHtml(String(data.deployment_class.left))}\nRight: ${escapeHtml(String(data.deployment_class.right))}</div></div>
        <div class="detail-card"><h3>Operator Review Burden</h3><div class="detail-pre">Left: ${escapeHtml(String(data.operator_review_burden.left))}\nRight: ${escapeHtml(String(data.operator_review_burden.right))}</div></div>
        <div class="detail-card"><h3>Task Fit</h3><div class="detail-pre">${escapeHtml(JSON.stringify(data.task_fit, null, 2))}</div></div>
        <div class="detail-card"><h3>Failure Families</h3><div class="detail-pre">${escapeHtml(JSON.stringify(data.failure_families, null, 2))}</div></div>
        <div class="detail-card"><h3>Negative Lanes</h3><div class="detail-pre">${escapeHtml(JSON.stringify(data.negative_lane_ids, null, 2))}</div></div>
        <div class="detail-card"><h3>Assistant Review Present</h3><div class="detail-pre">Left: ${escapeHtml(String(data.assistant_review_present.left))}\nRight: ${escapeHtml(String(data.assistant_review_present.right))}</div></div>
        <div class="detail-card"><h3>Assistant Cleanup Signal</h3><div class="detail-pre">${escapeHtml(JSON.stringify(data.assistant_review_cleanup, null, 2))}</div></div>
        <div class="detail-card"><h3>Assistant Cleanup By ID</h3><div class="detail-pre">${escapeHtml(JSON.stringify(data.assistant_review_cleanup_by_id, null, 2))}</div></div>
        <div class="detail-card"><h3>Strengths</h3><div class="detail-pre">${escapeHtml(JSON.stringify(data.strengths, null, 2))}</div></div>
        <div class="detail-card"><h3>Weaknesses</h3><div class="detail-pre">${escapeHtml(JSON.stringify(data.weaknesses, null, 2))}</div></div>
      `;
    }

    async function loadAssistantCompare(runPath, leftAssistant, rightAssistant) {
      const target = document.getElementById("assistantCompare");
      if (!runPath || !leftAssistant || !rightAssistant) {
        target.innerHTML = `<div class="detail-card"><h3>Assistant Comparison</h3><div class="detail-pre">Select a run and two assistants.</div></div>`;
        return;
      }
      const response = await fetch(
        "/api/assistant-compare?run=" + encodeURIComponent(runPath)
        + "&left=" + encodeURIComponent(leftAssistant)
        + "&right=" + encodeURIComponent(rightAssistant)
      );
      const data = await response.json();
      if (data.error) {
        target.innerHTML = `<div class="detail-card"><h3>Error</h3><div class="detail-pre">${escapeHtml(data.error)}</div></div>`;
        return;
      }
      target.innerHTML = `
        <div class="detail-card"><h3>Evaluator Fit Summary</h3><div class="detail-pre">${escapeHtml(JSON.stringify(data.fit_summary, null, 2))}</div></div>
        <div class="detail-card"><h3>Evaluator Fitness Score</h3><div class="detail-pre">${escapeHtml(JSON.stringify({left: data.left.evaluator_fitness, right: data.right.evaluator_fitness}, null, 2))}</div></div>
        <div class="detail-card"><h3>Validation Outcome</h3><div class="detail-pre">Left: ${escapeHtml(String(data.left.validation_passed))}\nRight: ${escapeHtml(String(data.right.validation_passed))}</div></div>
        <div class="detail-card"><h3>Attempt Count</h3><div class="detail-pre">Left: ${escapeHtml(String(data.left.attempt_count))}\nRight: ${escapeHtml(String(data.right.attempt_count))}</div></div>
        <div class="detail-card"><h3>Salvage Needed</h3><div class="detail-pre">Left: ${escapeHtml(String(data.left.had_salvage))}\nRight: ${escapeHtml(String(data.right.had_salvage))}</div></div>
        <div class="detail-card"><h3>Leading Prose</h3><div class="detail-pre">${escapeHtml(JSON.stringify({left: data.left.leading_prose, right: data.right.leading_prose}, null, 2))}</div></div>
        <div class="detail-card"><h3>Final Issues</h3><div class="detail-pre">${escapeHtml(JSON.stringify({left: data.left.final_issues, right: data.right.final_issues}, null, 2))}</div></div>
        <div class="detail-card"><h3>Validation Failure Payload</h3><div class="detail-pre">${escapeHtml(JSON.stringify({left: data.left.validation_failure, right: data.right.validation_failure}, null, 2))}</div></div>
      `;
    }

    function escapeHtml(text) {
      return text
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;");
    }

    function escapeJs(text) {
      return text
        .replaceAll("\\\\", "\\\\\\\\")
        .replaceAll("'", "\\\\'");
    }

    async function postJson(url, payload, targetId) {
      const target = document.getElementById(targetId);
      target.textContent = "Working...";
      const response = await fetch(url, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload)
      });
      const data = await response.json();
      target.textContent = data.output || JSON.stringify(data, null, 2);
      await loadStatus();
    }

    async function setProbeRequestDecision(failureFamily, decision) {
      let note = "";
      if (decision === "confirmed_for_forge") {
        note = prompt("Operator note for confirmed forge draft:", "") || "";
      } else if (decision === "probe_candidate") {
        note = prompt("Optional note for probe candidate:", "") || "";
      }
      await postJson("/api/probe-request-decision", {
        failure_family: failureFamily,
        decision: decision,
        note: note
      }, "runStatus");
    }

    document.getElementById("preflightRun").addEventListener("click", () => postJson("/api/preflight-run", {
      model: document.getElementById("modelConfig").value
    }, "runStatus"));

    document.getElementById("runMockGood").addEventListener("click", () => postJson("/api/run-mock-preset", {
      mode: "good"
    }, "runStatus"));

    document.getElementById("runMockMixed").addEventListener("click", () => postJson("/api/run-mock-preset", {
      mode: "mixed"
    }, "runStatus"));

    document.getElementById("runMockBad").addEventListener("click", () => postJson("/api/run-mock-preset", {
      mode: "bad"
    }, "runStatus"));

    document.getElementById("startRun").addEventListener("click", () => postJson("/api/run", {
      model: document.getElementById("modelConfig").value,
      host: document.getElementById("hostConfig").value,
      task_pack: document.getElementById("taskPack").value,
      out: document.getElementById("outDir").value
    }, "runStatus"));

    document.getElementById("preflightReview").addEventListener("click", () => postJson("/api/preflight-review", {
      run_dir: document.getElementById("runSelect").value,
      assistant_id: document.getElementById("assistantSelect").value
    }, "reviewStatus"));

    document.getElementById("startReview").addEventListener("click", () => postJson("/api/assistant-review", {
      run_dir: document.getElementById("runSelect").value,
      assistant_id: document.getElementById("assistantSelect").value
    }, "reviewStatus"));

    document.getElementById("detailRunSelect").addEventListener("change", (event) => {
      loadRunDetail(event.target.value);
    });

    document.getElementById("compareLeftRun").addEventListener("change", () => {
      loadRunCompare(
        document.getElementById("compareLeftRun").value,
        document.getElementById("compareRightRun").value
      );
    });

    document.getElementById("compareRightRun").addEventListener("change", () => {
      loadRunCompare(
        document.getElementById("compareLeftRun").value,
        document.getElementById("compareRightRun").value
      );
    });

    document.getElementById("assistantCompareRun").addEventListener("change", (event) => {
      fetch("/api/status")
        .then(response => response.json())
        .then(data => syncAssistantCompareOptions(event.target.value, data.assistants || []));
    });

    document.getElementById("assistantCompareLeft").addEventListener("change", () => {
      loadAssistantCompare(
        document.getElementById("assistantCompareRun").value,
        document.getElementById("assistantCompareLeft").value,
        document.getElementById("assistantCompareRight").value
      );
    });

    document.getElementById("assistantCompareRight").addEventListener("change", () => {
      loadAssistantCompare(
        document.getElementById("assistantCompareRun").value,
        document.getElementById("assistantCompareLeft").value,
        document.getElementById("assistantCompareRight").value
      );
    });

    document.getElementById("assistantFitSort").addEventListener("change", () => {
      fetch("/api/status")
        .then(response => response.json())
        .then(data => renderAssistantFitAggregate(data.assistant_fit_index || {aggregate: {}}));
    });

    document.getElementById("gauntletFamilySort").addEventListener("change", () => {
      fetch("/api/status")
        .then(response => response.json())
        .then(data => renderGauntletFamilyAggregate(data.gauntlet_history_index || {aggregate: {failure_families: {}}}));
    });

    loadStatus();
    setInterval(loadStatus, 2000);
  </script>
</body>
</html>
"""


class DashboardHandler(BaseHTTPRequestHandler):
    repo_root: Path
    job_manager: JobManager

    def _send_json(self, payload: dict[str, Any], status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8") if length else "{}"
        return json.loads(raw)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/":
            body = DASHBOARD_HTML.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == "/api/status":
            status = build_dashboard_status(self.repo_root)
            status["jobs"] = self.job_manager.list_jobs()
            self._send_json(status)
            return
        if self.path.startswith("/api/run-detail?"):
            from urllib.parse import parse_qs, urlparse

            query = parse_qs(urlparse(self.path).query)
            run_path = query.get("run", [""])[0]
            self._send_json(read_run_details(self.repo_root, run_path))
            return
        if self.path.startswith("/api/run-compare?"):
            from urllib.parse import parse_qs, urlparse

            query = parse_qs(urlparse(self.path).query)
            left = query.get("left", [""])[0]
            right = query.get("right", [""])[0]
            self._send_json(compare_runs(self.repo_root, left, right))
            return
        if self.path.startswith("/api/assistant-compare?"):
            from urllib.parse import parse_qs, urlparse

            query = parse_qs(urlparse(self.path).query)
            run_path = query.get("run", [""])[0]
            left = query.get("left", [""])[0]
            right = query.get("right", [""])[0]
            self._send_json(compare_assistant_reviews_within_run(self.repo_root, run_path, left, right))
            return
        self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        payload = self._read_json()
        try:
            if self.path == "/api/preflight-run":
                from .preflight import preflight_model_config, render_check_results

                results = preflight_model_config(self.repo_root, Path(payload["model"]), False)
                self._send_json({"output": render_check_results(results)})
                return
            if self.path == "/api/preflight-review":
                from .preflight import render_check_results

                run_dir = self.repo_root / payload["run_dir"]
                results = preflight_run_folder(run_dir)
                results.extend(
                    preflight_catalog_entry(self.repo_root, "assistant", payload["assistant_id"], False)
                )
                self._send_json({"output": render_check_results(results)})
                return
            if self.path == "/api/run":
                def action() -> str:
                    model = load_model_config(self.repo_root / payload["model"])
                    host = load_host_profile(self.repo_root / payload["host"])
                    task_pack = load_task_pack(self.repo_root / payload["task_pack"])
                    out_dir = self.repo_root / payload["out"]
                    ProbeRunner(self.repo_root, model, host, task_pack, out_dir).run()
                    return f"Run completed: {out_dir}"

                job = self.job_manager.enqueue("run", payload, action)
                self._send_json({"output": f"Run queued: {job['job_id']}", "job": job})
                return
            if self.path == "/api/run-mock-preset":
                def action() -> str:
                    mode = str(payload["mode"])
                    runner = build_mock_preset_runner(self.repo_root, mode)
                    runner.run()
                    return f"Mock preset run completed: runs/mock_{mode}"

                job = self.job_manager.enqueue("run-mock-preset", payload, action)
                self._send_json({"output": f"Mock preset queued: {job['job_id']}", "job": job})
                return
            if self.path == "/api/assistant-review":
                def action() -> str:
                    result = run_assistant_review(
                        self.repo_root,
                        self.repo_root / payload["run_dir"],
                        payload["assistant_id"],
                    )
                    return f"Assistant review written: {result.output_path}"

                job = self.job_manager.enqueue("assistant-review", payload, action)
                self._send_json({"output": f"Assistant review queued: {job['job_id']}", "job": job})
                return
            if self.path == "/api/probe-request-decision":
                upsert_probe_request_decision(
                    self.repo_root,
                    str(payload["failure_family"]),
                    str(payload["decision"]),
                    str(payload.get("note", "") or ""),
                )
                rebuild_gauntlet_history_index(self.repo_root)
                rebuild_probe_forge_drafts(self.repo_root)
                materialize_probe_draft_files(self.repo_root)
                self._send_json({"output": f"Updated decision for {payload['failure_family']}: {payload['decision']}"})
                return
        except Exception as exc:  # noqa: BLE001
            self._send_json({"error": str(exc), "output": f"Error: {exc}"}, status=HTTPStatus.BAD_REQUEST)
            return
        self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return


def run_dashboard_server(repo_root: Path, host: str, port: int) -> ThreadingHTTPServer:
    handler = type(
        "RepoDashboardHandler",
        (DashboardHandler,),
        {"repo_root": repo_root, "job_manager": JobManager()},
    )
    server = ThreadingHTTPServer((host, port), handler)
    return server
