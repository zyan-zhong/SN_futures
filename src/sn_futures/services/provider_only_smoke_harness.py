from __future__ import annotations

import json
import os
import tempfile
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

from ..api.json_utils import sanitize_for_json
from ..data_providers.akshare_news_provider import AkShareNewsProvider
from ..data_providers.base import PROVIDER_SCHEMA_VERSION, ProviderResult
from ..data_providers.institutional_status_providers import (
    PublicPolicyRssContractProvider,
    ShfePublicContractProvider,
    TushareFuturesContractProvider,
)
from ..utils.secret_sanitizer import sanitize_mapping, sanitize_text
from .local_api_provider_http_adapter import LocalApiProviderHttpAdapter


PROVIDER_ONLY_SMOKE_SCHEMA_VERSION = "provider-only-smoke-harness-v1"
DEFAULT_PROVIDERS = (
    "alpha_vantage",
    "newsapi",
    "akshare_news",
    "tushare_futures",
    "shfe_public",
    "public_policy_rss",
    "local_api_provider",
)
_LOCAL_FAKE_BASE_URL = "https://local-provider-smoke.invalid"
_LOCAL_FAKE_TOKEN = "provider-only-smoke-token"
_ENV_KEYS_TO_RESTORE = (
    "SN_DATA_DIR",
    "SN_INSIGHT_DATA_DIR",
    "SN_DISABLE_AUTO_SCHEDULER",
    "SN_ALPHA_VANTAGE_KEY",
    "SN_ALPHA_VANTAGE_API_KEY",
    "SN_NEWSAPI_KEY",
    "SN_TUSHARE_TOKEN",
    "SN_LOCAL_API_PROVIDER_TOKEN",
    "SN_LOCAL_API_PROVIDER_ENABLED",
    "SN_CUSTOM_HTTP_PROVIDER_API_KEY",
    "SN_MANAGED_PROXY_TOKEN",
    "SN_MANAGED_DATA_PROXY_TOKEN",
    "SN_MANAGED_PROXY_BASE_URL",
    "SN_MANAGED_DATA_PROXY_URL",
)
_DOWNSTREAM_FLAGS = (
    "feature_store_written",
    "production_cache_written",
    "training_invoked",
    "backtest_invoked",
    "active_updated",
    "customer_prediction_generated",
    "prediction_generated",
)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _safe(payload: Any) -> Any:
    return sanitize_for_json(sanitize_mapping(payload, extra_secrets=(_LOCAL_FAKE_TOKEN,)))


@contextmanager
def with_temp_runtime(runtime_dir: str | Path | None = None) -> Iterator[Path]:
    """Set local-only runtime env for provider smoke and restore it afterwards."""
    old_env = {key: os.environ.get(key) for key in _ENV_KEYS_TO_RESTORE}
    temp_dir: tempfile.TemporaryDirectory[str] | None = None
    try:
        if runtime_dir is None:
            temp_dir = tempfile.TemporaryDirectory(prefix="sn_provider_only_smoke_")
            runtime = Path(temp_dir.name)
        else:
            runtime = Path(runtime_dir)
            runtime.mkdir(parents=True, exist_ok=True)

        os.environ["SN_DATA_DIR"] = str(runtime)
        os.environ["SN_INSIGHT_DATA_DIR"] = str(runtime)
        os.environ["SN_DISABLE_AUTO_SCHEDULER"] = "1"
        for key in _ENV_KEYS_TO_RESTORE:
            if key in {"SN_DATA_DIR", "SN_INSIGHT_DATA_DIR", "SN_DISABLE_AUTO_SCHEDULER"}:
                continue
            os.environ.pop(key, None)
        yield runtime
    finally:
        for key, value in old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        if temp_dir is not None:
            temp_dir.cleanup()


def _source_status(
    provider_id: str,
    *,
    success: bool,
    error_code: str,
    row_count: int = 0,
    timed_out: bool = False,
    message: str = "",
) -> dict[str, Any]:
    return _safe(
        {
            "source_id": provider_id,
            "provider_id": provider_id,
            "function_name": "provider_only_smoke",
            "success": bool(success),
            "row_count": int(row_count),
            "error_code": "" if success else error_code,
            "error_message_sanitized": "" if success else sanitize_text(message or error_code),
            "timed_out": bool(timed_out),
        }
    )


