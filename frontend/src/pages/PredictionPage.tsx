import { useCallback, useState } from "react";
import type { PageKey } from "../App";
import { getActiveAbsenceDiagnostics, getForecastPath, refreshAll, refreshPredictions } from "../api/terminal";
import type { ActiveAbsenceDiagnosticsPayload, ForecastPathPayload, PredictionCard as PredictionCardType, TerminalSnapshot } from "../api/types";
import { ForecastPathChart } from "../components/charts/ForecastPathChart";
import { EmptyState } from "../components/common/EmptyState";
import { ErrorBoundary } from "../components/common/ErrorBoundary";
import { StatusPill } from "../components/common/StatusPill";
import { SectionCard } from "../components/layout/SectionCard";
import { PredictionGrid } from "../components/prediction/PredictionGrid";
import { usePolling } from "../hooks/usePolling";

const GROUPS = [
  { key: "intraday", label: "日内", match: ["5", "15", "30", "小时", "hour", "5m", "15m", "30m"] },
  { key: "1d", label: "1日", match: ["1日", "下一交易日", "tomorrow"] },
  { key: "3d", label: "3日", match: ["3日", "3d"] },
  { key: "5d", label: "5日", match: ["5日", "5d"] },
  { key: "10d", label: "10日", match: ["10日", "1-2周", "10d", "week"] },
  { key: "20d", label: "20日", match: ["20日", "20d"] },
  { key: "trend", label: "趋势", match: ["1-3个月", "趋势", "month", "three"] }
];

function cardText(card: PredictionCardType): string {
  return `${card.horizon || ""} ${card.horizon_zh || ""}`.toLowerCase();
}

function filterCards(predictions: PredictionCardType[], group: string): PredictionCardType[] {
  if (group === "all") return predictions;
  const spec = GROUPS.find((item) => item.key === group);
  if (!spec) return predictions;
  const filtered = predictions.filter((card) => spec.match.some((needle) => cardText(card).includes(needle.toLowerCase())));
  return filtered.length ? filtered : predictions;
}

