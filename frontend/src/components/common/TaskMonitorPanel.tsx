import { useEffect, useState } from "react";
import { cancelTerminalTask, getRecentTerminalTasks, getTerminalTaskStatus } from "../../api/terminal";
import type { TerminalTaskStatus } from "../../api/types";
import { formatDateTime, formatNullable } from "../../utils/format";
import { StatusPill } from "./StatusPill";

function tone(status?: string): "good" | "warn" | "bad" | "info" {
  if (status === "success") return "good";
  if (status === "failed") return "bad";
  if (status === "cancel_requested") return "warn";
  if (status === "running" || status === "queued") return "info";
  return "warn";
}

function statusLabel(status?: string): string {
  const labels: Record<string, string> = {
    queued: "排队中",
    running: "执行中",
    success: "已完成",
    failed: "失败",
    cancel_requested: "取消中",
    not_found: "未找到",
    missing: "缺少 ID"
  };
  return labels[status || ""] || formatNullable(status, "暂无任务");
}

export function TaskMonitorPanel({
  taskId,
  title = "后台任务",
  onComplete
}: {
  taskId?: string;
  title?: string;
  onComplete?: () => void;
}) {
  const [currentTaskId, setCurrentTaskId] = useState(taskId || "");
  const [task, setTask] = useState<TerminalTaskStatus | null>(null);
  const [recent, setRecent] = useState<TerminalTaskStatus[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    if (taskId) setCurrentTaskId(taskId);
  }, [taskId]);

  useEffect(() => {
    let cancelled = false;

    const loadRecent = () => {
      getRecentTerminalTasks(5)
        .then((payload) => {
          if (!cancelled) setRecent(payload.tasks || []);
        })
        .catch((err: Error) => {
          if (!cancelled) setError(err.message);
        });
    };

    loadRecent();
    const recentTimer = window.setInterval(loadRecent, 10000);
    return () => {
      cancelled = true;
      window.clearInterval(recentTimer);
    };
  }, []);

  useEffect(() => {
    if (!currentTaskId) return;
    let cancelled = false;

    const poll = () => {
      getTerminalTaskStatus(currentTaskId)
        .then((payload) => {
          if (cancelled) return;
          setTask(payload);
          if (payload.status === "success" || payload.status === "failed" || payload.status === "cancel_requested") {
            onComplete?.();
          }
        })
        .catch((err: Error) => {
          if (!cancelled) setError(err.message);
        });
    };

    poll();
    const timer = window.setInterval(poll, 2000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [currentTaskId, onComplete]);

  const visibleTask = task || recent[0] || null;

  return (
    <section className="task-monitor-panel" aria-label={title}>
      <div className="task-monitor-header">
        <div>
          <strong>{title}</strong>
          <span>长任务在后台执行，页面通过状态轮询更新。</span>
        </div>
        <StatusPill label={statusLabel(visibleTask?.status)} tone={tone(visibleTask?.status)} />
      </div>

      {error ? <p className="inline-error">{error}</p> : null}

      <div className="task-monitor-grid">
        <span>任务</span>
        <strong>{visibleTask?.kind || "暂无任务"}</strong>
        <span>进度</span>
        <strong>{visibleTask?.progress ?? 0}%</strong>
        <span>开始</span>
        <strong>{formatDateTime(visibleTask?.started_at)}</strong>
        <span>说明</span>
        <strong>{visibleTask?.message_zh || "等待任务状态。"}</strong>
      </div>

      {visibleTask?.error_message_zh ? <p className="inline-error">{visibleTask.error_message_zh}</p> : null}

      <div className="button-row">
        {visibleTask?.task_id ? (
          <button className="ghost-button" type="button" onClick={() => setCurrentTaskId(visibleTask.task_id || "")}>
            追踪任务
          </button>
        ) : null}
        {visibleTask?.task_id && ["queued", "running"].includes(String(visibleTask.status)) ? (
          <button className="ghost-button" type="button" onClick={() => cancelTerminalTask(visibleTask.task_id || "").then(setTask)}>
            取消
          </button>
        ) : null}
      </div>
    </section>
  );
}
