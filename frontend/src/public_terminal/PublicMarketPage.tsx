import { useEffect, useState } from "react";
import { getPublicMarket } from "./api";
import { DataWatermarkPanel } from "./components/DataWatermarkPanel";
import { IndicatorPanel } from "./components/IndicatorPanel";
import { KlinePanel } from "./components/KlinePanel";
import { MissingDataPanel } from "./components/MissingDataPanel";
import { WatchHeader } from "./components/WatchHeader";
import type { PublicMarketPayload } from "./types";
import { friendlyReason, friendlyStatus, technicalSummary } from "./userCopy";

export function PublicMarketPage() {
  const [payload, setPayload] = useState<PublicMarketPayload | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getPublicMarket()
      .then(setPayload)
      .catch((exc) => setError(exc instanceof Error ? exc.message : "Market data unavailable."));
  }, []);

  const market = payload?.market;
  const klineBars = market?.kline?.bars || market?.chart || [];
  const missingReasons = market?.missing_data?.reasons || (market?.reason ? [market.reason] : []);
  const hasBars = klineBars.length > 0 && market?.status !== "blocked";
  const watermarkPanel = market?.data_watermark_panel || {
    display_allowed: hasBars,
    prediction_allowed: false,
    cache_status: "unknown",
    stale_status: market?.status || "unknown",
    source_published_at: ""
  };

  return (
    <div className="page-stack public-terminal-page">
      {market ? <WatchHeader market={market} /> : null}

      {hasBars ? <KlinePanel bars={klineBars} /> : null}
      {hasBars && market?.indicators ? <IndicatorPanel indicators={market.indicators} /> : null}
      {market ? <DataWatermarkPanel panel={watermarkPanel} /> : null}
      <MissingDataPanel reasons={error ? [error] : missingReasons} />

      {!market ? (
        <section className="guided-empty-state">
          <header>
            <strong>{friendlyStatus("blocked")}</strong>
            <span>{error || friendlyReason("missing_daily_bars")}</span>
          </header>
        </section>
      ) : null}

      <details className="technical-details-drawer">
        <summary>Diagnostics</summary>
        <pre className="diagnostics-pre">
{`market payload / latest quote
${technicalSummary(payload)}`}
        </pre>
      </details>
    </div>
  );
}
