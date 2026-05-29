import { StatusPill } from "../common/StatusPill";

export function RiskBadge({ label }: { label?: string }) {
  const text = label || "数据不足";
  const tone = text.includes("低") ? "good" : text.includes("高") || text.includes("不足") ? "bad" : "warn";
  return <StatusPill label={text} tone={tone} />;
}
