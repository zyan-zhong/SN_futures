import { formatDateTime, formatNullable } from "../../utils/format";
import { StatusPill } from "./StatusPill";

type Tone = "good" | "warn" | "bad" | "neutral" | "info";

export function CompactProviderCard({
  name,
  status,
  reason,
  nextAction,
  lastAttemptTime,
  lastSuccessTime,
  rowCount,
  tone = "neutral"
}: {
  name: string;
  status: string;
  reason?: string;
  nextAction?: string;
  lastAttemptTime?: string;
  lastSuccessTime?: string;
  rowCount?: number;
  tone?: Tone;
}) {
  return (
    <article className="compact-provider-card">
      <header>
        <strong>{name}</strong>
        <StatusPill label={status} tone={tone} />
      </header>
      <div className="compact-provider-card__grid">
        <span>原因</span>
        <strong>{formatNullable(reason, "暂无")}</strong>
        <span>下一步</span>
        <strong>{formatNullable(nextAction, "观察")}</strong>
        <span>最近尝试</span>
        <strong>{formatDateTime(lastAttemptTime)}</strong>
        <span>最近成功</span>
        <strong>{formatDateTime(lastSuccessTime)}</strong>
        <span>行数</span>
        <strong>{rowCount ?? 0}</strong>
      </div>
    </article>
  );
}
