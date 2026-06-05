from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Iterable


class GateOptions:
    def __init__(
        self,
        *,
        python: str | None = None,
        npm: str = "npm",
        skip_e2e: bool = False,
        skip_frontend: bool = False,
        skip_frontend_build: bool = False,
        skip_pytest: bool = False,
        only_scans: bool = False,
        continue_on_error: bool = False,
    ) -> None:
        self.python = python or sys.executable
        self.npm = npm
        self.skip_e2e = skip_e2e
        self.skip_frontend = skip_frontend
        self.skip_frontend_build = skip_frontend_build
        self.skip_pytest = skip_pytest
        self.only_scans = only_scans
        self.continue_on_error = continue_on_error


class GateStep:
    def __init__(
        self,
        name: str,
        *,
        command: list[str] | None = None,
        cwd: Path | None = None,
        internal: str | None = None,
    ) -> None:
        self.name = name
        self.command = command
        self.cwd = cwd
        self.internal = internal


class Finding:
    def __init__(self, path: Path, reason: str, *, line: int | None = None) -> None:
        self.path = path
        self.reason = reason
        self.line = line

    def format(self, root: Path | None = None) -> str:
        path = self.path
        if root is not None:
            try:
                path = self.path.resolve().relative_to(root.resolve())
            except Exception:
                path = self.path
        suffix = f":{self.line}" if self.line else ""
        return f"{path}{suffix} - {self.reason}"


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = PROJECT_ROOT / "frontend"

SECRET_ENV_NAMES = (
    "SN_ALPHA_VANTAGE_KEY",
    "SN_NEWSAPI_KEY",
    "SN_TUSHARE_TOKEN",
    "SN_LOCAL_API_PROVIDER_TOKEN",
    "SN_MANAGED_PROXY_TOKEN",
    "SN_MANAGED_DATA_PROXY_TOKEN",
)

TEXT_SUFFIXES = {
    ".css",
    ".html",
    ".js",
    ".jsx",
    ".json",
    ".md",
    ".mjs",
    ".ps1",
    ".py",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}

SKIP_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "node_modules",
    "venv",
}

REAL_RESULT_DIRS = (
    "outputs",
    "app_data",
    "build",
    "dist",
    "release",
    "frontend/dist",
)

RELEASE_SCAN_DIRS = (
    "release",
    "dist",
    "build/SNInsightTerminal",
    "frontend/dist",
)

DIRTY_DATA_FLAGS = (
    "sample_data_used",
    "sample_mode",
    "sample",
    "baseline_used",
    "mock_data_used",
    "fixture_only",
)

RESEARCH_ALLOW_FLAGS = (
    "is_real_data_only",
    "allowed",
    "allowed_for_feature_store",
    "allowed_for_training",
    "allowed_for_prediction",
    "allowed_for_backtest",
    "allowed_for_customer_display",
    "promotion_pass",
    "gate_pass",
    "passed",
)

RESULT_HINT_KEYS = (
    "prediction",
    "forecast",
    "cards",
    "signals",
    "signal",
    "equity_curve",
    "backtest",
    "model_id",
    "raw_layer",
    "calibrated_layer",
    "guarded_layer",
)


def existing_test_paths(root: Path, candidates: Iterable[str]) -> list[str]:
    return [path for path in candidates if (root / path).exists()]


def resolve_tool(command: str) -> str:
    if not command:
        return command
    candidate = Path(command)
    if candidate.parent != Path(".") or candidate.exists():
        return str(candidate)
    if os.name == "nt":
        for name in (f"{command}.cmd", f"{command}.exe", f"{command}.bat", command, f"{command}.ps1"):
            resolved = shutil.which(name)
            if resolved:
                return resolved
    resolved = shutil.which(command)
    return resolved or command


