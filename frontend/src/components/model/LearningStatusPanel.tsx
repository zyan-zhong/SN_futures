import type { LearningStatus } from "../../api/types";
import { formatDateTime, formatNullable } from "../../utils/format";
import { EmptyState } from "../common/EmptyState";
import { SectionCard } from "../layout/SectionCard";

const rows: Array<[keyof LearningStatus, string]> = [
  ["latest_market_refresh", "最近行情刷新"],
  ["latest_prediction", "最近预测"],
  ["latest_validation", "最近验证"],
  ["latest_calibration", "最近校准"],
  ["latest_candidate_training", "最近候选训练"],
  ["latest_walk_forward", "最近 Walk-forward"],
  ["latest_event_ablation", "最近事件消融"],
  ["latest_promotion_check", "最近晋级检查"],
  ["next_task", "下一次任务"]
];

export function LearningStatusPanel({ status }: { status?: LearningStatus }) {
  if (!status) return <EmptyState label="暂无学习状态数据" />;
  return (
    <SectionCard title="学习与任务状态" subtitle="持续学习只生成候选模型，不绕过晋级门槛">
      <div className="status-table">
        {rows.map(([key, label]) => (
          <div className="status-row" key={key}>
            <span>{label}</span>
            <strong>{key.includes("latest") ? formatDateTime(status[key]) : formatNullable(status[key])}</strong>
          </div>
        ))}
      </div>
      <p className="muted">状态说明：{formatNullable(status.active_candidate_state, "学习状态待验证")}</p>
    </SectionCard>
  );
}
