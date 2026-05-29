from __future__ import annotations

import json
from typing import Any, Mapping

from .json_utils import safe_json_dumps, sanitize_for_json
from ..data_providers.newsapi_provider import fetch_newsapi_status, test_newsapi_connection
from ..runtime import get_user_output_dir
from ..services.terminal_service import (
    build_terminal_backtest_diagnostics,
    build_terminal_data_status,
    build_terminal_drawdown,
    build_terminal_equity_curve,
    build_terminal_event_evidence,
    build_terminal_factor_diagnostics,
    build_terminal_forecast_path,
    build_terminal_learning_status,
    build_terminal_model_health,
    build_terminal_news_events,
    build_terminal_position_scenario,
    build_terminal_price_history,
    build_terminal_report_full,
    build_terminal_predictions,
    build_terminal_reports,
    build_terminal_snapshot,
    build_terminal_summary,
    build_terminal_system_health,
)
from ..services.settings_service import (
    get_key_diagnostics,
    get_terminal_settings_status,
    reset_terminal_secrets,
    save_terminal_secrets,
)
from ..services.runtime_diagnostics_service import build_runtime_data_diagnostics
from ..services.refresh_service import get_refresh_history, get_refresh_status
from ..services.institutional_refresh_service import run_institutional_refresh_all, run_institutional_refresh_steps
from ..services.feature_coverage_service import build_feature_coverage_report
from ..services.feature_store_service import build_feature_store, get_feature_store_status
from ..services.online_feature_readiness_service import build_online_feature_readiness_report
from ..services.training_dataset_service import build_training_dataset, get_training_dataset_status
from ..services.walk_forward_training_service import (
    get_candidate_training_status,
    get_walk_forward_results,
    run_candidate_training,
)
from ..services.model_promotion_service import (
    get_active_model_status,
    get_promotion_report,
    promote_candidate,
)
from ..services.candidate_diagnostics_service import build_candidate_diagnostics_report
from ..services.model_research_service import (
    get_model_experiment_detail,
    get_threshold_optimization,
    list_model_experiments,
    run_model_experiment,
)
from ..services.institutional_validation_service import (
    get_institutional_stress_tests,
    get_institutional_validation_report,
    run_institutional_validation,
)
from ..services.oof_trace_service import (
    get_oof_trace_sample,
    get_oof_trace_summary,
    get_research_oof_trace_summary,
)
from ..services.oof_integrity_service import (
    get_high_confidence_report,
    get_oof_integrity_report,
)
from ..services.research_artifact_service import get_research_artifacts
from ..services.research_backtest_service import get_research_backtest_report, get_research_equity_curve, run_research_backtest
from ..services.research_strategy_optimizer import get_strategy_optimization_report, optimize_research_strategy
from ..services.research_v3_service import run_candidate_v3_research
from ..services.news_relevance_diagnostics_service import build_news_relevance_diagnostics
from ..services.online_data_source_registry import build_online_data_source_registry
from ..services.provider_observability_service import (
    export_diagnostics_bundle,
    get_provider_status_detail,
    get_refresh_last_error,
    test_provider,
)


