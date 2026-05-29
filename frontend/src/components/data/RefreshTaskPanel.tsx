import { useState } from "react";
import { getRefreshStatus, runRefreshTask } from "../../api/terminal";
import type { RefreshStatus, RefreshStepStatus } from "../../api/types";
import { formatDateTime, formatNullable, formatNumber } from "../../utils/format";
import { DataTable } from "../common/DataTable";
import { ErrorState } from "../common/ErrorState";
import { MetricCard } from "../common/MetricCard";
import { StatusPill } from "../common/StatusPill";
import { SectionCard } from "../layout/SectionCard";

function stepLabel(name?: string): string {
  const labels: Record<string, string> = {
    market: "行情",
    news: "新闻",
    events: "事件",
    features: "特征",
    predictions: "预测",
    reports: "报告"
  };
  return labels[name || ""] || formatNullable(name, "任务步骤");
}

function statusLabel(status?: string): string {
  const labels: Record<string, string> = {
    pending: "等待中",
    running: "执行中",
    success: "成功",
    failed: "失败",
    skipped: "已跳过",
    idle: "暂无任务"
  };
  return labels[status || ""] || formatNullable(status, "状态暂缺");
}

function tone(status?: string): "good" | "warn" | "bad" | "info" {
  if (status === "success") return "good";
  if (status === "failed") return "bad";
  if (status === "running") return "info";
  return "warn";
}

function rows(status?: RefreshStatus | null) {
  return (status?.steps || []).map((step: RefreshStepStatus) => ({
    ...step,
    step_label: stepLabel(step.step_name),
    status_label: statusLabel(step.status),
    output_count: step.output_files?.length || 0
  }));
}

export function RefreshTaskPanel({ initialStatus, onAfterRefresh }: { initialStatus?: RefreshStatus; onAfterRefresh?: () => void }) {
  const [status, setStatus] = useState<RefreshStatus | null>(initialStatus || null);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState<string | null>(null);

  const refreshStatus = () => {
    setError(null);
    getRefreshStatus().then(setStatus).catch((err: Error) => setError(err.message || "刷新状态暂时无法加载。"));
  };

  const run = (kind: "all" | "market" | "news" | "predictions" | "reports") => {
    setRunning(kind);
    setError(null);
    runRefreshTask(kind)
      .then((payload) => {
        setStatus(payload);
        onAfterRefresh?.();
      })
      .catch((err: Error) => setError(err.message || "刷新任务执行失败。"))
      .finally(() => setRunning(null));
  };

  return (
    <SectionCard
      title="数据刷新任务中心"
      subtitle="一键刷新会依次尝试行情、新闻、事件、特征、预测和报告；失败步骤会保留原因，不会伪造数据。"
      actions={
        <div className="button-row">
          <button className="primary-button" type="button" onClick={() => run("all")} disabled={Boolean(running)}>
            一键刷新数据
          </button>
          <button className="ghost-button" type="button" onClick={refreshStatus}>
            查看刷新状态
          </button>
        </div>
      }
    >
      {error ? <ErrorState title="刷新任务异常" message={error} actionLabel="重新读取状态" onAction={refreshStatus} /> : null}
      <div className="metric-grid">
        <MetricCard label="任务状态" value={statusLabel(status?.status)} hint={status?.message_zh || "暂无刷新任务记录"} tone={tone(status?.status)} />
        <MetricCard label="任务编号" value={status?.run_id || "暂无任务"} />
        <MetricCard label="开始时间" value={formatDateTime(status?.started_at)} />
        <MetricCard label="完成时间" value={formatDateTime(status?.finished_at)} />
      </div>
      <div className="button-row">
        <button className="ghost-button" type="button" onClick={() => run("market")} disabled={Boolean(running)}>
          刷新行情
        </button>
        <button className="ghost-button" type="button" onClick={() => run("news")} disabled={Boolean(running)}>
          刷新新闻
        </button>
        <button className="ghost-button" type="button" onClick={() => run("predictions")} disabled={Boolean(running)}>
          生成预测
        </button>
        <button className="ghost-button" type="button" onClick={() => run("reports")} disabled={Boolean(running)}>
          生成报告
        </button>
        {running ? <StatusPill label="任务执行中，请稍候" tone="info" /> : null}
      </div>
      <DataTable
        data={rows(status) as Array<Record<string, unknown>>}
        emptyLabel="暂无刷新步骤记录，请点击一键刷新数据。"
        columns={[
          { key: "step_label", title: "步骤" },
          { key: "status_label", title: "状态", format: "status" },
          { key: "message_zh", title: "说明", render: (row) => formatNullable(row.message_zh, "本步骤暂无说明") },
          { key: "duration_seconds", title: "耗时(秒)", render: (row) => formatNumber(row.duration_seconds as number | null | undefined, 2) },
          { key: "output_count", title: "输出文件数", format: "number" },
          { key: "error", title: "错误", render: (row) => formatNullable(row.error, "无") }
        ]}
      />
    </SectionCard>
  );
}
