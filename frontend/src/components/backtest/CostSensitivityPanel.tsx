import { SectionCard } from "../layout/SectionCard";

export function CostSensitivityPanel({ data }: { data?: Record<string, unknown> }) {
  const entries = Object.entries(data || {});
  return (
    <SectionCard title="成本敏感性" subtitle="手续费、滑点和冲击成本压力测试">
      {entries.length ? (
        <div className="compact-table">
          {entries.map(([key, value]) => (
            <div key={key}>
              <span>{key}</span>
              <strong>{String(value)}</strong>
            </div>
          ))}
        </div>
      ) : (
        <p className="muted">暂无成本敏感性数据。</p>
      )}
    </SectionCard>
  );
}
