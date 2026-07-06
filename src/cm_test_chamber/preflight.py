from __future__ import annotations

import json
import socket
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from .model_catalog import CatalogModel, load_catalog


@dataclass(slots=True)
class CheckResult:
    name: str
    ok: bool
    detail: str


def _endpoint_reachable(endpoint: str, timeout_seconds: float = 1.0) -> tuple[bool, str]:
    parsed = urlparse(endpoint)
    host = parsed.hostname
    port = parsed.port
    if not host or not port:
        return False, f"Invalid endpoint: {endpoint}"
    try:
        with socket.create_connection((host, port), timeout=timeout_seconds):
            return True, f"Reachable: {host}:{port}"
    except OSError as exc:
        return False, f"Unreachable: {host}:{port} ({exc})"


def _catalog_filename(role: str) -> str:
    if role == "assistant":
        return "assistant_models.json"
    if role == "model_under_test":
        return "models_under_test.json"
    raise ValueError(f"Unsupported role: {role}")


def load_catalog_entry(repo_root: Path, role: str, model_id: str) -> CatalogModel:
    catalog = load_catalog(repo_root / "configs" / "catalogs" / _catalog_filename(role))
    entry = next((item for item in catalog.models if item.id == model_id), None)
    if entry is None:
        raise ValueError(f"Unknown {role} id: {model_id}")
    return entry


def preflight_catalog_entry(repo_root: Path, role: str, model_id: str, check_endpoint: bool) -> list[CheckResult]:
    entry = load_catalog_entry(repo_root, role, model_id)
    file_path = repo_root / entry.file_path
    results = [
        CheckResult(
            name=f"{role}_catalog_entry",
            ok=True,
            detail=f"Loaded catalog entry: {entry.id}",
        ),
        CheckResult(
            name=f"{role}_model_file",
            ok=file_path.exists(),
            detail=f"Found model file: {entry.file_path}" if file_path.exists() else f"Missing model file: {entry.file_path}",
        ),
    ]
    if check_endpoint:
        ok, detail = _endpoint_reachable(entry.recommended_endpoint)
        results.append(CheckResult(name=f"{role}_endpoint", ok=ok, detail=detail))
    return results


def preflight_run_folder(run_dir: Path) -> list[CheckResult]:
    required = [
        "cognitive_fingerprint.json",
        "report.md",
        "probe_results.jsonl",
    ]
    results: list[CheckResult] = [
        CheckResult(
            name="run_dir",
            ok=run_dir.exists() and run_dir.is_dir(),
            detail=f"Found run directory: {run_dir}" if run_dir.exists() and run_dir.is_dir() else f"Missing run directory: {run_dir}",
        )
    ]
    for filename in required:
        path = run_dir / filename
        results.append(
            CheckResult(
                name=f"run_artifact:{filename}",
                ok=path.exists(),
                detail=f"Found {filename}" if path.exists() else f"Missing {filename}",
            )
        )
    return results


def preflight_model_config(repo_root: Path, config_path: Path, check_endpoint: bool) -> list[CheckResult]:
    target = repo_root / config_path
    results = [
        CheckResult(
            name="model_config",
            ok=target.exists(),
            detail=f"Found config: {config_path}" if target.exists() else f"Missing config: {config_path}",
        )
    ]
    if not target.exists():
        return results

    payload = json.loads(target.read_text(encoding="utf-8"))
    backend = payload.get("backend")
    results.append(
        CheckResult(
            name="model_backend",
            ok=backend in {"mock", "local_http"},
            detail=f"Backend: {backend}",
        )
    )
    if check_endpoint and backend == "local_http":
        endpoint = payload.get("endpoint", "")
        ok, detail = _endpoint_reachable(endpoint)
        results.append(CheckResult(name="model_endpoint", ok=ok, detail=detail))
    return results


def render_check_results(results: list[CheckResult]) -> str:
    lines: list[str] = []
    for result in results:
        status = "PASS" if result.ok else "FAIL"
        lines.append(f"[{status}] {result.name}: {result.detail}")
    overall = "PASS" if all(item.ok for item in results) else "FAIL"
    lines.append("")
    lines.append(f"Overall: {overall}")
    return "\n".join(lines) + "\n"
