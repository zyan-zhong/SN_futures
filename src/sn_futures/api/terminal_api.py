from __future__ import annotations

import json
from typing import Any, Mapping

from .json_utils import safe_json_dumps, sanitize_for_json
from .public_terminal_contracts import PUBLIC_TERMINAL_API_ENDPOINTS, PUBLIC_TERMINAL_RESPONSE_SCHEMAS
from .terminal_router import build_terminal_router
from ..core.data_safety import assert_public_payload_real_or_blocked
from ..public_terminal.schema import build_public_terminal_openapi
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
    build_terminal_predictions_payload,
    build_terminal_reports,
    build_terminal_summary,
    build_terminal_system_health,
)
from ..services.terminal_snapshot_perf import build_terminal_snapshot, build_terminal_snapshot_lite
from ..services.settings_service import (
    get_key_diagnostics,
    get_terminal_settings_status,
    reset_terminal_secrets,
    save_terminal_secrets,
)
from ..services.api_response_cache import cached_call, clear_api_response_cache
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
from ..services.active_release_service import approve_active_release
from ..services.active_absence_diagnostics_service import build_active_absence_diagnostics
from ..services.market_analysis_service import build_market_analysis
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
from ..services.feature_store_v4_service import build_feature_store_v4, run_candidate_v4_research
from ..services.feature_store_v5_service import build_feature_store_v5, build_feature_store_v6
from ..services.feature_store_v7_service import build_feature_store_v7, build_training_dataset_v7
from ..services.feature_store_v10_service import build_feature_store_v10
from ..services.feature_store_v11_service import build_feature_store_v11, run_managed_proxy_v11_real_loop
from ..services.feature_store_v12_service import build_feature_store_v12, get_feature_store_v12_status
from ..services.feature_store_v12_input_contract_service import (
    build_v12_input_contract_report,
    get_latest_v12_input_contract_report,
)
from ..services.feature_store_v12_build_plan_service import (
    get_latest_v12_build_plan_report,
    write_v12_build_plan_report,
)
from ..services.feature_store_v12_controlled_build_service import (
    execute_feature_store_v12_controlled_build,
    get_latest_v12_controlled_build_report,
)
from ..services.prediction_workspace_status_service import build_prediction_workspace_status
from ..services.setup_checklist_status_service import (
    build_setup_checklist_status,
    run_setup_checklist_safe_action,
    validate_no_forbidden_setup_actions,
)
from ..services.setup_action_run_ledger_service import (
    get_setup_action_history,
    record_setup_action_result,
    summarize_setup_action_telemetry,
)
from ..services.managed_data_audit_service import build_managed_audit_manifest, compute_managed_audit_readiness, get_latest_managed_audit_manifest
from ..services.managed_data_quality_service import build_managed_data_quality_scorecard, get_latest_managed_data_quality_scorecard
from ..services.managed_proxy_health_service import check_managed_proxy_health, get_managed_proxy_health, get_managed_proxy_readiness
from ..services.managed_proxy_reliability_service import (
    get_managed_proxy_reliability_report,
    run_managed_proxy_canary_check,
)
from ..services.managed_proxy_setup_service import (
    get_managed_proxy_setup_status,
    refresh_managed_proxy_setup,
    run_managed_proxy_schema_dry_run,
    validate_managed_proxy_config_source,
    validate_managed_proxy_endpoint_contract,
)
from ..services.managed_proxy_config_wizard_service import (
    get_managed_proxy_config_wizard,
    refresh_managed_proxy_config_wizard,
)
from ..services.managed_proxy_config_handoff_service import (
    get_config_handoff_report,
    refresh_config_handoff_report,
)
from ..services.local_api_provider_hub_service import (
    get_local_api_provider_hub,
    refresh_local_api_provider_hub,
)
from ..services.provider_credentials_service import (
    get_provider_credentials_report,
    refresh_provider_credentials_report,
)
from ..services.provider_smoke_test_service import get_latest_provider_smoke_report, run_provider_smoke_test
from ..services.provider_only_smoke_harness import run_provider_only_smoke
from ..public_terminal.provider_smoke_result_bridge_service import bridge_provider_smoke_result
from ..public_terminal.event_service import build_public_event_center
from ..public_terminal.market_service import build_public_market
from ..public_terminal.readiness_service import build_public_terminal_readiness
from ..public_terminal.report_service import build_public_report
from ..public_terminal.refresh_orchestrator import (
    cancel_public_refresh_task,
    get_public_refresh_task,
    start_public_refresh_data_status_task,
)
from ..prediction_core.realtime_loop import build_public_prediction_status_payload
from ..services.managed_proxy_operator_runbook_service import (
    get_operator_onboarding_runbook,
    refresh_operator_onboarding_runbook,
)
from ..services.managed_proxy_schema_mapper_service import get_schema_mapping_report, refresh_schema_mapping_report
from ..services.managed_pit_replay_service import get_latest_pit_replay_report, run_pit_replay_harness
from ..services.managed_proxy_sample_fixture_service import (
    get_latest_sample_fixture_report,
    import_managed_proxy_sample_fixture,
    run_fixture_contract_tests,
)
from ..services.managed_proxy_endpoint_smoke_service import get_latest_endpoint_smoke_report, run_endpoint_smoke_test
from ..services.managed_proxy_quarantine_snapshot_service import (
    get_latest_quarantine_snapshot_report,
    pull_managed_proxy_quarantine_snapshot,
)
from ..services.managed_proxy_quarantine_contract_service import (
    build_quarantine_contract_report,
    get_latest_quarantine_contract_report,
    promote_quarantine_to_research_cache,
)
from ..services.managed_data_backfill_planner_service import (
    get_latest_backfill_planner_report,
    write_backfill_planner_report,
)
from ..services.managed_data_production_cache_gate_service import (
    build_production_cache_gate_report,
    get_latest_production_cache_gate_report,
)
from ..services.regime_balanced_dataset_service import build_training_dataset_v10
from ..services.training_dataset_v12_service import build_training_dataset_v12, get_training_dataset_v12_status
from ..services.candidate_v5_research_service import run_candidate_v5_research
from ..services.candidate_v6_gated_research_service import run_candidate_v6_gated_research
from ..services.candidate_v7_research_service import run_candidate_v7_research
from ..services.candidate_v8_research_service import run_candidate_v8_research
from ..services.candidate_v8_diagnostics_service import build_candidate_v8_validation_diagnostics
from ..services.candidate_v9_research_service import run_candidate_v9_research
from ..services.candidate_v10_research_service import run_candidate_v10_research
from ..services.candidate_v12_research_service import get_candidate_v12_report, run_candidate_v12_research
from ..services.cpcv_validation_service import build_cpcv_report
from ..services.year_concentration_service import (
    get_year_concentration_report,
    refresh_year_concentration,
)
from ..services.cost_stress_attribution_service import (
    get_candidate_v10_report,
    get_cost_stress_attribution_report,
    refresh_cost_stress_attribution,
)
from ..services.v10_cost_failure_research_service import (
    build_cost_failure_research_report,
    get_v10_cost_failure_research_report,
)
from ..services.candidate_v10_remediation_preflight_service import (
    build_remediation_preflight,
    get_v10_remediation_preflight,
)
from ..services.shadow_mode_readiness_service import (
    build_shadow_mode_readiness_spec,
    get_shadow_mode_readiness_spec,
)
from ..services.shadow_output_contract_service import (
    build_shadow_output_contract_report,
    build_shadow_output_dry_run_artifact,
    get_shadow_output_contract_report,
    refresh_shadow_output_contract_report,
)
from ..services.shadow_replay_evaluator_service import (
    build_shadow_replay_evaluator,
    get_shadow_replay_report,
)
from ..services.model_registry_safety_service import (
    build_registry_safety_report,
    get_model_registry_safety_report,
)
from ..services.governance_access_control_service import (
    get_access_control_report,
    refresh_access_control_report,
)
from ..services.governance_observability_service import (
    get_governance_observability_report,
    refresh_governance_observability_report,
)
from ..services.incident_drill_service import (
    get_incident_drill_report,
    refresh_lockdown_state_report,
    run_incident_drill_simulation,
)
from ..services.manual_approval_service import (
    build_manual_approval_status,
    create_manual_approval_request,
    record_manual_approval_decision,
    refresh_manual_approval_status,
)
from ..services.research_decision_board_service import (
    build_research_decision_board,
    get_research_decision_board,
)
from ..services.evidence_bundle_service import get_latest_evidence_bundle, write_evidence_bundle
from ..services.evidence_freshness_service import build_evidence_freshness_report, get_evidence_freshness_report
from ..services.external_audit_export_service import get_external_audit_export, write_external_audit_package
from ..services.governance_maturity_matrix_service import get_latest_governance_maturity_matrix, write_governance_maturity_matrix
from ..services.model_card_service import get_latest_model_card, write_model_card
from ..services.production_cutover_checklist_service import (
    build_cutover_report,
    build_noop_release_plan,
    get_production_cutover_checklist,
)
from ..services.promotion_dry_run_evidence_service import (
    build_promotion_dry_run_evidence,
    get_promotion_dry_run_evidence,
)
from ..services.post_release_monitoring_spec_service import (
    build_post_release_monitoring_spec,
    get_post_release_monitoring_spec,
)
from ..services.rollback_rehearsal_service import (
    build_rollback_rehearsal_plan,
    get_latest_rollback_rehearsal_report,
    simulate_artifact_quarantine,
)
from ..services.experiment_hypothesis_registry_service import (
    build_anti_p_hacking_ledger,
    create_hypothesis_template,
    get_hypothesis_registry,
)
from ..services.research_run_ledger_service import build_run_ledger_report, get_run_ledger_report
from ..services.readiness_dag_service import get_readiness_dag_report, run_readiness_checks_dry_run, write_readiness_dag_report
from ..services.multi_objective_research_optimizer import optimize_multi_objective_research_strategy
from ..services.learning_scheduler_service import (
    get_learning_scheduler_status,
    pause_learning_scheduler,
    resume_learning_scheduler,
    run_learning_scheduler_once,
)
from ..services.task_queue_service import KNOWN_TASK_KINDS, cancel_task, get_recent_tasks, get_task_status, start_task
from ..services.task_notification_service import build_task_notifications
from ..services.performance_diagnostics_service import run_api_performance_diagnostics
from ..services.all_api_smoke_service import run_all_terminal_api_smoke
from ..services.cache_invalidation_service import invalidate_terminal_caches
from ..services.data_watermark_service import get_data_watermark_report
from ..services.data_consistency_audit_service import build_data_consistency_report
from ..services.full_system_report_service import build_full_system_txt_report, get_latest_full_system_txt_report
from ..services.system_report_triage_service import build_system_repair_plan, get_latest_system_repair_plan
from ..services.process_lifecycle_service import get_process_status, request_server_shutdown
from ..services.system_stability_audit_service import build_system_stability_audit
from ..services.chart_payload_service import (
    build_drawdown_curve_payload,
    build_equity_curve_payload,
    build_price_chart_payload,
    build_volume_chart_payload,
)
from ..services.news_relevance_diagnostics_service import build_news_relevance_diagnostics
from ..services.news_source_quality_service import build_source_quality_report
from ..services.online_data_source_registry import build_online_data_source_registry
from ..services.provider_observability_service import (
    export_diagnostics_bundle,
    get_provider_status_detail,
    get_refresh_last_error,
    test_provider,
)
from ..services.real_data_coverage_validation_service import get_candidate_v6_readiness


