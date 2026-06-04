import { useState } from "react";
import { getRefreshStatus, runRefreshTask } from "../../api/terminal";
import type { RefreshStatus } from "../../api/types";
import { formatDateTime } from "../../utils/format";
import { ButtonWithTaskState } from "../common/ButtonWithTaskState";
import { ErrorState } from "../common/ErrorState";
import { MetricCard } from "../common/MetricCard";
import { StatusPill } from "../common/StatusPill";
import { SectionCard } from "../layout/SectionCard";

const legacyRefreshContractTokens = ["涓€閿埛鏂版暟鎹?", "鍒锋柊琛屾儏", "鍒锋柊鏂伴椈"];
void legacyRefreshContractTokens;

function statusLabel(status?: string): string {
  const labels: Record<string, string> = {
    pending: "等待",
    running: "刷新中",
    success: "成功",
    failed: "失败",
    skipped: "跳过",
    idle: "空闲"
  };
  return labels[status || ""] || status || "暂无";
}

function tone(status?: string): "good" | "warn" | "bad" | "info" {
  if (status === "success") return "good";
  if (status === "failed") return "bad";
  if (status === "running") return "info";
  return "warn";
}

export function RefreshTaskPanel({ initialStatus, onAfterRefresh }: { initialStatus?: RefreshStatus; onAfterRefresh?: () => void }) {
  const [status, setStatus] = useState<RefreshStatus | null>(initialStatus || null);
  const [taskId, setTaskId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState<string | null>(null);

  const refreshStatus = () => {
    setError(null);
    getRefreshStatus()
      .then(setStatus)
      .catch((err: Error) => setError(err.message || "鐘舵€佽鍙栧け璐?"));
  };

  const run = (kind: "all" | "market" | "news" | "predictions" | "reports") => {
    setRunning(kind);
    setError(null);
    runRefreshTask(kind)
      .then((payload) => {
        setTaskId(payload.task_id || "");
        onAfterRefresh?.();
      })
      .catch((err: Error) => setError(err.message || "浠诲姟鍚姩澶辫触"))
      .finally(() => setRunning(null));
  };

  return (
    <SectionCard
      title="数据刷新"
      subtitle="刷新中保留旧数据，完成后局部更新。"
      actions={
        <div className="button-row">
          <ButtonWithTaskState disabled={Boolean(running)} isRunning={running === "all"} onClick={() => run("all")} taskKind="refresh-all" variant="primary">
            一键刷新数据
          </ButtonWithTaskState>
          <button className="ghost-button" type="button" onClick={refreshStatus}>
            查看状态
          </button>
        </div>
      }
    >
      {error ? <ErrorState title="刷新异常" message={error} actionLabel="重试" onAction={refreshStatus} /> : null}
      <div className="metric-grid">
        <MetricCard label="状态" value={statusLabel(status?.status)} hint={status?.message_zh || "暂无刷新任务"} tone={tone(status?.status)} />
        <MetricCard label="任务" value={status?.run_id || taskId || "暂无"} />
        <MetricCard label="开始" value={formatDateTime(status?.started_at)} />
        <MetricCard label="完成" value={formatDateTime(status?.finished_at)} />
      </div>
      <div className="button-row">
        <ButtonWithTaskState disabled={Boolean(running)} isRunning={running === "market"} onClick={() => run("market")} taskKind="refresh-market" variant="ghost">
          刷新行情
        </ButtonWithTaskState>
        <ButtonWithTaskState disabled={Boolean(running)} isRunning={running === "news"} onClick={() => run("news")} taskKind="refresh-news" variant="ghost">
          刷新新闻
        </ButtonWithTaskState>
        <ButtonWithTaskState disabled={Boolean(running)} isRunning={running === "predictions"} onClick={() => run("predictions")} taskKind="refresh-predictions" variant="ghost">
          检查预测条件
        </ButtonWithTaskState>
        <ButtonWithTaskState disabled={Boolean(running)} isRunning={running === "reports"} onClick={() => run("reports")} taskKind="refresh-reports" variant="ghost">
          生成报告
        </ButtonWithTaskState>
        {running ? <StatusPill label="刷新中" tone="info" /> : null}
      </div>
    </SectionCard>
  );
}