export function PredictionPage({
  snapshot,
  onNavigate,
  onRefresh,
  showSampleData = true
}: {
  snapshot?: TerminalSnapshot | null;
  onNavigate?: (page: PageKey) => void;
  onRefresh?: () => void;
  showSampleData?: boolean;
}) {
  const [group, setGroup] = useState("all");
  const [taskMessage, setTaskMessage] = useState("");
  const forecastLoader = useCallback(() => getForecastPath(), []);
  const activeAbsenceLoader = useCallback(() => getActiveAbsenceDiagnostics(), []);
  const { data: forecastPath, refresh: refreshForecastPath } = usePolling<ForecastPathPayload>(forecastLoader, 60000);
  const { data: activeAbsence } = usePolling<ActiveAbsenceDiagnosticsPayload>(activeAbsenceLoader, 60000);
  const predictions = snapshot?.predictions || [];
  const hasActive = Boolean(snapshot?.model_health?.active_model);
  const visibleForecastPath = forecastPath?.sample_mode && !showSampleData ? { ...forecastPath, points: [] } : forecastPath;
  const visible = filterCards(predictions, group);
  const candidateReasons = snapshot?.model_health?.failure_reasons || snapshot?.learning_status?.failure_reasons || [];

  async function runDataRefresh() {
    setTaskMessage("正在刷新真实数据...");
    const result = await refreshAll();
    setTaskMessage(result.message_zh || "刷新任务已完成。");
    onRefresh?.();
    void refreshForecastPath();
  }

  async function runActivePredictionRefresh() {
    if (!hasActive) {
      setTaskMessage("暂无通过 promotion gate 的 active model，未生成客户预测。");
      return;
    }
    setTaskMessage("正在刷新 active prediction...");
    const result = await refreshPredictions();
    setTaskMessage(result.message_zh || "active prediction 刷新完成。");
    onRefresh?.();
    void refreshForecastPath();
  }

  return (
    <div className="page-stack">
      <SectionCard
        title="预测观察"
        subtitle="只展示通过 promotion gate 的真实 active prediction；不显示 baseline，不默认展示交易点位。"
      >
        <div className="notice-card">
          <strong>{hasActive ? "Active model 已存在" : "暂无通过 promotion gate 的 active model"}</strong>
          <p>
            {hasActive
              ? "本页仅观察 active model 输出；研究 candidate、OOF 和回测请到模型研究与回测验证页。"
              : "最近 candidate 未通过严格 promotion gate，因此不生成客户预测。请查看模型研究、回测验证和数据覆盖。"}
          </p>
          {candidateReasons.length ? (
            <p>最近失败原因：{candidateReasons.slice(0, 4).join("；")}</p>
          ) : null}
          {!hasActive && activeAbsence?.root_causes?.length ? (
            <div className="compact-stack" data-testid="active-absence-diagnostics">
              <strong>Why no active model</strong>
              {activeAbsence.root_causes.slice(0, 4).map((cause) => (
                <span key={`${cause.category}-${cause.severity}`}>
                  {cause.severity || "P1"} / {cause.category}: {cause.evidence}
                </span>
              ))}
              <span>candidate_v6 plan: {activeAbsence.candidate_v6_plan?.status || "research_plan_only"}</span>
            </div>
          ) : null}
        </div>
        <div className="button-row">
          <button className="primary-button" type="button" onClick={() => void runDataRefresh()}>
            一键刷新数据
          </button>
          <button className="ghost-button" type="button" onClick={() => void runActivePredictionRefresh()} disabled={!hasActive}>
            生成预测（active only）
          </button>
          <button className="ghost-button" type="button" onClick={() => onRefresh?.()}>
            刷新终端快照
          </button>
          <button className="ghost-button" type="button" onClick={() => onNavigate?.("research")}>
            查看模型研究
          </button>
          <button className="ghost-button" type="button" onClick={() => onNavigate?.("governance")}>
            查看模型治理
          </button>
          <button className="ghost-button" type="button" onClick={() => onNavigate?.("backtest")}>
            查看回测验证
          </button>
          <button className="ghost-button" type="button" onClick={() => onNavigate?.("factors")}>
            查看数据覆盖
          </button>
          <button className="ghost-button" type="button" onClick={() => onNavigate?.("data")}>
            查看数据源状态
          </button>
          <button className="ghost-button" type="button" onClick={() => onNavigate?.("settings")}>
            设置与诊断
          </button>
          <button className="ghost-button" type="button" onClick={() => onNavigate?.("settings")}>
            前往设置
          </button>
          <button className="ghost-button" type="button" onClick={() => onNavigate?.("data")}>
            查看运行期诊断
          </button>
          {taskMessage ? <StatusPill label={taskMessage} tone="info" /> : null}
        </div>
      </SectionCard>

      <SectionCard title="七周期预测" subtitle="如果没有 active model，本区保持明确空状态，不展示样例或非 active 输出。">
        <div className="horizon-tabs" role="tablist" aria-label="预测周期分组">
          <button className={group === "all" ? "active" : ""} role="tab" aria-selected={group === "all"} type="button" onClick={() => setGroup("all")}>
            全部
          </button>
          {GROUPS.map((item) => (
            <button
              className={group === item.key ? "active" : ""}
              key={item.key}
              role="tab"
              aria-selected={group === item.key}
              type="button"
              onClick={() => setGroup(item.key)}
            >
              {item.label}
            </button>
          ))}
        </div>
        <ErrorBoundary moduleName="七周期预测卡片">
          {hasActive && predictions.length ? (
            <PredictionGrid predictions={visible} />
          ) : (
            <div className="empty-action-panel">
              <EmptyState label="暂无可用预测结果。请检查数据源配置、模型状态或运行预测任务。" />
            </div>
          )}
        </ErrorBoundary>
      </SectionCard>
      <SectionCard title="预测路径与区间" subtitle="无 active prediction 时不绘制伪路径；有 active 时才展示真实路径。">
        <ErrorBoundary moduleName="预测路径图">
          {hasActive ? (
            <ForecastPathChart forecastPath={visibleForecastPath} />
          ) : (
            <EmptyState label="暂无 active prediction path；请先让 candidate 通过 promotion gate 并经过人工审批。" />
          )}
        </ErrorBoundary>
      </SectionCard>
    </div>
  );
}
