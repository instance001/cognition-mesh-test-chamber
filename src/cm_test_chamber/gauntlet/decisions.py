from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


VALID_DECISIONS = {
    "monitor_only",
    "probe_candidate",
    "probe_needed",
    "confirmed_for_forge",
    "dismissed",
}


def _decision_registry_path(repo_root: Path) -> Path:
    return repo_root / "runs" / "probe_request_decisions.json"


def read_probe_request_decisions(repo_root: Path) -> dict[str, Any]:
    path = _decision_registry_path(repo_root)
    if not path.exists():
        return {"entries": []}
    return json.loads(path.read_text(encoding="utf-8"))


def write_probe_request_decisions(repo_root: Path, payload: dict[str, Any]) -> Path:
    path = _decision_registry_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def upsert_probe_request_decision(
    repo_root: Path,
    failure_family: str,
    decision: str,
    note: str | None = None,
) -> Path:
    if decision not in VALID_DECISIONS:
        raise ValueError(f"Unsupported decision: {decision}")
    payload = read_probe_request_decisions(repo_root)
    entries = payload.setdefault("entries", [])
    now = datetime.now(timezone.utc).isoformat()
    for entry in entries:
        if entry.get("failure_family") == failure_family:
            entry["decision"] = decision
            entry["note"] = note or ""
            entry["updated_at"] = now
            break
    else:
        entries.append(
            {
                "failure_family": failure_family,
                "decision": decision,
                "note": note or "",
                "updated_at": now,
            }
        )
    entries.sort(key=lambda item: item.get("failure_family", ""))
    return write_probe_request_decisions(repo_root, payload)
