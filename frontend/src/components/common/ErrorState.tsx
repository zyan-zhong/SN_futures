import { COPY } from "../../utils/copy";
import { sanitizeRecord } from "../../utils/sanitize";

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
          <pre>{JSON.stringify(sanitizeRecord(details), null, 2)}</pre>
        </details>
      ) : null}
    </div>
  );
}

