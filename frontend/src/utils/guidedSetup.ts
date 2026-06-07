import { formatNextAction } from "./statusTaxonomy";

export type SetupStepStatus = "current" | "complete" | "blocked" | "available" | "locked" | "running" | "failed";

export type SetupChecklistStep = {
  id: string;
  step_id?: string;
  title: string;
  label?: string;
  description: string;
  status: SetupStepStatus;
  isCurrent: boolean;
  is_current_step?: boolean;
  safeAction: string;
  safe_action_id?: string;
  action_enabled?: boolean;
  action_disabled_reason?: string;
  short_reason?: string;
  evidence_path?: string;
  disabledReason?: string;
};

export type GuidedEmptyState = {
  title: string;
  summary: string;
  reasons: string[];
  nextAction: string;
  safeActions: string[];
  disabledActions: Array<{ label: string; reason: string }>;
};

const requiredSetupSteps: SetupChecklistStep[] = [
  {
    id: "configure-local-api-provider",
    title: "Configure Local API Provider credentials",
    description: "Use local shell or ignored local config only. Do not paste API keys into ChatGPT, Codex, commits, logs, issues, or screenshots.",
    status: "current",
    isCurrent: true,
    safeAction: "refresh_provider_credentials",
    safe_action_id: "refresh_provider_credentials",
    action_enabled: true,
  },
  {
    id: "operator-runbook",
    title: "Review setup runbook",
    description: "Read the local setup instructions and verify masked provider state before any endpoint request.",
    status: "available",
    isCurrent: false,
    safeAction: "refresh_operator_runbook",
    safe_action_id: "refresh_operator_runbook",
    action_enabled: true,
  },
  {
    id: "provider-smoke",
    title: "Run Provider Smoke Test",
    description: "Use a minimal provider request after credentials are configured. It never writes Feature Store, trains, publishes active, or generates prediction.",
    status: "locked",
    isCurrent: false,
    safeAction: "run_provider_smoke",
    safe_action_id: "run_provider_smoke",
    disabledReason: "Local API provider credentials are not configured.",
  },
  {
    id: "schema-sample-fixture",
    title: "Run Schema Mapping / Sample Fixture Contract",
    description: "A sample fixture can validate contracts, but sample evidence cannot unlock v12 production readiness.",
    status: "available",
    isCurrent: false,
    safeAction: "run_sample_fixture_contract",
    safe_action_id: "run_sample_fixture_contract",
    action_enabled: true,
  },
  {
    id: "pit-audit",
    title: "Run PIT Replay / PIT Audit",
    description: "Only real provider rows can validate source/as-of/cutoff semantics for no-lookahead joins.",
    status: "locked",
    isCurrent: false,
    safeAction: "run_pit_replay",
    safe_action_id: "run_pit_replay",
    disabledReason: "Real provider rows and timestamp evidence are not available yet.",
  },
  {
    id: "data-quality",
    title: "Run Data Quality",
    description: "Check missing rates, duplicate keys, invalid inventory/open interest, basis outliers, and contract switch anomalies.",
    status: "locked",
    isCurrent: false,
    safeAction: "refresh_data_quality",
    safe_action_id: "refresh_data_quality",
    disabledReason: "PIT audit and real provider rows have not passed.",
  },
  {
    id: "v12-input-controlled-build",
    title: "Review v12 input contract / controlled build plan",
    description: "v12 input and controlled build are later gated steps. This checklist never builds v12 by itself.",
    status: "locked",
    isCurrent: false,
    safeAction: "refresh_decision_board",
    safe_action_id: "refresh_decision_board",
    disabledReason: "Upstream provider data, PIT, quality, and local cache gates are incomplete.",
  },
];

export function deriveSetupChecklist() {
  return requiredSetupSteps;
}

export function deriveSafeConfigSteps() {
  return [
    "Only set API keys in your local shell or ignored local config.",
    "Do not paste API keys into ChatGPT.",
    "Do not paste API keys into Codex.",
    "Do not write API keys into commits, issues, logs, screenshots, or reports.",
    "After configuration, refresh read-only status, run provider smoke, then continue with schema, PIT, and data quality checks.",
  ];
}

export function deriveBlockedPredictionExplanation(nextAllowedAction = "configure_local_api_provider_credentials") {
  return {
    title: "暂无真实预测",
    summary: "数据源未配置或真实数据水位未通过，预测已阻断。The system will not generate customer predictions and will not write an active model. 研究参考，不构成投资建议。",
    reasons: [
      "No active model exists.",
      "No customer prediction exists.",
      "Local API provider credentials are not configured.",
      "Feature Store v12 has not been built.",
      "No candidate has passed all gates.",
    ],
    nextAction: formatNextAction(nextAllowedAction),
    safeActions: ["View safe config instructions", "Refresh read-only status", "Run sample fixture contract"],
    disabledActions: [
      { label: "Generate prediction", reason: "Disabled because prediction_generation_allowed=false and no active model exists." },
      { label: "Publish active", reason: "Disabled because manual approval, registry safety, and cutover gates have not passed." },
      { label: "Train candidate", reason: "Disabled because Feature Store / Training Dataset v12 are not ready." },
      { label: "Build v12", reason: "Disabled because provider credentials, PIT, quality, and cache gates are incomplete." },
    ],
  };
}

export function deriveGuidedEmptyState(nextAllowedAction = "configure_local_api_provider_credentials"): GuidedEmptyState {
  return deriveBlockedPredictionExplanation(nextAllowedAction);
}
