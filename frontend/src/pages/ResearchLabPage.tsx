import { useEffect, useState } from "react";
import {
  getModelResearchExperimentDetail,
  getModelResearchExperiments,
  getLearningSchedulerStatus,
  getActiveAbsenceDiagnostics,
  getResearchArtifacts,
  getThresholdOptimization,
  approveActiveModel,
  optimizeResearchStrategy,
  pauseLearningScheduler,
  resumeLearningScheduler,
  runLearningScheduler,
  runCandidateV3Research,
  runCandidateV4Research,
  runCandidateV6Research,
  runCandidateV7Research,
  runCandidateV8Research,
  runCandidateV9Research,
  runCandidateV10Research,
  getCandidateV10Report,
  runCandidateV12Research,
  getCandidateV12Report,
  getYearConcentration,
  refreshYearConcentration,
  getCostStressAttribution,
  refreshCostStressAttribution,
  getV10CostRemediation,
  refreshV10CostRemediation,
  getV10RemediationPreflight,
  refreshV10RemediationPreflight,
  getShadowModeReadiness,
  refreshShadowModeReadiness,
  getModelRegistrySafety,
  refreshModelRegistrySafety,
  getEvidenceBundle,
  refreshEvidenceBundle,
  getEvidenceFreshness,
  refreshEvidenceFreshness,
  getHypothesisRegistry,
  createHypothesisTemplate,
  refreshAntiPHackingLedger,
  getRunLedger,
  refreshRunLedger,
  getReadinessDag,
  refreshReadinessDag,
  runSafeReadinessChecks,
  getPredictionWorkspaceStatus,
  getResearchDecisionBoard,
  refreshResearchDecisionBoard,
  getCandidateV8Diagnostics,
  getCpcvValidationReport,
  runModelExperiment
} from "../api/terminal";
import type {
  ModelResearchExperimentDetail,
  ModelResearchExperimentList,
  ActiveAbsenceDiagnosticsPayload,
  CandidateV3ResearchPayload,
  CandidateV4ResearchPayload,
  CandidateV6ResearchPayload,
  CandidateV7ResearchPayload,
  CandidateV8ResearchPayload,
  CandidateV9ResearchPayload,
  CandidateV10ResearchPayload,
  CandidateV12ResearchPayload,
  CandidateV8DiagnosticsPayload,
  CPCVValidationPayload,
  YearConcentrationPayload,
  CostStressAttributionPayload,
  V10CostRemediationPayload,
  CandidateV10RemediationPreflightPayload,
  ShadowModeReadinessPayload,
  ModelRegistrySafetyPayload,
  EvidenceBundlePayload,
  EvidenceFreshnessPayload,
  HypothesisRegistryPayload,
  AntiPHackingLedgerPayload,
  ResearchRunLedgerPayload,
  ReadinessDagPayload,
  PredictionWorkspaceStatusPayload,
  ResearchDecisionBoardPayload,
  ActiveReleaseApprovalPayload,
  LearningSchedulerStatus,
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

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function asStringList(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => String(item)).filter(Boolean) : [];
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
  const [candidateV6, setCandidateV6] = useState<CandidateV6ResearchPayload | null>(null);
  const [candidateV7, setCandidateV7] = useState<CandidateV7ResearchPayload | null>(null);
  const [candidateV8, setCandidateV8] = useState<CandidateV8ResearchPayload | null>(null);
  const [candidateV9, setCandidateV9] = useState<CandidateV9ResearchPayload | null>(null);
  const [candidateV10, setCandidateV10] = useState<CandidateV10ResearchPayload | null>(null);
  const [candidateV12, setCandidateV12] = useState<CandidateV12ResearchPayload | null>(null);
  const [yearConcentration, setYearConcentration] = useState<YearConcentrationPayload | null>(null);
  const [costStressAttribution, setCostStressAttribution] = useState<CostStressAttributionPayload | null>(null);
  const [v10CostRemediation, setV10CostRemediation] = useState<V10CostRemediationPayload | null>(null);
  const [v10RemediationPreflight, setV10RemediationPreflight] = useState<CandidateV10RemediationPreflightPayload | null>(null);
  const [shadowModeReadiness, setShadowModeReadiness] = useState<ShadowModeReadinessPayload | null>(null);
  const [modelRegistrySafety, setModelRegistrySafety] = useState<ModelRegistrySafetyPayload | null>(null);
  const [evidenceBundle, setEvidenceBundle] = useState<EvidenceBundlePayload | null>(null);
  const [evidenceFreshness, setEvidenceFreshness] = useState<EvidenceFreshnessPayload | null>(null);
  const [hypothesisRegistry, setHypothesisRegistry] = useState<HypothesisRegistryPayload | null>(null);
  const [antiPHackingLedger, setAntiPHackingLedger] = useState<AntiPHackingLedgerPayload | null>(null);
  const [runLedger, setRunLedger] = useState<ResearchRunLedgerPayload | null>(null);
  const [readinessDag, setReadinessDag] = useState<ReadinessDagPayload | null>(null);
  const [predictionWorkspace, setPredictionWorkspace] = useState<PredictionWorkspaceStatusPayload | null>(null);
  const [decisionBoard, setDecisionBoard] = useState<ResearchDecisionBoardPayload | null>(null);
  const [candidateV8Diagnostics, setCandidateV8Diagnostics] = useState<CandidateV8DiagnosticsPayload | null>(null);
  const [cpcvValidation, setCpcvValidation] = useState<CPCVValidationPayload | null>(null);
  const [activeAbsence, setActiveAbsence] = useState<ActiveAbsenceDiagnosticsPayload | null>(null);
  const [learningScheduler, setLearningScheduler] = useState<LearningSchedulerStatus | null>(null);
  const [activeApproval, setActiveApproval] = useState<ActiveReleaseApprovalPayload | null>(null);
  const [approvalPhrase, setApprovalPhrase] = useState("");
  const [approver, setApprover] = useState("");
  const [approvalNotes, setApprovalNotes] = useState("");
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

  async function loadLearningScheduler() {
    try {
      const payload = await getLearningSchedulerStatus();
      setLearningScheduler(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : "自学习调度器状态暂时无法加载。");
    }
  }

  async function loadActiveAbsenceDiagnostics() {
    try {
      const payload = await getActiveAbsenceDiagnostics();
      setActiveAbsence(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : "active absence diagnostics failed.");
    }
  }

  async function loadCandidateV12Report() {
    try {
      const payload = await getCandidateV12Report();
      setCandidateV12(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : "candidate_v12 report failed.");
    }
  }

  async function loadCandidateV10Report() {
    try {
      const payload = await getCandidateV10Report();
      setCandidateV10(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : "candidate_v10 report failed.");
    }
  }

  async function loadYearConcentration() {
    try {
      const payload = await getYearConcentration();
      setYearConcentration(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : "year concentration evidence failed.");
    }
  }

  async function loadCostStressAttribution() {
    try {
      const payload = await getCostStressAttribution();
      setCostStressAttribution(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : "cost stress attribution failed.");
    }
  }

  async function loadV10CostRemediation() {
    try {
      const payload = await getV10CostRemediation();
      setV10CostRemediation(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : "v10 cost remediation sandbox failed.");
    }
  }

  async function loadV10RemediationPreflight() {
    try {
      const payload = await getV10RemediationPreflight();
      setV10RemediationPreflight(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : "v10 remediation preflight failed.");
    }
  }

  async function loadShadowModeReadiness() {
    try {
      const payload = await getShadowModeReadiness();
      setShadowModeReadiness(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : "shadow mode readiness failed.");
    }
  }

  async function loadModelRegistrySafety() {
    try {
      const payload = await getModelRegistrySafety();
      setModelRegistrySafety(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : "model registry safety failed.");
    }
  }

  async function loadEvidenceBundle() {
    try {
      const payload = await getEvidenceBundle();
      setEvidenceBundle(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : "evidence bundle failed.");
    }
  }

  async function loadEvidenceFreshness() {
    try {
      const payload = await getEvidenceFreshness();
      setEvidenceFreshness(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : "evidence freshness failed.");
    }
  }

  async function loadHypothesisRegistry() {
    try {
      const payload = await getHypothesisRegistry();
      setHypothesisRegistry(payload);
      setAntiPHackingLedger(payload.anti_p_hacking_ledger ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "hypothesis registry failed.");
    }
  }

  async function loadRunLedger() {
    try {
      const payload = await getRunLedger();
      setRunLedger(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : "run ledger failed.");
    }
  }

  async function loadReadinessDag() {
    try {
      const payload = await getReadinessDag();
      setReadinessDag(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : "readiness DAG failed.");
    }
  }

  async function loadResearchDecisionBoard() {
    try {
      const payload = await getResearchDecisionBoard();
      setDecisionBoard(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : "research decision board failed.");
    }
  }

  async function loadPredictionWorkspaceStatus() {
    try {
      const payload = await getPredictionWorkspaceStatus();
      setPredictionWorkspace(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : "prediction workspace status failed.");
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
    void loadLearningScheduler();
    void loadActiveAbsenceDiagnostics();
    void loadCandidateV10Report();
    void loadCandidateV12Report();
    void loadYearConcentration();
    void loadCostStressAttribution();
    void loadV10CostRemediation();
    void loadV10RemediationPreflight();
    void loadShadowModeReadiness();
    void loadModelRegistrySafety();
    void loadEvidenceBundle();
    void loadEvidenceFreshness();
    void loadHypothesisRegistry();
    void loadRunLedger();
    void loadReadinessDag();
    void loadPredictionWorkspaceStatus();
    void loadResearchDecisionBoard();
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

  async function handleRunCandidateV6() {
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      const result = await runCandidateV6Research({ horizons: ["1d", "3d", "5d", "10d", "20d"] });
      setCandidateV6(result);
      setMessage(result.message_zh ?? "candidate_v6 gated research task submitted.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "candidate_v6 gated research flow failed.");
    } finally {
      setLoading(false);
    }
  }

  async function handleRunCandidateV7() {
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      const result = await runCandidateV7Research({ horizons: ["1d", "3d", "5d", "10d", "20d"] });
      setCandidateV7(result);
      setMessage(result.message_zh ?? "candidate_v7 stability research task submitted.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "candidate_v7 stability research flow failed.");
    } finally {
      setLoading(false);
    }
  }

  async function handleRunCandidateV8() {
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      const result = await runCandidateV8Research({ horizons: ["1d", "3d", "5d", "10d", "20d"] });
      setCandidateV8(result);
      setMessage(result.message_zh ?? "candidate_v8 stability research task submitted.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "candidate_v8 stability research flow failed.");
    } finally {
      setLoading(false);
    }
  }

  async function handleRunCandidateV9() {
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      const result = await runCandidateV9Research({ horizons: ["1d", "3d", "5d", "10d", "20d"] });
      setCandidateV9(result);
      setMessage(result.message_zh ?? "candidate_v9 regime-neutral research task submitted.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "candidate_v9 regime-neutral research flow failed.");
    } finally {
      setLoading(false);
    }
  }

  async function handleRunCandidateV10() {
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      const result = await runCandidateV10Research({ horizons: ["1d", "3d", "5d", "10d", "20d"] });
      setCandidateV10(result);
      setMessage(result.message_zh ?? "candidate_v10 regime-balanced CPCV research task submitted.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "candidate_v10 CPCV research flow failed.");
    } finally {
      setLoading(false);
    }
  }

  async function handleRunCandidateV12() {
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      const result = await runCandidateV12Research({ horizons: ["1d", "3d", "5d", "10d", "20d"] });
      setMessage(result.message_zh ?? "candidate_v12 research gate task submitted.");
      await loadCandidateV12Report();
    } catch (err) {
      setError(err instanceof Error ? err.message : "candidate_v12 research gate failed.");
    } finally {
      setLoading(false);
    }
  }

  async function handleRefreshYearConcentration() {
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      const result = await refreshYearConcentration();
      setYearConcentration(result);
      await Promise.all([loadCandidateV10Report(), loadCandidateV12Report()]);
      setMessage("year concentration evidence refreshed from existing OOF traces.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "year concentration evidence refresh failed.");
    } finally {
      setLoading(false);
    }
  }

  async function handleRefreshCostStressAttribution() {
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      const result = await refreshCostStressAttribution();
      setCostStressAttribution(result);
      await Promise.all([loadCandidateV10Report(), loadCandidateV12Report()]);
      setMessage("cost stress attribution refreshed from existing reports and OOF traces.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "cost stress attribution refresh failed.");
    } finally {
      setLoading(false);
    }
  }

  async function handleRefreshV10CostRemediation() {
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      const result = await refreshV10CostRemediation();
      setV10CostRemediation(result);
      setMessage("v10 cost remediation sandbox refreshed from existing OOF only.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "v10 cost remediation sandbox refresh failed.");
    } finally {
      setLoading(false);
    }
  }

  async function handleRefreshV10RemediationPreflight() {
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      const result = await refreshV10RemediationPreflight();
      setV10RemediationPreflight(result);
      setMessage("v10 remediation preflight refreshed from registered hypotheses and existing evidence only.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "v10 remediation preflight refresh failed.");
    } finally {
      setLoading(false);
    }
  }

  async function handleRefreshShadowModeReadiness() {
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      const result = await refreshShadowModeReadiness();
      setShadowModeReadiness(result);
      setMessage("shadow mode readiness refreshed without active or customer prediction outputs.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "shadow mode readiness refresh failed.");
    } finally {
      setLoading(false);
    }
  }

  async function handleRefreshModelRegistrySafety() {
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      const result = await refreshModelRegistrySafety();
      setModelRegistrySafety(result);
      setMessage("model registry safety refreshed without model registration or active write.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "model registry safety refresh failed.");
    } finally {
      setLoading(false);
    }
  }

  async function handleRefreshEvidenceBundle() {
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      const result = await refreshEvidenceBundle();
      setEvidenceBundle(result);
      setMessage("evidence bundle refreshed from existing reports only.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "evidence bundle refresh failed.");
    } finally {
      setLoading(false);
    }
  }

  async function handleRefreshEvidenceFreshness() {
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      const result = await refreshEvidenceFreshness();
      setEvidenceFreshness(result);
      setMessage("evidence freshness refreshed from existing reports only.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "evidence freshness refresh failed.");
    } finally {
      setLoading(false);
    }
  }

  async function handleRefreshAntiPHackingLedger() {
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      const result = await refreshAntiPHackingLedger();
      setAntiPHackingLedger(result);
      await loadHypothesisRegistry();
      setMessage("anti-p-hacking ledger refreshed without experiment execution.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "anti-p-hacking ledger refresh failed.");
    } finally {
      setLoading(false);
    }
  }

  async function handleCreateHypothesisTemplate() {
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      await createHypothesisTemplate({ remediation_id: String(v10CostRemediation?.recommended_next_experiment ?? "") });
      await loadHypothesisRegistry();
      setMessage("hypothesis template registered; no experiment was executed.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "hypothesis template creation failed.");
    } finally {
      setLoading(false);
    }
  }

  async function handleRefreshRunLedger() {
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      const result = await refreshRunLedger();
      setRunLedger(result);
      setMessage("run ledger refreshed from current safe reports only.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "run ledger refresh failed.");
    } finally {
      setLoading(false);
    }
  }

  async function handleRefreshReadinessDag() {
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      const result = await refreshReadinessDag();
      setReadinessDag(result);
      setMessage("readiness DAG refreshed from existing evidence only.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "readiness DAG refresh failed.");
    } finally {
      setLoading(false);
    }
  }

  async function handleRunSafeReadinessChecks() {
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      const result = await runSafeReadinessChecks();
      setReadinessDag(result);
      await Promise.all([loadResearchDecisionBoard(), loadEvidenceBundle(), loadEvidenceFreshness()]);
      setMessage("safe readiness checks finished without training, v12 build, active, or prediction.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "safe readiness checks failed.");
    } finally {
      setLoading(false);
    }
  }

  async function handleRefreshResearchDecisionBoard() {
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      const result = await refreshResearchDecisionBoard();
      setDecisionBoard(result);
      setMessage("research decision board refreshed from existing reports.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "research decision board refresh failed.");
    } finally {
      setLoading(false);
    }
  }

  async function handleLoadCandidateV8Diagnostics() {
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      const result = await getCandidateV8Diagnostics();
      setCandidateV8Diagnostics(result);
      setMessage("candidate_v8 validation diagnostics loaded.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "candidate_v8 validation diagnostics failed.");
    } finally {
      setLoading(false);
    }
  }

  async function handleLoadCpcvValidation() {
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      const result = await getCpcvValidationReport("v9");
      setCpcvValidation(result);
      setMessage(result.message_zh ?? "CPCV multi-path validation report loaded.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "CPCV validation report failed.");
    } finally {
      setLoading(false);
    }
  }

  async function handleRunLearningScheduler() {
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      const result = await runLearningScheduler({ force: true, manual: true });
      setLearningScheduler(result);
      setMessage(result.message_zh ?? "自学习调度器已手动运行。");
    } catch (err) {
      setError(err instanceof Error ? err.message : "自学习调度器运行失败。");
    } finally {
      setLoading(false);
    }
  }

  async function handlePauseLearningScheduler() {
    const result = await pauseLearningScheduler("用户在模型研究页暂停。");
    setLearningScheduler(result);
  }

  async function handleResumeLearningScheduler() {
    const result = await resumeLearningScheduler();
    setLearningScheduler(result);
  }

  async function handleApproveActive() {
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      const result = await approveActiveModel({
        candidate_version: "v5",
        approval_phrase: approvalPhrase,
        approver,
        notes: approvalNotes
      });
      setActiveApproval(result);
      setMessage(result.message_zh ?? "人工审批 active 流程已执行。");
    } catch (err) {
      setError(err instanceof Error ? err.message : "人工审批 active 发布失败。");
    } finally {
      setLoading(false);
    }
  }

  const rows = extractFirstHorizonRows(detail);
  const stability = detail?.feature_stability as Record<string, unknown> | undefined;
  const promotionPreview = detail?.promotion_preview as Record<string, unknown> | undefined;
  const featureStabilityEvidence = activeAbsence?.feature_stability_evidence ?? {};
  const featureStabilityMetric = asRecord(activeAbsence?.blocking_metrics?.feature_stability_score);
  const unstableFeatures = asStringList(featureStabilityEvidence.unstable_features).slice(0, 8);
  const stabilityRecommendations = asStringList(featureStabilityEvidence.recommendations).slice(0, 3);
  const candidateV7StabilityObjective = asRecord(candidateV7?.stability_objective);
  const candidateV7Metrics = asRecord(candidateV7StabilityObjective.metrics);
  const candidateV7Evidence = asRecord(candidateV7?.v7_feature_evidence);
  const candidateV7CostFeatures = asStringList(candidateV7Evidence.cost_features);
  const candidateV7PositioningFeatures = asStringList(candidateV7Evidence.positioning_features);
  const candidateV7Comparison = asRecord(candidateV7?.v6_vs_v7);
  const candidateV7CompareV6 = asRecord(candidateV7Comparison.v6);
  const candidateV7CompareV7 = asRecord(candidateV7Comparison.v7);
  const candidateV8Policy = asRecord(candidateV8?.stable_strategy_policy);
  const candidateV8Thresholds = asRecord(candidateV8Policy.threshold_policy);
  const candidateV8Complexity = asRecord(candidateV8Policy.complexity);
  const candidateV8Comparison = asRecord(candidateV8?.v7_vs_v8);
  const candidateV8CompareV7 = asRecord(candidateV8Comparison.v7);
  const candidateV8CompareV8 = asRecord(candidateV8Comparison.v8);
  const candidateV8Improvement = asRecord(candidateV8Comparison.improvement);
  const candidateV8Models = asStringList(candidateV8Complexity.models);
  const candidateV8PboAttribution = asRecord(candidateV8Diagnostics?.pbo_attribution);
  const candidateV8PboSummary = asRecord(candidateV8PboAttribution.summary);
  const candidateV8Reality = asRecord(candidateV8Diagnostics?.reality_check_bootstrap_summary);
  const candidateV8Regime = asRecord(candidateV8Diagnostics?.regime_concentration_attribution);
  const candidateV9Policy = asRecord(candidateV9?.regime_neutral_policy);
  const candidateV9RegimeQuota = asRecord(candidateV9Policy.regime_trade_quota);
  const candidateV9FoldQuota = asRecord(candidateV9Policy.fold_trade_quota);
  const candidateV9YearQuota = asRecord(candidateV9Policy.year_trade_quota);
  const candidateV9Comparison = asRecord(candidateV9?.v8_vs_v9);
  const candidateV9CompareV8 = asRecord(candidateV9Comparison.v8);
  const candidateV9CompareV9 = asRecord(candidateV9Comparison.v9);
  const candidateV10Comparison = asRecord(candidateV10?.v10_vs_v9);
  const candidateV10CompareV9 = asRecord(candidateV10Comparison.v9);
  const candidateV10CompareV10 = asRecord(candidateV10Comparison.v10);
  const candidateV10GateChecks = asRecord(candidateV10?.v10_gate_checks);
  const candidateV10Cpcv = asRecord(candidateV10?.cpcv_validation);
  const candidateV10CpcvPbo = asRecord(candidateV10Cpcv.pbo);
  const candidateV10CpcvReality = asRecord(candidateV10Cpcv.reality_check);
  const yearCandidateV10 = asRecord(yearConcentration?.candidate_v10);
  const yearCandidateV12 = asRecord(yearConcentration?.candidate_v12);
  const candidateV10YearConcentration = asRecord(candidateV10?.year_concentration_evidence ?? yearCandidateV10.year_concentration_evidence);
  const costCandidateV10 = asRecord(costStressAttribution?.candidate_v10);
  const costCandidateV12 = asRecord(costStressAttribution?.candidate_v12);
  const candidateV10CostAttribution = asRecord(candidateV10?.cost_stress_attribution ?? costCandidateV10.cost_stress_attribution);
  const candidateV12CostAttribution = asRecord(candidateV12?.cost_stress_attribution ?? costCandidateV12.cost_stress_attribution);
  const candidateV10CostByHorizon = asRecord(candidateV10CostAttribution.by_horizon);
  const candidateV10CostByRegime = asRecord(candidateV10CostAttribution.by_regime);
  const candidateV10CostByYear = asRecord(candidateV10CostAttribution.by_year);
  const candidateV10TurnoverDiagnostics = asRecord(candidateV10CostAttribution.turnover_diagnostics);
  const candidateV10SignalFlipDiagnostics = asRecord(candidateV10CostAttribution.signal_flip_diagnostics);
  const candidateV10HoldingDiagnostics = asRecord(candidateV10CostAttribution.holding_period_diagnostics);
  const candidateV10CostHorizonRows = Array.isArray(candidateV10CostByHorizon.rows) ? candidateV10CostByHorizon.rows as Record<string, unknown>[] : [];
  const candidateV10CostRegimeRows = Array.isArray(candidateV10CostByRegime.rows) ? candidateV10CostByRegime.rows as Record<string, unknown>[] : [];
  const candidateV10CostYearRows = Array.isArray(candidateV10CostByYear.rows) ? candidateV10CostByYear.rows as Record<string, unknown>[] : [];
  const v10RemediationHypotheses = Array.isArray(v10CostRemediation?.ranked_hypotheses)
    ? v10CostRemediation.ranked_hypotheses as Record<string, unknown>[]
    : [];
  const v10RemediationCounterfactuals = Array.isArray(v10CostRemediation?.no_train_counterfactuals)
    ? v10CostRemediation.no_train_counterfactuals as Record<string, unknown>[]
    : [];
  const v10RemediationBest = asRecord(v10CostRemediation?.best_no_train_counterfactual);
  const preflightOverfitting = asRecord(v10RemediationPreflight?.overfitting_risk);
  const preflightMetricBudget = asRecord(v10RemediationPreflight?.metric_budget_status);
  const preflightRecommendedRows = Array.isArray(v10RemediationPreflight?.recommended_experiment_order)
    ? v10RemediationPreflight.recommended_experiment_order as Record<string, unknown>[]
    : [];
  const preflightBlockedRows = Array.isArray(v10RemediationPreflight?.blocked_experiments)
    ? v10RemediationPreflight.blocked_experiments as Record<string, unknown>[]
    : [];
  const preflightWarnings = asStringList(v10RemediationPreflight?.warnings);
  const preflightBlockingReasons = asStringList(v10RemediationPreflight?.blocking_reasons);
  const shadowEntryGates = Array.isArray(shadowModeReadiness?.entry_gates)
    ? shadowModeReadiness.entry_gates as Record<string, unknown>[]
    : [];
  const shadowBlockedGates = asStringList(shadowModeReadiness?.blocked_gates);
  const shadowOutputContract = asRecord(shadowModeReadiness?.output_isolation_contract);
  const shadowPredictionIsolation = asRecord(shadowModeReadiness?.prediction_isolation);
  const shadowForbiddenOutputs = asStringList(shadowModeReadiness?.forbidden_outputs);
  const registrySafetyRollback = asRecord(modelRegistrySafety?.rollback_plan);
  const registrySafetyContract = asRecord(modelRegistrySafety?.contract);
  const registrySafetyPreconditions = asRecord(modelRegistrySafety?.preconditions);
  const registrySafetyRollbackCandidates = Array.isArray(registrySafetyRollback.rollback_candidates)
    ? registrySafetyRollback.rollback_candidates as Record<string, unknown>[]
    : [];
  const registrySafetyBlockingReasons = asStringList(modelRegistrySafety?.blocking_reasons);
  const registrySafetyRequiredPreconditions = asStringList(registrySafetyContract.required_preconditions);
  const candidateV12ReadinessChecks = asRecord(candidateV12?.readiness_checks);
  const candidateV12Reality = asRecord(candidateV12?.reality_check);
  const candidateV12CostStress = asRecord(candidateV12?.institutional_cost_stress);
  const candidateV12TwoXCost = asRecord(candidateV12CostStress["2x_cost"]);
  const candidateV12ThreeXCost = asRecord(candidateV12CostStress["3x_cost"]);
  const candidateV12YearConcentration = asRecord(candidateV12?.year_concentration_evidence ?? yearCandidateV12.year_concentration_evidence);
  const candidateV12GateChecks = asRecord(candidateV12?.gate_checks);
  const candidateV12Comparison = asRecord(candidateV12?.v12_vs_v10);
  const candidateV12CompareV10 = asRecord(candidateV12Comparison.v10);
  const candidateV12CompareV12 = asRecord(candidateV12Comparison.v12);
  const candidateV12Promotion = asRecord(candidateV12?.promotion_dry_run_result);
  const cpcvPbo = asRecord(cpcvValidation?.pbo);
  const cpcvReality = asRecord(cpcvValidation?.reality_check);
  const decisionBoardEvidencePaths = decisionBoard?.evidence_paths ?? {};
  const decisionBoardTopBlockers = asStringList(decisionBoard?.blocking_reasons).slice(0, 8);
  const decisionBoardStaleMissing = asStringList(decisionBoard?.stale_or_missing_reports).slice(0, 8);
  const predictionRequiredGates = asStringList(predictionWorkspace?.required_gates);
  const predictionBlockingReasons = asStringList(predictionWorkspace?.blocking_reasons).slice(0, 8);
  const currentResearchState = decisionBoard?.current_research_state ?? predictionWorkspace?.current_research_state ?? "managed_data_blocked";
  const nextAllowedAction = decisionBoard?.next_allowed_action ?? predictionWorkspace?.next_allowed_action ?? "configure_managed_proxy_endpoint_or_token";
  const activePublishAllowed = Boolean(decisionBoard?.active_publish_allowed ?? predictionWorkspace?.active_publish_allowed ?? false);
  const customerPredictionGenerated = Boolean(decisionBoard?.customer_prediction_generated ?? predictionWorkspace?.customer_prediction_generated ?? false);
  const candidateSummaryRows = [
    {
      candidate: "candidate_v12",
      status: candidateV12?.status ?? String(decisionBoard?.candidate_v12_summary?.status ?? "blocked"),
      scope: "current gated research",
      approval: candidateV12?.manual_approval_recommended ? "manual review possible" : "blocked",
      active: candidateV12?.active_updated ? "unexpected" : "not written"
    },
    {
      candidate: "candidate_v10",
      status: candidateV10?.status ?? String(decisionBoard?.candidate_v10_summary?.status ?? "research_only"),
      scope: "latest completed research evidence",
      approval: candidateV10?.manual_approval_recommended ? "manual review possible" : "blocked",
      active: candidateV10?.active_updated ? "unexpected" : "not written"
    }
  ];
  const evidenceMissingReports = asStringList(evidenceBundle?.missing_reports);
  const evidenceIncompleteReports = asStringList(evidenceBundle?.incomplete_reports);
  const evidenceChecklist = asRecord(evidenceBundle?.reproducibility_checklist);
  const evidenceSafetyFlags = asStringList(evidenceBundle?.safety_flags);
  const evidenceProblemReports = [
    ...evidenceMissingReports.map((name) => ({ name, state: "missing" })),
    ...evidenceIncompleteReports.map((name) => ({ name, state: "incomplete" }))
  ];
  const freshnessStaleReports = asStringList(evidenceFreshness?.stale_reports);
  const freshnessMissingTimestamps = asStringList(evidenceFreshness?.missing_timestamps);
  const freshnessBlockingReasons = asStringList(evidenceFreshness?.blocking_reasons);
  const freshnessTimestampInversions = Array.isArray(evidenceFreshness?.timestamp_inversions)
    ? evidenceFreshness.timestamp_inversions as Record<string, unknown>[]
    : [];
  const freshnessProblemReports = [
    ...freshnessStaleReports.map((name) => ({ name, state: "stale" })),
    ...freshnessMissingTimestamps.map((name) => ({ name, state: "missing timestamp" }))
  ];
  const hypothesisRows = Array.isArray(hypothesisRegistry?.hypotheses)
    ? hypothesisRegistry.hypotheses as Record<string, unknown>[]
    : [];
  const openHypothesisRows = hypothesisRows.filter((row) => String(row.status ?? "open") === "open");
  const hypothesisTemplates = Array.isArray(hypothesisRegistry?.hypothesis_templates)
    ? hypothesisRegistry.hypothesis_templates as Record<string, unknown>[]
    : [];
  const ledger = antiPHackingLedger ?? hypothesisRegistry?.anti_p_hacking_ledger ?? null;
  const experimentBudgetByBlocker = ledger?.experiment_budget_by_blocker ?? hypothesisRegistry?.experiment_budget_by_blocker ?? {};
  const experimentBudgetRows = Object.entries(experimentBudgetByBlocker).map(([blocker, payload]) => ({
    linked_blocker: blocker,
    registered_hypotheses: String(payload.registered_hypotheses ?? 0),
    remaining_budget: String(payload.remaining_budget ?? 0)
  }));
  const linkedBlockers = Array.from(new Set(hypothesisRows.map((row) => String(row.linked_blocker ?? "")).filter(Boolean)));
  const runLedgerRows = Array.isArray(runLedger?.latest_runs) ? runLedger.latest_runs as Record<string, unknown>[] : [];
  const runLedgerForbidden = asStringList(runLedger?.forbidden_side_effects);
  const readinessCriticalPath = asStringList(readinessDag?.critical_path);
  const readinessBlockedNodes = asStringList(readinessDag?.blocked_nodes);
  const readinessSkippedNodes = asStringList(readinessDag?.skipped_nodes);
  const readinessSafeChecks = asStringList(readinessDag?.runnable_safe_checks);
  const readinessForbiddenActions = asStringList(readinessDag?.forbidden_actions);
  const readinessTopBlockers = asStringList(readinessDag?.top_blockers);

  return (
    <div className="page-stack">
      <SectionCard
        title="Current State"
        subtitle="Research governance summary for the terminal; safe reads only, no training or prediction side effects."
      >
        <div className="metric-grid">
          <div className="metric-card">
            <span>current_research_state</span>
            <strong>{currentResearchState}</strong>
          </div>
          <div className="metric-card">
            <span>next_allowed_action</span>
            <strong>{nextAllowedAction}</strong>
          </div>
          <div className="metric-card">
            <span>active_publish_allowed</span>
            <strong>{String(activePublishAllowed)}</strong>
          </div>
          <div className="metric-card">
            <span>customer_prediction_generated</span>
            <strong>{String(customerPredictionGenerated)}</strong>
          </div>
        </div>
        <div className="notice-card">
          <strong>Active artifact write unavailable</strong>
          <span>No active artifact write action is available from this page while the governance board is blocked.</span>
        </div>
      </SectionCard>

      <SectionCard
        title="Prediction Workspace"
        subtitle="Blocked placeholder for future prediction workflows; it reports gates and never creates customer-visible output."
      >
        <div className="metric-grid">
          <div className="metric-card">
            <span>prediction_status</span>
            <strong>{predictionWorkspace?.prediction_status ?? "blocked"}</strong>
          </div>
          <div className="metric-card">
            <span>active_model_available</span>
            <strong>{String(predictionWorkspace?.active_model_available ?? false)}</strong>
          </div>
          <div className="metric-card">
            <span>prediction_generation_allowed</span>
            <strong>{String(predictionWorkspace?.prediction_generation_allowed ?? false)}</strong>
          </div>
          <div className="metric-card">
            <span>customer_prediction_generated</span>
            <strong>{String(predictionWorkspace?.customer_prediction_generated ?? false)}</strong>
          </div>
        </div>
        <div className="notice-card">
          <strong>no customer-visible output confirmation</strong>
          <span>Customer prediction paths remain forbidden until a future approved workflow explicitly separates shadow, active, and customer outputs.</span>
        </div>
        <DataTable
          data={predictionRequiredGates.map((gate) => ({ gate }))}
          emptyLabel="No prediction workspace gates loaded"
          columns={[{ key: "gate", title: "required_gates" }]}
        />
        <DataTable
          data={predictionBlockingReasons.map((reason) => ({ reason }))}
          emptyLabel="No prediction workspace blockers loaded"
          columns={[{ key: "reason", title: "blocking_reasons" }]}
        />
      </SectionCard>

      <SectionCard
        title="Candidate Research"
        subtitle="Current candidate evidence is research-only; archived candidate runs are collapsed below."
      >
        <DataTable
          data={candidateSummaryRows}
          columns={[
            { key: "candidate", title: "Candidate" },
            { key: "status", title: "Status" },
            { key: "scope", title: "Scope" },
            { key: "approval", title: "Manual approval" },
            { key: "active", title: "Active" }
          ]}
        />
      </SectionCard>

      <SectionCard
        title="Research Decision Board"
        subtitle="Unified research gate state from managed data, PIT audit, feature store, datasets, candidates, validation, and attribution."
        actions={<button className="secondary-button" type="button" onClick={handleRefreshResearchDecisionBoard} disabled={loading}>Refresh board</button>}
      >
        <div className="metric-grid">
          <div className="metric-card">
            <span>current_research_state</span>
            <strong>{decisionBoard?.current_research_state ?? "missing"}</strong>
          </div>
          <div className="metric-card">
            <span>next_allowed_action</span>
            <strong>{decisionBoard?.next_allowed_action ?? "no_action_until_data_ready"}</strong>
          </div>
          <div className="metric-card">
            <span>candidate_training_allowed</span>
            <strong>{String(decisionBoard?.candidate_training_allowed ?? false)}</strong>
          </div>
          <div className="metric-card">
            <span>candidate_v12_allowed</span>
            <strong>{String(decisionBoard?.candidate_v12_allowed ?? false)}</strong>
          </div>
          <div className="metric-card">
            <span>manual_approval_recommended</span>
            <strong>{String(decisionBoard?.manual_approval_recommended ?? false)}</strong>
          </div>
          <div className="metric-card">
            <span>active_publish_allowed</span>
            <strong>{String(decisionBoard?.active_publish_allowed ?? false)}</strong>
          </div>
        </div>
        <DataTable
          data={decisionBoardTopBlockers.map((reason) => ({ reason }))}
          emptyLabel="No top blocking reasons loaded"
          columns={[{ key: "reason", title: "top blocking reasons" }]}
        />
        <DataTable
          data={Object.entries(decisionBoardEvidencePaths).slice(0, 8).map(([name, path]) => ({ name, path }))}
          emptyLabel="No evidence paths loaded"
          columns={[
            { key: "name", title: "evidence paths" },
            { key: "path", title: "Path" }
          ]}
        />
        <DataTable
          data={decisionBoardStaleMissing.map((item) => ({ item }))}
          emptyLabel="No stale/missing reports"
          columns={[{ key: "item", title: "stale/missing reports" }]}
        />
      </SectionCard>
      <SectionCard
        title="Readiness DAG"
        subtitle="Safe dependency view for managed data and research gates; skipped nodes are never treated as pass."
        actions={
          <div className="button-row">
            <button className="secondary-button" type="button" onClick={handleRefreshReadinessDag} disabled={loading}>Refresh DAG</button>
            <button className="secondary-button" type="button" onClick={handleRunSafeReadinessChecks} disabled={loading}>Run safe checks</button>
          </div>
        }
      >
        <div className="metric-grid">
          <div className="metric-card">
            <span>current DAG status</span>
            <strong>{readinessDag?.status ?? "missing"}</strong>
          </div>
          <div className="metric-card">
            <span>critical path</span>
            <strong>{readinessCriticalPath.join(" -> ") || "missing"}</strong>
          </div>
          <div className="metric-card">
            <span>blocked nodes</span>
            <strong>{String(readinessBlockedNodes.length)}</strong>
          </div>
          <div className="metric-card">
            <span>skipped nodes</span>
            <strong>{String(readinessSkippedNodes.length)}</strong>
          </div>
          <div className="metric-card">
            <span>next allowed action</span>
            <strong>{readinessDag?.next_allowed_action ?? "review_readiness_dag"}</strong>
          </div>
          <div className="metric-card">
            <span>training/active/prediction</span>
            <strong>
              {String(readinessDag?.training_invoked ?? false)} /
              {String(readinessDag?.active_updated ?? false)} /
              {String(readinessDag?.customer_prediction_generated ?? false)}
            </strong>
          </div>
        </div>
        <DataTable
          data={readinessTopBlockers.slice(0, 10).map((blocker) => ({ blocker }))}
          emptyLabel="No readiness blockers loaded"
          columns={[{ key: "blocker", title: "top blockers" }]}
        />
        <DataTable
          data={readinessSafeChecks.map((check) => ({ check }))}
          emptyLabel="No runnable safe checks"
          columns={[{ key: "check", title: "runnable safe checks" }]}
        />
        <DataTable
          data={readinessSkippedNodes.slice(0, 10).map((node) => ({ node }))}
          emptyLabel="No skipped nodes"
          columns={[{ key: "node", title: "skipped nodes" }]}
        />
        <DataTable
          data={readinessForbiddenActions.map((action) => ({ action }))}
          emptyLabel="No forbidden actions loaded"
          columns={[{ key: "action", title: "forbidden actions" }]}
        />
      </SectionCard>
      <SectionCard
        title="Evidence Freshness"
        subtitle="Staleness and timestamp consistency audit for existing evidence reports; stale reports are not treated as pass."
        actions={<button className="secondary-button" type="button" onClick={handleRefreshEvidenceFreshness} disabled={loading}>Refresh freshness</button>}
      >
        <div className="metric-grid">
          <div className="metric-card">
            <span>freshness status</span>
            <strong>{evidenceFreshness?.status ?? "missing"}</strong>
          </div>
          <div className="metric-card">
            <span>stale reports</span>
            <strong>{String(freshnessStaleReports.length)}</strong>
          </div>
          <div className="metric-card">
            <span>missing timestamps</span>
            <strong>{String(freshnessMissingTimestamps.length)}</strong>
          </div>
          <div className="metric-card">
            <span>timestamp inversions</span>
            <strong>{String(freshnessTimestampInversions.length)}</strong>
          </div>
          <div className="metric-card">
            <span>generated at</span>
            <strong>{formatDateTime(evidenceFreshness?.generated_at)}</strong>
          </div>
          <div className="metric-card">
            <span>training/active/prediction</span>
            <strong>
              {String(evidenceFreshness?.training_invoked ?? false)} /
              {String(evidenceFreshness?.active_updated ?? false)} /
              {String(evidenceFreshness?.customer_prediction_generated ?? false)}
            </strong>
          </div>
        </div>
        <DataTable
          data={freshnessProblemReports.slice(0, 10)}
          emptyLabel="No stale reports or missing timestamps"
          columns={[
            { key: "name", title: "report" },
            { key: "state", title: "freshness issue" }
          ]}
        />
        <DataTable
          data={freshnessTimestampInversions.slice(0, 8)}
          emptyLabel="No timestamp inversions"
          columns={[
            { key: "upstream", title: "upstream" },
            { key: "downstream", title: "downstream" },
            { key: "age_gap_hours", title: "age gap hours" }
          ]}
        />
        <DataTable
          data={freshnessBlockingReasons.slice(0, 8).map((reason) => ({ reason }))}
          emptyLabel="No freshness blockers"
          columns={[{ key: "reason", title: "freshness blockers" }]}
        />
      </SectionCard>
      <SectionCard
        title="Evidence Bundle"
        subtitle="Research-only reproducibility index from existing reports and hashes; no training, OOF, feature-store build, active, or prediction."
        actions={<button className="secondary-button" type="button" onClick={handleRefreshEvidenceBundle} disabled={loading}>Refresh evidence bundle</button>}
      >
        <div className="metric-grid">
          <div className="metric-card">
            <span>bundle status</span>
            <strong>{evidenceBundle?.status ?? "missing"}</strong>
          </div>
          <div className="metric-card">
            <span>evidence file count</span>
            <strong>{String(evidenceBundle?.evidence_file_count ?? 0)}</strong>
          </div>
          <div className="metric-card">
            <span>missing/incomplete reports</span>
            <strong>{String(evidenceMissingReports.length + evidenceIncompleteReports.length)}</strong>
          </div>
          <div className="metric-card">
            <span>next allowed action</span>
            <strong>{evidenceBundle?.next_allowed_action ?? "review_missing_evidence"}</strong>
          </div>
          <div className="metric-card">
            <span>current research state</span>
            <strong>{evidenceBundle?.current_research_state ?? "missing"}</strong>
          </div>
          <div className="metric-card">
            <span>training/active/prediction</span>
            <strong>
              {String(evidenceBundle?.training_invoked ?? false)} /
              {String(evidenceBundle?.active_updated ?? false)} /
              {String(evidenceBundle?.customer_prediction_generated ?? false)}
            </strong>
          </div>
        </div>
        <DataTable
          data={evidenceProblemReports.slice(0, 10)}
          emptyLabel="No missing or incomplete evidence reports"
          columns={[
            { key: "name", title: "report" },
            { key: "state", title: "state" }
          ]}
        />
        <DataTable
          data={Object.entries(evidenceChecklist).map(([name, value]) => ({ name, value: Array.isArray(value) ? value.join(", ") : String(value ?? "missing") })).slice(0, 8)}
          emptyLabel="No reproducibility checklist loaded"
          columns={[
            { key: "name", title: "checklist" },
            { key: "value", title: "status" }
          ]}
        />
        <DataTable
          data={evidenceSafetyFlags.map((flag) => ({ flag }))}
          emptyLabel="No safety flags loaded"
          columns={[{ key: "flag", title: "safety flags" }]}
        />
      </SectionCard>
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
          <span>本页面不发布 active、不生成客户预测、不会接实盘、不降低 promotion gate。Logistic/Ridge 仅作为内部对照指标。</span>
        </div>
        {loading ? <LoadingState label="正在运行模型研究实验..." /> : null}
        {message ? <div className="inline-success">{message}</div> : null}
        {error ? <ErrorState message={error} onRetry={loadExperiments} /> : null}
      </SectionCard>

      <SectionCard
        title="Why no active model"
        subtitle="Active remains disabled until promotion gate, institutional validation, cost stress, and stability checks all pass."
      >
        {!activeAbsence ? (
          <EmptyState label="Active absence diagnostics not loaded" description="The research page will show blockers after the diagnostics API responds." />
        ) : (
          <div className="compact-stack" data-testid="research-active-absence-diagnostics">
            <div className="metric-grid">
              <div className="metric-card">
                <span>active status</span>
                <strong>{activeAbsence.active_status ?? "none"}</strong>
              </div>
              <div className="metric-card">
                <span>latest candidate</span>
                <strong>{activeAbsence.candidate_version ?? "unknown"}</strong>
              </div>
              <div className="metric-card">
                <span>candidate_v6 plan</span>
                <strong>{activeAbsence.candidate_v6_plan?.status ?? "research_plan_only"}</strong>
              </div>
            </div>
            <DataTable
              data={(activeAbsence?.root_causes ?? []).slice(0, 8).map((cause) => ({ ...cause }))}
              emptyLabel="No active blockers loaded."
              columns={[
                { key: "severity", title: "Severity" },
                { key: "category", title: "Blocker" },
                { key: "evidence", title: "Evidence" },
                { key: "fix_plan", title: "Fix plan" }
              ]}
            />
            <div className="notice-card">
              <strong>No fabricated forecasts</strong>
              <span>This page explains why active is absent and does not create prediction cards or lower the promotion gate.</span>
            </div>
          </div>
        )}
      </SectionCard>

      <SectionCard
        title="Feature stability evidence"
        subtitle="candidate_v5 fold-wise importance stability used by institutional validation and active absence diagnostics."
      >
        <div className="metric-grid">
          <div className="metric-card">
            <span>Feature stability score</span>
            <strong>{formatNullable(featureStabilityEvidence.stability_score ?? featureStabilityMetric.value)}</strong>
          </div>
          <div className="metric-card">
            <span>threshold</span>
            <strong>{formatNullable(featureStabilityEvidence.threshold ?? featureStabilityMetric.threshold)}</strong>
          </div>
          <div className="metric-card">
            <span>status</span>
            <strong>{featureStabilityEvidence.passed ?? featureStabilityMetric.passed ? "passed" : "blocked"}</strong>
          </div>
          <div className="metric-card">
            <span>fold evidence</span>
            <strong>{formatNullable(featureStabilityEvidence.informative_fold_count ?? featureStabilityEvidence.fold_count)}</strong>
          </div>
        </div>
        <div className="data-table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>unstable features</th>
                <th>recommendation</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>{unstableFeatures.length ? unstableFeatures.join(", ") : "none"}</td>
                <td>{stabilityRecommendations.length ? stabilityRecommendations.join(" ") : "No additional stability action."}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </SectionCard>

      <SectionCard
        title="自学习调度器"
        subtitle="自动刷新数据、构建 Feature Store、训练 candidate、做机构级验证并归档报告；不会自动发布 active。"
        actions={
          <div className="button-row">
            <button className="secondary-button" type="button" onClick={handleRunLearningScheduler} disabled={loading}>手动运行</button>
            <button className="secondary-button" type="button" onClick={handlePauseLearningScheduler}>暂停</button>
            <button className="secondary-button" type="button" onClick={handleResumeLearningScheduler}>恢复</button>
          </div>
        }
      >
        <div className="metric-grid">
          <div className="metric-card">
            <span>状态</span>
            <strong>{learningScheduler?.paused ? "paused" : learningScheduler?.status ?? "not_loaded"}</strong>
          </div>
          <div className="metric-card">
            <span>最近运行</span>
            <strong>{formatDateTime(learningScheduler?.last_run_at)}</strong>
          </div>
          <div className="metric-card">
            <span>下次计划</span>
            <strong>{learningScheduler?.next_task ?? "daily_market_refresh"}</strong>
          </div>
          <div className="metric-card">
            <span>人工审批</span>
            <strong>{learningScheduler?.manual_approval_required ? "等待人工审批" : "未触发"}</strong>
          </div>
        </div>
        <div className="notice-card">
          <strong>No auto active</strong>
          <span>{learningScheduler?.manual_approval_message_zh ?? "调度器只运行 promotion dry-run；不会自动发布 active，不会生成客户预测。"}</span>
        </div>
        <DataTable
          data={(learningScheduler?.tasks ?? []).map((task) => ({ ...task }))}
          emptyLabel="暂无自学习调度任务记录"
          columns={[
            { key: "task", title: "任务" },
            { key: "status", title: "状态" },
            { key: "ran_at", title: "运行时间", render: (row) => formatDateTime(row.ran_at as string | undefined) },
            { key: "message_zh", title: "说明" }
          ]}
        />
        {learningScheduler?.last_failure_reasons?.length ? (
          <div className="empty-state">失败原因：{learningScheduler.last_failure_reasons.join("；")}</div>
        ) : null}
        {learningScheduler?.artifact_dir ? (
          <div className="inline-success">Artifact：{learningScheduler.artifact_dir}</div>
        ) : null}
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
      <details className="archive-panel archived-candidates">
        <summary>Archived Candidates</summary>
        <div className="notice-card">
          <strong>research-only archive</strong>
          <span>candidate_v3, candidate_v4, candidate_v6, candidate_v7, candidate_v8, and candidate_v9 are collapsed by default to keep the current decision state clear.</span>
        </div>
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
          <span>candidate_v4 does not write active_model.json, does not create customer-facing forecast output, and does not lower the promotion gate.</span>
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
      <SectionCard
        title="candidate_v6 gated research"
        subtitle="v5 vs v6 comparison, Tushare enhanced fields, OOF trace, OOF high-confidence, research backtest, institutional validation, and promotion dry-run."
        actions={<button className="secondary-button" type="button" onClick={handleRunCandidateV6} disabled={loading}>Run candidate_v6</button>}
      >
        <div className="notice-card">
          <strong>Strict gate</strong>
          <span>candidate_v6 runs only after readiness, leakage, sample/mock, baseline, and feature stability evidence pass. Passing dry-run means waiting for human approval; this page does not publish active.</span>
        </div>
        <div className="metric-grid">
          <div className="metric-card">
            <span>candidate_v6</span>
            <strong>{candidateV6?.status ?? "not_run"}</strong>
          </div>
          <div className="metric-card">
            <span>institutional validation</span>
            <strong>{candidateV6?.institutional_validation?.status ?? "not_run"}</strong>
          </div>
          <div className="metric-card">
            <span>promotion dry-run</span>
            <strong>{candidateV6?.promotion_dry_run?.status ?? "not_run"}</strong>
          </div>
        </div>
        <DataTable
          data={[
            {
              version: "v5 vs v6",
              fields: candidateV6?.new_fields?.join(", ") || "waiting for candidate_v6 run",
              backtest: candidateV6?.research_backtest?.status ?? "not_run",
              approval: candidateV6?.manual_approval_recommended ? "waiting for human approval" : "not approved"
            }
          ]}
          columns={[
            { key: "version", title: "Version" },
            { key: "fields", title: "New Tushare fields" },
            { key: "backtest", title: "Research backtest" },
            { key: "approval", title: "Approval" }
          ]}
        />
      </SectionCard>
      <SectionCard
        title="人工审批 active 发布"
        subtitle="Only formal approval can request active artifact release after dry-run gates pass."
        actions={<button className="secondary-button" type="button" disabled>Active artifact write unavailable</button>}
      >
        <div className="notice-card">
          <strong>风险声明</strong>
          <span>审批短语必须为“我确认仅作为研究预测，不构成投资建议”。发布 active 仅启用研究预测观察，不提供交易指令，不接实盘，不承诺收益。</span>
        </div>
        <div className="control-grid">
          <label>
            审批人
            <input value={approver} onChange={(event) => setApprover(event.target.value)} placeholder="approver" />
          </label>
          <label>
            审批短语
            <input value={approvalPhrase} onChange={(event) => setApprovalPhrase(event.target.value)} placeholder="我确认仅作为研究预测，不构成投资建议" />
          </label>
          <label>
            备注
            <input value={approvalNotes} onChange={(event) => setApprovalNotes(event.target.value)} placeholder="DSR/PBO/成本压力/特征稳定性复核说明" />
          </label>
        </div>
        <DataTable
          data={(activeApproval?.approval_checklist ?? []).map((item) => ({ ...item }))}
          emptyLabel="尚未执行人工审批；请先确认 promotion dry-run 已通过。"
          columns={[
            { key: "name", title: "gate pass checklist" },
            { key: "passed", title: "通过" },
            { key: "failure_reason_zh", title: "失败原因" }
          ]}
        />
        {activeApproval?.audit_path ? <div className="inline-success">审批记录：{activeApproval.audit_path}</div> : null}
        {activeApproval?.blocking_reasons?.length ? (
          <div className="empty-state">不可发布原因：{activeApproval.blocking_reasons.join("；")}</div>
        ) : null}
      </SectionCard>
      <SectionCard
        title="candidate_v7 stability research"
        subtitle="v6 vs v7 comparison for PBO, DSR, Reality Check, cost pressure, feature stability, and promotion dry-run."
        actions={<button className="secondary-button" type="button" onClick={handleRunCandidateV7} disabled={loading}>Run candidate_v7</button>}
      >
        <div className="notice-card">
          <strong>Research only</strong>
          <span>candidate_v7 uses Feature Store v7 cost and positioning fields, then runs dry-run promotion only. Passing means waiting for human approval.</span>
        </div>
        <div className="metric-grid">
          <div className="metric-card">
            <span>candidate_v7</span>
            <strong>{candidateV7?.status ?? "not_run"}</strong>
          </div>
          <div className="metric-card">
            <span>PBO</span>
            <strong>{formatNullable(candidateV7Metrics.PBO)}</strong>
          </div>
          <div className="metric-card">
            <span>DSR</span>
            <strong>{formatNullable(candidateV7Metrics.DSR)}</strong>
          </div>
          <div className="metric-card">
            <span>promotion dry-run</span>
            <strong>{candidateV7?.promotion_dry_run?.status ?? "not_run"}</strong>
          </div>
        </div>
        <DataTable
          data={[
            {
              version: "v6",
              pbo: formatNullable(candidateV7CompareV6.PBO),
              dsr: formatNullable(candidateV7CompareV6.DSR),
              reality: formatNullable(candidateV7CompareV6["Reality Check p-value"]),
              cost2x: formatNullable(candidateV7CompareV6["2x cost expectancy"]),
              cost3x: formatNullable(candidateV7CompareV6["3x cost expectancy"])
            },
            {
              version: "v7",
              pbo: formatNullable(candidateV7CompareV7.PBO),
              dsr: formatNullable(candidateV7CompareV7.DSR),
              reality: formatNullable(candidateV7CompareV7["Reality Check p-value"]),
              cost2x: formatNullable(candidateV7CompareV7["2x cost expectancy"]),
              cost3x: formatNullable(candidateV7CompareV7["3x cost expectancy"])
            }
          ]}
          columns={[
            { key: "version", title: "Version" },
            { key: "pbo", title: "PBO" },
            { key: "dsr", title: "DSR" },
            { key: "reality", title: "Reality Check" },
            { key: "cost2x", title: "2x cost" },
            { key: "cost3x", title: "3x cost" }
          ]}
        />
        <DataTable
          data={[
            {
              group: "cost pressure",
              fields: candidateV7CostFeatures.join(", ") || "waiting for candidate_v7 run",
              backtest: candidateV7?.research_backtest?.status ?? "not_run",
              approval: candidateV7?.manual_approval_recommended ? "waiting for human approval" : "not approved"
            },
            {
              group: "positioning",
              fields: candidateV7PositioningFeatures.join(", ") || "waiting for candidate_v7 run",
              backtest: candidateV7?.research_backtest?.status ?? "not_run",
              approval: candidateV7?.manual_approval_recommended ? "waiting for human approval" : "not approved"
            }
          ]}
          columns={[
            { key: "group", title: "Feature group" },
            { key: "fields", title: "v7 fields" },
            { key: "backtest", title: "Research backtest" },
            { key: "approval", title: "Approval" }
          ]}
        />
      </SectionCard>
      <SectionCard
        title="candidate_v8 stability"
        subtitle="v7 vs v8 stability comparison, disabled horizons, no-trade reasons, dry-run only."
        actions={
          <div className="button-row">
            <button className="secondary-button" type="button" onClick={handleLoadCandidateV8Diagnostics} disabled={loading}>v8 diagnostics</button>
            <button className="secondary-button" type="button" onClick={handleRunCandidateV8} disabled={loading}>Run candidate_v8</button>
          </div>
        }
      >
        <div className="notice-card">
          <strong>Still blocked unless dry-run passes</strong>
          <span>candidate_v8 reduces frequency and drawdown exposure; even a pass only waits for human approval.</span>
        </div>
        <div className="metric-grid">
          <div className="metric-card">
            <span>candidate_v8</span>
            <strong>{candidateV8?.status ?? "not_run"}</strong>
          </div>
          <div className="metric-card">
            <span>PBO change</span>
            <strong>{formatNullable(candidateV8Improvement.PBO)}</strong>
          </div>
          <div className="metric-card">
            <span>DSR change</span>
            <strong>{formatNullable(candidateV8Improvement.DSR)}</strong>
          </div>
          <div className="metric-card">
            <span>promotion dry-run</span>
            <strong>{candidateV8?.promotion_dry_run?.status ?? "not_run"}</strong>
          </div>
        </div>
        <DataTable
          data={[
            {
              version: "v7",
              pbo: formatNullable(candidateV8CompareV7.PBO),
              dsr: formatNullable(candidateV8CompareV7.DSR),
              reality: formatNullable(candidateV8CompareV7["Reality Check p-value"]),
              drawdown: formatNullable(candidateV8CompareV7.max_drawdown),
              turnover: formatNullable(candidateV8CompareV7.turnover),
              trades: formatNullable(candidateV8CompareV7.trade_count)
            },
            {
              version: "v8",
              pbo: formatNullable(candidateV8CompareV8.PBO),
              dsr: formatNullable(candidateV8CompareV8.DSR),
              reality: formatNullable(candidateV8CompareV8["Reality Check p-value"]),
              drawdown: formatNullable(candidateV8CompareV8.max_drawdown),
              turnover: formatNullable(candidateV8CompareV8.turnover),
              trades: formatNullable(candidateV8CompareV8.trade_count)
            }
          ]}
          columns={[
            { key: "version", title: "v7 vs v8" },
            { key: "pbo", title: "PBO" },
            { key: "dsr", title: "DSR" },
            { key: "reality", title: "Reality Check" },
            { key: "drawdown", title: "Drawdown" },
            { key: "turnover", title: "Turnover" },
            { key: "trades", title: "Trades" }
          ]}
        />
        <DataTable
          data={[
            {
              item: "disabled horizons",
              value: (candidateV8?.disabled_horizons ?? []).join(", ") || "none",
              next: candidateV8?.manual_approval_recommended ? "waiting for human approval" : "still blocked"
            },
            {
              item: "no-trade reasons",
              value: (candidateV8?.no_trade_reasons ?? []).join(", ") || "waiting for candidate_v8 run",
              next: `min confidence ${formatNullable(candidateV8Thresholds.min_confidence)}`
            },
            {
              item: "model complexity",
              value: candidateV8Models.join(", ") || "stable subset pending",
              next: "not higher than v7"
            }
          ]}
          columns={[
            { key: "item", title: "Policy" },
            { key: "value", title: "Value" },
            { key: "next", title: "State" }
          ]}
        />
        <div className="subsection-title">v8 failure attribution</div>
        <DataTable
          data={[
            {
              source: "PBO source",
              value: formatNullable(candidateV8PboSummary.pbo),
              detail: `gap ${formatNullable(candidateV8PboSummary.gap_to_threshold)}`
            },
            {
              source: "Regime concentration",
              value: String(candidateV8Regime.dominant_regime ?? "not_loaded"),
              detail: formatNullable(candidateV8Regime.dominant_contribution)
            },
            {
              source: "Reality Check gap",
              value: formatNullable(candidateV8Reality.p_value),
              detail: `gap ${formatNullable(candidateV8Reality.gap_to_threshold)}`
            },
            {
              source: "v9 actions",
              value: String(candidateV8Diagnostics?.recommended_v9_actions?.length ?? 0),
              detail: candidateV8Diagnostics?.validation_passed ? "ready" : "blocked"
            }
          ]}
          columns={[
            { key: "source", title: "Attribution" },
            { key: "value", title: "Value" },
            { key: "detail", title: "Detail" }
          ]}
        />
      </SectionCard>
      <SectionCard
        title="CPCV multi-path validation"
        subtitle="Research-only multi-path PBO and Reality Check from existing OOF traces; no active artifact write or customer-facing forecast output."
        actions={<button className="secondary-button" type="button" onClick={handleLoadCpcvValidation} disabled={loading}>Load CPCV report</button>}
      >
        <div className="metric-grid">
          <div className="metric-card">
            <span>split count</span>
            <strong>{formatNullable(cpcvValidation?.split_count)}</strong>
          </div>
          <div className="metric-card">
            <span>PBO</span>
            <strong>{formatNullable(cpcvPbo.pbo)}</strong>
          </div>
          <div className="metric-card">
            <span>Reality Check</span>
            <strong>{formatNullable(cpcvReality.aggregate_p_value)}</strong>
          </div>
          <div className="metric-card">
            <span>research only</span>
            <strong>{cpcvValidation?.research_only === false ? "unexpected" : "true"}</strong>
          </div>
        </div>
        <DataTable
          data={(cpcvValidation?.pbo_by_path ?? []).slice(0, 8).map((row) => ({ ...row }))}
          emptyLabel="No CPCV PBO paths loaded."
          columns={[
            { key: "path_id", title: "Path" },
            { key: "selected_strategy", title: "Selected strategy" },
            { key: "selected_test_rank", title: "Rank" },
            { key: "selected_test_metric", title: "Test metric", format: "number" },
            { key: "overfit", title: "Overfit" }
          ]}
        />
        <DataTable
          data={(cpcvValidation?.reality_check_by_path ?? []).slice(0, 8).map((row) => ({ ...row }))}
          emptyLabel="No CPCV Reality Check paths loaded."
          columns={[
            { key: "path_id", title: "Path" },
            { key: "selected_strategy", title: "Selected strategy" },
            { key: "p_value", title: "p-value", format: "number" },
            { key: "observed_mean", title: "Observed mean", format: "number" },
            { key: "passed", title: "Passed" }
          ]}
        />
      </SectionCard>
      <SectionCard
        title="candidate_v9 regime-neutral"
        subtitle="v8 vs v9 comparison with regime concentration, fold/year quotas, CPCV-like PBO, and dry-run only."
        actions={<button className="secondary-button" type="button" onClick={handleRunCandidateV9} disabled={loading}>Run candidate_v9</button>}
      >
        <div className="notice-card">
          <strong>Research only</strong>
          <span>v9 only changes selection, no-trade, and threshold policy. If it passes, the state is 可进入人工审批; this page does not publish active.</span>
        </div>
        <div className="metric-grid">
          <div className="metric-card">
            <span>candidate_v9</span>
            <strong>{candidateV9?.status ?? "not_run"}</strong>
          </div>
          <div className="metric-card">
            <span>institutional validation</span>
            <strong>{candidateV9?.institutional_validation?.status ?? "not_run"}</strong>
          </div>
          <div className="metric-card">
            <span>promotion dry-run</span>
            <strong>{candidateV9?.promotion_dry_run?.status ?? "not_run"}</strong>
          </div>
          <div className="metric-card">
            <span>approval</span>
            <strong>{candidateV9?.manual_approval_recommended ? "可进入人工审批" : "blocked or not_run"}</strong>
          </div>
        </div>
        <DataTable
          data={[
            {
              version: "v8",
              pbo: formatNullable(candidateV9CompareV8.PBO),
              dsr: formatNullable(candidateV9CompareV8.DSR),
              reality: formatNullable(candidateV9CompareV8["Reality Check p-value"]),
              regime: formatNullable(candidateV9CompareV8["regime concentration"]),
              fold: formatNullable(candidateV9CompareV8["fold concentration"]),
              trades: formatNullable(candidateV9CompareV8.trade_count)
            },
            {
              version: "v9",
              pbo: formatNullable(candidateV9CompareV9.PBO),
              dsr: formatNullable(candidateV9CompareV9.DSR),
              reality: formatNullable(candidateV9CompareV9["Reality Check p-value"]),
              regime: formatNullable(candidateV9CompareV9["regime concentration"]),
              fold: formatNullable(candidateV9CompareV9["fold concentration"]),
              trades: formatNullable(candidateV9CompareV9.trade_count)
            }
          ]}
          columns={[
            { key: "version", title: "v8 vs v9" },
            { key: "pbo", title: "PBO" },
            { key: "dsr", title: "DSR" },
            { key: "reality", title: "Reality Check" },
            { key: "regime", title: "regime concentration" },
            { key: "fold", title: "fold concentration" },
            { key: "trades", title: "Trades" }
          ]}
        />
        <DataTable
          data={[
            {
              item: "trade quota",
              value: `regime ${formatNullable(candidateV9RegimeQuota.max_single_regime_trade_share)}`,
              state: `fold ${formatNullable(candidateV9FoldQuota.max_single_fold_trade_share)} / year ${formatNullable(candidateV9YearQuota.max_single_year_trade_share)}`
            },
            {
              item: "regime concentration",
              value: String(candidateV9RegimeQuota.capped_regimes ?? "waiting for v9"),
              state: "no-trade if over-concentrated"
            },
            {
              item: "model complexity",
              value: String(asRecord(candidateV9Policy.complexity).not_higher_than_v8 ?? "pending"),
              state: "not higher than v8"
            }
          ]}
          columns={[
            { key: "item", title: "Policy" },
            { key: "value", title: "Value" },
            { key: "state", title: "State" }
          ]}
        />
      </SectionCard>
      </details>
      <SectionCard
        title="candidate_v10 CPCV"
        subtitle="Runs from regime-balanced dataset v10 with CPCV-like validation and dry-run promotion only."
        actions={<button className="secondary-button" type="button" onClick={handleRunCandidateV10} disabled={loading}>Run candidate_v10</button>}
      >
        <div className="notice-card">
          <strong>Research only</strong>
          <span>candidate_v10 uses regime-balanced dataset v10 and CPCV path checks. Passing means manual_approval_recommended only; this page does not publish active.</span>
        </div>
        <div className="metric-grid">
          <div className="metric-card">
            <span>candidate_v10</span>
            <strong>{candidateV10?.status ?? "not_run"}</strong>
          </div>
          <div className="metric-card">
            <span>CPCV PBO</span>
            <strong>{formatNullable(candidateV10CpcvPbo.pbo)}</strong>
          </div>
          <div className="metric-card">
            <span>Reality Check</span>
            <strong>{formatNullable(candidateV10CpcvReality.aggregate_p_value)}</strong>
          </div>
          <div className="metric-card">
            <span>approval</span>
            <strong>{candidateV10?.manual_approval_recommended ? "可进入人工审批" : "blocked or not_run"}</strong>
          </div>
        </div>
        <DataTable
          data={[
            {
              version: "v9",
              pbo: formatNullable(candidateV10CompareV9.PBO),
              dsr: formatNullable(candidateV10CompareV9.DSR),
              reality: formatNullable(candidateV10CompareV9["Reality Check p-value"]),
              regime: formatNullable(candidateV10CompareV9["regime concentration"]),
              fold: formatNullable(candidateV10CompareV9["fold concentration"]),
              trades: formatNullable(candidateV10CompareV9.trade_count)
            },
            {
              version: "v10",
              pbo: formatNullable(candidateV10CompareV10.PBO),
              dsr: formatNullable(candidateV10CompareV10.DSR),
              reality: formatNullable(candidateV10CompareV10["Reality Check p-value"]),
              regime: formatNullable(candidateV10CompareV10["regime concentration"]),
              fold: formatNullable(candidateV10CompareV10["fold concentration"]),
              trades: formatNullable(candidateV10CompareV10.trade_count)
            }
          ]}
          columns={[
            { key: "version", title: "v10 vs v9" },
            { key: "pbo", title: "PBO" },
            { key: "dsr", title: "DSR" },
            { key: "reality", title: "Reality Check" },
            { key: "regime", title: "regime concentration" },
            { key: "fold", title: "fold concentration" },
            { key: "trades", title: "Trades" }
          ]}
        />
        <DataTable
          data={[
            {
              item: "PBO < 0.2",
              value: String(candidateV10GateChecks.pbo_lt_0_2 ?? "pending"),
              state: formatNullable(candidateV10GateChecks.pbo)
            },
            {
              item: "Reality Check pass",
              value: String(candidateV10GateChecks.reality_check_pass ?? "pending"),
              state: formatNullable(candidateV10CpcvReality.aggregate_p_value)
            },
            {
              item: "regime concentration pass",
              value: String(candidateV10GateChecks.regime_concentration_pass ?? "pending"),
              state: formatNullable(candidateV10GateChecks.regime_concentration)
            },
            {
              item: "cost pressure positive",
              value: String(candidateV10GateChecks.cost_pressure_positive ?? "pending"),
              state: `2x ${formatNullable(candidateV10GateChecks.two_x_cost_expectancy)} / 3x ${formatNullable(candidateV10GateChecks.three_x_cost_expectancy)}`
            }
          ]}
          columns={[
            { key: "item", title: "Gate" },
            { key: "value", title: "Pass" },
            { key: "state", title: "Value" }
          ]}
        />
      </SectionCard>
      <SectionCard
        title="Year Concentration Evidence"
        subtitle="Reads existing OOF trace timestamps only; missing or skipped evidence cannot pass manual approval."
        actions={<button className="secondary-button" type="button" onClick={handleRefreshYearConcentration} disabled={loading}>Refresh evidence</button>}
      >
        <div className="metric-grid">
          <div className="metric-card">
            <span>Candidate v10 year evidence</span>
            <strong>{formatNullable(candidateV10YearConcentration.status, "missing")}</strong>
          </div>
          <div className="metric-card">
            <span>max year pnl share</span>
            <strong>{formatNullable(candidateV10YearConcentration.max_year_pnl_share)}</strong>
          </div>
          <div className="metric-card">
            <span>max year sample share</span>
            <strong>{formatNullable(candidateV10YearConcentration.max_year_sample_share)}</strong>
          </div>
          <div className="metric-card">
            <span>positive/negative/total years</span>
            <strong>
              {formatNullable(candidateV10YearConcentration.positive_year_count, "0")} /
              {formatNullable(candidateV10YearConcentration.negative_year_count, "0")} /
              {formatNullable(candidateV10YearConcentration.total_year_count, "0")}
            </strong>
          </div>
          <div className="metric-card">
            <span>Candidate v12 year evidence</span>
            <strong>{formatNullable(candidateV12YearConcentration.status, "missing")}</strong>
          </div>
          <div className="metric-card">
            <span>skipped reason</span>
            <strong>{formatNullable(candidateV12YearConcentration.skipped_reason, "not_skipped")}</strong>
          </div>
        </div>
        <DataTable
          data={[
            {
              candidate: "v10",
              status: formatNullable(candidateV10YearConcentration.status, "missing"),
              max_pnl_share: formatNullable(candidateV10YearConcentration.max_year_pnl_share),
              max_sample_share: formatNullable(candidateV10YearConcentration.max_year_sample_share),
              years: `${formatNullable(candidateV10YearConcentration.positive_year_count, "0")}/${formatNullable(candidateV10YearConcentration.negative_year_count, "0")}/${formatNullable(candidateV10YearConcentration.total_year_count, "0")}`,
              reasons: asStringList(candidateV10YearConcentration.blocking_reasons).join(", ") || "none"
            },
            {
              candidate: "v12",
              status: formatNullable(candidateV12YearConcentration.status, "missing"),
              max_pnl_share: formatNullable(candidateV12YearConcentration.max_year_pnl_share),
              max_sample_share: formatNullable(candidateV12YearConcentration.max_year_sample_share),
              years: `${formatNullable(candidateV12YearConcentration.positive_year_count, "0")}/${formatNullable(candidateV12YearConcentration.negative_year_count, "0")}/${formatNullable(candidateV12YearConcentration.total_year_count, "0")}`,
              reasons: asStringList(candidateV12YearConcentration.blocking_reasons).join(", ") || formatNullable(candidateV12YearConcentration.skipped_reason, "none")
            }
          ]}
          columns={[
            { key: "candidate", title: "Candidate" },
            { key: "status", title: "Status" },
            { key: "max_pnl_share", title: "Max PnL Share" },
            { key: "max_sample_share", title: "Max Sample Share" },
            { key: "years", title: "positive/negative/total years" },
            { key: "reasons", title: "blocking reasons" }
          ]}
        />
      </SectionCard>
      <SectionCard
        title="Cost Stress Attribution"
        subtitle="Explains institutional 2x/3x cost stress from existing candidate reports and OOF traces only."
        actions={<button className="secondary-button" type="button" onClick={handleRefreshCostStressAttribution} disabled={loading}>Refresh cost attribution</button>}
      >
        <div className="metric-grid">
          <div className="metric-card">
            <span>Candidate v10 attribution status</span>
            <strong>{formatNullable(candidateV10CostAttribution.status, "missing")}</strong>
          </div>
          <div className="metric-card">
            <span>Candidate v12 attribution status</span>
            <strong>{formatNullable(candidateV12CostAttribution.status, "missing")}</strong>
          </div>
          <div className="metric-card">
            <span>turnover diagnostics</span>
            <strong>{formatNullable(candidateV10TurnoverDiagnostics.average_turnover)}</strong>
          </div>
          <div className="metric-card">
            <span>signal flip diagnostics</span>
            <strong>{formatNullable(candidateV10SignalFlipDiagnostics.signal_flip_rate)}</strong>
          </div>
          <div className="metric-card">
            <span>holding period diagnostics</span>
            <strong>{formatNullable(candidateV10HoldingDiagnostics.avg_holding_period)}</strong>
          </div>
          <div className="metric-card">
            <span>skipped reason</span>
            <strong>{formatNullable(candidateV12CostAttribution.skipped_reason, "not_skipped")}</strong>
          </div>
        </div>
        <DataTable
          data={candidateV10CostHorizonRows.slice(0, 8).map((row) => ({ ...row }))}
          emptyLabel="No by horizon cost attribution loaded."
          columns={[
            { key: "horizon", title: "by horizon" },
            { key: "trade_count", title: "Trades" },
            { key: "gross_expectancy", title: "Gross", format: "number" },
            { key: "net_expectancy_2x", title: "Net 2x", format: "number" },
            { key: "net_expectancy_3x", title: "Net 3x", format: "number" },
            { key: "turnover", title: "Turnover", format: "number" },
            { key: "main_failure_driver", title: "Driver" }
          ]}
        />
        <DataTable
          data={candidateV10CostRegimeRows.slice(0, 8).map((row) => ({ ...row }))}
          emptyLabel="No by regime cost attribution loaded."
          columns={[
            { key: "regime_label", title: "by regime" },
            { key: "trade_count", title: "Trades" },
            { key: "net_expectancy_2x", title: "Net 2x", format: "number" },
            { key: "net_expectancy_3x", title: "Net 3x", format: "number" },
            { key: "cost_drag", title: "Cost drag", format: "number" },
            { key: "signal_flip_rate", title: "Flip rate", format: "number" },
            { key: "main_failure_driver", title: "Driver" }
          ]}
        />
        <DataTable
          data={candidateV10CostYearRows.slice(0, 8).map((row) => ({ ...row }))}
          emptyLabel="No by year cost attribution loaded."
          columns={[
            { key: "year", title: "by year" },
            { key: "trade_count", title: "Trades" },
            { key: "net_expectancy_2x", title: "Net 2x", format: "number" },
            { key: "net_expectancy_3x", title: "Net 3x", format: "number" },
            { key: "cost_drag", title: "Cost drag", format: "number" },
            { key: "turnover", title: "Turnover", format: "number" },
            { key: "main_failure_driver", title: "Driver" }
          ]}
        />
        <DataTable
          data={asStringList(candidateV10CostAttribution.failure_drivers).map((driver) => ({ driver }))}
          emptyLabel="No failure drivers"
          columns={[{ key: "driver", title: "failure drivers" }]}
        />
      </SectionCard>
      <SectionCard
        title="Hypothesis Registry"
        subtitle="Predeclared experiment ledger for future research; registration never executes experiments, training, active, or prediction."
        actions={
          <div className="button-row">
            <button className="secondary-button" type="button" onClick={handleCreateHypothesisTemplate} disabled={loading}>Create hypothesis template</button>
            <button className="secondary-button" type="button" onClick={handleRefreshAntiPHackingLedger} disabled={loading}>Refresh ledger</button>
          </div>
        }
      >
        <div className="metric-grid">
          <div className="metric-card">
            <span>registry status</span>
            <strong>{hypothesisRegistry?.status ?? "empty"}</strong>
          </div>
          <div className="metric-card">
            <span>open hypotheses</span>
            <strong>{String(hypothesisRegistry?.open_hypotheses ?? openHypothesisRows.length)}</strong>
          </div>
          <div className="metric-card">
            <span>linked blockers</span>
            <strong>{String(linkedBlockers.length)}</strong>
          </div>
          <div className="metric-card">
            <span>p-hacking risk</span>
            <strong>{ledger?.p_hacking_risk_level ?? hypothesisRegistry?.p_hacking_risk_level ?? "none"}</strong>
          </div>
          <div className="metric-card">
            <span>experiment budget usage</span>
            <strong>{String(experimentBudgetRows.length)}</strong>
          </div>
          <div className="metric-card">
            <span>training/active/prediction</span>
            <strong>
              {String(hypothesisRegistry?.training_invoked ?? ledger?.training_invoked ?? false)} /
              {String(hypothesisRegistry?.active_updated ?? ledger?.active_updated ?? false)} /
              {String(hypothesisRegistry?.customer_prediction_generated ?? ledger?.customer_prediction_generated ?? false)}
            </strong>
          </div>
        </div>
        <DataTable
          data={openHypothesisRows.slice(0, 8)}
          emptyLabel="No open hypotheses registered"
          columns={[
            { key: "hypothesis_id", title: "open hypotheses" },
            { key: "linked_blocker", title: "linked blockers" },
            { key: "expected_direction", title: "expected direction" },
            { key: "status", title: "status" }
          ]}
        />
        <DataTable
          data={experimentBudgetRows.slice(0, 8)}
          emptyLabel="No experiment budget usage"
          columns={[
            { key: "linked_blocker", title: "linked blocker" },
            { key: "registered_hypotheses", title: "registered" },
            { key: "remaining_budget", title: "remaining" }
          ]}
        />
        <DataTable
          data={hypothesisTemplates.slice(0, 5)}
          emptyLabel="No hypothesis templates from remediation sandbox"
          columns={[
            { key: "hypothesis_id", title: "template" },
            { key: "linked_blocker", title: "linked blocker" },
            { key: "risk_of_overfitting", title: "overfit risk" }
          ]}
        />
      </SectionCard>
      <SectionCard
        title="Remediation Preflight"
        subtitle="Checks registered v10 remediation hypotheses against existing cost, year, CPCV, and gate evidence before any future experiment."
        actions={<button className="secondary-button" type="button" onClick={handleRefreshV10RemediationPreflight} disabled={loading}>Refresh preflight</button>}
      >
        <div className="metric-grid">
          <div className="metric-card">
            <span>preflight status</span>
            <strong>{v10RemediationPreflight?.status ?? "not_run"}</strong>
          </div>
          <div className="metric-card">
            <span>recommended experiments</span>
            <strong>{String(preflightRecommendedRows.length)}</strong>
          </div>
          <div className="metric-card">
            <span>overfitting risk</span>
            <strong>{formatNullable(preflightOverfitting.risk_level, "missing")}</strong>
          </div>
          <div className="metric-card">
            <span>metric budget</span>
            <strong>{formatNullable(preflightMetricBudget.p_hacking_risk_level, "missing")}</strong>
          </div>
          <div className="metric-card">
            <span>blocked experiments</span>
            <strong>{String(preflightBlockedRows.length)}</strong>
          </div>
          <div className="metric-card">
            <span>training/active/prediction</span>
            <strong>
              {String(v10RemediationPreflight?.training_invoked ?? false)} /
              {String(v10RemediationPreflight?.active_updated ?? false)} /
              {String(v10RemediationPreflight?.customer_prediction_generated ?? false)}
            </strong>
          </div>
        </div>
        <DataTable
          data={preflightRecommendedRows.slice(0, 8)}
          emptyLabel="No recommended experiments loaded"
          columns={[
            { key: "hypothesis_id", title: "recommended experiments" },
            { key: "linked_blocker", title: "linked blocker" },
            { key: "matched_remediation_id", title: "remediation" },
            { key: "affected_horizon", title: "horizon" },
            { key: "affected_regime", title: "regime" },
            { key: "rank_score", title: "rank", format: "number" }
          ]}
        />
        <DataTable
          data={preflightBlockedRows.slice(0, 8)}
          emptyLabel="No blocked experiments"
          columns={[
            { key: "hypothesis_id", title: "blocked experiments" },
            { key: "title", title: "title" },
            { key: "blocking_reasons", title: "reason" }
          ]}
        />
        <DataTable
          data={[...preflightWarnings, ...preflightBlockingReasons].slice(0, 10).map((reason) => ({ reason }))}
          emptyLabel="No preflight warnings or blockers loaded"
          columns={[{ key: "reason", title: "warnings / blockers" }]}
        />
      </SectionCard>
      <SectionCard
        title="Shadow Mode Readiness"
        subtitle="Readiness spec for future shadow observations; refresh never writes active or customer prediction outputs."
        actions={<button className="secondary-button" type="button" onClick={handleRefreshShadowModeReadiness} disabled={loading}>Refresh shadow readiness</button>}
      >
        <div className="metric-grid">
          <div className="metric-card">
            <span>readiness status</span>
            <strong>{shadowModeReadiness?.status ?? "not_run"}</strong>
          </div>
          <div className="metric-card">
            <span>shadow_mode_allowed</span>
            <strong>{String(shadowModeReadiness?.shadow_mode_allowed ?? false)}</strong>
          </div>
          <div className="metric-card">
            <span>blocked gates</span>
            <strong>{String(shadowBlockedGates.length)}</strong>
          </div>
          <div className="metric-card">
            <span>approval required</span>
            <strong>{String(shadowModeReadiness?.approval_required ?? true)}</strong>
          </div>
          <div className="metric-card">
            <span>output isolation contract</span>
            <strong>{String(shadowOutputContract.paths_are_separate ?? false)}</strong>
          </div>
          <div className="metric-card">
            <span>training/active/prediction</span>
            <strong>
              false /
              {String(shadowModeReadiness?.active_updated ?? false)} /
              {String(shadowModeReadiness?.customer_prediction_generated ?? false)}
            </strong>
          </div>
        </div>
        <DataTable
          data={shadowEntryGates}
          emptyLabel="No shadow entry gates loaded"
          columns={[
            { key: "gate", title: "entry gate" },
            { key: "status", title: "status" },
            { key: "passed", title: "passed" },
            { key: "reason", title: "reason" }
          ]}
        />
        <DataTable
          data={shadowBlockedGates.map((gate) => ({ gate }))}
          emptyLabel="No blocked gates"
          columns={[{ key: "gate", title: "blocked gates" }]}
        />
        <DataTable
          data={[
            { item: "shadow_output_root", value: formatNullable(shadowOutputContract.shadow_output_root, "missing") },
            { item: "customer_predictions_root", value: formatNullable(shadowOutputContract.customer_predictions_root, "missing") },
            { item: "paths_are_separate", value: String(shadowOutputContract.paths_are_separate ?? false) },
            { item: "customer_predictions_absent", value: String(shadowPredictionIsolation.customer_predictions_absent ?? false) },
            { item: "active_model_absent", value: String(shadowPredictionIsolation.active_model_absent ?? false) }
          ]}
          emptyLabel="No output isolation contract loaded"
          columns={[
            { key: "item", title: "output isolation contract" },
            { key: "value", title: "value" }
          ]}
        />
        <DataTable
          data={shadowForbiddenOutputs.map((output) => ({ output }))}
          emptyLabel="No forbidden outputs listed"
          columns={[{ key: "output", title: "forbidden outputs" }]}
        />
      </SectionCard>
      <SectionCard
        title="Registry Safety / Rollback"
        subtitle="Model registry safety contract and rollback readiness; refresh never registers a model or writes active."
        actions={<button className="secondary-button" type="button" onClick={handleRefreshModelRegistrySafety} disabled={loading}>Refresh registry safety</button>}
      >
        <div className="metric-grid">
          <div className="metric-card">
            <span>registry safety status</span>
            <strong>{modelRegistrySafety?.status ?? "missing"}</strong>
          </div>
          <div className="metric-card">
            <span>active_write_allowed</span>
            <strong>{String(modelRegistrySafety?.active_write_allowed ?? false)}</strong>
          </div>
          <div className="metric-card">
            <span>rollback_target_available</span>
            <strong>{String(modelRegistrySafety?.rollback_target_available ?? false)}</strong>
          </div>
          <div className="metric-card">
            <span>unapproved_active_detected</span>
            <strong>{String(modelRegistrySafety?.unapproved_active_detected ?? false)}</strong>
          </div>
          <div className="metric-card">
            <span>promotion dry-run</span>
            <strong>{modelRegistrySafety?.promotion_dry_run_status ?? "missing"}</strong>
          </div>
          <div className="metric-card">
            <span>active/prediction</span>
            <strong>
              {String(modelRegistrySafety?.active_updated ?? false)} /
              {String(modelRegistrySafety?.customer_prediction_generated ?? false)}
            </strong>
          </div>
        </div>
        <DataTable
          data={registrySafetyBlockingReasons.map((reason) => ({ reason }))}
          emptyLabel="No registry safety blockers"
          columns={[{ key: "reason", title: "blocking reasons" }]}
        />
        <DataTable
          data={registrySafetyRollbackCandidates.slice(0, 8)}
          emptyLabel="No rollback target candidates"
          columns={[
            { key: "source", title: "rollback source" },
            { key: "path", title: "path" },
            { key: "exists", title: "exists" }
          ]}
        />
        <DataTable
          data={registrySafetyRequiredPreconditions.map((condition) => ({ condition }))}
          emptyLabel="No required registry preconditions loaded"
          columns={[{ key: "condition", title: "required preconditions" }]}
        />
        <DataTable
          data={asStringList(registrySafetyPreconditions.blocking_reasons).map((reason) => ({ reason }))}
          emptyLabel="No active write precondition blockers"
          columns={[{ key: "reason", title: "active write preconditions" }]}
        />
      </SectionCard>
      <SectionCard
        title="Run Ledger"
        subtitle="Append-only manifest ledger for safe research reports; refresh records current report files only."
        actions={<button className="secondary-button" type="button" onClick={handleRefreshRunLedger} disabled={loading}>Refresh run ledger</button>}
      >
        <div className="metric-grid">
          <div className="metric-card">
            <span>run ledger status</span>
            <strong>{runLedger?.status ?? "missing"}</strong>
          </div>
          <div className="metric-card">
            <span>latest runs</span>
            <strong>{String(runLedger?.latest_run_count ?? runLedgerRows.length)}</strong>
          </div>
          <div className="metric-card">
            <span>violation count</span>
            <strong>{String(runLedger?.violation_count ?? 0)}</strong>
          </div>
          <div className="metric-card">
            <span>safe checks vs heavy tasks</span>
            <strong>{String(runLedger?.safe_check_count ?? 0)} / {String(runLedger?.heavy_task_count ?? 0)}</strong>
          </div>
          <div className="metric-card">
            <span>forbidden side effects</span>
            <strong>{runLedgerForbidden.join(", ") || "active_model, customer_prediction"}</strong>
          </div>
          <div className="metric-card">
            <span>training/active/prediction</span>
            <strong>
              {String(runLedger?.training_invoked ?? false)} /
              {String(runLedger?.active_updated ?? false)} /
              {String(runLedger?.customer_prediction_generated ?? false)}
            </strong>
          </div>
        </div>
        <DataTable
          data={runLedgerRows.slice(-10).reverse()}
          emptyLabel="No run ledger entries"
          columns={[
            { key: "run_id", title: "latest runs" },
            { key: "service_name", title: "service" },
            { key: "run_type", title: "type" },
            { key: "status", title: "status" },
            { key: "finished_at", title: "finished" }
          ]}
        />
        <DataTable
          data={runLedgerForbidden.map((effect) => ({ effect }))}
          emptyLabel="No forbidden side effects configured"
          columns={[{ key: "effect", title: "forbidden side effects" }]}
        />
      </SectionCard>
      <SectionCard
        title="Cost Failure Remediation Sandbox"
        subtitle="Research-only hypotheses from existing candidate_v10 OOF and cost attribution; no training, no approval, no active."
        actions={<button className="secondary-button" type="button" onClick={handleRefreshV10CostRemediation} disabled={loading}>Refresh remediation sandbox</button>}
      >
        <div className="notice-card">
          <strong>research_only</strong>
          <span>manual approval unchanged; this sandbox does not alter candidate_v10 gates or manual_approval_recommended.</span>
        </div>
        <div className="metric-grid">
          <div className="metric-card">
            <span>remediation status</span>
            <strong>{v10CostRemediation?.status ?? "not_run"}</strong>
          </div>
          <div className="metric-card">
            <span>best counterfactual</span>
            <strong>{formatNullable(v10RemediationBest.hypothesis_id, "missing")}</strong>
          </div>
          <div className="metric-card">
            <span>net 3x delta</span>
            <strong>{formatNullable(v10RemediationBest.net_3x_delta)}</strong>
          </div>
          <div className="metric-card">
            <span>recommended next experiment</span>
            <strong>{formatNullable(v10CostRemediation?.recommended_next_experiment, "refresh_oof_evidence")}</strong>
          </div>
          <div className="metric-card">
            <span>manual approval unchanged</span>
            <strong>{v10CostRemediation?.manual_approval_recommended ? "unexpected" : "false"}</strong>
          </div>
          <div className="metric-card">
            <span>training / active / prediction</span>
            <strong>
              {String(v10CostRemediation?.training_invoked ?? false)} /
              {String(v10CostRemediation?.active_updated ?? false)} /
              {String(v10CostRemediation?.customer_prediction_generated ?? false)}
            </strong>
          </div>
        </div>
        <DataTable
          data={v10RemediationHypotheses.slice(0, 7).map((row) => ({ ...row }))}
          emptyLabel="No remediation hypotheses loaded."
          columns={[
            { key: "id", title: "Hypothesis" },
            { key: "affected_horizon", title: "Horizon" },
            { key: "affected_regime", title: "Regime" },
            { key: "affected_year", title: "Year" },
            { key: "risk_of_overfitting", title: "Overfit risk" },
            { key: "rank_score", title: "Rank score", format: "number" }
          ]}
        />
        <DataTable
          data={v10RemediationCounterfactuals.slice(0, 7).map((row) => ({ ...row }))}
          emptyLabel="No no-train counterfactuals loaded."
          columns={[
            { key: "hypothesis_id", title: "Counterfactual" },
            { key: "research_only", title: "research_only" },
            { key: "trade_count", title: "Trades" },
            { key: "trade_retention", title: "Retention", format: "number" },
            { key: "net_expectancy_2x", title: "Net 2x", format: "number" },
            { key: "net_expectancy_3x", title: "Net 3x", format: "number" },
            { key: "net_3x_delta", title: "Delta 3x", format: "number" }
          ]}
        />
        <DataTable
          data={asStringList(v10CostRemediation?.blocking_reasons).map((reason) => ({ reason }))}
          emptyLabel="No remediation sandbox blockers."
          columns={[{ key: "reason", title: "blocking reasons" }]}
        />
      </SectionCard>
      <SectionCard
        title="candidate_v12 research gate"
        subtitle="Blocked-first gate from Training Dataset v12 and Feature Store v12. It never publishes active or creates customer predictions."
        actions={<button className="secondary-button" type="button" onClick={handleRunCandidateV12} disabled={loading}>Run candidate_v12</button>}
      >
        <div className="notice-card">
          <strong>active/prediction status</strong>
          <span>
            active_updated={String(candidateV12?.active_updated ?? false)} / customer_prediction_generated={String(candidateV12?.customer_prediction_generated ?? false)}
          </span>
        </div>
        <div className="metric-grid">
          <div className="metric-card">
            <span>candidate status</span>
            <strong>{candidateV12?.status ?? "not_run"}</strong>
          </div>
          <div className="metric-card">
            <span>Training Dataset v12 status</span>
            <strong>{candidateV12?.training_dataset_status ?? "missing"}</strong>
          </div>
          <div className="metric-card">
            <span>Feature Store v12 status</span>
            <strong>{candidateV12?.feature_store_status ?? "missing"}</strong>
          </div>
          <div className="metric-card">
            <span>training_invoked</span>
            <strong>{String(candidateV12?.training_invoked ?? false)}</strong>
          </div>
          <div className="metric-card">
            <span>PBO</span>
            <strong>{formatNullable(candidateV12?.pbo)}</strong>
          </div>
          <div className="metric-card">
            <span>Reality Check</span>
            <strong>{formatNullable(candidateV12Reality.aggregate_p_value)}</strong>
          </div>
          <div className="metric-card">
            <span>institutional 2x/3x cost</span>
            <strong>{formatNullable(candidateV12TwoXCost.expectancy)} / {formatNullable(candidateV12ThreeXCost.expectancy)}</strong>
          </div>
          <div className="metric-card">
            <span>year concentration</span>
            <strong>{formatNullable(candidateV12YearConcentration.max_year_pnl_share)}</strong>
          </div>
          <div className="metric-card">
            <span>manual_approval_recommended</span>
            <strong>{candidateV12?.manual_approval_recommended ? "yes" : "no"}</strong>
          </div>
          <div className="metric-card">
            <span>promotion dry-run</span>
            <strong>{formatNullable(candidateV12Promotion.status, "skipped")}</strong>
          </div>
        </div>
        <DataTable
          data={Object.entries(candidateV12ReadinessChecks).map(([check, payload]) => ({
            check,
            passed: String(asRecord(payload).passed ?? "pending"),
            reason: formatNullable(asRecord(payload).reason, "")
          }))}
          emptyLabel="No candidate_v12 readiness checks"
          columns={[
            { key: "check", title: "readiness checks" },
            { key: "passed", title: "Passed" },
            { key: "reason", title: "Reason" }
          ]}
        />
        <DataTable
          data={[
            {
              version: "v10",
              pbo: formatNullable(candidateV12CompareV10.PBO),
              reality: formatNullable(candidateV12CompareV10["Reality Check p-value"]),
              regime: formatNullable(candidateV12CompareV10["regime concentration"]),
              fold: formatNullable(candidateV12CompareV10["fold concentration"]),
              year: formatNullable(candidateV12CompareV10["year concentration"])
            },
            {
              version: "v12",
              pbo: formatNullable(candidateV12CompareV12.PBO),
              reality: formatNullable(candidateV12CompareV12["Reality Check p-value"]),
              regime: formatNullable(candidateV12CompareV12["regime concentration"]),
              fold: formatNullable(candidateV12CompareV12["fold concentration"]),
              year: formatNullable(candidateV12CompareV12["year concentration"])
            }
          ]}
          columns={[
            { key: "version", title: "v12 vs v10" },
            { key: "pbo", title: "PBO" },
            { key: "reality", title: "Reality Check" },
            { key: "regime", title: "Regime" },
            { key: "fold", title: "Fold" },
            { key: "year", title: "Year" }
          ]}
        />
        <DataTable
          data={[
            { gate: "PBO < 0.2", value: String(candidateV12GateChecks.pbo_lt_0_2 ?? "pending") },
            { gate: "Reality Check pass", value: String(candidateV12GateChecks.reality_check_pass ?? "pending") },
            { gate: "institutional cost stress", value: String(candidateV12GateChecks.institutional_cost_stress_pass ?? "pending") },
            { gate: "year concentration pass", value: String(candidateV12GateChecks.year_concentration_pass ?? "pending") },
            { gate: "promotion dry-run pass", value: String(candidateV12GateChecks.promotion_dry_run_pass ?? "pending") }
          ]}
          columns={[
            { key: "gate", title: "Gate" },
            { key: "value", title: "Value" }
          ]}
        />
        <DataTable
          data={asStringList(candidateV12?.blocking_reasons).map((reason) => ({ reason }))}
          emptyLabel="No candidate_v12 blocking reasons"
          columns={[{ key: "reason", title: "blocking reasons" }]}
        />
      </SectionCard>
      {selectedId ? <OOFTracePanel experimentId={selectedId} /> : null}
    </div>
  );
}
