from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from ..api.json_utils import sanitize_for_json
from ..config import mask_secret
from ..runtime import get_user_output_dir
from ..utils.secret_sanitizer import sanitize_text
from .managed_proxy_schema_mapper_service import CANONICAL_FIELDS
from .managed_proxy_setup_service import get_managed_proxy_setup_status, validate_managed_proxy_config_source


RUNBOOK_VERSION = "managed_proxy_operator_runbook_v1"
RUNBOOK_REPORT_FILENAME = "managed_proxy_operator_runbook_report.json"
REQUIRED_ENV_TEMPLATE_KEYS = (
    "SN_MANAGED_PROXY_ENABLED",
    "SN_MANAGED_PROXY_BASE_URL",
    "SN_MANAGED_PROXY_TOKEN",
    "SN_MANAGED_PROXY_TIMEOUT_SECONDS",
)
LEGACY_ENV_ALIAS_KEYS = (
    "SN_MANAGED_DATA_PROXY_ENABLED",
    "SN_MANAGED_DATA_PROXY_URL",
    "SN_MANAGED_DATA_PROXY_TOKEN",
    "SN_MANAGED_DATA_PROXY_TIMEOUT_SECONDS",
)
REQUIRED_LOCAL_CONFIG_KEYS = REQUIRED_ENV_TEMPLATE_KEYS
REQUIRED_GITIGNORE_PATTERNS = (
    ".env",
    ".env.local",
    "config/managed_proxy.local.json",
    "config/managed_proxy.mapping.local.json",
    "secrets/",
)
ENV_ALIAS_PAIRS = (
    ("SN_MANAGED_PROXY_ENABLED", "SN_MANAGED_DATA_PROXY_ENABLED"),
    ("SN_MANAGED_PROXY_BASE_URL", "SN_MANAGED_DATA_PROXY_URL"),
    ("SN_MANAGED_PROXY_TOKEN", "SN_MANAGED_DATA_PROXY_TOKEN"),
    ("SN_MANAGED_PROXY_TIMEOUT_SECONDS", "SN_MANAGED_DATA_PROXY_TIMEOUT_SECONDS"),
)
SECRET_RE = re.compile(
    r"(?i)(authorization\s*[:=]\s*[^\s,;\"']+|bearer\s+[A-Za-z0-9._\-]{8,}|token\s*[:=]\s*[^\s,;\"']+|secret\s*[:=]\s*[^\s,;\"']+)"
)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _report_path() -> Path:
    path = get_user_output_dir() / "diagnostics" / RUNBOOK_REPORT_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8-sig")
    except Exception:
        return ""


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: Mapping[str, Any]) -> dict[str, Any]:
    safe = sanitize_for_json(dict(payload))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
    return safe


def _status_for(path: Path, missing_items: list[str]) -> str:
    if not path.exists():
        return "missing"
    return "pass" if not missing_items else "blocked"


def validate_operator_config_files(*, project_root: Path | None = None) -> dict[str, Any]:
    root = project_root or _project_root()
    env_path = root / ".env.example"
    local_path = root / "config" / "managed_proxy.example.json"
    mapping_path = root / "config" / "managed_proxy.mapping.example.json"
    env_text = _read_text(env_path)
    local_payload = _read_json(local_path)
    local_text = json.dumps(local_payload, ensure_ascii=False) if local_payload else _read_text(local_path)
    mapping_payload = _read_json(mapping_path)
    field_mapping = mapping_payload.get("field_mapping") if isinstance(mapping_payload.get("field_mapping"), Mapping) else {}
    mapped_canonical = {str(value) for value in dict(field_mapping).values() if str(value).strip()}
    missing_env = [key for key in REQUIRED_ENV_TEMPLATE_KEYS if key not in env_text]
    missing_local = [key for key in REQUIRED_LOCAL_CONFIG_KEYS if key not in local_text]
    missing_mapping = [field for field in CANONICAL_FIELDS if field not in mapped_canonical and field not in {"feature_date"}]
    if "feature_date" in CANONICAL_FIELDS and "feature_date" not in mapped_canonical and "trading_date" not in mapped_canonical:
        missing_mapping.append("feature_date_or_trading_date")
    return sanitize_for_json(
        {
            "env_template_status": {
                "status": _status_for(env_path, missing_env),
                "path": str(env_path),
                "missing_keys": missing_env,
                "required_keys": list(REQUIRED_ENV_TEMPLATE_KEYS),
                "legacy_alias_keys": list(LEGACY_ENV_ALIAS_KEYS),
            },
            "local_config_template_status": {
                "status": _status_for(local_path, missing_local),
                "path": str(local_path),
                "missing_keys": missing_local,
                "required_keys": list(REQUIRED_LOCAL_CONFIG_KEYS),
            },
            "mapping_template_status": {
                "status": _status_for(mapping_path, missing_mapping),
                "path": str(mapping_path),
                "missing_canonical_fields": list(dict.fromkeys(missing_mapping)),
                "required_canonical_fields": list(CANONICAL_FIELDS),
            },
        }
    )


