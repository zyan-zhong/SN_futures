import { useCallback } from "react";
import { getCandidateDiagnostics } from "../../api/terminal";
import type { CandidateDiagnosticsPayload, CandidateHorizonDiagnostics } from "../../api/types";
import { usePolling } from "../../hooks/usePolling";
import { formatNullable, formatNumber, formatPercent } from "../../utils/format";
import { CollapsibleDebug } from "../common/CollapsibleDebug";
import { DataTable } from "../common/DataTable";
import { ErrorState } from "../common/ErrorState";
import { LoadingState } from "../common/LoadingState";
import { StatusPill } from "../common/StatusPill";
import { SectionCard } from "../layout/SectionCard";

function horizonRows(data?: CandidateDiagnosticsPayload | null) {
  const horizons = data?.horizons || {};
  return Object.entries(horizons).map(([horizon, item]) => ({
    horizon,
    failure_reasons: (item.failure_reasons || []).join("；") || "未触发 gate 失败原因",
    directional_accuracy: item.metric_summary?.directional_accuracy,
    brier_score: item.metric_summary?.brier_score,
    calibration_error: item.metric_summary?.calibration_error,
    coverage_rate: item.metric_summary?.coverage_rate,
    cost_adjusted_expectancy: item.metric_summary?.cost_adjusted_expectancy,
    max_drawdown_proxy: item.metric_summary?.max_drawdown_proxy,
    diagnosis: (item.error_diagnosis_zh || []).slice(0, 2).join("；"),
  }));
}

function confidenceRows(item?: CandidateHorizonDiagnostics) {
  return (item?.confidence_deciles || []).map((row) => ({
    bucket: row.bucket,
    coverage: row.coverage,
    accuracy: row.accuracy,
    cost_adjusted_expectancy: row.cost_adjusted_expectancy,
    note_zh: row.note_zh,
  }));
}

function calibrationRows(item?: CandidateHorizonDiagnostics) {
  return (item?.calibration_bins || []).map((row) => ({
    bin: row.bin,
    sample_count: row.sample_count,
    brier_contribution: row.brier_contribution,
    calibration_error: row.calibration_error,
    note_zh: row.note_zh,
  }));
}

function featureRows(item?: CandidateHorizonDiagnostics) {
  return (item?.feature_importance_top || []).slice(0, 8).map((row) => ({
    feature: row.feature,
    importance: row.importance,
  }));
}

function firstHorizon(data?: CandidateDiagnosticsPayload | null): CandidateHorizonDiagnostics | undefined {
  const horizons = data?.horizons || {};
  const key = ["1d", "3d", "5d", "10d", "20d"].find((item) => horizons[item]);
  return key ? horizons[key] : Object.values(horizons)[0];
}

