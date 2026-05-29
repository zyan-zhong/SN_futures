export function SampleModeBanner({
  visible,
  message = "当前为样例数据模式，请点击一键刷新数据获取真实数据。"
}: {
  visible?: boolean;
  message?: string;
}) {
  if (!visible) return null;
  return (
    <div className="sample-mode-banner" role="status" aria-live="polite">
      <strong>样例数据模式</strong>
      <span>{message}</span>
    </div>
  );
}
