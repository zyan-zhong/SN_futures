import type { BacktestDiagnostics } from "../../api/types";
import { formatNullable } from "../../utils/format";
import { EmptyState } from "../common/EmptyState";
import { MetricCard } from "../common/MetricCard";
import { SectionCard } from "../layout/SectionCard";

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

export function BacktestPanel({ diagnostics }: { diagnostics?: BacktestDiagnostics }) {
  if (!diagnostics) return <EmptyState label="暂无回测诊断数据" />;
  const metrics = asRecord(diagnostics.walk_forward_metrics);
  const failureReasons = Array.isArray(diagnostics.failure_reasons) ? diagnostics.failure_reasons : [];
  return (
    <SectionCard title="Walk-forward 回测" subtitle="仅展示成本后、样本外与基准对比结果">
      <div className="metric-grid">
        {Object.entries(metrics).slice(0, 8).map(([key, value]) => (
          <MetricCard label={key} value={formatNullable(value)} key={key} />
        ))}
        {!Object.keys(metrics).length ? <MetricCard label="回测状态" value="暂未运行" /> : null}
      </div>
      <p className="muted">晋级结论：{formatNullable(diagnostics.promotion_gate_result, "待验证")}</p>
      <div className="reason-list">
        {(failureReasons.length ? failureReasons : ["暂无失败原因"]).map((item) => (
          <span key={item}>{item}</span>
        ))}
      </div>
    </SectionCard>
  );
}
