import { useEffect, useState } from "react";
import { getPublicReadiness, getPublicTask, startPublicDataRefresh } from "./api";
import type { PublicReadinessPayload, PublicTaskPayload } from "./types";
import { friendlyNextAction, friendlyReason, friendlyStatus, technicalSummary } from "./userCopy";

export function PublicDataStatusPage() {
  const [readiness, setReadiness] = useState<PublicReadinessPayload | null>(null);
  const [task, setTask] = useState<PublicTaskPayload | null>(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  async function reloadReadiness() {
    setReadiness(await getPublicReadiness());
  }

  useEffect(() => {
    reloadReadiness().catch(() => setMessage("暂时无法读取数据完整度。"));
  }, []);

  useEffect(() => {
    if (!task?.task_id || !["queued", "running"].includes(String(task.status))) return undefined;
    const timer = window.setInterval(() => {
      getPublicTask(task.task_id || "")
        .then((payload) => {
          setTask(payload);
          if (!["queued", "running"].includes(String(payload.status))) {
            window.clearInterval(timer);
            void reloadReadiness();
          }
        })
        .catch(() => undefined);
    }, 1200);
    return () => window.clearInterval(timer);
  }, [task?.task_id, task?.status]);

  async function refreshStatus() {
    setBusy(true);
    setMessage("");
    try {
      const payload = await startPublicDataRefresh();
      setTask(payload);
      setMessage("刷新任务已开始。页面会自动更新结果。");
    } catch (exc) {
      setMessage(exc instanceof Error ? exc.message : "刷新失败，请先完成数据源检查。");
    } finally {
      setBusy(false);
    }
  }

  const reason = task?.reason || readiness?.data_watermark?.reason || readiness?.blocking_reasons?.[0];

  return (
    <div className="page-stack public-terminal-page">
      <section className="section-card">
        <div className="section-card__header">
          <div>
            <h1>数据完整度</h1>
            <p>这里查看真实或缓存数据是否足够展示市场页和报告页。</p>
          </div>
          <button className="primary-button" type="button" disabled={busy} onClick={() => void refreshStatus()}>
            刷新数据状态
          </button>
        </div>
        <div className="metric-grid compact">
          <div className="metric-card">
            <span className="metric-label">当前状态</span>
            <strong>{friendlyStatus(task?.status ?? readiness?.data_watermark?.status ?? readiness?.status)}</strong>
            <small>{friendlyReason(reason)}</small>
          </div>
          <div className="metric-card">
            <span className="metric-label">下一步</span>
            <strong>{friendlyNextAction(readiness?.next_action)}</strong>
            <small>没有数据时不会假装成功。</small>
          </div>
          <div className="metric-card">
            <span className="metric-label">暂无真实预测</span>
            <strong>未生成</strong>
            <small>刷新数据状态不会训练、预测或回测。</small>
          </div>
        </div>
        {message ? <p role="status" className="inline-warning">{message}</p> : null}
      </section>

      <details className="technical-details-drawer">
        <summary>诊断详情</summary>
        <pre className="diagnostics-pre">
{`watermark / task result
${technicalSummary({ readiness, task })}`}
        </pre>
      </details>
    </div>
  );
}
