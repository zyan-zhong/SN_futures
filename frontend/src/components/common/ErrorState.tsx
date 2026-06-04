import { COPY } from "../../utils/copy";
import { sanitizeRecord } from "../../utils/sanitize";

function summarizeDetails(details: unknown): string {
  const safe = sanitizeRecord(details);
  if (!safe || typeof safe !== "object") return String(safe ?? "empty");
  return Object.entries(safe as Record<string, unknown>)
    .map(([key, value]) => `${key}: ${String(value ?? "").slice(0, 160)}`)
    .join(" | ");
}

export function ErrorState({
  title = "模块加载失败",
  message,
  description,
  actionLabel = "刷新",
  onAction,
  onRetry,
  secondaryActionLabel,
  onSecondaryAction,
  details
}: {
  title?: string;
  message?: string | null;
  description?: string;
  actionLabel?: string;
  onAction?: () => void;
  onRetry?: () => void;
  secondaryActionLabel?: string;
  onSecondaryAction?: () => void;
  details?: unknown;
}) {
  const primary = onAction || onRetry;
  return (
    <div className="state-box error-state" role="alert">
      <strong>{title}</strong>
      <span>{message || description || "接口暂不可用，请稍后重试。"}</span>
      <div className="button-row">
        {primary ? (
          <button className="ghost-button" type="button" onClick={primary}>
            {actionLabel}
          </button>
        ) : null}
        {onSecondaryAction ? (
          <button className="ghost-button" type="button" onClick={onSecondaryAction}>
            {secondaryActionLabel || "查看数据源状态"}
          </button>
        ) : null}
      </div>
      {details ? (
        <details className="debug-panel">
          <summary>{COPY.debugTitle}</summary>
          <code className="debug-summary">{summarizeDetails(details)}</code>
        </details>
      ) : null}
    </div>
  );
}