def _blocked_result(provider_id: str, data_kind: str, error_code: str, *, allow_remote: bool, message: str = "") -> ProviderResult:
    fetched_at = _now()
    timed_out = error_code == "request_timeout"
    source_statuses = [
        _source_status(
            provider_id,
            success=False,
            error_code=error_code,
            timed_out=timed_out,
            message=message or error_code,
        )
    ]
    manifest = _safe(
        {
            "schema_version": PROVIDER_ONLY_SMOKE_SCHEMA_VERSION,
            "provider_interface_schema_version": PROVIDER_SCHEMA_VERSION,
            "provider_id": provider_id,
            "data_kind": data_kind,
            "allow_remote": bool(allow_remote),
            "fetched_at": fetched_at,
            "as_of": "",
            "row_count": 0,
            "normalized_row_count": 0,
            "source_statuses": source_statuses,
            "blocking_reasons": [error_code],
            "sample_data_used": False,
            "baseline_used": False,
            "cache_status": "missing",
            "stale_status": "missing",
            **{key: False for key in _DOWNSTREAM_FLAGS},
        }
    )
    return ProviderResult(
        provider_id=provider_id,
        data_kind=data_kind,
        success=False,
        status_code="blocked",
        error_code=error_code,
        rows=[],
        normalized_rows=[],
        fetched_at=fetched_at,
        source_timestamp="",
        as_of="",
        from_cache=False,
        stale=False,
        rate_limited=error_code == "rate_limited",
        schema_version=PROVIDER_SCHEMA_VERSION,
        manifest=manifest,
        sanitized_error=sanitize_text(message or error_code),
    )


def _mark_manifest(result: ProviderResult, *, allow_remote: bool) -> dict[str, Any]:
    manifest = dict(result.manifest if isinstance(result.manifest, Mapping) else {})
    source_statuses = manifest.get("source_statuses")
    if not isinstance(source_statuses, list) or not source_statuses:
        source_statuses = [
            _source_status(
                result.provider_id,
                success=result.success,
                error_code=result.error_code or "provider_smoke_failed",
                row_count=len(result.normalized_rows or result.rows),
                message=result.sanitized_error or result.error_code,
            )
        ]
    manifest.update(
        {
            "schema_version": str(manifest.get("schema_version") or PROVIDER_ONLY_SMOKE_SCHEMA_VERSION),
            "provider_interface_schema_version": PROVIDER_SCHEMA_VERSION,
            "provider_id": result.provider_id,
            "data_kind": result.data_kind,
            "allow_remote": bool(allow_remote),
            "row_count": len(result.rows),
            "normalized_row_count": len(result.normalized_rows),
            "source_statuses": source_statuses,
            "sample_data_used": False,
            "baseline_used": False,
            **{key: False for key in _DOWNSTREAM_FLAGS},
        }
    )
    return _safe(manifest)


def _result_item(result: ProviderResult, *, allow_remote: bool) -> dict[str, Any]:
    manifest = _mark_manifest(result, allow_remote=allow_remote)
    source_statuses = manifest.get("source_statuses") if isinstance(manifest.get("source_statuses"), list) else []
    return _safe(
        {
            "provider_id": result.provider_id,
            "data_kind": result.data_kind,
            "status": "pass" if result.success else "blocked",
            "success": bool(result.success),
            "error_code": result.error_code,
            "status_code": result.status_code,
            "row_count": len(result.rows),
            "normalized_row_count": len(result.normalized_rows),
            "source_statuses": source_statuses,
            "manifest": manifest,
            "sanitized_error": result.sanitized_error,
        }
    )


