import { useEffect, useId, useMemo, useState } from "react";
import {
  buildNoopReleasePlan,
  buildShadowOutputDryRun,
  getEvidenceBundle,
  getExternalAuditExport,
  getEvidenceFreshness,
  getGovernanceAccessControl,
  getGovernanceMaturityMatrix,
  getGovernanceObservability,
  getIncidentDrill,
  getHypothesisRegistry,
  getManualApproval,
  getModelCard,
  getModelRegistrySafety,
  getPostReleaseMonitoringSpec,
  getProductionCutoverChecklist,
  getPromotionDryRunEvidence,
  getReadinessDag,
  getResearchDecisionBoard,
  getRollbackRehearsal,
  getRunLedger,
  getShadowModeReadiness,
  getShadowOutputContract,
  getShadowReplay,
  refreshAntiPHackingLedger,
  refreshEvidenceBundle,
  refreshExternalAuditExport,
  refreshEvidenceFreshness,
  refreshGovernanceAccessControl,
  refreshGovernanceMaturityMatrix,
  refreshGovernanceObservability,
  refreshLockdownState,
  refreshManualApproval,
  refreshModelCard,
  refreshModelRegistrySafety,
  refreshPostReleaseMonitoringSpec,
  refreshProductionCutoverChecklist,
  refreshPromotionDryRunEvidence,
  refreshReadinessDag,
  refreshResearchDecisionBoard,
  refreshRollbackRehearsal,
  refreshRunLedger,
  refreshShadowModeReadiness,
  refreshShadowOutputContract,
  refreshShadowReplay,
  runIncidentDrill,
  runSafeReadinessChecks,
  simulateArtifactQuarantine
} from "../api/terminal";
import type {
  AntiPHackingLedgerPayload,
  EvidenceBundlePayload,
  ExternalAuditExportPayload,
  PostReleaseMonitoringSpecPayload,
  ProductionCutoverChecklistPayload,
  PromotionDryRunEvidencePayload,
  EvidenceFreshnessPayload,
  GovernanceAccessControlPayload,
  GovernanceMaturityMatrixPayload,
  GovernanceObservabilityPayload,
  IncidentDrillPayload,
  HypothesisRegistryPayload,
  ManualApprovalPayload,
  ModelCardPayload,
  ModelRegistrySafetyPayload,
  ReadinessDagPayload,
  ResearchDecisionBoardPayload,
  RollbackRehearsalPayload,
  ResearchRunLedgerPayload,
  ShadowModeReadinessPayload,
  ShadowOutputContractPayload,
  ShadowReplayPayload
} from "../api/types";
import { DataTable } from "../components/common/DataTable";
import { EmptyState } from "../components/common/EmptyState";
import { ErrorState } from "../components/common/ErrorState";
import { LoadingState } from "../components/common/LoadingState";
import { StatusPill } from "../components/common/StatusPill";
import { WorkspaceGuardBanner } from "../components/common/WorkspaceGuardBanner";
import { SectionCard } from "../components/layout/SectionCard";
import { formatDateTime, formatNullable } from "../utils/format";
import { formatNextAction, formatStatusLabel, getDisabledReason, getStatusTone } from "../utils/statusTaxonomy";

type RefreshFn<T> = () => Promise<T>;

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function asStringList(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => String(item)).filter(Boolean) : [];
}

function StatusValue({ value }: { value?: string | null }) {
  const label = formatStatusLabel(formatNullable(value, "missing"));
  return <StatusPill label={label} tone={getStatusTone(value)} />;
}

