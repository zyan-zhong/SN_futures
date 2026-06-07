import { getJson, postJson } from "./client";
import type { TaskNotificationsPayload, TerminalTaskList, TerminalTaskStatus } from "./types/tasks";

export function startTerminalTask(kind: string, payload: Record<string, unknown> = {}) {
  return postJson<TerminalTaskStatus>("/api/terminal/tasks/start", { ...payload, kind }, { timeoutMs: 30000 });
}

export function getTerminalTaskStatus(taskId: string) {
  return getJson<TerminalTaskStatus>(`/api/terminal/tasks/status?id=${encodeURIComponent(taskId)}`, { timeoutMs: 5000, dedupe: false });
}

export function getRecentTerminalTasks(limit = 20) {
  return getJson<TerminalTaskList>(`/api/terminal/tasks/recent?limit=${encodeURIComponent(String(limit))}`, { timeoutMs: 5000, dedupe: false });
}

export function getTaskNotifications(limit = 20) {
  return getJson<TaskNotificationsPayload>(`/api/terminal/task-notifications?limit=${encodeURIComponent(String(limit))}`, { timeoutMs: 5000, dedupe: false });
}

export function cancelTerminalTask(taskId: string) {
  return postJson<TerminalTaskStatus>(`/api/terminal/tasks/cancel?id=${encodeURIComponent(taskId)}`, {}, { timeoutMs: 5000 });
}
