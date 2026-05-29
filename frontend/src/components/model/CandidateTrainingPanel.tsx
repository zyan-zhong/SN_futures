import { useCallback, useState } from "react";
import { getCandidateStatus, getWalkForwardResults, trainCandidateModel } from "../../api/terminal";
import type { CandidateTrainingStatus, WalkForwardResultsPayload } from "../../api/types";
import { usePolling } from "../../hooks/usePolling";
import { formatDateTime, formatNullable, formatNumber, formatPercent } from "../../utils/format";
import { DataTable } from "../common/DataTable";
import { ErrorState } from "../common/ErrorState";
import { LoadingState } from "../common/LoadingState";
import { StatusPill } from "../common/StatusPill";
import { SectionCard } from "../layout/SectionCard";

function metricRows(data?: CandidateTrainingStatus | null) {
  const metrics = data?.metrics_by_horizon || {};
  return Object.entries(metrics).map(([horizon, row]) => ({
    horizon,
    directional_accuracy: row.directional_accuracy,
    balanced_accuracy: row.balanced_accuracy,
    brier_score: row.brier_score,
    calibration_error: row.calibration_error,
    information_coefficient: row.information_coefficient,
    coverage_rate: row.coverage_rate,
    abstain_rate: row.abstain_rate,
    cost_adjusted_expectancy: row.cost_adjusted_expectancy,
    fold_count: row.fold_count,
    sample_count: row.sample_count,
  }));
}

function foldRows(walkForward?: WalkForwardResultsPayload | null) {
  const results = walkForward?.results || {};
  return Object.entries(results).flatMap(([horizon, payload]) => {
    const folds = Array.isArray(payload.folds) ? payload.folds : [];
    return folds.slice(0, 3).map((fold: Record<string, unknown>) => ({
      horizon,
      fold: fold.fold,
      train: `${formatNullable(fold.train_start)} 至 ${formatNullable(fold.train_end)}`,
      validation: `${formatNullable(fold.validation_start)} 至 ${formatNullable(fold.validation_end)}`,
      train_samples: fold.train_samples,
      validation_samples: fold.validation_samples,
      purged_samples: fold.purged_samples,
      embargo_samples: fold.embargo_samples,
    }));
  });
}

