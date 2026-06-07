import { useEffect, useState } from "react";
import { getPredictionWorkspaceStatus, getResearchDecisionBoard, getSetupChecklistStatus } from "../api/terminal";
import type { PredictionWorkspaceStatusPayload, ResearchDecisionBoardPayload, SetupChecklistStatusPayload } from "../api/types";
import { DataTable } from "../components/common/DataTable";
import { WorkspaceGuardBanner } from "../components/common/WorkspaceGuardBanner";
import { SectionCard } from "../components/layout/SectionCard";
import { GuidedSetupChecklist } from "../components/setup/GuidedSetupChecklist";
import { LocalFirstStatusPanel } from "../components/setup/LocalFirstStatusPanel";
import { PredictionBlockedEmptyState } from "../components/setup/PredictionBlockedEmptyState";
import { SafeConfigInstructions } from "../components/setup/SafeConfigInstructions";
import { formatBooleanFlag, formatWorkspaceFieldLabel } from "../utils/copySystem";
import { formatNextAction, formatStatusLabel } from "../utils/statusTaxonomy";

function asRows(values?: string[]) {
  return (values ?? []).slice(0, 8).map((reason) => ({ reason }));
}

export function TerminalOverviewPage() {
  const [board, setBoard] = useState<ResearchDecisionBoardPayload | null>(null);
  const [workspace, setWorkspace] = useState<PredictionWorkspaceStatusPayload | null>(null);
  const [setupChecklist, setSetupChecklist] = useState<SetupChecklistStatusPayload | null>(null);

  useEffect(() => {
    void getResearchDecisionBoard().then(setBoard).catch(() => setBoard(null));
    void getPredictionWorkspaceStatus().then(setWorkspace).catch(() => setWorkspace(null));
    void getSetupChecklistStatus().then(setSetupChecklist).catch(() => setSetupChecklist(null));
  }, []);

  const setup_action_telemetry = setupChecklist?.setup_action_telemetry;

  return (
    <div className="page-stack">
      <WorkspaceGuardBanner workspace="Terminal Overview" source={{ ...(board ?? {}), ...(workspace ?? {}) }} />
      <LocalFirstStatusPanel title="System Readiness" />
      <PredictionBlockedEmptyState nextAllowedAction={workspace?.next_allowed_action} />
      <GuidedSetupChecklist />
      <SectionCard title="Current State" subtitle="Terminal Overview keeps the first screen focused on the current blocker and next safe action.">
        <div className="metric-grid">
          <div className="metric-card">
            <span>{formatWorkspaceFieldLabel("current_state")}</span>
            <strong>{formatStatusLabel(board?.current_research_state ?? workspace?.current_research_state ?? "managed_data_blocked")}</strong>
          </div>
          <div className="metric-card">
            <span>{formatWorkspaceFieldLabel("next_allowed_action")}</span>
            <strong>{formatNextAction(board?.next_allowed_action ?? workspace?.next_allowed_action ?? "configure_managed_proxy_endpoint_or_token")}</strong>
          </div>
          <div className="metric-card">
            <span>{formatWorkspaceFieldLabel("active_publish_allowed")}</span>
            <strong>{formatBooleanFlag(board?.active_publish_allowed ?? false)}</strong>
          </div>
          <div className="metric-card">
            <span>{formatWorkspaceFieldLabel("customer_prediction_generated")}</span>
            <strong>{formatBooleanFlag(board?.customer_prediction_generated ?? false)}</strong>
          </div>
        </div>
      </SectionCard>

      <SectionCard title="Prediction Workspace summary" subtitle="Blocked placeholder only; no customer-visible output is generated.">
        <div className="metric-grid">
          <div className="metric-card">
            <span>{formatWorkspaceFieldLabel("prediction_status")}</span>
            <strong>{formatStatusLabel(workspace?.prediction_status ?? "blocked")}</strong>
          </div>
          <div className="metric-card">
            <span>{formatWorkspaceFieldLabel("prediction_generation_allowed")}</span>
            <strong>{formatBooleanFlag(workspace?.prediction_generation_allowed ?? false)}</strong>
          </div>
          <div className="metric-card">
            <span>{formatWorkspaceFieldLabel("active_model_available")}</span>
            <strong>{formatBooleanFlag(workspace?.active_model_available ?? false)}</strong>
          </div>
        </div>
      </SectionCard>

      <SectionCard title="Recent safe setup action" subtitle="Setup action telemetry is read-only and cannot unlock prediction by itself.">
        <div className="metric-grid">
          <div className="metric-card">
            <span>latest action</span>
            <strong>{setup_action_telemetry?.latest_action || "not run"}</strong>
          </div>
          <div className="metric-card">
            <span>latest action status</span>
            <strong>{formatStatusLabel(setup_action_telemetry?.latest_action_status ?? "not_run")}</strong>
          </div>
          <div className="metric-card">
            <span>current setup step</span>
            <strong>{setupChecklist?.current_step || "configure_local_api_provider_credentials"}</strong>
          </div>
        </div>
      </SectionCard>

      <details aria-label="Advanced Diagnostics / Research Governance" className="technical-details-drawer">
        <summary>Advanced Diagnostics / Research Governance</summary>
        <SectionCard title="Managed Proxy / v12 chain" subtitle="Legacy and advanced governance diagnostics are secondary to local provider readiness.">
          <div className="metric-grid">
            <div className="metric-card">
              <span>managed proxy</span>
              <strong>{formatStatusLabel(board?.managed_proxy_summary?.status ?? "blocked")}</strong>
            </div>
            <div className="metric-card">
              <span>Feature Store v12</span>
              <strong>{formatStatusLabel(board?.feature_store_v12_summary?.status ?? "blocked")}</strong>
            </div>
            <div className="metric-card">
              <span>Training Dataset v12</span>
              <strong>{formatStatusLabel(board?.training_dataset_v12_summary?.status ?? "blocked")}</strong>
            </div>
          </div>
        </SectionCard>
      </details>

      <SectionCard title="No-active / no-prediction confirmation" subtitle="This overview is read-only and does not start backend tasks.">
        <div className="notice-card">
          <strong>active and customer output remain unavailable</strong>
          <span>Active 更新：否 / customer prediction 生成：否</span>
        </div>
        <SafeConfigInstructions />
      </SectionCard>

      <SectionCard title="Latest blocking reasons" subtitle="Short blocker list from the Decision Board and Prediction Workspace.">
        <DataTable
          data={asRows(board?.blocking_reasons).concat(asRows(workspace?.blocking_reasons)).slice(0, 8)}
          emptyLabel="No blocking reasons loaded"
          columns={[{ key: "reason", title: "reason" }]}
        />
      </SectionCard>
    </div>
  );
}
