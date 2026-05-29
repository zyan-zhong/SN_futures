import type { PredictionCard as PredictionCardType } from "../../api/types";
import { EmptyState } from "../common/EmptyState";
import { PredictionCard } from "./PredictionCard";

export function PredictionGrid({
  predictions,
  emptyLabel = "暂无可用预测结果。请检查数据源配置、模型状态或运行预测任务。"
}: {
  predictions?: PredictionCardType[];
  emptyLabel?: string;
}) {
  if (!predictions?.length) return <EmptyState label={emptyLabel} />;
  return (
    <div className="prediction-grid">
      {predictions.map((card, index) => (
        <PredictionCard card={card} key={`${card.horizon || "horizon"}-${index}`} />
      ))}
    </div>
  );
}
