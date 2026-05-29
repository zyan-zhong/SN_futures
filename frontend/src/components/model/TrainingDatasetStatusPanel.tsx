import { useCallback, useState } from "react";
import { buildTrainingDataset, getTrainingDatasetStatus } from "../../api/terminal";
import type { TrainingDatasetStatus } from "../../api/types";
import { usePolling } from "../../hooks/usePolling";
import { formatDateTime, formatNullable, formatNumber } from "../../utils/format";
import { DataTable } from "../common/DataTable";
import { ErrorState } from "../common/ErrorState";
import { LoadingState } from "../common/LoadingState";
import { StatusPill } from "../common/StatusPill";

export function TrainingDatasetStatusPanel() {
  const loader = useCallback(() => getTrainingDatasetStatus(), []);
  const { data, error, loading, refresh } = usePolling<TrainingDatasetStatus>(loader, 60000);
  const [building, setBuilding] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function onBuild() {
    setBuilding(true);
    setMessage(null);
    try {
      const result = await buildTrainingDataset({ horizons: [1, 3, 5, 10, 20], min_feature_coverage: 0.7 });
      setMessage(result.message_zh || "训练数据集已生成。");
      await refresh();
    } catch (exc) {
      setMessage(exc instanceof Error ? exc.message : "训练数据集构建失败。");
    } finally {
      setBuilding(false);
    }
  }

  if (loading && !data) return <LoadingState label="正在读取训练数据集状态..." />;
  if (error && !data) return <ErrorState title="训练数据集状态暂时无法加载" message={error} actionLabel="重新加载" onAction={refresh} />;

  const rows = Object.entries(data?.sample_count_by_horizon || {}).map(([horizon, count]) => ({
    horizon,
    count,
    distribution: JSON.stringify(data?.label_distribution_by_horizon?.[horizon] || {}),
  }));

  return (
    <div className="page-stack">
      <div className="button-row">
        <button className="primary-button" type="button" disabled={building} onClick={() => void onBuild()}>
          {building ? "正在构建训练数据集..." : "构建训练数据集"}
        </button>
        <button className="ghost-button" type="button" onClick={() => void refresh()}>
          刷新状态
        </button>
      </div>
      {message ? <StatusPill label={message} tone={message.includes("失败") ? "bad" : "good"} /> : null}
      <div className="metric-grid compact">
        <div className="metric-card">
          <span className="metric-label">生成状态</span>
          <strong>{formatNullable(data?.status, "尚未生成")}</strong>
          <small>{formatDateTime(data?.generated_at)}</small>
        </div>
        <div className="metric-card">
          <span className="metric-label">特征数</span>
          <strong>{formatNumber(data?.feature_count, 0)}</strong>
          <small>真实可用因子列</small>
        </div>
        <div className="metric-card">
          <span className="metric-label">泄漏检查</span>
          <strong>{data?.leakage_check_pass ? "通过" : "待检查"}</strong>
          <small>标签列不得进入特征</small>
        </div>
        <div className="metric-card">
          <span className="metric-label">数据范围</span>
          <strong>{formatNullable(data?.date_start, "数据暂缺")}</strong>
          <small>至 {formatNullable(data?.date_end, "数据暂缺")}</small>
        </div>
      </div>
      <DataTable
        data={rows}
        columns={[
          { key: "horizon", title: "周期", render: (row) => formatNullable(row.horizon) },
          { key: "count", title: "样本数", render: (row) => formatNumber(row.count, 0) },
          { key: "distribution", title: "标签分布", render: (row) => formatNullable(row.distribution) },
        ]}
      />
      <p className="muted">
        本步骤只构建训练数据集，不训练模型、不生成预测、不生成回测，不接入 baseline。
      </p>
    </div>
  );
}
