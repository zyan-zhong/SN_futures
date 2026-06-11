import type { PublicMarketBar } from "../types";

function numberValue(value: unknown) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function barHeight(bar: PublicMarketBar, min: number, max: number) {
  const close = numberValue(bar.close);
  if (max <= min) return 50;
  return Math.max(12, Math.min(96, 18 + ((close - min) / (max - min)) * 78));
}

export function KlinePanel({ bars }: { bars: PublicMarketBar[] }) {
  const visible = bars.slice(-60);
  const closes = visible.map((bar) => numberValue(bar.close)).filter((value) => value > 0);
  const min = Math.min(...closes);
  const max = Math.max(...closes);
  const latest = visible[visible.length - 1];

  return (
    <section className="section-card" data-testid="kline-panel">
      <div className="section-card__header">
        <div>
          <h2>Daily K</h2>
          <p>{visible.length} bars</p>
        </div>
      </div>
      <div className="simple-chart market-kline-chart" aria-label="Daily K chart">
        {visible.map((bar, index) => (
          <span
            key={`${String(bar.date || bar.time || index)}-${index}`}
            data-kline-bar
            title={`${String(bar.date || "--")} close ${String(bar.close ?? "--")}`}
            style={{ height: `${barHeight(bar, min, max)}%` }}
          />
        ))}
      </div>
      <div className="market-kline-footer">
        <span>Volume {String(latest?.volume ?? "--")}</span>
        <span>Open interest {String(latest?.open_interest ?? "--")}</span>
      </div>
    </section>
  );
}