def validate_secret_storage_boundaries(*, project_root: Path | None = None) -> dict[str, Any]:
    root = project_root or _project_root()
    path = root / ".gitignore"
    text = _read_text(path)
    missing = [pattern for pattern in REQUIRED_GITIGNORE_PATTERNS if pattern not in text]
    return sanitize_for_json(
        {
            "status": "pass" if path.exists() and not missing else "missing" if not path.exists() else "blocked",
            "path": str(path),
            "required_patterns": list(REQUIRED_GITIGNORE_PATTERNS),
            "missing_patterns": missing,
        }
    )


def _clean(value: Any) -> str:
    text = str(value or "").strip()
    lower = text.lower()
    if not text or lower in {"masked", "[masked]", "redacted", "[redacted]", "configured", "your_token_here"}:
        return ""
    if set(text) <= {"*"}:
        return ""
    return text


def validate_operator_environment_aliases() -> dict[str, Any]:
    aliases_checked: list[str] = []
    conflicts: list[str] = []
    configured: list[str] = []
    for canonical, legacy in ENV_ALIAS_PAIRS:
        aliases_checked.extend([canonical, legacy])
        canonical_value = _clean(os.environ.get(canonical, ""))
        legacy_value = _clean(os.environ.get(legacy, ""))
        if canonical_value:
            configured.append(canonical)
        if legacy_value:
            configured.append(legacy)
        if canonical_value and legacy_value and canonical_value != legacy_value:
            conflicts.append(f"{canonical}/{legacy}")
    return sanitize_for_json(
        {
            "status": "pass" if not conflicts else "warning",
            "aliases_checked": aliases_checked,
            "configured_aliases": sorted(set(configured)),
            "conflicts": conflicts,
            "message": "SN_MANAGED_PROXY_* and legacy SN_MANAGED_DATA_PROXY_* aliases are accepted; conflicting values should be resolved locally.",
        }
    )


def validate_no_raw_secret_echo(payload: Mapping[str, Any], *, extra_secrets: list[str] | None = None) -> dict[str, Any]:
    raw = json.dumps(payload, ensure_ascii=False, default=str)
    secrets = [_clean(secret) for secret in (extra_secrets or [])]
    blockers: list[str] = []
    if SECRET_RE.search(raw) or "Authorization" in raw or "Bearer " in raw:
        blockers.append("raw_secret_echo_detected")
    for secret in secrets:
        if secret and secret in raw:
            blockers.append("configured_secret_echo_detected")
    return sanitize_for_json(
        {
            "status": "pass" if not blockers else "blocked",
            "blocking_reasons": list(dict.fromkeys(blockers)),
        }
    )


def _config_state() -> dict[str, Any]:
    config = validate_managed_proxy_config_source()
    return {
        "enabled": bool(config.get("enabled")),
        "configured": bool(config.get("configured")),
        "endpoint_configured": bool(config.get("base_url_configured")),
        "token_configured": bool(config.get("token_configured")),
        "token_masked": str(config.get("token_masked") or ""),
        "base_url_source": str(config.get("base_url_source") or "none"),
        "token_source": str(config.get("token_source") or "none"),
        "timeout_seconds": int(config.get("timeout_seconds") or 20),
    }


def _setup_steps() -> list[str]:
    return [
        "Do not paste managed proxy tokens into ChatGPT, Codex prompts, Git commits, issues, logs, screenshots, or support tickets.",
        "Set the managed proxy token only in a local shell, ignored local config, or OS secret store.",
        "Use .env.example and config/managed_proxy.example.json as templates; put real values only in .env, .env.local, config/managed_proxy.local.json, or secrets/.",
        "After local changes, first run refresh operator runbook to verify templates and masked configuration status.",
        "Then run managed proxy setup dry-run.",
        "Then run managed proxy health.",
        "Then run schema mapping.",
        "Then run PIT replay, PIT audit, and managed data quality before any Feature Store v12 build is considered.",
        "All responses must show only configured/masked token metadata.",
    ]


def _verification_commands() -> list[str]:
    return [
        "$env:SN_MANAGED_PROXY_ENABLED='true'",
        "$env:SN_MANAGED_PROXY_BASE_URL='https://managed-proxy.example'",
        "$env:SN_MANAGED_PROXY_TOKEN='<MANAGED_PROXY_TOKEN_FROM_LOCAL_SECRET_STORE>'",
        "POST /api/terminal/managed-proxy/refresh-operator-runbook",
        "POST /api/terminal/managed-proxy/refresh-setup",
        "POST /api/terminal/managed-proxy/run-contract-dry-run",
        "POST /api/terminal/managed-proxy/check",
        "POST /api/terminal/managed-proxy/refresh-schema-mapping",
        "POST /api/terminal/managed-proxy/run-pit-replay",
        "POST /api/terminal/managed-proxy/run-audit",
        "POST /api/terminal/managed-proxy/refresh-data-quality",
    ]


def _next_action(blocking: list[str], current_config: Mapping[str, Any], setup_status: Mapping[str, Any]) -> str:
    if blocking:
        return "fix_operator_runbook_templates"
    if not current_config.get("endpoint_configured") or not current_config.get("token_configured"):
        return "configure_managed_proxy_endpoint_or_token"
    return str(setup_status.get("next_allowed_action") or "run_managed_proxy_setup_dry_run")


