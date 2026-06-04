import { useEffect, useState } from "react";
import { getSetupChecklistStatus, runSetupChecklistSafeAction } from "../../api/terminal";
import type { SetupActionRunPayload, SetupActionTelemetryPayload, SetupChecklistStatusPayload, SetupChecklistStepPayload } from "../../api/types";
import { deriveSetupChecklist, type SetupChecklistStep, type SetupStepStatus } from "../../utils/guidedSetup";
import { formatStatusLabel } from "../../utils/statusTaxonomy";
import { LocalApiProviderHandoffCard } from "./LocalApiProviderHandoffCard";
import { NextActionStepper } from "./NextActionStepper";
import { SafeConfigInstructions } from "./SafeConfigInstructions";

const fallbackActionByStep: Record<string, string> = {
  "configure-local-api-provider": "refresh_provider_credentials",
  "configure-managed-proxy": "refresh_provider_credentials",
  "operator-runbook": "refresh_operator_runbook",
  "provider-smoke": "run_provider_smoke",
  "endpoint-smoke": "run_provider_smoke",
  "schema-sample-fixture": "run_sample_fixture_contract",
  "pit-audit": "run_pit_replay",
  "data-quality": "refresh_data_quality",
  "v12-input-controlled-build": "refresh_decision_board",
};

const canonicalStepLabels: Record<string, string> = {
  configure_local_api_provider_credentials: "Configure Local API Provider credentials",
  configure_managed_proxy_endpoint_token: "Configure Local API Provider credentials",
};

function normalizeStatus(value: unknown): SetupStepStatus {
  const text = String(value || "").trim();
  if (["complete", "blocked", "available", "locked", "running", "failed", "current"].includes(text)) {
    return text as SetupStepStatus;
  }
  return "blocked";
}

function normalizeRemoteStep(step: SetupChecklistStepPayload): SetupChecklistStep {
  const id = step.step_id || "setup-step";
  const label = canonicalStepLabels[id] || step.label || id;
  const reason = step.short_reason || "Safe setup progress check";
  const actionId = step.safe_action_id || "refresh_provider_credentials";
  return {
    id,
    step_id: id,
    title: label,
    label,
    description: reason,
    status: normalizeStatus(step.status),
    isCurrent: Boolean(step.is_current_step),
    is_current_step: Boolean(step.is_current_step),
    safeAction: actionId,
    safe_action_id: actionId,
    action_enabled: Boolean(step.action_enabled),
    action_disabled_reason: step.action_disabled_reason || "",
    short_reason: reason,
    evidence_path: step.evidence_path || "",
    disabledReason: step.action_disabled_reason || "",
  };
}

function normalizeFallbackStep(step: SetupChecklistStep): SetupChecklistStep {
  const actionId = fallbackActionByStep[step.id] || step.safe_action_id || "refresh_provider_credentials";
  const disabledReason = step.disabledReason || "";
  return {
    ...step,
    step_id: step.step_id || step.id,
    label: step.label || step.title,
    safe_action_id: actionId,
    action_enabled: Boolean(step.action_enabled ?? (!disabledReason && step.status !== "locked")),
    action_disabled_reason: disabledReason,
    is_current_step: step.is_current_step ?? step.isCurrent,
    short_reason: step.short_reason || step.description,
  };
}

function stepsFromStatus(status: SetupChecklistStatusPayload): SetupChecklistStep[] {
  const remoteSteps = status.steps || [];
  if (remoteSteps.length > 0) {
    return remoteSteps.map(normalizeRemoteStep);
  }
  return deriveSetupChecklist().map(normalizeFallbackStep);
}

function formatActionLabel(actionId: string) {
  return actionId.replace(/_/g, " ");
}

function latestRunFor(actionId: string, history: SetupActionRunPayload[]) {
  return history.find((item) => item.action_id === actionId);
}

function telemetryLabel(telemetry: SetupActionTelemetryPayload) {
  const action = telemetry.latest_action || "not run";
  const status = telemetry.latest_action_status || "not_run";
  return `${formatActionLabel(action)} / ${formatStatusLabel(status)}`;
}

function isLocalProviderStep(step?: SetupChecklistStep) {
  const id = step?.step_id || step?.id || "";
  return id === "configure_local_api_provider_credentials" || id === "configure_managed_proxy_endpoint_token" || id === "configure-local-api-provider" || id === "configure-managed-proxy";
}