export function CandidateDiagnosticsPanel() {
  const loader = useCallback(() => getCandidateDiagnostics(), []);
  const { data, error, loading, refresh } = usePolling<CandidateDiagnosticsPayload>(loader, 60000);
  const selected = firstHorizon(data);

  if (loading && !data) return <LoadingState label="正在读取 Candidate 失败归因..." />;
  if (error && !data) {
    return <ErrorState title="Candidate 失败归因暂时无法加载" message={error} actionLabel="重新加载" onAction={refresh} />;
  }

  return (
    <SectionCard
      title="Candidate 失败归因"
      subtitle="只读研究诊断：不发布 active、不生成客户预测、不降低 promotion gate。"
      actions={
        <button className="ghost-button" type="button" onClick={() => void refresh()}>
          刷新归因
        </button>
      }
    >
      <div className="status-row">
        <StatusPill label={data?.status || "未运行"} tone={data?.status === "success" ? "info" : "warn"} />
        <span className="muted">{data?.message_zh || "暂无 candidate 诊断结果。"}</span>
      </div>

      <div className="insight-list">
        {(data?.global_findings || ["暂无全局发现。"]).map((item) => (
          <div className="insight-item" key={item}>
            {item}
          </div>
        ))}
      </div>

      <DataTable
        data={horizonRows(data)}
        emptyLabel="暂无 candidate 失败归因，请先训练 candidate 并运行 promotion gate。"
        columns={[
          { key: "horizon", title: "周期", render: (row) => formatNullable(row.horizon) },
          { key: "failure_reasons", title: "失败原因", render: (row) => formatNullable(row.failure_reasons) },
          { key: "directional_accuracy", title: "方向准确率", render: (row) => formatPercent(row.directional_accuracy as number | null | undefined) },
          { key: "brier_score", title: "Brier", render: (row) => formatNumber(row.brier_score as number | null | undefined, 4) },
          { key: "calibration_error", title: "ECE", render: (row) => formatNumber(row.calibration_error as number | null | undefined, 4) },
          { key: "coverage_rate", title: "覆盖率", render: (row) => formatPercent(row.coverage_rate as number | null | undefined) },
          { key: "cost_adjusted_expectancy", title: "成本后期望", render: (row) => formatNumber(row.cost_adjusted_expectancy as number | null | undefined, 5) },
          { key: "max_drawdown_proxy", title: "回撤代理", render: (row) => formatNumber(row.max_drawdown_proxy as number | null | undefined, 4) },
          { key: "diagnosis", title: "诊断摘要", render: (row) => formatNullable(row.diagnosis) },
        ]}
      />

      <div className="two-column">
        <SectionCard title="高置信分层" subtitle="当前依据已保存的 covered signal 汇总指标做诊断。">
          <DataTable
            data={confidenceRows(selected)}
            emptyLabel="暂无高置信分层数据。"
            columns={[
              { key: "bucket", title: "分层", render: (row) => formatNullable(row.bucket) },
              { key: "coverage", title: "覆盖率", render: (row) => formatPercent(row.coverage as number | null | undefined) },
              { key: "accuracy", title: "准确率", render: (row) => formatPercent(row.accuracy as number | null | undefined) },
              { key: "cost_adjusted_expectancy", title: "成本后期望", render: (row) => formatNumber(row.cost_adjusted_expectancy as number | null | undefined, 5) },
            ]}
          />
        </SectionCard>

        <SectionCard title="校准问题" subtitle="缺少逐样本概率时，先展示 fold 级校准误差。">
          <DataTable
            data={calibrationRows(selected)}
            emptyLabel="暂无校准分层数据。"
            columns={[
              { key: "bin", title: "分组", render: (row) => formatNullable(row.bin) },
              { key: "sample_count", title: "样本数", render: (row) => formatNumber(row.sample_count as number | null | undefined, 0) },
              { key: "brier_contribution", title: "Brier", render: (row) => formatNumber(row.brier_contribution as number | null | undefined, 4) },
              { key: "calibration_error", title: "ECE", render: (row) => formatNumber(row.calibration_error as number | null | undefined, 4) },
            ]}
          />
        </SectionCard>
      </div>

      <div className="two-column">
        <SectionCard title="Regime 与回撤">
          <div className="insight-list">
            {(selected?.regime_performance || []).slice(0, 5).map((row) => (
              <div className="insight-item" key={String(row.regime)}>
                {formatNullable(row.regime)}：样本 {formatNumber(row.sample_count as number | null | undefined, 0)}
                {row.message_zh ? `，${row.message_zh}` : ""}
              </div>
            ))}
          </div>
          <CollapsibleDebug data={selected?.drawdown_attribution || {}} />
        </SectionCard>

        <SectionCard title="特征重要性稳定性">
          <DataTable
            data={featureRows(selected)}
            emptyLabel="暂无特征重要性。"
            columns={[
              { key: "feature", title: "因子", render: (row) => formatNullable(row.feature) },
              { key: "importance", title: "重要性", render: (row) => formatPercent(row.importance as number | null | undefined) },
            ]}
          />
        </SectionCard>
      </div>

      <SectionCard title="下一步研究计划">
        <ol className="ordered-list">
          {(data?.recommended_research_plan || []).map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ol>
      </SectionCard>
    </SectionCard>
  );
}
