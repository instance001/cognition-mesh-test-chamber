from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .decisions import read_probe_request_decisions


def _gauntlet_history_index_path(repo_root: Path) -> Path:
    return repo_root / "runs" / "gauntlet_history_index.json"


def build_gauntlet_history_aggregate(index_payload: dict[str, Any]) -> dict[str, Any]:
    decisions_map = {
        entry.get("failure_family"): entry
        for entry in (index_payload.get("probe_request_decisions") or {}).get("entries", [])
        if entry.get("failure_family")
    }
    failure_family_summary: dict[str, dict[str, Any]] = {}
    model_summary: dict[str, dict[str, Any]] = {}
    for entry in index_payload.get("entries", []):
        model_name = entry.get("model_name") or "unknown"
        model_metrics = model_summary.setdefault(
            model_name,
            {
                "runs": 0,
                "score_total": 0.0,
                "average_score": 0.0,
                "systemic_failures": 0,
                "flaky_failures": 0,
                "host_sensitive_failures": 0,
                "soft_failures": 0,
                "probe_needed_count": 0,
            },
        )
        model_metrics["runs"] += 1
        model_metrics["score_total"] += float(entry.get("overall_score") or 0.0)
        model_metrics["systemic_failures"] += int(entry.get("systemic_failures") or 0)
        model_metrics["flaky_failures"] += int(entry.get("flaky_failures") or 0)
        model_metrics["host_sensitive_failures"] += int(entry.get("host_sensitive_failures") or 0)
        model_metrics["soft_failures"] += int(entry.get("soft_failures") or 0)
        model_metrics["probe_needed_count"] += sum(
            1 for item in entry.get("candidate_probe_requests", []) if item.get("recommendation") == "probe_needed"
        )

        for request in entry.get("candidate_probe_requests", []):
            family = request.get("failure_family") or "unknown"
            family_metrics = failure_family_summary.setdefault(
                family,
                {
                    "appearances": 0,
                    "probe_needed_count": 0,
                    "systemic_count": 0,
                    "flaky_count": 0,
                    "host_sensitive_count": 0,
                    "soft_count": 0,
                    "observed_only_count": 0,
                    "fail_count_total": 0,
                    "pass_count_total": 0,
                    "highest_severity": "low",
                    "models_seen": [],
                    "latest_retry_observation": "not_run",
                    "operator_decision": "unreviewed",
                    "operator_note": "",
                },
            )
            family_metrics["appearances"] += 1
            family_metrics["fail_count_total"] += int(request.get("fail_count") or 0)
            family_metrics["pass_count_total"] += int(request.get("pass_count") or 0)
            classification = request.get("classification") or "unknown"
            if classification == "systemic":
                family_metrics["systemic_count"] += 1
            elif classification == "flaky":
                family_metrics["flaky_count"] += 1
            elif classification == "host_sensitive":
                family_metrics["host_sensitive_count"] += 1
            elif classification == "soft":
                family_metrics["soft_count"] += 1
            elif classification == "observed_only":
                family_metrics["observed_only_count"] += 1
            if request.get("recommendation") == "probe_needed":
                family_metrics["probe_needed_count"] += 1
            if model_name not in family_metrics["models_seen"]:
                family_metrics["models_seen"].append(model_name)
            severity = request.get("severity") or "low"
            if _severity_rank(severity) > _severity_rank(family_metrics["highest_severity"]):
                family_metrics["highest_severity"] = severity
            family_metrics["latest_retry_observation"] = request.get("retry_observation") or "not_run"

    for model_name, metrics in model_summary.items():
        if metrics["runs"] > 0:
            metrics["average_score"] = round(metrics["score_total"] / metrics["runs"], 4)
        metrics["rationale"] = _model_rationale(metrics)
    for family, metrics in failure_family_summary.items():
        metrics["models_seen"].sort()
        decision_entry = decisions_map.get(family) or {}
        metrics["operator_decision"] = decision_entry.get("decision", "unreviewed")
        metrics["operator_note"] = decision_entry.get("note", "")
        metrics["rationale"] = _failure_family_rationale(family, metrics)
    return {
        "failure_families": failure_family_summary,
        "models": model_summary,
    }


