export function LoadingState({
  title = "正在加载本地终端数据...",
  label,
  description
}: {
  title?: string;
  label?: string;
  description?: string;
}) {
  return (
    <div className="state-box loading-state">
      <span className="spinner" />
      <div>
        <strong>{label || title}</strong>
        {description ? <span>{description}</span> : null}
      </div>
    </div>
  );
}
