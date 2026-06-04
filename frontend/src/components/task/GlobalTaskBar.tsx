import { useEffect, useState } from "react";
import { getTaskNotifications } from "../../api/terminal";
import type { TaskNotificationsPayload, TerminalTaskStatus } from "../../api/types";
import { formatStatusLabel, getStatusTone } from "../../utils/statusTaxonomy";
import { StatusPill } from "../common/StatusPill";

function tone(status?: string): "good" | "warn" | "bad" | "info" {
  return getStatusTone(status) === "neutral" ? "warn" : getStatusTone(status) as "good" | "warn" | "bad" | "info";
}

function label(status?: string) {
  if (status === "running") return "运行中";
  if (status === "queued") return "排队中";
  if (status === "success") return formatStatusLabel("pass");
  if (status === "failed") return formatStatusLabel("fail");
  return "空闲";
}

export function GlobalTaskBar() {
  const [notifications, setNotifications] = useState<TaskNotificationsPayload | null>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;

    const load = () => {
      getTaskNotifications(8)
        .then((payload) => {
          if (!cancelled) setNotifications(payload);
        })
        .catch(() => {
          if (!cancelled) setNotifications(null);
        });
    };

    load();
    const timer = window.setInterval(load, 8000);
    window.addEventListener("setup-action-completed", load);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
      window.removeEventListener("setup-action-completed", load);
    };
  }, []);

  const task = notifications?.toast_task ?? null;
  const centerTasks = notifications?.notification_center?.tasks ?? [];
  const latestFailed = notifications?.latest_failed_task ?? null;
  const setup_action_history = notifications?.setup_action_history ?? notifications?.notification_center?.setup_action_history ?? {};
  const latest_action_status = setup_action_history.latest_action_status ?? "not_run";
  const active = task?.status === "running" || task?.status === "queued";
  const staleSuppressed = Boolean(notifications?.stale_failure_suppressed);

  return (
    <aside className="global-task-bar" aria-label="Task Notification Center">
      <button
        aria-controls="task-notification-center-drawer"
        aria-expanded={open}
        aria-label={open ? "Close Task Notification Center" : "Open Task Notification Center"}
        className="global-task-bar__summary"
        type="button"
        onClick={() => setOpen((value) => !value)}
      >
        <StatusPill label={label(task?.status)} tone={tone(task?.status)} />
        <span>{task?.kind || "Task Notification Center"}</span>
        {active ? <em>stale-while-refreshing</em> : null}
        <strong>details</strong>
      </button>
      {open ? (
        <div className="global-task-bar__drawer" id="task-notification-center-drawer" role="region" aria-label="Task Notification Center history">
          <div className="task-notification-center__header">
            <span>Task Notification Center</span>
            <strong>{staleSuppressed ? "stale failure moved to history" : "current task state"}</strong>
          </div>
          <div>
            <span>current toast task</span>
            <strong>{task?.kind || "none"}</strong>
          </div>
          <div>
            <span>progress</span>
            <strong>{task?.progress ?? 0}%</strong>
          </div>
          <p>{task?.message_zh || "No running task. Failed research tasks stay in task history and do not overlay the main workspace."}</p>
          <div className="task-notification-center__setup-actions" tabIndex={0}>
            <span>safe setup action history</span>
            <strong>{setup_action_history.latest_action || "none"} / {formatStatusLabel(latest_action_status)}</strong>
            <p>
              success {setup_action_history.successful_action_count ?? 0} / failed {setup_action_history.failed_action_count ?? 0} / blocked {setup_action_history.blocked_action_count ?? 0}
            </p>
          </div>
          {latestFailed ? (
            <div className="task-notification-center__failed">
              <span>latest failed research task</span>
              <strong>{latestFailed.kind || "task"} / {latestFailed.status || "failed"}</strong>
              <p>{latestFailed.error_message_zh || latestFailed.message_zh || "research task failure recorded in history"}</p>
            </div>
          ) : null}
          <div className="task-notification-center__history">
            <span>task history</span>
            <ul>
              {centerTasks.slice(0, 5).map((item: TerminalTaskStatus) => (
                <li key={item.task_id || `${item.kind}-${item.created_at}`}>
                  <strong>{item.kind || "task"}</strong>
                  <span>{formatStatusLabel(item.status || "missing")}</span>
                  <em>{String(item.payload?.candidate_version || item.payload?.version || "")}</em>
                </li>
              ))}
            </ul>
          </div>
        </div>
      ) : null}
    </aside>
  );
}