def build_gate_steps(options: GateOptions, root: Path | None = None) -> list[GateStep]:
    root = root or PROJECT_ROOT
    py = options.python
    npm = resolve_tool(options.npm)
    steps: list[GateStep] = [
        GateStep("repo cleanliness check", command=[py, "scripts/check_repo_cleanliness.py"], cwd=root),
        GateStep("secret scan", internal="secret_scan"),
        GateStep("release package safety scan", internal="release_package_scan"),
        GateStep("real-result sample/baseline scan", internal="real_result_scan"),
        GateStep("historical OHLCV scaling scan", internal="historical_scaling_scan"),
    ]

    if options.only_scans:
        return steps

    steps.append(GateStep("python compileall", command=[py, "-m", "compileall", "-q", "src", "scripts", "tests"], cwd=root))

    if not options.skip_pytest:
        api_contract_tests = existing_test_paths(
            root,
            (
                "tests/test_frontend_api_contracts.py",
                "tests/test_terminal_router_registry.py",
                "tests/test_terminal_ui_api_map_contract.py",
            ),
        )
        if api_contract_tests:
            steps.append(GateStep("API endpoint contract tests", command=[py, "-m", "pytest", "-q", *api_contract_tests], cwd=root))

        watermark_tests = existing_test_paths(
            root,
            (
                "tests/test_provenance_gate_contract.py",
                "tests/test_frontend_data_watermark_contract.py",
                "tests/test_data_watermark_consistency_after_refresh.py",
            ),
        )
        if watermark_tests:
            steps.append(GateStep("data watermark schema tests", command=[py, "-m", "pytest", "-q", *watermark_tests], cwd=root))

        steps.append(GateStep("pytest full suite", command=[py, "-m", "pytest", "-q"], cwd=root))

    if not options.skip_frontend:
        steps.append(GateStep("frontend typecheck", command=[npm, "run", "typecheck"], cwd=root / "frontend"))
        if not options.skip_frontend_build:
            steps.append(GateStep("frontend build", command=[npm, "run", "build"], cwd=root / "frontend"))
        steps.append(GateStep("frontend UI contract check", command=[npm, "run", "check:ui"], cwd=root / "frontend"))
        if not options.skip_e2e:
            steps.append(GateStep("frontend e2e", command=[npm, "run", "test:e2e"], cwd=root / "frontend"))

    return steps


def truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "ok", "pass", "passed", "allowed", "success"}
    return False


def should_skip_path(path: Path) -> bool:
    return any(part in SKIP_DIRS for part in path.parts)


def iter_files(paths: Iterable[Path], *, suffixes: set[str] | None = None) -> Iterable[Path]:
    suffixes = suffixes or TEXT_SUFFIXES
    for base in paths:
        if not base.exists():
            continue
        if base.is_file():
            if base.suffix.lower() in suffixes and not should_skip_path(base):
                yield base
            continue
        for path in base.rglob("*"):
            if path.is_file() and path.suffix.lower() in suffixes and not should_skip_path(path):
                yield path


def read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            return path.read_text(encoding="utf-8-sig")
        except Exception:
            return None
    except Exception:
        return None


