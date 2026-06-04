import { useCallback, useState } from "react";
import { buildFeatureStore, buildFeatureStoreV12, getCandidateV6Readiness, getFactorDiagnostics, getFeatureCoverage, getFeatureStoreStatus, getFeatureStoreV12, getFeatureStoreV12BuildPlan, getFeatureStoreV12ControlledBuild, getFeatureStoreV12InputContract, getOnlineFeatureReadiness, refreshFeatureStoreV12BuildPlan, refreshFeatureStoreV12InputContract, refreshManagedProxyV11, runFeatureStoreV12ControlledBuild } from "../api/terminal";
import type {
  CandidateV6ReadinessPayload,
  FactorDiagnosticFeature,
  FactorDiagnosticsPayload,
  FeatureCoverageFeature,
  FeatureCoveragePayload,
  FeatureStoreStatus,
  FeatureStoreV12BuildPlanPayload,
  FeatureStoreV12ControlledBuildPayload,
  FeatureStoreV12InputContractPayload,
  OnlineFieldReadiness,
  OnlineFeatureReadinessPayload,
} from "../api/types";
import { FactorBarChart } from "../components/charts/FactorBarChart";
import { DataTable } from "../components/common/DataTable";
import { EmptyState } from "../components/common/EmptyState";
import { ErrorState } from "../components/common/ErrorState";
import { LoadingState } from "../components/common/LoadingState";
import { SectionCard } from "../components/layout/SectionCard";
import { usePolling } from "../hooks/usePolling";
import { formatNumber, formatNullable } from "../utils/format";

const fallbackGroups = ["技术面", "均值回归", "期限结构", "基差", "库存", "跨市场", "事件", "Regime"];

function availabilityLabel(row: FeatureCoverageFeature) {
  if (row.usable_for_training) return "可训练";
  if (row.availability === "partial") return "部分可用";
  return "不可用";
}

