from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from ..api.json_utils import sanitize_for_json
from ..config import mask_secret
from ..runtime import get_user_output_dir
from ..utils.secret_sanitizer import sanitize_mapping, sanitize_text


HANDOFF_VERSION = "managed_proxy_config_handoff_v1"
HANDOFF_REPORT_FILENAME = "managed_proxy_config_handoff_report.json"

CANONICAL_ENV_KEYS = (
    "SN_MANAGED_PROXY_ENABLED",
    "SN_MANAGED_PROXY_BASE_URL",
    "SN_MANAGED_PROXY_TOKEN",
)
LEGACY_ENV_KEYS = (
    "SN_MANAGED_DATA_PROXY_ENABLED",
    "SN_MANAGED_DATA_PROXY_URL",
    "SN_MANAGED_DATA_PROXY_TOKEN",
)
ENV_ALIAS_PAIRS = (
    ("SN_MANAGED_PROXY_ENABLED", "SN_MANAGED_DATA_PROXY_ENABLED"),
    ("SN_MANAGED_PROXY_BASE_URL", "SN_MANAGED_DATA_PROXY_URL"),
    ("SN_MANAGED_PROXY_TOKEN", "SN_MANAGED_DATA_PROXY_TOKEN"),
)
REQUIRED_GITIGNORE_PATTERNS = (
    ".env",
    ".env.local",
    "config/managed_proxy.local.json",
    "config/managed_proxy.mapping.local.json",
    "secrets/",
)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _report_path(project_root: Path | None = None) -> Path:
    base = project_root / "outputs" if project_root is not None else get_user_output_dir()
    path = base / "diagnostics" / HANDOFF_REPORT_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _safe(payload: Any) -> Any:
    return sanitize_for_json(sanitize_mapping(payload))


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


def _clean(value: Any) -> str:
    text = str(value or "").strip()
    lower = text.lower()
    if not text or lower in {"masked", "[masked]", "redacted", "[redacted]", "configured", "your_token_here"}:
        return ""
    if set(text) <= {"*"}:
        return ""
    return text


def _env_value(*names: str) -> tuple[str, str]:
    for name in names:
        value = _clean(os.environ.get(name, ""))
        if value:
            return value, name
    return "", "none"


def _local_config_value(root: Path, *names: str) -> tuple[str, str, list[str]]:
    sources: list[str] = []
    for path in (root / ".env.local", root / "config" / "managed_proxy.local.json"):
        if path.exists():
            sources.append(str(path))
    payload = _read_json(root / "config" / "managed_proxy.local.json")
    for name in names:
        value = _clean(payload.get(name, ""))
        if value:
            return value, "config/managed_proxy.local.json", sources
    return "", "none", sources


def detect_local_managed_proxy_config(*, project_root: Path | None = None) -> dict[str, Any]:
    root = project_root or _project_root()
    enabled_env, enabled_env_source = _env_value("SN_MANAGED_PROXY_ENABLED", "SN_MANAGED_DATA_PROXY_ENABLED")
    base_env, base_env_source = _env_value("SN_MANAGED_PROXY_BASE_URL", "SN_MANAGED_DATA_PROXY_URL")
    token_env, token_env_source = _env_value("SN_MANAGED_PROXY_TOKEN", "SN_MANAGED_DATA_PROXY_TOKEN")

    enabled_local, enabled_local_source, local_sources = _local_config_value(
        root, "enabled", "SN_MANAGED_PROXY_ENABLED", "SN_MANAGED_DATA_PROXY_ENABLED"
    )
    base_local, base_local_source, local_sources = _local_config_value(
        root, "base_url", "endpoint", "SN_MANAGED_PROXY_BASE_URL", "SN_MANAGED_DATA_PROXY_URL"
    )
    token_local, token_local_source, local_sources = _local_config_value(
        root, "token", "SN_MANAGED_PROXY_TOKEN", "SN_MANAGED_DATA_PROXY_TOKEN"
    )

    enabled = enabled_env or enabled_local
    base_url = base_env or base_local
    token = token_env or token_local
    sources = [source for source in (enabled_env_source, base_env_source, token_env_source) if source != "none"]
    sources.extend(source for source in (enabled_local_source, base_local_source, token_local_source) if source != "none")
    sources.extend(local_sources)
    return _safe(
        {
            "enabled_configured": bool(enabled),
            "endpoint_configured": bool(base_url),
            "token_configured": bool(token),
            "token_masked": mask_secret(token) if token else "",
            "config_sources_detected": sorted(set(sources)) or ["none"],
            "enabled_source": enabled_env_source if enabled_env else enabled_local_source,
            "endpoint_source": base_env_source if base_env else base_local_source,
            "token_source": token_env_source if token_env else token_local_source,
        }
    )


