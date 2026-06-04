import { SectionCard } from "../layout/SectionCard";

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function formatCostValue(value: unknown): string {
  if (value === null || value === undefined || (typeof value === "number" && Number.isNaN(value))) return "数据暂缺";
  if (typeof value === "number") return Number.isFinite(value) ? value.toFixed(4) : "数据暂缺";
  if (typeof value === "boolean") return value ? "通过" : "未通过";
  if (typeof value === "string") return value.trim() || "数据暂缺";
  return "已归档";
}

export function CostSensitivityPanel({ data }: { data?: Record<string, unknown> }) {
  const entries = Object.entries(asRecord(data));
  return (
    <SectionCard title="成本敏感性" subtitle="手续费、滑点和冲击成本压力测试">
      {entries.length ? (
        <div className="compact-table">
          {entries.map(([key, value]) => (
            <div key={key}>
              <span>{key}</span>
              <strong>{formatCostValue(value)}</strong>
            </div>
          ))}
        </div>
      ) : (
        <p className="muted">暂无成本敏感性数据。</p>
      )}
    </SectionCard>
  );
}
