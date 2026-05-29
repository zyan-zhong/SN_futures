import type { PredictionCard as PredictionCardType } from "../../api/types";
import {
  formatNumber,
  formatPercent,
  formatRange,
  formatSignal,
  formatSignalStrength
} from "../../utils/format";
import { hasTradePoints, isDegraded, isLowQuality } from "../../utils/guards";
import { CollapsibleDebug } from "../common/CollapsibleDebug";
import { StatusPill } from "../common/StatusPill";
import { SignalBadge } from "./SignalBadge";

function listOrFallback(items: string[] | undefined, fallback: string): string[] {
  return items?.length ? items : [fallback];
}

function backtestSummaryText(value: PredictionCardType["backtest_summary"]): string {
  if (!value || !Object.keys(value).length) return "回测摘要暂缺";
  const pieces = Object.entries(value)
    .slice(0, 5)
    .map(([key, item]) => `${key}：${typeof item === "number" ? formatNumber(item, 3) : String(item)}`);
  return pieces.join("；");
}

export function PredictionCard({ card }: { card: PredictionCardType }) {
  const degraded = isDegraded(card.model_status);
  const lowQuality = isLowQuality(card.data_quality);
  const tradePointsVisible = hasTradePoints(card);
  const signal = formatSignal(card.signal);
  const strength = formatSignalStrength(card.signal, card.confidence_score);
  const tone = signal.includes("多头") ? "long-card" : signal.includes("空头") ? "short-card" : "neutral-card";
  const calibrated = typeof card.calibrated_prob_up === "number" ? card.calibrated_prob_up : null;
  const neutralZone = calibrated !== null && calibrated >= 0.45 && calibrated <= 0.55;

  return (
    <article className={`prediction-card ${tone}`}>
      <div className="prediction-card-head">
        <div>
          <span className="eyebrow">{card.horizon_zh || card.horizon || "周期"}</span>
          <h3>{card.direction || "观望"}</h3>
        </div>
        <SignalBadge signal={card.signal} />
      </div>

      <div className="probability-row">
        <div>
          <span>校准后上涨概率</span>
          <strong>{formatPercent(card.calibrated_prob_up)}</strong>
        </div>
        <div>
          <span>原始概率</span>
          <strong>{formatPercent(card.raw_prob_up)}</strong>
        </div>
        <div>
          <span>置信度</span>
          <strong>{formatPercent(card.confidence_score)}</strong>
        </div>
      </div>

      <div className="probability-bar" aria-label="上涨概率条">
        <span className="neutral-zone" />
        <span className="probability-fill" style={{ width: `${Math.max(0, Math.min(100, (calibrated ?? 0) * 100))}%` }} />
      </div>
      <p className="muted probability-caption">{neutralZone ? "方向不明确：概率位于 45%–55% 中性区间。" : "概率条用于观察方向倾向，不代表确定性结论。"}</p>

      <div className="tag-strip">
        <StatusPill label={`信号强度 ${strength}`} tone={strength === "强" ? "good" : strength === "数据不足" ? "warn" : "info"} />
        <StatusPill label={`预测收益 ${formatPercent(card.expected_return)}`} tone="info" />
        <StatusPill label={`Trade Edge ${formatPercent(card.trade_edge)}`} tone={typeof card.trade_edge === "number" && card.trade_edge > 0 ? "good" : "warn"} />
        <StatusPill label={`数据质量 ${formatPercent(card.data_quality)}`} tone={lowQuality ? "bad" : "good"} />
        <StatusPill label={degraded ? "已降级为研究观察" : card.model_status || "模型状态待验证"} tone={degraded ? "warn" : "info"} />
      </div>

      <div className="price-band">
        <span>预测区间</span>
        <strong>{formatRange(card.predicted_range)}</strong>
      </div>

      <div className="trade-points">
        <h4>研究观察点位</h4>
        {tradePointsVisible ? (
          <>
            <div className="trade-point-grid">
              <span>入场观察：{formatNumber(card.entry, 0)}</span>
              <span>风险失效：{formatNumber(card.stop_loss, 0)}</span>
              <span>目标观察：{formatNumber(card.take_profit, 0)}</span>
            </div>
            <p className="muted">非交易建议，仅作投研观察。</p>
          </>
        ) : (
          <p>暂无交易点位。{lowQuality ? "数据质量不足，已降级为研究观察。" : degraded ? "模型已降级为研究观察。" : "当前信号不满足点位输出条件。"} 非交易建议，仅作投研观察。</p>
        )}
      </div>

      <details className="info-collapse">
        <summary>决策说明</summary>
        <p>{card.decision_explanation || "方向优势仍在验证中，当前以研究观察为主。"}</p>
      </details>

      <details className="info-collapse">
        <summary>因子明细</summary>
        <ul>
          {listOrFallback(card.top_factors, "核心因子暂缺").slice(0, 6).map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </details>

      <details className="info-collapse">
        <summary>事件依据</summary>
        <ul>
          {listOrFallback(card.event_evidence, "暂无高权重入模事件").slice(0, 6).map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </details>

      <details className="info-collapse">
        <summary>回测摘要</summary>
        <p>{backtestSummaryText(card.backtest_summary)}</p>
      </details>

      <div className="risk-notes">
        {listOrFallback(card.risk_notes, "预测可能存在误差、延迟或失效风险。").slice(0, 3).map((item) => (
          <span key={item}>{item}</span>
        ))}
      </div>

      <div className="path-guard">路径守门：{card.path_guard_summary || "等待路径守门验证"}</div>
      <CollapsibleDebug data={card} />
    </article>
  );
}

