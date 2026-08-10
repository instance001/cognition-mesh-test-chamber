import sys
from pathlib import Path

import pytest

from cm_test_chamber.app_paths import APP_LAYOUT_DIRS, ensure_app_layout, resolve_app_root
from cm_test_chamber.cli import main


def test_ensure_app_layout_bootstraps_binary_first_run_layout(tmp_path):
    ensure_app_layout(tmp_path)

    for relative_path in APP_LAYOUT_DIRS:
        assert (tmp_path / relative_path).is_dir()


def test_resolve_app_root_uses_executable_parent_when_frozen(tmp_path, monkeypatch):
    exe_path = tmp_path / "dist" / "cm-test-chamber.exe"
    exe_path.parent.mkdir()
    exe_path.write_text("", encoding="utf-8")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe_path))

    assert resolve_app_root(Path(__file__)) == exe_path.parent.resolve()


def test_cli_bootstraps_layout_before_argparse_exits_for_no_args(tmp_path, monkeypatch):
    exe_path = tmp_path / "dist" / "cm-test-chamber.exe"
    exe_path.parent.mkdir()
    exe_path.write_text("", encoding="utf-8")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe_path))

    with pytest.raises(SystemExit):
        main([])

    for relative_path in APP_LAYOUT_DIRS:
        assert (exe_path.parent / relative_path).is_dir()
