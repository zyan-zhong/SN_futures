import { useEffect, useState } from "react";
import {
  getModelResearchExperimentDetail,
  getModelResearchExperiments,
  getResearchArtifacts,
  getThresholdOptimization,
  optimizeResearchStrategy,
  runCandidateV3Research,
  runCandidateV4Research,
  runModelExperiment
} from "../api/terminal";
import type {
  ModelResearchExperimentDetail,
  ModelResearchExperimentList,
  CandidateV3ResearchPayload,
  CandidateV4ResearchPayload,
  ResearchArtifactsPayload,
  StrategyOptimizationPayload,
  ThresholdOptimizationPayload
} from "../api/types";
import { DataTable } from "../components/common/DataTable";
import { EmptyState } from "../components/common/EmptyState";
import { ErrorState } from "../components/common/ErrorState";
import { LoadingState } from "../components/common/LoadingState";
import { SectionCard } from "../components/layout/SectionCard";
import { OOFTracePanel } from "../components/model/OOFTracePanel";
import { formatDateTime, formatNullable, formatPercent } from "../utils/format";

const labelVariants = [
  { value: "direction_thresholded", label: "去噪方向标签" },
  { value: "direction_raw", label: "原始方向标签" },
  { value: "triple_barrier_atr", label: "ATR 三重障碍标签" },
  { value: "high_confidence_meta_label", label: "高置信 meta 标签" }
];

const modelFamilies = [
  { value: "sklearn_hist_gradient", label: "HistGradientBoosting" },
  { value: "lightgbm_gbdt", label: "LightGBM GBDT" },
  { value: "lightgbm_random_forest", label: "LightGBM 随机森林模式" },
  { value: "extra_trees", label: "ExtraTrees 稳定性对照" },
  { value: "random_forest", label: "RandomForest 稳定性对照" }
];

function extractFirstHorizonRows(detail?: ModelResearchExperimentDetail | null) {
  const thresholdResults = detail?.threshold_results as Record<string, unknown> | undefined;
  if (!thresholdResults) return [];
  return Object.entries(thresholdResults).map(([horizon, rows]) => {
    const first = Array.isArray(rows) ? (rows[0] as Record<string, unknown> | undefined) : undefined;
    const top20 = first?.by_coverage && typeof first.by_coverage === "object"
      ? (first.by_coverage as Record<string, Record<string, unknown>>).top_20pct
      : undefined;
    return {
      horizon,
      coverage: top20?.coverage,
      accuracy: top20?.accuracy_at_coverage,
      expectancy: top20?.expectancy_at_coverage,
      drawdown: top20?.drawdown_at_coverage,
      sample_count: top20?.sample_count
    };
  });
}

