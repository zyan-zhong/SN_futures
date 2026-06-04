from __future__ import annotations

from typing import Any

def refresh_fundamentals(force: bool = False) -> dict[str, Any]:
    from .fundamental_data_service import refresh_fundamental_data

    return refresh_fundamental_data(force=force)


def refresh_shfe_direct_probe() -> dict[str, Any]:
    from .shfe_public_data_service import detect_shfe_direct_access

    result = detect_shfe_direct_access()
    return {
        "status": "success" if result.get("status") in {"accessible", "blocked_by_waf"} else "failed",
        "message_zh": result.get("message_zh") or result.get("error_message_zh") or "SHFE 官网直连探测已完成。",
        "output_files": [],
        "provider_attempts": [result],
        "shfe_direct_status": result.get("status"),
        "active_updated": False,
        "customer_prediction_generated": False,
        "baseline_used": False,
    }


def refresh_akshare_function_probe() -> dict[str, Any]:
    from .shfe_public_data_service import probe_akshare_futures_fundamental_functions

    result = probe_akshare_futures_fundamental_functions()
    return {
        "status": "success" if result.get("success") else "skipped",
        "message_zh": result.get("message_zh") or "AKShare 期货基础数据函数探测已完成。",
        "output_files": [],
        "provider_attempts": result.get("functions") or [],
        "active_updated": False,
        "customer_prediction_generated": False,
        "baseline_used": False,
    }


def refresh_shfe_inventory() -> dict[str, Any]:
    from .shfe_public_data_service import fetch_shfe_inventory_via_akshare

    return fetch_shfe_inventory_via_akshare()


def refresh_shfe_warehouse_receipts() -> dict[str, Any]:
    from .shfe_public_data_service import fetch_shfe_warehouse_receipt_via_akshare

    return fetch_shfe_warehouse_receipt_via_akshare()


def refresh_spot_basis() -> dict[str, Any]:
    from .shfe_public_data_service import fetch_spot_basis_via_akshare

    return fetch_spot_basis_via_akshare()


def refresh_exchange_daily() -> dict[str, Any]:
    from .shfe_public_data_service import fetch_exchange_daily_via_akshare

    return fetch_exchange_daily_via_akshare()


def refresh_member_positions() -> dict[str, Any]:
    from .shfe_public_data_service import fetch_member_position_via_akshare

    return fetch_member_position_via_akshare()


def refresh_cross_market(force: bool = False) -> dict[str, Any]:
    from .cross_market_data_service import refresh_cross_market_data

    return refresh_cross_market_data(force=force)


def refresh_online_cross_market(force: bool = False) -> dict[str, Any]:
    from .online_cross_market_service import refresh_online_cross_market_data

    return refresh_online_cross_market_data(force=force)


def refresh_online_lme_tin(force: bool = False) -> dict[str, Any]:
    from .online_lme_tin_service import refresh_online_lme_tin_data

    return refresh_online_lme_tin_data(force=force)


def refresh_managed_proxy(force: bool = False) -> dict[str, Any]:
    from .managed_data_proxy_service import refresh_managed_data_proxy

    return refresh_managed_data_proxy(force=force)


def refresh_tushare_futures(force: bool = False) -> dict[str, Any]:
    from .tushare_futures_service import refresh_tushare_futures_data

    return refresh_tushare_futures_data(force=force)


def refresh_tushare_contracts() -> dict[str, Any]:
    from .tushare_futures_service import fetch_fut_basic

    return fetch_fut_basic()


def refresh_tushare_daily() -> dict[str, Any]:
    from .tushare_futures_service import fetch_sn_fut_daily

    return fetch_sn_fut_daily()


def refresh_tushare_warehouse() -> dict[str, Any]:
    from .tushare_futures_service import fetch_sn_warehouse_receipt

    return fetch_sn_warehouse_receipt()


def refresh_tushare_settlement() -> dict[str, Any]:
    from .tushare_futures_service import fetch_sn_settlement

    return fetch_sn_settlement()


