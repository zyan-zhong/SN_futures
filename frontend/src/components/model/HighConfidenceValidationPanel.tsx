import { useCallback, useState } from "react";
import { getHighConfidenceReport, getOOFIntegrityReport } from "../../api/terminal";
import type { HighConfidenceReport, HighConfidenceSubsetMetrics, OOFIntegrityReport } from "../../api/types";
import { usePolling } from "../../hooks/usePolling";
import { formatNumber } from "../../utils/format";
import { DataTable } from "../common/DataTable";
import { ErrorState } from "../common/ErrorState";
import { LoadingState } from "../common/LoadingState";
import { SectionCard } from "../layout/SectionCard";

const horizons = ["1d", "3d", "5d", "10d", "20d"];
const subsetKeys = ["top_10pct", "top_20pct", "top_30pct"];

function subsetRows(payload?: HighConfidenceReport | null) {
  const subsets = payload?.confidence_subset ?? {};
  return subsetKeys.map((key) => {
    const item = (subsets[key] ?? {}) as HighConfidenceSubsetMetrics;
    return {
      bucket: key.replace("top_", "Top ").replace("pct", "%"),
      sample_count: item.sample_count,
      actual_coverage: item.actual_coverage,
      direction_accuracy: item.direction_accuracy,
      balanced_accuracy: item.balanced_accuracy,
      cost_adjusted_expectancy: item.cost_adjusted_expectancy,
      max_drawdown_proxy: item.max_drawdown_proxy,
      worst_fold_accuracy: item.worst_fold_accuracy,
      worst_regime_accuracy: item.worst_regime_accuracy,
      worst_year_accuracy: item.worst_year_accuracy
    };
  });
}

function previewRows(payload?: HighConfidenceReport | null) {
  const preview = payload?.preview ?? {};
  const dsr = (preview.dsr_preview ?? {}) as Record<string, unknown>;
  const pbo = (preview.pbo_preview ?? {}) as Record<string, unknown>;
  const reality = (preview.reality_check_preview ?? {}) as Record<string, unknown>;
  const stress = (preview.cost_stress ?? {}) as Record<string, unknown>;
  return [
    { item: "DSR preview", value: dsr.deflated_sharpe_ratio ?? dsr.dsr ?? "数据暂缺" },
    { item: "PBO preview", value: pbo.pbo ?? pbo.probability_of_backtest_overfitting ?? "数据暂缺" },
    { item: "Reality Check p-value", value: reality.p_value ?? "数据暂缺" },
    { item: "2x 成本压力", value: stress["2x_cost"] ?? "数据暂缺" },
    { item: "3x 成本压力", value: stress["3x_cost"] ?? "数据暂缺" }
  ];
}

function contributionRows(payload: HighConfidenceReport | null | undefined, key: "hit_rate_by_fold" | "hit_rate_by_regime" | "hit_rate_by_year") {
  const top10 = (payload?.confidence_subset?.top_10pct ?? {}) as HighConfidenceSubsetMetrics;
  return (top10[key] ?? []) as Array<Record<string, unknown>>;
}

