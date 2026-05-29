import { useCallback, useState } from "react";
import { getOOFTraceSummary, getResearchOOFTraceSummary } from "../../api/terminal";
import type { OOFTraceSummary } from "../../api/types";
import { usePolling } from "../../hooks/usePolling";
import { formatNullable, formatNumber } from "../../utils/format";
import { DataTable } from "../common/DataTable";
import { ErrorState } from "../common/ErrorState";
import { LoadingState } from "../common/LoadingState";
import { SectionCard } from "../layout/SectionCard";

const horizons = ["1d", "3d", "5d", "10d", "20d"];

function asRows(value?: Array<Record<string, unknown>>) {
  return Array.isArray(value) ? value : [];
}

function getResearchFirstSummary(payload?: OOFTraceSummary | null): OOFTraceSummary | undefined {
  const summaries = payload?.summaries;
  if (!summaries) return undefined;
  const first = Object.values(summaries)[0];
  return first as OOFTraceSummary | undefined;
}

export function OOFTracePanel({ experimentId }: { experimentId?: string }) {
  const [horizon, setHorizon] = useState("1d");
  const loader = useCallback(
    () => (experimentId ? getResearchOOFTraceSummary(experimentId) : getOOFTraceSummary(horizon)),
    [experimentId, horizon]
  );
  const { data, error, loading, refresh } = usePolling<OOFTraceSummary>(loader, 60000);
  const summary = experimentId ? getResearchFirstSummary(data) : data;

  return (
    <SectionCard
      title="OOF 样本外验证轨迹"
      subtitle="逐样本 out-of-fold 轨迹仅用于研究诊断，不是客户预测，也不会发布 active。"
      actions={
        experimentId ? null : (
          <select aria-label="选择 OOF 周期" value={horizon} onChange={(event) => setHorizon(event.target.value)}>
            {horizons.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        )
      }
    >
      {loading ? <LoadingState label="正在加载 OOF 验证轨迹..." /> : null}
      {error ? <ErrorState message={error} onRetry={refresh} /> : null}

      <div className="metric-grid">
        <div className="metric-card">
          <span>Trace 行数</span>
          <strong>{formatNumber(summary?.row_count)}</strong>
        </div>
        <div className="metric-card">
          <span>Fold 数</span>
          <strong>{formatNumber(summary?.fold_count)}</strong>
        </div>
        <div className="metric-card">
          <span>Top 10% 命中</span>
          <strong>{formatNumber(summary?.top_10pct?.accuracy as number | null | undefined)}</strong>
        </div>
        <div className="metric-card">
          <span>Top 20% 命中</span>
          <strong>{formatNumber(summary?.top_20pct?.accuracy as number | null | undefined)}</strong>
        </div>
      </div>

      <div className="notice-card">
        <strong>轨迹范围</strong>
        <span>
          {formatNullable(summary?.date_start)} 至 {formatNullable(summary?.date_end)}
        </span>
      </div>

      <div className="two-column">
        <DataTable
          data={asRows(summary?.calibration_bins)}
          emptyLabel="暂无校准分桶，请先运行 candidate walk-forward。"
          columns={[
            { key: "bin", title: "概率分桶" },
            { key: "predicted_probability_mean", title: "预测概率均值", format: "number" },
            { key: "realized_up_rate", title: "真实上涨率", format: "number" },
            { key: "sample_count", title: "样本数", format: "number" },
            { key: "brier_contribution", title: "Brier 贡献", format: "number" }
          ]}
        />
        <DataTable
          data={asRows(summary?.confidence_deciles)}
          emptyLabel="暂无高置信分层，请先运行 candidate walk-forward。"
          columns={[
            { key: "bucket", title: "置信分层" },
            { key: "sample_count", title: "样本数", format: "number" },
            { key: "coverage", title: "覆盖率", format: "number" },
            { key: "accuracy", title: "命中率", format: "number" },
            { key: "cost_adjusted_expectancy", title: "成本后期望", format: "number" }
          ]}
        />
      </div>

      <div className="two-column">
        <DataTable
          data={asRows(summary?.regime_error_hotspots)}
          emptyLabel="暂无 Regime 错误热区。"
          columns={[
            { key: "regime_label", title: "Regime" },
            { key: "sample_count", title: "样本数", format: "number" },
            { key: "signal_count", title: "信号数", format: "number" },
            { key: "error_count", title: "错误数", format: "number" },
            { key: "error_rate", title: "错误率", format: "number" }
          ]}
        />
        <DataTable
          data={asRows(summary?.high_confidence_wrong_samples)}
          emptyLabel="暂无高置信错误样本。"
          columns={[
            { key: "label_start_time", title: "样本时间" },
            { key: "fold_id", title: "Fold" },
            { key: "confidence", title: "置信度", format: "number" },
            { key: "predicted_direction", title: "预测方向", format: "number" },
            { key: "realized_direction", title: "真实方向", format: "number" },
            { key: "drawdown_contribution", title: "回撤贡献", format: "number" }
          ]}
        />
      </div>
    </SectionCard>
  );
}