TERMINAL_API_DOCS = {
    "title": "SN 期货专业终端 API",
    "version": "v1",
    "framework": "ThreadingHTTPServer",
    "description": "当前后端仍使用现有 ThreadingHTTPServer 分发；本组接口为下一代专业终端提供稳定聚合合同。",
    "endpoints": [
        {"method": "GET", "path": "/api/terminal/docs", "description": "返回专业终端 API 文档。"},
        {"method": "GET", "path": "/api/terminal/summary", "description": "返回顶部状态栏和总览摘要。"},
        {"method": "GET", "path": "/api/terminal/snapshot", "description": "返回终端首页完整快照。"},
        {"method": "GET", "path": "/api/terminal/predictions", "description": "返回七周期预测卡片列表。"},
        {"method": "GET", "path": "/api/terminal/model-health", "description": "返回模型健康、晋级和降级状态。"},
        {"method": "GET", "path": "/api/terminal/learning-status", "description": "返回学习、回测、候选训练和任务状态。"},
        {"method": "GET", "path": "/api/terminal/backtest-diagnostics", "description": "返回指定周期的回测诊断。"},
        {"method": "POST", "path": "/api/terminal/position-scenario", "description": "返回合规持仓情景观察区。"},
        {"method": "GET", "path": "/api/terminal/reports", "description": "返回日报、周报、月报和事件报告摘要。"},
        {"method": "GET", "path": "/api/terminal/data-status", "description": "返回数据源、缓存和数据水位状态。"},
        {"method": "GET", "path": "/api/terminal/system-health", "description": "返回系统健康和真实性审计摘要。"},
        {"method": "GET", "path": "/api/terminal/runtime-diagnostics", "description": "诊断预测缓存、报告、新闻事件和运行期数据链路是否存在。"},
        {"method": "GET", "path": "/api/terminal/charts/price-history", "description": "????????????????????????????"},
        {"method": "GET", "path": "/api/terminal/charts/forecast-path", "description": "??????????????????"},
        {"method": "GET", "path": "/api/terminal/charts/equity-curve", "description": "??????????????????"},
        {"method": "GET", "path": "/api/terminal/charts/drawdown", "description": "??????????????????"},
        {"method": "GET", "path": "/api/terminal/events/news", "description": "????????? provider ???"},
        {"method": "GET", "path": "/api/terminal/events/relevance-report", "description": "返回 NewsAPI 新闻相关性过滤报告，区分入模、仅展示和已排除新闻。"},
        {"method": "GET", "path": "/api/terminal/events/relevance-diagnostics", "description": "返回 NewsAPI query group、关键词命中和排除原因诊断。"},
        {"method": "GET", "path": "/api/terminal/events/evidence", "description": "???????????"},
        {"method": "GET", "path": "/api/terminal/reports/full", "description": "???????? Markdown ???"},
        {"method": "GET", "path": "/api/terminal/factors/diagnostics", "description": "??????????????????"},
        {"method": "GET", "path": "/api/terminal/factors/coverage", "description": "审计真实行情、新闻、库存、基差、外盘和宏观字段能够支撑的因子覆盖率；不训练模型、不生成预测。"},
        {"method": "GET", "path": "/api/terminal/factors/online-readiness", "description": "审计自动在线字段可用性、因子准备度和下一轮模型研究优先级；不训练模型、不生成预测。"},
        {"method": "POST", "path": "/api/terminal/training-dataset/build", "description": "基于真实行情和可用因子构建无未来函数训练数据集；不训练模型、不生成预测、不生成回测。"},
        {"method": "GET", "path": "/api/terminal/training-dataset/status", "description": "返回训练数据集 manifest、样本数、特征数、标签分布和泄漏检查状态。"},
        {"method": "POST", "path": "/api/terminal/models/train-candidate", "description": "训练 candidate 模型并执行 purged walk-forward；不发布 active、不生成客户预测。"},
        {"method": "GET", "path": "/api/terminal/models/candidate-status", "description": "返回 candidate 模型训练、注册和非 active 状态。"},
        {"method": "GET", "path": "/api/terminal/models/walk-forward-results", "description": "返回 purged walk-forward 结果，可按 horizon 过滤。"},
        {"method": "POST", "path": "/api/terminal/models/promote-candidate", "description": "执行严格 promotion gate；只有通过真实验证的 candidate 才能写入 active。"},
        {"method": "GET", "path": "/api/terminal/models/active-status", "description": "返回当前 active model 状态。"},
        {"method": "GET", "path": "/api/terminal/models/promotion-report", "description": "返回最近一次 promotion gate 报告和中文失败原因。"},
        {"method": "GET", "path": "/api/terminal/models/candidate-diagnostics", "description": "返回 candidate 失败归因、校准、置信分层、regime、特征稳定性和下一步研究建议；不发布 active、不生成客户预测。"},
        {"method": "POST", "path": "/api/terminal/refresh/all", "description": "同步执行行情、在线基本面、新闻、事件、特征覆盖率和报告刷新；不自动生成客户预测。"},
        {"method": "POST", "path": "/api/terminal/refresh/market", "description": "刷新行情缓存和数据水位。"},
        {"method": "POST", "path": "/api/terminal/refresh/news", "description": "刷新 NewsAPI 新闻数据，未配置时清晰跳过。"},
        {"method": "GET", "path": "/api/terminal/newsapi/status", "description": "返回 NewsAPI 配置和最近在线验证状态，不泄露 key。"},
        {"method": "POST", "path": "/api/terminal/newsapi/test", "description": "使用 X-Api-Key header 执行低成本 NewsAPI 在线验证。"},
        {"method": "POST", "path": "/api/terminal/refresh/predictions", "description": "刷新预测缓存；数据不足时不生成伪预测。"},
        {"method": "POST", "path": "/api/terminal/refresh/reports", "description": "生成报告；数据不足时生成数据不足版报告。"},
        {"method": "GET", "path": "/api/terminal/refresh/status", "description": "返回最近一次刷新任务状态。"},
        {"method": "GET", "path": "/api/terminal/refresh/history", "description": "返回刷新任务历史。"},
        {"method": "GET", "path": "/api/terminal/refresh/last-error", "description": "返回最近一次刷新失败、跳过或错误原因。"},
        {"method": "GET", "path": "/api/terminal/providers/status-detail", "description": "返回数据源 provider 明细和刷新链路状态。"},
        {"method": "POST", "path": "/api/terminal/providers/test", "description": "测试 market/newsapi/shfe_public/akshare_news/miit_policy 状态，返回脱敏结果。"},
        {"method": "POST", "path": "/api/terminal/diagnostics/export", "description": "导出脱敏诊断包到本机日志目录。"},
        {"method": "GET", "path": "/api/terminal/settings/status", "description": "返回本机数据源密钥配置状态，只显示脱敏信息。"},
        {"method": "POST", "path": "/api/terminal/settings/secrets", "description": "保存 Alpha Vantage 与 NewsAPI 密钥到本机用户目录。"},
        {"method": "POST", "path": "/api/terminal/settings/reset", "description": "重置本机密钥，不删除其他用户数据。"},
    ],
}
TERMINAL_API_DOCS["endpoints"].extend(
    [
        {"method": "POST", "path": "/api/terminal/refresh/fundamentals", "description": "刷新期限结构、基差、库存和仓单底层数据；没有真实源时只返回缺失说明。"},
        {"method": "POST", "path": "/api/terminal/refresh/cross-market", "description": "刷新外盘、汇率和宏观字段；不作为沪锡主行情源。"},
    ]
)
TERMINAL_API_DOCS["endpoints"].append(
    {
        "method": "GET",
        "path": "/api/terminal/settings/key-diagnostics",
        "description": "返回 Alpha Vantage、NewsAPI 和托管数据服务 key 的读取来源、脱敏状态和最近验证状态；不返回完整 key。",
    }
)
TERMINAL_API_DOCS["endpoints"].extend(
    [
        {
            "method": "POST",
            "path": "/api/terminal/feature-store/build",
            "description": "Build versioned Feature Store v3 from real OHLCV, cross-market, and event factor inputs; no training or prediction.",
        },
        {
            "method": "GET",
            "path": "/api/terminal/feature-store/status",
            "description": "Return Feature Store version, field sources, alignment rules, usable fields, and excluded fields.",
        },
        {"method": "POST", "path": "/api/terminal/research/run-model-experiment", "description": "运行模型研究实验；只写研究产物，不发布 active、不生成客户预测、不降低 promotion gate。"},
        {"method": "GET", "path": "/api/terminal/research/experiments", "description": "列出模型研究实验。"},
        {"method": "GET", "path": "/api/terminal/research/experiment-detail", "description": "读取模型研究实验详情。"},
        {"method": "GET", "path": "/api/terminal/research/threshold-optimization", "description": "读取高置信选择性预测阈值优化结果。"},
        {"method": "POST", "path": "/api/terminal/validation/run-institutional-check", "description": "运行机构级反过拟合、成本压力和 regime 压力验证；不发布 active。"},
        {"method": "GET", "path": "/api/terminal/validation/report", "description": "读取机构级验证报告。"},
        {"method": "GET", "path": "/api/terminal/validation/stress-tests", "description": "读取成本和市场状态压力测试结果。"},
        {"method": "GET", "path": "/api/terminal/models/oof-trace-summary", "description": "读取指定 horizon 的 OOF 样本外验证轨迹摘要；不是客户预测。"},
        {"method": "GET", "path": "/api/terminal/models/oof-trace-sample", "description": "读取指定 horizon 的 OOF 样本外验证轨迹样本截取；不是客户预测。"},
        {"method": "GET", "path": "/api/terminal/models/oof-integrity-report", "description": "读取 OOF trace 完整性审计和高置信子集稳健性验证；不发布 active。"},
        {"method": "GET", "path": "/api/terminal/models/high-confidence-report", "description": "读取指定 horizon 的高置信 OOF 子集验证；不是客户预测。"},
        {"method": "GET", "path": "/api/terminal/online-data-sources/status", "description": "返回在线数据源 registry；客户不需要 CSV/Excel，系统自动尝试公开源、key 源和可选托管源。"},
        {"method": "GET", "path": "/api/terminal/research/oof-trace-summary", "description": "读取研究实验 OOF 样本外验证轨迹摘要。"},
        {"method": "POST", "path": "/api/terminal/research/run-candidate-v3", "description": "运行 candidate_v3 研究流程，生成 OOF、机构级验证、研究回测和归档；不发布 active、不生成客户预测。"},
        {"method": "POST", "path": "/api/terminal/research/run-backtest", "description": "基于 OOF trace 生成研究型收益曲线、回撤曲线和交易列表；不是客户预测。"},
        {"method": "GET", "path": "/api/terminal/research/backtest-report", "description": "读取研究型回测 Markdown 报告。"},
        {"method": "GET", "path": "/api/terminal/research/equity-curve", "description": "读取研究型 OOF 收益曲线。"},
        {"method": "GET", "path": "/api/terminal/research/artifacts", "description": "读取研究资料归档列表或指定 run_id 详情。"},
        {"method": "POST", "path": "/api/terminal/research/optimize-strategy", "description": "运行研究策略阈值优化；只在历史 folds 选阈值，不降低 promotion gate。"},
    ]
)