function RefreshButton({
  disabled,
  label,
  onClick
}: {
  disabled: boolean;
  label: string;
  onClick: () => void;
}) {
  const disabledReason = disabled ? getDisabledReason("safe_report_refresh") : "";
  const reactId = useId().replace(/:/g, "");
  const reasonId = `${reactId}-disabled-reason-${label.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
  return (
    <>
      <button
        aria-describedby={disabled ? reasonId : undefined}
        aria-label={label}
        className="secondary-button"
        disabled={disabled}
        title={disabledReason || label}
        type="button"
        onClick={onClick}
      >
        {label}
      </button>
      {disabled ? <span className="sr-only" id={reasonId}>{disabledReason}</span> : null}
    </>
  );
}

function WidgetCard({
  title,
  subtitle,
  actions,
  children
}: {
  title: string;
  subtitle: string;
  actions?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <SectionCard title={title} subtitle={subtitle} actions={actions}>
      {children}
    </SectionCard>
  );
}

function ListTable({ items, title, emptyLabel }: { items: string[]; title: string; emptyLabel: string }) {
  return (
    <DataTable
      data={items.map((item) => ({ item }))}
      emptyLabel={emptyLabel}
      columns={[{ key: "item", title }]}
    />
  );
}

export function GovernanceConsolePage() {
  const [decisionBoard, setDecisionBoard] = useState<ResearchDecisionBoardPayload | null>(null);
  const [readinessDag, setReadinessDag] = useState<ReadinessDagPayload | null>(null);
  const [evidenceFreshness, setEvidenceFreshness] = useState<EvidenceFreshnessPayload | null>(null);
  const [evidenceBundle, setEvidenceBundle] = useState<EvidenceBundlePayload | null>(null);
  const [externalAuditExport, setExternalAuditExport] = useState<ExternalAuditExportPayload | null>(null);
  const [productionCutover, setProductionCutover] = useState<ProductionCutoverChecklistPayload | null>(null);
  const [postReleaseMonitoring, setPostReleaseMonitoring] = useState<PostReleaseMonitoringSpecPayload | null>(null);
  const [rollbackRehearsal, setRollbackRehearsal] = useState<RollbackRehearsalPayload | null>(null);
  const [promotionDryRunEvidence, setPromotionDryRunEvidence] = useState<PromotionDryRunEvidencePayload | null>(null);
  const [modelCard, setModelCard] = useState<ModelCardPayload | null>(null);
  const [maturityMatrix, setMaturityMatrix] = useState<GovernanceMaturityMatrixPayload | null>(null);
  const [runLedger, setRunLedger] = useState<ResearchRunLedgerPayload | null>(null);
  const [hypothesisRegistry, setHypothesisRegistry] = useState<HypothesisRegistryPayload | null>(null);
  const [antiPHackingLedger, setAntiPHackingLedger] = useState<AntiPHackingLedgerPayload | null>(null);
  const [shadowModeReadiness, setShadowModeReadiness] = useState<ShadowModeReadinessPayload | null>(null);
  const [modelRegistrySafety, setModelRegistrySafety] = useState<ModelRegistrySafetyPayload | null>(null);
  const [accessControl, setAccessControl] = useState<GovernanceAccessControlPayload | null>(null);
  const [governanceObservability, setGovernanceObservability] = useState<GovernanceObservabilityPayload | null>(null);
  const [incidentDrill, setIncidentDrill] = useState<IncidentDrillPayload | null>(null);
  const [manualApproval, setManualApproval] = useState<ManualApprovalPayload | null>(null);
  const [shadowOutputContract, setShadowOutputContract] = useState<ShadowOutputContractPayload | null>(null);
  const [shadowReplay, setShadowReplay] = useState<ShadowReplayPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const decisionBlockingReasons = asStringList(decisionBoard?.blocking_reasons);
  const readinessForbiddenActions = asStringList(readinessDag?.forbidden_actions);
  const readinessBlockedNodes = asStringList(readinessDag?.blocked_nodes);
  const readinessSkippedNodes = asStringList(readinessDag?.skipped_nodes);
  const evidenceMissingReports = asStringList(evidenceBundle?.missing_reports);
  const evidenceIncompleteReports = asStringList(evidenceBundle?.incomplete_reports);
  const auditMissingReports = asStringList(externalAuditExport?.missing_reports);
  const auditIncompleteReports = asStringList(externalAuditExport?.incomplete_reports);
  const auditRedactedFields = asStringList(externalAuditExport?.redacted_fields);
  const auditOmittedSensitiveFiles = asStringList(externalAuditExport?.omitted_sensitive_files);
  const cutoverRequiredManualSteps = asStringList(productionCutover?.required_manual_steps);
  const cutoverForbiddenActions = asStringList(productionCutover?.forbidden_actions);
  const cutoverRollbackSummary = asRecord(productionCutover?.rollback_plan_summary);
  const cutoverPreconditionRows = Array.isArray(productionCutover?.precondition_checks) ? productionCutover.precondition_checks : [];
  const monitoringReadinessGaps = asStringList(postReleaseMonitoring?.readiness_gaps);
  const monitoringAlertThresholds = Object.entries(asRecord(postReleaseMonitoring?.alert_thresholds)).map(([name, value]) => ({
    name,
    threshold: String(asRecord(value).threshold ?? ""),
    action: String(asRecord(value).action ?? "")
  }));
  const rollbackArtifacts = Array.isArray(rollbackRehearsal?.artifacts_detected) ? rollbackRehearsal.artifacts_detected : [];
  const rollbackActions = Array.isArray(rollbackRehearsal?.simulated_quarantine_actions) ? rollbackRehearsal.simulated_quarantine_actions : [];
  const rollbackPlan = asStringList(rollbackRehearsal?.rollback_plan);
  const rollbackManualActions = asStringList(rollbackRehearsal?.manual_actions_required);
  const rollbackSafetyChecks = Object.entries(asRecord(rollbackRehearsal?.safety_checks)).map(([check, value]) => ({
    check,
    value: String(value)
  }));
  const promotionPreconditionRows = Array.isArray(promotionDryRunEvidence?.precondition_checks) ? promotionDryRunEvidence.precondition_checks : [];
  const promotionRegistryPlan = asRecord(promotionDryRunEvidence?.simulated_registry_write_plan);
  const promotionBoundaryChecks = asRecord(promotionDryRunEvidence?.artifact_boundary_checks);
  const promotionBoundaryRows = Object.entries(promotionBoundaryChecks).map(([check, value]) => ({
    check,
    value: String(value)
  }));
  const promotionBlockingReasons = asStringList(promotionDryRunEvidence?.blocking_reasons);
  const modelCardLimitations = asStringList(modelCard?.known_limitations);
  const modelCardGateFailures = asStringList(modelCard?.gate_failures);
  const modelCardIntendedUse = asStringList(modelCard?.intended_use);
  const modelCardProhibitedUse = asStringList(modelCard?.prohibited_use);
  const modelCardNoActive = asRecord(modelCard?.no_active_confirmation);
  const modelCardNoPrediction = asRecord(modelCard?.no_prediction_confirmation);
  const maturityShadowReadiness = asRecord(maturityMatrix?.shadow_readiness);
  const maturityDomainRows = Object.entries(asRecord(maturityMatrix?.domain_scores))
    .map(([domain, value]) => ({
      domain,
      score: Number(asRecord(value).score ?? 0),
      status: String(asRecord(value).status ?? "missing")
    }))
    .sort((left, right) => left.score - right.score)
    .slice(0, 8)
    .map((item) => ({ ...item, score: item.score.toFixed(2) }));
  const maturityCriticalGaps = asStringList(maturityMatrix?.critical_gaps);
  const maturityCompletedControls = asStringList(maturityMatrix?.completed_controls);
  const maturityMissingControls = asStringList(maturityMatrix?.missing_controls);
  const maturityPromptRows: Record<string, unknown>[] = Array.isArray(maturityMatrix?.recommended_prompt_sequence)
    ? maturityMatrix.recommended_prompt_sequence.map((item) => ({
      priority: item.priority,
      action: item.action
    }))
    : [];
  const freshnessStaleReports = asStringList(evidenceFreshness?.stale_reports);
  const freshnessMissingTimestamps = asStringList(evidenceFreshness?.missing_timestamps);
  const shadowBlockedGates = asStringList(shadowModeReadiness?.blocked_gates);
  const registryBlockingReasons = asStringList(modelRegistrySafety?.blocking_reasons);
  const runLedgerForbiddenEffects = asStringList(runLedger?.forbidden_side_effects);
  const accessForbiddenActions = asStringList(accessControl?.forbidden_actions);
  const accessBlockedHeavyActions = asStringList(accessControl?.blocked_heavy_actions);
  const accessBlockedSecretActions = asStringList(accessControl?.blocked_secret_actions);
  const accessAllowedSafeActions = asStringList(accessControl?.allowed_safe_actions);
  const accessUiApiViolations = asStringList(accessControl?.ui_api_violations);
  const observabilityTelemetry = asRecord(governanceObservability?.telemetry_summary);
  const observabilitySlo = asRecord(governanceObservability?.slo_results);
  const observabilityBudget = asRecord(governanceObservability?.error_budget);
  const incidentRealLockdown = asRecord(incidentDrill?.real_lockdown_state);
  const incidentScenarioRows = Array.isArray(incidentDrill?.scenario_results) ? incidentDrill.scenario_results : [];
  const incidentPlaybook = asStringList(incidentDrill?.remediation_playbook);
  const manualApprovalChecks = Array.isArray(manualApproval?.precondition_checks) ? manualApproval.precondition_checks : [];
  const manualApprovalBlockingReasons = asStringList(manualApproval?.blocking_reasons);
  const shadowOutputBlockingReasons = asStringList(shadowOutputContract?.blocking_reasons);
  const shadowReplayRiskTags = asStringList(shadowReplay?.top_risk_tags ?? shadowReplay?.risk_tags);
  const shadowReplaySkippedReasons = asStringList(shadowReplay?.skipped_reasons);
  const shadowReplayStabilityMetrics = asRecord(shadowReplay?.stability_metrics);
  const incidentForbiddenActions = [
    "training",
    "active artifact write",
    "customer-facing forecast output",
    "secret write",
    "v12 build"
  ];
  const permissionMatrixRows = Object.entries(asRecord(accessControl?.permission_matrix)).map(([category, value]) => {
    const row = asRecord(value);
    return {
      category,
      default_allowed: String(Boolean(row.default_allowed)),
      requires: Array.isArray(row.requires) ? row.requires.join(", ") : ""
    };
  });

  const nextAllowedAction = (
    decisionBoard?.next_allowed_action
    ?? readinessDag?.next_allowed_action
    ?? evidenceBundle?.next_allowed_action
    ?? "review_governance_console"
  );

  const actionBoundaryRows = useMemo(() => [
    {
      action_class: "safe check",
      action: "Run safe readiness checks",
      allowed: "yes",
      handler: "runSafeReadinessChecks"
    },
    {
      action_class: "report refresh",
      action: "Refresh existing governance reports",
      allowed: "yes",
      handler: "refresh* safe report helpers"
    },
    {
      action_class: "heavy task",
      action: "Feature-store, training-dataset, OOF, candidate, and promotion workflows",
      allowed: "no",
      handler: "not exposed in this console"
    },
    {
      action_class: "forbidden action",
      action: "Registry write and customer-facing output generation",
      allowed: "no",
      handler: "not exposed in this console"
    }
  ], []);

  async function loadAll() {
    setLoading(true);
    setError(null);
    setMessage(null);
    const [
      boardResult,
      dagResult,
      freshnessResult,
      bundleResult,
      externalAuditResult,
      productionCutoverResult,
      postReleaseMonitoringResult,
      rollbackRehearsalResult,
      promotionDryRunResult,
      modelCardResult,
      maturityMatrixResult,
      ledgerResult,
      hypothesisResult,
      shadowResult,
      registryResult,
      accessControlResult,
      observabilityResult,
      incidentResult,
      manualApprovalResult,
      shadowOutputResult,
      shadowReplayResult
    ] = await Promise.allSettled([
      getResearchDecisionBoard(),
      getReadinessDag(),
      getEvidenceFreshness(),
      getEvidenceBundle(),
      getExternalAuditExport(),
      getProductionCutoverChecklist(),
      getPostReleaseMonitoringSpec(),
      getRollbackRehearsal(),
      getPromotionDryRunEvidence(),
      getModelCard(),
      getGovernanceMaturityMatrix(),
      getRunLedger(),
      getHypothesisRegistry(),
      getShadowModeReadiness(),
      getModelRegistrySafety(),
      getGovernanceAccessControl(),
      getGovernanceObservability(),
      getIncidentDrill(),
      getManualApproval(),
      getShadowOutputContract(),
      getShadowReplay()
    ]);

    const errors: string[] = [];
    if (boardResult.status === "fulfilled") setDecisionBoard(boardResult.value);
    else errors.push("decision board");
    if (dagResult.status === "fulfilled") setReadinessDag(dagResult.value);
    else errors.push("readiness DAG");
    if (freshnessResult.status === "fulfilled") setEvidenceFreshness(freshnessResult.value);
    else errors.push("evidence freshness");
    if (bundleResult.status === "fulfilled") setEvidenceBundle(bundleResult.value);
    else errors.push("evidence bundle");
    if (externalAuditResult.status === "fulfilled") setExternalAuditExport(externalAuditResult.value);
    else errors.push("external audit export");
    if (productionCutoverResult.status === "fulfilled") setProductionCutover(productionCutoverResult.value);
    else errors.push("production cutover checklist");
    if (postReleaseMonitoringResult.status === "fulfilled") setPostReleaseMonitoring(postReleaseMonitoringResult.value);
    else errors.push("post-release monitoring spec");
    if (rollbackRehearsalResult.status === "fulfilled") setRollbackRehearsal(rollbackRehearsalResult.value);
    else errors.push("rollback rehearsal");
    if (promotionDryRunResult.status === "fulfilled") setPromotionDryRunEvidence(promotionDryRunResult.value);
    else errors.push("promotion dry-run evidence");
    if (modelCardResult.status === "fulfilled") setModelCard(modelCardResult.value);
    else errors.push("model card");
    if (maturityMatrixResult.status === "fulfilled") setMaturityMatrix(maturityMatrixResult.value);
    else errors.push("maturity matrix");
    if (ledgerResult.status === "fulfilled") setRunLedger(ledgerResult.value);
    else errors.push("run ledger");
    if (hypothesisResult.status === "fulfilled") {
      setHypothesisRegistry(hypothesisResult.value);
      setAntiPHackingLedger(hypothesisResult.value.anti_p_hacking_ledger ?? null);
    } else {
      errors.push("hypothesis registry");
    }
    if (shadowResult.status === "fulfilled") setShadowModeReadiness(shadowResult.value);
    else errors.push("shadow mode readiness");
    if (registryResult.status === "fulfilled") setModelRegistrySafety(registryResult.value);
    else errors.push("model registry safety");
    if (accessControlResult.status === "fulfilled") setAccessControl(accessControlResult.value);
    else errors.push("access control");
    if (observabilityResult.status === "fulfilled") setGovernanceObservability(observabilityResult.value);
    else errors.push("observability");
    if (incidentResult.status === "fulfilled") setIncidentDrill(incidentResult.value);
    else errors.push("incident drill");
    if (manualApprovalResult.status === "fulfilled") setManualApproval(manualApprovalResult.value);
    else errors.push("manual approval");
    if (shadowOutputResult.status === "fulfilled") setShadowOutputContract(shadowOutputResult.value);
    else errors.push("shadow output contract");
    if (shadowReplayResult.status === "fulfilled") setShadowReplay(shadowReplayResult.value);
    else errors.push("shadow replay evaluator");

    setError(errors.length ? `Some governance reports failed to load: ${errors.join(", ")}` : null);
    setLoading(false);
  }

  async function runRefresh<T>(label: string, refresh: RefreshFn<T>, assign: (payload: T) => void) {
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      const payload = await refresh();
      assign(payload);
      setMessage(`${label} refreshed as a safe governance report.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : `${label} refresh failed.`);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadAll();
  }, []);

  return (
    <div className="page-stack">
      <WorkspaceGuardBanner workspace="Governance Console" source={{ ...(decisionBoard ?? {}), ...(accessControl ?? {}) }} />
      <SectionCard
        title="Governance Console"
        subtitle="Unified research governance view for safe checks, report refreshes, blockers, and forbidden actions."
        actions={
          <div className="button-row">
            <RefreshButton disabled={loading} label="Refresh all governance reports" onClick={() => void loadAll()} />
            <RefreshButton
              disabled={loading}
              label="Run safe checks"
              onClick={() => void runRefresh("Readiness safe checks", runSafeReadinessChecks, setReadinessDag)}
            />
          </div>
        }
      >
        {loading ? <LoadingState label="Loading governance reports..." /> : null}
        {error ? <ErrorState message={error} onRetry={loadAll} /> : null}
        {message ? <div className="inline-success">{message}</div> : null}
        <div className="metric-grid">
          <div className="metric-card">
            <span>governance console status</span>
            <strong>{error ? "degraded" : "ready"}</strong>
            <small>{formatDateTime(decisionBoard?.generated_at ?? readinessDag?.generated_at ?? evidenceBundle?.generated_at)}</small>
          </div>
          <div className="metric-card">
            <span>next_allowed_action</span>
            <strong>{formatNextAction(nextAllowedAction)}</strong>
            <small>One safe next step; never a heavy task from this page.</small>
          </div>
          <div className="metric-card">
            <span>blocked reasons</span>
            <strong>{String(decisionBlockingReasons.length + readinessBlockedNodes.length + registryBlockingReasons.length)}</strong>
            <small>Missing, blocked, and stale evidence are not treated as pass.</small>
          </div>
          <div className="metric-card">
            <span>forbidden actions</span>
            <strong>{String(readinessForbiddenActions.length + runLedgerForbiddenEffects.length + 2)}</strong>
            <small>Heavy workflows are visible as boundaries, not controls.</small>
          </div>
        </div>
        <DataTable
          data={actionBoundaryRows}
          emptyLabel="No action boundary rows"
          columns={[
            { key: "action_class", title: "action class" },
            { key: "action", title: "action" },
            { key: "allowed", title: "allowed" },
            { key: "handler", title: "handler" }
          ]}
        />
      </SectionCard>

      <WidgetCard
        title="Access Control"
        subtitle="Governance permission matrix for safe reads, safe refreshes, heavy builds, research training, registry writes, customer outputs, and secret writes."
        actions={<RefreshButton disabled={loading} label="Refresh access control" onClick={() => void runRefresh("Access Control", refreshGovernanceAccessControl, setAccessControl)} />}
      >
        <div className="metric-grid">
          <div className="metric-card">
            <span>access control status</span>
            <strong><StatusValue value={accessControl?.status} /></strong>
          </div>
          <div className="metric-card">
            <span>permission matrix summary</span>
            <strong>{String(permissionMatrixRows.length)}</strong>
            <small>safe_read / safe_refresh allowed; heavy and write classes guarded.</small>
          </div>
          <div className="metric-card">
            <span>active_write_allowed</span>
            <strong>{String(accessControl?.active_write_allowed ?? false)}</strong>
          </div>
          <div className="metric-card">
            <span>customer_prediction_write_allowed</span>
            <strong>{String(accessControl?.customer_prediction_write_allowed ?? false)}</strong>
          </div>
          <div className="metric-card">
            <span>blocked heavy actions</span>
            <strong>{String(accessBlockedHeavyActions.length)}</strong>
          </div>
          <div className="metric-card">
            <span>blocked secret actions</span>
            <strong>{String(accessBlockedSecretActions.length)}</strong>
          </div>
          <div className="metric-card">
            <span>UI/API action inventory</span>
            <strong>{String((accessControl?.api_action_inventory?.length ?? 0) + (accessControl?.ui_action_inventory?.length ?? 0))}</strong>
          </div>
          <div className="metric-card">
            <span>UI/API violations</span>
            <strong>{String(accessControl?.ui_api_violations_count ?? accessUiApiViolations.length)}</strong>
          </div>
        </div>
        <DataTable
          data={permissionMatrixRows}
          emptyLabel="No permission matrix loaded"
          columns={[
            { key: "category", title: "permission matrix summary" },
            { key: "default_allowed", title: "default allowed" },
            { key: "requires", title: "requires" }
          ]}
        />
        <DataTable
          data={accessForbiddenActions.map((action) => ({ action }))}
          emptyLabel="No forbidden actions loaded"
          columns={[{ key: "action", title: "forbidden actions" }]}
        />
        <ListTable items={accessBlockedHeavyActions} title="blocked heavy actions" emptyLabel="No blocked heavy actions loaded" />
        <ListTable items={accessBlockedSecretActions} title="blocked secret actions" emptyLabel="No blocked secret actions loaded" />
      </WidgetCard>

      <WidgetCard
        title="Observability / SLO"
        subtitle="Safe-check telemetry, freshness, secret scan, and error-budget state."
        actions={<RefreshButton disabled={loading} label="Refresh observability" onClick={() => void runRefresh("Observability", refreshGovernanceObservability, setGovernanceObservability)} />}
      >
        <div className="metric-grid">
          <div className="metric-card">
            <span>observability status</span>
            <strong><StatusValue value={governanceObservability?.status} /></strong>
          </div>
          <div className="metric-card">
            <span>SLO status</span>
            <strong><StatusValue value={String(observabilitySlo.status ?? governanceObservability?.status ?? "missing")} /></strong>
          </div>
          <div className="metric-card">
            <span>safe check success rate</span>
            <strong>{String(observabilityTelemetry.safe_check_success_rate ?? "missing")}</strong>
          </div>
          <div className="metric-card">
            <span>p95 latency</span>
            <strong>{String(observabilityTelemetry.p95_latency_ms ?? "missing")}</strong>
          </div>
          <div className="metric-card">
            <span>error budget remaining</span>
            <strong>{String(observabilityBudget.remaining_ratio ?? "missing")}</strong>
          </div>
          <div className="metric-card">
            <span>stale reports</span>
            <strong>{String(observabilityTelemetry.stale_report_count ?? 0)}</strong>
          </div>
          <div className="metric-card">
            <span>secret scan status</span>
            <strong><StatusValue value={String(observabilityTelemetry.secret_scan_status ?? "missing")} /></strong>
          </div>
          <div className="metric-card">
            <span>forbidden violations</span>
            <strong>{String(observabilityTelemetry.forbidden_action_violation_count ?? 0)}</strong>
          </div>
        </div>
        <ListTable items={asStringList(governanceObservability?.blocking_reasons)} title="blocking reasons" emptyLabel="No observability blockers loaded" />
      </WidgetCard>

      <WidgetCard
        title="Incident Drill / Lockdown"
        subtitle="Simulation-only incident drill and real lockdown state from existing governance evidence."
        actions={
          <div className="button-row">
            <RefreshButton disabled={loading} label="Run incident drill" onClick={() => void runRefresh("Incident Drill", () => runIncidentDrill({ simulation_only: true }), setIncidentDrill)} />
            <RefreshButton disabled={loading} label="Refresh lockdown state" onClick={() => void runRefresh("Lockdown State", refreshLockdownState, setIncidentDrill)} />
          </div>
        }
      >
        <div className="metric-grid">
          <div className="metric-card">
            <span>incident drill status</span>
            <strong><StatusValue value={incidentDrill?.status} /></strong>
          </div>
          <div className="metric-card">
            <span>lockdown status</span>
            <strong>{String(incidentRealLockdown.lockdown_triggered ?? false)}</strong>
          </div>
          <div className="metric-card">
            <span>scenarios</span>
            <strong>{String(incidentDrill?.scenarios_passed ?? 0)} / {String(incidentDrill?.scenarios_run ?? 0)}</strong>
          </div>
          <div className="metric-card">
            <span>manual unlock required</span>
            <strong>{String(incidentRealLockdown.manual_unlock_required ?? false)}</strong>
          </div>
          <div className="metric-card">
            <span>simulated only</span>
            <strong>{String(incidentDrill?.simulated_artifacts_only ?? true)}</strong>
          </div>
          <div className="metric-card">
            <span>forbidden actions</span>
            <strong>{String(incidentForbiddenActions.length)}</strong>
          </div>
        </div>
        <DataTable
          data={incidentScenarioRows}
          emptyLabel="No incident drill scenarios loaded"
          columns={[
            { key: "scenario", title: "scenarios" },
            { key: "status", title: "status" },
            { key: "lockdown_triggered", title: "lockdown" }
          ]}
        />
        <ListTable items={incidentPlaybook} title="remediation playbook" emptyLabel="No remediation playbook loaded" />
        <ListTable items={incidentForbiddenActions} title="forbidden actions" emptyLabel="No forbidden actions loaded" />
      </WidgetCard>

      <WidgetCard
        title="Manual Approval"
        subtitle="Two-person review workflow for shadow, dry-run promotion, or registry review only."
        actions={<RefreshButton disabled={loading} label="Refresh manual approval" onClick={() => void runRefresh("Manual Approval", refreshManualApproval, setManualApproval)} />}
      >
        <div className="metric-grid">
          <div className="metric-card">
            <span>approval status</span>
            <strong><StatusValue value={manualApproval?.status} /></strong>
          </div>
          <div className="metric-card">
            <span>requested action</span>
            <strong>{manualApproval?.requested_action ?? "shadow_mode_only"}</strong>
          </div>
          <div className="metric-card">
            <span>two-person review status</span>
            <strong>{String(manualApproval?.two_person_review_pass ?? false)}</strong>
          </div>
          <div className="metric-card">
            <span>expiry</span>
            <strong>{formatDateTime(manualApproval?.expires_at)}</strong>
          </div>
          <div className="metric-card">
            <span>active_write_allowed</span>
            <strong>{String(manualApproval?.active_write_allowed ?? false)}</strong>
          </div>
          <div className="metric-card">
            <span>customer_prediction_write_allowed</span>
            <strong>{String(manualApproval?.customer_prediction_write_allowed ?? false)}</strong>
          </div>
        </div>
        <p className="compact-note">Active artifact writes are not supported here.</p>
        <DataTable
          data={manualApprovalChecks}
          emptyLabel="No precondition checks loaded"
          columns={[
            { key: "name", title: "precondition checks" },
            { key: "status", title: "status" },
            { key: "reason", title: "reason" }
          ]}
        />
        <ListTable items={manualApprovalBlockingReasons} title="blocking reasons" emptyLabel="No manual approval blockers loaded" />
      </WidgetCard>

      <WidgetCard
        title="Shadow Output Contract"
        subtitle="Dry-run-only schema and path isolation for future shadow outputs."
        actions={
          <div className="button-row">
            <RefreshButton disabled={loading} label="Refresh shadow contract" onClick={() => void runRefresh("Shadow Output Contract", refreshShadowOutputContract, setShadowOutputContract)} />
            <RefreshButton disabled={loading} label="Build shadow dry-run" onClick={() => void runRefresh("Shadow Output Dry-Run", () => buildShadowOutputDryRun({ candidate_version: "v12", horizon: "1d", instrument: "SN" }), setShadowOutputContract)} />
          </div>
        }
      >
        <div className="metric-grid">
          <div className="metric-card">
            <span>shadow output allowed</span>
            <strong>{String(shadowOutputContract?.shadow_output_allowed ?? false)}</strong>
          </div>
          <div className="metric-card">
            <span>dry-run artifact status</span>
            <strong>{shadowOutputContract?.dry_run_artifact_created ? "created" : "not_created"}</strong>
          </div>
          <div className="metric-card">
            <span>output root</span>
            <strong>{shadowOutputContract?.shadow_output_root ?? "outputs/shadow_mode"}</strong>
          </div>
          <div className="metric-card">
            <span>path isolation</span>
            <strong><StatusValue value={shadowOutputContract?.path_isolation_status} /></strong>
          </div>
          <div className="metric-card">
            <span>schema validation</span>
            <strong><StatusValue value={shadowOutputContract?.schema_validation_status} /></strong>
          </div>
          <div className="metric-card">
            <span>customer prediction collision status</span>
            <strong><StatusValue value={shadowOutputContract?.customer_prediction_collision_status} /></strong>
          </div>
        </div>
        <ListTable items={shadowOutputBlockingReasons} title="blocking reasons" emptyLabel="No shadow output blockers loaded" />
      </WidgetCard>

      <WidgetCard
        title="Shadow Replay Evaluator"
        subtitle="Research-only replay from existing OOF traces; it is not a customer prediction."
        actions={<RefreshButton disabled={loading} label="Refresh shadow replay" onClick={() => void runRefresh("Shadow Replay Evaluator", () => refreshShadowReplay({ candidate_version: "v10" }), setShadowReplay)} />}
      >
        <div className="metric-grid">
          <div className="metric-card">
            <span>status</span>
            <strong><StatusValue value={shadowReplay?.status} /></strong>
          </div>
          <div className="metric-card">
            <span>source candidate</span>
            <strong>{shadowReplay?.source_candidate_version ?? "v10"}</strong>
          </div>
          <div className="metric-card">
            <span>replay rows</span>
            <strong>{String(shadowReplay?.replay_row_count ?? 0)}</strong>
          </div>
          <div className="metric-card">
            <span>schema validation</span>
            <strong><StatusValue value={shadowReplay?.schema_validation_status} /></strong>
          </div>
          <div className="metric-card">
            <span>output isolation</span>
            <strong><StatusValue value={shadowReplay?.output_isolation_status} /></strong>
          </div>
          <div className="metric-card">
            <span>stability metrics</span>
            <strong>{String(Object.keys(shadowReplayStabilityMetrics).length)}</strong>
            <small>flip rate: {String(shadowReplayStabilityMetrics.signal_flip_rate ?? "missing")}</small>
          </div>
          <div className="metric-card">
            <span>top risk tags</span>
            <strong>{String(shadowReplayRiskTags.length)}</strong>
          </div>
          <div className="metric-card">
            <span>active/customer prediction confirmation</span>
            <strong>{String(!(shadowReplay?.active_updated ?? false) && !(shadowReplay?.customer_prediction_generated ?? false))}</strong>
          </div>
        </div>
        <ListTable items={shadowReplayRiskTags} title="top risk tags" emptyLabel="No shadow replay risk tags loaded" />
        <ListTable items={shadowReplaySkippedReasons} title="skipped reasons" emptyLabel="No shadow replay skips loaded" />
      </WidgetCard>

      <WidgetCard
        title="Post-Release Monitoring Spec"
        subtitle="Planning-only drift sentinel contract; no live monitoring daemon or customer prediction is started here."
        actions={<RefreshButton disabled={loading} label="Refresh monitoring spec" onClick={() => void runRefresh("Post-Release Monitoring Spec", refreshPostReleaseMonitoringSpec, setPostReleaseMonitoring)} />}
      >
        <div className="metric-grid">
          <div className="metric-card">
            <span>status</span>
            <strong><StatusValue value={postReleaseMonitoring?.status} /></strong>
          </div>
          <div className="metric-card">
            <span>monitoring mode</span>
            <strong>{postReleaseMonitoring?.monitoring_mode ?? "planning_only"}</strong>
          </div>
          <div className="metric-card">
            <span>live monitoring enabled</span>
            <strong>{String(postReleaseMonitoring?.live_monitoring_enabled ?? false)}</strong>
          </div>
          <div className="metric-card">
            <span>sentinel count</span>
            <strong>{String(postReleaseMonitoring?.sentinel_count ?? 0)}</strong>
          </div>
          <div className="metric-card">
            <span>key alert thresholds</span>
            <strong>{String(monitoringAlertThresholds.length)}</strong>
          </div>
          <div className="metric-card">
            <span>readiness gaps</span>
            <strong>{String(monitoringReadinessGaps.length)}</strong>
          </div>
          <div className="metric-card">
            <span>shadow replay status</span>
            <strong><StatusValue value={postReleaseMonitoring?.shadow_replay_status} /></strong>
            <small>{postReleaseMonitoring?.shadow_replay_source_candidate ?? "missing"}</small>
          </div>
          <div className="metric-card">
            <span>active/customer prediction sentinel status</span>
            <strong><StatusValue value={postReleaseMonitoring?.active_customer_prediction_sentinel_status} /></strong>
          </div>
        </div>
        <DataTable
          data={monitoringAlertThresholds.slice(0, 8)}
          emptyLabel="No monitoring thresholds loaded"
          columns={[
            { key: "name", title: "key alert thresholds" },
            { key: "threshold", title: "threshold" },
            { key: "action", title: "action" }
          ]}
        />
        <ListTable items={monitoringReadinessGaps} title="readiness gaps" emptyLabel="No monitoring readiness gaps loaded" />
      </WidgetCard>

      <WidgetCard
        title="Rollback / Quarantine"
        subtitle="Simulation-only rollback rehearsal for unapproved active, registry, shadow, and customer prediction artifacts."
        actions={
          <div className="button-row">
            <RefreshButton disabled={loading} label="Refresh rollback rehearsal" onClick={() => void runRefresh("Rollback Rehearsal", refreshRollbackRehearsal, setRollbackRehearsal)} />
            <RefreshButton disabled={loading} label="Simulate artifact quarantine" onClick={() => void runRefresh("Artifact Quarantine Simulation", simulateArtifactQuarantine, setRollbackRehearsal)} />
          </div>
        }
      >
        <div className="metric-grid">
          <div className="metric-card">
            <span>rehearsal status</span>
            <strong><StatusValue value={rollbackRehearsal?.status} /></strong>
          </div>
          <div className="metric-card">
            <span>quarantine_needed</span>
            <strong>{String(rollbackRehearsal?.quarantine_needed ?? false)}</strong>
          </div>
          <div className="metric-card">
            <span>artifacts_detected</span>
            <strong>{String(rollbackArtifacts.length)}</strong>
          </div>
          <div className="metric-card">
            <span>simulated quarantine actions</span>
            <strong>{String(rollbackActions.length)}</strong>
          </div>
          <div className="metric-card">
            <span>rollback plan</span>
            <strong>{String(rollbackPlan.length)}</strong>
          </div>
          <div className="metric-card">
            <span>manual actions required</span>
            <strong>{String(rollbackManualActions.length)}</strong>
          </div>
          <div className="metric-card">
            <span>safety checks</span>
            <strong>{String(rollbackSafetyChecks.length)}</strong>
          </div>
          <div className="metric-card">
            <span>report path</span>
            <strong>{rollbackRehearsal?.report_path ? "available" : "missing"}</strong>
          </div>
        </div>
        <DataTable
          data={rollbackArtifacts}
          emptyLabel="No unapproved artifacts detected"
          columns={[
            { key: "artifact_type", title: "artifacts_detected" },
            { key: "reason", title: "reason" },
            { key: "recommended_action", title: "recommended action" }
          ]}
        />
        <DataTable
          data={rollbackActions}
          emptyLabel="No simulated quarantine actions"
          columns={[
            { key: "artifact_type", title: "simulated quarantine actions" },
            { key: "reason", title: "reason" },
            { key: "simulation_only", title: "simulation only" }
          ]}
        />
        <ListTable items={rollbackPlan} title="rollback plan" emptyLabel="No rollback plan loaded" />
        <ListTable items={rollbackManualActions} title="manual actions required" emptyLabel="No manual actions loaded" />
        <DataTable
          data={rollbackSafetyChecks}
          emptyLabel="No safety checks loaded"
          columns={[
            { key: "check", title: "safety checks" },
            { key: "value", title: "value" }
          ]}
        />
      </WidgetCard>

      <WidgetCard
        title="Research Decision Board"
        subtitle="Top-level research state and next allowed action."
        actions={<RefreshButton disabled={loading} label="Refresh board" onClick={() => void runRefresh("Research Decision Board", refreshResearchDecisionBoard, setDecisionBoard)} />}
      >
        <div className="metric-grid">
          <div className="metric-card">
            <span>status</span>
            <strong><StatusValue value={decisionBoard?.status} /></strong>
          </div>
          <div className="metric-card">
            <span>current_research_state</span>
            <strong>{decisionBoard?.current_research_state ?? "missing"}</strong>
          </div>
          <div className="metric-card">
            <span>next_allowed_action</span>
            <strong>{formatNextAction(decisionBoard?.next_allowed_action ?? "review_decision_board")}</strong>
          </div>
          <div className="metric-card">
            <span>manual_approval_recommended</span>
            <strong>{String(decisionBoard?.manual_approval_recommended ?? false)}</strong>
          </div>
        </div>
        <ListTable items={decisionBlockingReasons} title="blocked reasons" emptyLabel="No decision board blockers" />
      </WidgetCard>

      <WidgetCard
        title="Readiness DAG"
        subtitle="Dependency graph for safe gate checks; skipped nodes never count as pass."
        actions={
          <div className="button-row">
            <RefreshButton disabled={loading} label="Refresh DAG" onClick={() => void runRefresh("Readiness DAG", refreshReadinessDag, setReadinessDag)} />
            <RefreshButton disabled={loading} label="Run safe checks" onClick={() => void runRefresh("Readiness safe checks", runSafeReadinessChecks, setReadinessDag)} />
          </div>
        }
      >
        <div className="metric-grid">
          <div className="metric-card">
            <span>status</span>
            <strong><StatusValue value={readinessDag?.status} /></strong>
          </div>
          <div className="metric-card">
            <span>critical path</span>
            <strong>{asStringList(readinessDag?.critical_path).join(" -> ") || "missing"}</strong>
          </div>
          <div className="metric-card">
            <span>blocked nodes</span>
            <strong>{String(readinessBlockedNodes.length)}</strong>
          </div>
          <div className="metric-card">
            <span>skipped nodes</span>
            <strong>{String(readinessSkippedNodes.length)}</strong>
          </div>
        </div>
        <ListTable items={readinessForbiddenActions} title="forbidden actions" emptyLabel="No forbidden actions loaded" />
      </WidgetCard>

      <WidgetCard
        title="Evidence Freshness"
        subtitle="Staleness and timestamp consistency for evidence reports."
        actions={<RefreshButton disabled={loading} label="Refresh freshness" onClick={() => void runRefresh("Evidence Freshness", refreshEvidenceFreshness, setEvidenceFreshness)} />}
      >
        <div className="metric-grid">
          <div className="metric-card">
            <span>freshness status</span>
            <strong><StatusValue value={evidenceFreshness?.status} /></strong>
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
            <strong>{String(evidenceFreshness?.timestamp_inversions?.length ?? 0)}</strong>
          </div>
        </div>
      </WidgetCard>

      <WidgetCard
        title="Evidence Bundle"
        subtitle="Reproducibility index from existing report files and hashes."
        actions={<RefreshButton disabled={loading} label="Refresh evidence bundle" onClick={() => void runRefresh("Evidence Bundle", refreshEvidenceBundle, setEvidenceBundle)} />}
      >
        <div className="metric-grid">
          <div className="metric-card">
            <span>bundle status</span>
            <strong><StatusValue value={evidenceBundle?.status} /></strong>
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
            <span>next_allowed_action</span>
            <strong>{formatNextAction(evidenceBundle?.next_allowed_action ?? "review_missing_evidence")}</strong>
          </div>
        </div>
      </WidgetCard>

      <WidgetCard
        title="External Audit Export"
        subtitle="Redacted reviewer package with evidence paths, hashes, blockers, and no raw rows."
        actions={<RefreshButton disabled={loading} label="Refresh audit export" onClick={() => void runRefresh("External Audit Export", refreshExternalAuditExport, setExternalAuditExport)} />}
      >
        <div className="metric-grid">
          <div className="metric-card">
            <span>export status</span>
            <strong><StatusValue value={externalAuditExport?.status} /></strong>
          </div>
          <div className="metric-card">
            <span>export root</span>
            <strong>{externalAuditExport?.export_root ?? "missing"}</strong>
          </div>
          <div className="metric-card">
            <span>evidence file count</span>
            <strong>{String(externalAuditExport?.evidence_file_count ?? 0)}</strong>
          </div>
          <div className="metric-card">
            <span>missing/incomplete reports</span>
            <strong>{String(auditMissingReports.length + auditIncompleteReports.length)}</strong>
          </div>
          <div className="metric-card">
            <span>redaction status</span>
            <strong><StatusValue value={externalAuditExport?.redaction_status} /></strong>
            <small>{String(auditRedactedFields.length)} redacted fields</small>
          </div>
          <div className="metric-card">
            <span>review summary path</span>
            <strong>{externalAuditExport?.review_summary_path ?? "missing"}</strong>
          </div>
        </div>
        <ListTable items={auditOmittedSensitiveFiles} title="omitted sensitive files" emptyLabel="No sensitive files omitted" />
      </WidgetCard>

      <WidgetCard
        title="Production Cutover Checklist"
        subtitle="No-op release checklist for manual review boundaries; it is not approval."
        actions={
          <div className="button-row">
            <RefreshButton disabled={loading} label="Refresh cutover checklist" onClick={() => void runRefresh("Production Cutover Checklist", refreshProductionCutoverChecklist, setProductionCutover)} />
            <RefreshButton disabled={loading} label="Build no-op release plan" onClick={() => void runRefresh("No-op Release Plan", () => buildNoopReleasePlan({ candidate_version: "v12" }), setProductionCutover)} />
          </div>
        }
      >
        <div className="metric-grid">
          <div className="metric-card">
            <span>cutover_allowed</span>
            <strong>{String(productionCutover?.cutover_allowed ?? false)}</strong>
          </div>
          <div className="metric-card">
            <span>noop plan status</span>
            <strong>{productionCutover?.noop_release_plan_ready ? "ready" : "blocked"}</strong>
          </div>
          <div className="metric-card">
            <span>precondition checks</span>
            <strong>{String(cutoverPreconditionRows.length)}</strong>
          </div>
          <div className="metric-card">
            <span>required manual steps</span>
            <strong>{String(cutoverRequiredManualSteps.length)}</strong>
          </div>
          <div className="metric-card">
            <span>forbidden actions</span>
            <strong>{String(cutoverForbiddenActions.length)}</strong>
          </div>
          <div className="metric-card">
            <span>rollback plan summary</span>
            <strong><StatusValue value={String(cutoverRollbackSummary.status ?? "missing")} /></strong>
          </div>
        </div>
        <DataTable
          data={cutoverPreconditionRows}
          emptyLabel="No cutover precondition checks loaded"
          columns={[
            { key: "name", title: "precondition checks" },
            { key: "status", title: "status" },
            { key: "reason", title: "reason" }
          ]}
        />
        <ListTable items={cutoverRequiredManualSteps} title="required manual steps" emptyLabel="No required manual steps loaded" />
        <ListTable items={cutoverForbiddenActions} title="forbidden actions" emptyLabel="No forbidden actions loaded" />
      </WidgetCard>

      <WidgetCard
        title="Promotion Dry-Run Evidence"
        subtitle="Evidence-only registry write simulation with active and customer prediction boundaries."
        actions={<RefreshButton disabled={loading} label="Refresh promotion dry-run evidence" onClick={() => void runRefresh("Promotion Dry-Run Evidence", () => refreshPromotionDryRunEvidence({ candidate_version: "v12" }), setPromotionDryRunEvidence)} />}
      >
        <div className="metric-grid">
          <div className="metric-card">
            <span>promotion dry-run status</span>
            <strong><StatusValue value={promotionDryRunEvidence?.status} /></strong>
          </div>
          <div className="metric-card">
            <span>precondition checks</span>
            <strong>{String(promotionPreconditionRows.length)}</strong>
          </div>
          <div className="metric-card">
            <span>simulated registry write plan</span>
            <strong>{String(promotionRegistryPlan.status ?? "missing")}</strong>
            <small>{String(promotionRegistryPlan.requested_action ?? "promotion_dry_run_only")}</small>
          </div>
          <div className="metric-card">
            <span>artifact boundary checks</span>
            <strong>{String(promotionBoundaryRows.length)}</strong>
          </div>
          <div className="metric-card">
            <span>active/customer prediction confirmation</span>
            <strong>{String(!(promotionDryRunEvidence?.active_updated ?? false) && !(promotionDryRunEvidence?.customer_prediction_generated ?? false))}</strong>
            <small>active write allowed: {String(promotionDryRunEvidence?.active_write_allowed ?? false)}</small>
          </div>
          <div className="metric-card">
            <span>report path</span>
            <strong>{promotionDryRunEvidence?.report_path ?? "missing"}</strong>
          </div>
        </div>
        <DataTable
          data={promotionPreconditionRows}
          emptyLabel="No promotion dry-run precondition checks loaded"
          columns={[
            { key: "name", title: "precondition checks" },
            { key: "status", title: "status" },
            { key: "reason", title: "reason" }
          ]}
        />
        <DataTable
          data={promotionBoundaryRows}
          emptyLabel="No artifact boundary checks loaded"
          columns={[
            { key: "check", title: "artifact boundary checks" },
            { key: "value", title: "value" }
          ]}
        />
        <ListTable items={promotionBlockingReasons} title="blocking reasons" emptyLabel="No promotion dry-run blockers loaded" />
      </WidgetCard>

      <WidgetCard
        title="Model Card / Risk Disclosure"
        subtitle="Research-only model card for reviewer use; it documents blockers and forbidden uses without approval or prediction rights."
        actions={<RefreshButton disabled={loading} label="Refresh model card" onClick={() => void runRefresh("Model Card", refreshModelCard, setModelCard)} />}
      >
        <div className="metric-grid">
          <div className="metric-card">
            <span>current status</span>
            <strong><StatusValue value={modelCard?.current_status ?? modelCard?.status} /></strong>
          </div>
          <div className="metric-card">
            <span>intended use</span>
            <strong>{modelCardIntendedUse[0] ?? "research_only"}</strong>
            <small>{String(modelCardIntendedUse.length)} allowed review contexts</small>
          </div>
          <div className="metric-card">
            <span>prohibited use</span>
            <strong>{String(modelCardProhibitedUse.length)}</strong>
            <small>production, active, customer prediction, and advice remain forbidden.</small>
          </div>
          <div className="metric-card">
            <span>key limitations</span>
            <strong>{String(modelCardLimitations.length)}</strong>
          </div>
          <div className="metric-card">
            <span>gate failures</span>
            <strong>{String(modelCardGateFailures.length)}</strong>
          </div>
          <div className="metric-card">
            <span>model_card.md path</span>
            <strong>{modelCard?.model_card_md_path ?? "missing"}</strong>
          </div>
          <div className="metric-card">
            <span>risk_disclosure.md path</span>
            <strong>{modelCard?.risk_disclosure_path ?? "missing"}</strong>
          </div>
          <div className="metric-card">
            <span>no-active/no-prediction confirmation</span>
            <strong>{String(Boolean(modelCardNoActive.confirmed) && Boolean(modelCardNoPrediction.confirmed))}</strong>
            <small>active updated: {String(modelCard?.active_updated ?? false)} / prediction generated: {String(modelCard?.customer_prediction_generated ?? false)}</small>
          </div>
        </div>
        <ListTable items={modelCardProhibitedUse} title="prohibited use" emptyLabel="No prohibited use loaded" />
        <ListTable items={modelCardLimitations} title="key limitations" emptyLabel="No model card limitations loaded" />
        <ListTable items={modelCardGateFailures} title="gate failures" emptyLabel="No model card gate failures loaded" />
      </WidgetCard>

      <WidgetCard
        title="Maturity Gap Matrix"
        subtitle="Final hardening roadmap across data, research, governance, shadow, and production readiness gates."
        actions={<RefreshButton disabled={loading} label="Refresh maturity matrix" onClick={() => void runRefresh("Maturity Gap Matrix", refreshGovernanceMaturityMatrix, setMaturityMatrix)} />}
      >
        <div className="metric-grid">
          <div className="metric-card">
            <span>production_readiness</span>
            <strong>{String(maturityMatrix?.production_readiness ?? false)}</strong>
          </div>
          <div className="metric-card">
            <span>shadow_readiness</span>
            <strong>{String(Boolean(maturityShadowReadiness.ready))}</strong>
            <small>score {String(maturityShadowReadiness.score ?? "missing")}</small>
          </div>
          <div className="metric-card">
            <span>lowest scoring domains</span>
            <strong>{String(maturityDomainRows.length)}</strong>
          </div>
          <div className="metric-card">
            <span>critical gaps</span>
            <strong>{String(maturityCriticalGaps.length)}</strong>
          </div>
          <div className="metric-card">
            <span>completed controls</span>
            <strong>{String(maturityCompletedControls.length)}</strong>
          </div>
          <div className="metric-card">
            <span>missing controls</span>
            <strong>{String(maturityMissingControls.length)}</strong>
          </div>
          <div className="metric-card">
            <span>recommended prompt sequence</span>
            <strong>{String(maturityPromptRows.length)}</strong>
          </div>
          <div className="metric-card">
            <span>report path</span>
            <strong>{maturityMatrix?.report_path ?? "missing"}</strong>
          </div>
        </div>
        <DataTable
          data={maturityDomainRows}
          emptyLabel="No maturity domain scores loaded"
          columns={[
            { key: "domain", title: "lowest scoring domains" },
            { key: "score", title: "score" },
            { key: "status", title: "status" }
          ]}
        />
        <ListTable items={maturityCriticalGaps} title="critical gaps" emptyLabel="No maturity critical gaps loaded" />
        <ListTable items={maturityCompletedControls} title="completed controls" emptyLabel="No completed controls loaded" />
        <ListTable items={maturityMissingControls} title="missing controls" emptyLabel="No missing controls loaded" />
        <DataTable
          data={maturityPromptRows}
          emptyLabel="No recommended prompt sequence loaded"
          columns={[
            { key: "priority", title: "priority" },
            { key: "action", title: "recommended prompt sequence" }
          ]}
        />
      </WidgetCard>

      <WidgetCard
        title="Run Ledger"
        subtitle="Append-only manifest ledger for safe research checks and report refreshes."
        actions={<RefreshButton disabled={loading} label="Refresh run ledger" onClick={() => void runRefresh("Run Ledger", refreshRunLedger, setRunLedger)} />}
      >
        <div className="metric-grid">
          <div className="metric-card">
            <span>run ledger status</span>
            <strong><StatusValue value={runLedger?.status} /></strong>
          </div>
          <div className="metric-card">
            <span>latest runs</span>
            <strong>{String(runLedger?.latest_run_count ?? runLedger?.latest_runs?.length ?? 0)}</strong>
          </div>
          <div className="metric-card">
            <span>violation count</span>
            <strong>{String(runLedger?.violation_count ?? 0)}</strong>
          </div>
          <div className="metric-card">
            <span>safe checks vs heavy tasks</span>
            <strong>{String(runLedger?.safe_check_count ?? 0)} / {String(runLedger?.heavy_task_count ?? 0)}</strong>
          </div>
        </div>
        <ListTable items={runLedgerForbiddenEffects} title="forbidden side effects" emptyLabel="No forbidden side effects configured" />
      </WidgetCard>

      <WidgetCard
        title="Hypothesis Registry"
        subtitle="Predeclared experiment hypotheses and anti-p-hacking ledger."
        actions={<RefreshButton disabled={loading} label="Refresh anti-p-hacking ledger" onClick={() => void runRefresh("Anti-p-hacking ledger", refreshAntiPHackingLedger, setAntiPHackingLedger)} />}
      >
        <div className="metric-grid">
          <div className="metric-card">
            <span>registry status</span>
            <strong><StatusValue value={hypothesisRegistry?.status} /></strong>
          </div>
          <div className="metric-card">
            <span>open hypotheses</span>
            <strong>{String(hypothesisRegistry?.open_hypotheses ?? 0)}</strong>
          </div>
          <div className="metric-card">
            <span>p-hacking risk</span>
            <strong>{hypothesisRegistry?.p_hacking_risk_level ?? antiPHackingLedger?.p_hacking_risk_level ?? "unknown"}</strong>
          </div>
          <div className="metric-card">
            <span>experiment budget usage</span>
            <strong>{String(Object.keys(asRecord(hypothesisRegistry?.experiment_budget_by_blocker)).length)}</strong>
          </div>
        </div>
      </WidgetCard>

      <WidgetCard
        title="Shadow Mode Readiness"
        subtitle="Readiness contract for future shadow observations and output isolation."
        actions={<RefreshButton disabled={loading} label="Refresh shadow readiness" onClick={() => void runRefresh("Shadow Mode Readiness", refreshShadowModeReadiness, setShadowModeReadiness)} />}
      >
        <div className="metric-grid">
          <div className="metric-card">
            <span>readiness status</span>
            <strong><StatusValue value={shadowModeReadiness?.status} /></strong>
          </div>
          <div className="metric-card">
            <span>shadow_mode_allowed</span>
            <strong>{String(shadowModeReadiness?.shadow_mode_allowed ?? false)}</strong>
          </div>
          <div className="metric-card">
            <span>approval_required</span>
            <strong>{String(shadowModeReadiness?.approval_required ?? true)}</strong>
          </div>
          <div className="metric-card">
            <span>blocked gates</span>
            <strong>{String(shadowBlockedGates.length)}</strong>
          </div>
        </div>
        <ListTable items={shadowBlockedGates} title="blocked gates" emptyLabel="No shadow mode blockers" />
      </WidgetCard>

      <WidgetCard
        title="Model Registry Safety"
        subtitle="Safety contract and rollback readiness for future registry writes."
        actions={<RefreshButton disabled={loading} label="Refresh registry safety" onClick={() => void runRefresh("Model Registry Safety", refreshModelRegistrySafety, setModelRegistrySafety)} />}
      >
        <div className="metric-grid">
          <div className="metric-card">
            <span>registry safety status</span>
            <strong><StatusValue value={modelRegistrySafety?.status} /></strong>
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
        </div>
        <ListTable items={registryBlockingReasons} title="blocking reasons" emptyLabel="No registry safety blockers" />
      </WidgetCard>

      {!decisionBoard && !readinessDag && !evidenceBundle && !loading ? (
        <EmptyState
          title="No governance reports loaded"
          description="Use safe report refreshes after the backend is available."
          actionLabel="Refresh all governance reports"
          onAction={loadAll}
        />
      ) : null}
    </div>
  );
}