def refresh_tushare_holding() -> dict[str, Any]:
    from .tushare_futures_service import fetch_sn_holding

    return fetch_sn_holding()


def refresh_event_relevance() -> dict[str, Any]:
    from .news_relevance_service import refresh_news_relevance

    return refresh_news_relevance()


def run_institutional_refresh_all(force: bool = False) -> dict[str, Any]:
    """Run refresh-all with institutional factor source steps inserted.

    This wrapper keeps the existing refresh framework intact while ensuring
    fundamentals, cross-market data and news relevance are attempted before
    feature coverage/report generation.  It never creates predictions unless
    the existing prediction gate allows them.
    """
    from . import refresh_service as base
    if not base._LOCK.acquire(blocking=False):  # type: ignore[attr-defined]
        return {"status": "running", "message_zh": "已有刷新任务正在执行，请稍后再试。", "steps": []}
    try:
        return _run_institutional_refresh_all_unlocked(force=force)
    finally:
        base._LOCK.release()  # type: ignore[attr-defined]


def _run_institutional_refresh_all_unlocked(force: bool = False) -> dict[str, Any]:
    from . import refresh_service as base

    def run_steps(step_names: list[str], *, force: bool = False) -> dict[str, Any]:
        funcs = {
            "market": lambda: base.refresh_market_data(force=force),
            "shfe_direct_probe": refresh_shfe_direct_probe,
            "akshare_function_probe": refresh_akshare_function_probe,
            "shfe_inventory": refresh_shfe_inventory,
            "shfe_warehouse_receipts": refresh_shfe_warehouse_receipts,
            "spot_basis": refresh_spot_basis,
            "exchange_daily": refresh_exchange_daily,
            "member_positions": refresh_member_positions,
            "fundamentals": lambda: refresh_fundamentals(force=force),
            "online_cross_market": lambda: refresh_online_cross_market(force=force),
            "online_lme_tin": lambda: refresh_online_lme_tin(force=force),
            "managed_data_proxy": lambda: refresh_managed_proxy(force=force),
            "tushare_futures": lambda: refresh_tushare_futures(force=force),
            "tushare_contracts": refresh_tushare_contracts,
            "tushare_daily": refresh_tushare_daily,
            "tushare_warehouse": refresh_tushare_warehouse,
            "tushare_settlement": refresh_tushare_settlement,
            "tushare_holding": refresh_tushare_holding,
            "cross_market": lambda: refresh_cross_market(force=force),
            "news": lambda: base.refresh_news_data(force=force),
            "event_relevance": refresh_event_relevance,
            "events": base.refresh_event_store,
            "features": base.refresh_features,
            "reports": base.refresh_reports,
        }
        old_run_steps = base._run_steps  # type: ignore[attr-defined]
        try:
            # Reuse the base runner's status/history/log implementation by
            # temporarily exposing the institutional step names through a small
            # adapter.  Existing step functions are not changed.
            def adapter(names: list[str], *, force: bool = False) -> dict[str, Any]:
                expanded: list[str] = []
                for name in names:
                    if name in funcs:
                        expanded.append(name)
                    else:
                        expanded.append(name)
                return _run_expanded_with_base_logging(expanded, funcs, force=force)

            base._run_steps = adapter  # type: ignore[attr-defined]
            return base._run_steps(step_names, force=force)  # type: ignore[attr-defined]
        finally:
            base._run_steps = old_run_steps  # type: ignore[attr-defined]

    return run_steps(
        [
            "market",
            "shfe_direct_probe",
            "akshare_function_probe",
            "shfe_inventory",
            "shfe_warehouse_receipts",
            "spot_basis",
            "exchange_daily",
            "member_positions",
            "fundamentals",
            "online_cross_market",
            "online_lme_tin",
            "managed_data_proxy",
            "tushare_futures",
            "cross_market",
            "news",
            "event_relevance",
            "events",
            "features",
            "reports",
        ],
        force=force,
    )