def rebuild_gauntlet_history_index(repo_root: Path) -> Path:
    runs_root = repo_root / "runs"
    entries: list[dict[str, Any]] = []
    if runs_root.exists():
        for child in sorted(runs_root.iterdir(), key=lambda item: item.name):
            if not child.is_dir():
                continue
            scores_path = child / "gauntlet_scores.json"
            if not scores_path.exists():
                continue
            fingerprint_path = child / "gauntlet_fingerprint.json"
            summary_path = child / "gauntlet_summary.md"
            requests_path = child / "gauntlet_candidate_probe_requests.json"
            snapshot_path = child / "gauntlet_run_config_snapshot.json"
            scores = json.loads(scores_path.read_text(encoding="utf-8"))
            fingerprint = json.loads(fingerprint_path.read_text(encoding="utf-8")) if fingerprint_path.exists() else {}
            candidate_probe_requests = (
                json.loads(requests_path.read_text(encoding="utf-8")) if requests_path.exists() else []
            )
            snapshot = json.loads(snapshot_path.read_text(encoding="utf-8")) if snapshot_path.exists() else {}
            entries.append(
                {
                    "run_name": child.name,
                    "run_path": child.relative_to(repo_root).as_posix(),
                    "gauntlet_id": scores.get("gauntlet_id"),
                    "model_name": (snapshot.get("model") or {}).get("model_name"),
                    "retry_policy": scores.get("retry_policy") or snapshot.get("retry_policy"),
                    "overall_score": scores.get("overall_score"),
                    "turn_count": len(scores.get("turns", [])),
                    "weakest_lane": fingerprint.get("weakest_lane"),
                    "most_repeated_failure_family": fingerprint.get("most_repeated_failure_family"),
                    "systemic_failures": fingerprint.get("systemic_failures", 0),
                    "flaky_failures": fingerprint.get("flaky_failures", 0),
                    "host_sensitive_failures": fingerprint.get("host_sensitive_failures", 0),
                    "soft_failures": fingerprint.get("soft_failures", 0),
                    "candidate_probe_requests": candidate_probe_requests,
                    "summary_path": summary_path.relative_to(repo_root).as_posix() if summary_path.exists() else None,
                    "updated_at": scores_path.stat().st_mtime,
                }
            )
    index_payload = {
        "entries": entries,
        "probe_request_decisions": read_probe_request_decisions(repo_root),
    }
    index_payload["aggregate"] = build_gauntlet_history_aggregate(index_payload)
    index_path = _gauntlet_history_index_path(repo_root)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps(index_payload, indent=2) + "\n", encoding="utf-8")
    return index_path


def read_or_rebuild_gauntlet_history_index(repo_root: Path) -> dict[str, Any]:
    index_path = _gauntlet_history_index_path(repo_root)
    if not index_path.exists():
        rebuild_gauntlet_history_index(repo_root)
    if not index_path.exists():
        return {
            "entries": [],
            "probe_request_decisions": {"entries": []},
            "aggregate": {"failure_families": {}, "models": {}},
        }
    return json.loads(index_path.read_text(encoding="utf-8"))


def _severity_rank(label: str) -> int:
    return {"low": 1, "moderate": 2, "high": 3, "critical": 4}.get(label, 0)


def _model_rationale(metrics: dict[str, Any]) -> str:
    pieces: list[str] = []
    if metrics["runs"] > 0:
        pieces.append(f"{metrics['runs']} gauntlet run(s)")
        pieces.append(f"average score {metrics['average_score']}")
    if metrics["systemic_failures"] > 0:
        pieces.append(f"{metrics['systemic_failures']} systemic failure bucket(s)")
    if metrics["flaky_failures"] > 0:
        pieces.append(f"{metrics['flaky_failures']} flaky failure bucket(s)")
    if metrics["host_sensitive_failures"] > 0:
        pieces.append(f"{metrics['host_sensitive_failures']} host-sensitive bucket(s)")
    if metrics["probe_needed_count"] > 0:
        pieces.append(f"{metrics['probe_needed_count']} probe-needed signal(s)")
    return "; ".join(pieces) if pieces else "no historical gauntlet signal yet"


def _failure_family_rationale(family: str, metrics: dict[str, Any]) -> str:
    pieces = [f"{family} appeared {metrics['appearances']} time(s)"]
    if metrics["systemic_count"] > 0:
        pieces.append(f"{metrics['systemic_count']} systemic")
    if metrics["flaky_count"] > 0:
        pieces.append(f"{metrics['flaky_count']} flaky")
    if metrics["host_sensitive_count"] > 0:
        pieces.append(f"{metrics['host_sensitive_count']} host-sensitive")
    if metrics["probe_needed_count"] > 0:
        pieces.append(f"{metrics['probe_needed_count']} probe-needed")
    if metrics["models_seen"]:
        pieces.append(f"models: {', '.join(metrics['models_seen'])}")
    return "; ".join(pieces)
