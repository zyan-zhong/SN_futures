import type { GovernanceAccessControlPayload, PredictionWorkspaceStatusPayload, ResearchDecisionBoardPayload } from "../api/types";
import { formatNextAction, formatStatusLabel } from "./statusTaxonomy";

export type WorkspaceGuardSource = Partial<PredictionWorkspaceStatusPayload & ResearchDecisionBoardPayload & GovernanceAccessControlPayload>;

export type WorkspaceGuardState = {
  workspace: string;
  current_state: string;
  next_allowed_action: string;
  prediction_generation_allowed: false;
  active_publish_allowed: false;
  no_active_confirmation: boolean;
  no_prediction_confirmation: boolean;
  forbidden_primary_actions: string[];
  safe_actions: string[];
  banner_title: string;
  banner_message: string;
};

const forbiddenPrimaryActions = [
  "generate customer prediction",
  "live prediction",
  "customer-visible output path",
  "active publish",
  "build Feature Store v12",
  "run candidate",
  "run promotion",
  "write active model"
];

const defaultSafeActions = [
  "read status",
  "refresh safe report",
  "copy summary",
  "open collapsed details",
  "download existing report"
];

function asString(value: unknown, fallback: string) {
  return typeof value === "string" && value.trim() ? value : fallback;
}

export function deriveWorkspaceCtaState(workspace: string, source: WorkspaceGuardSource = {}): WorkspaceGuardState {
  const currentState = asString(source.current_research_state, asString(source.status, "managed_data_blocked"));
  const nextAllowedAction = asString(source.next_allowed_action, "configure_managed_proxy_endpoint_or_token");
  const noActive = source.active_model_path_exists === undefined ? true : !source.active_model_path_exists;
  const noPrediction = source.customer_predictions_path_exists === undefined
    ? source.customer_prediction_generated !== true
    : !source.customer_predictions_path_exists && source.customer_prediction_generated !== true;

  return {
    workspace,
    current_state: currentState,
    next_allowed_action: nextAllowedAction,
    prediction_generation_allowed: false,
    active_publish_allowed: false,
    no_active_confirmation: noActive,
    no_prediction_confirmation: noPrediction,
    forbidden_primary_actions: forbiddenPrimaryActions,
    safe_actions: defaultSafeActions,
    banner_title: "Workspace guard",
    banner_message: deriveBlockedWorkspaceBanner(currentState, nextAllowedAction)
  };
}

export function deriveRouteAccessSummary(workspace: string, source: WorkspaceGuardSource = {}) {
  const guard = deriveWorkspaceCtaState(workspace, source);
  return {
    route: workspace,
    current_state: guard.current_state,
    next_allowed_action: guard.next_allowed_action,
    safe_read_allowed: true,
    safe_refresh_allowed: true,
    heavy_build_allowed: false,
    research_train_allowed: false,
    active_publish_allowed: false,
    customer_prediction_write_allowed: false
  };
}

export function deriveBlockedWorkspaceBanner(currentState = "managed_data_blocked", nextAllowedAction = "configure_managed_proxy_endpoint_or_token") {
  return `${formatStatusLabel(currentState)}；下一步：${formatNextAction(nextAllowedAction)}。预测生成、active 写入、v12 构建和 candidate run CTA 均保持受保护。`;
}

export function assertNoForbiddenPrimaryActions(actionLabels: string[] = []) {
  const normalized = actionLabels.map((label) => label.toLowerCase());
  const forbidden_actions_found = forbiddenPrimaryActions.filter((forbidden) => normalized.some((label) => label.includes(forbidden)));
  return {
    passed: forbidden_actions_found.length === 0,
    forbidden_actions_found,
    forbidden_primary_actions: forbiddenPrimaryActions
  };
}

export function groupSafeActionsByWorkspace(workspace: string) {
  return {
    workspace,
    allowed_safe_actions: defaultSafeActions,
    blocked_heavy_actions: ["build Feature Store v12", "build Training Dataset v12", "run candidate", "run promotion"],
    blocked_prediction_actions: ["generate customer prediction", "live prediction", "customer-visible output path"],
    blocked_active_actions: ["active publish", "write active model"]
  };
}