def validate_env_alias_consistency() -> dict[str, Any]:
    conflicts: list[str] = []
    configured_aliases: list[str] = []
    for canonical, legacy in ENV_ALIAS_PAIRS:
        canonical_value = _clean(os.environ.get(canonical, ""))
        legacy_value = _clean(os.environ.get(legacy, ""))
        if canonical_value:
            configured_aliases.append(canonical)
        if legacy_value:
            configured_aliases.append(legacy)
        if canonical_value and legacy_value and canonical_value != legacy_value:
            conflicts.append(f"{canonical}/{legacy}")
    return _safe(
        {
            "status": "pass" if not conflicts else "warning",
            "canonical_env_keys": list(CANONICAL_ENV_KEYS),
            "legacy_env_keys": list(LEGACY_ENV_KEYS),
            "configured_aliases": sorted(set(configured_aliases)),
            "conflicts": conflicts,
        }
    )


def validate_local_config_safety(*, project_root: Path | None = None) -> dict[str, Any]:
    root = project_root or _project_root()
    gitignore = _read_text(root / ".gitignore")
    missing = [pattern for pattern in REQUIRED_GITIGNORE_PATTERNS if pattern not in gitignore]
    env_example_exists = (root / ".env.example").exists()
    local_template_exists = (root / "config" / "managed_proxy.example.json").exists()
    mapping_template_exists = (root / "config" / "managed_proxy.mapping.example.json").exists()
    return _safe(
        {
            "status": "pass" if not missing and env_example_exists and local_template_exists and mapping_template_exists else "blocked",
            "env_example_exists": env_example_exists,
            "local_config_template_exists": local_template_exists,
            "mapping_config_template_exists": mapping_template_exists,
            "local_config_exists": (root / "config" / "managed_proxy.local.json").exists(),
            "env_local_exists": (root / ".env.local").exists(),
            "missing_gitignore_patterns": missing,
        }
    )


def _gitignore_secret_coverage(*, project_root: Path | None = None) -> dict[str, Any]:
    safety = validate_local_config_safety(project_root=project_root)
    return _safe(
        {
            "status": "pass" if not safety.get("missing_gitignore_patterns") else "blocked",
            "required_patterns": list(REQUIRED_GITIGNORE_PATTERNS),
            "missing_patterns": safety.get("missing_gitignore_patterns") or [],
        }
    )


def build_copy_safe_setup_commands() -> list[str]:
    return [
        '$env:SN_MANAGED_PROXY_ENABLED="true"',
        '$env:SN_MANAGED_PROXY_BASE_URL="https://your-managed-proxy.example.com"',
        '$env:SN_MANAGED_PROXY_TOKEN="<paste-token-only-in-your-local-shell>"',
        'python -m pytest -q tests/test_managed_proxy_setup_service.py',
    ]


def validate_no_raw_secret_in_handoff(payload: Mapping[str, Any], *, extra_secrets: list[str] | None = None) -> dict[str, Any]:
    raw = json.dumps(payload, ensure_ascii=False, default=str)
    blockers: list[str] = []
    for secret in extra_secrets or []:
        text = _clean(secret)
        if text and text in raw:
            blockers.append("raw_secret_echo_detected")
    lowered = raw.lower()
    if "authorization:" in lowered or "bearer " in lowered:
        blockers.append("authorization_header_echo_detected")
    return _safe({"status": "pass" if not blockers else "blocked", "blocking_reasons": list(dict.fromkeys(blockers))})


