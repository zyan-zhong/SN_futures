import { useEffect, useMemo, useState } from "react";
import { getPublicPredictionStatus } from "../api";
import type { PublicPredictionStatusPayload } from "../types";

function statusLabel(status?: string) {
  if (status === "ready_to_predict") return "证据就绪";
  if (status === "skipped") return "等待资源";
  return "暂不预测";
}

function reasonLabel(payload: PublicPredictionStatusPayload | null, error: string) {
  if (error) return "状态暂时不可用";
  const status = payload?.prediction_status;
  if (status?.status === "ready_to_predict") return "数据、模型发布和校验记录已通过。";
  if (status?.reason === "rate_limited") return "刷新过于频繁，稍后会再次检查。";
  if (status?.reason === "resource_busy") return "本机资源正忙，稍后会再次检查。";
  if (status?.blocking_reasons?.length) return "仍有数据或模型证据缺口。";
  return "等待数据和模型证据。";
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
  const label = useMemo(() => statusLabel(status?.status), [status?.status]);
  const reason = reasonLabel(payload, error);
  const nextCheck = status?.next_allowed_at || status?.checked_at || "";

  return (
    <section className="section-card prediction-status-panel" aria-label="预测状态">
      <div className="section-card__header">
        <div>
          <h2>预测状态</h2>
          <p>{reason}</p>
        </div>
        <span className={`status-pill ${status?.status === "ready_to_predict" ? "ok" : "warn"}`}>{label}</span>
      </div>
      <div className="status-strip">
        <span>自动检查</span>
        <strong>{status?.dry_run ? "只读" : "待启动"}</strong>
        <span>{nextCheck ? `最近检查 ${nextCheck}` : "尚未检查"}</span>
      </div>
    </section>
  );
}
