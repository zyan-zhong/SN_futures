import { formatNullable } from "../../utils/format";
import { StatusPill } from "./StatusPill";

export function MetricCard({
  label,
  value,
  hint,
  tone = "neutral"
}: {
  label: string;
  value: unknown;
  hint?: string;
  tone?: "good" | "warn" | "bad" | "neutral" | "info";
}) {
  return (
    <div className="metric-card">
      <div className="metric-label">{label}</div>
      <div className="metric-value">{formatNullable(value)}</div>
      {hint ? <StatusPill label={hint} tone={tone} /> : null}
    </div>
  );
}