TERMINAL_API_DOCS = {
    "title": "SN 期货专业终端 API",
    "version": "v1",
    "framework": "ThreadingHTTPServer",
    "description": "当前后端仍使用现有 ThreadingHTTPServer 分发；本组接口为下一代专业终端提供稳定聚合合同。",
    "endpoints": [
        {"method": "GET", "path": "/api/terminal/docs", "description": "返回专业终端 API 文档。"},
        {"method": "GET", "path": "/api/terminal/summary", "description": "返回顶部状态栏和总览摘要。"},
        {"method": "GET", "path": "/api/terminal/snapshot-lite", "description": "返回首屏连接用轻量快照，不同步执行重任务。"},
        {"method": "GET", "path": "/api/terminal/snapshot", "description": "返回缓存后的完整终端快照，避免重复重计算。"},
        {"method": "GET", "path": "/api/terminal/predictions", "description": "返回七周期预测卡片列表。"},
        {"method": "GET", "path": "/api/terminal/model-health", "description": "返回模型健康、晋级和降级状态。"},
        {"method": "GET", "path": "/api/terminal/learning-status", "description": "返回学习、回测、候选训练和任务状态。"},
        {"method": "GET", "path": "/api/terminal/backtest-diagnostics", "description": "返回指定周期的回测诊断。"},
        {"method": "GET", "path": "/api/terminal/backtest/auditable", "description": "只读读取可审计研究回测 BacktestManifest、metrics、equity 和 trades；不从 UI chart payload 拼回测。"},
        {"method": "POST", "path": "/api/terminal/position-scenario", "description": "返回合规持仓情景观察区。"},
        {"method": "GET", "path": "/api/terminal/reports", "description": "返回日报、周报、月报和事件报告摘要。"},
        {"method": "GET", "path": "/api/terminal/data-status", "description": "返回数据源、缓存和数据水位状态。"},
        {"method": "GET", "path": "/api/terminal/data-consistency-report", "description": "审计行情历史、图表、行情分析和数据水位是否指向同一最新真实日期。"},
        {"method": "GET", "path": "/api/terminal/system-health", "description": "返回系统健康和真实性审计摘要。"},
        {"method": "GET", "path": "/api/terminal/runtime-diagnostics", "description": "诊断预测缓存、报告、新闻事件和运行期数据链路是否存在。"},
        {"method": "GET", "path": "/api/terminal/charts/price-history", "description": "????????????????????????????"},
        {"method": "GET", "path": "/api/terminal/charts/volume", "description": "返回成交量/持仓量图表 payload；缺字段时返回明确空状态，不绘制空白图。"},
        {"method": "GET", "path": "/api/terminal/market-analysis", "description": "基于真实 OHLCV、technical 和 regime 输出专业行情分析；不是预测，不生成交易点位。"},
        {"method": "GET", "path": "/api/terminal/charts/forecast-path", "description": "??????????????????"},
        {"method": "GET", "path": "/api/terminal/charts/equity-curve", "description": "??????????????????"},
        {"method": "GET", "path": "/api/terminal/charts/drawdown", "description": "??????????????????"},
        {"method": "GET", "path": "/api/terminal/events/news", "description": "????????? provider ???"},
        {"method": "GET", "path": "/api/terminal/events/relevance-report", "description": "返回 NewsAPI 新闻相关性过滤报告，区分入模、仅展示和已排除新闻。"},
        {"method": "GET", "path": "/api/terminal/events/relevance-diagnostics", "description": "返回 NewsAPI query group、关键词命中和排除原因诊断。"},
        {"method": "GET", "path": "/api/terminal/events/source-quality-report", "description": "返回新闻源白名单、黑名单和 source reliability 诊断。"},
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
        {"method": "POST", "path": "/api/terminal/models/approve-active", "description": "人工审批发布 active；必须先通过 dry-run gate 和机构级验证，不接实盘交易。"},
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
TERMINAL_API_DOCS["response_schemas"] = dict(PUBLIC_TERMINAL_RESPONSE_SCHEMAS)
TERMINAL_API_DOCS["endpoints"].extend(PUBLIC_TERMINAL_API_ENDPOINTS)
TERMINAL_API_DOCS["public_terminal"] = build_public_terminal_openapi()
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
TERMINAL_API_DOCS["endpoints"].append(
    {
        "method": "POST",
        "path": "/api/terminal/refresh/tushare",
        "description": "Refresh Tushare SHFE tin futures fundamentals; no model training, active promotion or customer prediction.",
    }
)
TERMINAL_API_DOCS["endpoints"].append(
    {
        "method": "POST",
        "path": "/api/terminal/refresh/managed-proxy",
        "description": "Refresh managed structured fundamentals; no CSV/Excel, no fake data, no prediction.",
    }
)
TERMINAL_API_DOCS["endpoints"].append(
    {
        "method": "GET",
        "path": "/api/terminal/models/candidate-v6/readiness",
        "description": "Return candidate_v6 real-data readiness from Feature Store v5 coverage; no model training, active publishing, or customer prediction.",
    }
)
TERMINAL_API_DOCS["endpoints"].extend(
    [
        {
            "method": "GET",
            "path": "/api/terminal/training-dataset/v12",
            "description": "Return Training Dataset v12 blocked-first manifest status; Feature Store v12 is the only allowed source.",
        },
        {
            "method": "POST",
            "path": "/api/terminal/training-dataset/build-v12",
            "description": "Build Training Dataset v12 only when Feature Store v12, PIT readiness and managed coverage pass; no candidate training or active publish.",
        },
    ]
)
TERMINAL_API_DOCS["endpoints"].extend(
    [
        {
            "method": "POST",
            "path": "/api/terminal/feature-store/build",
            "description": "Build versioned Feature Store v3/v4/v5/v6/v7/v10/v11/v12 from real data inputs; v12 requires managed proxy health readiness; no model training, active publishing, or customer prediction.",
        },
        {
            "method": "GET",
            "path": "/api/terminal/feature-store/status",
            "description": "Return Feature Store version, field sources, alignment rules, usable fields, and excluded fields.",
        },
        {
            "method": "GET",
            "path": "/api/terminal/feature-store/v12",
            "description": "Return Feature Store v12 managed proxy health + PIT audit gate status; no model training or prediction.",
        },
        {
            "method": "POST",
            "path": "/api/terminal/feature-store/build-v12",
            "description": "Build Feature Store v12 only when managed proxy health and PIT audit pass; no training dataset auto-trigger.",
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
        {"method": "POST", "path": "/api/terminal/research/run-candidate-v4", "description": "仅当真实 cross-market/event 增量字段达标时运行 candidate_v4；否则返回阻断原因，不训练、不发布 active。"},
        {"method": "POST", "path": "/api/terminal/research/run-candidate-v5", "description": "基于 Feature Store v5 训练 candidate_v5，生成 OOF、研究回测、多目标优化、机构级验证和 promotion dry-run；不发布 active。"},
        {"method": "POST", "path": "/api/terminal/research/run-backtest", "description": "基于 OOF trace 生成研究型收益曲线、回撤曲线和交易列表；不是客户预测。"},
        {"method": "GET", "path": "/api/terminal/research/backtest-report", "description": "读取研究型回测 Markdown 报告。"},
        {"method": "GET", "path": "/api/terminal/research/equity-curve", "description": "读取研究型 OOF 收益曲线。"},
        {"method": "GET", "path": "/api/terminal/research/artifacts", "description": "读取研究资料归档列表或指定 run_id 详情。"},
        {"method": "POST", "path": "/api/terminal/research/optimize-strategy", "description": "运行研究策略阈值优化；只在历史 folds 选阈值，不降低 promotion gate。"},
        {"method": "POST", "path": "/api/terminal/research/optimize-multi-objective", "description": "运行 candidate 多目标研究优化；评估收益、回撤、DSR/PBO、成本压力和集中度约束，不写 active。"},
    ]
)
TERMINAL_API_DOCS["endpoints"].extend(
    [
        {"method": "GET", "path": "/api/terminal/learning-scheduler/status", "description": "读取本地自学习调度器状态、最近运行、下次计划和失败原因；不会自动发布 active。"},
        {"method": "POST", "path": "/api/terminal/learning-scheduler/run", "description": "手动触发本地自学习调度器；只做 refresh、Feature Store、candidate、验证和归档，不写 active。"},
        {"method": "POST", "path": "/api/terminal/learning-scheduler/pause", "description": "暂停本地自学习调度器。"},
        {"method": "POST", "path": "/api/terminal/learning-scheduler/resume", "description": "恢复本地自学习调度器。"},
    ]
)
TERMINAL_API_DOCS["endpoints"].extend(
    [
        {"method": "GET", "path": "/api/terminal/performance/diagnostics", "description": "计时关键终端 API，输出缓存命中、慢原因和推荐修复。"},
        {"method": "POST", "path": "/api/terminal/tasks/start", "description": "启动异步任务，避免 refresh/train/backtest/validation 阻塞 HTTP。"},
        {"method": "GET", "path": "/api/terminal/tasks/status", "description": "读取异步任务状态。"},
        {"method": "GET", "path": "/api/terminal/tasks/recent", "description": "读取最近异步任务。"},
        {"method": "GET", "path": "/api/terminal/task-notifications", "description": "Task Notification Center state; read-only and suppresses stale failed research task toast overlays."},
        {"method": "POST", "path": "/api/terminal/tasks/cancel", "description": "请求取消异步任务。"},
    ]
)


TERMINAL_API_DOCS["endpoints"].extend(
    [
        {
            "method": "GET",
            "path": "/api/terminal/system/process-status",
            "description": "Read local backend process runtime status; does not start tasks or expose secrets.",
        },
        {
            "method": "POST",
            "path": "/api/terminal/system/shutdown",
            "description": "Request local backend shutdown; no remote service, trading action, or secret echo.",
        },
        {
            "method": "POST",
            "path": "/api/terminal/reports/full-system-txt",
            "description": "Build a local full-system text report from existing diagnostics only.",
        },
        {
            "method": "GET",
            "path": "/api/terminal/reports/full-system-txt/latest",
            "description": "Read the latest local full-system text report.",
        },
        {
            "method": "GET",
            "path": "/api/terminal/models/active-absence-diagnostics",
            "description": "Read diagnostics explaining why no active model is available; no fake prediction is generated.",
        },
        {
            "method": "POST",
            "path": "/api/terminal/research/run-candidate-v6",
            "description": "Run candidate_v6 gated research; dry-run only, no active publishing or customer prediction.",
        },
    ]
)


TERMINAL_API_DOCS["endpoints"].extend(
    [
        {
            "method": "POST",
            "path": "/api/terminal/diagnostics/build-repair-plan",
            "description": "Build a read-only system repair plan from existing diagnostic artifacts; no training, active publishing, or customer prediction.",
        },
        {
            "method": "GET",
            "path": "/api/terminal/diagnostics/repair-plan",
            "description": "Read the latest generated system repair plan.",
        },
    ]
)

TERMINAL_API_DOCS["endpoints"].append(
    {
        "method": "POST",
        "path": "/api/terminal/research/run-candidate-v7",
        "description": "Run candidate_v7 gated research from Feature Store v7 and Dataset v7; research-only, dry-run promotion, no active publishing, no customer prediction.",
    }
)
TERMINAL_API_DOCS["endpoints"].append(
    {
        "method": "POST",
        "path": "/api/terminal/research/run-candidate-v8",
        "description": "Run candidate_v8 stability research from Feature Store v7 and Dataset v7; horizon-specific no-trade, dry-run promotion, no active publishing, no customer prediction.",
    }
)
TERMINAL_API_DOCS["endpoints"].append(
    {
        "method": "GET",
        "path": "/api/terminal/research/candidate-v8-diagnostics",
        "description": "Read and build candidate_v8 institutional validation diagnostics; no training, active publishing, or customer prediction.",
    }
)
TERMINAL_API_DOCS["endpoints"].append(
    {
        "method": "GET",
        "path": "/api/terminal/research/cpcv-report",
        "description": "Read or build CPCV-like multi-path validation report for research-only PBO and Reality Check; no active publishing or customer prediction.",
    }
)
TERMINAL_API_DOCS["endpoints"].append(
    {
        "method": "POST",
        "path": "/api/terminal/research/run-cpcv-validation",
        "description": "Build CPCV-like multi-path validation report from existing OOF traces; no training, active publishing, or customer prediction.",
    }
)
TERMINAL_API_DOCS["endpoints"].append(
    {
        "method": "POST",
        "path": "/api/terminal/research/run-candidate-v9",
        "description": "Run candidate_v9 regime-neutral research from candidate_v8 attribution; selection/no-trade only, dry-run promotion, no active publishing, no customer prediction.",
    }
)
TERMINAL_API_DOCS["endpoints"].append(
    {
        "method": "POST",
        "path": "/api/terminal/research/run-candidate-v10",
        "description": "Run candidate_v10 from regime-balanced dataset v10 and CPCV-like validation; dry-run promotion only, no active publishing, no customer prediction.",
    }
)
TERMINAL_API_DOCS["endpoints"].extend(
    [
        {
            "method": "GET",
            "path": "/api/terminal/research/year-concentration",
            "description": "Read latest candidate year concentration evidence summary; does not train, promote, or generate customer predictions.",
        },
        {
            "method": "POST",
            "path": "/api/terminal/research/refresh-year-concentration",
            "description": "Refresh year concentration evidence from existing OOF traces and candidate reports only; no training, promotion, or customer prediction.",
        },
        {
            "method": "GET",
            "path": "/api/terminal/research/candidate-v10-report",
            "description": "Read candidate_v10 research report with year concentration evidence; no training, active publishing, or customer prediction.",
        },
    ]
)
TERMINAL_API_DOCS["endpoints"].extend(
    [
        {
            "method": "GET",
            "path": "/api/terminal/research/cost-stress-attribution",
            "description": "Read latest institutional cost stress attribution summary; no training, OOF generation, promotion, active publishing, or customer prediction.",
        },
        {
            "method": "POST",
            "path": "/api/terminal/research/refresh-cost-stress-attribution",
            "description": "Refresh institutional cost stress attribution from existing candidate reports and OOF traces only; no training, promotion, or customer prediction.",
        },
    ]
)
TERMINAL_API_DOCS["endpoints"].extend(
    [
        {
            "method": "GET",
            "path": "/api/terminal/research/v10-cost-remediation",
            "description": "Read candidate_v10 cost failure remediation research sandbox from existing OOF/cost evidence only; no training, approval, active publishing, or customer prediction.",
        },
        {
            "method": "POST",
            "path": "/api/terminal/research/refresh-v10-cost-remediation",
            "description": "Refresh candidate_v10 cost failure remediation hypotheses and no-train counterfactuals from existing OOF only; no training, approval, active publishing, or customer prediction.",
        },
        {
            "method": "GET",
            "path": "/api/terminal/research/v10-remediation-preflight",
            "description": "Read candidate_v10 remediation experiment preflight from existing hypotheses, cost attribution, year evidence, CPCV, and candidate reports only; no training, OOF generation, gate changes, active publishing, or customer prediction.",
        },
        {
            "method": "POST",
            "path": "/api/terminal/research/refresh-v10-remediation-preflight",
            "description": "Refresh candidate_v10 remediation experiment preflight using existing evidence only; does not train, build v12, generate OOF, change candidate gates, publish active, or generate customer prediction.",
        },
        {
            "method": "GET",
            "path": "/api/terminal/research/shadow-mode-readiness",
            "description": "Read the shadow mode readiness spec and output isolation contract; no real predictions, active model updates, or customer prediction generation.",
        },
        {
            "method": "POST",
            "path": "/api/terminal/research/refresh-shadow-mode-readiness",
            "description": "Refresh the shadow mode readiness spec from existing gate evidence only; does not train, publish active, or generate real/customer predictions.",
        },
        {
            "method": "GET",
            "path": "/api/terminal/research/model-registry-safety",
            "description": "Read the model registry safety contract and rollback readiness report; no model registration, active write, or customer prediction generation.",
        },
        {
            "method": "POST",
            "path": "/api/terminal/research/refresh-model-registry-safety",
            "description": "Refresh model registry safety and rollback checks from existing reports only; does not register models, write active, or generate customer predictions.",
        },
    ]
)
TERMINAL_API_DOCS["endpoints"].extend(
    [
        {
            "method": "GET",
            "path": "/api/terminal/research/decision-board",
            "description": "Read the research decision board aggregating data readiness, validation evidence, and allowed next actions; no training, promotion, active publishing, or customer prediction.",
        },
        {
            "method": "GET",
            "path": "/api/terminal/prediction-workspace/status",
            "description": "Read blocked/ready state for the Prediction Workspace; read-only and never trains, publishes active, or creates customer predictions.",
        },
        {
            "method": "GET",
            "path": "/api/terminal/setup-checklist/status",
            "description": "Read the user-facing setup checklist progress state with step statuses and safe actions only; no endpoint calls, v12 build, training, active publishing, or customer prediction.",
        },
        {
            "method": "POST",
            "path": "/api/terminal/setup-checklist/run-safe-action",
            "description": "Run a whitelisted setup checklist safe action such as report refresh, endpoint smoke, sample fixture contract, PIT replay, PIT audit, or data quality; forbidden build/train/promotion/active/prediction/secret actions are rejected.",
        },
        {
            "method": "GET",
            "path": "/api/terminal/setup-checklist/action-history",
            "description": "Read safe setup action run history and redacted run ledger entries; no training, v12 build, candidate, promotion, active, prediction, or secret write.",
        },
        {
            "method": "GET",
            "path": "/api/terminal/setup-checklist/action-telemetry",
            "description": "Read setup checklist UX telemetry summary from safe action runs; no training, v12 build, candidate, promotion, active, prediction, or secret write.",
        },
        {
            "method": "POST",
            "path": "/api/terminal/research/refresh-decision-board",
            "description": "Build the research decision board from existing reports only; no training, OOF generation, promotion, active publishing, or customer prediction.",
        },
    ]
)
TERMINAL_API_DOCS["endpoints"].extend(
    [
        {
            "method": "GET",
            "path": "/api/terminal/research/evidence-bundle",
            "description": "Read the reproducibility evidence bundle index aggregating existing reports and hashes only; no training, OOF generation, feature-store build, promotion, active publishing, or customer prediction.",
        },
        {
            "method": "POST",
            "path": "/api/terminal/research/refresh-evidence-bundle",
            "description": "Refresh the reproducibility evidence bundle index from existing reports only; no training, OOF generation, feature-store build, promotion, active publishing, or customer prediction.",
        },
    ]
)
TERMINAL_API_DOCS["endpoints"].extend(
    [
        {
            "method": "GET",
            "path": "/api/terminal/research/evidence-freshness",
            "description": "Read the evidence freshness and staleness audit for existing reports only; no training, OOF generation, Feature Store build, promotion, active publishing, or customer prediction.",
        },
        {
            "method": "POST",
            "path": "/api/terminal/research/refresh-evidence-freshness",
            "description": "Recompute the evidence freshness and timestamp consistency audit from existing reports only; no training, OOF generation, Feature Store build, promotion, active publishing, or customer prediction.",
        },
    ]
)
TERMINAL_API_DOCS["endpoints"].extend(
    [
        {
            "method": "GET",
            "path": "/api/terminal/research/hypothesis-registry",
            "description": "Read the experiment hypothesis registry and anti-p-hacking ledger; no experiment execution, training, Feature Store build, active publishing, or customer prediction.",
        },
        {
            "method": "POST",
            "path": "/api/terminal/research/create-hypothesis-template",
            "description": "Create a predeclared hypothesis entry from an existing remediation template; does not execute experiments, train models, publish active, or generate predictions.",
        },
        {
            "method": "POST",
            "path": "/api/terminal/research/refresh-anti-p-hacking-ledger",
            "description": "Refresh the anti-p-hacking ledger from existing hypothesis entries and evidence only; no experiment execution, training, active publishing, or prediction.",
        },
    ]
)
TERMINAL_API_DOCS["endpoints"].extend(
    [
        {
            "method": "GET",
            "path": "/api/terminal/research/run-ledger",
            "description": "Read the append-only research run ledger and latest run manifests; no training, Feature Store build, candidate, active publishing, or customer prediction.",
        },
        {
            "method": "POST",
            "path": "/api/terminal/research/refresh-run-ledger",
            "description": "Refresh the run ledger report by recording current safe report files only; no training, Feature Store build, candidate, active publishing, or customer prediction.",
        },
    ]
)
TERMINAL_API_DOCS["endpoints"].extend(
    [
        {
            "method": "GET",
            "path": "/api/terminal/research/readiness-dag",
            "description": "Read the readiness DAG state across managed proxy, PIT, data quality, v12, candidate, decision board, and evidence bundle gates; no training, OOF generation, Feature Store build, promotion, active publishing, or customer prediction.",
        },
        {
            "method": "POST",
            "path": "/api/terminal/research/refresh-readiness-dag",
            "description": "Refresh the readiness DAG report from existing evidence only; no training, OOF generation, Feature Store build, promotion, active publishing, or customer prediction.",
        },
        {
            "method": "POST",
            "path": "/api/terminal/research/run-safe-readiness-checks",
            "description": "Run only safe readiness checks in dependency order; skips downstream checks when upstream gates are blocked and never builds v12, runs candidate, promotion, active, or prediction.",
        },
    ]
)
TERMINAL_API_DOCS["endpoints"].extend(
    [
        {
            "method": "GET",
            "path": "/api/terminal/governance/access-control",
            "description": "Read governance access-control permission matrix and UI/API action inventory; no training, Feature Store build, promotion, active publishing, customer prediction, or secret write.",
        },
        {
            "method": "POST",
            "path": "/api/terminal/governance/refresh-access-control",
            "description": "Refresh the governance access-control report and record a safe_refresh run ledger entry; no training, Feature Store build, promotion, active publishing, customer prediction, or secret write.",
        },
        {
            "method": "GET",
            "path": "/api/terminal/governance/observability",
            "description": "Read governance observability, SLO, error-budget, staleness, secret-scan, and violation telemetry; no training, Feature Store build, promotion, active publishing, customer prediction, or secret write.",
        },
        {
            "method": "POST",
            "path": "/api/terminal/governance/refresh-observability",
            "description": "Refresh the governance observability report and record a safe_refresh run ledger entry; no training, Feature Store build, promotion, active publishing, customer prediction, or secret write.",
        },
        {
            "method": "GET",
            "path": "/api/terminal/governance/incident-drill",
            "description": "Read incident drill and break-glass lockdown report; no training, Feature Store build, promotion, active publishing, customer prediction, or secret write.",
        },
        {
            "method": "POST",
            "path": "/api/terminal/governance/run-incident-drill",
            "description": "Run simulation-only incident drill scenarios and record a safe_dry_run ledger entry; no real active model, customer prediction, training, Feature Store build, promotion, or secret write.",
        },
        {
            "method": "POST",
            "path": "/api/terminal/governance/refresh-lockdown-state",
            "description": "Refresh real lockdown state from existing governance evidence only; no simulation artifact is treated as real incident and no training, active publishing, customer prediction, or secret write occurs.",
        },
        {
            "method": "GET",
            "path": "/api/terminal/governance/manual-approval",
            "description": "Read manual approval workflow status and two-person review state; no training, Feature Store build, promotion, active publishing, customer prediction, or secret write.",
        },
        {
            "method": "POST",
            "path": "/api/terminal/governance/refresh-manual-approval",
            "description": "Refresh manual approval precondition status from existing governance evidence only; no training, active publishing, customer prediction, promotion, or secret write.",
        },
        {
            "method": "POST",
            "path": "/api/terminal/governance/create-manual-approval-request",
            "description": "Create a report-only manual approval request for shadow, dry-run promotion, or registry review; active publishing and customer prediction are unsupported.",
        },
        {
            "method": "POST",
            "path": "/api/terminal/governance/record-manual-approval-decision",
            "description": "Record a two-person manual approval decision for non-active governance actions only; does not write active model, run promotion, or generate customer prediction.",
        },
        {
            "method": "GET",
            "path": "/api/terminal/governance/shadow-output-contract",
            "description": "Read the shadow output dry-run format and prediction isolation contract; no real prediction, active model, customer output, training, or secret write.",
        },
        {
            "method": "POST",
            "path": "/api/terminal/governance/refresh-shadow-output-contract",
            "description": "Refresh the shadow output contract report from existing governance evidence only; no real prediction, active model, customer output, or training.",
        },
        {
            "method": "POST",
            "path": "/api/terminal/governance/build-shadow-output-dry-run",
            "description": "Build a synthetic contract-only shadow output dry-run artifact under outputs/shadow_mode; never writes customer_predictions or active_model.",
        },
        {
            "method": "GET",
            "path": "/api/terminal/governance/shadow-replay",
            "description": "Read research-only shadow replay evaluator output from existing OOF traces; no training, OOF generation, promotion, active model, or customer prediction.",
        },
        {
            "method": "POST",
            "path": "/api/terminal/governance/refresh-shadow-replay",
            "description": "Refresh research-only shadow replay from existing OOF traces and record safe dry-run evidence; never writes active_model or customer_predictions.",
        },
        {
            "method": "GET",
            "path": "/api/terminal/governance/post-release-monitoring-spec",
            "description": "Read post-release monitoring planning spec and drift sentinel contract; no daemon deployment, training, Feature Store build, promotion, active model, or customer prediction.",
        },
        {
            "method": "POST",
            "path": "/api/terminal/governance/refresh-post-release-monitoring-spec",
            "description": "Refresh the post-release monitoring planning spec as report_write only; no monitoring daemon, live prediction, active model, training, candidate, or promotion.",
        },
        {
            "method": "GET",
            "path": "/api/terminal/governance/rollback-rehearsal",
            "description": "Read rollback rehearsal and artifact quarantine simulation report; no file deletion, file movement, active model write, customer prediction, training, or promotion.",
        },
        {
            "method": "POST",
            "path": "/api/terminal/governance/refresh-rollback-rehearsal",
            "description": "Refresh rollback rehearsal evidence as report_write only; it detects unapproved artifacts but never deletes, moves, writes active_model, trains, promotes, or generates customer predictions.",
        },
        {
            "method": "POST",
            "path": "/api/terminal/governance/simulate-artifact-quarantine",
            "description": "Build a simulation-only quarantine manifest for unapproved artifacts; real delete and move operations are forbidden.",
        },
        {
            "method": "GET",
            "path": "/api/terminal/governance/external-audit-export",
            "description": "Read the redacted external audit export index with evidence paths and hashes only; no raw managed rows, OOF trace content, training, active model, or customer prediction.",
        },
        {
            "method": "POST",
            "path": "/api/terminal/governance/refresh-external-audit-export",
            "description": "Refresh the redacted external audit export package and record a report_write ledger entry; no training, Feature Store build, candidate, promotion, active publishing, or customer prediction.",
        },
        {
            "method": "GET",
            "path": "/api/terminal/governance/production-cutover-checklist",
            "description": "Read the production cutover checklist and no-op release readiness from existing governance reports only; no training, promotion, active publishing, or customer prediction.",
        },
        {
            "method": "POST",
            "path": "/api/terminal/governance/refresh-production-cutover-checklist",
            "description": "Refresh the production cutover checklist report; this is report_write only and never trains, promotes, writes active, or generates customer prediction.",
        },
        {
            "method": "POST",
            "path": "/api/terminal/governance/build-noop-release-plan",
            "description": "Build a no-op release plan artifact for manual review only; it never calls promotion, writes active_model, trains, or writes customer_predictions.",
        },
        {
            "method": "GET",
            "path": "/api/terminal/governance/promotion-dry-run-evidence",
            "description": "Read promotion dry-run evidence v2 and artifact boundary checks; no training, OOF generation, real promotion, active model write, or customer prediction.",
        },
        {
            "method": "POST",
            "path": "/api/terminal/governance/refresh-promotion-dry-run-evidence",
            "description": "Refresh promotion dry-run evidence as a safe_dry_run ledger entry; simulates registry write planning only and never writes active_model or customer_predictions.",
        },
        {
            "method": "GET",
            "path": "/api/terminal/governance/model-card",
            "description": "Read the research-only model card and risk disclosure summary; no training, Feature Store build, promotion, active model write, customer prediction, raw data export, or OOF export.",
        },
        {
            "method": "POST",
            "path": "/api/terminal/governance/refresh-model-card",
            "description": "Refresh model_card.json, model_card.md, and risk_disclosure.md from existing governance evidence only; no training, Feature Store build, promotion, active model write, customer prediction, raw data export, or OOF export.",
        },
        {
            "method": "GET",
            "path": "/api/terminal/governance/maturity-matrix",
            "description": "Read governance maturity gap matrix, final hardening roadmap, and prompt sequence; no training, v12 build, candidate, promotion, active model write, customer prediction, raw data export, or OOF export.",
        },
        {
            "method": "POST",
            "path": "/api/terminal/governance/refresh-maturity-matrix",
            "description": "Refresh governance maturity gap matrix as report_write only; no training, Feature Store or Training Dataset v12 build, candidate, promotion, active model write, customer prediction, raw data export, or OOF export.",
        },
    ]
)
TERMINAL_API_DOCS["endpoints"].extend(
    [
        {
            "method": "GET",
            "path": "/api/terminal/research/candidate-v12-report",
            "description": "Read candidate_v12 blocked-first research gate report; no active publishing or customer prediction.",
        },
        {
            "method": "POST",
            "path": "/api/terminal/research/run-candidate-v12",
            "description": "Run candidate_v12 research gate only when Training Dataset v12 and Feature Store v12 are ready; dry-run promotion only.",
        },
    ]
)
TERMINAL_API_DOCS["endpoints"].append(
    {
        "method": "POST",
        "path": "/api/terminal/refresh/managed-proxy-v11",
        "description": "Refresh managed proxy fundamentals and build Feature Store v11 readiness; no fake data, no model training, no active publishing.",
    }
)
TERMINAL_API_DOCS["endpoints"].extend(
    [
        {
            "method": "GET",
            "path": "/api/terminal/local-api-provider/hub",
            "description": "Return Local API Provider Hub status, credential handoff summary, legacy proxy compatibility, and safe next action; no raw keys, v12 build, training, active, or prediction.",
        },
        {
            "method": "POST",
            "path": "/api/terminal/local-api-provider/refresh-hub",
            "description": "Refresh Local API Provider Hub report from masked local credential state only; no endpoint call unless provider smoke is explicitly requested, no v12 build, training, active, or prediction.",
        },
        {
            "method": "GET",
            "path": "/api/terminal/local-api-provider/credentials",
            "description": "Return masked Local API Provider credential handoff; no raw key input, no key write, no endpoint call, no v12 build, training, active, or prediction.",
        },
        {
            "method": "POST",
            "path": "/api/terminal/local-api-provider/refresh-credentials",
            "description": "Refresh masked provider credential handoff from local environment only; request body is ignored and no secret write occurs.",
        },
        {
            "method": "GET",
            "path": "/api/terminal/local-api-provider/smoke",
            "description": "Return latest Local API Provider smoke report; smoke reports never write Feature Store, production cache, active model, or customer prediction.",
        },
        {
            "method": "POST",
            "path": "/api/terminal/local-api-provider/run-smoke",
            "description": "Run a minimal provider smoke check for a configured local API provider; no Feature Store build, training, candidate, active, or prediction.",
        },
        {
            "method": "GET",
            "path": "/api/terminal/managed-proxy/health",
            "description": "Return managed proxy configuration, masked token, required field coverage and blocking reasons; no secrets, no model training.",
        },
        {
            "method": "GET",
            "path": "/api/terminal/managed-proxy/setup",
            "description": "Return managed proxy secure setup status, endpoint contract, masked token metadata, and next setup action; no raw secrets, no training.",
        },
        {
            "method": "POST",
            "path": "/api/terminal/managed-proxy/refresh-setup",
            "description": "Refresh managed proxy setup report from local configuration only; no Feature Store, training, candidate, promotion, active, or prediction trigger.",
        },
        {
            "method": "GET",
            "path": "/api/terminal/managed-proxy/endpoint-contract",
            "description": "Return managed proxy endpoint contract requirements without exposing token, endpoint secret, or Authorization header.",
        },
        {
            "method": "POST",
            "path": "/api/terminal/managed-proxy/run-contract-dry-run",
            "description": "Run managed proxy endpoint/schema/PIT dry-run validation; no fake data, no Feature Store build, no training, no active publishing.",
        },
        {
            "method": "GET",
            "path": "/api/terminal/managed-proxy/config-wizard",
            "description": "Return safe managed proxy local configuration guidance and template status; no raw token input, no health/audit/v12/training trigger.",
        },
        {
            "method": "GET",
            "path": "/api/terminal/managed-proxy/config-handoff",
            "description": "Return secure managed proxy configuration handoff and local config detector; no raw token input, endpoint call, v12 build, training, active, or prediction.",
        },
        {
            "method": "POST",
            "path": "/api/terminal/managed-proxy/refresh-config-wizard",
            "description": "Refresh safe managed proxy configuration wizard report; request body is ignored, no secret write, no downstream task trigger.",
        },
        {
            "method": "POST",
            "path": "/api/terminal/managed-proxy/refresh-config-handoff",
            "description": "Refresh secure managed proxy configuration handoff from local masked config state only; request body is ignored and no secret write or downstream task trigger occurs.",
        },
        {
            "method": "GET",
            "path": "/api/terminal/managed-proxy/operator-runbook",
            "description": "Return managed proxy operator onboarding runbook, safe config verification, masked token state, and next action; no raw token input, endpoint call, v12 build, training, active, or prediction.",
        },
        {
            "method": "POST",
            "path": "/api/terminal/managed-proxy/refresh-operator-runbook",
            "description": "Refresh managed proxy operator onboarding runbook from local templates and masked config state only; request body is ignored, no secret write or downstream task trigger.",
        },
        {
            "method": "GET",
            "path": "/api/terminal/managed-proxy/schema-mapping",
            "description": "Return managed proxy provider-to-canonical field mapping contract; no raw secrets, no Feature Store build, no training.",
        },
        {
            "method": "POST",
            "path": "/api/terminal/managed-proxy/refresh-schema-mapping",
            "description": "Refresh managed proxy schema mapping report; request body is ignored, no data mutation, no v12 build, no training.",
        },
        {
            "method": "POST",
            "path": "/api/terminal/managed-proxy/check",
            "description": "Run a low-cost managed proxy live health check for required fundamentals; no fake data, no active publishing.",
        },
        {
            "method": "GET",
            "path": "/api/terminal/managed-proxy/readiness",
            "description": "Return whether managed proxy is allowed to enter Feature Store v12 build.",
        },
        {
            "method": "GET",
            "path": "/api/terminal/managed-proxy/reliability",
            "description": "Return managed proxy canary reliability guardrail, circuit breaker, schema drift and cache staleness status; no refresh, v12 build or training.",
        },
        {
            "method": "POST",
            "path": "/api/terminal/managed-proxy/run-canary",
            "description": "Run low-cost managed proxy canary health check only; no bulk data refresh, Feature Store build, candidate, active, or prediction.",
        },
        {
            "method": "GET",
            "path": "/api/terminal/managed-proxy/data-quality",
            "description": "Return managed data quality scorecard and anomaly gates; no Feature Store build, training, active, or prediction.",
        },
        {
            "method": "POST",
            "path": "/api/terminal/managed-proxy/refresh-data-quality",
            "description": "Refresh managed data quality scorecard from existing managed rows only; no data refresh, v12 build, candidate, active, or prediction.",
        },
        {
            "method": "GET",
            "path": "/api/terminal/managed-proxy/audit",
            "description": "Return latest managed proxy point-in-time data audit manifest; no secrets, no model training.",
        },
        {
            "method": "POST",
            "path": "/api/terminal/managed-proxy/run-audit",
            "description": "Build managed proxy point-in-time data audit manifest; no fake data, no active publishing.",
        },
        {
            "method": "GET",
            "path": "/api/terminal/managed-proxy/audit-readiness",
            "description": "Return whether managed proxy point-in-time audit allows Feature Store v12 build.",
        },
        {
            "method": "GET",
            "path": "/api/terminal/managed-proxy/pit-replay",
            "description": "Return latest PIT replay harness report for managed rows; no Feature Store build, training, active, or prediction.",
        },
        {
            "method": "POST",
            "path": "/api/terminal/managed-proxy/run-pit-replay",
            "description": "Run PIT replay harness from existing managed rows only; no v12 build, candidate, promotion, active, or prediction.",
        },
        {
            "method": "GET",
            "path": "/api/terminal/managed-proxy/sample-fixture",
            "description": "Return managed proxy sample fixture contract harness status; fixture-only evidence cannot unlock Feature Store v12.",
        },
        {
            "method": "POST",
            "path": "/api/terminal/managed-proxy/import-sample-fixture",
            "description": "Import bundled non-sensitive managed proxy sample fixture for contract tests only; body is ignored, no real managed cache, v12 build, training, active, or prediction.",
        },
        {
            "method": "POST",
            "path": "/api/terminal/managed-proxy/run-sample-fixture-contract-tests",
            "description": "Run schema, PIT replay, audit, and data quality contract tests against the sample fixture only; never production-eligible and never unlocks v12.",
        },
        {
            "method": "GET",
            "path": "/api/terminal/managed-proxy/endpoint-smoke",
            "description": "Return latest managed proxy real endpoint smoke report; no raw rows, no Feature Store build, no training, active, or prediction.",
        },
        {
            "method": "POST",
            "path": "/api/terminal/managed-proxy/run-endpoint-smoke",
            "description": "Run a minimal real endpoint smoke request for auth, schema, PIT timestamp, and token echo only; body is ignored and raw rows are never persisted.",
        },
        {
            "method": "GET",
            "path": "/api/terminal/managed-proxy/quarantine-snapshot",
            "description": "Return latest managed proxy quarantined snapshot report; quarantine-only evidence cannot unlock Feature Store v12.",
        },
        {
            "method": "POST",
            "path": "/api/terminal/managed-proxy/pull-quarantine-snapshot",
            "description": "Pull a tiny managed proxy snapshot only after endpoint smoke pass; no custom output path, raw secret input, managed cache write, v12 build, training, active, or prediction.",
        },
        {
            "method": "GET",
            "path": "/api/terminal/managed-proxy/quarantine-contract",
            "description": "Return latest quarantine contract and research cache gate report; research cache is never production managed data and never unlocks v12.",
        },
        {
            "method": "POST",
            "path": "/api/terminal/managed-proxy/run-quarantine-contract",
            "description": "Run schema, PIT replay, PIT audit, and data quality contracts against the quarantined snapshot only; no v12 build, training, active, or prediction.",
        },
        {
            "method": "POST",
            "path": "/api/terminal/managed-proxy/promote-quarantine-to-research-cache",
            "description": "Promote passing quarantined snapshot rows into research cache only; no production cache, Feature Store v12 build, training, active, or prediction.",
        },
        {
            "method": "GET",
            "path": "/api/terminal/managed-proxy/backfill-plan",
            "description": "Return the real managed data backfill planner report with coverage budget and abort conditions; no data fetch, production cache write, v12 build, training, active, or prediction.",
        },
        {
            "method": "POST",
            "path": "/api/terminal/managed-proxy/refresh-backfill-plan",
            "description": "Refresh the real managed data backfill plan only; request body cannot execute historical backfill, write cache, build v12, train, active, or prediction.",
        },
        {
            "method": "GET",
            "path": "/api/terminal/managed-proxy/production-cache-gate",
            "description": "Return the production managed cache promotion gate report; dry-run only, no production cache write, v12 build, training, active, or prediction.",
        },
        {
            "method": "POST",
            "path": "/api/terminal/managed-proxy/refresh-production-cache-gate",
            "description": "Refresh production managed cache promotion gate evidence only; cannot write production cache, build v12, train, active, or prediction.",
        },
        {
            "method": "POST",
            "path": "/api/terminal/managed-proxy/build-production-cache-dry-run",
            "description": "Build a production managed cache promotion dry-run plan only; no production cache write, v12 build, training, active, or prediction.",
        },
        {
            "method": "GET",
            "path": "/api/terminal/feature-store/v12-input-contract",
            "description": "Return the production managed cache readiness diff against Feature Store v12 input requirements; no v12 build, training, active, or prediction.",
        },
        {
            "method": "POST",
            "path": "/api/terminal/feature-store/refresh-v12-input-contract",
            "description": "Refresh the v12 input contract report only; request body cannot pass secrets, custom paths, v12 build, training, active, or prediction.",
        },
        {
            "method": "GET",
            "path": "/api/terminal/feature-store/v12-build-plan",
            "description": "Return Feature Store v12 build dry-run plan with inputs, outputs, rollback and forbidden side effects; no v12 build, TD build, training, active, or prediction.",
        },
        {
            "method": "POST",
            "path": "/api/terminal/feature-store/refresh-v12-build-plan",
            "description": "Refresh Feature Store v12 build dry-run plan only; request body cannot pass secrets, custom paths, v12 build, TD build, training, active, or prediction.",
        },
        {
            "method": "GET",
            "path": "/api/terminal/feature-store/v12-controlled-build",
            "description": "Return Feature Store v12 controlled build execution report; does not run TD v12, candidate, promotion, active, or prediction.",
        },
        {
            "method": "POST",
            "path": "/api/terminal/feature-store/run-v12-controlled-build",
            "description": "Run the controlled Feature Store v12 executor only when all upstream gates pass; forbids custom paths, force, upstream auto-build, training, active, or prediction.",
        },
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


def _forbidden_quarantine_snapshot_request(payload: Mapping[str, Any]) -> dict[str, Any] | None:
    forbidden_secret_keys = {"token", "authorization", "header", "headers", "api_key", "apikey", "secret", "base_url", "endpoint", "url"}
    forbidden_path_keys = {"output_path", "quarantine_path", "custom_output_path", "path"}
    keys = {str(key).lower() for key in payload.keys()}
    if keys & forbidden_secret_keys:
        return {"error": "raw_secret_input_forbidden", "message": "managed proxy quarantine snapshot API does not accept raw token, endpoint, or Authorization header input."}
    if keys & forbidden_path_keys:
        return {"error": "custom_output_path_forbidden", "message": "managed proxy quarantine snapshot output path is fixed to the quarantine directory."}
    return None


def _forbidden_quarantine_contract_request(payload: Mapping[str, Any]) -> dict[str, Any] | None:
    forbidden_secret_keys = {"token", "authorization", "header", "headers", "api_key", "apikey", "secret", "base_url", "endpoint", "url"}
    forbidden_path_keys = {"output_path", "quarantine_path", "research_cache_path", "custom_output_path", "path"}
    forbidden_production_keys = {"production_cache", "production_cache_path", "feature_store_v12", "build_v12", "build_feature_store_v12", "training", "candidate", "promotion", "active", "prediction"}
    keys = {str(key).lower() for key in payload.keys()}
    if keys & forbidden_secret_keys:
        return {"error": "raw_secret_input_forbidden", "message": "managed proxy quarantine contract API does not accept raw token, endpoint, or Authorization header input."}
    if keys & forbidden_path_keys:
        return {"error": "custom_output_path_forbidden", "message": "managed proxy quarantine contract output paths are fixed to quarantine diagnostics and research cache directories."}
    if keys & forbidden_production_keys:
        return {"error": "production_cache_promotion_forbidden", "message": "quarantine contract API cannot promote production cache, build v12, train, active, or prediction outputs."}
    return None


def _forbidden_backfill_planner_request(payload: Mapping[str, Any]) -> dict[str, Any] | None:
    forbidden_secret_keys = {"token", "authorization", "header", "headers", "api_key", "apikey", "secret", "base_url", "endpoint", "url"}
    forbidden_path_keys = {"output_path", "cache_path", "managed_cache_path", "production_cache_path", "custom_output_path", "path"}
    forbidden_execution_keys = {
        "execute",
        "fetch",
        "backfill",
        "historical_backfill",
        "production_cache",
        "feature_store_v12",
        "build_v12",
        "build_feature_store_v12",
        "training",
        "candidate",
        "promotion",
        "active",
        "prediction",
    }
    keys = {str(key).lower() for key in payload.keys()}
    if keys & forbidden_secret_keys:
        return {"error": "raw_secret_input_forbidden", "message": "managed data backfill planner API does not accept raw token, endpoint, or Authorization header input."}
    if keys & forbidden_path_keys:
        return {"error": "custom_output_path_forbidden", "message": "managed data backfill planner output path is fixed to diagnostics only."}
    if keys & forbidden_execution_keys:
        return {"error": "backfill_execution_forbidden", "message": "managed data backfill planner only writes a plan; it cannot fetch rows, write production cache, build v12, train, active, or prediction outputs."}
    return None


def _forbidden_production_cache_gate_request(payload: Mapping[str, Any]) -> dict[str, Any] | None:
    forbidden_secret_keys = {"token", "authorization", "header", "headers", "api_key", "apikey", "secret", "base_url", "endpoint", "url"}
    forbidden_path_keys = {"output_path", "cache_path", "managed_cache_path", "production_cache_path", "custom_output_path", "path"}
    forbidden_execution_keys = {
        "write",
        "execute",
        "fetch",
        "backfill",
        "historical_backfill",
        "production_cache",
        "production_cache_write",
        "feature_store_v12",
        "build_v12",
        "build_feature_store_v12",
        "train",
        "training",
        "candidate",
        "promotion",
        "active",
        "prediction",
    }
    keys = {str(key).lower() for key in payload.keys()}
    if keys & forbidden_secret_keys:
        return {"error": "raw_secret_input_forbidden", "message": "production cache gate API does not accept raw token, endpoint, or Authorization header input."}
    if keys & forbidden_path_keys:
        return {"error": "custom_output_path_forbidden", "message": "production cache gate output paths are fixed; custom production cache paths are forbidden."}
    if keys & forbidden_execution_keys:
        return {"error": "production_cache_write_forbidden", "message": "production cache gate is dry-run/report-only; it cannot write cache, build v12, train, active, or prediction outputs."}
    return None


def _forbidden_v12_input_contract_request(payload: Mapping[str, Any]) -> dict[str, Any] | None:
    forbidden_secret_keys = {"token", "authorization", "header", "headers", "api_key", "apikey", "secret", "base_url", "endpoint", "url"}
    forbidden_path_keys = {"output_path", "feature_store_path", "cache_path", "custom_output_path", "path"}
    forbidden_execution_keys = {
        "write",
        "execute",
        "build",
        "feature_store_v12",
        "build_v12",
        "build_feature_store_v12",
        "train",
        "training",
        "candidate",
        "promotion",
        "active",
        "prediction",
    }
    keys = {str(key).lower() for key in payload.keys()}
    if keys & forbidden_secret_keys:
        return {"error": "raw_secret_input_forbidden", "message": "v12 input contract API does not accept raw token, endpoint, or Authorization header input."}
    if keys & forbidden_path_keys:
        return {"error": "custom_output_path_forbidden", "message": "v12 input contract report path is fixed to diagnostics; custom output paths are forbidden."}
    if keys & forbidden_execution_keys:
        return {"error": "v12_build_forbidden", "message": "v12 input contract is report-only; it cannot build Feature Store v12, train, active, or prediction outputs."}
    return None


def _forbidden_v12_build_plan_request(payload: Mapping[str, Any]) -> dict[str, Any] | None:
    forbidden_secret_keys = {"token", "authorization", "header", "headers", "api_key", "apikey", "secret", "base_url", "endpoint", "url"}
    forbidden_path_keys = {"output_path", "feature_store_path", "manifest_path", "training_dataset_path", "custom_output_path", "path"}
    forbidden_execution_keys = {
        "write",
        "execute",
        "build",
        "feature_store_v12",
        "build_v12",
        "build_feature_store_v12",
        "build_training_dataset_v12",
        "train",
        "training",
        "candidate",
        "promotion",
        "active",
        "prediction",
    }
    keys = {str(key).lower() for key in payload.keys()}
    if keys & forbidden_secret_keys:
        return {"error": "raw_secret_input_forbidden", "message": "v12 build plan API does not accept raw token, endpoint, or Authorization header input."}
    if keys & forbidden_path_keys:
        return {"error": "custom_output_path_forbidden", "message": "v12 build plan output path is fixed to diagnostics; custom build output paths are forbidden."}
    if keys & forbidden_execution_keys:
        return {"error": "v12_build_forbidden", "message": "v12 build plan is dry-run/report-only; it cannot build Feature Store v12, build TD v12, train, active, or prediction outputs."}
    return None


def _forbidden_v12_controlled_build_request(payload: Mapping[str, Any]) -> dict[str, Any] | None:
    forbidden_secret_keys = {"token", "authorization", "header", "headers", "api_key", "apikey", "secret", "base_url", "endpoint", "url"}
    forbidden_path_keys = {"output_path", "feature_store_path", "manifest_path", "training_dataset_path", "custom_output_path", "path"}
    forbidden_force_keys = {"force", "force_build", "override", "skip_preconditions", "bypass_gate"}
    forbidden_upstream_keys = {"build_missing", "refresh_missing", "build_upstream", "run_upstream", "auto_build", "production_cache", "production_cache_write"}
    forbidden_downstream_keys = {
        "build_training_dataset_v12",
        "training_dataset",
        "training_dataset_v12",
        "train",
        "training",
        "candidate",
        "candidate_v12",
        "promotion",
        "active",
        "prediction",
        "customer_prediction",
    }
    keys = {str(key).lower() for key in payload.keys()}
    if keys & forbidden_secret_keys:
        return {"error": "raw_secret_input_forbidden", "message": "v12 controlled build API does not accept raw token, endpoint, or Authorization header input."}
    if keys & forbidden_path_keys:
        return {"error": "custom_output_path_forbidden", "message": "v12 controlled build output paths are fixed; custom output paths are forbidden."}
    if keys & forbidden_force_keys:
        return {"error": "force_controlled_build_forbidden", "message": "v12 controlled build cannot be forced or run with skipped preconditions."}
    if keys & forbidden_upstream_keys:
        return {"error": "upstream_auto_build_forbidden", "message": "v12 controlled build cannot auto-build missing upstream production cache, input contract, or dry-run plan evidence."}
    if keys & forbidden_downstream_keys:
        return {"error": "downstream_action_forbidden", "message": "v12 controlled build cannot trigger TD v12, candidate, promotion, active, or prediction outputs."}
    return None


def _ok(payload: Any) -> tuple[int, dict[str, Any]]:
    # Force JSON serialisability here so tests can catch contract regressions
    # without needing to boot the HTTP server.
    safe_json_dumps(payload)
    return 200, sanitize_for_json(payload)


def _public_ok(payload: Any) -> tuple[int, dict[str, Any]]:
    return _ok(assert_public_payload_real_or_blocked(payload if isinstance(payload, Mapping) else {}))


def _task_response(kind: str, fn: Any, payload: dict[str, Any] | None = None) -> tuple[int, dict[str, Any]]:
    return _ok(start_task(kind, fn, payload=payload or {}))


def _unknown_task_kind(kind: str) -> tuple[int, dict[str, Any]] | None:
    if kind in KNOWN_TASK_KINDS:
        return None
    return 400, {
        "error": "invalid_task_kind",
        "message": f"未知任务类型：{kind}",
        "allowed_kinds": sorted(KNOWN_TASK_KINDS),
    }


_TERMINAL_ROUTER = None


def _terminal_router():
    global _TERMINAL_ROUTER
    if _TERMINAL_ROUTER is None:
        _TERMINAL_ROUTER = build_terminal_router(TERMINAL_API_DOCS)
    return _TERMINAL_ROUTER


def _handle_public_terminal_api(
    path: str,
    method: str,
    query: Mapping[str, list[str]] | None = None,
    body: Any = None,
) -> tuple[int, dict[str, Any]]:
    if method == "GET" and path == "/api/public-terminal/openapi.json":
        return _ok(build_public_terminal_openapi())

    if method == "GET" and path == "/api/public-terminal/readiness":
        return _public_ok(build_public_terminal_readiness())

    if method == "GET" and path == "/api/public-terminal/prediction-status":
        return _public_ok(build_public_prediction_status_payload())

    if method == "GET" and path == "/api/public-terminal/market":
        return _public_ok(build_public_market())

    if method == "GET" and path == "/api/public-terminal/events":
        return _public_ok(build_public_event_center())

    if method == "GET" and path == "/api/public-terminal/report":
        return _public_ok(build_public_report())

    if method == "POST" and path in {"/api/public-terminal/provider-smoke", "/api/public-terminal/provider-smoke-real"}:
        payload, error = _parse_body(body)
        if error is not None:
            return 400, error
        provider = str((payload or {}).get("provider") or "").strip().lower()
        allow_remote = bool((payload or {}).get("allow_remote")) if path.endswith("provider-smoke-real") else False
        smoke = run_provider_only_smoke(
            providers=[provider] if provider else None,
            allow_remote=allow_remote,
            persist=False,
        )
        return _public_ok(bridge_provider_smoke_result(smoke, source="provider_only_harness"))

    if method == "POST" and path == "/api/public-terminal/refresh-data-status":
        return _public_ok(start_public_refresh_data_status_task())

    task_prefix = "/api/public-terminal/tasks/"
    if path.startswith(task_prefix):
        task_id = path[len(task_prefix) :].strip("/")
        if not task_id:
            return 400, {"error": "missing_task_id", "reason": "missing_task_id"}
        if task_id.endswith("/cancel"):
            task_id = task_id[: -len("/cancel")].strip("/")
            if method == "POST":
                return _public_ok(cancel_public_refresh_task(task_id))
        elif method == "GET" and "/" not in task_id:
            return _public_ok(get_public_refresh_task(task_id))

    return 404, {"error": "not_found", "message": "Public Terminal API path not found."}


def handle_terminal_api(
    path: str,
    method: str = "GET",
    query: Mapping[str, list[str]] | None = None,
    body: Any = None,
) -> tuple[int, dict[str, Any]]:
    method = method.upper()
    if path.startswith("/api/public-terminal/"):
        return _handle_public_terminal_api(path, method, query, body)
    if not path.startswith("/api/terminal/"):
        return 404, {"error": "not_found", "message": "不是 terminal API 路径。"}

    router = _terminal_router()
    if router.path_registered(path):
        return router.dispatch(method, path, query, body)

    if method == "GET":
        if path == "/api/terminal/docs":
            return _ok(TERMINAL_API_DOCS)
        if path == "/api/terminal/summary":
            return _ok(cached_call("terminal:summary", 5, build_terminal_summary))
        if path == "/api/terminal/snapshot-lite":
            return _ok(cached_call("terminal:snapshot-lite", 5, build_terminal_snapshot_lite))
        if path == "/api/terminal/snapshot":
            return _ok(cached_call("terminal:snapshot", 5, build_terminal_snapshot))
        if path == "/api/terminal/predictions":
            return _ok(build_terminal_predictions_payload())
        if path == "/api/terminal/prediction-workspace/status":
            return _ok(build_prediction_workspace_status())
        if path == "/api/terminal/setup-checklist/status":
            return _ok(build_setup_checklist_status())
        if path == "/api/terminal/setup-checklist/action-history":
            limit = int(_query_value(query, "limit", "20") or "20")
            return _ok(get_setup_action_history(limit=limit))
        if path == "/api/terminal/setup-checklist/action-telemetry":
            return _ok(summarize_setup_action_telemetry())
        if path == "/api/terminal/model-health":
            return _ok(cached_call("terminal:model-health", 5, build_terminal_model_health))
        if path == "/api/terminal/learning-status":
            return _ok(build_terminal_learning_status())
        if path == "/api/terminal/backtest-diagnostics":
            return _ok(build_terminal_backtest_diagnostics(_query_value(query, "horizon", "")))
        if path == "/api/terminal/reports":
            return _ok(build_terminal_reports())
        if path == "/api/terminal/data-status":
            return _ok(cached_call("terminal:data-status", 10, build_terminal_data_status))
        if path == "/api/terminal/local-api-provider/hub":
            return _ok(get_local_api_provider_hub())
        if path == "/api/terminal/local-api-provider/credentials":
            return _ok(get_provider_credentials_report())
        if path == "/api/terminal/local-api-provider/smoke":
            return _ok(get_latest_provider_smoke_report())
        if path == "/api/terminal/managed-proxy/setup":
            return _ok(get_managed_proxy_setup_status())
        if path == "/api/terminal/managed-proxy/config-wizard":
            return _ok(get_managed_proxy_config_wizard())
        if path == "/api/terminal/managed-proxy/config-handoff":
            return _ok(get_config_handoff_report())
        if path == "/api/terminal/managed-proxy/operator-runbook":
            return _ok(get_operator_onboarding_runbook())
        if path == "/api/terminal/managed-proxy/schema-mapping":
            return _ok(get_schema_mapping_report())
        if path == "/api/terminal/managed-proxy/endpoint-contract":
            return _ok(validate_managed_proxy_endpoint_contract(validate_managed_proxy_config_source()))
        if path == "/api/terminal/managed-proxy/health":
            return _ok(get_managed_proxy_health())
        if path == "/api/terminal/managed-proxy/readiness":
            return _ok(get_managed_proxy_readiness())
        if path == "/api/terminal/managed-proxy/reliability":
            return _ok(get_managed_proxy_reliability_report())
        if path == "/api/terminal/managed-proxy/data-quality":
            return _ok(get_latest_managed_data_quality_scorecard())
        if path == "/api/terminal/managed-proxy/audit":
            return _ok(get_latest_managed_audit_manifest())
        if path == "/api/terminal/managed-proxy/audit-readiness":
            return _ok(compute_managed_audit_readiness())
        if path == "/api/terminal/managed-proxy/pit-replay":
            return _ok(get_latest_pit_replay_report())
        if path == "/api/terminal/managed-proxy/sample-fixture":
            return _ok(get_latest_sample_fixture_report())
        if path == "/api/terminal/managed-proxy/endpoint-smoke":
            return _ok(get_latest_endpoint_smoke_report())
        if path == "/api/terminal/managed-proxy/quarantine-snapshot":
            return _ok(get_latest_quarantine_snapshot_report())
        if path == "/api/terminal/managed-proxy/quarantine-contract":
            return _ok(get_latest_quarantine_contract_report())
        if path == "/api/terminal/managed-proxy/backfill-plan":
            return _ok(get_latest_backfill_planner_report())
        if path == "/api/terminal/managed-proxy/production-cache-gate":
            return _ok(get_latest_production_cache_gate_report())
        if path == "/api/terminal/feature-store/v12-input-contract":
            return _ok(get_latest_v12_input_contract_report())
        if path == "/api/terminal/feature-store/v12-build-plan":
            return _ok(get_latest_v12_build_plan_report())
        if path == "/api/terminal/feature-store/v12-controlled-build":
            return _ok(get_latest_v12_controlled_build_report())
        if path == "/api/terminal/data-watermark":
            return _ok(get_data_watermark_report())
        if path == "/api/terminal/data-consistency-report":
            return _ok(build_data_consistency_report())
        if path == "/api/terminal/online-data-sources/status":
            return _ok(build_online_data_source_registry())
        if path == "/api/terminal/learning-scheduler/status":
            return _ok(get_learning_scheduler_status())
        if path == "/api/terminal/system-health":
            return _ok(cached_call("terminal:system-health", 5, build_terminal_system_health))
        if path == "/api/terminal/system/process-status":
            return _ok(get_process_status())
        if path == "/api/terminal/performance/diagnostics":
            return _ok(run_api_performance_diagnostics())
        if path == "/api/terminal/diagnostics/stability-audit":
            return _ok(build_system_stability_audit())
        if path == "/api/terminal/diagnostics/all-api-smoke":
            return _ok(run_all_terminal_api_smoke())
        if path == "/api/terminal/diagnostics/repair-plan":
            return _ok(get_latest_system_repair_plan())
        if path == "/api/terminal/runtime-diagnostics":
            return _ok(build_runtime_data_diagnostics())
        if path == "/api/terminal/charts/price-history":
            chart_payload = build_price_chart_payload()
            if chart_payload.get("points"):
                return _ok(chart_payload)
            legacy_payload = build_terminal_price_history()
            if legacy_payload.get("points"):
                legacy_payload.update(
                    {
                        "schema_version": chart_payload.get("schema_version", 1),
                        "chart_type": "price",
                        "x_field": "time",
                        "y_fields": ["open", "high", "low", "close"],
                        "units": {"price": "CNY/ton"},
                        "source_files": chart_payload.get("source_files", ["sn_market_history.json"]),
                    }
                )
                return _ok(legacy_payload)
            return _ok(chart_payload)
        if path == "/api/terminal/charts/volume":
            return _ok(build_volume_chart_payload())
        if path == "/api/terminal/market-analysis":
            return _ok(build_market_analysis())
        if path == "/api/terminal/charts/forecast-path":
            return _ok(build_terminal_forecast_path())
        if path == "/api/terminal/charts/equity-curve":
            return _ok(build_equity_curve_payload())
        if path == "/api/terminal/charts/drawdown":
            return _ok(build_drawdown_curve_payload())
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
        if path == "/api/terminal/events/source-quality-report":
            return _ok(build_source_quality_report())
        if path == "/api/terminal/events/evidence":
            return _ok(build_terminal_event_evidence(_query_value(query, "horizon", "tomorrow")))
        if path == "/api/terminal/reports/full":
            return _ok(build_terminal_report_full(_query_value(query, "type", "daily")))
        if path == "/api/terminal/reports/full-system-txt/latest":
            return _ok(get_latest_full_system_txt_report())
        if path == "/api/terminal/factors/diagnostics":
            return _ok(build_terminal_factor_diagnostics())
        if path == "/api/terminal/factors/coverage":
            version = _query_value(query, "version", None) or "latest"
            return _ok(
                cached_call(
                    f"terminal:feature-coverage:{version}",
                    30,
                    lambda: build_feature_coverage_report(report_version=None if version == "latest" else version),
                )
            )
        if path == "/api/terminal/factors/online-readiness":
            return _ok(build_online_feature_readiness_report())
        if path == "/api/terminal/feature-store/v12":
            return _ok(get_feature_store_v12_status())
        if path == "/api/terminal/feature-store/status":
            version = _query_value(query, "version", "v3") or "v3"
            if str(version).lower() == "v12":
                return _ok(get_feature_store_v12_status())
            return _ok(get_feature_store_status(version=version))
        if path == "/api/terminal/training-dataset/status":
            dataset_version = _query_value(query, "dataset_version", "v1") or "v1"
            if str(dataset_version).lower() == "v12":
                return _ok(get_training_dataset_v12_status())
            return _ok(get_training_dataset_status(dataset_version=dataset_version))
        if path == "/api/terminal/training-dataset/v12":
            return _ok(get_training_dataset_v12_status())
        if path == "/api/terminal/models/candidate-status":
            return _ok(get_candidate_training_status(candidate_version=_query_value(query, "candidate_version", "v1") or "v1"))
        if path == "/api/terminal/models/candidate-v6/readiness":
            return _ok(get_candidate_v6_readiness())
        if path == "/api/terminal/models/walk-forward-results":
            return _ok(get_walk_forward_results(_query_value(query, "horizon", ""), candidate_version=_query_value(query, "candidate_version", "v1") or "v1"))
        if path == "/api/terminal/models/active-status":
            return _ok(get_active_model_status())
        if path == "/api/terminal/models/active-absence-diagnostics":
            return _ok(build_active_absence_diagnostics())
        if path == "/api/terminal/models/promotion-report":
            return _ok(get_promotion_report(candidate_version=_query_value(query, "candidate_version", "v1") or "v1"))
        if path == "/api/terminal/models/candidate-diagnostics":
            return _ok(build_candidate_diagnostics_report())
        if path == "/api/terminal/research/candidate-v8-diagnostics":
            return _ok(build_candidate_v8_validation_diagnostics())
        if path == "/api/terminal/research/cpcv-report":
            return _ok(build_cpcv_report(candidate_version=_query_value(query, "candidate_version", "v9") or "v9"))
        if path == "/api/terminal/research/year-concentration":
            return _ok(get_year_concentration_report())
        if path == "/api/terminal/research/cost-stress-attribution":
            return _ok(get_cost_stress_attribution_report())
        if path == "/api/terminal/research/v10-cost-remediation":
            return _ok(get_v10_cost_failure_research_report())
        if path == "/api/terminal/research/v10-remediation-preflight":
            return _ok(get_v10_remediation_preflight())
        if path == "/api/terminal/research/shadow-mode-readiness":
            return _ok(get_shadow_mode_readiness_spec())
        if path == "/api/terminal/research/model-registry-safety":
            return _ok(get_model_registry_safety_report())
        if path == "/api/terminal/research/decision-board":
            return _ok(get_research_decision_board())
        if path == "/api/terminal/research/evidence-bundle":
            return _ok(get_latest_evidence_bundle())
        if path == "/api/terminal/research/evidence-freshness":
            return _ok(get_evidence_freshness_report())
        if path == "/api/terminal/research/hypothesis-registry":
            return _ok(get_hypothesis_registry())
        if path == "/api/terminal/research/run-ledger":
            return _ok(get_run_ledger_report())
        if path == "/api/terminal/research/readiness-dag":
            return _ok(get_readiness_dag_report())
        if path == "/api/terminal/governance/access-control":
            return _ok(get_access_control_report())
        if path == "/api/terminal/governance/observability":
            return _ok(get_governance_observability_report())
        if path == "/api/terminal/governance/incident-drill":
            return _ok(get_incident_drill_report())
        if path == "/api/terminal/governance/manual-approval":
            return _ok(build_manual_approval_status())
        if path == "/api/terminal/governance/shadow-output-contract":
            return _ok(get_shadow_output_contract_report())
        if path == "/api/terminal/governance/shadow-replay":
            return _ok(get_shadow_replay_report())
        if path == "/api/terminal/governance/post-release-monitoring-spec":
            return _ok(get_post_release_monitoring_spec())
        if path == "/api/terminal/governance/rollback-rehearsal":
            return _ok(get_latest_rollback_rehearsal_report())
        if path == "/api/terminal/governance/external-audit-export":
            return _ok(get_external_audit_export())
        if path == "/api/terminal/governance/production-cutover-checklist":
            return _ok(get_production_cutover_checklist())
        if path == "/api/terminal/governance/promotion-dry-run-evidence":
            return _ok(get_promotion_dry_run_evidence())
        if path == "/api/terminal/governance/model-card":
            return _ok(get_latest_model_card())
        if path == "/api/terminal/governance/maturity-matrix":
            return _ok(get_latest_governance_maturity_matrix())
        if path == "/api/terminal/research/candidate-v10-report":
            return _ok(get_candidate_v10_report())
        if path == "/api/terminal/research/candidate-v12-report":
            return _ok(get_candidate_v12_report())
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
            report_version = _query_value(query, "candidate_version", None) or _query_value(query, "version", "v3") or "v3"
            return _ok(
                get_research_backtest_report(
                    run_id=_query_value(query, "run_id", None),
                    candidate_version=report_version,
                )
            )
        if path == "/api/terminal/research/equity-curve":
            curve_version = _query_value(query, "candidate_version", None) or _query_value(query, "version", "v3") or "v3"
            return _ok(
                get_research_equity_curve(
                    run_id=_query_value(query, "run_id", None),
                    horizon=_query_value(query, "horizon", "1d") or "1d",
                    candidate_version=curve_version,
                )
            )
        if path == "/api/terminal/research/artifacts":
            artifact_version = _query_value(query, "candidate_version", None) or _query_value(query, "version", None)
            run_id = _query_value(query, "run_id", None) or "latest"
            version = artifact_version or "latest"
            return _ok(
                cached_call(
                    f"terminal:artifacts:{run_id}:{version}",
                    30,
                    lambda: get_research_artifacts(
                        run_id=None if run_id == "latest" else run_id,
                        candidate_version=None if version == "latest" else version,
                    ),
                )
            )
        if path == "/api/terminal/tasks/status":
            return _ok(get_task_status(_query_value(query, "id", "")))
        if path == "/api/terminal/tasks/recent":
            return _ok(get_recent_tasks(int(_query_value(query, "limit", "20") or "20")))
        if path == "/api/terminal/task-notifications":
            return _ok(build_task_notifications(int(_query_value(query, "limit", "20") or "20")))
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
                clear_api_response_cache()
                return _task_response("refresh_all", lambda: run_institutional_refresh_all(force=force), {"force": force})
            if path == "/api/terminal/refresh/market":
                clear_api_response_cache("terminal:")
                return _task_response(
                    "refresh_market",
                    lambda refresh_fn=run_institutional_refresh_steps, force=force: refresh_fn(["market"], force=force),
                    {"force": force},
                )
            if path == "/api/terminal/refresh/fundamentals":
                clear_api_response_cache("terminal:")
                return _task_response("refresh_all", lambda: run_institutional_refresh_steps(["fundamentals", "features"], force=force), {"force": force, "steps": ["fundamentals", "features"]})
            if path == "/api/terminal/refresh/cross-market":
                clear_api_response_cache("terminal:")
                return _task_response("refresh_cross_market", lambda: run_institutional_refresh_steps(["online_cross_market", "features"], force=force), {"force": force})
            if path == "/api/terminal/refresh/tushare":
                clear_api_response_cache("terminal:")
                return _task_response("refresh_all", lambda: run_institutional_refresh_steps(["tushare_futures", "features"], force=force), {"force": force, "steps": ["tushare_futures", "features"]})
            if path == "/api/terminal/refresh/managed-proxy":
                clear_api_response_cache("terminal:")
                return _task_response("refresh_all", lambda: run_institutional_refresh_steps(["managed_data_proxy", "features"], force=force), {"force": force, "steps": ["managed_data_proxy", "features"]})
            if path == "/api/terminal/refresh/managed-proxy-v11":
                clear_api_response_cache("terminal:")
                return _task_response(
                    "refresh_all",
                    lambda: run_managed_proxy_v11_real_loop(force=force),
                    {"force": force, "steps": ["managed_data_proxy", "feature_store_v11"], "feature_store_version": "v11", "active_publish": False},
                )
            if path == "/api/terminal/refresh/news":
                clear_api_response_cache("terminal:")
                return _task_response("refresh_news", lambda: run_institutional_refresh_steps(["news", "event_relevance", "events", "features"], force=force), {"force": force})
            if path == "/api/terminal/refresh/predictions":
                return _task_response("refresh_all", lambda: run_institutional_refresh_steps(["predictions"], force=force), {"force": force, "steps": ["predictions"]})
            if path == "/api/terminal/refresh/reports":
                return _task_response("refresh_all", lambda: run_institutional_refresh_steps(["reports"], force=force), {"force": force, "steps": ["reports"]})
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
            result = test_provider(str((payload or {}).get("provider") or ""))
            bridge_provider_smoke_result(result, source="legacy_provider_test")
            return _ok(result)
        if path == "/api/terminal/newsapi/test":
            return _ok(test_newsapi_connection())
        if path == "/api/terminal/system/shutdown":
            payload, _ = _parse_body(body)
            return _ok(request_server_shutdown(str((payload or {}).get("reason") or "api")))
        if path == "/api/terminal/cache/invalidate":
            payload, _ = _parse_body(body)
            return _ok(invalidate_terminal_caches(str((payload or {}).get("reason") or "manual")))
        if path == "/api/terminal/setup-checklist/run-safe-action":
            payload, error = _parse_body(body)
            if error is not None:
                return 400, error
            action_id = str((payload or {}).get("action_id") or (payload or {}).get("safe_action_id") or "")
            validation = validate_no_forbidden_setup_actions(action_id)
            if validation.get("status") != "allowed":
                return 400, validation
            clear_api_response_cache("terminal:")
            return _ok(run_setup_checklist_safe_action(action_id))
        if path == "/api/terminal/diagnostics/export":
            return _ok(export_diagnostics_bundle())
        if path == "/api/terminal/local-api-provider/refresh-hub":
            clear_api_response_cache("terminal:")
            return _ok(refresh_local_api_provider_hub())
        if path == "/api/terminal/local-api-provider/refresh-credentials":
            clear_api_response_cache("terminal:")
            payload = refresh_provider_credentials_report()
            record_setup_action_result(
                "refresh_provider_credentials",
                status="success" if payload.get("status") == "configured" else "blocked",
                blocking_reasons=payload.get("blocking_reasons") or [],
                next_allowed_action=str(payload.get("current_step") or "configure_local_api_provider_credentials"),
                triggered_endpoint="/api/terminal/local-api-provider/refresh-credentials",
            )
            return _ok(payload)
        if path == "/api/terminal/local-api-provider/run-smoke":
            payload, error = _parse_body(body)
            if error is not None:
                return 400, error
            forbidden_keys = [
                key
                for key in (payload or {})
                if any(fragment in str(key).lower() for fragment in ("key", "token", "secret", "password", "authorization"))
            ]
            if forbidden_keys:
                return 400, sanitize_for_json(
                    {
                        "status": "blocked",
                        "blocking_reasons": ["raw_provider_credential_input_forbidden"],
                        "forbidden_fields": forbidden_keys,
                        "training_invoked": False,
                        "active_updated": False,
                        "customer_prediction_generated": False,
                    }
                )
            provider = str((payload or {}).get("provider") or (payload or {}).get("provider_id") or "twelvedata")
            clear_api_response_cache("terminal:")
            smoke = run_provider_smoke_test(provider)
            bridge_provider_smoke_result(smoke, source="local_api_provider_smoke")
            record_setup_action_result(
                "run_provider_smoke",
                status="success" if smoke.get("status") in {"pass", "research_only"} else "blocked",
                blocking_reasons=smoke.get("blocking_reasons") or [],
                next_allowed_action="refresh_schema_mapping" if smoke.get("status") == "pass" else "configure_local_api_provider_credentials",
                triggered_endpoint="/api/terminal/local-api-provider/run-smoke",
            )
            return _ok(smoke)
        if path == "/api/terminal/managed-proxy/check":
            clear_api_response_cache("terminal:")
            return _ok(check_managed_proxy_health())
        if path == "/api/terminal/managed-proxy/refresh-setup":
            clear_api_response_cache("terminal:")
            return _ok(refresh_managed_proxy_setup())
        if path == "/api/terminal/managed-proxy/refresh-config-wizard":
            clear_api_response_cache("terminal:")
            return _ok(refresh_managed_proxy_config_wizard())
        if path == "/api/terminal/managed-proxy/refresh-config-handoff":
            clear_api_response_cache("terminal:")
            payload = refresh_config_handoff_report()
            record_setup_action_result(
                "refresh_config_handoff",
                status="success",
                blocking_reasons=[],
                next_allowed_action=str(payload.get("next_safe_actions_after_config", [""])[0] if payload.get("next_safe_actions_after_config") else ""),
                triggered_endpoint="/api/terminal/managed-proxy/refresh-config-handoff",
            )
            return _ok(payload)
        if path == "/api/terminal/managed-proxy/refresh-operator-runbook":
            clear_api_response_cache("terminal:")
            return _ok(refresh_operator_onboarding_runbook())
        if path == "/api/terminal/managed-proxy/refresh-schema-mapping":
            clear_api_response_cache("terminal:")
            return _ok(refresh_schema_mapping_report())
        if path == "/api/terminal/managed-proxy/run-contract-dry-run":
            clear_api_response_cache("terminal:")
            return _ok(run_managed_proxy_schema_dry_run())
        if path == "/api/terminal/managed-proxy/run-canary":
            clear_api_response_cache("terminal:")
            return _ok(run_managed_proxy_canary_check())
        if path == "/api/terminal/managed-proxy/refresh-data-quality":
            clear_api_response_cache("terminal:")
            return _ok(build_managed_data_quality_scorecard())
        if path == "/api/terminal/managed-proxy/run-audit":
            clear_api_response_cache("terminal:")
            return _ok(build_managed_audit_manifest())
        if path == "/api/terminal/managed-proxy/run-pit-replay":
            clear_api_response_cache("terminal:")
            return _ok(run_pit_replay_harness())
        if path == "/api/terminal/managed-proxy/import-sample-fixture":
            clear_api_response_cache("terminal:")
            return _ok(import_managed_proxy_sample_fixture())
        if path == "/api/terminal/managed-proxy/run-sample-fixture-contract-tests":
            clear_api_response_cache("terminal:")
            return _ok(run_fixture_contract_tests())
        if path == "/api/terminal/managed-proxy/run-endpoint-smoke":
            clear_api_response_cache("terminal:")
            return _ok(run_endpoint_smoke_test())
        if path == "/api/terminal/managed-proxy/pull-quarantine-snapshot":
            payload, error = _parse_body(body)
            if error is not None:
                return 400, error
            forbidden = _forbidden_quarantine_snapshot_request(payload or {})
            if forbidden is not None:
                return 400, forbidden
            requested_rows_raw = (payload or {}).get("requested_rows", 1)
            try:
                requested_rows = int(requested_rows_raw)
            except (TypeError, ValueError):
                return 400, {"error": "invalid_requested_rows", "message": "requested_rows must be an integer."}
            clear_api_response_cache("terminal:")
            return _ok(pull_managed_proxy_quarantine_snapshot(requested_rows=requested_rows))
        if path == "/api/terminal/managed-proxy/run-quarantine-contract":
            payload, error = _parse_body(body)
            if error is not None:
                return 400, error
            forbidden = _forbidden_quarantine_contract_request(payload or {})
            if forbidden is not None:
                return 400, forbidden
            clear_api_response_cache("terminal:")
            return _ok(build_quarantine_contract_report())
        if path == "/api/terminal/managed-proxy/promote-quarantine-to-research-cache":
            payload, error = _parse_body(body)
            if error is not None:
                return 400, error
            forbidden = _forbidden_quarantine_contract_request(payload or {})
            if forbidden is not None:
                return 400, forbidden
            clear_api_response_cache("terminal:")
            return _ok(promote_quarantine_to_research_cache())
        if path == "/api/terminal/managed-proxy/refresh-backfill-plan":
            payload, error = _parse_body(body)
            if error is not None:
                return 400, error
            forbidden = _forbidden_backfill_planner_request(payload or {})
            if forbidden is not None:
                return 400, forbidden
            clear_api_response_cache("terminal:")
            return _ok(write_backfill_planner_report())
        if path in {
            "/api/terminal/managed-proxy/refresh-production-cache-gate",
            "/api/terminal/managed-proxy/build-production-cache-dry-run",
        }:
            payload, error = _parse_body(body)
            if error is not None:
                return 400, error
            forbidden = _forbidden_production_cache_gate_request(payload or {})
            if forbidden is not None:
                return 400, forbidden
            clear_api_response_cache("terminal:")
            return _ok(build_production_cache_gate_report())
        if path == "/api/terminal/feature-store/refresh-v12-input-contract":
            payload, error = _parse_body(body)
            if error is not None:
                return 400, error
            forbidden = _forbidden_v12_input_contract_request(payload or {})
            if forbidden is not None:
                return 400, forbidden
            clear_api_response_cache("terminal:")
            return _ok(build_v12_input_contract_report())
        if path == "/api/terminal/feature-store/refresh-v12-build-plan":
            payload, error = _parse_body(body)
            if error is not None:
                return 400, error
            forbidden = _forbidden_v12_build_plan_request(payload or {})
            if forbidden is not None:
                return 400, forbidden
            clear_api_response_cache("terminal:")
            return _ok(write_v12_build_plan_report())
        if path == "/api/terminal/feature-store/run-v12-controlled-build":
            payload, error = _parse_body(body)
            if error is not None:
                return 400, error
            forbidden = _forbidden_v12_controlled_build_request(payload or {})
            if forbidden is not None:
                return 400, forbidden
            clear_api_response_cache("terminal:")
            return _ok(execute_feature_store_v12_controlled_build())
        if path == "/api/terminal/diagnostics/build-repair-plan":
            return _ok(build_system_repair_plan())
        if path == "/api/terminal/reports/full-system-txt":
            return _ok(build_full_system_txt_report())
        if path == "/api/terminal/feature-store/build":
            payload, error = _parse_body(body)
            if error is not None:
                return 400, error
            version = str((payload or {}).get("version") or "v3")
            clear_api_response_cache("terminal:feature")
            return _task_response(
                "build_feature_store",
                lambda: build_feature_store_v12()
                if version.lower() == "v12"
                else build_feature_store_v11()
                if version.lower() == "v11"
                else build_feature_store_v10()
                if version.lower() == "v10"
                else build_feature_store_v7()
                if version.lower() == "v7"
                else build_feature_store_v6()
                if version.lower() == "v6"
                else build_feature_store_v5()
                if version.lower() == "v5"
                else build_feature_store_v4()
                if version.lower() == "v4"
                else build_feature_store(version=version),
                {"version": version, "active_publish": False},
            )
        if path == "/api/terminal/feature-store/build-v12":
            clear_api_response_cache("terminal:feature")
            return _task_response(
                "build_feature_store",
                lambda: build_feature_store_v12(),
                {"version": "v12", "active_publish": False, "training_dataset_v12_auto_triggered": False},
            )
        if path == "/api/terminal/training-dataset/build-v12":
            clear_api_response_cache("terminal:training-dataset")
            return _task_response(
                "build_training_dataset",
                lambda: build_training_dataset_v12(),
                {
                    "dataset_version": "v12",
                    "feature_store_version": "v12",
                    "active_publish": False,
                    "candidate_v12_auto_triggered": False,
                },
            )
        if path == "/api/terminal/training-dataset/build":
            payload, error = _parse_body(body)
            if error is not None:
                return 400, error
            raw_horizons = (payload or {}).get("horizons") or [1, 3, 5, 10, 20]
            horizons = [int(item) for item in raw_horizons] if isinstance(raw_horizons, list) else [1, 3, 5, 10, 20]
            min_coverage = float((payload or {}).get("min_feature_coverage", 0.7))
            dataset_version = str((payload or {}).get("dataset_version") or "v1")
            feature_store_version = str((payload or {}).get("feature_store_version")) if (payload or {}).get("feature_store_version") else None
            return _task_response(
                "build_training_dataset",
                lambda: build_training_dataset_v12(horizons=tuple(horizons))
                if dataset_version.lower() == "v12"
                else build_training_dataset_v10(horizons=tuple(horizons), min_feature_coverage=min_coverage)
                if dataset_version.lower() == "v10"
                else build_training_dataset_v7(horizons=tuple(horizons), min_feature_coverage=min_coverage)
                if dataset_version.lower() == "v7"
                else build_training_dataset(
                    horizons=horizons,
                    min_feature_coverage=min_coverage,
                    dataset_version=dataset_version,
                    feature_set=str((payload or {}).get("feature_set") or "ohlcv_technical_regime"),
                    feature_store_version=feature_store_version,
                ),
                {
                    "horizons": horizons,
                    "dataset_version": dataset_version,
                    "feature_store_version": "v12" if dataset_version.lower() == "v12" else feature_store_version,
                    "active_publish": False,
                    "candidate_v12_auto_triggered": False if dataset_version.lower() == "v12" else None,
                },
            )
        if path == "/api/terminal/models/train-candidate":
            payload, error = _parse_body(body)
            if error is not None:
                return 400, error
            raw_horizons = (payload or {}).get("horizons") or ["1d", "3d", "5d", "10d", "20d"]
            horizons = [str(item) for item in raw_horizons] if isinstance(raw_horizons, list) else ["1d", "3d", "5d", "10d", "20d"]
            return _ok(
                start_task(
                    "train_candidate",
                    lambda train_fn=run_candidate_training, payload=payload, horizons=horizons: train_fn(
                        horizons=horizons,
                        candidate_version=str((payload or {}).get("candidate_version") or "v1"),
                        dataset_version=str((payload or {}).get("dataset_version") or "v1"),
                        feature_set=str((payload or {}).get("feature_set") or ""),
                        label_variants=(payload or {}).get("label_variants") if isinstance((payload or {}).get("label_variants"), list) else None,
                        models=(payload or {}).get("models") if isinstance((payload or {}).get("models"), list) else None,
                        calibration=(payload or {}).get("calibration") if isinstance((payload or {}).get("calibration"), list) else None,
                        no_trade_filters=(payload or {}).get("no_trade_filters") if isinstance((payload or {}).get("no_trade_filters"), list) else None,
                    ),
                    payload={"horizons": horizons},
                )
            )
        if path == "/api/terminal/tasks/start":
            payload, error = _parse_body(body)
            if error is not None:
                return 400, error
            kind = str((payload or {}).get("kind") or "manual")
            invalid = _unknown_task_kind(kind)
            if invalid is not None:
                return invalid
            return _ok(start_task(kind, payload=payload or {}))
        if path == "/api/terminal/tasks/cancel":
            return _ok(cancel_task(_query_value(query, "id", "")))
        if path == "/api/terminal/models/promote-candidate":
            payload, _ = _parse_body(body)
            dry_query = str(_query_value(query, "dry_run", "") or "").lower() in {"1", "true", "yes"}
            dry_body = bool((payload or {}).get("dry_run")) if isinstance(payload, dict) else False
            return _ok(promote_candidate(candidate_version=str((payload or {}).get("candidate_version") or _query_value(query, "candidate_version", "v1") or "v1"), dry_run=dry_query or dry_body))
        if path == "/api/terminal/models/approve-active":
            payload, error = _parse_body(body)
            if error is not None:
                return 400, error
            return _ok(
                approve_active_release(
                    candidate_version=str((payload or {}).get("candidate_version") or "v5"),
                    approval_phrase=str((payload or {}).get("approval_phrase") or ""),
                    approver=str((payload or {}).get("approver") or ""),
                    notes=str((payload or {}).get("notes") or ""),
                )
            )
        if path == "/api/terminal/research/run-model-experiment":
            payload, error = _parse_body(body)
            if error is not None:
                return 400, error
            return _task_response("train_candidate", lambda: run_model_experiment(payload or {}), {"experiment": True})
        if path == "/api/terminal/research/run-candidate-v3":
            payload, _ = _parse_body(body)
            raw_horizons = (payload or {}).get("horizons") or ["1d", "3d", "5d", "10d", "20d"]
            horizons = [str(item) for item in raw_horizons] if isinstance(raw_horizons, list) else ["1d", "3d", "5d", "10d", "20d"]
            return _task_response("train_candidate", lambda: run_candidate_v3_research(horizons=horizons), {"candidate_version": "v3", "horizons": horizons})
        if path == "/api/terminal/research/run-candidate-v4":
            payload, _ = _parse_body(body)
            raw_horizons = (payload or {}).get("horizons") or ["1d", "3d", "5d", "10d", "20d"]
            horizons = [str(item) for item in raw_horizons] if isinstance(raw_horizons, list) else ["1d", "3d", "5d", "10d", "20d"]
            return _task_response("train_candidate", lambda: run_candidate_v4_research(horizons=horizons), {"candidate_version": "v4", "horizons": horizons})
        if path == "/api/terminal/research/run-candidate-v5":
            payload, _ = _parse_body(body)
            raw_horizons = (payload or {}).get("horizons") or ["1d", "3d", "5d", "10d", "20d"]
            horizons = [str(item) for item in raw_horizons] if isinstance(raw_horizons, list) else ["1d", "3d", "5d", "10d", "20d"]
            return _task_response("train_candidate", lambda: run_candidate_v5_research(horizons=horizons), {"candidate_version": "v5", "horizons": horizons})
        if path == "/api/terminal/research/run-candidate-v6":
            payload, _ = _parse_body(body)
            raw_horizons = (payload or {}).get("horizons") or ["1d", "3d", "5d", "10d", "20d"]
            horizons = [str(item) for item in raw_horizons] if isinstance(raw_horizons, list) else ["1d", "3d", "5d", "10d", "20d"]
            return _task_response(
                "train_candidate",
                lambda: run_candidate_v6_gated_research(horizons=horizons),
                {"candidate_version": "v6", "horizons": horizons, "active_publish": False},
            )
        if path == "/api/terminal/research/run-candidate-v7":
            payload, _ = _parse_body(body)
            raw_horizons = (payload or {}).get("horizons") or ["1d", "3d", "5d", "10d", "20d"]
            horizons = [str(item) for item in raw_horizons] if isinstance(raw_horizons, list) else ["1d", "3d", "5d", "10d", "20d"]
            return _task_response(
                "train_candidate",
                lambda: run_candidate_v7_research(horizons=horizons),
                {"candidate_version": "v7", "horizons": horizons, "active_publish": False},
            )
        if path == "/api/terminal/research/run-candidate-v8":
            payload, _ = _parse_body(body)
            raw_horizons = (payload or {}).get("horizons") or ["1d", "3d", "5d", "10d", "20d"]
            horizons = [str(item) for item in raw_horizons] if isinstance(raw_horizons, list) else ["1d", "3d", "5d", "10d", "20d"]
            return _task_response(
                "train_candidate",
                lambda: run_candidate_v8_research(horizons=horizons),
                {"candidate_version": "v8", "horizons": horizons, "active_publish": False},
            )
        if path == "/api/terminal/research/run-candidate-v9":
            payload, _ = _parse_body(body)
            raw_horizons = (payload or {}).get("horizons") or ["1d", "3d", "5d", "10d", "20d"]
            horizons = [str(item) for item in raw_horizons] if isinstance(raw_horizons, list) else ["1d", "3d", "5d", "10d", "20d"]
            return _task_response(
                "train_candidate",
                lambda: run_candidate_v9_research(horizons=horizons),
                {"candidate_version": "v9", "horizons": horizons, "active_publish": False},
            )
        if path == "/api/terminal/research/run-candidate-v10":
            payload, _ = _parse_body(body)
            raw_horizons = (payload or {}).get("horizons") or ["1d", "3d", "5d", "10d", "20d"]
            horizons = [str(item) for item in raw_horizons] if isinstance(raw_horizons, list) else ["1d", "3d", "5d", "10d", "20d"]
            return _task_response(
                "train_candidate",
                lambda: run_candidate_v10_research(horizons=horizons),
                {"candidate_version": "v10", "horizons": horizons, "active_publish": False},
            )
        if path == "/api/terminal/research/refresh-year-concentration":
            return _ok(refresh_year_concentration())
        if path == "/api/terminal/research/refresh-cost-stress-attribution":
            return _ok(refresh_cost_stress_attribution())
        if path == "/api/terminal/research/refresh-v10-cost-remediation":
            return _ok(build_cost_failure_research_report())
        if path == "/api/terminal/research/refresh-v10-remediation-preflight":
            return _ok(build_remediation_preflight())
        if path == "/api/terminal/research/refresh-shadow-mode-readiness":
            return _ok(build_shadow_mode_readiness_spec())
        if path == "/api/terminal/research/refresh-model-registry-safety":
            return _ok(build_registry_safety_report())
        if path == "/api/terminal/research/refresh-decision-board":
            return _ok(build_research_decision_board())
        if path == "/api/terminal/research/refresh-evidence-bundle":
            return _ok(write_evidence_bundle())
        if path == "/api/terminal/research/refresh-evidence-freshness":
            return _ok(build_evidence_freshness_report())
        if path == "/api/terminal/research/create-hypothesis-template":
            payload, _ = _parse_body(body)
            return _ok(create_hypothesis_template(payload))
        if path == "/api/terminal/research/refresh-anti-p-hacking-ledger":
            return _ok(build_anti_p_hacking_ledger())
        if path == "/api/terminal/research/refresh-run-ledger":
            return _ok(build_run_ledger_report())
        if path == "/api/terminal/research/refresh-readiness-dag":
            return _ok(write_readiness_dag_report())
        if path == "/api/terminal/research/run-safe-readiness-checks":
            clear_api_response_cache("terminal:")
            return _ok(run_readiness_checks_dry_run())
        if path == "/api/terminal/governance/refresh-access-control":
            return _ok(refresh_access_control_report())
        if path == "/api/terminal/governance/refresh-observability":
            return _ok(refresh_governance_observability_report())
        if path == "/api/terminal/governance/run-incident-drill":
            payload, _ = _parse_body(body)
            simulation_only = bool((payload or {}).get("simulation_only", True))
            return _ok(run_incident_drill_simulation(simulation_only=simulation_only))
        if path == "/api/terminal/governance/refresh-lockdown-state":
            return _ok(refresh_lockdown_state_report())
        if path == "/api/terminal/governance/refresh-manual-approval":
            return _ok(refresh_manual_approval_status())
        if path == "/api/terminal/governance/create-manual-approval-request":
            payload, error = _parse_body(body)
            if error is not None:
                return 400, error
            expires = (payload or {}).get("expires_in_hours", 72) if isinstance(payload, dict) else 72
            try:
                expires_in_hours = int(expires)
            except (TypeError, ValueError):
                expires_in_hours = 72
            return _ok(
                create_manual_approval_request(
                    requested_action=str((payload or {}).get("requested_action") or "shadow_mode_only"),
                    candidate_version=str((payload or {}).get("candidate_version") or "v12"),
                    expires_in_hours=expires_in_hours,
                )
            )
        if path == "/api/terminal/governance/record-manual-approval-decision":
            payload, error = _parse_body(body)
            if error is not None:
                return 400, error
            reviewers = (payload or {}).get("reviewers") if isinstance(payload, dict) else []
            return _ok(
                record_manual_approval_decision(
                    decision=str((payload or {}).get("decision") or ""),
                    reviewers=reviewers if isinstance(reviewers, list) else [],
                    notes=str((payload or {}).get("notes") or ""),
                )
            )
        if path == "/api/terminal/governance/refresh-shadow-output-contract":
            return _ok(refresh_shadow_output_contract_report())
        if path == "/api/terminal/governance/build-shadow-output-dry-run":
            payload, error = _parse_body(body)
            if error is not None:
                return 400, error
            return _ok(
                build_shadow_output_dry_run_artifact(
                    synthetic_contract_only=True,
                    candidate_version=str((payload or {}).get("candidate_version") or "v12"),
                    horizon=str((payload or {}).get("horizon") or "1d"),
                    instrument=str((payload or {}).get("instrument") or "SN"),
                )
            )
        if path == "/api/terminal/governance/refresh-external-audit-export":
            return _ok(write_external_audit_package())
        if path == "/api/terminal/governance/refresh-production-cutover-checklist":
            return _ok(build_cutover_report())
        if path == "/api/terminal/governance/build-noop-release-plan":
            payload, error = _parse_body(body)
            if error is not None:
                return 400, error
            return _ok(
                build_noop_release_plan(
                    intended_candidate_version=str((payload or {}).get("candidate_version") or "v12"),
                )
            )
        if path == "/api/terminal/governance/refresh-promotion-dry-run-evidence":
            payload, error = _parse_body(body)
            if error is not None:
                return 400, error
            return _ok(
                build_promotion_dry_run_evidence(
                    candidate_version=str((payload or {}).get("candidate_version") or "v12"),
                )
            )
        if path == "/api/terminal/governance/refresh-model-card":
            return _ok(write_model_card())
        if path == "/api/terminal/governance/refresh-maturity-matrix":
            return _ok(write_governance_maturity_matrix())
        if path == "/api/terminal/governance/refresh-shadow-replay":
            payload, error = _parse_body(body)
            if error is not None:
                return 400, error
            return _ok(
                build_shadow_replay_evaluator(
                    candidate_version=str((payload or {}).get("candidate_version") or "v10"),
                )
            )
        if path == "/api/terminal/governance/refresh-post-release-monitoring-spec":
            payload, error = _parse_body(body)
            if error is not None:
                return 400, error
            return _ok(build_post_release_monitoring_spec())
        if path == "/api/terminal/governance/refresh-rollback-rehearsal":
            payload, error = _parse_body(body)
            if error is not None:
                return 400, error
            return _ok(build_rollback_rehearsal_plan())
        if path == "/api/terminal/governance/simulate-artifact-quarantine":
            payload, error = _parse_body(body)
            if error is not None:
                return 400, error
            return _ok(simulate_artifact_quarantine())
        if path == "/api/terminal/research/run-candidate-v12":
            payload, _ = _parse_body(body)
            raw_horizons = (payload or {}).get("horizons") or ["1d", "3d", "5d", "10d", "20d"]
            horizons = [str(item) for item in raw_horizons] if isinstance(raw_horizons, list) else ["1d", "3d", "5d", "10d", "20d"]
            return _task_response(
                "train_candidate",
                lambda: run_candidate_v12_research(horizons=horizons, build_missing=False),
                {
                    "candidate_version": "v12",
                    "dataset_version": "v12",
                    "feature_store_version": "v12",
                    "horizons": horizons,
                    "active_publish": False,
                    "customer_prediction_generated": False,
                },
            )
        if path == "/api/terminal/research/run-cpcv-validation":
            payload, _ = _parse_body(body)
            candidate_version = str((payload or {}).get("candidate_version") or "v9")
            return _task_response(
                "run_validation",
                lambda: build_cpcv_report(candidate_version=candidate_version),
                {"candidate_version": candidate_version, "validation": "cpcv", "active_publish": False},
            )
        if path == "/api/terminal/research/run-backtest":
            payload, _ = _parse_body(body)
            raw_horizons = (payload or {}).get("horizons") or ["1d", "3d", "5d", "10d", "20d"]
            horizons = [str(item) for item in raw_horizons] if isinstance(raw_horizons, list) else ["1d", "3d", "5d", "10d", "20d"]
            version = str((payload or {}).get("candidate_version") or (payload or {}).get("version") or _query_value(query, "version", "v3") or "v3")
            return _task_response("run_research_backtest", lambda: run_research_backtest(candidate_version=version, horizons=horizons), {"candidate_version": version, "horizons": horizons})
        if path == "/api/terminal/research/optimize-strategy":
            payload, _ = _parse_body(body)
            raw_horizons = (payload or {}).get("horizons") or ["1d", "3d", "5d", "10d", "20d"]
            horizons = [str(item) for item in raw_horizons] if isinstance(raw_horizons, list) else ["1d", "3d", "5d", "10d", "20d"]
            version = str((payload or {}).get("candidate_version") or (payload or {}).get("version") or _query_value(query, "version", "v3") or "v3")
            return _task_response("run_research_backtest", lambda: optimize_research_strategy(candidate_version=version, horizons=horizons), {"candidate_version": version, "horizons": horizons, "optimizer": "threshold"})
        if path == "/api/terminal/research/optimize-multi-objective":
            payload, _ = _parse_body(body)
            raw_horizons = (payload or {}).get("horizons") or ["1d", "3d", "5d", "10d", "20d"]
            horizons = [str(item) for item in raw_horizons] if isinstance(raw_horizons, list) else ["1d", "3d", "5d", "10d", "20d"]
            version = str((payload or {}).get("candidate_version") or (payload or {}).get("version") or _query_value(query, "version", "v5") or "v5")
            return _task_response("run_research_backtest", lambda: optimize_multi_objective_research_strategy(candidate_version=version, horizons=horizons), {"candidate_version": version, "horizons": horizons, "optimizer": "multi_objective"})
        if path == "/api/terminal/learning-scheduler/run":
            payload, error = _parse_body(body)
            if error is not None:
                return 400, error
            raw_tasks = (payload or {}).get("tasks")
            tasks = [str(item) for item in raw_tasks] if isinstance(raw_tasks, list) else None
            force = bool((payload or {}).get("force") or (payload or {}).get("manual"))
            return _task_response("run_learning_scheduler", lambda: run_learning_scheduler_once(force=force, tasks=tasks), {"force": force, "tasks": tasks or []})
        if path == "/api/terminal/learning-scheduler/pause":
            payload, _ = _parse_body(body)
            return _ok(pause_learning_scheduler(str((payload or {}).get("reason_zh") or (payload or {}).get("reason") or "")))
        if path == "/api/terminal/learning-scheduler/resume":
            return _ok(resume_learning_scheduler())
        if path == "/api/terminal/validation/run-institutional-check":
            payload, _ = _parse_body(body)
            candidate_version = str((payload or {}).get("candidate_version") or "v1")
            dry_run = bool((payload or {}).get("dry_run"))
            return _task_response("run_validation", lambda: run_institutional_validation(candidate_version=candidate_version, dry_run=dry_run), {"candidate_version": candidate_version, "dry_run": dry_run})
        return 404, {"error": "not_found", "message": "未知 terminal API 路径。"}

    return 405, {"error": "method_not_allowed", "message": "该 terminal API 不支持当前请求方法。"}
