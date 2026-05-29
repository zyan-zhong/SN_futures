import { useCallback, useState } from "react";
import { buildFeatureStore, getFactorDiagnostics, getFeatureCoverage, getFeatureStoreStatus, getOnlineFeatureReadiness } from "../api/terminal";
import type {
  FactorDiagnosticFeature,
  FactorDiagnosticsPayload,
  FeatureCoverageFeature,
  FeatureCoveragePayload,
  FeatureStoreStatus,
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
  const featureStoreLoader = useCallback(() => getFeatureStoreStatus("v3"), []);
  const [featureStoreBuilding, setFeatureStoreBuilding] = useState(false);
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
    data: featureStore,
    error: featureStoreError,
    loading: featureStoreLoading,
    refresh: refreshFeatureStore,
  } = usePolling<FeatureStoreStatus>(featureStoreLoader, 60000);
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
      await Promise.all([refreshFeatureStore(), refreshCoverage(), refreshOnlineReadiness()]);
    } catch (err) {
      setFeatureStoreActionError(err instanceof Error ? err.message : "Feature Store v3 构建失败");
    } finally {
      setFeatureStoreBuilding(false);
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
        <div className="button-row">
          <button type="button" className="primary-button" onClick={buildStore} disabled={featureStoreBuilding}>
            {featureStoreBuilding ? "正在构建..." : "一键构建 Feature Store"}
          </button>
          <button type="button" className="secondary-button" onClick={refreshFeatureStore}>
            刷新状态
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
      <SectionCard title="自动在线因子准备度" subtitle="审计公开在线源、API key 源和托管源能否补齐机构级字段；客户不需要上传 CSV/Excel。">
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
                <small>客户不需要上传 CSV/Excel</small>
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
