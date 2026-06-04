export function ApiHealthBadge({ status }: { status?: string }) {
  const normalized = (status || "unknown").toLowerCase();
  const tone = normalized.includes("success") || normalized.includes("ok") || normalized.includes("正常")
    ? "ok"
    : normalized.includes("missing") || normalized.includes("limited") || normalized.includes("warning")
      ? "warning"
      : normalized.includes("fail") || normalized.includes("error")
        ? "error"
        : "neutral";
  return <span className={`status-pill status-${tone}`}>API {status || "unknown"}</span>;
}
