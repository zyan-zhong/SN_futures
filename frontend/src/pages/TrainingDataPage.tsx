import { useCallback, useState } from "react";
import { buildTrainingDataset, getTrainingDatasetStatus } from "../api/terminal";
import type { TrainingDatasetStatus } from "../api/types";
import { DataTable } from "../components/common/DataTable";
import { ErrorState } from "../components/common/ErrorState";
import { LoadingState } from "../components/common/LoadingState";
import { StatusPill } from "../components/common/StatusPill";
import { SectionCard } from "../components/layout/SectionCard";
import { usePolling } from "../hooks/usePolling";
import { formatDateTime, formatNullable, formatNumber } from "../utils/format";

const datasetVersions = ["v1", "v2", "v3", "v4"];

function distributionRows(status?: TrainingDatasetStatus | null) {
  return Object.entries(status?.sample_count_by_horizon || {}).map(([horizon, count]) => ({
    horizon,
    sample_count: count,
    label_distribution: JSON.stringify(status?.label_distribution_by_horizon?.[horizon] || {}),
    return_summary: JSON.stringify(status?.return_summary_by_horizon?.[horizon] || {})
  }));
}

function datasetPathRows(status?: TrainingDatasetStatus | null) {
  return Object.entries(status?.dataset_paths || {}).map(([horizon, filePath]) => ({ horizon, file_path: filePath }));
}

export function TrainingDataPage() {
  const [version, setVersion] = useState("v3");
  const [building, setBuilding] = useState(false);
  const [message, setMessage] = useState("");
  const loader = useCallback(() => getTrainingDatasetStatus(version), [version]);
  const { data, error, loading, refresh } = usePolling<TrainingDatasetStatus>(loader, 60000);

  async function handleBuildDataset() {
    setBuilding(true);
    setMessage("");
    try {
      const result = await buildTrainingDataset({
        dataset_version: version,
        feature_store_version: version === "v1" || version === "v2" ? undefined : version,
        feature_set: version === "v1" ? "usable_real_features" : "ohlcv_technical_regime_cross_market_event",
        horizons: [1, 3, 5, 10, 20],
        min_feature_coverage: 0.7
      });
      setMessage(result.message_zh || `${version} training dataset build completed.`);
      await refresh();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Training dataset build failed.");
    } finally {
      setBuilding(false);
    }
  }

  if (loading && !data) return <LoadingState label="正在读取训练数据状态..." />;
  if (error && !data) return <ErrorState title="训练数据状态暂时无法加载" message={error} actionLabel="重新加载" onAction={refresh} />;

  return (
    <div className="page-stack">
      <SectionCard
        title="训练数据 Training Data"
        subtitle="查看 v1/v2/v3/v4 数据集、样本数、特征数、标签分布、泄漏检查和 manifest。此页不训练模型。"
        actions={
          <select aria-label="dataset version selector" value={version} onChange={(event) => setVersion(event.target.value)}>
            {datasetVersions.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        }
      >
        <div className="button-row">
          <button className="primary-button" type="button" onClick={() => void handleBuildDataset()} disabled={building}>
            {building ? "正在构建..." : `构建 ${version} 训练数据`}
          </button>
          <button className="secondary-button" type="button" onClick={() => void refresh()}>
            刷新状态
          </button>
          <StatusPill label="不训练模型 / 不生成预测 / 不接 baseline" tone="info" />
        </div>
        {message ? <StatusPill label={message} tone={message.includes("fail") || message.includes("失败") ? "bad" : "info"} /> : null}
      </SectionCard>

      <SectionCard title={`${version} manifest summary`} subtitle="Manifest 用于复现实验并审计泄漏风险。">
        <div className="metric-grid compact">
          <div className="metric-card">
            <span className="metric-label">状态</span>
            <strong>{formatNullable(data?.status, "not_built")}</strong>
            <small>{formatDateTime(data?.generated_at)}</small>
          </div>
          <div className="metric-card">
            <span className="metric-label">样本范围</span>
            <strong>{formatNullable(data?.date_start, "暂无")}</strong>
            <small>至 {formatNullable(data?.date_end, "暂无")}</small>
          </div>
          <div className="metric-card">
            <span className="metric-label">特征数</span>
            <strong>{formatNumber(data?.feature_count, 0)}</strong>
            <small>feature_cols: {data?.feature_cols?.length || 0}</small>
          </div>
          <div className="metric-card">
            <span className="metric-label">泄漏检查</span>
            <strong>{data?.leakage_check_pass ? "通过" : "待检查/未通过"}</strong>
            <small>标签列不得进入 feature_cols</small>
          </div>
          <div className="metric-card">
            <span className="metric-label">cross-market 字段</span>
            <strong>{data?.cross_market_feature_cols?.length || 0}</strong>
            <small>{(data?.cross_market_feature_cols || []).slice(0, 4).join(", ") || "未纳入"}</small>
          </div>
          <div className="metric-card">
            <span className="metric-label">event 字段</span>
            <strong>{data?.event_feature_cols?.length || 0}</strong>
            <small>{(data?.event_feature_cols || []).slice(0, 4).join(", ") || "未纳入"}</small>
          </div>
        </div>
        <div className="notice-card">
          <strong>Manifest path</strong>
          <p>{formatNullable(data?.manifest_path, "暂无 manifest")}</p>
          <strong>Feature Store</strong>
          <p>{formatNullable(data?.feature_store_manifest_path || data?.feature_store_path, "未绑定 Feature Store")}</p>
        </div>
      </SectionCard>

      <SectionCard title="样本数与标签分布" subtitle="每个 horizon 的样本数、方向标签分布和收益摘要。">
        <DataTable
          data={distributionRows(data)}
          emptyLabel="暂无训练样本分布"
          columns={[
            { key: "horizon", title: "Horizon" },
            { key: "sample_count", title: "样本数", format: "number" },
            { key: "label_distribution", title: "标签分布" },
            { key: "return_summary", title: "收益摘要" },
          ]}
        />
      </SectionCard>

      <SectionCard title="数据集文件" subtitle="用于下载/归档 train_*.parquet 或 CSV 路径。">
        <DataTable
          data={datasetPathRows(data)}
          emptyLabel="暂无数据集文件路径"
          columns={[
            { key: "horizon", title: "Horizon" },
            { key: "file_path", title: "Dataset path" },
          ]}
        />
      </SectionCard>
    </div>
  );
}
