import { useCallback, useState } from "react";
import { getPriceHistory, getProviderStatusDetail, refreshMarket } from "../api/terminal";
import type { PriceHistoryPayload, ProviderStatusDetailPayload } from "../api/types";
import { PriceChart } from "../components/charts/PriceChart";
import { DataTable } from "../components/common/DataTable";
import { ErrorState } from "../components/common/ErrorState";
import { LoadingState } from "../components/common/LoadingState";
import { StatusPill } from "../components/common/StatusPill";
import { SectionCard } from "../components/layout/SectionCard";
import { usePolling } from "../hooks/usePolling";
import { formatDateTime, formatNullable, formatNumber, formatPrice, toFiniteNumber } from "../utils/format";

type MarketPagePayload = {
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
  const rows = [
    ...asArray(status?.realtime_attempts).map((row) => ({ lane: "realtime", ...row })),
    ...asArray(status?.history_attempts).map((row) => ({ lane: "history", ...row })),
    ...asArray(status?.shfe_attempts).map((row) => ({ lane: "shfe_aux", ...row })),
  ];
  return rows.slice(0, 24);
}

function cacheRows(status?: Record<string, unknown>): Array<Record<string, unknown>> {
  const cache = asRecord(status?.cache_status);
  return Object.entries(cache).map(([key, value]) => ({ cache: key, ...asRecord(value) }));
}

