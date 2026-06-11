import type { PublicMarketPayload } from "../types";

type Panel = NonNullable<NonNullable<PublicMarketPayload["market"]>["data_watermark_panel"]>;

export function DataWatermarkPanel({ panel }: { panel: Panel }) {
  return (
    <section className="section-card" data-testid="data-watermark-panel">
      <div className="section-card__header">
        <div>
          <h2>Data Watermark</h2>
          <p>{String(panel.source_published_at || "--")}</p>
        </div>
      </div>
      <div className="market-watermark-grid">
        <span>display {panel.display_allowed ? "allowed" : "blocked"}</span>
        <span>prediction {panel.prediction_allowed ? "allowed" : "denied"}</span>
        <span>{String(panel.cache_status || "unknown")}</span>
        <span>{String(panel.stale_status || "unknown")}</span>
      </div>
    </section>
  );
}
