from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir
from .managed_proxy_setup_service import get_managed_proxy_setup_status


WIZARD_VERSION = "managed_proxy_config_wizard_v1"
WIZARD_REPORT_FILENAME = "managed_proxy_config_wizard_report.json"
REQUIRED_ENV_VARS = (
    "SN_MANAGED_PROXY_ENABLED",
    "SN_MANAGED_PROXY_BASE_URL",
    "SN_MANAGED_PROXY_TOKEN",
    "SN_MANAGED_PROXY_TIMEOUT_SECONDS",
)
REQUIRED_GITIGNORE_PATTERNS = (".env", ".env.local", "config/managed_proxy.local.json", "secrets/")


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _report_path() -> Path:
    path = get_user_output_dir() / "diagnostics" / WIZARD_REPORT_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _write_json(path: Path, payload: Mapping[str, Any]) -> dict[str, Any]:
    safe = sanitize_for_json(dict(payload))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
    return safe


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def validate_local_config_templates(*, project_root: Path | None = None) -> dict[str, Any]:
    root = project_root or _project_root()
    env_path = root / ".env.example"
    local_path = root / "config" / "managed_proxy.example.json"
    env_text = _read_text(env_path)
    local_text = _read_text(local_path)
    env_missing = [name for name in REQUIRED_ENV_VARS if name not in env_text]
    local_missing = [name for name in REQUIRED_ENV_VARS if name not in local_text]
    return {
        "env_var_template_status": "pass" if env_path.exists() and not env_missing else "missing" if not env_path.exists() else "incomplete",
        "local_config_template_status": "pass" if local_path.exists() and not local_missing else "missing" if not local_path.exists() else "incomplete",
        "env_template_path": str(env_path),
        "local_config_template_path": str(local_path),
        "env_missing_keys": env_missing,
        "local_config_missing_keys": local_missing,
    }


def validate_gitignore_secret_coverage(*, project_root: Path | None = None) -> dict[str, Any]:
    root = project_root or _project_root()
    path = root / ".gitignore"
    text = _read_text(path)
    missing = [pattern for pattern in REQUIRED_GITIGNORE_PATTERNS if pattern not in text]
    return {
        "status": "pass" if path.exists() and not missing else "missing" if not path.exists() else "incomplete",
        "path": str(path),
        "required_patterns": list(REQUIRED_GITIGNORE_PATTERNS),
        "missing_patterns": missing,
    }


def build_env_var_setup_instructions() -> list[str]:
    return [
        "Set SN_MANAGED_PROXY_ENABLED, SN_MANAGED_PROXY_BASE_URL, SN_MANAGED_PROXY_TOKEN, and SN_MANAGED_PROXY_TIMEOUT_SECONDS only in a local shell or ignored environment file.",
        "Do not paste managed proxy tokens into ChatGPT, logs, commits, issues, screenshots, or support tickets.",
    ]


def build_local_config_setup_instructions() -> list[str]:
    return [
        "Copy config/managed_proxy.example.json to config/managed_proxy.local.json and fill real values only on this machine.",
        "Keep config/managed_proxy.local.json ignored by git and never include raw token values in reports.",
    ]


def build_safe_dry_run_checklist() -> list[str]:
    return [
        "Run managed proxy setup dry-run after local configuration.",
        "Run managed proxy health only after setup passes.",
        "Run PIT audit only after health returns required fields.",
        "Confirm all responses show only masked token metadata.",
    ]


def compute_wizard_next_action(blocking_reasons: list[str], setup_status: Mapping[str, Any]) -> str:
    if any(reason in blocking_reasons for reason in ("env_template_missing", "local_config_template_missing", "gitignore_secret_coverage_incomplete")):
        return "fix_managed_proxy_config_templates"
    if not setup_status.get("base_url_configured") or not setup_status.get("token_configured"):
        return "configure_managed_proxy_endpoint_or_token"
    return str(setup_status.get("next_allowed_action") or "run_managed_proxy_setup_dry_run")


def build_managed_proxy_config_wizard(*, project_root: Path | None = None, write: bool = True) -> dict[str, Any]:
    root = project_root or _project_root()
    templates = validate_local_config_templates(project_root=root)
    gitignore = validate_gitignore_secret_coverage(project_root=root)
    setup_status = get_managed_proxy_setup_status()
    blocking: list[str] = []
    if templates["env_var_template_status"] != "pass":
        blocking.append("env_template_missing" if templates["env_var_template_status"] == "missing" else "env_template_incomplete")
    if templates["local_config_template_status"] != "pass":
        blocking.append("local_config_template_missing" if templates["local_config_template_status"] == "missing" else "local_config_template_incomplete")
    if gitignore["status"] != "pass":
        blocking.append("gitignore_secret_coverage_incomplete")
    status = "ready" if not blocking else "blocked"
    payload = {
        "status": status,
        "wizard_version": WIZARD_VERSION,
        "generated_at": _now(),
        "setup_status": setup_status.get("status", "blocked"),
        "endpoint_configured": bool(setup_status.get("base_url_configured")),
        "token_configured": bool(setup_status.get("token_configured")),
        "safe_config_methods": ["environment_variables", "local_ignored_config"],
        "env_var_template_status": templates["env_var_template_status"],
        "local_config_template_status": templates["local_config_template_status"],
        "gitignore_secret_coverage": gitignore,
        "setup_steps": [
            *build_env_var_setup_instructions(),
            *build_local_config_setup_instructions(),
            "After configuration, run setup dry-run, then health, then PIT audit.",
            "All API and UI responses must show masked token metadata only.",
        ],
        "dry_run_checklist": build_safe_dry_run_checklist(),
        "next_allowed_action": compute_wizard_next_action(blocking, setup_status),
        "blocking_reasons": blocking,
        "warning_reasons": [] if status == "ready" else ["managed proxy cannot proceed until local setup guidance is complete."],
        "training_invoked": False,
        "active_updated": False,
        "customer_prediction_generated": False,
        "report_path": str(_report_path()),
    }
    if write:
        return write_config_wizard_report(payload)
    return sanitize_for_json(payload)


def write_config_wizard_report(payload: Mapping[str, Any]) -> dict[str, Any]:
    return _write_json(_report_path(), payload)


def get_managed_proxy_config_wizard() -> dict[str, Any]:
    path = _report_path()
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, Mapping):
                return sanitize_for_json(dict(payload))
        except Exception:
            pass
    return build_managed_proxy_config_wizard()


def refresh_managed_proxy_config_wizard() -> dict[str, Any]:
    return build_managed_proxy_config_wizard()
