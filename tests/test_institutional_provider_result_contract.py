from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sn_futures.data_providers.institutional_status_providers import (  # noqa: E402
    PublicPolicyRssContractProvider,
    ShfePublicContractProvider,
    TushareFuturesContractProvider,
)
from sn_futures.data_providers.provider_registry import build_provider_registry  # noqa: E402
from sn_futures.services.provider_status_canonical_service import build_canonical_provider_status  # noqa: E402


class ValidRowsClient:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows

    def fetch_rows(self) -> list[dict[str, object]]:
        return self.rows


class EmptyRowsClient:
    def fetch_rows(self) -> list[dict[str, object]]:
        return []


class RateLimitedClient:
    def __init__(self, secret: str = "") -> None:
        self.secret = secret

    def fetch_rows(self) -> list[dict[str, object]]:
        raise RuntimeError(f"429 rate limit exceeded token={self.secret}")


class ApiChangedClient:
    pass


class MalformedPayloadClient:
    def fetch_rows(self) -> dict[str, object]:
        return {"unexpected_payload": object()}


def assert_no_downstream_side_effects(result_dict: dict[str, object]) -> None:
    manifest = result_dict["manifest"]
    assert isinstance(manifest, dict)
    for key in (
        "feature_store_written",
        "training_invoked",
        "backtest_invoked",
        "active_updated",
        "customer_prediction_generated",
        "sample_data_used",
        "baseline_used",
    ):
        assert manifest[key] is False


def test_tushare_provider_result_handles_import_missing_without_secret_leakage() -> None:
    secret = "TUSHARE_SECRET_TOKEN_123456789"
    provider = TushareFuturesContractProvider(
        token=secret,
        client=None,
        module_loader=lambda: (_ for _ in ()).throw(ImportError(f"No module named tushare token={secret}")),
    )

    result = provider.fetch()
    payload = result.to_dict()
    status = result.to_status().to_dict()
    encoded = json.dumps(payload, ensure_ascii=False)

    assert result.success is False
    assert result.error_code == "import_missing"
    assert status["error_code"] == "import_missing"
    assert payload["manifest"]["source_statuses"][0]["error_code"] == "import_missing"
    assert secret not in encoded
    assert "***" in encoded
    assert_no_downstream_side_effects(payload)


def test_tushare_provider_result_handles_token_missing_before_any_api_call() -> None:
    provider = TushareFuturesContractProvider(token="", client=ValidRowsClient([{"ts_code": "SN2601.SHFE"}]))

    result = provider.fetch()
    payload = result.to_dict()

    assert result.success is False
    assert result.error_code == "token_missing"
    assert result.rows == []
    assert result.normalized_rows == []
    assert payload["manifest"]["blocking_reasons"]
    assert payload["manifest"]["source_statuses"][0]["error_code"] == "token_missing"
    assert_no_downstream_side_effects(payload)


def test_tushare_token_missing_takes_precedence_over_optional_import_probe() -> None:
    provider = TushareFuturesContractProvider(
        token="",
        client=ValidRowsClient([{"ts_code": "SN2601.SHFE", "trade_date": "2026-06-01"}]),
        module_loader=lambda: (_ for _ in ()).throw(ImportError("No module named tushare")),
    )

    result = provider.fetch()

    assert result.success is False
    assert result.error_code == "token_missing"
    assert result.rows == []
    assert result.normalized_rows == []


def test_shfe_public_provider_result_handles_api_changed_empty_malformed_rate_limit_and_valid_rows() -> None:
    valid_rows = [{"symbol": "SN", "trade_date": "2026-06-01", "inventory": 1200}]
    cases = [
        (ShfePublicContractProvider(client=ApiChangedClient()), False, "api_changed", 0),
        (ShfePublicContractProvider(client=EmptyRowsClient()), False, "no_rows", 0),
        (ShfePublicContractProvider(client=ValidRowsClient([{"symbol": "SN"}])), False, "missing_required_columns", 0),
        (ShfePublicContractProvider(client=RateLimitedClient()), False, "rate_limited", 0),
        (ShfePublicContractProvider(client=ValidRowsClient(valid_rows)), True, "", 1),
    ]

    for provider, success, error_code, normalized_count in cases:
        result = provider.fetch()
        payload = result.to_dict()
        status = result.to_status().to_dict()

        assert result.success is success
        assert result.error_code == error_code
        assert status["normalized_row_count"] == normalized_count
        assert payload["manifest"]["provider_id"] == "shfe_public"
        assert payload["manifest"]["source_statuses"]
        assert payload["manifest"]["allowed_for_feature_store"] is False
        assert_no_downstream_side_effects(payload)


def test_public_policy_rss_provider_result_handles_malformed_payload_as_structured_error() -> None:
    result = PublicPolicyRssContractProvider(client=MalformedPayloadClient()).fetch()
    payload = result.to_dict()
    status = result.to_status().to_dict()

    assert result.success is False
    assert result.error_code == "malformed_response"
    assert status["success"] is False
    assert status["normalized_row_count"] == 0
    assert payload["manifest"]["source_statuses"][0]["error_code"] == "malformed_response"
    assert payload["manifest"]["allowed_for_feature_store"] is False
    assert_no_downstream_side_effects(payload)


def test_public_policy_rss_provider_result_rejects_non_object_rows_as_malformed() -> None:
    result = PublicPolicyRssContractProvider(client=ValidRowsClient(["not-a-row"])).fetch()  # type: ignore[list-item]

    assert result.success is False
    assert result.error_code == "malformed_response"
    assert result.rows == []
    assert result.normalized_rows == []


def test_public_policy_rss_provider_result_requires_source_published_at_and_keeps_fetched_at_separate() -> None:
    malformed = PublicPolicyRssContractProvider(
        client=ValidRowsClient(
            [
                {
                    "title": "MIIT tin solder policy page",
                    "url": "https://www.miit.gov.cn/policy/tin",
                }
            ]
        )
    ).fetch()

    valid = PublicPolicyRssContractProvider(
        client=ValidRowsClient(
            [
                {
                    "title": "MIIT tin solder policy update",
                    "url": "https://www.miit.gov.cn/policy/tin",
                    "source_published_at": "2026-06-01T09:00:00+08:00",
                }
            ]
        )
    ).fetch()

    assert malformed.success is False
    assert malformed.error_code == "missing_required_columns"
    assert valid.success is True
    assert valid.normalized_rows[0]["source_published_at"] == "2026-06-01T09:00:00+08:00"
    assert valid.fetched_at != valid.source_timestamp
    assert valid.manifest["source_published_at_coverage"] == 1.0
    assert valid.manifest["allowed_for_feature_store"] is False
    assert_no_downstream_side_effects(valid.to_dict())


def test_provider_registry_includes_institutional_status_contract_providers() -> None:
    registry = build_provider_registry()

    assert "tushare_futures" in registry
    assert "shfe_public" in registry
    assert "public_policy_rss" in registry
    assert registry["tushare_futures"].data_kind == "futures_fundamentals"
    assert registry["shfe_public"].data_kind == "exchange_public"
    assert registry["public_policy_rss"].data_kind == "policy"


def test_canonical_provider_status_exposes_institutional_contract_registry(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))

    payload = build_canonical_provider_status()
    provider_ids = {row["provider_id"] for row in payload["provider_registry"]}

    assert payload["provider_interface_schema_version"] == "provider-result-v1"
    assert "tushare_futures" in provider_ids
    assert "shfe_public" in provider_ids
    assert "public_policy_rss" in provider_ids
