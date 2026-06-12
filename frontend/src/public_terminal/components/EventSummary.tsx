import type { PublicEventCenterSummary } from "../types";

type EventSummaryInput = PublicEventCenterSummary & {
  status?: string;
  reason?: string;
};

function categoryText(categories: Record<string, number> | undefined) {
  const entries = Object.entries(categories || {}).filter(([, value]) => Number(value) > 0);
  if (!entries.length) return "no categories";
  return entries.map(([key, value]) => `${key} ${value}`).join(" / ");
}

export function EventSummary({ dataTestId, summary }: { dataTestId: string; summary?: EventSummaryInput }) {
  const total = Number(summary?.total_count || 0);
  const eligible = Number(summary?.eligible_count || 0);
  const rejected = Number(summary?.rejected_count || 0);
  return (
    <div className="metric-grid compact" data-testid={dataTestId}>
      <div className="metric-card">
        <span className="metric-label">Total events</span>
        <strong>{total}</strong>
        <small>{summary?.reason || summary?.status || "event rows loaded"}</small>
      </div>
      <div className="metric-card">
        <span className="metric-label">Model eligible</span>
        <strong>{eligible} eligible</strong>
        <small>Requires source time and SHFE SN relevance.</small>
      </div>
      <div className="metric-card">
        <span className="metric-label">Rejected</span>
        <strong>{rejected}</strong>
        <small>Visible for audit, not used in model input.</small>
      </div>
      <div className="metric-card">
        <span className="metric-label">Categories</span>
        <strong>{categoryText(summary?.categories)}</strong>
        <small>Latest source {summary?.latest_source_published_at || "missing"} / fetched {summary?.latest_fetched_at || "missing"}</small>
      </div>
    </div>
  );
}
