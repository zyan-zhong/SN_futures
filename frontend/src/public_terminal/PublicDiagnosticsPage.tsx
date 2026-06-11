import { useState } from "react";
import { getPublicReadiness } from "./api";
import { technicalSummary } from "./userCopy";

export function PublicDiagnosticsPage() {
  const [details, setDetails] = useState("尚未生成诊断信息。");
  const [message, setMessage] = useState("");

  async function loadDiagnostics() {
    try {
      const readiness = await getPublicReadiness();
      const text = technicalSummary({
        readiness,
        note: "No raw key is included in this public diagnostic view."
      });
      setDetails(text);
      setMessage("诊断信息已更新，可以复制给支持人员。");
    } catch (exc) {
      setMessage(exc instanceof Error ? exc.message : "诊断信息暂不可用。");
    }
  }

  async function copyDiagnostics() {
    try {
      await navigator.clipboard?.writeText(details);
      setMessage("已复制诊断信息。");
    } catch {
      setMessage("浏览器不允许复制；请手动选中文本。");
    }
  }

  return (
    <div className="page-stack public-terminal-page">
      <section className="section-card">
        <div className="section-card__header">
          <div>
            <h1>诊断</h1>
            <p>这里用于排查失败原因，不会显示 key 原文。</p>
          </div>
        </div>
        <div className="button-row">
          <button className="primary-button" type="button" onClick={() => void loadDiagnostics()}>
            更新诊断信息
          </button>
          <button className="secondary-button" type="button" onClick={() => void copyDiagnostics()}>
            复制诊断信息
          </button>
        </div>
        <pre className="diagnostics-pre" aria-label="可复制诊断信息">{details}</pre>
        {message ? <p role="status" className="inline-warning">{message}</p> : null}
      </section>

      <details className="technical-details-drawer">
        <summary>诊断详情</summary>
        <p>provider / smoke / watermark / manifest 等技术字段只在这里展开查看。</p>
      </details>
    </div>
  );
}
