from __future__ import annotations

import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TMP_ROOT = ROOT / "tmp_test_runs" / "pytest_temp"


class WorkspaceTemporaryDirectory:
    """TempDirectory replacement for workspace-write Windows sandboxes."""

    def __init__(
        self,
        suffix: str | None = None,
        prefix: str | None = None,
        dir: str | None = None,
        ignore_cleanup_errors: bool = False,
        **_: Any,
    ) -> None:
        root = Path(dir) if dir else TMP_ROOT
        root.mkdir(parents=True, exist_ok=True)
        self._ignore_cleanup_errors = ignore_cleanup_errors
        name = f"{prefix or 'tmp'}{uuid.uuid4().hex}{suffix or ''}"
        self.name = str(root / name)
        Path(self.name).mkdir(parents=True, exist_ok=True)

    def __enter__(self) -> str:
        return self.name

    def __exit__(self, *_: Any) -> None:
        self.cleanup()

    def cleanup(self) -> None:
        shutil.rmtree(self.name, ignore_errors=True or self._ignore_cleanup_errors)


tempfile.TemporaryDirectory = WorkspaceTemporaryDirectory  # type: ignore[assignment]
