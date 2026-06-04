from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import PurePosixPath


@dataclass(frozen=True)
class Finding:
    path: str
    reason: str


ROOT_DIRS = {
    ".mypy_cache": "cache directory",
    ".pytest_cache": "pytest cache directory",
    ".ruff_cache": "ruff cache directory",
    "app_data": "runtime application data",
    "build": "build output",
    "dist": "packaged distribution output",
    "e2e-artifacts": "browser/e2e artifact output",
    "logs": "runtime log output",
    "outputs": "runtime report/model output",
    "test-results": "test result artifact output",
    "_sn_runtime": "local runtime directory",
    "_sn_setup_runtime": "local setup runtime directory",
}

ANY_SEGMENT_DIRS = {
    "__pycache__": "Python bytecode cache",
    ".pytest_cache": "pytest cache directory",
    "logs": "runtime log output",
}

FORBIDDEN_SUFFIXES = {
    ".sqlite": "SQLite database",
    ".sqlite3": "SQLite database",
    ".db": "database file",
    ".pyc": "Python bytecode cache",
    ".pyo": "Python bytecode cache",
}

FORBIDDEN_FILENAMES = {
    "runtime_state.json": "runtime state file",
    "server_session.json": "runtime server session file",
    "server_port.json": "runtime server port file",
}


def normalize_path(path: str) -> str:
    return path.strip().replace("\\", "/")


def classify_forbidden_path(path: str) -> Finding | None:
    normalized = normalize_path(path)
    if not normalized:
        return None

    parts = PurePosixPath(normalized).parts
    if not parts:
        return None

    first = parts[0]
    if first in ROOT_DIRS:
        return Finding(normalized, ROOT_DIRS[first])

    if first.startswith("tmp_"):
        return Finding(normalized, "temporary workspace artifact")

    for part in parts:
        if part in ANY_SEGMENT_DIRS:
            return Finding(normalized, ANY_SEGMENT_DIRS[part])
        if part.startswith("tmp_"):
            return Finding(normalized, "temporary workspace artifact")

    filename = parts[-1]
    if filename in FORBIDDEN_FILENAMES:
        return Finding(normalized, FORBIDDEN_FILENAMES[filename])

    if normalized.endswith(".sqlite-journal"):
        return Finding(normalized, "SQLite journal file")

    suffix = PurePosixPath(normalized).suffix.lower()
    if suffix in FORBIDDEN_SUFFIXES:
        return Finding(normalized, FORBIDDEN_SUFFIXES[suffix])

    if normalized.startswith("release/") and filename.lower().endswith(".exe"):
        return Finding(normalized, "release installer should be published as a release asset")

    if normalized == "release/SHA256SUMS.txt":
        return Finding(normalized, "local release checksum artifact")

    if normalized.startswith("frontend/dist/"):
        return Finding(normalized, "frontend build output")

    return None


def find_forbidden_paths(paths: list[str]) -> list[Finding]:
    findings = []
    for path in paths:
        finding = classify_forbidden_path(path)
        if finding is not None:
            findings.append(finding)
    return findings


def tracked_files_from_git() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        raise SystemExit(result.returncode)
    return result.stdout.splitlines()


def paths_from_stdin() -> list[str]:
    return sys.stdin.read().splitlines()


def print_findings(findings: list[Finding]) -> None:
    print("FAIL: forbidden tracked runtime/artifact/release files were found.")
    print("失败: git 已跟踪运行态/构建产物/安装包/数据库/缓存文件。")
    print("These files must stay local; remove them from the index with git rm --cached.")
    print()
    for finding in findings:
        print(f"- {finding.path}  [{finding.reason}]")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fail if git-tracked files include runtime, build, release, database, or cache artifacts."
    )
    parser.add_argument(
        "--stdin",
        action="store_true",
        help="Read tracked-path candidates from stdin instead of git ls-files. Useful for tests.",
    )
    args = parser.parse_args(argv)

    paths = paths_from_stdin() if args.stdin else tracked_files_from_git()
    findings = find_forbidden_paths(paths)
    if findings:
        print_findings(findings)
        return 1

    print("PASS: repository cleanliness check passed.")
    print("通过: git tracked 文件未包含运行态/构建产物/安装包/数据库/缓存。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
