from __future__ import annotations

import sys
from pathlib import Path


APP_LAYOUT_DIRS: tuple[str, ...] = (
    "configs",
    "configs/catalogs",
    "configs/gauntlets",
    "configs/hosts",
    "configs/models",
    "configs/task_profiles",
    "probes",
    "local_probes",
    "local_probes/drafts",
    "negative_lanes",
    "negative_lanes/generated",
    "runs",
    "reports",
    "runtime",
    "model_under_test",
    "assistant_models",
    "sandbox",
    "sandbox/fake_filesystem",
    "sandbox/fake_filesystem/sample_repo",
)


def resolve_app_root(anchor_file: Path | None = None) -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return (anchor_file or Path(__file__)).resolve().parents[2]


def app_layout_path(app_root: Path, relative_path: str) -> Path:
    return app_root / Path(relative_path)


def ensure_app_layout(app_root: Path) -> None:
    for relative_path in APP_LAYOUT_DIRS:
        app_layout_path(app_root, relative_path).mkdir(parents=True, exist_ok=True)