def _run_one_provider(
    provider_id: str,
    *,
    allow_remote: bool,
    fake_client: Any | None,
    runtime: Path,
) -> ProviderResult:
    provider = str(provider_id or "").strip().lower()
    if provider == "alpha_vantage":
        return _blocked_result(provider, "daily_bar", "remote_http_disabled", allow_remote=allow_remote)
    if provider == "newsapi":
        return _blocked_result(provider, "news_event", "remote_http_disabled", allow_remote=allow_remote)
    if provider == "akshare_news":
        if fake_client is None and not allow_remote:
            return _blocked_result(provider, "news", "remote_http_disabled", allow_remote=allow_remote)
        return AkShareNewsProvider(ak_module=fake_client if fake_client is not None else None, max_rows_per_source=50).fetch(
            persist=False,
            output_dir=runtime / "outputs",
        )
    if provider == "tushare_futures":
        if fake_client is None and not allow_remote:
            return _blocked_result(provider, "futures_fundamentals", "remote_http_disabled", allow_remote=allow_remote)
        return TushareFuturesContractProvider(client=fake_client, token="provider-only-smoke-token").fetch(
            persist=False,
            output_dir=runtime / "outputs",
        )
    if provider == "shfe_public":
        if fake_client is None and not allow_remote:
            return _blocked_result(provider, "exchange_public", "remote_http_disabled", allow_remote=allow_remote)
        return ShfePublicContractProvider(client=fake_client).fetch(persist=False, output_dir=runtime / "outputs")
    if provider == "public_policy_rss":
        if fake_client is None and not allow_remote:
            return _blocked_result(provider, "policy", "remote_http_disabled", allow_remote=allow_remote)
        return PublicPolicyRssContractProvider(client=fake_client).fetch(persist=False, output_dir=runtime / "outputs")
    if provider == "local_api_provider":
        if fake_client is None and not allow_remote:
            return _blocked_result(provider, "market_daily_bar", "remote_http_disabled", allow_remote=allow_remote)
        adapter = LocalApiProviderHttpAdapter(
            provider_id=provider,
            base_url=_LOCAL_FAKE_BASE_URL,
            token=_LOCAL_FAKE_TOKEN,
            data_kind="market_daily_bar",
            http_client=fake_client,
            allow_remote=allow_remote,
            timeout_seconds=10,
        )
        return adapter.smoke()
    return _blocked_result(provider or "unknown_provider", "provider_smoke", "unknown_provider", allow_remote=allow_remote)


def _safe_run_one_provider(
    provider_id: str,
    *,
    allow_remote: bool,
    fake_client: Any | None,
    runtime: Path,
) -> ProviderResult:
    try:
        return _run_one_provider(provider_id, allow_remote=allow_remote, fake_client=fake_client, runtime=runtime)
    except TimeoutError as exc:
        return _blocked_result(provider_id, "provider_smoke", "request_timeout", allow_remote=allow_remote, message=str(exc))
    except Exception as exc:
        message = sanitize_text(str(exc))
        lower = message.lower()
        if "rate" in lower or "limit" in lower or "429" in lower:
            error_code = "rate_limited"
        elif "timeout" in lower:
            error_code = "request_timeout"
        elif "malformed" in lower:
            error_code = "malformed_response"
        else:
            error_code = "request_failed"
        return _blocked_result(provider_id, "provider_smoke", error_code, allow_remote=allow_remote, message=message)


def run_provider_only_smoke(
    providers: Sequence[str] | None = None,
    *,
    allow_remote: bool = False,
    runtime_dir: str | Path | None = None,
    fake_clients: Mapping[str, Any] | None = None,
    persist: bool = False,
    output_json_path: str | Path | None = None,
) -> dict[str, Any]:
    requested = tuple(str(provider).strip().lower() for provider in (providers or DEFAULT_PROVIDERS) if str(provider).strip())
    fake_client_map = {str(key).strip().lower(): value for key, value in dict(fake_clients or {}).items()}
    with with_temp_runtime(runtime_dir) as runtime:
        items = [
            _result_item(
                _safe_run_one_provider(
                    provider,
                    allow_remote=allow_remote,
                    fake_client=fake_client_map.get(provider),
                    runtime=runtime,
                ),
                allow_remote=allow_remote,
            )
            for provider in requested
        ]
        passed_count = sum(1 for item in items if item.get("status") == "pass")
        failed_count = len(items) - passed_count
        status = "pass" if items and failed_count == 0 else ("partial_success" if passed_count else "blocked")
        report_path = Path(output_json_path) if output_json_path is not None else runtime / "outputs" / "diagnostics" / "provider_only_smoke_report.json"
        report = _safe(
            {
                "schema_version": PROVIDER_ONLY_SMOKE_SCHEMA_VERSION,
                "generated_at": _now(),
                "status": status,
                "allow_remote": bool(allow_remote),
                "warnings": ["explicit_remote_smoke_enabled"] if allow_remote else [],
                "runtime_dir": str(runtime),
                "report_path": str(report_path),
                "provider_count": len(items),
                "passed_count": passed_count,
                "failed_count": failed_count,
                "providers": items,
                **{key: False for key in _DOWNSTREAM_FLAGS},
            }
        )
        if persist:
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return report
