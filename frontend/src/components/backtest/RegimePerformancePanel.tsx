import { SectionCard } from "../layout/SectionCard";

export function RegimePerformancePanel({ data }: { data?: Record<string, unknown> }) {
  const entries = Object.entries(data || {});
  return (
    <SectionCard title="Regime 分组表现" subtitle="趋势、震荡、高波动和事件驱动状态下的表现">
      {entries.length ? (
        <div className="compact-table">
          {entries.map(([key, value]) => (
            <div key={key}>
              <span>{key}</span>
              <strong>{typeof value === "object" ? JSON.stringify(value) : String(value)}</strong>
            </div>
          ))}
        </div>
      ) : (
        <p className="muted">暂无分组表现数据。</p>
      )}
    </SectionCard>
  );
}
