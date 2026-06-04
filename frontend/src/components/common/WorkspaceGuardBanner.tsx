import type { WorkspaceGuardSource } from "../../utils/workspaceGuards";
import { deriveWorkspaceCtaState } from "../../utils/workspaceGuards";
import { formatBooleanFlag, formatRawStatusLabel, formatWorkspaceFieldLabel } from "../../utils/copySystem";
import { formatNextAction, formatStatusLabel, getStatusDescription } from "../../utils/statusTaxonomy";

export function WorkspaceGuardBanner({
  workspace,
  source
}: {
  workspace: string;
  source?: WorkspaceGuardSource;
}) {
  const guard = deriveWorkspaceCtaState(workspace, source);

  return (
    <section
      aria-label={`${workspace} workspace guard`}
      aria-live="polite"
      className="workspace-guard-banner"
      role="status"
    >
      <div>
        <span>{formatWorkspaceFieldLabel("current_state")}</span>
        <strong>{formatStatusLabel(guard.current_state)}</strong>
        <em>{getStatusDescription(guard.current_state)}</em>
      </div>
      <div>
        <span>{formatWorkspaceFieldLabel("next_allowed_action")}</span>
        <strong>{formatNextAction(guard.next_allowed_action)}</strong>
      </div>
      <div>
        <span>{formatWorkspaceFieldLabel("prediction_generation_allowed")}</span>
        <strong>{formatBooleanFlag(guard.prediction_generation_allowed)}</strong>
      </div>
      <div>
        <span>{formatWorkspaceFieldLabel("active_publish_allowed")}</span>
        <strong>{formatBooleanFlag(guard.active_publish_allowed)}</strong>
      </div>
      <div data-audit-label="no-active confirmation">
        <span>无 active 确认</span>
        <strong>{formatBooleanFlag(guard.no_active_confirmation)}</strong>
      </div>
      <div data-audit-label="no-prediction confirmation">
        <span>无 customer prediction 确认</span>
        <strong>{formatBooleanFlag(guard.no_prediction_confirmation)}</strong>
      </div>
      <details aria-label="Raw status details" className="technical-details-drawer workspace-guard-banner__raw">
        <summary>Raw status</summary>
        <dl>
          <div>
            <dt>{formatRawStatusLabel("current_state")}</dt>
            <dd>{guard.current_state}</dd>
          </div>
          <div>
            <dt>{formatRawStatusLabel("next_allowed_action")}</dt>
            <dd>{guard.next_allowed_action}</dd>
          </div>
          <div>
            <dt>Raw status: prediction_generation_allowed</dt>
            <dd>{String(guard.prediction_generation_allowed)}</dd>
          </div>
          <div>
            <dt>Raw status: active_publish_allowed</dt>
            <dd>{String(guard.active_publish_allowed)}</dd>
          </div>
        </dl>
      </details>
    </section>
  );
}
