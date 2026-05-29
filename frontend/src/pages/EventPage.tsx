import { useCallback } from "react";
import type { PageKey } from "../App";
import { getNewsEvents, getNewsRelevanceDiagnostics, getNewsSourceQualityReport, getPriceHistory, refreshNews } from "../api/terminal";
import type { NewsEventItem, NewsEventsPayload, NewsRelevanceDiagnosticsPayload, NewsSourceQualityReport, PriceHistoryPayload } from "../api/types";
import { PriceChart } from "../components/charts/PriceChart";
import { DataTable } from "../components/common/DataTable";
import { EmptyState } from "../components/common/EmptyState";
import { ErrorBoundary } from "../components/common/ErrorBoundary";
import { ErrorState } from "../components/common/ErrorState";
import { LoadingState } from "../components/common/LoadingState";
import { StatusPill } from "../components/common/StatusPill";
import { SectionCard } from "../components/layout/SectionCard";
import { usePolling } from "../hooks/usePolling";
import { formatNumber, formatNullable } from "../utils/format";

function categoryLabel(value?: string): string {
  const labels: Record<string, string> = {
    supply: "供应",
    demand: "需求",
    inventory: "库存",
    exchange: "交易所",
    macro: "宏观",
    policy: "政策",
    company: "公司",
    irrelevant: "无关",
    other: "其他"
  };
  return labels[String(value || "other")] || "其他";
}