export function CandidateTrainingPanel() {
  const loader = useCallback(() => getCandidateStatus(), []);
  const { data, error, loading, refresh } = usePolling<CandidateTrainingStatus>(loader, 60000);
  const [walkForward, setWalkForward] = useState<WalkForwardResultsPayload | null>(null);
  const [running, setRunning] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function onTrain() {
    setRunning(true);
    setMessage(null);
    try {
      const result = await trainCandidateModel({ horizons: ["1d", "3d", "5d", "10d", "20d"] });
      setMessage(result.message_zh || "candidate 训练完成。");
      const wf = await getWalkForwardResults();
      setWalkForward(wf);
      await refresh();
    } catch (exc) {
      setMessage(exc instanceof Error ? exc.message : "candidate 训练失败。");
    } finally {
      setRunning(false);
    }
  }

  async function onLoadWalkForward() {
    setWalkForward(await getWalkForwardResults());
  }

  if (loading && !data) return <LoadingState label="正在读取 candidate 训练状态..." />;
  if (error && !data) return <ErrorState title="candidate 训练状态暂时无法加载" message={error} actionLabel="重新加载" onAction={refresh} />;

  return (
    <SectionCard title="Candidate 训练与 Purged Walk-forward" subtitle="候选模型必须先完成无未来函数验证；候选模型不能替代 active。">
      <div className="button-row">
        <button className="primary-button" type="button" disabled={running} onClick={() => void onTrain()}>
          {running ? "正在训练 candidate..." : "训练 candidate model"}
        </button>
        <button className="ghost-button" type="button" onClick={() => void onLoadWalkForward()}>
          查看 Walk-forward 结果
        </button>
        <button className="ghost-button" type="button" onClick={() => void refresh()}>
          刷新状态
        </button>
      </div>
      {message ? <StatusPill label={message} tone={message.includes("失败") ? "bad" : "info"} /> : null}
      <div className="metric-grid compact">
        <div className="metric-card">
          <span className="metric-label">候选状态</span>
          <strong>{formatNullable(data?.status, "暂未运行")}</strong>
          <small>{formatDateTime(data?.generated_at)}</small>
        </div>
        <div className="metric-card">
          <span className="metric-label">是否 active</span>
          <strong>{data?.candidate_is_active ? "异常：已 active" : "否，仍为 candidate"}</strong>
          <small>Promotion gate 未通过前不生成真实预测</small>
        </div>
        <div className="metric-card">
          <span className="metric-label">客户预测</span>
          <strong>{data?.customer_prediction_generated ? "异常：已生成" : "未生成"}</strong>
          <small>本页仅展示研究验证</small>
        </div>
        <div className="metric-card">
          <span className="metric-label">候选记录</span>
          <strong>{formatNumber(data?.records?.length, 0)}</strong>
          <small>registry 仅保存 candidate</small>
        </div>
      </div>
      <DataTable
        data={metricRows(data)}
        emptyLabel="暂无 candidate 指标，请先训练 candidate model。"
        columns={[
          { key: "horizon", title: "周期", render: (row) => formatNullable(row.horizon) },
          { key: "directional_accuracy", title: "方向准确率", render: (row) => formatPercent(row.directional_accuracy as number | null | undefined) },
          { key: "balanced_accuracy", title: "平衡准确率", render: (row) => formatPercent(row.balanced_accuracy as number | null | undefined) },
          { key: "brier_score", title: "Brier", render: (row) => formatNumber(row.brier_score as number | null | undefined, 4) },
          { key: "calibration_error", title: "ECE", render: (row) => formatNumber(row.calibration_error as number | null | undefined, 4) },
          { key: "information_coefficient", title: "IC", render: (row) => formatNumber(row.information_coefficient as number | null | undefined, 4) },
          { key: "coverage_rate", title: "覆盖率", render: (row) => formatPercent(row.coverage_rate as number | null | undefined) },
          { key: "abstain_rate", title: "观望率", render: (row) => formatPercent(row.abstain_rate as number | null | undefined) },
          { key: "fold_count", title: "Fold", render: (row) => formatNumber(row.fold_count as number | null | undefined, 0) },
          { key: "sample_count", title: "样本数", render: (row) => formatNumber(row.sample_count as number | null | undefined, 0) },
        ]}
      />
      <DataTable
        data={foldRows(walkForward)}
        emptyLabel="暂未加载 Walk-forward fold 明细。"
        columns={[
          { key: "horizon", title: "周期", render: (row) => formatNullable(row.horizon) },
          { key: "fold", title: "Fold", render: (row) => formatNumber(row.fold as number | null | undefined, 0) },
          { key: "train", title: "训练区间", render: (row) => formatNullable(row.train) },
          { key: "validation", title: "验证区间", render: (row) => formatNullable(row.validation) },
          { key: "train_samples", title: "训练样本", render: (row) => formatNumber(row.train_samples as number | null | undefined, 0) },
          { key: "validation_samples", title: "验证样本", render: (row) => formatNumber(row.validation_samples as number | null | undefined, 0) },
          { key: "purged_samples", title: "Purge 样本", render: (row) => formatNumber(row.purged_samples as number | null | undefined, 0) },
          { key: "embargo_samples", title: "Embargo 样本", render: (row) => formatNumber(row.embargo_samples as number | null | undefined, 0) },
        ]}
      />
      <p className="muted">
        内部对照指标只用于研究验证，不会进入客户预测页。candidate 通过 promotion gate 前不会替代 active，也不会生成真实客户预测。
      </p>
    </SectionCard>
  );
}