export function FactorPage({ showSampleData = true }: { showSampleData?: boolean }) {
  const diagnosticsLoader = useCallback(() => getFactorDiagnostics(), []);
  const coverageLoader = useCallback(() => getFeatureCoverage(), []);
  const onlineReadinessLoader = useCallback(() => getOnlineFeatureReadiness(), []);
  const candidateV6ReadinessLoader = useCallback(() => getCandidateV6Readiness(), []);
  const featureStoreLoader = useCallback(() => getFeatureStoreStatus("v3"), []);
  const featureStoreV4Loader = useCallback(() => getFeatureStoreStatus("v4"), []);
  const featureStoreV5Loader = useCallback(() => getFeatureStoreStatus("v5"), []);
  const featureStoreV6Loader = useCallback(() => getFeatureStoreStatus("v6"), []);
  const featureStoreV7Loader = useCallback(() => getFeatureStoreStatus("v7"), []);
  const featureStoreV10Loader = useCallback(() => getFeatureStoreStatus("v10"), []);
  const featureStoreV11Loader = useCallback(() => getFeatureStoreStatus("v11"), []);
  const featureStoreV12Loader = useCallback(() => getFeatureStoreV12(), []);
  const featureStoreV12InputContractLoader = useCallback(() => getFeatureStoreV12InputContract(), []);
  const featureStoreV12BuildPlanLoader = useCallback(() => getFeatureStoreV12BuildPlan(), []);
  const featureStoreV12ControlledBuildLoader = useCallback(() => getFeatureStoreV12ControlledBuild(), []);
  const [featureStoreBuilding, setFeatureStoreBuilding] = useState(false);
  const [featureStoreV12BuildPlanRefreshing, setFeatureStoreV12BuildPlanRefreshing] = useState(false);
  const [featureStoreV12ControlledBuildRunning, setFeatureStoreV12ControlledBuildRunning] = useState(false);
  const [featureStoreActionError, setFeatureStoreActionError] = useState("");
  const { data, error, loading, refresh } = usePolling<FactorDiagnosticsPayload>(diagnosticsLoader, 60000);
  const {
    data: coverage,
    error: coverageError,
    loading: coverageLoading,
    refresh: refreshCoverage,
  } = usePolling<FeatureCoveragePayload>(coverageLoader, 60000);
  const {
    data: onlineReadiness,
    error: onlineReadinessError,
    loading: onlineReadinessLoading,
    refresh: refreshOnlineReadiness,
  } = usePolling<OnlineFeatureReadinessPayload>(onlineReadinessLoader, 60000);
  const {
    data: candidateV6Readiness,
    error: candidateV6ReadinessError,
    loading: candidateV6ReadinessLoading,
    refresh: refreshCandidateV6Readiness,
  } = usePolling<CandidateV6ReadinessPayload>(candidateV6ReadinessLoader, 60000);
  const {
    data: featureStore,
    error: featureStoreError,
    loading: featureStoreLoading,
    refresh: refreshFeatureStore,
  } = usePolling<FeatureStoreStatus>(featureStoreLoader, 60000);
  const {
    data: featureStoreV4,
    refresh: refreshFeatureStoreV4,
  } = usePolling<FeatureStoreStatus>(featureStoreV4Loader, 60000);
  const {
    data: featureStoreV5,
    refresh: refreshFeatureStoreV5,
  } = usePolling<FeatureStoreStatus>(featureStoreV5Loader, 60000);
  const {
    data: featureStoreV6,
    refresh: refreshFeatureStoreV6,
  } = usePolling<FeatureStoreStatus>(featureStoreV6Loader, 60000);
  const {
    data: featureStoreV7,
    refresh: refreshFeatureStoreV7,
  } = usePolling<FeatureStoreStatus>(featureStoreV7Loader, 60000);
  const {
    data: featureStoreV10,
    refresh: refreshFeatureStoreV10,
  } = usePolling<FeatureStoreStatus>(featureStoreV10Loader, 60000);
  const {
    data: featureStoreV11,
    refresh: refreshFeatureStoreV11,
  } = usePolling<FeatureStoreStatus>(featureStoreV11Loader, 60000);
  const {
    data: featureStoreV12,
    refresh: refreshFeatureStoreV12,
  } = usePolling<FeatureStoreStatus>(featureStoreV12Loader, 60000);
  const {
    data: featureStoreV12InputContract,
    refresh: refreshFeatureStoreV12InputContractStatus,
  } = usePolling<FeatureStoreV12InputContractPayload>(featureStoreV12InputContractLoader, 60000);
  const {
    data: featureStoreV12BuildPlan,
    refresh: refreshFeatureStoreV12BuildPlanStatus,
  } = usePolling<FeatureStoreV12BuildPlanPayload>(featureStoreV12BuildPlanLoader, 60000);
  const {
    data: featureStoreV12ControlledBuild,
    refresh: refreshFeatureStoreV12ControlledBuildStatus,
  } = usePolling<FeatureStoreV12ControlledBuildPayload>(featureStoreV12ControlledBuildLoader, 60000);
  const groups = data?.sample_mode && !showSampleData ? [] : data?.groups || [];
  const coverageGroups = coverage?.groups || [];
  const usableCount = coverage?.usable_feature_cols?.length || 0;
  const partialCount = coverage?.partial_feature_cols?.length || 0;
  const missingCount = coverage?.not_usable_feature_cols?.length || 0;
  const buildStore = async () => {
    setFeatureStoreBuilding(true);
    setFeatureStoreActionError("");
    try {
      await buildFeatureStore({ version: "v3" });
      await buildFeatureStore({ version: "v5" });
      await buildFeatureStore({ version: "v6" });
      await buildFeatureStore({ version: "v7" });
      await buildFeatureStore({ version: "v10" });
      await buildFeatureStore({ version: "v11" });
      await refreshFeatureStoreV12InputContract();
      await refreshFeatureStoreV12BuildPlan();
      await buildFeatureStoreV12();
      await Promise.all([refreshFeatureStore(), refreshFeatureStoreV4(), refreshFeatureStoreV5(), refreshFeatureStoreV6(), refreshFeatureStoreV7(), refreshFeatureStoreV10(), refreshFeatureStoreV11(), refreshFeatureStoreV12(), refreshFeatureStoreV12InputContractStatus(), refreshFeatureStoreV12BuildPlanStatus(), refreshFeatureStoreV12ControlledBuildStatus(), refreshCoverage(), refreshOnlineReadiness(), refreshCandidateV6Readiness()]);
    } catch (err) {
      setFeatureStoreActionError(err instanceof Error ? err.message : "Feature Store v3 构建失败");
    } finally {
      setFeatureStoreBuilding(false);
    }
  };

  const runManagedProxyV11 = async () => {
    setFeatureStoreBuilding(true);
    setFeatureStoreActionError("");
    try {
      await refreshManagedProxyV11({ force: true });
      await refreshFeatureStoreV12InputContract();
      await refreshFeatureStoreV12BuildPlan();
      await Promise.all([refreshFeatureStoreV10(), refreshFeatureStoreV11(), refreshFeatureStoreV12(), refreshFeatureStoreV12InputContractStatus(), refreshFeatureStoreV12BuildPlanStatus(), refreshCoverage(), refreshOnlineReadiness()]);
    } catch (err) {
      setFeatureStoreActionError(err instanceof Error ? err.message : "managed proxy v11 refresh failed");
    } finally {
      setFeatureStoreBuilding(false);
    }
  };

  const refreshV12BuildPlan = async () => {
    setFeatureStoreV12BuildPlanRefreshing(true);
    setFeatureStoreActionError("");
    try {
      await refreshFeatureStoreV12BuildPlan();
      await refreshFeatureStoreV12BuildPlanStatus();
    } catch (err) {
      setFeatureStoreActionError(err instanceof Error ? err.message : "Feature Store v12 build dry-run plan refresh failed");
    } finally {
      setFeatureStoreV12BuildPlanRefreshing(false);
    }
  };

  const runV12ControlledBuild = async () => {
    setFeatureStoreV12ControlledBuildRunning(true);
    setFeatureStoreActionError("");
    try {
      await runFeatureStoreV12ControlledBuild();
      await Promise.all([refreshFeatureStoreV12ControlledBuildStatus(), refreshFeatureStoreV12(), refreshCoverage()]);
    } catch (err) {
      setFeatureStoreActionError(err instanceof Error ? err.message : "Feature Store v12 controlled build executor failed");
    } finally {
      setFeatureStoreV12ControlledBuildRunning(false);
    }
  };

  if (loading) return <LoadingState label="正在加载因子诊断..." />;
  if (error) {
    return <ErrorState title="因子诊断暂时无法加载" message={error} actionLabel="重新加载" onAction={refresh} />;
  }

  return (
    <div className="page-stack">
      <SectionCard title="Feature Store v3" subtitle="统一对齐 OHLCV、cross-market 和 event_factor_inputs；本步骤不生成预测、不训练模型。">
        <div className="metric-grid compact">
          <div className="metric-card">
            <span className="metric-label">Feature Store 版本</span>
            <strong>{featureStore?.version || "v3"}</strong>
            <small>{featureStore?.status || (featureStoreLoading ? "loading" : "not_built")}</small>
          </div>
          <div className="metric-card">
            <span className="metric-label">样本行数</span>
            <strong>{featureStore?.row_count ?? 0}</strong>
            <small>{formatNullable(featureStore?.date_start)} 至 {formatNullable(featureStore?.date_end)}</small>
          </div>
          <div className="metric-card">
            <span className="metric-label">usable_fields</span>
            <strong>{featureStore?.usable_fields?.length || 0}</strong>
            <small>{(featureStore?.usable_fields || []).slice(0, 4).join("、") || "暂无"}</small>
          </div>
          <div className="metric-card">
            <span className="metric-label">excluded_fields</span>
            <strong>{featureStore?.excluded_fields?.length || 0}</strong>
            <small>{(featureStore?.excluded_fields || []).slice(0, 4).join("、") || "暂无"}</small>
          </div>
        </div>
        <div className="metric-grid compact">
          <div className="metric-card">
            <span className="metric-label">Feature Store v3 manifest</span>
            <strong>{featureStore?.exists ? "ready" : "not_ready"}</strong>
            <small>{featureStore?.manifest_path || "manifest not built"}</small>
          </div>
          <div className="metric-card">
            <span className="metric-label">Feature Store v4 status</span>
            <strong>{featureStoreV4?.status || "not_ready"}</strong>
            <small>{featureStoreV4?.message_zh || featureStoreV4?.manifest_path || "requires real incremental fields"}</small>
          </div>
          <div className="metric-card">
            <span className="metric-label">v4 usable_fields</span>
            <strong>{featureStoreV4?.usable_fields?.length || 0}</strong>
            <small>{(featureStoreV4?.usable_fields || []).slice(0, 4).join(", ") || "blocked or empty"}</small>
          </div>
          <div className="metric-card">
            <span className="metric-label">Feature Store v5 status</span>
            <strong>{featureStoreV5?.status || "not_ready"}</strong>
            <small>{featureStoreV5?.message_zh || featureStoreV5?.manifest_path || "Tushare / managed proxy / Alpha / News inputs"}</small>
          </div>
          <div className="metric-card">
            <span className="metric-label">v5 usable_fields</span>
            <strong>{featureStoreV5?.usable_fields?.length || 0}</strong>
            <small>{(featureStoreV5?.usable_fields || []).slice(0, 4).join(", ") || "not built"}</small>
          </div>
          <div className="metric-card">
            <span className="metric-label">v5 source quality</span>
            <strong>{featureStoreV5?.mock_data_used ? "mock_detected" : "real_or_missing"}</strong>
            <small>{Object.keys(featureStoreV5?.source_quality || {}).slice(0, 4).join(", ") || "build v5 to inspect sources"}</small>
          </div>
          <div className="metric-card">
            <span className="metric-label">Feature Store v6 status</span>
            <strong>{featureStoreV6?.status || "not_ready"}</strong>
            <small>{featureStoreV6?.message_zh || featureStoreV6?.manifest_path || "Tushare auxiliary interfaces"}</small>
          </div>
          <div className="metric-card">
            <span className="metric-label">v6 auxiliary fields</span>
            <strong>{["warehouse_receipt_delta_1w", "trading_fee", "long_margin_rate", "member_net_position"].filter((field) => featureStoreV6?.usable_fields?.includes(field)).length}</strong>
            <small>{["warehouse_receipt_delta_1w", "trading_fee", "long_margin_rate", "member_net_position"].join(", ")}</small>
          </div>
          <div className="metric-card">
            <span className="metric-label">failed_subinterfaces</span>
            <strong>{featureStoreV6?.failed_subinterfaces?.length || 0}</strong>
            <small>{(featureStoreV6?.failed_subinterfaces || []).map((item) => String(item.api_name || item.status || "unknown")).slice(0, 3).join(", ") || "none"}</small>
          </div>
          <div className="metric-card">
            <span className="metric-label">Feature Store v7 status</span>
            <strong>{featureStoreV7?.status || "not_ready"}</strong>
            <small>{featureStoreV7?.manifest_path || "cost and positioning features"}</small>
          </div>
          <div className="metric-card">
            <span className="metric-label">v7 cost features</span>
            <strong>{featureStoreV7?.cost_features?.length || 0}</strong>
            <small>{(featureStoreV7?.cost_features || []).slice(0, 4).join(", ") || "not built"}</small>
          </div>
          <div className="metric-card">
            <span className="metric-label">v7 positioning features</span>
            <strong>{featureStoreV7?.positioning_features?.length || 0}</strong>
            <small>{(featureStoreV7?.positioning_features || []).slice(0, 4).join(", ") || "not built"}</small>
          </div>
          <div className="metric-card">
            <span className="metric-label">v7 sparse policy</span>
            <strong>{featureStoreV7?.sparse_feature_policy ? "configured" : "not_ready"}</strong>
            <small>{(featureStoreV7?.sparse_features || []).slice(0, 4).join(", ") || "sparse holding policy"}</small>
          </div>
          <div className="metric-card">
            <span className="metric-label">warehouse_missing_policy</span>
            <strong>{featureStoreV7?.warehouse_missing_policy?.warehouse_receipt_available ? "real_warehouse_ready" : "missing_risk_flag"}</strong>
            <small>{featureStoreV7?.warehouse_missing_policy?.reason || "inventory_missing_flag / warehouse_data_quality_score"}</small>
          </div>
          <div className="metric-card">
            <span className="metric-label">Feature Store v10</span>
            <strong>{featureStoreV10?.feature_store_v10_readiness?.status || featureStoreV10?.status || "not_ready"}</strong>
            <small>managed fundamentals / no_fake_data: {featureStoreV10?.no_fake_data ? "true" : "pending"}</small>
          </div>
          <div className="metric-card">
            <span className="metric-label">v10 managed fields</span>
            <strong>{featureStoreV10?.managed_fundamental_fields?.length || 0}</strong>
            <small>{(featureStoreV10?.managed_fundamental_fields || []).slice(0, 4).join(", ") || "shfe_warehouse_receipt / basis / LME pending"}</small>
          </div>
          <div className="metric-card">
            <span className="metric-label">v10 missing fields</span>
            <strong>{featureStoreV10?.missing_managed_fields?.length || 0}</strong>
            <small>{(featureStoreV10?.missing_managed_fields || ["shfe_inventory", "spot_futures_basis", "lme_tin_close"]).slice(0, 4).join(", ")}</small>
          </div>
          <div className="metric-card">
            <span className="metric-label">Feature Store v11</span>
            <strong>{featureStoreV11?.feature_store_v11_readiness?.status || featureStoreV11?.status || "not_ready"}</strong>
            <small>managed proxy minimal real loop / no_fake_data: {featureStoreV11?.no_fake_data ? "true" : "pending"}</small>
          </div>
          <div className="metric-card">
            <span className="metric-label">v11 managed fields</span>
            <strong>{featureStoreV11?.managed_fundamental_fields?.length || 0}</strong>
            <small>{(featureStoreV11?.managed_fundamental_fields || []).slice(0, 4).join(", ") || "spot/basis/inventory/LME pending"}</small>
          </div>
          <div className="metric-card">
            <span className="metric-label">v11 missing fields</span>
            <strong>{featureStoreV11?.feature_store_v11_readiness?.missing_fields?.length || featureStoreV11?.missing_managed_fields?.length || 0}</strong>
            <small>{(featureStoreV11?.feature_store_v11_readiness?.missing_fields || featureStoreV11?.missing_managed_fields || ["shfe_warehouse_receipt", "spot_futures_basis", "lme_tin_close"]).slice(0, 4).join(", ")}</small>
          </div>
          <div className="metric-card">
            <span className="metric-label">Feature Store v12</span>
            <strong>{featureStoreV12?.status || "not_ready"}</strong>
            <small>blocked-first PIT managed build</small>
          </div>
          <div className="metric-card">
            <span className="metric-label">health status</span>
            <strong>{featureStoreV12?.health_status || "missing"}</strong>
            <small>audit status: {featureStoreV12?.audit_status || "missing"}</small>
          </div>
          <div className="metric-card">
            <span className="metric-label">managed field coverage</span>
            <strong>{featureStoreV12?.managed_field_coverage?.label || "0/0"}</strong>
            <small>{(featureStoreV12?.missing_fundamental_fields || []).slice(0, 4).join(", ") || "required fields complete"}</small>
          </div>
          <div className="metric-card">
            <span className="metric-label">timestamp coverage</span>
            <strong>{featureStoreV12?.timestamp_field_coverage?.label || "0/0"}</strong>
            <small>{(featureStoreV12?.missing_timestamp_fields || []).slice(0, 4).join(", ") || "timestamp fields complete"}</small>
          </div>
          <div className="metric-card">
            <span className="metric-label">PIT join</span>
            <strong>{featureStoreV12?.point_in_time_join_ready ? "ready" : "blocked"}</strong>
            <small>no-lookahead: {featureStoreV12?.no_lookahead_pass ? "pass" : "blocked"}</small>
          </div>
          <div className="metric-card">
            <span className="metric-label">v12 Input Contract</span>
            <strong>{featureStoreV12InputContract?.status || featureStoreV12?.v12_input_contract_status || "blocked"}</strong>
            <small>input_contract_ready: {featureStoreV12InputContract?.input_contract_ready || featureStoreV12?.v12_input_contract_ready ? "true" : "false"}</small>
          </div>
          <div className="metric-card">
            <span className="metric-label">missing_required_fields</span>
            <strong>{featureStoreV12InputContract?.missing_required_fields?.length || 0}</strong>
            <small>{(featureStoreV12InputContract?.missing_required_fields || []).slice(0, 4).join(", ") || "none"}</small>
          </div>
          <div className="metric-card">
            <span className="metric-label">missing_timestamp_fields</span>
            <strong>{featureStoreV12InputContract?.missing_timestamp_fields?.length || 0}</strong>
            <small>{(featureStoreV12InputContract?.missing_timestamp_fields || []).slice(0, 4).join(", ") || "none"}</small>
          </div>
          <div className="metric-card">
            <span className="metric-label">coverage diff</span>
            <strong>{String(featureStoreV12InputContract?.coverage_diff?.row_count ?? 0)}</strong>
            <small>feature_store_v12_build_allowed: {featureStoreV12InputContract?.feature_store_v12_build_allowed ? "true" : "false"}</small>
          </div>
          <div className="metric-card">
            <span className="metric-label">v12 Build Dry-Run Plan</span>
            <strong>{featureStoreV12BuildPlan?.status || "blocked"}</strong>
            <small>feature_store_v12_build_executed: {featureStoreV12BuildPlan?.feature_store_v12_build_executed ? "true" : "false"}</small>
          </div>
          <div className="metric-card">
            <span className="metric-label">expected_feature_store_path</span>
            <strong>{featureStoreV12BuildPlan?.expected_row_count ?? 0}</strong>
            <small>{featureStoreV12BuildPlan?.expected_feature_store_path || "not planned"}</small>
          </div>
          <div className="metric-card">
            <span className="metric-label">expected_manifest_path</span>
            <strong>{featureStoreV12BuildPlan?.expected_fields?.length || 0}</strong>
            <small>{featureStoreV12BuildPlan?.expected_manifest_path || "not planned"}</small>
          </div>
          <div className="metric-card">
            <span className="metric-label">resource_budget</span>
            <strong>{String(featureStoreV12BuildPlan?.resource_budget?.max_runtime_seconds ?? 0)}s</strong>
            <small>max rows {String(featureStoreV12BuildPlan?.resource_budget?.max_output_rows ?? 0)}</small>
          </div>
          <div className="metric-card">
            <span className="metric-label">forbidden_side_effects</span>
            <strong>{featureStoreV12BuildPlan?.forbidden_side_effects?.length || 0}</strong>
            <small>{(featureStoreV12BuildPlan?.forbidden_side_effects || []).slice(0, 3).join(", ") || "build/train/active/prediction forbidden"}</small>
          </div>
          <div className="metric-card">
            <span className="metric-label">v12 Controlled Build Executor</span>
            <strong>{featureStoreV12ControlledBuild?.status || "blocked"}</strong>
            <small>build_executed: {featureStoreV12ControlledBuild?.build_executed ? "true" : "false"}</small>
          </div>
          <div className="metric-card">
            <span className="metric-label">feature_store_v12_path</span>
            <strong>{featureStoreV12ControlledBuild?.row_count ?? 0}</strong>
            <small>{featureStoreV12ControlledBuild?.feature_store_v12_path || "not executed"}</small>
          </div>
          <div className="metric-card">
            <span className="metric-label">artifact_boundary_checks</span>
            <strong>{featureStoreV12ControlledBuild?.artifact_boundary_checks?.status || "blocked"}</strong>
            <small>{(featureStoreV12ControlledBuild?.blocking_reasons || ["does not trigger TD v12 or candidate"]).slice(0, 3).join(", ")}</small>
          </div>
          <div className="metric-card">
            <span className="metric-label">training dataset v12</span>
            <strong>{featureStoreV12?.training_dataset_v12_allowed ? "allowed" : "blocked"}</strong>
            <small>{(featureStoreV12?.blocking_reasons || ["health/audit/fields gate not passed"]).slice(0, 3).join(", ")}</small>
          </div>
        </div>
        <div className="notice-card">
          <strong>沪锡仓单策略</strong>
          <p>{featureStoreV7?.warehouse_missing_policy?.message_zh || "当前无真实沪锡仓单数据，系统未伪造字段；模型将使用缺失风险标记。"}</p>
          <p>risk features: {(featureStoreV7?.warehouse_policy_features || ["inventory_missing_flag", "warehouse_data_quality_score"]).join(", ")}</p>
        </div>
        <div className="button-row">
          <button type="button" className="primary-button" onClick={buildStore} disabled={featureStoreBuilding}>
            {featureStoreBuilding ? "正在构建..." : "一键构建 Feature Store"}
          </button>
          <button type="button" className="secondary-button" onClick={() => void Promise.all([refreshFeatureStore(), refreshFeatureStoreV4(), refreshFeatureStoreV5(), refreshFeatureStoreV6(), refreshFeatureStoreV7()])}>
            刷新状态
          </button>
          <button type="button" className="secondary-button" onClick={runManagedProxyV11} disabled={featureStoreBuilding}>
            刷新 managed proxy v11
          </button>
          <button type="button" className="secondary-button" onClick={refreshV12BuildPlan} disabled={featureStoreV12BuildPlanRefreshing}>
            {featureStoreV12BuildPlanRefreshing ? "刷新 dry-run plan..." : "刷新 v12 build dry-run plan"}
          </button>
          <button type="button" className="secondary-button" onClick={runV12ControlledBuild} disabled={featureStoreV12ControlledBuildRunning}>
            {featureStoreV12ControlledBuildRunning ? "运行 controlled executor..." : "运行 v12 controlled build"}
          </button>
          <span className="status-pill status-info">不生成预测</span>
        </div>
        {featureStoreError ? <p className="error-text">{featureStoreError}</p> : null}
        {featureStoreActionError ? <p className="error-text">{featureStoreActionError}</p> : null}
        <div className="notice-card">
          <strong>对齐规则</strong>
          <p>market history 为主 index；cross-market 最多 forward-fill 5 个交易日；event factor 只按 trade_date 精确对齐。</p>
          <strong>字段来源</strong>
          <p>{Object.keys(featureStore?.field_sources || {}).slice(0, 12).join("、") || "构建后显示字段来源"}</p>
        </div>
      </SectionCard>
      <SectionCard
        title="candidate_v6 数据准入"
        subtitle="只检查真实字段覆盖、样例/模拟数据和 no-lookahead，不训练模型、不发布 active、不生成客户预测。"
        actions={<button type="button" className="secondary-button" onClick={() => void refreshCandidateV6Readiness()}>刷新准入</button>}
      >
        {candidateV6ReadinessLoading ? (
          <LoadingState label="正在检查 candidate_v6 数据准入..." />
        ) : candidateV6ReadinessError ? (
          <ErrorState title="candidate_v6 准入暂时无法加载" message={candidateV6ReadinessError} actionLabel="重新加载" onAction={refreshCandidateV6Readiness} />
        ) : (
          <div className="page-stack">
            <div className="metric-grid compact">
              <div className="metric-card">
                <span className="metric-label">readiness</span>
                <strong>{candidateV6Readiness?.status || "blocked"}</strong>
                <small>{candidateV6Readiness?.ready ? "真实增量字段已达准入" : "等待真实增量字段达标"}</small>
              </div>
              <div className="metric-card">
                <span className="metric-label">新增字段组</span>
                <strong>{candidateV6Readiness?.new_factor_groups?.length || 0}</strong>
                <small>{(candidateV6Readiness?.new_factor_groups || []).join("、") || "暂无"}</small>
              </div>
              <div className="metric-card">
                <span className="metric-label">新增字段</span>
                <strong>{candidateV6Readiness?.new_fields?.length || 0}</strong>
                <small>{(candidateV6Readiness?.new_fields || []).slice(0, 5).join("、") || "暂无"}</small>
              </div>
              <div className="metric-card">
                <span className="metric-label">no-lookahead</span>
                <strong>{candidateV6Readiness?.no_lookahead_pass ? "pass" : "blocked"}</strong>
                <small>{candidateV6Readiness?.feature_store_leakage_check_pass ? "feature leakage pass" : "等待 Feature Store v5"}</small>
              </div>
            </div>
            <div className="notice-card">
              <strong>缺失字段</strong>
              <p>{(candidateV6Readiness?.missing_fields || []).slice(0, 20).join("、") || "暂无"}</p>
              <strong>阻断原因</strong>
              <p>{(candidateV6Readiness?.blocked_reasons || []).join("、") || "暂无"}</p>
              <strong>下一步</strong>
              <p>{(candidateV6Readiness?.next_actions_zh || []).join("；") || "刷新 Tushare / Managed Proxy 后重建 Feature Store v5。"}</p>
              <span className="status-pill status-info">本接口不训练 candidate_v6</span>
            </div>
          </div>
        )}
      </SectionCard>
      <SectionCard title="SHFE / 库存 / 仓单 / 基差覆盖率" subtitle="展示真实底层数据覆盖情况；不伪造库存、仓单、基差或现货价格。">
        <div className="factor-group-grid">
          <div className="factor-group">
            <strong>SHFE 官网直连</strong>
            <span>若显示 blocked_by_waf，表示官网直连被人机验证阻断；系统会改用 AKShare/缓存辅助源，不影响主行情。</span>
          </div>
          <div className="factor-group">
            <strong>库存 / 仓单</strong>
            <span>只使用真实 SHFE 锡库存和注册仓单；无锡数据时保持不可用，不用其它品种替代。</span>
          </div>
          <div className="factor-group">
            <strong>现货 / 基差</strong>
            <span>依赖真实现货锡价格、升贴水和期货收盘；缺字段时 basis 因子继续标记为不可用。</span>
          </div>
          <div className="factor-group">
            <strong>交易所日线 / 持仓</strong>
            <span>用于补齐成交量、持仓量和辅助覆盖率；不会生成预测或 active 模型。</span>
          </div>
        </div>
      </SectionCard>
      <SectionCard title="Tushare 字段覆盖" subtitle="Tushare Pro 可补齐低成本期货基础数据；只有真实 SN 行会进入因子覆盖率。">
        <div className="factor-group-grid">
          <div className="factor-group">
            <strong>open_interest</strong>
            <span>来自 sn_tushare_daily.json，可改善 raw_market 和换月/持仓相关研究字段。</span>
          </div>
          <div className="factor-group">
            <strong>warehouse_receipt</strong>
            <span>来自 sn_tushare_warehouse_receipt.json，用于仓单变化覆盖；不等同于库存，不伪造 inventory。</span>
          </div>
          <div className="factor-group">
            <strong>settlement</strong>
            <span>来自 sn_tushare_settlement.json，用于结算价、保证金和手续费参数研究。</span>
          </div>
          <div className="factor-group">
            <strong>holding</strong>
            <span>来自 sn_tushare_holding.json，可生成 member_net_position 等持仓排名研究字段。</span>
          </div>
        </div>
      </SectionCard>
      <SectionCard title="managed 字段覆盖" subtitle="发行方托管数据服务可补齐公开源不稳定的现货、基差、库存、LME 和期限结构字段。">
        <div className="reason-list">
          <span>Feature Store v10 readiness: {featureStoreV10?.feature_store_v10_readiness?.status || "blocked"}.</span>
          <span>Feature Store v11 readiness: {featureStoreV11?.feature_store_v11_readiness?.status || "blocked"}.</span>
          <span>spot_futures_basis / spot_price / spot_premium：用于 basis 因子。</span>
          <span>shfe_inventory / shfe_warehouse_receipt / lme_inventory：用于库存和仓单因子。</span>
          <span>lme_tin_close：用于 LME tin return 和内外盘价差。</span>
          <span>near_contract_close / far_contract_close / near_open_interest / far_open_interest：用于 term structure。</span>
        </div>
        <p className="muted">managed proxy 只接收结构化真实字段；无数据时显示排除原因，不生成 fake factor。no_fake_data.</p>
      </SectionCard>
      <SectionCard title="自动在线因子准备度" subtitle="客户不需要上传 CSV/Excel；系统审计在线源、API key 源和托管源能否补齐机构级字段。">
        {onlineReadinessLoading ? (
          <LoadingState label="正在审计自动在线字段可用性..." />
        ) : onlineReadinessError ? (
          <ErrorState title="自动在线因子准备度暂时无法加载" message={onlineReadinessError} actionLabel="重新加载" onAction={refreshOnlineReadiness} />
        ) : (
          <div className="page-stack">
            <div className="metric-grid compact">
              <div className="metric-card">
                <span className="metric-label">客户上传文件</span>
                <strong>{onlineReadiness?.client_upload_required ? "需要" : "不需要"}</strong>
                <small>无需手工上传文件</small>
              </div>
              <div className="metric-card">
                <span className="metric-label">自动在线可用字段</span>
                <strong>{onlineReadiness?.available_fields?.length || 0}</strong>
                <small>{(onlineReadiness?.available_fields || []).slice(0, 4).join("、") || "暂无"}</small>
              </div>
              <div className="metric-card">
                <span className="metric-label">仍不可用字段</span>
                <strong>{onlineReadiness?.unavailable_fields?.length || 0}</strong>
                <small>公开源不可用时不伪造数据</small>
              </div>
              <div className="metric-card">
                <span className="metric-label">研究范围</span>
                <strong>{onlineReadiness?.research_readiness?.can_train_online_cross_market_model ? "可加入跨市场" : "技术/Regime 优先"}</strong>
                <small>{onlineReadiness?.research_readiness?.reason_zh || "等待在线准备度报告"}</small>
              </div>
            </div>
            <div className="notice-card">
              <strong>当前可继续研究</strong>
              <p>{onlineReadiness?.research_priority?.can_continue_research?.join("；") || "请先刷新真实行情和在线数据源。"}</p>
              <strong>当前不建议研究</strong>
              <p>{onlineReadiness?.research_priority?.not_recommended_now?.join("；") || "暂无"}</p>
              <span className="status-pill status-warning">公开在线源当前无法提供的字段，系统不会伪造数据。</span>
            </div>
            <DataTable
              data={(onlineReadiness?.field_readiness || []) as Array<OnlineFieldReadiness & Record<string, unknown>>}
              columns={[
                { key: "field", title: "字段", render: (row) => formatNullable(row.field) },
                { key: "category", title: "类别", render: (row) => formatNullable(row.category) },
                { key: "source", title: "来源", render: (row) => formatNullable(row.source) },
                { key: "status", title: "状态", render: (row) => formatNullable(row.status) },
                { key: "non_null_rate", title: "非空率", render: (row) => `${formatNumber(Number(row.non_null_rate || 0) * 100, 1)}%` },
                { key: "message_zh", title: "说明", render: (row) => formatNullable(row.message_zh) },
              ]}
            />
          </div>
        )}
      </SectionCard>
      <SectionCard title="机构级因子覆盖率" subtitle="基于真实行情与已接入底层数据审计，不训练模型、不生成预测。">
        <div className="factor-group-grid">
          <div className="factor-group"><strong>基差因子状态</strong><span>依赖真实现货锡价格、升贴水和主力期货收盘。</span></div>
          <div className="factor-group"><strong>库存/仓单因子状态</strong><span>依赖 SHFE 库存、注册仓单和 LME 锡库存。</span></div>
          <div className="factor-group"><strong>外盘/汇率因子状态</strong><span>依赖 LME 锡、USD/CNY、DXY、US10Y。</span></div>
          <div className="factor-group"><strong>新闻相关性状态</strong><span>低相关新闻不会进入事件因子，入模由 relevance gate 控制。</span></div>
        </div>
      </SectionCard>
      <SectionCard title="真实因子覆盖率" subtitle="只审计真实行情和可用底层字段，不训练模型、不生成预测、不生成回测。">
        {coverageLoading ? (
          <LoadingState label="正在审计真实因子覆盖率..." />
        ) : coverageError ? (
          <ErrorState title="真实因子覆盖率暂时无法加载" message={coverageError} actionLabel="重新加载" onAction={refreshCoverage} />
        ) : coverageGroups.length ? (
          <div className="page-stack">
            <div className="metric-grid compact">
              <div className="metric-card">
                <span className="metric-label">样本数</span>
                <strong>{coverage?.sample_count ?? "数据暂缺"}</strong>
                <small>
                  {formatNullable(coverage?.date_start)} 至 {formatNullable(coverage?.date_end)}
                </small>
              </div>
              <div className="metric-card">
                <span className="metric-label">可训练因子</span>
                <strong>{usableCount}</strong>
                <small>覆盖率达到训练阈值</small>
              </div>
              <div className="metric-card">
                <span className="metric-label">部分可用</span>
                <strong>{partialCount}</strong>
                <small>需要补齐或延长样本</small>
              </div>
              <div className="metric-card">
                <span className="metric-label">不可用因子</span>
                <strong>{missingCount}</strong>
                <small>缺底层字段或全空</small>
              </div>
            </div>

            <div className="notice-card">
              <strong>训练准备度</strong>
              <p>{coverage?.training_readiness?.reason_zh || "数据暂缺"}</p>
              <span className="status-pill status-info">
                OHLCV 技术模型：{coverage?.training_readiness?.can_train_ohlcv_model ? "具备基础条件" : "暂不具备"}
              </span>
              <span className="status-pill status-warning">
                完整基本面模型：{coverage?.training_readiness?.can_train_full_fundamental_model ? "具备条件" : "暂不具备"}
              </span>
            </div>

            <div className="notice-card">
              <strong>cross_market_diagnostics</strong>
              <p>
                日期范围：{formatNullable(coverage?.cross_market_diagnostics?.date_start)} 至{" "}
                {formatNullable(coverage?.cross_market_diagnostics?.date_end)}；交集：
                {coverage?.cross_market_diagnostics?.exact_date_overlap_count ?? 0}；对齐非空：
                {coverage?.cross_market_diagnostics?.aligned_non_null_count ?? 0}；stale：
                {coverage?.cross_market_diagnostics?.stale_row_count ?? 0}。
              </p>
              <p>
                from_cache / stale 状态会在 rate_limited 或 using_cache_rate_limited 时解释字段是否来自最近成功缓存；排除原因：
                {(coverage?.cross_market_diagnostics?.blocking_reasons || []).join("、") || "暂无"}。
              </p>
            </div>

            {coverage?.blocking_missing_fields?.length ? (
              <div className="notice-card warning">
                <strong>缺失底层字段</strong>
                <p>{coverage.blocking_missing_fields.join("、")}</p>
              </div>
            ) : null}

            <DataTable
              data={coverageGroups.map((group) => ({
                group: group.group,
                feature_count: group.feature_count,
                available_feature_count: group.available_feature_count,
                partial_feature_count: group.partial_feature_count,
                missing_feature_count: group.missing_feature_count,
                coverage_rate: group.coverage_rate,
              }))}
              columns={[
                { key: "group", title: "因子组", render: (row) => formatNullable(row.group) },
                { key: "feature_count", title: "因子数", render: (row) => formatNumber(row.feature_count, 0) },
                { key: "available_feature_count", title: "可训练", render: (row) => formatNumber(row.available_feature_count, 0) },
                { key: "partial_feature_count", title: "部分可用", render: (row) => formatNumber(row.partial_feature_count, 0) },
                { key: "missing_feature_count", title: "不可用", render: (row) => formatNumber(row.missing_feature_count, 0) },
                { key: "coverage_rate", title: "覆盖率", render: (row) => `${formatNumber(Number(row.coverage_rate || 0) * 100, 1)}%` },
              ]}
            />

            {coverageGroups.map((group) => (
              <SectionCard
                key={group.group || "coverage-group"}
                title={`${formatNullable(group.group, "因子组")} 明细`}
                subtitle="可训练/部分可用/不可用按真实非空覆盖率与底层字段判断。"
              >
                <DataTable
                  data={(group.features || []) as Array<FeatureCoverageFeature & Record<string, unknown>>}
                  columns={[
                    { key: "name", title: "因子", render: (row) => formatNullable(row.name) },
                    { key: "availability", title: "状态", render: (row) => availabilityLabel(row) },
                    { key: "non_null_rate", title: "非空率", render: (row) => `${formatNumber(Number(row.non_null_rate || 0) * 100, 1)}%` },
                    { key: "latest_value", title: "最新值", render: (row) => formatNullable(row.latest_value) },
                    { key: "missing_reason", title: "缺失原因", render: (row) => formatNullable(row.missing_reason, "无") },
                  ]}
                />
              </SectionCard>
            ))}
          </div>
        ) : (
          <EmptyState label={coverage?.message_zh || "暂无真实因子覆盖率数据，请先刷新真实行情。"} />
        )}
      </SectionCard>

      <SectionCard title="因子诊断" subtitle="读取 /api/terminal/factors/diagnostics；无诊断产物时给出刷新引导，不显示伪指标。">
        {groups.length ? (
          <div className="page-stack">
            {groups.map((group) => (
              <SectionCard key={group.group || "factor-group"} title={formatNullable(group.group, "因子分组")} subtitle="因子值、IC 和方向提示来自运行期诊断产物。">
                <DataTable
                  data={(group.features || []) as Array<FactorDiagnosticFeature & Record<string, unknown>>}
                  columns={[
                    { key: "name", title: "因子", render: (row) => formatNullable(row.name) },
                    { key: "value", title: "当前值", render: (row) => formatNumber(row.value, 4) },
                    { key: "ic", title: "IC", render: (row) => formatNumber(row.ic, 4) },
                    { key: "missing", title: "缺失", render: (row) => (row.missing ? "是" : "否") },
                    { key: "direction_hint", title: "方向提示", render: (row) => formatNullable(row.direction_hint, "待验证") },
                  ]}
                />
              </SectionCard>
            ))}
          </div>
        ) : (
          <div className="empty-action-panel">
            <EmptyState label={data?.message_zh || "暂无完整因子诊断数据，请先运行一键刷新数据。"} />
            <div className="factor-group-grid">
              {fallbackGroups.map((group) => (
                <div className="factor-group" key={group}>
                  <strong>{group}</strong>
                  <span>等待因子诊断产物接入。</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </SectionCard>
      <FactorBarChart />
    </div>
  );
}