export function EventPage({
  onNavigate,
  showSampleData = true
}: {
  onNavigate?: (page: PageKey) => void;
  showSampleData?: boolean;
}) {
  const newsLoader = useCallback(() => getNewsEvents(), []);
  const diagnosticsLoader = useCallback(() => getNewsRelevanceDiagnostics(), []);
  const sourceQualityLoader = useCallback(() => getNewsSourceQualityReport(), []);
  const priceLoader = useCallback(() => getPriceHistory(), []);
  const { data, error, loading, refresh } = usePolling<NewsEventsPayload>(newsLoader, 60000);
  const { data: relevanceDiagnostics, refresh: refreshDiagnostics } = usePolling<NewsRelevanceDiagnosticsPayload>(
    diagnosticsLoader,
    60000
  );
  const { data: sourceQualityReport, refresh: refreshSourceQuality } = usePolling<NewsSourceQualityReport>(
    sourceQualityLoader,
    60000
  );
  const { data: priceHistory, refresh: refreshPriceHistory } = usePolling<PriceHistoryPayload>(priceLoader, 60000);
  const events = data?.sample_mode && !showSampleData ? [] : data?.events || [];
  const visiblePriceHistory = priceHistory?.sample_mode && !showSampleData ? { ...priceHistory, points: [] } : priceHistory;

  async function runNewsRefresh() {
    await refreshNews();
    void refresh();
    void refreshDiagnostics();
    void refreshSourceQuality();
    void refreshPriceHistory();
  }

  if (loading) return <LoadingState label="正在加载行情与新闻..." />;
  if (error) {
    return <ErrorState title="行情与新闻暂时无法加载" message={error} actionLabel="重新加载" onAction={refresh} />;
  }

  const notConfigured = Boolean(data?.message_zh?.includes("未配置") || data?.message_zh?.includes("NewsAPI"));
  const modelEvents = events.filter((event) => event.used_in_model);
  const displayOnlyEvents = events.filter((event) => !event.used_in_model && Number(event.relevance_score || 0) >= 0.25);
  const excludedEvents = events.filter((event) => !event.used_in_model && Number(event.relevance_score || 0) < 0.25);
  const queryGroupRows = Object.entries(relevanceDiagnostics?.query_groups || {}).map(([query_group, stats]) => ({
    query_group,
    returned_count: stats.returned_count || 0,
    used_in_model_count: stats.used_in_model_count || 0,
    avg_relevance: stats.avg_relevance || 0
  }));
  const sourceQualityRows = sourceQualityReport?.domains || [];

  const newsColumns = [
    { key: "title", title: "标题", render: (row: NewsEventItem) => formatNullable(row.title, "未命名新闻") },
    { key: "source", title: "来源", render: (row: NewsEventItem) => formatNullable(row.source) },
    { key: "published_at", title: "发布时间", format: "date" as const },
    { key: "query_group", title: "Query Group", render: (row: NewsEventItem) => formatNullable(row.query_group) },
    { key: "category", title: "分类", render: (row: NewsEventItem) => categoryLabel(row.category) },
    { key: "impact_score", title: "影响分", render: (row: NewsEventItem) => formatNumber(row.impact_score, 2) },
    { key: "sentiment_score", title: "情绪分", render: (row: NewsEventItem) => formatNumber(row.sentiment_score, 2) },
    { key: "relevance_score", title: "相关性分数", render: (row: NewsEventItem) => formatNumber(row.relevance_score, 2) },
    { key: "used_in_model", title: "是否入模", render: (row: NewsEventItem) => (row.used_in_model ? "已入模" : "未入模") },
    { key: "keyword_hits", title: "关键词证据", render: (row: NewsEventItem) => (row.keyword_hits || []).join(", ") || "数据暂缺" },
    {
      key: "negative_keyword_hits",
      title: "负面命中",
      render: (row: NewsEventItem) => (row.negative_keyword_hits || []).join(", ") || "无"
    },
    { key: "exclusion_reason", title: "排除原因", render: (row: NewsEventItem) => row.exclusion_reason || "数据暂缺" },
    { key: "url", title: "原文", render: (row: NewsEventItem) => (row.url ? "可打开" : "数据暂缺") }
  ];

  const queryGroupColumns = [
    { key: "query_group", title: "Query Group" },
    { key: "returned_count", title: "候选数", format: "number" as const },
    { key: "used_in_model_count", title: "入模数", format: "number" as const },
    { key: "avg_relevance", title: "平均相关性", render: (row: Record<string, unknown>) => formatNumber(row.avg_relevance as number, 2) }
  ];

  return (
    <div className="page-stack">
      <SectionCard title="行情与新闻" subtitle="先看沪锡行情历史，再看新闻事件；没有真实数据时会显示空状态或样例标识。">
        <ErrorBoundary moduleName="行情历史图">
          <PriceChart priceHistory={visiblePriceHistory} />
        </ErrorBoundary>
      </SectionCard>

      <SectionCard title="新闻事件" subtitle="读取 /api/terminal/events/news；不显示假新闻，未配置 NewsAPI 时给出清晰指引。">
        <div className="notice-card">
          <strong>新闻相关性过滤</strong>
          <p>高相关新闻才进入事件因子；低相关新闻仅展示；无关新闻标记为未入模，不会伪造事件因子。</p>
          <p className="muted">真实锡新闻误杀风险会通过关键词证据、负面命中和 query group 统计暴露出来。</p>
          <span className="status-pill status-info">高相关事件</span>
          <span className="status-pill status-warning">低相关新闻折叠</span>
          <span className="status-pill status-neutral">入模/未入模标记</span>
        </div>
        <div className="button-row">
          <button className="primary-button" type="button" onClick={() => void runNewsRefresh()}>
            刷新新闻
          </button>
          <button className="ghost-button" type="button" onClick={() => onNavigate?.("settings")}>
            前往设置
          </button>
          <StatusPill label={data?.message_zh || "事件状态待验证"} tone={events.length ? "info" : "warn"} />
        </div>
        <ErrorBoundary moduleName="新闻事件列表">
          {queryGroupRows.length ? (
            <SectionCard title="Query Group 统计" subtitle="用于判断是哪组 query 返回候选、哪组产生入模事件。">
              <DataTable data={queryGroupRows} columns={queryGroupColumns} />
            </SectionCard>
          ) : null}
          {sourceQualityRows.length ? (
            <SectionCard title="新闻源质量诊断" subtitle="展示 source reliability、hard evidence、白名单和黑名单影响；来源质量不会绕过沪锡相关性门槛。">
              <DataTable
                data={sourceQualityRows as Array<Record<string, unknown>>}
                columns={[
                  { key: "domain", title: "Domain" },
                  { key: "article_count", title: "新闻数", format: "number" as const },
                  { key: "used_in_model_count", title: "入模数", format: "number" as const },
                  {
                    key: "avg_source_reliability",
                    title: "来源可靠度",
                    render: (row: Record<string, unknown>) => formatNumber(row.avg_source_reliability as number, 2)
                  }
                ]}
              />
            </SectionCard>
          ) : null}
          {events.length ? (
            <div className="page-stack">
              <SectionCard title={`入模事件（${modelEvents.length}）`} subtitle="仅 used_in_model=true 的高相关新闻进入事件因子。">
                {modelEvents.length ? (
                  <DataTable data={modelEvents as Array<NewsEventItem & Record<string, unknown>>} columns={newsColumns} />
                ) : (
                  <EmptyState label="没有通过相关性门槛的锡产业新闻，不会伪造事件因子。" />
                )}
              </SectionCard>
              <SectionCard title={`仅展示新闻（${displayOnlyEvents.length}）`} subtitle="相关性不足以入模，仅供人工浏览。">
                {displayOnlyEvents.length ? (
                  <DataTable data={displayOnlyEvents as Array<NewsEventItem & Record<string, unknown>>} columns={newsColumns} />
                ) : (
                  <EmptyState label="暂无仅展示新闻。" />
                )}
              </SectionCard>
              <details className="debug-details">
                <summary>已排除新闻（{excludedEvents.length}）</summary>
                {excludedEvents.length ? (
                  <DataTable data={excludedEvents as Array<NewsEventItem & Record<string, unknown>>} columns={newsColumns} />
                ) : (
                  <p className="muted">暂无已排除新闻。</p>
                )}
              </details>
            </div>
          ) : (
            <div className="empty-action-panel">
              <EmptyState
                label={
                  notConfigured
                    ? "未配置 NewsAPI，无法拉取外部新闻。可以前往设置页配置，也可以继续使用行情和本地缓存。"
                    : "暂无新闻事件。请尝试刷新新闻，或稍后扩大时间窗口。"
                }
              />
              <div className="button-row">
                <button className="ghost-button" type="button" onClick={() => void runNewsRefresh()}>
                  刷新新闻
                </button>
                <button className="ghost-button" type="button" onClick={() => onNavigate?.("settings")}>
                  配置 NewsAPI
                </button>
              </div>
            </div>
          )}
        </ErrorBoundary>
      </SectionCard>

      <SectionCard title="事件分类说明" subtitle="事件分数用于投研解释和模型特征窗口，不代表确定性因果。">
        <div className="factor-group-grid">
          {["供应冲击", "需求冲击", "库存冲击", "交易所事件", "宏观冲击"].map((name) => (
            <div className="factor-group" key={name}>
              <strong>{name}</strong>
              <span>来自 NewsAPI 高相关新闻和事件 store；数据不足时显示数据暂缺。</span>
            </div>
          ))}
        </div>
      </SectionCard>
    </div>
  );
}