def _walk_dicts(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_dicts(child)


def _dict_has_result_hint(value: dict[str, Any]) -> bool:
    keys = {str(key).lower() for key in value.keys()}
    if any(key in keys for key in RESULT_HINT_KEYS):
        return True
    status = str(value.get("status", "") or value.get("final_status", "")).lower()
    return status in {"success", "allowed", "passed", "ok"}


def _json_payload(path: Path) -> Any | None:
    text = read_text(path)
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        return None


def find_real_result_policy_violations(paths: Iterable[Path]) -> list[Finding]:
    findings: list[Finding] = []
    for path in paths:
        payload = _json_payload(path)
        if payload is None:
            continue
        for item in _walk_dicts(payload):
            dirty_flags = [flag for flag in DIRTY_DATA_FLAGS if truthy(item.get(flag))]
            allowed_flags = [flag for flag in RESEARCH_ALLOW_FLAGS if truthy(item.get(flag))]
            if dirty_flags and allowed_flags:
                findings.append(
                    Finding(
                        path,
                        "sample/demo/baseline payload is marked as a real or allowed research result: "
                        + ", ".join([*dirty_flags, *allowed_flags]),
                    )
                )
                break
            if dirty_flags and _dict_has_result_hint(item) and str(item.get("status", "")).lower() in {"success", "allowed", "passed"}:
                findings.append(
                    Finding(path, "sample/demo/baseline payload is exposed as a successful result: " + ", ".join(dirty_flags))
                )
                break
            cache_status = str(item.get("cache_status", "")).lower()
            stale_status = str(item.get("stale_status", "")).lower()
            if cache_status == "last_good_cache" and stale_status in {"stale", "missing"}:
                illegal = [flag for flag in ("allowed_for_training", "allowed_for_prediction", "allowed_for_backtest") if truthy(item.get(flag))]
                if illegal:
                    findings.append(
                        Finding(path, "stale last-good-cache is allowed for research use: " + ", ".join(illegal))
                    )
                    break
    return findings


OHLCV_NAME_RE = r"(?:open|high|low|close|spot_price)"
HISTORICAL_SCALING_PATTERNS = (
    re.compile(rf"\[[\"']{OHLCV_NAME_RE}[\"']\]\s*\*=\s*.*(?:scale|ratio|live|latest)", re.IGNORECASE),
    re.compile(rf"\[[\"']{OHLCV_NAME_RE}[\"']\]\s*=\s*.*\*\s*.*(?:scale|ratio|live|latest)", re.IGNORECASE),
    re.compile(rf"\b{OHLCV_NAME_RE}\b\s*=\s*.*\*\s*.*(?:scale|ratio|live|latest)", re.IGNORECASE),
)


def find_historical_scaling_violations(paths: Iterable[Path]) -> list[Finding]:
    findings: list[Finding] = []
    for path in paths:
        text = read_text(path)
        if not text:
            continue
        lower = text.lower()
        if "last_close" not in lower and "prev_close" not in lower and "live_scale" not in lower and "scale_ratio" not in lower:
            continue
        if "live" not in lower and "latest" not in lower:
            continue
        lines = text.splitlines()
        for index, line in enumerate(lines, start=1):
            if any(pattern.search(line) for pattern in HISTORICAL_SCALING_PATTERNS):
                findings.append(
                    Finding(
                        path,
                        "possible live/latest ratio mutates historical OHLCV; live data must stay in latest_quote/display_overlay",
                        line=index,
                    )
                )
                break
    return findings


def candidate_real_result_json_paths(root: Path) -> list[Path]:
    bases = [root / rel for rel in REAL_RESULT_DIRS]
    return list(iter_files(bases, suffixes={".json"}))


def candidate_source_paths(root: Path) -> list[Path]:
    bases = [
        root / "src",
        root / "scripts",
        root / "frontend" / "src",
        root / "frontend" / "scripts",
        root / "packaging",
    ]
    return list(iter_files(bases, suffixes={".py", ".ts", ".tsx", ".js", ".mjs", ".ps1"}))


SECRET_VALUE_RE = re.compile(
    r"(?i)(?:api[_-]?key|x-api-key|authorization|bearer|token)\s*[:=]\s*[\"']?(?!\*{3,}|<|your_|test_|example|masked|redacted)[A-Za-z0-9._\-]{12,}"
)


def configured_secret_values() -> list[str]:
    values: list[str] = []
    for name in SECRET_ENV_NAMES:
        value = str(os.environ.get(name, "") or "").strip()
        if len(value) >= 8 and not value.lower().startswith(("test_", "your_", "example")):
            values.append(value)
    return values


def find_secret_scan_findings(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    exact_values = configured_secret_values()
    scan_roots = [
        root / "src",
        root / "scripts",
        root / "frontend" / "src",
        root / "frontend" / "scripts",
        root / "packaging",
        root / "docs",
        root / "release",
        root / "dist",
        root / "frontend" / "dist",
    ]
    for path in iter_files(scan_roots):
        text = read_text(path)
        if not text:
            continue
        for secret in exact_values:
            if secret and secret in text:
                findings.append(Finding(path, "exact configured secret value appears outside user config"))
                break
        if findings and findings[-1].path == path:
            continue
        in_release_tree = any(part in {"release", "dist"} for part in path.parts) or "frontend" in path.parts and "dist" in path.parts
        if in_release_tree and SECRET_VALUE_RE.search(text):
            findings.append(Finding(path, "possible raw API key/token/header in release/static artifact"))
    return findings


FORBIDDEN_RELEASE_NAMES = {
    ".env",
    "secrets.json",
    "private_release_keys.json",
    "private_bundle_seed.json",
}
FORBIDDEN_RELEASE_SUFFIXES = {
    ".db",
    ".key",
    ".log",
    ".p12",
    ".pfx",
    ".sqlite",
    ".sqlite3",
}
FORBIDDEN_RELEASE_DIR_PARTS = {
    "_sn_runtime",
    "_sn_setup_runtime",
    "app_data",
    "cache",
    "logs",
    "outputs",
    "runtime",
}

RELEASE_FIX = "Fix: remove it from dist/release/build outputs and keep secrets only in the per-user config/secrets.json path."


def find_release_package_violations(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    if not root.exists():
        return findings
    paths = [root] if root.is_file() else [path for path in root.rglob("*") if path.is_file()]
    for path in paths:
        name = path.name.lower()
        parts = {part.lower() for part in path.parts}
        if name in FORBIDDEN_RELEASE_NAMES or (name.startswith(".env.") and name not in {".env.example", ".env.sample", ".env.template"}):
            findings.append(Finding(path, f"secret or environment file must not be packaged. {RELEASE_FIX}"))
        elif path.suffix.lower() == ".pem" and not (path.name.lower() == "cacert.pem" and "certifi" in parts):
            findings.append(Finding(path, f"private key/certificate material must not be packaged without explicit review. {RELEASE_FIX}"))
        elif path.suffix.lower() in FORBIDDEN_RELEASE_SUFFIXES:
            findings.append(Finding(path, f"runtime database/log/private key artifact must not be packaged. {RELEASE_FIX}"))
        elif parts & FORBIDDEN_RELEASE_DIR_PARTS:
            findings.append(Finding(path, f"runtime data/cache/log/output path must not be packaged. {RELEASE_FIX}"))
    return findings


FORBIDDEN_PACKAGING_DATA_PATTERNS = (
    ("private_bundle_seed.json", "private bundle seed must never be added to PyInstaller datas"),
    ("private_release_keys.json", "private release key input must never be added to PyInstaller datas"),
    ("secrets.json", "user secrets must never be added to PyInstaller datas"),
    ('project_root / ".env"', "development .env must never be added to PyInstaller datas"),
    ("app_data", "runtime app_data must never be added to PyInstaller datas"),
    ('"outputs"', "runtime outputs must never be added to PyInstaller datas"),
    ('"cache"', "runtime cache must never be added to PyInstaller datas"),
    ('"logs"', "runtime logs must never be added to PyInstaller datas"),
    (".sqlite", "SQLite files must never be added to PyInstaller datas"),
    (".db", "database files must never be added to PyInstaller datas"),
)


def find_packaging_manifest_violations(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    spec = root / "packaging" / "SNInsightTerminal.spec"
    spec_text = read_text(spec) or ""
    for pattern, reason in FORBIDDEN_PACKAGING_DATA_PATTERNS:
        if pattern in spec_text:
            findings.append(Finding(spec, f"{reason}. Fix: remove the entry and read secrets only from user config/secrets.json."))

    build_script = root / "packaging" / "build_release.ps1"
    script_text = read_text(build_script) or ""
    forbidden_script_terms = (
        ("ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $PrivateBundleSeed", "build script still writes private_bundle_seed.json"),
        ("datas.append", "build script must not mutate PyInstaller datas"),
        ("仅保留 PyInstaller bundle 内部副本", "build script still describes keeping a bundled private seed"),
    )
    for term, reason in forbidden_script_terms:
        if term in script_text:
            findings.append(Finding(build_script, f"{reason}. Fix: disable embedded private bundles and use user config/secrets.json."))
    if "PrivateBundleKeys 已禁用" not in script_text:
        findings.append(Finding(build_script, "PrivateBundleKeys is not explicitly disabled. Fix: fail fast and direct users to config\\secrets.json."))
    return findings


def assert_release_build_contract(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    build_script = root / "packaging" / "build_release.ps1"
    text = read_text(build_script) or ""
    required_terms = (
        "Assert-NoEmbeddedPrivateBundle",
        "Assert-CleanDistForInstaller",
        "Remove-RuntimeDataFromDist",
        ".env",
        "secrets.json",
        "private_bundle_seed.json",
    )
    for term in required_terms:
        if term not in text:
            findings.append(Finding(build_script, f"release build script missing package exclusion guard: {term}"))

    user_data = root / "src" / "sn_futures" / "user_data.py"
    user_data_text = read_text(user_data) or ""
    for term in ("LOCALAPPDATA", "SN_DATA_DIR", "SN_INSIGHT_DATA_DIR", "secrets_path"):
        if term not in user_data_text:
            findings.append(Finding(user_data, f"user data directory contract missing: {term}"))
    findings.extend(find_packaging_manifest_violations(root))
    return findings


def run_internal_step(name: str, root: Path) -> int:
    if name == "secret_scan":
        findings = find_secret_scan_findings(root)
    elif name == "release_package_scan":
        findings = assert_release_build_contract(root)
        for rel in RELEASE_SCAN_DIRS:
            findings.extend(find_release_package_violations(root / rel))
    elif name == "real_result_scan":
        findings = find_real_result_policy_violations(candidate_real_result_json_paths(root))
    elif name == "historical_scaling_scan":
        findings = find_historical_scaling_violations(candidate_source_paths(root))
    else:
        print(f"Unknown internal quality gate step: {name}", file=sys.stderr)
        return 2

    if findings:
        print(f"FAIL: {name}")
        print(f"失败: {name} 发现发行前阻塞项。")
        for finding in findings:
            print(f"- {finding.format(root)}")
        return 1
    print(f"PASS: {name}")
    return 0


def run_command_step(step: GateStep) -> int:
    assert step.command is not None
    try:
        result = subprocess.run(step.command, cwd=str(step.cwd) if step.cwd else None, check=False)
        return int(result.returncode)
    except FileNotFoundError as exc:
        print(f"Command not found: {step.command[0]} ({exc})", file=sys.stderr)
        return 127


def run_steps(steps: list[GateStep], root: Path, *, continue_on_error: bool = False) -> int:
    started = time.time()
    failures: list[str] = []
    for index, step in enumerate(steps, start=1):
        print(f"==> [{index}/{len(steps)}] {step.name}", flush=True)
        step_started = time.time()
        code = run_internal_step(step.internal, root) if step.internal else run_command_step(step)
        elapsed = time.time() - step_started
        if code != 0:
            print(f"FAIL: {step.name} ({elapsed:.1f}s)")
            failures.append(step.name)
            if not continue_on_error:
                return code
            continue
        print(f"PASS: {step.name} ({elapsed:.1f}s)")
    if failures:
        print("SNInsightTerminal quality gate failed. Failed steps:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print(f"SNInsightTerminal quality gate passed in {time.time() - started:.1f}s.")
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run SNInsightTerminal final local release quality gate.")
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--npm", default=os.environ.get("NPM", "npm"))
    parser.add_argument("--skip-e2e", action="store_true")
    parser.add_argument("--skip-frontend", action="store_true")
    parser.add_argument("--skip-frontend-build", action="store_true")
    parser.add_argument("--skip-pytest", action="store_true")
    parser.add_argument("--only-scans", action="store_true")
    parser.add_argument("--continue-on-error", action="store_true")
    parser.add_argument("--list", action="store_true", help="Print configured steps without running them.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = args.root.resolve()
    options = GateOptions(
        python=args.python,
        npm=args.npm,
        skip_e2e=args.skip_e2e,
        skip_frontend=args.skip_frontend,
        skip_frontend_build=args.skip_frontend_build,
        skip_pytest=args.skip_pytest,
        only_scans=args.only_scans,
        continue_on_error=args.continue_on_error,
    )
    steps = build_gate_steps(options, root)
    if args.list:
        for step in steps:
            if step.command:
                cwd = f" (cwd={step.cwd})" if step.cwd else ""
                print(f"- {step.name}: {' '.join(step.command)}{cwd}")
            else:
                print(f"- {step.name}: internal:{step.internal}")
        return 0
    return run_steps(steps, root, continue_on_error=args.continue_on_error)


if __name__ == "__main__":
    raise SystemExit(main())
