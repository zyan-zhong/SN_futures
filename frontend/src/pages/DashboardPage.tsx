import { useCallback } from "react";
import { getPriceHistory } from "../api/terminal";
import type { PriceHistoryPayload, TerminalSnapshot } from "../api/types";
import { PriceChart } from "../components/charts/PriceChart";
import { EmptyState } from "../components/common/EmptyState";
import { ErrorBoundary } from "../components/common/ErrorBoundary";
import { StatusPill } from "../components/common/StatusPill";
import { DataSourceStatusPanel } from "../components/data/DataSourceStatusPanel";
import { RefreshTaskPanel } from "../components/data/RefreshTaskPanel";
import { SystemStatusBanner } from "../components/dashboard/SystemStatusBanner";
import { SectionCard } from "../components/layout/SectionCard";
import { LearningStatusPanel } from "../components/model/LearningStatusPanel";
import { ModelHealthPanel } from "../components/model/ModelHealthPanel";
import { PredictionGrid } from "../components/prediction/PredictionGrid";
import { usePolling } from "../hooks/usePolling";
import { formatDateTime, formatNullable, formatPercent, formatPrice, formatSignal } from "../utils/format";
import { isDegraded, isLowQuality, isObserveSignal } from "../utils/guards";

function missingFieldsSummary(snapshot?: TerminalSnapshot | null): string {
  const sources = snapshot?.data_status?.sources || [];
  const missing = sources.filter((source) => !source.enabled || !source.success).map((source) => source.source_name || "数据源");
  if (!missing.length) return "关键字段未发现明显缺失";
  return missing.slice(0, 3).join("、");
}

function dataSourceSummary(snapshot?: TerminalSnapshot | null): string {
  const sources = snapshot?.data_status?.sources || [];
  if (!sources.length) return "数据源状态暂缺";
  const ok = sources.filter((source) => source.success).length;
  return `${ok}/${sources.length} 个数据源可用`;
}

export function DashboardPage({
  snapshot,
  onRefresh,
  showSampleData = true
}: {
  snapshot?: TerminalSnapshot | null;
  onRefresh?: () => void;
  showSampleData?: boolean;
}) {
  const priceHistoryLoader = useCallback(() => getPriceHistory(), []);
  const { data: priceHistory, refresh: refreshPriceHistory } = usePolling<PriceHistoryPayload>(priceHistoryLoader, 60000);
  const summary = snapshot?.summary;
  const predictions = snapshot?.predictions || [];
  const visiblePriceHistory = priceHistory?.sample_mode && !showSampleData ? { ...priceHistory, points: [] } : priceHistory;
  const signal = formatSignal(summary?.current_signal);
  const degraded = isDegraded(summary?.model_status) || Boolean(snapshot?.model_health?.degradation_status?.includes("降级"));
  const lowQuality = isLowQuality(summary?.data_quality_score);
  const noTradePoints = isObserveSignal(signal) || degraded || lowQuality;
  const modelStatus = degraded ? "degraded：已降级" : formatNullable(summary?.model_status, "模型待验证");
  const promotion = formatNullable(snapshot?.model_health?.promotion_status, "晋级状态暂缺");
  const riskText = lowQuality ? "数据不足" : formatNullable(summary?.risk_level, "数据不足");

  return (
    <div className="page-stack">
      <ErrorBoundary moduleName="系统状态横幅">
        <SystemStatusBanner snapshot={snapshot} />
      </ErrorBoundary>
      <ErrorBoundary moduleName="数据刷新任务中心">
        <RefreshTaskPanel
          initialStatus={snapshot?.refresh_status}
          onAfterRefresh={() => {
            onRefresh?.();
            void refreshPriceHistory();
          }}
        />
      </ErrorBoundary>

      <ErrorBoundary moduleName="总览大盘">
        <SectionCard title="总览大盘" subtitle="客户级状态摘要：系统、行情、数据、模型、信号与风险一屏可读">
          <div className="metric-grid dashboard-core-grid">
            <div className="metric-card core-status-card">
              <div className="metric-label">系统状态</div>
              <div className="metric-value">{degraded ? "降级" : lowQuality ? "数据不足" : "正常"}</div>
              <StatusPill label={summary?.system_status || "系统运行中"} tone={degraded || lowQuality ? "warn" : "good"} />
            </div>

            <div className="metric-card core-status-card">
              <div className="metric-label">主合约与最新价格</div>
              <div className="metric-value">{formatNullable(summary?.main_contract, "SN")} · {formatPrice(summary?.latest_price)}</div>
              <span className="muted">涨跌：{formatPercent(summary?.price_change_pct)}；更新时间：{formatDateTime(summary?.last_update_time)}</span>
            </div>

            <div className="metric-card core-status-card">
              <div className="metric-label">数据质量</div>
              <div className="metric-value">{formatPercent(summary?.data_quality_score)}</div>
              <span className="muted">缺失摘要：{missingFieldsSummary(snapshot)}</span>
              <StatusPill label={dataSourceSummary(snapshot)} tone={lowQuality ? "warn" : "info"} />
            </div>

            <div className="metric-card core-status-card">
              <div className="metric-label">当前研究信号</div>
              <div className="metric-value">{signal}</div>
              <span className="muted">{noTradePoints ? "暂无交易点位" : "存在研究观察点位"}</span>
            </div>

            <div className="metric-card core-status-card">
              <div className="metric-label">模型状态</div>
              <div className="metric-value">{modelStatus}</div>
              <StatusPill label={`Promotion Gate：${promotion}`} tone={degraded ? "warn" : "info"} />
            </div>

            <div className="metric-card core-status-card">
              <div className="metric-label">风险状态</div>
              <div className="metric-value">{riskText}</div>
              <span className="muted">仅供投研参考，不构成投资建议。</span>
            </div>
          </div>
        </SectionCard>
      </ErrorBoundary>

      <ErrorBoundary moduleName="七周期预测摘要">
        <SectionCard title="七周期预测摘要" subtitle="各周期独立模型输出；观望、降级或低数据质量时不展示交易点位">
          {predictions.length ? (
            <PredictionGrid predictions={predictions.slice(0, 7)} />
          ) : (
            <EmptyState label="暂无可用预测结果。请检查数据源配置、模型状态或运行预测任务。" />
          )}
        </SectionCard>
      </ErrorBoundary>

      <ErrorBoundary moduleName="预测区间概览">
        <SectionCard title="预测区间概览" subtitle="用于快速观察不同周期中枢与上下界；完整时间路径以后端图表接口为准">
          <PriceChart predictions={predictions} priceHistory={visiblePriceHistory} />
        </SectionCard>
      </ErrorBoundary>

      <ErrorBoundary moduleName="模型健康与学习状态">
        <div className="two-column">
          <ModelHealthPanel health={snapshot?.model_health} />
          <LearningStatusPanel status={snapshot?.learning_status} />
        </div>
      </ErrorBoundary>
      <ErrorBoundary moduleName="数据源状态">
        <DataSourceStatusPanel sources={snapshot?.data_status?.sources} />
      </ErrorBoundary>
    </div>
  );
}