def build_safe_config_verification_report(*, project_root: Path | None = None) -> dict[str, Any]:
    root = project_root or _project_root()
    files = validate_operator_config_files(project_root=root)
    boundaries = validate_secret_storage_boundaries(project_root=root)
    aliases = validate_operator_environment_aliases()
    current = _config_state()
    raw_candidate = {
        "files": files,
        "boundaries": boundaries,
        "aliases": aliases,
        "current_config_state": current,
    }
    safe_echo = validate_no_raw_secret_echo(raw_candidate, extra_secrets=[os.environ.get("SN_MANAGED_PROXY_TOKEN", ""), os.environ.get("SN_MANAGED_DATA_PROXY_TOKEN", "")])
    return sanitize_for_json(
        {
            "status": "pass" if safe_echo["status"] == "pass" and boundaries["status"] == "pass" else "blocked",
            "config_file_status": files,
            "gitignore_secret_coverage": boundaries,
            "env_alias_consistency": aliases,
            "current_config_state": current,
            "safe_echo_check": safe_echo,
            "training_invoked": False,
            "active_updated": False,
            "customer_prediction_generated": False,
        }
    )


def build_operator_onboarding_runbook(*, project_root: Path | None = None, write: bool = True) -> dict[str, Any]:
    root = project_root or _project_root()
    files = validate_operator_config_files(project_root=root)
    boundaries = validate_secret_storage_boundaries(project_root=root)
    aliases = validate_operator_environment_aliases()
    current = _config_state()
    setup_status = get_managed_proxy_setup_status()
    blocking: list[str] = []
    if files["env_template_status"]["status"] != "pass":
        blocking.append("env_template_missing" if files["env_template_status"]["status"] == "missing" else "env_template_incomplete")
    if files["local_config_template_status"]["status"] != "pass":
        blocking.append("local_config_template_missing" if files["local_config_template_status"]["status"] == "missing" else "local_config_template_incomplete")
    if files["mapping_template_status"]["status"] != "pass":
        blocking.append("mapping_template_missing" if files["mapping_template_status"]["status"] == "missing" else "mapping_template_incomplete")
    if boundaries["status"] != "pass":
        blocking.append("gitignore_secret_coverage_incomplete")
    warnings: list[str] = []
    if aliases["status"] == "warning":
        warnings.append("managed_proxy_env_alias_conflict")
    if not current["endpoint_configured"] or not current["token_configured"]:
        warnings.append("managed_proxy_endpoint_or_token_missing")
    status = "blocked" if blocking else "ready" if current["endpoint_configured"] and current["token_configured"] else "ready_with_missing_config"
    payload = {
        "status": status,
        "generated_at": _now(),
        "runbook_version": RUNBOOK_VERSION,
        "config_methods": ["local_shell_environment", "ignored_env_file", "ignored_local_json_config", "os_secret_store"],
        "env_template_status": files["env_template_status"],
        "local_config_template_status": files["local_config_template_status"],
        "mapping_template_status": files["mapping_template_status"],
        "gitignore_secret_coverage": boundaries,
        "current_config_state": current,
        "endpoint_configured": bool(current["endpoint_configured"]),
        "token_configured": bool(current["token_configured"]),
        "token_masked": mask_secret(os.environ.get("SN_MANAGED_PROXY_TOKEN", "") or os.environ.get("SN_MANAGED_DATA_PROXY_TOKEN", "")) if current["token_configured"] and not current["token_masked"] else current["token_masked"],
        "env_alias_consistency": aliases,
        "safe_setup_steps": _setup_steps(),
        "verification_commands": _verification_commands(),
        "next_allowed_action": _next_action(blocking, current, setup_status),
        "blocking_reasons": list(dict.fromkeys(blocking)),
        "warning_reasons": list(dict.fromkeys(warnings)),
        "training_invoked": False,
        "active_updated": False,
        "customer_prediction_generated": False,
        "report_path": str(_report_path()),
    }
    safe_echo = validate_no_raw_secret_echo(payload, extra_secrets=[os.environ.get("SN_MANAGED_PROXY_TOKEN", ""), os.environ.get("SN_MANAGED_DATA_PROXY_TOKEN", "")])
    payload["safe_echo_check"] = safe_echo
    if safe_echo["status"] != "pass":
        payload["status"] = "blocked"
        payload["blocking_reasons"] = list(dict.fromkeys(list(payload["blocking_reasons"]) + list(safe_echo["blocking_reasons"])))
        payload["next_allowed_action"] = "fix_operator_runbook_secret_echo"
    if write:
        return _write_json(_report_path(), payload)
    return sanitize_for_json(payload)


def refresh_operator_onboarding_runbook() -> dict[str, Any]:
    return build_operator_onboarding_runbook(write=True)


def get_operator_onboarding_runbook() -> dict[str, Any]:
    path = _report_path()
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
            if isinstance(payload, Mapping):
                return sanitize_for_json(dict(payload))
        except Exception:
            pass
    return build_operator_onboarding_runbook(write=True)
