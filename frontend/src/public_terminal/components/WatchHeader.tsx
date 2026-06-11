import type { PublicMarketPayload } from "../types";

type Market = NonNullable<PublicMarketPayload["market"]>;

function formatNumber(value: unknown) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return "--";
  return parsed.toLocaleString("en-US", { maximumFractionDigits: 2 });
}

export function WatchHeader({ market }: { market: Market }) {
  const header = market.watch_header || {};
  return (
    <section className="section-card market-watch-header" data-testid="watch-header">
      <div className="section-card__header">
        <div>
          <h1>市场数据</h1>
          <p>{header.symbol || "SN"} watch board</p>
        </div>
      </div>
      <div className="market-watch-grid">
        <div>
          <span className="metric-label">Latest</span>
          <strong data-testid="watch-latest-price">{formatNumber(header.latest_price)}</strong>
          <small>{header.latest_quote_display_only ? "display-only quote" : "daily close"}</small>
        </div>
        <div>
          <span className="metric-label">Daily close</span>
          <strong>{formatNumber(header.daily_close)}</strong>
          <small>{String(header.trade_date || "--")}</small>
        </div>
        <div>
          <span className="metric-label">Volume</span>
          <strong>{formatNumber(header.volume)}</strong>
          <small>open interest {formatNumber(header.open_interest)}</small>
        </div>
      </div>
    </section>
  );
}
