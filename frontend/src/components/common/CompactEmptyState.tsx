export function CompactEmptyState({
  status = "暂无数据",
  reason = "后端暂未返回可展示数据。",
  nextAction = "请刷新数据或查看诊断。"
}: {
  status?: string;
  reason?: string;
  nextAction?: string;
}) {
  return (
    <div className="empty-state compact-empty-state">
      <strong>{status}</strong>
      <p>原因：{reason}</p>
      <p>下一步：{nextAction}</p>
    </div>
  );
}