export function GuidedSetupChecklist({ compact = false }: { compact?: boolean }) {
  const [status, setStatus] = useState<SetupChecklistStatusPayload>();
  const [runningAction, setRunningAction] = useState("");
  const [actionMessage, setActionMessage] = useState("");
  const [actionError, setActionError] = useState("");
  const steps = status ? stepsFromStatus(status) : deriveSetupChecklist().map(normalizeFallbackStep);
  const current = steps.find((step) => step.is_current_step || step.isCurrent) || steps[0];
  const setupActionTelemetry = status?.setup_action_telemetry || {};
  const setupActionHistory = status?.setup_action_history || [];

  useEffect(() => {
    let cancelled = false;
    void getSetupChecklistStatus()
      .then((payload) => {
        if (!cancelled) setStatus(payload);
      })
      .catch((error: unknown) => {
        if (!cancelled) setActionError(error instanceof Error ? error.message : "Setup checklist status unavailable");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleSafeAction(actionId: string) {
    setRunningAction(actionId);
    setActionError("");
    setActionMessage("");
    try {
      const result = await runSetupChecklistSafeAction({ action_id: actionId });
      if (result.checklist_status) {
        setStatus(result.checklist_status);
      } else {
        const latest = await getSetupChecklistStatus();
        setStatus(latest);
      }
      setActionMessage(`${formatActionLabel(actionId)} ${formatStatusLabel(result.status || "success")}`);
      window.dispatchEvent(new CustomEvent("setup-action-completed"));
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Safe action failed");
    } finally {
      setRunningAction("");
    }
  }

  return (
    <section aria-label="Setup Checklist" className={compact ? "guided-setup-checklist compact" : "guided-setup-checklist"}>
      <header>
        <div>
          <strong>Setup Checklist</strong>
          <span>Current step: {current.label ?? current.title}</span>
        </div>
        <em>{current.safe_action_id ?? current.safeAction}</em>
      </header>
      <NextActionStepper steps={steps} />
      {isLocalProviderStep(current) && <LocalApiProviderHandoffCard compact={compact} />}
      <div className="guided-setup-telemetry" aria-live="polite">
        <strong>Latest safe setup action</strong>
        <span>{telemetryLabel(setupActionTelemetry)}</span>
        <small>
          success {setupActionTelemetry.successful_action_count ?? 0} / failed {setupActionTelemetry.failed_action_count ?? 0} / blocked {setupActionTelemetry.blocked_action_count ?? 0}
        </small>
      </div>
      <div className="guided-setup-actions" aria-label="Safe setup actions">
        {steps.map((step, index) => {
          const actionId = step.safe_action_id || step.safeAction;
          const isRunning = runningAction === actionId;
          const disabledReason = step.action_disabled_reason || step.disabledReason || "Waiting for upstream setup evidence.";
          const reasonId = `setup-action-${index}-reason`;
          const latestRun = latestRunFor(actionId, setupActionHistory);
          return (
            <div className="guided-setup-action" key={`${step.step_id ?? step.id}-${actionId}`}>
              <button
                type="button"
                onClick={() => void handleSafeAction(actionId)}
                disabled={isRunning || !step.action_enabled}
                aria-label={`Run ${formatActionLabel(actionId)}`}
                aria-describedby={reasonId}
              >
                {isRunning ? "Running" : formatActionLabel(actionId)}
              </button>
              <small id={reasonId}>
                {step.action_enabled ? "Safe setup action; never trains, builds v12, publishes active, or generates prediction." : `Disabled reason: ${disabledReason}`}
              </small>
              <em>last run: {formatStatusLabel(latestRun?.status || "not_run")}</em>
            </div>
          );
        })}
      </div>
      <div className="guided-setup-history" aria-label="Safe setup action history" tabIndex={0}>
        <strong>Safe action history</strong>
        <ul>
          {setupActionHistory.slice(0, 4).map((item) => (
            <li key={item.run_id || `${item.action_id}-${item.finished_at}`}>
              <span>{formatActionLabel(item.action_id || "setup action")}</span>
              <em>{formatStatusLabel(item.status || "missing")}</em>
              <small>{item.duration_ms ?? 0}ms</small>
            </li>
          ))}
        </ul>
      </div>
      {actionMessage && <p role="status" className="guided-setup-action-status">{actionMessage}</p>}
      {actionError && <p role="status" className="guided-setup-action-error">{actionError}</p>}
      {!compact && <SafeConfigInstructions />}
    </section>
  );
}