export function HighConfidenceValidationPanel() {
  const [horizon, setHorizon] = useState("1d");
  const loader = useCallback(() => getHighConfidenceReport(horizon), [horizon]);
  const { data, error, loading, refresh } = usePolling<HighConfidenceReport>(loader, 60000);
  const integrity = usePolling<OOFIntegrityReport>(() => getOOFIntegrityReport(), 120000);

  return (
    <SectionCard
      title="高置信子集验证"
      subtitle="基于 out-of-fold 样本外轨迹审计高置信子集稳定性；不发布 active，不生成客户预测。"
      actions={
        <select aria-label="选择高置信验证周期" value={horizon} onChange={(event) => setHorizon(event.target.value)}>
          {horizons.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
      }
    >
      <div className="notice-card warning">
        <strong>研究边界</strong>
        <span>高置信 OOF 命中率不是客户预测，不代表未来收益，不构成投资建议。</span>
      </div>

      {loading ? <LoadingState label="正在加载高置信 OOF 验证..." /> : null}
      {error ? <ErrorState message={error} onRetry={refresh} /> : null}

      <div className="metric-grid">
        <div className="metric-card">
          <span>当前周期</span>
          <strong>{horizon}</strong>
        </div>
        <div className="metric-card">
          <span>晋级状态</span>
          <strong>{integrity.data?.promotion_readiness ?? "数据暂缺"}</strong>
        </div>
        <div className="metric-card">
          <span>Blocking 数</span>
          <strong>{formatNumber(data?.blocking_reasons?.length)}</strong>
        </div>
        <div className="metric-card">
          <span>Warning 数</span>
          <strong>{formatNumber(data?.warnings?.length)}</strong>
        </div>
      </div>

      <DataTable
        data={subsetRows(data)}
        emptyLabel="暂无高置信子集验证结果，请先运行 candidate walk-forward。"
        columns={[
          { key: "bucket", title: "子集" },
          { key: "sample_count", title: "样本数", format: "number" },
          { key: "actual_coverage", title: "覆盖率", format: "percent" },
          { key: "direction_accuracy", title: "方向命中率", format: "percent" },
          { key: "balanced_accuracy", title: "平衡准确率", format: "percent" },
          { key: "cost_adjusted_expectancy", title: "成本后期望", format: "number" },
          { key: "max_drawdown_proxy", title: "回撤代理", format: "number" },
          { key: "worst_fold_accuracy", title: "最差 Fold", format: "percent" },
          { key: "worst_regime_accuracy", title: "最差 Regime", format: "percent" },
          { key: "worst_year_accuracy", title: "最差年份", format: "percent" }
        ]}
      />

      <div className="two-column">
        <DataTable
          data={previewRows(data)}
          emptyLabel="暂无 DSR/PBO preview。"
          columns={[
            { key: "item", title: "验证项" },
            { key: "value", title: "结果" }
          ]}
        />
        <div className="diagnostic-list">
          <h3>Blocking reasons</h3>
          {(data?.blocking_reasons ?? []).length ? (
            <ul>
              {(data?.blocking_reasons ?? []).map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          ) : (
            <p>暂无阻断项，但仍需通过完整 promotion gate。</p>
          )}
          <h3>Warnings</h3>
          {(data?.warnings ?? []).length ? (
            <ul>
              {(data?.warnings ?? []).map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          ) : (
            <p>暂无额外警告。</p>
          )}
        </div>
      </div>

      <div className="three-column">
        <DataTable
          data={contributionRows(data, "hit_rate_by_fold")}
          emptyLabel="暂无 fold 贡献数据。"
          columns={[
            { key: "fold_id", title: "Fold" },
            { key: "sample_count", title: "样本数", format: "number" },
            { key: "accuracy", title: "命中率", format: "percent" },
            { key: "contribution", title: "贡献占比", format: "percent" }
          ]}
        />
        <DataTable
          data={contributionRows(data, "hit_rate_by_regime")}
          emptyLabel="暂无 regime 贡献数据。"
          columns={[
            { key: "regime_label", title: "Regime" },
            { key: "sample_count", title: "样本数", format: "number" },
            { key: "accuracy", title: "命中率", format: "percent" },
            { key: "contribution", title: "贡献占比", format: "percent" }
          ]}
        />
        <DataTable
          data={contributionRows(data, "hit_rate_by_year")}
          emptyLabel="暂无年份贡献数据。"
          columns={[
            { key: "year", title: "年份" },
            { key: "sample_count", title: "样本数", format: "number" },
            { key: "accuracy", title: "命中率", format: "percent" },
            { key: "contribution", title: "贡献占比", format: "percent" }
          ]}
        />
      </div>
    </SectionCard>
  );
}
