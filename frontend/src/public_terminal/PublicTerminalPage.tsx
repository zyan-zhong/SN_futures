import { useEffect, useState } from "react";
import { getPublicReadiness } from "./api";
import type { PublicReadinessPayload } from "./types";
import { friendlyNextAction, friendlyReason, friendlyStatus, technicalSummary } from "./userCopy";
import { PredictionStatusPanel } from "./components/PredictionStatusPanel";

export function PublicTerminalPage() {
  const [readiness, setReadiness] = useState<PublicReadinessPayload | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    getPublicReadiness()
      .then((payload) => {
        if (!cancelled) setReadiness(payload);
      })
      .catch((exc) => {
        if (!cancelled) setError(exc instanceof Error ? exc.message : "服务暂不可用");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const firstReason = readiness?.blocking_reasons?.[0] || readiness?.data_watermark?.reason;
  const predictionCore = readiness?.prediction_core_readiness;
  const canPredict = Boolean(predictionCore?.can_predict);

  return (
    <div className="page-stack public-terminal-page">
      <section className="section-card">
        <div className="section-card__header">
          <div>
            <h1>当前状态</h1>
            <p>这里显示客户终端现在能做什么，以及下一步点哪里。</p>
          </div>
        </div>
        <div className="metric-grid compact">
          <div className="metric-card">
            <span className="metric-label">数据源检查</span>
            <strong>{readiness?.provider_smoke_passed ? "已通过" : "需要检查"}</strong>
            <small>{error || friendlyReason(firstReason)}</small>
          </div>
          <div className="metric-card">
            <span className="metric-label">数据完整度</span>
            <strong>{friendlyStatus(readiness?.data_watermark?.status ?? readiness?.status)}</strong>
            <small>{friendlyReason(readiness?.data_watermark?.reason ?? firstReason)}</small>
          </div>
          <div className="metric-card">
            <span className="metric-label">预测准备</span>
            <strong>{canPredict ? "证据已就绪" : "暂无真实预测"}</strong>
            <small>{canPredict ? "只显示准备状态，尚不生成预测值。" : "缺少模型发布、校验记录或最新数据证据。"}</small>
          </div>
          <div className="metric-card">
            <span className="metric-label">下一步</span>
            <strong>{friendlyNextAction(readiness?.next_action)}</strong>
            <small>可以先配置 key，也可以稍后再配置。</small>
          </div>
        </div>
      </section>

      <PredictionStatusPanel />

      <section className="guided-empty-state">
        <header>
          <strong>为什么没有预测</strong>
          <span>系统还没有拿到足够真实数据。为了避免误导，预测区会保持为空。</span>
        </header>
        <div className="guided-empty-state__grid">
          <div>
            <strong>现在可以做</strong>
            <ul>
              <li>在 Setup 配置数据源 key，或选择稍后配置。</li>
              <li>运行数据源检查，确认 key 和数据接口可用。</li>
              <li>到 Data Status 查看数据完整度。</li>
            </ul>
          </div>
          <div>
            <strong>失败怎么办</strong>
            <p>先看页面上的下一步；如果仍不清楚，再打开 Diagnostics 复制诊断信息。</p>
          </div>
        </div>
      </section>

      <details className="technical-details-drawer">
        <summary>诊断详情</summary>
        <pre className="diagnostics-pre">
{`provider smoke / data watermark / manifest
${technicalSummary(readiness)}`}
        </pre>
      </details>
    </div>
  );
}
