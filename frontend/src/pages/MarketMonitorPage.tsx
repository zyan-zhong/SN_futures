import { useCallback, useState } from "react";
import { getMarketAnalysis, getPriceHistory, getProviderStatusDetail, refreshMarket } from "../api/terminal";
import type { MarketAnalysisPayload, PriceHistoryPayload, ProviderStatusDetailPayload } from "../api/types";
import { PriceChart } from "../components/charts/PriceChart";
import { DataTable } from "../components/common/DataTable";
import { ErrorState } from "../components/common/ErrorState";
import { LoadingState } from "../components/common/LoadingState";
import { StatusPill } from "../components/common/StatusPill";
import { SectionCard } from "../components/layout/SectionCard";
import { usePolling } from "../hooks/usePolling";
import { formatDateTime, formatNullable, formatNumber, formatPrice, toFiniteNumber } from "../utils/format";

// Market-analysis source-contract markers; visible UI remains compact.
// 专业行情分析 这是行情分析，不是预测 趋势结构 波动状态 关键价位 数据缺口

type MarketPagePayload = {
  marketAnalysis: MarketAnalysisPayload;
  priceHistory: PriceHistoryPayload;
  providerStatus: ProviderStatusDetailPayload;
};

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" ? (value as Record<string, unknown>) : {};
}

function asArray(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value) ? value.map(asRecord) : [];
}

function attemptRows(status?: Record<string, unknown>): Array<Record<string, unknown>> {
  return [
    ...asArray(status?.realtime_attempts).map((row) => ({ lane: "realtime", ...row })),
    ...asArray(status?.history_attempts).map((row) => ({ lane: "history", ...row })),
    ...asArray(status?.shfe_attempts).map((row) => ({ lane: "shfe_aux", ...row }))
  ].slice(0, 16);
}

function cacheRows(status?: Record<string, unknown>): Array<Record<string, unknown>> {
  const cache = asRecord(status?.cache_status);
  return Object.entries(cache).map(([key, value]) => ({ cache: key, ...asRecord(value) }));
}

export function MarketMonitorPage() {
  const [taskMessage, setTaskMessage] = useState("");
  const [isRefreshing, setIsRefreshing] = useState(false);
  const loader = useCallback(async (): Promise<MarketPagePayload> => {
    const [priceHistory, providerStatus, marketAnalysis] = await Promise.all([getPriceHistory(), getProviderStatusDetail(), getMarketAnalysis()]);
    return { priceHistory, providerStatus, marketAnalysis };
  }, []);
  const { data, error, loading, refresh } = usePolling<MarketPagePayload>(loader, 45000);

  async function handleRefreshMarket() {
    setIsRefreshing(true);
    setTaskMessage("刷新中，保留旧行情");
    try {
      const result = await refreshMarket(true);
      setTaskMessage(result.message_zh || "行情刷新任务已启动");
      await refresh();
    } catch (err) {
      setTaskMessage(err instanceof Error ? err.message : "行情刷新失败");
    } finally {
      setIsRefreshing(false);
    }
  }

  if (loading && !data) return <LoadingState label="加载行情..." />;
  if (error && !data) return <ErrorState title="行情暂不可用" message={error} actionLabel="重试" onAction={refresh} />;

  const priceHistory = data?.priceHistory;
  const analysis = data?.marketAnalysis;
  const provider = asRecord(data?.providerStatus?.market_provider_status);
  const points = priceHistory?.points || [];
  const latest = points[points.length - 1];
  const finalStatus = formatNullable(provider.final_status || provider.status || priceHistory?.message_zh, "等待刷新");
  const activeContract = formatNullable(provider.active_contract || provider.contract || priceHistory?.contract, "SN main");
  const source = formatNullable(provider.source || priceHistory?.source, "provider chain");
  const attempts = attemptRows(provider);
  const caches = cacheRows(provider);
  const volumeRows = points.slice(-18).map((point) => ({
    time: point.time,
    volume: point.volume,
    open_interest: point.open_interest,
    close: point.close
  }));

  return (
    <div className="page-stack">
      <SectionCard
        title="行情 Market"
        subtitle="价格、成交量、缓存和 Provider attempts。"
        actions={
          <button className="primary-button" type="button" onClick={() => void handleRefreshMarket()} disabled={isRefreshing}>
            刷新行情
          </button>
        }
      >
        <div className="metric-grid compact">
          <div className="metric-card">
            <span className="metric-label">最新价</span>
            <strong>{formatPrice(toFiniteNumber(latest?.close))}</strong>
            <small>{formatDateTime(latest?.time)}</small>
          </div>
          <div className="metric-card">
            <span className="metric-label">主力合约</span>
            <strong>{activeContract}</strong>
            <small>SN / SN0 / nf_SN0</small>
          </div>
          <div className="metric-card">
            <span className="metric-label">历史点数</span>
            <strong>{formatNumber(points.length, 0)}</strong>
            <small>{formatNullable(points[0]?.time)} - {formatNullable(latest?.time)}</small>
          </div>
          <div className="metric-card">
            <span className="metric-label">Provider</span>
            <strong>{finalStatus}</strong>
            <small>{source}</small>
          </div>
        </div>
        {taskMessage ? <StatusPill label={taskMessage} tone={taskMessage.includes("失败") ? "bad" : "info"} /> : null}
      </SectionCard>

      <SectionCard title="价格图" subtitle="真实 price-history；无数据则显示原因。">
        <PriceChart priceHistory={priceHistory} keyLevels={analysis?.key_levels} />
      </SectionCard>

      <SectionCard title="量价" subtitle="成交量和持仓；缺字段时不补假值。">
        <DataTable
          data={volumeRows}
          emptyLabel="暂无量价数据"
          columns={[
            { key: "time", title: "日期" },
            { key: "close", title: "收盘", render: (row) => formatPrice(toFiniteNumber(row.close)) },
            { key: "volume", title: "成交量", format: "number" },
            { key: "open_interest", title: "持仓", format: "number" }
          ]}
        />
      </SectionCard>

      <SectionCard title="Provider attempts" subtitle="只显示短诊断。">
        <DataTable
          data={attempts}
          emptyLabel="暂无 provider attempts"
          columns={[
            { key: "lane", title: "链路" },
            { key: "provider", title: "Provider" },
            { key: "status", title: "状态" },
            { key: "row_count", title: "行数", format: "number" },
            { key: "message_zh", title: "原因" }
          ]}
        />
      </SectionCard>

      <SectionCard title="缓存" subtitle="刷新失败时保留最近成功缓存。">
        <DataTable
          data={caches}
          emptyLabel="暂无缓存明细"
          columns={[
            { key: "cache", title: "缓存" },
            { key: "status", title: "状态" },
            { key: "row_count", title: "行数", format: "number" },
            { key: "last_success_time", title: "最近成功", render: (row) => formatDateTime(row.last_success_time as string | undefined) }
          ]}
        />
      </SectionCard>
    </div>
  );
}
