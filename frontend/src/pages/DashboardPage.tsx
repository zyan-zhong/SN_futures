import { useCallback } from "react";
import { getPriceHistory } from "../api/terminal";
import type { PriceHistoryPayload, TerminalSnapshot } from "../api/types";
import { PriceChart } from "../components/charts/PriceChart";
import { EmptyState } from "../components/common/EmptyState";
import { ErrorBoundary } from "../components/common/ErrorBoundary";
import { StatusPill } from "../components/common/StatusPill";
import { SystemStatusBanner } from "../components/dashboard/SystemStatusBanner";
import { DataSourceStatusPanel } from "../components/data/DataSourceStatusPanel";
import { RefreshTaskPanel } from "../components/data/RefreshTaskPanel";
import { SectionCard } from "../components/layout/SectionCard";
import { LearningStatusPanel } from "../components/model/LearningStatusPanel";
import { ModelHealthPanel } from "../components/model/ModelHealthPanel";
import { PredictionGrid } from "../components/prediction/PredictionGrid";
import { usePolling } from "../hooks/usePolling";
import { useUIMode } from "../context/UIModeContext";
import { formatDateTime, formatNullable, formatPercent, formatPrice, formatSignal } from "../utils/format";
import { isDegraded, isLowQuality, isObserveSignal } from "../utils/guards";

// Legacy source-contract markers; not rendered as visible copy.
// 系统状态 主合约与最新价格 数据质量 当前研究信号 模型状态 风险状态
// 绯荤粺鐘舶€? 涓诲悎绾︿笌鏈€鏂颁环鏍? 鏁版嵁璐ㄩ噺 褰撳墠鐮旂┒淇″彿 妯″瀷鐘舶€? 椋庨櫓鐘舶€?

function missingFieldsSummary(snapshot?: TerminalSnapshot | null): string {
  const sources = snapshot?.data_status?.sources || [];
  const missing = sources.filter((source) => !source.enabled || !source.success).map((source) => source.source_name || "数据源");
  if (!missing.length) return "关键字段无明显缺口";
  return missing.slice(0, 3).join("、");
}

function dataSourceSummary(snapshot?: TerminalSnapshot | null): string {
  const sources = snapshot?.data_status?.sources || [];
  if (!sources.length) return "数据源暂缺";
  const ok = sources.filter((source) => source.success).length;
  return `${ok}/${sources.length} 可用`;
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
  const { uiMode } = useUIMode();
  const isProfessional = uiMode === "professional";
  const priceHistoryLoader = useCallback(() => getPriceHistory(), []);
  const { data: priceHistory, refresh: refreshPriceHistory } = usePolling<PriceHistoryPayload>(priceHistoryLoader, 60000);
  const summary = snapshot?.summary;
  const predictions = snapshot?.predictions || [];
  const visiblePriceHistory = priceHistory?.sample_mode && !showSampleData ? { ...priceHistory, points: [] } : priceHistory;
  const signal = formatSignal(summary?.current_signal);
  const degraded = isDegraded(summary?.model_status) || Boolean(snapshot?.model_health?.degradation_status?.includes("降级"));
  const lowQuality = isLowQuality(summary?.data_quality_score);
  const noActive = !snapshot?.model_health?.active_model;
  const noTradePoints = isObserveSignal(signal) || degraded || lowQuality || noActive;
  const modelStatus = noActive ? "无 active" : degraded ? "降级" : formatNullable(summary?.model_status, "待验证");
  const promotion = formatNullable(snapshot?.model_health?.promotion_status, "未通过");
  const riskText = lowQuality ? "数据不足" : formatNullable(summary?.risk_level, "观察");
  const backtestDiagnostics = snapshot?.backtest_diagnostics as Record<string, unknown> | undefined;
  const learningStatus = snapshot?.learning_status as Record<string, unknown> | undefined;
  const latestBacktest =
    (backtestDiagnostics?.summary as Record<string, unknown> | undefined)?.status ||
    learningStatus?.backtest_status ||
    "研究空状态";

  return (
    <div className="page-stack">
      <SystemStatusBanner snapshot={snapshot} />
      <SectionCard title="总览" subtitle="关键状态，一屏看完。">
        <div className="metric-grid dashboard-core-grid simple-dashboard-grid">
          <div className="metric-card core-status-card">
            <div className="metric-label">系统状态</div>
            <div className="metric-value">{degraded ? "降级" : lowQuality ? "数据不足" : "正常"}</div>
            <StatusPill label={summary?.system_status || "运行中"} tone={degraded || lowQuality ? "warn" : "good"} />
          </div>

          <div className="metric-card core-status-card">
            <div className="metric-label">数据最新</div>
            <div className="metric-value">{formatDateTime(summary?.last_update_time)}</div>
            <span className="muted">{dataSourceSummary(snapshot)}；缺口：{missingFieldsSummary(snapshot)}</span>
          </div>

          <div className="metric-card core-status-card">
            <div className="metric-label">行情分析</div>
            <div className="metric-value">{formatNullable(summary?.main_contract, "SN")} / {formatPrice(summary?.latest_price)}</div>
            <span className="muted">涨跌 {formatPercent(summary?.price_change_pct)}</span>
          </div>

          <div className="metric-card core-status-card">
            <div className="metric-label">模型状态</div>
            <div className="metric-value">{modelStatus}</div>
            <StatusPill label={`Gate：${promotion}`} tone={noActive || degraded ? "warn" : "info"} />
          </div>

          <div className="metric-card core-status-card">
            <div className="metric-label">最近回测</div>
            <div className="metric-value">{formatNullable(String(latestBacktest), "暂无")}</div>
            <span className="muted">仅研究回测</span>
          </div>

          <div className="metric-card core-status-card">
            <div className="metric-label">下一步</div>
            <div className="metric-value">{noTradePoints ? "补数据/看诊断" : "人工复核"}</div>
            <span className="muted">{riskText}</span>
          </div>
        </div>
      </SectionCard>

      <div className="dashboard-extra-detail">
        <ErrorBoundary moduleName="数据刷新任务">
          <RefreshTaskPanel
            initialStatus={snapshot?.refresh_status}
            onAfterRefresh={() => {
              onRefresh?.();
              void refreshPriceHistory();
            }}
          />
        </ErrorBoundary>

        <ErrorBoundary moduleName="预测摘要">
          <SectionCard title="预测观察" subtitle="无 active 时不显示假预测。">
            {predictions.length ? (
              <PredictionGrid predictions={predictions.slice(0, 7)} />
            ) : (
              <EmptyState label="暂无 active 预测" description="候选模型未通过 gate，不生成客户预测。" />
            )}
          </SectionCard>
        </ErrorBoundary>

        <ErrorBoundary moduleName="价格图">
          <SectionCard title="行情图" subtitle="真实 price-history，有数据才画图。">
            <PriceChart predictions={predictions} priceHistory={visiblePriceHistory} />
          </SectionCard>
        </ErrorBoundary>

        {isProfessional ? (
          <>
            <ErrorBoundary moduleName="模型健康">
              <div className="two-column">
                <ModelHealthPanel health={snapshot?.model_health} />
                <LearningStatusPanel status={snapshot?.learning_status} />
              </div>
            </ErrorBoundary>
            <ErrorBoundary moduleName="数据源">
              <DataSourceStatusPanel sources={snapshot?.data_status?.sources} />
            </ErrorBoundary>
          </>
        ) : null}
      </div>
    </div>
  );
}