export function MarketMonitorPage() {
  const [taskMessage, setTaskMessage] = useState("");
  const loader = useCallback(async (): Promise<MarketPagePayload> => {
    const [priceHistory, providerStatus] = await Promise.all([getPriceHistory(), getProviderStatusDetail()]);
    return { priceHistory, providerStatus };
  }, []);
  const { data, error, loading, refresh } = usePolling<MarketPagePayload>(loader, 45000);

  async function handleRefreshMarket() {
    setTaskMessage("正在刷新真实沪锡行情...");
    try {
      const result = await refreshMarket(true);
      setTaskMessage(result.message_zh || "行情刷新任务已完成。");
      await refresh();
    } catch (err) {
      setTaskMessage(err instanceof Error ? err.message : "行情刷新失败，请查看 provider attempts。");
    }
  }

  if (loading && !data) return <LoadingState label="正在加载行情监控..." />;
  if (error && !data) return <ErrorState title="行情监控暂时无法加载" message={error} actionLabel="重新加载" onAction={refresh} />;

  const priceHistory = data?.priceHistory;
  const provider = asRecord(data?.providerStatus?.market_provider_status);
  const points = priceHistory?.points || [];
  const latest = points[points.length - 1];
  const finalStatus = formatNullable(provider.final_status || provider.status || priceHistory?.message_zh, "等待行情刷新");
  const activeContract = formatNullable(provider.active_contract || provider.contract || priceHistory?.contract, "SN main/continuous");
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
        title="行情监控 Market Monitor"
        subtitle="展示实时 quote、历史价格、成交量、持仓量、provider attempts、缓存状态和 SN 符号映射。"
        actions={
          <button className="primary-button" type="button" onClick={() => void handleRefreshMarket()}>
            刷新行情
          </button>
        }
      >
        <div className="metric-grid compact">
          <div className="metric-card">
            <span className="metric-label">最新价格</span>
            <strong>{formatPrice(toFiniteNumber(latest?.close))}</strong>
            <small>{formatDateTime(latest?.time)}</small>
          </div>
          <div className="metric-card">
            <span className="metric-label">主力合约</span>
            <strong>{activeContract}</strong>
            <small>symbol mapping: SN / SN0 / nf_SN0</small>
          </div>
          <div className="metric-card">
            <span className="metric-label">历史点数</span>
            <strong>{formatNumber(points.length, 0)}</strong>
            <small>{formatNullable(points[0]?.time)} - {formatNullable(latest?.time)}</small>
          </div>
          <div className="metric-card">
            <span className="metric-label">Provider 状态</span>
            <strong>{finalStatus}</strong>
            <small>{source}</small>
          </div>
          <div className="metric-card">
            <span className="metric-label">交易时段</span>
            <strong>{formatNullable(provider.trading_session || provider.session, "按交易所日历判断")}</strong>
            <small>非交易时段不视为实时源失败</small>
          </div>
          <div className="metric-card">
            <span className="metric-label">缓存状态</span>
            <strong>{caches.length ? "可审计" : "暂无缓存明细"}</strong>
            <small>last good cache 只用于展示，不冒充新行情</small>
          </div>
        </div>
        {taskMessage ? <StatusPill label={taskMessage} tone={taskMessage.includes("失败") ? "bad" : "info"} /> : null}
      </SectionCard>

      <SectionCard title="历史价格图" subtitle="price-history 有真实数据时显示图表；无数据时显示 provider 失败原因。">
        <PriceChart priceHistory={priceHistory} />
      </SectionCard>

      <SectionCard title="成交量与持仓量" subtitle="持仓量字段存在时显示；缺失时保持空状态，不伪造。">
        <DataTable
          data={volumeRows as Array<Record<string, unknown>>}
          emptyLabel="暂无成交量或持仓量数据"
          columns={[
            { key: "time", title: "交易日", render: (row) => formatNullable(row.time) },
            { key: "close", title: "收盘", render: (row) => formatPrice(toFiniteNumber(row.close)) },
            { key: "volume", title: "成交量", render: (row) => formatNumber(toFiniteNumber(row.volume), 0) },
            { key: "open_interest", title: "持仓量", render: (row) => formatNumber(toFiniteNumber(row.open_interest), 0) },
          ]}
        />
      </SectionCard>

      <SectionCard title="Provider attempts" subtitle="展示 Sina、AKShare realtime/history、SHFE auxiliary 和 symbol_used。">
        <DataTable
          data={attempts}
          emptyLabel="暂无 provider attempts，请先点击刷新行情。"
          columns={[
            { key: "lane", title: "链路", render: (row) => formatNullable(row.lane) },
            { key: "provider_name", title: "Provider", render: (row) => formatNullable(row.provider_name || row.source_name) },
            { key: "symbol_used", title: "Symbol", render: (row) => formatNullable(row.symbol_used || row.symbol) },
            { key: "success", title: "成功", render: (row) => (row.success ? "是" : "否") },
            { key: "rows", title: "行数", render: (row) => formatNumber(toFiniteNumber(row.rows || row.row_count), 0) },
            { key: "latest_time", title: "最新时间", render: (row) => formatNullable(row.latest_time || row.quote_time) },
            { key: "error_message_zh", title: "失败原因", render: (row) => formatNullable(row.error_message_zh || row.message_zh, "无") },
          ]}
        />
      </SectionCard>

      <SectionCard title="缓存与 symbol 映射" subtitle="缓存使用必须显式标记 from_cache/stale；不会把缓存伪装为新行情。">
        <div className="two-column">
          <DataTable
            data={caches}
            emptyLabel="暂无缓存状态"
            columns={[
              { key: "cache", title: "缓存", render: (row) => formatNullable(row.cache) },
              { key: "success", title: "可用", render: (row) => (row.success || row.exists ? "是" : "否") },
              { key: "from_cache", title: "from_cache", render: (row) => (row.from_cache ? "是" : "否") },
              { key: "stale", title: "stale", render: (row) => (row.stale ? "是" : "否") },
              { key: "last_success_time", title: "最近成功", render: (row) => formatNullable(row.last_success_time || row.generated_at) },
            ]}
          />
          <div className="notice-card">
            <strong>Symbol mapping</strong>
            <p>{JSON.stringify(provider.symbol_mapping || provider.symbol_status || { normalized: activeContract }, null, 2).replace(/null/g, "missing")}</p>
            <strong>Refresh boundary</strong>
            <p>本页只刷新真实行情，不训练模型、不发布 active、不生成客户预测。</p>
          </div>
        </div>
      </SectionCard>
    </div>
  );
}
