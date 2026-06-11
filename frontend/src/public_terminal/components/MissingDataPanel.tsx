export function MissingDataPanel({ reasons }: { reasons: string[] }) {
  if (!reasons.length) return null;
  const missingDailyBars = reasons.includes("missing_daily_bars");
  return (
    <section className="guided-empty-state" data-testid="missing-data-panel">
      <header>
        <strong>{missingDailyBars ? "暂时没有可展示的行情图" : "Missing data"}</strong>
        <span>{missingDailyBars ? `缺少历史行情数据 · 0 bars · ${reasons.join(", ")}` : reasons.join(", ")}</span>
      </header>
    </section>
  );
}
