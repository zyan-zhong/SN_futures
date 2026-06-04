import { formatDateTime } from "../../utils/format";

export function DataFreshnessBadge({
  fromCache,
  stale,
  updatedAt
}: {
  fromCache?: boolean;
  stale?: boolean;
  updatedAt?: string;
}) {
  const label = stale ? "过期缓存" : fromCache ? "最近成功缓存" : "实时/最新文件";
  const tone = stale ? "warning" : fromCache ? "info" : "ok";
  return (
    <span className={`status-pill status-${tone}`}>
      {label}
      {updatedAt ? ` · ${formatDateTime(updatedAt)}` : ""}
    </span>
  );
}
