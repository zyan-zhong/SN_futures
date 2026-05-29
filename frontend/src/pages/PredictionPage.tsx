import { useCallback, useState } from "react";
import type { PageKey } from "../App";
import { getForecastPath, refreshAll, refreshPredictions } from "../api/terminal";
import type { ForecastPathPayload, PredictionCard as PredictionCardType, TerminalSnapshot } from "../api/types";
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
  const { data: forecastPath, refresh: refreshForecastPath } = usePolling<ForecastPathPayload>(forecastLoader, 60000);
  const predictions = snapshot?.predictions || [];
  const visibleForecastPath = forecastPath?.sample_mode && !showSampleData ? { ...forecastPath, points: [] } : forecastPath;
  const visible = filterCards(predictions, group);

  async function runPredictionRefresh(kind: "all" | "predictions") {
    setTaskMessage(kind === "all" ? "正在执行一键刷新数据..." : "正在生成预测...");
    const result = kind === "all" ? await refreshAll() : await refreshPredictions();
    setTaskMessage(result.message_zh || "刷新任务已完成。");
    onRefresh?.();
    void refreshForecastPath();
  }

  return (
    <div className="page-stack">
      <SectionCard title="七周期预测" subtitle="按周期查看方向、概率、收益、风险、事件证据和路径守门。">
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
          {predictions.length ? (
            <PredictionGrid predictions={visible} />
          ) : (
            <div className="empty-action-panel">
              <EmptyState label="暂无可用预测结果。请检查数据源配置、模型状态或运行预测任务。" />
              <div className="button-row">
                <button className="primary-button" type="button" onClick={() => void runPredictionRefresh("all")}>
                  一键刷新数据
                </button>
                <button className="ghost-button" type="button" onClick={() => void runPredictionRefresh("predictions")}>
                  生成预测
                </button>
                <button className="ghost-button" type="button" onClick={() => window.location.reload()}>
                  刷新终端快照
                </button>
                <button className="ghost-button" type="button" onClick={() => onNavigate?.("settings")}>
                  前往设置
                </button>
                <button className="ghost-button" type="button" onClick={() => onNavigate?.("data")}>
                  查看数据源状态
                </button>
                <button className="ghost-button" type="button" onClick={() => onNavigate?.("governance")}>
                  查看模型治理
                </button>
                <button className="ghost-button" type="button" onClick={() => onNavigate?.("data")}>
                  查看运行期诊断
                </button>
              </div>
              {taskMessage ? <StatusPill label={taskMessage} tone="info" /> : null}
            </div>
          )}
        </ErrorBoundary>
      </SectionCard>
      <SectionCard title="预测路径与区间" subtitle="直接读取 /api/terminal/charts/forecast-path；无预测时不画伪路径。">
        <ErrorBoundary moduleName="预测路径图">
          <ForecastPathChart forecastPath={visibleForecastPath} />
        </ErrorBoundary>
      </SectionCard>
    </div>
  );
}
