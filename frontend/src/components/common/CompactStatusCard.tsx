import { formatNullable } from "../../utils/format";

export function CompactStatusCard({
  label,
  value,
  detail,
  tone = "neutral"
}: {
  label: string;
  value?: unknown;
  detail?: string;
  tone?: "ok" | "warning" | "error" | "neutral" | "info";
}) {
  return (
    <div className={`metric-card compact-status-card tone-${tone}`}>
      <span className="metric-label">{label}</span>
      <strong>{formatNullable(value, "暂无")}</strong>
      {detail ? <small>{detail}</small> : null}
    </div>
  );
}
