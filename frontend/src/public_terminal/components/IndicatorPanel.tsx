import type { PublicMarketPayload } from "../types";

type Indicators = NonNullable<NonNullable<PublicMarketPayload["market"]>["indicators"]>;

const INDICATOR_LABELS: Record<string, string> = {
  sma_5: "SMA 5",
  sma_20: "SMA 20",
  rsi_14: "RSI 14",
  macd: "MACD",
  macd_signal: "MACD Signal",
  volatility_20: "Volatility 20"
};

function formatValue(value: unknown) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return "--";
  if (Math.abs(parsed) < 1) return parsed.toFixed(4);
  return parsed.toLocaleString("en-US", { maximumFractionDigits: 2 });
}

export function IndicatorPanel({ indicators }: { indicators: Indicators }) {
  const values = indicators.values || {};
  const entries = Object.entries(INDICATOR_LABELS).filter(([key]) => values[key] !== undefined);
  if (indicators.status !== "ready") {
    return (
      <section className="section-card" data-testid="indicator-panel">
        <div className="section-card__header">
          <div>
            <h2>Indicators</h2>
            <p>{(indicators.blocking_reasons || []).join(", ") || "blocked"}</p>
          </div>
        </div>
      </section>
    );
  }
  return (
    <section className="section-card" data-testid="indicator-panel">
      <div className="section-card__header">
        <div>
          <h2>Indicators</h2>
          <p>RSI / MACD / SMA / Volatility</p>
        </div>
      </div>
      <div className="market-indicator-grid">
        {entries.map(([key, label]) => (
          <div key={key}>
            <span className="metric-label">{label}</span>
            <strong>{formatValue(values[key])}</strong>
          </div>
        ))}
      </div>
    </section>
  );
}
