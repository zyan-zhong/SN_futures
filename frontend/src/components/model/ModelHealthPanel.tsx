import type { ModelHealth } from "../../api/types";
import { formatDateTime, formatNullable } from "../../utils/format";
import { EmptyState } from "../common/EmptyState";
import { MetricCard } from "../common/MetricCard";
import { SectionCard } from "../layout/SectionCard";

export function ModelHealthPanel({ health }: { health?: ModelHealth }) {
  if (!health) return <EmptyState label="暂无模型健康数据" />;
  return (
    <SectionCard title="模型健康" subtitle="active、candidate 与降级状态">
      <div className="metric-grid">
        <MetricCard label="Active 模型" value={health.active_model} />
        <MetricCard label="Candidate 模型" value={health.candidate_model} />
        <MetricCard label="晋级状态" value={health.promotion_status} />
        <MetricCard label="降级状态" value={health.degradation_status} />
        <MetricCard label="最近检查" value={formatDateTime(health.last_check_time)} />
      </div>
      <div className="reason-list">
        {(health.failure_reasons?.length ? health.failure_reasons : ["暂无失败原因"]).map((item) => (
          <span key={item}>{formatNullable(item)}</span>
        ))}
      </div>
    </SectionCard>
  );
}
