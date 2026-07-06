from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class MockSandbox:
    source_root: Path
    temp_root: Path
    repo_root: Path
    manifest: set[str]

    @classmethod
    def from_fixture(cls, fixture_root: Path) -> "MockSandbox":
        temp_root = Path(tempfile.mkdtemp(prefix="cm_sandbox_"))
        repo_root = temp_root / fixture_root.name
        shutil.copytree(fixture_root, repo_root)
        manifest = {
            path.relative_to(repo_root).as_posix()
            for path in repo_root.rglob("*")
            if path.is_file()
        }
        return cls(source_root=fixture_root, temp_root=temp_root, repo_root=repo_root, manifest=manifest)

    def resolve_checked(self, relative_path: str) -> Path:
        candidate = (self.repo_root / relative_path).resolve()
        if self.repo_root.resolve() not in candidate.parents and candidate != self.repo_root.resolve():
            raise ValueError(f"Path escapes sandbox root: {relative_path}")
        return candidate

    def cleanup(self) -> None:
        shutil.rmtree(self.temp_root, ignore_errors=True)
