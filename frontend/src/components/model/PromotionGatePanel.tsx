import { useCallback, useState } from "react";
import type { ModelHealth, PromotionReportPayload } from "../../api/types";
import { getActiveModelStatus, getPromotionReport, promoteCandidateModel } from "../../api/terminal";
import { usePolling } from "../../hooks/usePolling";
import { formatDateTime, formatNullable } from "../../utils/format";
import { DataTable } from "../common/DataTable";
import { ErrorState } from "../common/ErrorState";
import { LoadingState } from "../common/LoadingState";
import { StatusPill } from "../common/StatusPill";
import { SectionCard } from "../layout/SectionCard";

function decisionRows(report?: PromotionReportPayload | null) {
  return (report?.decisions || []).map((item) => ({
    horizon: item.horizon,
    model_id: item.model_id,
    passed: item.passed ? "通过" : "未通过",
    failure_reasons: item.failure_reasons?.join("；") || "无",
  }));
}

export function PromotionGatePanel({ health }: { health?: ModelHealth }) {
  const loader = useCallback(() => getPromotionReport(), []);
  const { data, error, loading, refresh } = usePolling<PromotionReportPayload>(loader, 60000);
  const [running, setRunning] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [activeMessage, setActiveMessage] = useState<string | null>(null);

  async function onPromote() {
    setRunning(true);
    setMessage(null);
    try {
      const result = await promoteCandidateModel();
      setMessage(result.message_zh || "promotion gate 已执行。");
      const active = await getActiveModelStatus();
      setActiveMessage(active.message_zh || active.status || null);
      await refresh();
    } catch (exc) {
      setMessage(exc instanceof Error ? exc.message : "promotion gate 执行失败。");
    } finally {
      setRunning(false);
    }
  }

  if (loading && !data) return <LoadingState label="正在读取 promotion gate 报告..." />;
  if (error && !data) return <ErrorState title="Promotion Gate 暂时无法加载" message={error} actionLabel="重新加载" onAction={refresh} />;

  return (
    <SectionCard title="Promotion Gate" subtitle="candidate 必须通过真实 walk-forward、成本后表现、校准、数据质量和风险阈值后，才允许成为 active。">
      <div className="button-row">
        <button className="primary-button" type="button" disabled={running} onClick={() => void onPromote()}>
          {running ? "正在执行 Promotion Gate..." : "执行 Promotion Gate"}
        </button>
        <button className="ghost-button" type="button" onClick={() => void refresh()}>
          刷新报告
        </button>
      </div>
      <div className="check-list">
        <span>walk-forward fold 数与验证样本数必须达标</span>
        <span>方向准确率必须超过朴素阈值</span>
        <span>Brier 与 ECE 必须低于阈值</span>
        <span>成本后期望必须为正，回撤代理必须受控</span>
        <span>特征覆盖率、数据质量、无泄漏检查必须通过</span>
        <span>sample 与 baseline 不允许晋级为 active</span>
      </div>
      {message ? <StatusPill label={message} tone={message.includes("未通过") ? "warn" : "info"} /> : null}
      {activeMessage ? <StatusPill label={activeMessage} tone="info" /> : null}
      <p className="muted">当前晋级状态：{data?.message_zh || health?.promotion_status || "暂未运行"}</p>
      <p className="muted">最近检查时间：{formatDateTime(data?.generated_at)}</p>
      <DataTable
        data={decisionRows(data)}
        emptyLabel="暂无 promotion gate 结果，请先训练 candidate 并执行 Promotion Gate。"
        columns={[
          { key: "horizon", title: "周期", render: (row) => formatNullable(row.horizon) },
          { key: "model_id", title: "Candidate", render: (row) => formatNullable(row.model_id) },
          { key: "passed", title: "结果", format: "status", render: (row) => formatNullable(row.passed) },
          { key: "failure_reasons", title: "失败原因 / 下一步", render: (row) => formatNullable(row.failure_reasons) },
        ]}
      />
      <p className="muted">
        active model 存在后，预测页才允许接入真实模型预测；本按钮不会生成客户预测，也不会绕过 promotion gate。
      </p>
    </SectionCard>
  );
}
