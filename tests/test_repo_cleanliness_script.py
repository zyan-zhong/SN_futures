from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_repo_cleanliness_script_flags_forbidden_tracked_paths_from_stdin() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/check_repo_cleanliness.py", "--stdin"],
        input="src/sn_futures/data.py\napp_data/runtime/server_session.json\n",
        text=True,
        capture_output=True,
        check=False,
    )

    combined_output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "app_data/runtime/server_session.json" in combined_output
    assert "runtime" in combined_output.lower()


def test_quality_gate_runs_repo_cleanliness_check() -> None:
    quality_gate = Path("scripts/quality_gate.ps1").read_text(encoding="utf-8")

    assert "repo cleanliness" in quality_gate
    assert "scripts\\check_repo_cleanliness.py" in quality_gate
