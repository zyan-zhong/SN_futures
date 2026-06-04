from __future__ import annotations

import sys

sys.path.insert(0, "src")

from sn_futures.services.tushare_param_probe_service import classify_tushare_error, validate_required_columns


def test_tushare_error_classification_distinguishes_operational_failures() -> None:
    assert classify_tushare_error(RuntimeError("permission denied: no access to fut_settle")) == "permission_denied"
    assert classify_tushare_error(RuntimeError("积分不足，超过每分钟访问频率限制")) == "quota_limited"
    assert classify_tushare_error(RuntimeError("token invalid or auth failed")) == "key_invalid"
    assert classify_tushare_error(RuntimeError("connection timeout")) == "network_failed"
    assert classify_tushare_error(RuntimeError("unexpected server error")) == "request_failed"


def test_schema_mismatch_is_not_reported_as_generic_request_failed() -> None:
    status = validate_required_columns("fut_holding", ["trade_date", "symbol", "broker", "long_hld"])

    assert status["ok"] is False
    assert status["status"] == "schema_mismatch"
    assert "short_hld" in status["missing_columns"]
