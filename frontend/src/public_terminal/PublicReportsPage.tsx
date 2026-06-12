import { useEffect, useState } from "react";
import { getPublicReport } from "./api";
import { EventSummary } from "./components/EventSummary";
import type { PublicReportPayload } from "./types";
import { friendlyReason, friendlyStatus, technicalSummary } from "./userCopy";

export function PublicReportsPage() {
  const [payload, setPayload] = useState<PublicReportPayload | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    getPublicReport().then(setPayload).catch((exc) => setError(exc instanceof Error ? exc.message : "报告暂不可用。"));
  }, []);

  const report = payload?.report;
  const exportAllowed = Boolean(report?.export_allowed);
  const eventSummary = report?.event_summary;
  const eventSection = report?.event_section || eventSummary;

  function handleExport() {
    if (!exportAllowed) return;
    setMessage("报告导出已准备好；未生成预测、训练或回测。");
  }

  return (
    <div className="page-stack public-terminal-page">
      <section className="section-card">
        <div className="section-card__header">
          <div>
            <h1>报告</h1>
            <p>报告只说明数据覆盖情况，不会给出买卖指令。</p>
          </div>
          <button className="primary-button" type="button" disabled={!exportAllowed} onClick={handleExport}>
            导出报告
          </button>
        </div>
        <div className="metric-grid compact">
          <div className="metric-card">
            <span className="metric-label">当前状态</span>
            <strong>{friendlyStatus(report?.status)}</strong>
            <small>{error || friendlyReason(report?.reason, "数据不足")}</small>
          </div>
          <div className="metric-card">
            <span className="metric-label">市场数据</span>
            <strong>{report?.market_data_coverage === "empty" ? "数据不足" : "已有覆盖"}</strong>
            <small>缺少数据时导出会保持关闭。</small>
          </div>
          <div className="metric-card">
            <span className="metric-label">事件数据</span>
            <strong>{report?.event_coverage === "empty" ? "数据不足" : "已有覆盖"}</strong>
            <small>{Number(eventSummary?.eligible_count || 0)} usable / {Number(eventSummary?.rejected_count || 0)} excluded</small>
          </div>
          <div className="metric-card">
            <span className="metric-label">暂无真实预测</span>
            <strong>未生成</strong>
            <small>仅供研究参考，不用于自动交易。</small>
          </div>
        </div>
        {message ? <p role="status" className="inline-warning">{message}</p> : null}
      </section>

      <section className="section-card">
        <div className="section-card__header">
          <div>
            <h2>Event Summary</h2>
            <p>News, policy, exchange notices, and supply-chain events are counted by provenance and SHFE SN relevance.</p>
          </div>
          <span className="status-pill">{friendlyStatus(report?.event_coverage === "ready" ? "ready" : "blocked")}</span>
        </div>
        <EventSummary dataTestId="report-event-summary-section" summary={eventSection} />
      </section>

      <section className="guided-empty-state">
        <header>
          <strong>{report?.status === "success" || report?.status === "ready" ? "报告可查看" : "数据不足"}</strong>
          <span>下一步：先完成数据源检查和数据完整度刷新。</span>
        </header>
      </section>

      <details className="technical-details-drawer">
        <summary>诊断详情</summary>
        <pre className="diagnostics-pre">
{`report payload / coverage
${technicalSummary(payload)}`}
        </pre>
      </details>
    </div>
  );
}