export function ResearchLabPage() {
  const [labelVariant, setLabelVariant] = useState("direction_thresholded");
  const [modelFamily, setModelFamily] = useState("sklearn_hist_gradient");
  const [experiments, setExperiments] = useState<ModelResearchExperimentList | null>(null);
  const [selectedId, setSelectedId] = useState("");
  const [detail, setDetail] = useState<ModelResearchExperimentDetail | null>(null);
  const [thresholds, setThresholds] = useState<ThresholdOptimizationPayload | null>(null);
  const [candidateV3, setCandidateV3] = useState<CandidateV3ResearchPayload | null>(null);
  const [candidateV4, setCandidateV4] = useState<CandidateV4ResearchPayload | null>(null);
  const [strategyOptimization, setStrategyOptimization] = useState<StrategyOptimizationPayload | null>(null);
  const [artifacts, setArtifacts] = useState<ResearchArtifactsPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function loadExperiments() {
    setError(null);
    try {
      const payload = await getModelResearchExperiments();
      setExperiments(payload);
      const firstId = payload.experiments?.[0]?.experiment_id ?? "";
      if (firstId && !selectedId) setSelectedId(firstId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "研究实验列表暂时无法加载。");
    }
  }

  async function loadDetail(id: string) {
    if (!id) return;
    setError(null);
    try {
      const [detailPayload, thresholdPayload] = await Promise.all([
        getModelResearchExperimentDetail(id),
        getThresholdOptimization(id)
      ]);
      setDetail(detailPayload);
      setThresholds(thresholdPayload);
    } catch (err) {
      setError(err instanceof Error ? err.message : "研究实验详情暂时无法加载。");
    }
  }

  useEffect(() => {
    void loadExperiments();
  }, []);

  useEffect(() => {
    if (selectedId) void loadDetail(selectedId);
  }, [selectedId]);

  async function handleRunExperiment() {
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      const result = await runModelExperiment({
        label_variant: labelVariant,
        model_family: modelFamily,
        feature_set: "usable_real_features"
      });
      setMessage(result.message_zh ?? "研究实验已完成。");
      await loadExperiments();
      if (result.experiment_id) {
        setSelectedId(result.experiment_id);
        await loadDetail(result.experiment_id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "研究实验运行失败。");
    } finally {
      setLoading(false);
    }
  }

  async function handleRunCandidateV3() {
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      const result = await runCandidateV3Research({ horizons: ["1d", "3d", "5d", "10d", "20d"] });
      setCandidateV3(result);
      const [optimizationPayload, artifactsPayload] = await Promise.all([
        optimizeResearchStrategy({ candidate_version: "v3", horizons: ["1d", "3d", "5d", "10d", "20d"] }),
        getResearchArtifacts(result.artifact_run_id)
      ]);
      setStrategyOptimization(optimizationPayload);
      setArtifacts(artifactsPayload);
      setMessage(result.message_zh ?? "candidate_v3 研究流程已完成。");
    } catch (err) {
      setError(err instanceof Error ? err.message : "candidate_v3 研究流程运行失败。");
    } finally {
      setLoading(false);
    }
  }

  async function handleRunCandidateV4() {
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      const result = await runCandidateV4Research({ horizons: ["1d", "3d", "5d", "10d", "20d"] });
      setCandidateV4(result);
      if (result.status !== "blocked") {
        const [optimizationPayload, artifactsPayload] = await Promise.all([
          optimizeResearchStrategy({ candidate_version: "v4", horizons: ["1d", "3d", "5d", "10d", "20d"] }),
          getResearchArtifacts(result.artifact_run_id)
        ]);
        setStrategyOptimization(optimizationPayload);
        setArtifacts(artifactsPayload);
      }
      setMessage(result.message_zh ?? result.reason_zh ?? "candidate_v4 research flow finished.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "candidate_v4 research flow failed.");
    } finally {
      setLoading(false);
    }
  }

  const rows = extractFirstHorizonRows(detail);
  const stability = detail?.feature_stability as Record<string, unknown> | undefined;
  const promotionPreview = detail?.promotion_preview as Record<string, unknown> | undefined;

  return (
    <div className="page-stack">
      <SectionCard
        title="研究实验室"
        subtitle="只做 candidate 改进研究；候选模型不能替代 active，正式上线仍必须通过原 promotion gate。"
        actions={<button className="primary-button" type="button" onClick={handleRunExperiment} disabled={loading}>运行实验</button>}
      >
        <div className="control-grid">
          <label>
            标签变体
            <select value={labelVariant} onChange={(event) => setLabelVariant(event.target.value)}>
              {labelVariants.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
            </select>
          </label>
          <label>
            特征集
            <select value="usable_real_features" disabled>
              <option value="usable_real_features">真实可用因子</option>
            </select>
          </label>
          <label>
            模型族
            <select value={modelFamily} onChange={(event) => setModelFamily(event.target.value)}>
              {modelFamilies.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
            </select>
          </label>
        </div>
        <div className="notice-card">
          <strong>研究边界</strong>
          <span>本页面不发布 active、不生成客户预测、不降低 promotion gate。Logistic/Ridge 仅作为内部对照指标，不进入预测页。</span>
        </div>
        {loading ? <LoadingState label="正在运行模型研究实验..." /> : null}
        {message ? <div className="inline-success">{message}</div> : null}
        {error ? <ErrorState message={error} onRetry={loadExperiments} /> : null}
      </SectionCard>

      <SectionCard title="实验列表" subtitle="每次实验写入独立目录，禁止覆盖旧实验。">
        {experiments?.experiments?.length ? (
          <div className="button-row">
            {experiments.experiments.map((item) => (
              <button
                key={item.experiment_id}
                className={item.experiment_id === selectedId ? "secondary-button active" : "secondary-button"}
                type="button"
                onClick={() => setSelectedId(item.experiment_id ?? "")}
              >
                {formatDateTime(item.created_at)} · {formatNullable(item.status)}
              </button>
            ))}
          </div>
        ) : (
          <EmptyState label="暂无研究实验" description="请先构建训练数据集，然后运行实验。" />
        )}
      </SectionCard>

      <SectionCard title="高置信覆盖率与成本后表现" subtitle="不宣传低覆盖率准确率；必须同时报告覆盖率和样本数。">
        <DataTable
          data={rows}
          emptyLabel="暂无阈值优化结果"
          columns={[
            { key: "horizon", title: "周期" },
            { key: "coverage", title: "覆盖率", render: (row) => formatPercent(row.coverage as number | null | undefined) },
            { key: "accuracy", title: "命中率", render: (row) => formatPercent(row.accuracy as number | null | undefined) },
            { key: "expectancy", title: "成本后期望", format: "number" },
            { key: "drawdown", title: "回撤代理", format: "number" },
            { key: "sample_count", title: "样本数", format: "number" }
          ]}
        />
      </SectionCard>

      <SectionCard title="校准改进与特征稳定性" subtitle="包含 Brier/ECE 分桶、fold-wise importance stability 和不稳定特征黑名单。">
        <div className="metric-grid">
          <div className="metric-card">
            <span>阈值优化</span>
            <strong>{thresholds?.threshold_results ? "已生成" : "数据暂缺"}</strong>
          </div>
          <div className="metric-card">
            <span>特征稳定性</span>
            <strong>{stability ? "已生成" : "数据暂缺"}</strong>
          </div>
          <div className="metric-card">
            <span>Promotion preview</span>
            <strong>{promotionPreview?.eligible_for_active ? "需正式 gate" : "未发布 active"}</strong>
          </div>
        </div>
      </SectionCard>

      <SectionCard title="一键导出实验报告" subtitle="当前实验产物已落盘，可从 artifact_dir 复制或归档。">
        <div className="notice-card">
          <strong>实验目录</strong>
          <span>{formatNullable(detail?.artifact_dir)}</span>
        </div>
        <div className="notice-card">
          <strong>下一步</strong>
          <span>若研究指标改善，仍需单独执行 candidate 训练、walk-forward 验证和严格 promotion gate；未达标则继续保留为研究实验。</span>
        </div>
      </SectionCard>
      <SectionCard
        title="candidate_v3 研究归档"
        subtitle="v1/v2/v3 对比、strategy optimization、artifacts 下载和 promotion dry-run 只用于研究，不发布 active。"
        actions={<button className="secondary-button" type="button" onClick={handleRunCandidateV3} disabled={loading}>运行 candidate_v3</button>}
      >
        <div className="notice-card">
          <strong>研究边界</strong>
          <span>candidate_v3 不会写 active_model.json，不生成客户预测，不降低 promotion gate。</span>
        </div>
        <div className="metric-grid">
          <div className="metric-card">
            <span>candidate_v3</span>
            <strong>{candidateV3?.status ?? "not_run"}</strong>
          </div>
          <div className="metric-card">
            <span>strategy optimization</span>
            <strong>{strategyOptimization?.status ?? "not_run"}</strong>
          </div>
          <div className="metric-card">
            <span>artifacts 下载</span>
            <strong>{artifacts?.artifact_dir ?? candidateV3?.artifact_dir ?? "not_ready"}</strong>
          </div>
        </div>
        <div className="data-table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Version</th>
                <th>Scope</th>
                <th>Status</th>
                <th>Active</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>v1/v2/v3 对比</td>
                <td>research only</td>
                <td>{candidateV3?.promotion_dry_run?.status ?? "等待运行"}</td>
                <td>{candidateV3?.active_updated ? "unexpected" : "not written"}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </SectionCard>
      <SectionCard
        title="candidate_v4 readiness and research"
        subtitle="v4 only runs when real cross-market or event incremental fields pass the coverage gate; otherwise it returns a blocking reason."
        actions={<button className="secondary-button" type="button" onClick={handleRunCandidateV4} disabled={loading}>Run candidate_v4</button>}
      >
        <div className="notice-card">
          <strong>Research boundary</strong>
          <span>candidate_v4 does not write active_model.json, does not generate customer predictions, and does not lower the promotion gate.</span>
        </div>
        <div className="metric-grid">
          <div className="metric-card">
            <span>v4 readiness</span>
            <strong>{candidateV4?.status ?? "not_run"}</strong>
          </div>
          <div className="metric-card">
            <span>incremental fields</span>
            <strong>{candidateV4?.incremental_feature_cols?.length ?? 0}</strong>
          </div>
          <div className="metric-card">
            <span>promotion dry-run</span>
            <strong>{candidateV4?.promotion_dry_run?.status ?? "not_run"}</strong>
          </div>
        </div>
        {candidateV4?.status === "blocked" ? (
          <div className="empty-state">{candidateV4.reason_zh ?? "No real incremental cross-market/event fields were available, so candidate_v4 was not trained."}</div>
        ) : null}
        <div className="data-table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Version</th>
                <th>New fields</th>
                <th>Artifacts</th>
                <th>Active</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>v1/v2/v3/v4 comparison</td>
                <td>{candidateV4?.incremental_feature_cols?.join(", ") || "blocked or not_run"}</td>
                <td>{candidateV4?.artifact_dir ?? "not_ready"}</td>
                <td>{candidateV4?.active_updated ? "unexpected" : "not written"}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </SectionCard>
      {selectedId ? <OOFTracePanel experimentId={selectedId} /> : null}
    </div>
  );
}