def _query_value(query: Mapping[str, list[str]] | None, key: str, default: str = "") -> str:
    if not query:
        return default
    values = query.get(key)
    if not values:
        return default
    return str(values[0])


def _parse_body(body: Any) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if body is None or body == "":
        return {}, None
    if isinstance(body, dict):
        return body, None
    if isinstance(body, (bytes, bytearray)):
        body = body.decode("utf-8", errors="replace")
    if isinstance(body, str):
        try:
            parsed = json.loads(body) if body.strip() else {}
        except Exception:
            return None, {"error": "invalid_json", "message": "请求体不是有效 JSON，请检查持仓情景输入。"}
        if not isinstance(parsed, dict):
            return None, {"error": "invalid_json", "message": "请求体必须是 JSON 对象。"}
        return parsed, None
    return None, {"error": "invalid_json", "message": "请求体格式不支持。"}


def _ok(payload: Any) -> tuple[int, dict[str, Any]]:
    # Force JSON serialisability here so tests can catch contract regressions
    # without needing to boot the HTTP server.
    safe_json_dumps(payload)
    return 200, sanitize_for_json(payload)


def handle_terminal_api(
    path: str,
    method: str = "GET",
    query: Mapping[str, list[str]] | None = None,
    body: Any = None,
) -> tuple[int, dict[str, Any]]:
    method = method.upper()
    if not path.startswith("/api/terminal/"):
        return 404, {"error": "not_found", "message": "不是 terminal API 路径。"}

    if method == "GET":
        if path == "/api/terminal/docs":
            return _ok(TERMINAL_API_DOCS)
        if path == "/api/terminal/summary":
            return _ok(build_terminal_summary())
        if path == "/api/terminal/snapshot":
            return _ok(build_terminal_snapshot())
        if path == "/api/terminal/predictions":
            return _ok({"predictions": build_terminal_predictions()})
        if path == "/api/terminal/model-health":
            return _ok(build_terminal_model_health())
        if path == "/api/terminal/learning-status":
            return _ok(build_terminal_learning_status())
        if path == "/api/terminal/backtest-diagnostics":
            return _ok(build_terminal_backtest_diagnostics(_query_value(query, "horizon", "")))
        if path == "/api/terminal/reports":
            return _ok(build_terminal_reports())
        if path == "/api/terminal/data-status":
            return _ok(build_terminal_data_status())
        if path == "/api/terminal/online-data-sources/status":
            return _ok(build_online_data_source_registry())
        if path == "/api/terminal/system-health":
            return _ok(build_terminal_system_health())
        if path == "/api/terminal/runtime-diagnostics":
            return _ok(build_runtime_data_diagnostics())
        if path == "/api/terminal/charts/price-history":
            return _ok(build_terminal_price_history())
        if path == "/api/terminal/charts/forecast-path":
            return _ok(build_terminal_forecast_path())
        if path == "/api/terminal/charts/equity-curve":
            return _ok(build_terminal_equity_curve())
        if path == "/api/terminal/charts/drawdown":
            return _ok(build_terminal_drawdown())
        if path == "/api/terminal/events/news":
            return _ok(build_terminal_news_events())
        if path == "/api/terminal/events/relevance-report":
            report_path = get_user_output_dir() / "events" / "news_relevance_report.json"
            try:
                payload = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else {}
            except Exception:
                payload = {}
            return _ok(payload or {"message_zh": "暂无新闻相关性报告，请先刷新新闻。", "used_in_model_count": 0, "rejected_count": 0})
        if path == "/api/terminal/events/relevance-diagnostics":
            return _ok(build_news_relevance_diagnostics())
        if path == "/api/terminal/events/evidence":
            return _ok(build_terminal_event_evidence(_query_value(query, "horizon", "tomorrow")))
        if path == "/api/terminal/reports/full":
            return _ok(build_terminal_report_full(_query_value(query, "type", "daily")))
        if path == "/api/terminal/factors/diagnostics":
            return _ok(build_terminal_factor_diagnostics())
        if path == "/api/terminal/factors/coverage":
            return _ok(build_feature_coverage_report(report_version=_query_value(query, "version", None)))
        if path == "/api/terminal/factors/online-readiness":
            return _ok(build_online_feature_readiness_report())
        if path == "/api/terminal/feature-store/status":
            return _ok(get_feature_store_status(version=_query_value(query, "version", "v3") or "v3"))
        if path == "/api/terminal/training-dataset/status":
            return _ok(get_training_dataset_status(dataset_version=_query_value(query, "dataset_version", "v1") or "v1"))
        if path == "/api/terminal/models/candidate-status":
            return _ok(get_candidate_training_status(candidate_version=_query_value(query, "candidate_version", "v1") or "v1"))
        if path == "/api/terminal/models/walk-forward-results":
            return _ok(get_walk_forward_results(_query_value(query, "horizon", ""), candidate_version=_query_value(query, "candidate_version", "v1") or "v1"))
        if path == "/api/terminal/models/active-status":
            return _ok(get_active_model_status())
        if path == "/api/terminal/models/promotion-report":
            return _ok(get_promotion_report(candidate_version=_query_value(query, "candidate_version", "v1") or "v1"))
        if path == "/api/terminal/models/candidate-diagnostics":
            return _ok(build_candidate_diagnostics_report())
        if path == "/api/terminal/models/oof-trace-summary":
            return _ok(get_oof_trace_summary(_query_value(query, "horizon", "1d"), candidate_version=_query_value(query, "candidate_version", "v1") or "v1"))
        if path == "/api/terminal/models/oof-trace-sample":
            return _ok(get_oof_trace_sample(_query_value(query, "horizon", "1d"), int(_query_value(query, "limit", "200") or "200"), candidate_version=_query_value(query, "candidate_version", "v1") or "v1"))
        if path == "/api/terminal/models/oof-integrity-report":
            return _ok(get_oof_integrity_report(candidate_version=_query_value(query, "candidate_version", "v1") or "v1"))
        if path == "/api/terminal/models/high-confidence-report":
            return _ok(get_high_confidence_report(_query_value(query, "horizon", "1d"), candidate_version=_query_value(query, "candidate_version", "v1") or "v1"))
        if path == "/api/terminal/research/experiments":
            return _ok(list_model_experiments())
        if path == "/api/terminal/research/experiment-detail":
            return _ok(get_model_experiment_detail(_query_value(query, "id", "")))
        if path == "/api/terminal/research/threshold-optimization":
            return _ok(get_threshold_optimization(_query_value(query, "id", "")))
        if path == "/api/terminal/research/oof-trace-summary":
            return _ok(get_research_oof_trace_summary(_query_value(query, "id", "")))
        if path == "/api/terminal/research/backtest-report":
            return _ok(
                get_research_backtest_report(
                    run_id=_query_value(query, "run_id", None),
                    candidate_version=_query_value(query, "candidate_version", "v3") or "v3",
                )
            )
        if path == "/api/terminal/research/equity-curve":
            return _ok(
                get_research_equity_curve(
                    run_id=_query_value(query, "run_id", None),
                    horizon=_query_value(query, "horizon", "1d") or "1d",
                    candidate_version=_query_value(query, "candidate_version", "v3") or "v3",
                )
            )
        if path == "/api/terminal/research/artifacts":
            return _ok(get_research_artifacts(run_id=_query_value(query, "run_id", None)))
        if path == "/api/terminal/validation/report":
            return _ok(get_institutional_validation_report(candidate_version=_query_value(query, "candidate_version", "v1") or "v1"))
        if path == "/api/terminal/validation/stress-tests":
            return _ok(get_institutional_stress_tests(candidate_version=_query_value(query, "candidate_version", "v1") or "v1"))
        if path == "/api/terminal/refresh/status":
            return _ok(get_refresh_status())
        if path == "/api/terminal/refresh/history":
            return _ok(get_refresh_history())
        if path == "/api/terminal/refresh/last-error":
            return _ok(get_refresh_last_error())
        if path == "/api/terminal/providers/status-detail":
            return _ok(get_provider_status_detail())
        if path == "/api/terminal/newsapi/status":
            return _ok(test_newsapi_connection())
        if path == "/api/terminal/settings/status":
            return _ok(get_terminal_settings_status())
        if path == "/api/terminal/settings/key-diagnostics":
            return _ok(get_key_diagnostics())
        return 404, {"error": "not_found", "message": "未知 terminal API 路径。"}

    if method == "POST":
        if path.startswith("/api/terminal/refresh/"):
            payload, error = _parse_body(body)
            if error is not None:
                return 400, error
            force = bool((payload or {}).get("force", False))
            if path == "/api/terminal/refresh/all":
                return _ok(run_institutional_refresh_all(force=force))
            if path == "/api/terminal/refresh/market":
                return _ok(run_institutional_refresh_steps(["market"], force=force))
            if path == "/api/terminal/refresh/fundamentals":
                return _ok(run_institutional_refresh_steps(["fundamentals", "features"], force=force))
            if path == "/api/terminal/refresh/cross-market":
                return _ok(run_institutional_refresh_steps(["online_cross_market", "features"], force=force))
            if path == "/api/terminal/refresh/news":
                return _ok(run_institutional_refresh_steps(["news", "event_relevance", "events", "features"], force=force))
            if path == "/api/terminal/refresh/predictions":
                return _ok(run_institutional_refresh_steps(["predictions"], force=force))
            if path == "/api/terminal/refresh/reports":
                return _ok(run_institutional_refresh_steps(["reports"], force=force))
            return 404, {"error": "not_found", "message": "未知 refresh API 路径。"}
        if path == "/api/terminal/position-scenario":
            payload, error = _parse_body(body)
            if error is not None:
                return 400, error
            return _ok(build_terminal_position_scenario(payload or {}))
        if path == "/api/terminal/settings/secrets":
            payload, error = _parse_body(body)
            if error is not None:
                return 400, error
            try:
                return _ok(save_terminal_secrets(payload or {}))
            except ValueError as exc:
                return 400, {"error": "invalid_secret", "message": str(exc)}
        if path == "/api/terminal/settings/reset":
            return _ok(reset_terminal_secrets())
        if path == "/api/terminal/providers/test":
            payload, error = _parse_body(body)
            if error is not None:
                return 400, error
            return _ok(test_provider(str((payload or {}).get("provider") or "")))
        if path == "/api/terminal/newsapi/test":
            return _ok(test_newsapi_connection())
        if path == "/api/terminal/diagnostics/export":
            return _ok(export_diagnostics_bundle())
        if path == "/api/terminal/feature-store/build":
            payload, error = _parse_body(body)
            if error is not None:
                return 400, error
            return _ok(build_feature_store(version=str((payload or {}).get("version") or "v3")))
        if path == "/api/terminal/training-dataset/build":
            payload, error = _parse_body(body)
            if error is not None:
                return 400, error
            raw_horizons = (payload or {}).get("horizons") or [1, 3, 5, 10, 20]
            horizons = [int(item) for item in raw_horizons] if isinstance(raw_horizons, list) else [1, 3, 5, 10, 20]
            min_coverage = float((payload or {}).get("min_feature_coverage", 0.7))
            return _ok(
                build_training_dataset(
                    horizons=horizons,
                    min_feature_coverage=min_coverage,
                    dataset_version=str((payload or {}).get("dataset_version") or "v1"),
                    feature_set=str((payload or {}).get("feature_set") or "ohlcv_technical_regime"),
                    feature_store_version=(str((payload or {}).get("feature_store_version")) if (payload or {}).get("feature_store_version") else None),
                )
            )
        if path == "/api/terminal/models/train-candidate":
            payload, error = _parse_body(body)
            if error is not None:
                return 400, error
            raw_horizons = (payload or {}).get("horizons") or ["1d", "3d", "5d", "10d", "20d"]
            horizons = [str(item) for item in raw_horizons] if isinstance(raw_horizons, list) else ["1d", "3d", "5d", "10d", "20d"]
            return _ok(
                run_candidate_training(
                    horizons=horizons,
                    candidate_version=str((payload or {}).get("candidate_version") or "v1"),
                    dataset_version=str((payload or {}).get("dataset_version") or "v1"),
                    feature_set=str((payload or {}).get("feature_set") or ""),
                    label_variants=(payload or {}).get("label_variants") if isinstance((payload or {}).get("label_variants"), list) else None,
                    models=(payload or {}).get("models") if isinstance((payload or {}).get("models"), list) else None,
                    calibration=(payload or {}).get("calibration") if isinstance((payload or {}).get("calibration"), list) else None,
                    no_trade_filters=(payload or {}).get("no_trade_filters") if isinstance((payload or {}).get("no_trade_filters"), list) else None,
                )
            )
        if path == "/api/terminal/models/promote-candidate":
            payload, _ = _parse_body(body)
            dry_query = str(_query_value(query, "dry_run", "") or "").lower() in {"1", "true", "yes"}
            dry_body = bool((payload or {}).get("dry_run")) if isinstance(payload, dict) else False
            return _ok(promote_candidate(candidate_version=str((payload or {}).get("candidate_version") or _query_value(query, "candidate_version", "v1") or "v1"), dry_run=dry_query or dry_body))
        if path == "/api/terminal/research/run-model-experiment":
            payload, error = _parse_body(body)
            if error is not None:
                return 400, error
            return _ok(run_model_experiment(payload or {}))
        if path == "/api/terminal/research/run-candidate-v3":
            payload, _ = _parse_body(body)
            raw_horizons = (payload or {}).get("horizons") or ["1d", "3d", "5d", "10d", "20d"]
            horizons = [str(item) for item in raw_horizons] if isinstance(raw_horizons, list) else ["1d", "3d", "5d", "10d", "20d"]
            return _ok(run_candidate_v3_research(horizons=horizons))
        if path == "/api/terminal/research/run-backtest":
            payload, _ = _parse_body(body)
            raw_horizons = (payload or {}).get("horizons") or ["1d", "3d", "5d", "10d", "20d"]
            horizons = [str(item) for item in raw_horizons] if isinstance(raw_horizons, list) else ["1d", "3d", "5d", "10d", "20d"]
            return _ok(run_research_backtest(candidate_version=str((payload or {}).get("candidate_version") or "v3"), horizons=horizons))
        if path == "/api/terminal/research/optimize-strategy":
            payload, _ = _parse_body(body)
            raw_horizons = (payload or {}).get("horizons") or ["1d", "3d", "5d", "10d", "20d"]
            horizons = [str(item) for item in raw_horizons] if isinstance(raw_horizons, list) else ["1d", "3d", "5d", "10d", "20d"]
            return _ok(optimize_research_strategy(candidate_version=str((payload or {}).get("candidate_version") or "v3"), horizons=horizons))
        if path == "/api/terminal/validation/run-institutional-check":
            payload, _ = _parse_body(body)
            return _ok(run_institutional_validation(candidate_version=str((payload or {}).get("candidate_version") or "v1"), dry_run=bool((payload or {}).get("dry_run"))))
        return 404, {"error": "not_found", "message": "未知 terminal API 路径。"}

    return 405, {"error": "method_not_allowed", "message": "该 terminal API 不支持当前请求方法。"}
