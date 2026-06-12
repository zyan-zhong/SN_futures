import { useEffect, useMemo, useState } from "react";
import { getPublicPredictionStatus } from "../api";
import type { PublicPredictionStatusPayload } from "../types";

const EVIDENCE_LABELS: Record<string, string> = {
  active_model: "缺少已批准的模型发布",
  data_watermark: "缺少可验证的数据水位",
  intraday_bars: "缺少分钟线数据",
  feature_store: "缺少特征数据证据",
  training_dataset: "缺少训练数据集证据",
  labels: "缺少标签定义",
  walk_forward: "缺少滚动验证记录",
  calibration: "缺少校准记录",
  feature_manifest: "模型数据清单不一致",
  active_release_audit: "缺少发布审计记录",
};

function labelFor(value: string) {
  if (EVIDENCE_LABELS[value]) return EVIDENCE_LABELS[value];
  if (value.endsWith("_rows")) return "可用样本数量不足";
  return "证据不足";
}

function statusLabel(dryRunStatus?: string, status?: string) {
  if (dryRunStatus === "ready_to_predict" || status === "ready_to_predict") return "证据就绪";
  if (dryRunStatus === "resource_busy") return "资源忙";
  if (dryRunStatus === "stale_data") return "数据过期";
  if (status === "skipped") return "稍后检查";
  return "暂不能预测";
}

function reasonLabel(payload: PublicPredictionStatusPayload | null, error: string) {
  if (error) return "实时检查状态暂时不可用。";
  const status = payload?.prediction_status;
  if (status?.dry_run_status === "ready_to_predict" || status?.status === "ready_to_predict") {
    return "只读检查已通过；当前页面仍不会生成或展示预测结果。";
  }
  if (status?.dry_run_status === "resource_busy" || status?.reason === "resource_busy") {
    return "本机资源正忙，系统会稍后再检查。";
  }
  if (status?.dry_run_status === "stale_data" || status?.reason === "stale_data") {
    return "最新数据水位已过期，系统不会展示预测结果。";
  }
  if (status?.reason === "rate_limited") return "检查过于频繁，系统会稍后再检查。";
  if (status?.blocking_reasons?.length) return "仍缺少数据或模型证据，系统不会展示预测结果。";
  return "等待数据、模型证据和资源检查。";
}

function EvidenceList({ items }: { items: string[] }) {
  const uniqueItems = Array.from(new Set(items)).slice(0, 4);
  return (
    <div className="metric-card">
      <span className="metric-label">缺少证据</span>
      {uniqueItems.length ? (
        <ul className="compact-list">
          {uniqueItems.map((item) => (
            <li key={item}>{labelFor(item)}</li>
          ))}
        </ul>
      ) : (
        <strong>暂无缺口</strong>
      )}
    </div>
  );
}

export function PredictionStatusPanel() {
  const [payload, setPayload] = useState<PublicPredictionStatusPayload | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    getPublicPredictionStatus()
      .then((result) => {
        if (!cancelled) setPayload(result);
      })
      .catch(() => {
        if (!cancelled) setError("unavailable");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const status = payload?.prediction_status;
  const label = useMemo(() => statusLabel(status?.dry_run_status, status?.status), [status?.dry_run_status, status?.status]);
  const reason = reasonLabel(payload, error);
  const missingEvidence = status?.missing_evidence ?? [];

  return (
    <section className="section-card prediction-status-panel" aria-label="实时预测检查状态">
      <div className="section-card__header">
        <div>
          <h2>实时预测检查</h2>
          <p>{reason}</p>
        </div>
        <span className={`status-pill ${status?.status === "ready_to_predict" ? "ok" : "warn"}`}>{label}</span>
      </div>
      <div className="metric-grid compact">
        <div className="metric-card">
          <span className="metric-label">能否预测</span>
          <strong>{status?.can_predict ? "可以进入预测检查" : "暂不能预测"}</strong>
          <small>不会显示方向、价格或概率。</small>
        </div>
        <div className="metric-card">
          <span className="metric-label">只读检查</span>
          <strong>{status?.dry_run ? "已启用" : "等待检查"}</strong>
          <small>{status?.next_allowed_at ? `下次检查 ${status.next_allowed_at}` : "不会启动训练或回测。"}</small>
        </div>
        <EvidenceList items={missingEvidence} />
      </div>
    </section>
  );
}