def run_institutional_refresh_steps(step_names: list[str], *, force: bool = False) -> dict[str, Any]:
    from . import refresh_service as base

    if not base._LOCK.acquire(blocking=False):  # type: ignore[attr-defined]
        return {"status": "running", "message_zh": "已有刷新任务正在执行，请稍后再试。", "steps": []}
    try:
        return _run_institutional_refresh_steps_unlocked(step_names, force=force)
    finally:
        base._LOCK.release()  # type: ignore[attr-defined]


def _run_institutional_refresh_steps_unlocked(step_names: list[str], *, force: bool = False) -> dict[str, Any]:
    from . import refresh_service as base

    funcs = {
        "market": lambda: base.refresh_market_data(force=force),
        "shfe_direct_probe": refresh_shfe_direct_probe,
        "akshare_function_probe": refresh_akshare_function_probe,
        "shfe_inventory": refresh_shfe_inventory,
        "shfe_warehouse_receipts": refresh_shfe_warehouse_receipts,
        "spot_basis": refresh_spot_basis,
        "exchange_daily": refresh_exchange_daily,
        "member_positions": refresh_member_positions,
        "fundamentals": lambda: refresh_fundamentals(force=force),
        "online_cross_market": lambda: refresh_online_cross_market(force=force),
        "online_lme_tin": lambda: refresh_online_lme_tin(force=force),
        "managed_data_proxy": lambda: refresh_managed_proxy(force=force),
        "tushare_futures": lambda: refresh_tushare_futures(force=force),
        "tushare_contracts": refresh_tushare_contracts,
        "tushare_daily": refresh_tushare_daily,
        "tushare_warehouse": refresh_tushare_warehouse,
        "tushare_settlement": refresh_tushare_settlement,
        "tushare_holding": refresh_tushare_holding,
        "cross_market": lambda: refresh_cross_market(force=force),
        "news": lambda: base.refresh_news_data(force=force),
        "event_relevance": refresh_event_relevance,
        "events": base.refresh_event_store,
        "features": base.refresh_features,
        "reports": base.refresh_reports,
    }
    return _run_expanded_with_base_logging(step_names, funcs, force=force)


def _run_expanded_with_base_logging(step_names: list[str], funcs: dict[str, Any], *, force: bool = False) -> dict[str, Any]:
    from . import refresh_service as base

    # This mirrors refresh_service._run_steps intentionally so institutional
    # steps are represented in the same refresh_status/history files.
    run: dict[str, Any] = {
        "run_id": f"refresh-{int(base.time.time())}",
        "started_at": base._now(),  # type: ignore[attr-defined]
        "finished_at": "",
        "status": "running",
        "steps": [],
        "message_zh": "刷新任务执行中。",
        "active_updated": False,
        "customer_prediction_generated": False,
        "baseline_used": False,
    }
    base._write_json(base._status_path(), run)  # type: ignore[attr-defined]
    for name in step_names:
        if name not in funcs:
            run["steps"].append(
                {
                    "step_name": name,
                    "status": "failed",
                    "started_at": base._now(),  # type: ignore[attr-defined]
                    "finished_at": base._now(),  # type: ignore[attr-defined]
                    "duration_seconds": 0,
                    "message_zh": "未知刷新步骤",
                    "output_files": [],
                    "error": name,
                }
            )
        else:
            run["steps"].append(base._step(name, funcs[name]))  # type: ignore[attr-defined]
        base._write_json(base._status_path(), run)  # type: ignore[attr-defined]
    failed = [step for step in run["steps"] if step.get("status") == "failed"]
    run["status"] = "failed" if failed else "success"
    run["message_zh"] = "部分刷新步骤失败，已保留可用缓存。" if failed else "刷新任务完成。"
    run["finished_at"] = base._now()  # type: ignore[attr-defined]
    base._write_json(base._status_path(), run)  # type: ignore[attr-defined]
    base._append_history(run)  # type: ignore[attr-defined]
    return base.sanitize_for_json(run)
