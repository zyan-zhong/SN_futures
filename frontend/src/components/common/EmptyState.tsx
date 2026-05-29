export function EmptyState({
  title = "暂无可用数据",
  label,
  description,
  actionLabel,
  onAction,
  secondaryActionLabel,
  onSecondaryAction
}: {
  title?: string;
  label?: string;
  description?: string;
  actionLabel?: string;
  onAction?: () => void;
  secondaryActionLabel?: string;
  onSecondaryAction?: () => void;
}) {
  return (
    <div className="state-box empty-state">
      <strong>{label || title}</strong>
      {description ? <span>{description}</span> : null}
      {(onAction || onSecondaryAction) ? (
        <div className="button-row">
          {onAction ? (
            <button className="ghost-button" type="button" onClick={onAction}>
              {actionLabel || "刷新"}
            </button>
          ) : null}
          {onSecondaryAction ? (
            <button className="ghost-button" type="button" onClick={onSecondaryAction}>
              {secondaryActionLabel || "前往设置"}
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