def _next_actions(detected: Mapping[str, Any]) -> list[str]:
    if not detected.get("endpoint_configured") or not detected.get("token_configured"):
        return [
            "configure_managed_proxy_endpoint_or_token_locally",
            "refresh_config_handoff",
            "refresh_operator_runbook",
            "refresh_managed_proxy_setup",
            "run_endpoint_smoke",
        ]
    return ["refresh_config_handoff", "refresh_managed_proxy_setup", "run_endpoint_smoke"]


def build_secure_config_handoff(*, project_root: Path | None = None, write: bool = True) -> dict[str, Any]:
    root = project_root or _project_root()
    detected = detect_local_managed_proxy_config(project_root=root)
    alias = validate_env_alias_consistency()
    safety = validate_local_config_safety(project_root=root)
    gitignore = _gitignore_secret_coverage(project_root=root)
    blocking: list[str] = []
    warnings: list[str] = []
    if not detected["endpoint_configured"]:
        blocking.append("managed_proxy_endpoint_missing")
    if not detected["token_configured"]:
        blocking.append("managed_proxy_token_missing")
    if safety["status"] != "pass":
        warnings.append("local_config_safety_incomplete")
    if gitignore["status"] != "pass":
        warnings.append("gitignore_secret_coverage_incomplete")
    if alias["status"] != "pass":
        warnings.append("managed_proxy_env_alias_conflict")

    status = "ready" if not blocking else "missing_config"
    payload = {
        "status": status,
        "generated_at": _now(),
        "handoff_version": HANDOFF_VERSION,
        "current_step": "configure_managed_proxy_endpoint_token",
        "endpoint_configured": bool(detected["endpoint_configured"]),
        "token_configured": bool(detected["token_configured"]),
        "token_masked": str(detected.get("token_masked") or ""),
        "enabled_configured": bool(detected["enabled_configured"]),
        "config_sources_detected": detected["config_sources_detected"],
        "env_alias_consistency": alias,
        "gitignore_secret_coverage": gitignore,
        "local_config_safety": safety,
        "copy_safe_setup_commands": build_copy_safe_setup_commands(),
        "user_action_checklist": [
            "Set endpoint/token only in a local shell or ignored local config.",
            "Confirm .env.local and config/managed_proxy.local.json are ignored by git.",
            "Run refresh-config-handoff.",
            "Run setup checklist refresh_operator_runbook.",
            "Run refresh_managed_proxy_setup.",
            "Run endpoint smoke.",
            "Continue to quarantine snapshot only after smoke passes.",
            "Never paste token into ChatGPT, Codex, commits, logs, issues, or screenshots.",
        ],
        "next_safe_actions_after_config": _next_actions(detected),
        "blocking_reasons": blocking,
        "warning_reasons": warnings,
        "feature_store_v12_allowed": False,
        "training_invoked": False,
        "active_updated": False,
        "customer_prediction_generated": False,
        "report_path": str(_report_path(root if project_root is not None else None)),
    }
    secret_check = validate_no_raw_secret_in_handoff(payload)
    if secret_check["status"] != "pass":
        payload["status"] = "blocked"
        payload["blocking_reasons"] = list(dict.fromkeys([*payload["blocking_reasons"], *secret_check["blocking_reasons"]]))
    safe = _safe(payload)
    if write:
        return write_config_handoff_report(safe)
    return safe


def write_config_handoff_report(payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
    safe = _safe(dict(payload or build_secure_config_handoff(write=False)))
    _report_path().write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
    return safe


def get_config_handoff_report() -> dict[str, Any]:
    path = _report_path()
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, Mapping):
                return _safe(dict(payload))
        except Exception:
            pass
    return build_secure_config_handoff()


def refresh_config_handoff_report() -> dict[str, Any]:
    return build_secure_config_handoff()
