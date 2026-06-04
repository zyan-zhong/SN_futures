import { useEffect, useState } from "react";
import { getPredictionWorkspaceStatus, getSetupChecklistStatus } from "../api/terminal";
import type { PredictionWorkspaceStatusPayload, SetupChecklistStatusPayload } from "../api/types";
import { DataTable } from "../components/common/DataTable";
import { WorkspaceGuardBanner } from "../components/common/WorkspaceGuardBanner";
import { SectionCard } from "../components/layout/SectionCard";
import { GuidedSetupChecklist } from "../components/setup/GuidedSetupChecklist";
import { PredictionBlockedEmptyState } from "../components/setup/PredictionBlockedEmptyState";
import { formatBooleanFlag, formatRawStatusLabel, formatWorkspaceFieldLabel } from "../utils/copySystem";
import { formatNextAction, formatStatusLabel } from "../utils/statusTaxonomy";

export function PredictionWorkspacePage() {
  const [workspace, setWorkspace] = useState<PredictionWorkspaceStatusPayload | null>(null);
  const [setupChecklist, setSetupChecklist] = useState<SetupChecklistStatusPayload | null>(null);

  useEffect(() => {
    void getPredictionWorkspaceStatus().then(setWorkspace).catch(() => setWorkspace(null));
    void getSetupChecklistStatus().then(setSetupChecklist).catch(() => setSetupChecklist(null));
  }, []);

  const setup_action_telemetry = setupChecklist?.setup_action_telemetry;

  return (
    <div className="page-stack">
      <WorkspaceGuardBanner workspace="Prediction Workspace" source={workspace ?? {}} />
      <PredictionBlockedEmptyState nextAllowedAction={workspace?.next_allowed_action} />
      <SectionCard title="Prediction Workspace" subtitle="Read-only blocked workspace. It does not call backend prediction endpoints.">
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
          <div className="metric-card">
            <span>{formatWorkspaceFieldLabel("customer_prediction_generated")}</span>
            <strong>{formatBooleanFlag(workspace?.customer_prediction_generated ?? false)}</strong>
          </div>
        </div>
        <details aria-label="Prediction raw status details" className="technical-details-drawer">
          <summary>Raw status</summary>
          <dl>
            <div>
              <dt>{formatRawStatusLabel("prediction_status")}</dt>
              <dd>{workspace?.prediction_status ?? "blocked"}</dd>
            </div>
            <div>
              <dt>Raw status: prediction_generation_allowed</dt>
              <dd>{String(workspace?.prediction_generation_allowed ?? false)}</dd>
            </div>
            <div>
              <dt>Raw status: active_model_available</dt>
              <dd>{String(workspace?.active_model_available ?? false)}</dd>
            </div>
            <div>
              <dt>Raw status: customer_prediction_generated</dt>
              <dd>{String(workspace?.customer_prediction_generated ?? false)}</dd>
            </div>
          </dl>
        </details>
        <div className="notice-card">
          <strong>无 active model 确认</strong>
          <span>{workspace?.active_model_path_exists ? "发现异常 active artifact" : "active_model.json 不存在"}</span>
        </div>
        <div className="notice-card">
          <strong>无 customer prediction 确认</strong>
          <span>{workspace?.customer_predictions_path_exists ? "发现异常 customer output" : "customer_predictions 不存在"}</span>
        </div>
      </SectionCard>

      <SectionCard title="required gates" subtitle="All gates must pass before any future isolated shadow or prediction workflow can be considered.">
        <DataTable data={(workspace?.required_gates ?? []).map((gate) => ({ gate }))} emptyLabel="No gates loaded" columns={[{ key: "gate", title: "gate" }]} />
      </SectionCard>

      <SectionCard title="Recent safe check result" subtitle="Safe setup checks can update evidence, but prediction remains blocked without active approval.">
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
            <span>{formatWorkspaceFieldLabel("prediction_generation_allowed")}</span>
            <strong>{formatBooleanFlag(workspace?.prediction_generation_allowed ?? false)}</strong>
          </div>
        </div>
      </SectionCard>

      <SectionCard title="blocking reasons" subtitle="Current blocker list, including Decision Board state and artifact boundary checks.">
        <DataTable
          data={(workspace?.blocking_reasons ?? []).slice(0, 12).map((reason) => ({ reason }))}
          emptyLabel="No blockers loaded"
          columns={[{ key: "reason", title: "reason" }]}
        />
        <div className="notice-card">
          <strong>{formatWorkspaceFieldLabel("next_allowed_action")}</strong>
          <span>{formatNextAction(workspace?.next_allowed_action ?? "configure_managed_proxy_endpoint_or_token")}</span>
        </div>
        <details aria-label="Prediction next action raw status details" className="technical-details-drawer">
          <summary>Raw status</summary>
          <dl>
            <div>
              <dt>{formatRawStatusLabel("next_allowed_action")}</dt>
              <dd>{workspace?.next_allowed_action ?? "configure_managed_proxy_endpoint_or_token"}</dd>
            </div>
          </dl>
        </details>
      </SectionCard>

      <GuidedSetupChecklist compact />

      <SectionCard title="evidence paths" subtitle="Read-only evidence pointers; no customer output paths are accepted here.">
        <DataTable
          data={Object.entries(workspace?.evidence_paths ?? {}).slice(0, 10).map(([name, path]) => ({ name, path }))}
          emptyLabel="No evidence paths loaded"
          columns={[
            { key: "name", title: "name" },
            { key: "path", title: "path" }
          ]}
        />
      </SectionCard>
    </div>
  );
}
