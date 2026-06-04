import { expect, test, type Page } from "@playwright/test";

test.setTimeout(120_000);

const forbiddenPosts = [
  "/api/terminal/models/candidate",
  "/api/terminal/promotion",
  "/api/terminal/active",
  "/api/terminal/predictions"
];

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    window.localStorage.setItem("firstRunCompleted", "true");
    window.localStorage.setItem("showSampleData", "true");
    window.localStorage.setItem("uiMode", JSON.stringify("professional"));
  });
  await installWorkspaceMocks(page);
});

function setupChecklistPayload(sampleFixtureRan = false) {
  const telemetry = {
    status: "ready",
    latest_action: sampleFixtureRan ? "run_sample_fixture_contract" : "",
    latest_action_status: sampleFixtureRan ? "success" : "not_run",
    successful_action_count: sampleFixtureRan ? 1 : 0,
    failed_action_count: 0,
    blocked_action_count: 0,
    current_step: "configure_local_api_provider_credentials",
    recommended_next_action: "configure_local_api_provider_credentials",
    feature_store_v12_allowed: false,
    is_prediction_failure: false,
    training_invoked: false,
    active_updated: false,
    customer_prediction_generated: false
  };
  const history = sampleFixtureRan ? [{
    run_id: "setup-action-sample-fixture",
    action_id: "run_sample_fixture_contract",
    action_label: "Run Sample Fixture Contract",
    duration_ms: 12,
    status: "success",
    run_type: "safe_setup_action",
    action_scope: "setup_checklist",
    blocking_reasons: [],
    training_invoked: false,
    active_updated: false,
    customer_prediction_generated: false
  }] : [];
  return {
    status: "blocked",
    current_step: "configure_local_api_provider_credentials",
    prediction_generation_allowed: false,
    feature_store_v12_allowed: false,
    provider_mode: "local_api_provider",
    enabled_safe_actions: ["refresh_provider_credentials", "refresh_operator_runbook", "run_sample_fixture_contract", "refresh_schema_mapping"],
    locked_steps: ["run_provider_smoke", "run_pit_replay", "run_pit_audit", "refresh_data_quality", "review_v12_input_contract"],
    steps: [
      {
        step_id: "configure_local_api_provider_credentials",
        label: "Configure Local API Provider credentials",
        status: "available",
        short_reason: "configure local API provider credentials",
        safe_action_id: "refresh_provider_credentials",
        action_enabled: true,
        action_disabled_reason: "",
        evidence_path: "outputs/diagnostics/managed_proxy_operator_runbook_report.json",
        is_current_step: true
      },
      {
        step_id: "verify_operator_runbook",
        label: "Operator Runbook / Setup Verification",
        status: "available",
        short_reason: "operator runbook can be refreshed safely",
        safe_action_id: "refresh_operator_runbook",
        action_enabled: true,
        action_disabled_reason: "",
        evidence_path: "outputs/diagnostics/managed_proxy_operator_runbook_report.json",
        is_current_step: false
      },
      {
        step_id: "run_provider_smoke",
        label: "Provider Smoke Test",
        status: "locked",
        short_reason: "provider smoke requires configured local API provider key",
        safe_action_id: "run_provider_smoke",
        action_enabled: false,
        action_disabled_reason: "Local API provider credentials are not configured.",
        evidence_path: "outputs/diagnostics/managed_proxy_endpoint_smoke_report.json",
        is_current_step: false
      },
      {
        step_id: "run_sample_fixture_contract",
        label: "Schema Mapping / Sample Fixture Contract",
        status: sampleFixtureRan ? "complete" : "available",
        short_reason: "sample fixture contract is safe and cannot unlock v12",
        safe_action_id: "run_sample_fixture_contract",
        action_enabled: true,
        action_disabled_reason: "",
        evidence_path: "outputs/diagnostics/managed_proxy_sample_fixture_contract_report.json",
        is_current_step: false
      },
      {
        step_id: "refresh_schema_mapping",
        label: "Schema Mapping",
        status: "available",
        short_reason: "schema mapping report is safe to refresh",
        safe_action_id: "refresh_schema_mapping",
        action_enabled: true,
        action_disabled_reason: "",
        evidence_path: "outputs/diagnostics/managed_proxy_schema_mapping_report.json",
        is_current_step: false
      },
      {
        step_id: "run_pit_replay",
        label: "PIT Replay / PIT Audit",
        status: "locked",
        short_reason: "PIT replay requires real managed rows",
        safe_action_id: "run_pit_replay",
        action_enabled: false,
        action_disabled_reason: "Real managed endpoint data is not available yet.",
        evidence_path: "",
        is_current_step: false
      },
      {
        step_id: "run_pit_audit",
        label: "PIT Audit",
        status: "locked",
        short_reason: "PIT audit requires PIT replay evidence",
        safe_action_id: "run_pit_audit",
        action_enabled: false,
        action_disabled_reason: "Real managed endpoint data is not available yet.",
        evidence_path: "",
        is_current_step: false
      },
      {
        step_id: "refresh_data_quality",
        label: "Data Quality",
        status: "locked",
        short_reason: "data quality requires PIT-ready managed rows",
        safe_action_id: "refresh_data_quality",
        action_enabled: false,
        action_disabled_reason: "Real managed endpoint data is not available yet.",
        evidence_path: "",
        is_current_step: false
      },
      {
        step_id: "review_v12_input_contract",
        label: "v12 input / controlled build",
        status: "locked",
        short_reason: "v12 input contract is review-only here and never auto-builds v12",
        safe_action_id: "refresh_decision_board",
        action_enabled: false,
        action_disabled_reason: "Upstream managed data, PIT, quality, and production cache gates are not complete.",
        evidence_path: "",
        is_current_step: false
      }
    ],
    setup_action_telemetry: telemetry,
    setup_action_history: history,
    setup_action_history_count: history.length,
    training_invoked: false,
    active_updated: false,
    customer_prediction_generated: false
  };
}

function configHandoffPayload() {
  return {
    status: "missing_config",
    handoff_version: "managed_proxy_config_handoff_v1",
    current_step: "configure_managed_proxy_endpoint_token",
    endpoint_configured: false,
    token_configured: false,
    token_masked: "",
    enabled_configured: false,
    config_sources_detected: ["none"],
    env_alias_consistency: { status: "pass", configured_aliases: [], conflicts: [] },
    gitignore_secret_coverage: { status: "pass", missing_patterns: [], required_patterns: [".env.local", "config/managed_proxy.local.json"] },
    local_config_safety: { status: "pass", local_config_exists: false, env_local_exists: false },
    copy_safe_setup_commands: [
      '$env:SN_MANAGED_PROXY_ENABLED="true"',
      '$env:SN_MANAGED_PROXY_BASE_URL="https://your-managed-proxy.example.com"',
      '$env:SN_MANAGED_PROXY_TOKEN="<paste-token-only-in-your-local-shell>"'
    ],
    next_safe_actions_after_config: [
      "configure_managed_proxy_endpoint_or_token_locally",
      "refresh_config_handoff",
      "refresh_operator_runbook",
      "refresh_managed_proxy_setup",
      "run_endpoint_smoke"
    ],
    blocking_reasons: ["managed_proxy_endpoint_missing", "managed_proxy_token_missing"],
    warning_reasons: [],
    feature_store_v12_allowed: false,
    training_invoked: false,
    active_updated: false,
    customer_prediction_generated: false
  };
}

function providerCredentialsPayload() {
  return {
    status: "missing_config",
    credentials_version: "local_api_provider_credentials_v1",
    provider_mode: "local_api_provider",
    current_step: "configure_local_api_provider_credentials",
    provider_credentials_status: "missing_config",
    configured_providers: [],
    missing_provider_credentials: ["twelvedata", "alphavantage"],
    providers: {
      twelvedata: { provider_id: "twelvedata", key_configured: false, key_masked: "", research_only: false, production_eligible: true, realtime_guarantee: true, can_unlock_v12: true },
      alphavantage: { provider_id: "alphavantage", key_configured: false, key_masked: "", research_only: false, production_eligible: true, realtime_guarantee: false, can_unlock_v12: true },
      fred: { provider_id: "fred", key_configured: false, key_masked: "", research_only: false, production_eligible: true, realtime_guarantee: false, can_unlock_v12: true },
      yfinance_research_only: { provider_id: "yfinance_research_only", key_configured: false, key_masked: "", research_only: true, production_eligible: false, realtime_guarantee: false, can_unlock_v12: false }
    },
    copy_safe_setup_commands: [
      '$env:SN_DATA_PROVIDER_PRIMARY="twelvedata"',
      '$env:SN_TWELVEDATA_API_KEY="<paste-key-only-in-your-local-shell>"',
      '$env:SN_ALPHA_VANTAGE_API_KEY="<paste-key-only-in-your-local-shell>"',
      '$env:SN_FRED_API_KEY="<paste-key-only-in-your-local-shell>"'
    ],
    legacy_managed_proxy_status: { status: "not_configured", required_for_local_mode: false },
    blocking_reasons: ["provider_api_key_missing"],
    warning_reasons: [],
    feature_store_v12_allowed: false,
    training_invoked: false,
    active_updated: false,
    customer_prediction_generated: false
  };
}

function providerSmokePayload() {
  return {
    status: "blocked",
    provider: "twelvedata",
    provider_mode: "local_api_provider",
    auth_status: "blocked",
    endpoint_reachable: false,
    field_coverage: { fields_seen: [], missing_canonical_fields: [] },
    freshness_status: "not_run",
    feature_store_v12_allowed: false,
    feature_store_written: false,
    production_cache_written: false,
    training_invoked: false,
    active_updated: false,
    customer_prediction_generated: false,
    blocking_reasons: ["provider_key_missing"]
  };
}

function localApiProviderHubPayload() {
  return {
    status: "blocked",
    hub_version: "local_api_provider_hub_v1",
    provider_mode: "local_api_provider",
    current_step: "configure_local_api_provider_credentials",
    provider_credentials_status: "missing_config",
    configured_providers: [],
    missing_provider_credentials: ["twelvedata", "alphavantage"],
    managed_proxy_required: false,
    legacy_managed_proxy_status: { status: "not_configured", required_for_local_mode: false },
    yfinance_research_only: { research_only: true, production_eligible: false, realtime_guarantee: false, can_unlock_v12: false },
    provider_smoke_status: "blocked",
    provider_smoke: providerSmokePayload(),
    provider_credentials: providerCredentialsPayload(),
    next_allowed_action: "configure_local_api_provider_credentials",
    feature_store_v12_allowed: false,
    training_invoked: false,
    active_updated: false,
    customer_prediction_generated: false
  };
}

function taskNotificationsPayload(sampleFixtureRan = false) {
  const setupActionHistory = {
    status: "ready",
    latest_action: sampleFixtureRan ? "run_sample_fixture_contract" : "",
    latest_action_status: sampleFixtureRan ? "success" : "not_run",
    successful_action_count: sampleFixtureRan ? 1 : 0,
    failed_action_count: 0,
    blocked_action_count: 0,
    current_step: "configure_managed_proxy_endpoint_token",
    recommended_next_action: "configure_managed_proxy_endpoint_or_token",
    feature_store_v12_allowed: false,
    is_prediction_failure: false,
    training_invoked: false,
    active_updated: false,
    customer_prediction_generated: false
  };
  return {
    status: "success",
    toast_task: null,
    stale_failure_suppressed: true,
    latest_failed_task: {
      task_id: "old-train-candidate",
      kind: "research task",
      status: "failed",
      error_message_zh: "train_candidate failed"
    },
    setup_action_history: setupActionHistory,
    notification_center: {
      title: "Task Notification Center",
      active_tasks: [],
      failed_tasks: [{ task_id: "old-train-candidate", kind: "research task", status: "failed" }],
      tasks: [{ task_id: "old-train-candidate", kind: "research task", status: "failed" }],
      setup_action_history: setupActionHistory
    }
  };
}

async function installWorkspaceMocks(page: Page) {
  let sampleFixtureRan = false;
  await page.route("**/api/terminal/snapshot-lite", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        summary: { main_contract: "SN0", system_status: "blocked", current_signal: "watch" },
        predictions: [],
        sample_mode: false
      })
    });
  });
  await page.route("**/api/terminal/task-notifications**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(taskNotificationsPayload(sampleFixtureRan))
    });
  });
  await page.route("**/api/terminal/research/decision-board", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        status: "blocked",
        current_research_state: "managed_data_blocked",
        next_allowed_action: "configure_managed_proxy_endpoint_or_token",
        active_publish_allowed: false,
        customer_prediction_generated: false,
        managed_proxy_summary: { status: "blocked" },
        feature_store_v12_summary: { status: "blocked" },
        training_dataset_v12_summary: { status: "blocked" },
        blocking_reasons: ["managed_proxy_endpoint_or_token_missing"]
      })
    });
  });
  await page.route("**/api/terminal/prediction-workspace/status", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        status: "blocked",
        current_research_state: "managed_data_blocked",
        prediction_status: "blocked",
        prediction_generation_allowed: false,
        active_model_available: false,
        customer_prediction_generated: false,
        active_model_path_exists: false,
        customer_predictions_path_exists: false,
        next_allowed_action: "configure_managed_proxy_endpoint_or_token",
        required_gates: ["active_model", "manual_approval", "shadow_mode"],
        blocking_reasons: ["no active model", "managed proxy blocked"],
        evidence_paths: { decision_board: "outputs/governance/research_decision_board.json" }
      })
    });
  });
  await page.route("**/api/terminal/setup-checklist/status", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(setupChecklistPayload(sampleFixtureRan))
    });
  });
  await page.route("**/api/terminal/local-api-provider/hub", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(localApiProviderHubPayload())
    });
  });
  await page.route("**/api/terminal/local-api-provider/credentials", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(providerCredentialsPayload())
    });
  });
  await page.route("**/api/terminal/local-api-provider/refresh-credentials", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(providerCredentialsPayload())
    });
  });
  await page.route("**/api/terminal/local-api-provider/smoke", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(providerSmokePayload())
    });
  });
  await page.route("**/api/terminal/local-api-provider/run-smoke", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(providerSmokePayload())
    });
  });
  await page.route("**/api/terminal/managed-proxy/config-handoff", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(configHandoffPayload())
    });
  });
  await page.route("**/api/terminal/managed-proxy/refresh-config-handoff", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(configHandoffPayload())
    });
  });
  await page.route("**/api/terminal/setup-checklist/run-safe-action", async (route) => {
    const action = route.request().postDataJSON() as { action_id?: string };
    if (action.action_id === "run_sample_fixture_contract") sampleFixtureRan = true;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        status: "success",
        action_id: action.action_id,
        action_result: {
          status: action.action_id === "run_sample_fixture_contract" ? "ready" : "blocked",
          feature_store_v12_allowed: false,
          customer_prediction_generated: false
        },
        checklist_status: setupChecklistPayload(sampleFixtureRan),
        training_invoked: false,
        active_updated: false,
        customer_prediction_generated: false
      })
    });
  });
  await page.route("**/api/terminal/candidate-v10/research", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ status: "research_only", promotion_dry_run: { status: "blocked" } }) });
  });
  await page.route("**/api/terminal/models/candidate-v12/research", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ status: "blocked", reason_zh: "v12 not ready" }) });
  });
  await page.route("**/api/terminal/**", async (route) => {
    const request = route.request();
    if (request.url().includes("/api/terminal/setup-checklist/status")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(setupChecklistPayload(sampleFixtureRan))
      });
      return;
    }
    if (request.url().includes("/api/terminal/setup-checklist/run-safe-action")) {
      const action = request.postDataJSON() as { action_id?: string };
      if (action.action_id === "run_sample_fixture_contract") sampleFixtureRan = true;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          status: "success",
          action_id: action.action_id,
          action_result: {
            status: action.action_id === "run_sample_fixture_contract" ? "ready" : "blocked",
            feature_store_v12_allowed: false,
            customer_prediction_generated: false
          },
          checklist_status: setupChecklistPayload(sampleFixtureRan),
          training_invoked: false,
          active_updated: false,
          customer_prediction_generated: false
        })
      });
      return;
    }
    if (request.url().includes("/api/terminal/local-api-provider/hub")) {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(localApiProviderHubPayload()) });
      return;
    }
    if (request.url().includes("/api/terminal/local-api-provider/credentials") || request.url().includes("/api/terminal/local-api-provider/refresh-credentials")) {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(providerCredentialsPayload()) });
      return;
    }
    if (request.url().includes("/api/terminal/local-api-provider/smoke") || request.url().includes("/api/terminal/local-api-provider/run-smoke")) {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(providerSmokePayload()) });
      return;
    }
    if (request.url().includes("/api/terminal/task-notifications")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(taskNotificationsPayload(sampleFixtureRan))
      });
      return;
    }
    if (request.url().includes("/api/terminal/managed-proxy/config-handoff")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(configHandoffPayload())
      });
      return;
    }
    if (request.url().includes("/api/terminal/managed-proxy/refresh-config-handoff")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(configHandoffPayload())
      });
      return;
    }
    if (request.method() === "POST") {
      await route.fulfill({ status: 405, contentType: "application/json", body: JSON.stringify({ status: "forbidden" }) });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        status: "blocked",
        next_allowed_action: "configure_local_api_provider_credentials",
        blocking_reasons: ["provider api key missing"],
        active_updated: false,
        customer_prediction_generated: false
      })
    });
  });
}

async function openByNavText(page: Page, label: RegExp) {
  const button = page.getByRole("button", { name: label }).first();
  await expect(button).toBeVisible();
  await button.click();
  await expect(button).toHaveClass(/active/, { timeout: 5_000 });
  await expect(page.locator(".error-boundary")).toHaveCount(0);
}

async function openByKeyboardNavText(page: Page, label: RegExp) {
  const button = page.getByRole("button", { name: label }).first();
  await expect(button).toBeVisible();
  await button.focus();
  await expect(button).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(button).toHaveClass(/active/, { timeout: 5_000 });
  await expect(page.locator(".error-boundary")).toHaveCount(0);
}

async function expectWorkspaceGuard(page: Page) {
  const guard = page.locator(".workspace-guard-banner").first();
  await expect(guard).toBeVisible();
  await expect(guard).toContainText("当前状态");
  await expect(guard).toContainText("下一步允许动作");
  await expect(guard).toContainText("预测生成权限");
  await expect(guard).toContainText("Active 发布权限");
  await expect(guard).toContainText("否");
  await expect(guard).toContainText("无 active 确认");
  await expect(guard).toContainText("无 customer prediction 确认");
  const primaryText = await guard.innerText();
  expect(primaryText).not.toContain("current_state");
  expect(primaryText).not.toContain("next_allowed_action");
  expect(primaryText).not.toContain("prediction_generation_allowed=false");
  expect(primaryText).not.toContain("active_publish_allowed=false");
}

async function expectNoForbiddenPrimaryButtons(page: Page) {
  await expect(page.getByRole("button", { name: /generate customer prediction|live prediction|customer-visible output path/i })).toHaveCount(0);
  await expect(page.getByRole("button", { name: /publish active|active publish|write active/i })).toHaveCount(0);
}

async function expectNoRawTokenInput(page: Page) {
  await expect(page.locator('input[name*="token" i]')).toHaveCount(0);
  await expect(page.locator('textarea[name*="token" i]')).toHaveCount(0);
  await expect(page.getByLabel(/token/i)).toHaveCount(0);
}

test("split terminal workspaces are navigable and keep blocked prediction read-only", async ({ page }) => {
  const postCalls: string[] = [];
  page.on("request", (request) => {
    if (request.method() === "POST") postCalls.push(new URL(request.url()).pathname);
  });

  await page.goto("./");
  await openByNavText(page, /Terminal Overview/);
  await expectWorkspaceGuard(page);
  await expectNoForbiddenPrimaryButtons(page);
  await expect(page.getByRole("heading", { name: "Current State" })).toBeVisible();
  await expect(page.locator("body")).toContainText("Configure Local API Provider credentials");
  await expect(page.locator("body")).not.toContainText("candidate_v3");

  await openByNavText(page, /Prediction Workspace/);
  await expectWorkspaceGuard(page);
  await expectNoForbiddenPrimaryButtons(page);
  await expect(page.getByRole("heading", { name: "Prediction Workspace" })).toBeVisible();
  await expect(page.locator("body")).toContainText("预测生成权限");
  await expect(page.locator("body")).toContainText("customer_predictions 不存在");

  await openByNavText(page, /Data Onboarding/);
  await expectWorkspaceGuard(page);
  await expectNoForbiddenPrimaryButtons(page);
  await expect(page.getByText("Operator Runbook", { exact: true })).toBeVisible();
  await expect(page.getByText("Production Cache Gate", { exact: true })).toBeVisible();
  await expect(page.getByText("v12 Input Contract", { exact: true })).toBeVisible();
  await expect(page.getByText("Detailed data source cards", { exact: true })).toBeVisible();

  await openByNavText(page, /Candidate Research/);
  await expectWorkspaceGuard(page);
  await expectNoForbiddenPrimaryButtons(page);
  await expect(page.getByText("Candidate v12 current blocked summary")).toBeVisible();
  await expect(page.getByText("Candidate v10 research-only summary")).toBeVisible();

  await openByNavText(page, /Research Archive/);
  await expectWorkspaceGuard(page);
  await expectNoForbiddenPrimaryButtons(page);
  await expect(page.getByText("Research Archive").first()).toBeVisible();
  await expect(page.getByText("candidate_v3")).not.toBeVisible();
  await page.getByText("Archived Candidates").click();
  await expect(page.getByText("candidate_v3")).toBeVisible();
  await expect(page.getByRole("button", { name: /Run candidate_/ })).toHaveCount(0);

  await openByNavText(page, /Research Governance/);
  await expectWorkspaceGuard(page);
  await expectNoForbiddenPrimaryButtons(page);
  await expect(page.getByRole("heading", { name: "Governance Console" })).toBeVisible();
  await expect(page.locator("body")).toContainText("forbidden");

  expect(postCalls.filter((path) => forbiddenPosts.some((forbidden) => path.includes(forbidden)))).toEqual([]);
});

test("workspace navigation, archive details, and task center are keyboard operable", async ({ page }) => {
  await page.goto("./");
  await openByKeyboardNavText(page, /Prediction Workspace/);
  await expectWorkspaceGuard(page);

  await openByKeyboardNavText(page, /Research Archive/);
  const archiveSummary = page.locator('details[aria-label="Archived Candidates"] summary');
  await archiveSummary.focus();
  await expect(archiveSummary).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.getByText("candidate_v3")).toBeVisible();
  await page.keyboard.press("Enter");
  await expect(page.getByText("candidate_v3")).not.toBeVisible();

  const taskCenter = page.getByRole("button", { name: /Open Task Notification Center/ });
  await taskCenter.focus();
  await expect(taskCenter).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("#task-notification-center-drawer")).toContainText("Task Notification Center");
  await expect(page.getByRole("button", { name: /Close Task Notification Center/ })).toBeVisible();
  await page.keyboard.press("Enter");
  await expect(page.locator("#task-notification-center-drawer")).toHaveCount(0);
});

test("guided setup checklist and blocked empty states explain the safe first step", async ({ page }) => {
  await page.goto("./");
  await openByNavText(page, /Terminal Overview/);
  await expect(page.getByRole("region", { name: "Setup Checklist" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Local API Provider Handoff" }).first()).toBeVisible();
  await expect(page.getByText("$env:SN_TWELVEDATA_API_KEY=\"<paste-key-only-in-your-local-shell>\"").first()).toBeVisible();
  await expect(page.getByRole("button", { name: /Copy local API provider placeholder command/i }).first()).toBeVisible();
  await expect(page.getByText("Configure Local API Provider credentials").first()).toBeVisible();
  await expect(page.getByText("Do not paste API keys into ChatGPT").first()).toBeVisible();
  await expect(page.getByText("Do not paste API keys into Codex").first()).toBeVisible();
  const localCurrentStep = page.locator(".next-action-stepper li[aria-current='step']").first();
  await expect(localCurrentStep).toContainText("Configure Local API Provider credentials");
  await localCurrentStep.focus();
  await expect(localCurrentStep).toBeFocused();
  const sampleFixtureButtonForLocalProvider = page.getByRole("button", { name: /run sample fixture contract/i }).first();
  await sampleFixtureButtonForLocalProvider.focus();
  await expect(sampleFixtureButtonForLocalProvider).toBeFocused();
  await sampleFixtureButtonForLocalProvider.click();
  await expect(page.locator("body")).toContainText("run sample fixture contract");
  await expectNoRawTokenInput(page);
  await expectNoForbiddenPrimaryButtons(page);

  await openByNavText(page, /Prediction Workspace/);
  await expect(page.getByRole("region", { name: "Prediction blocked empty state" })).toBeVisible();
  await expect(page.getByText("Prediction is blocked").first()).toBeVisible();
  await expect(page.getByText("No active model exists.").first()).toBeVisible();
  await expect(page.getByText("Local API provider credentials are not configured.").first()).toBeVisible();
  await expectNoRawTokenInput(page);
  await expectNoForbiddenPrimaryButtons(page);

  await openByNavText(page, /Data Onboarding/);
  await expect(page.getByRole("region", { name: "Local API Provider Handoff" }).first()).toBeVisible();
  await expect(page.getByText("Local API Provider Hub").first()).toBeVisible();
  await expect(page.getByText("Provider / Endpoint Smoke").first()).toBeVisible();
  await expect(page.getByText("PIT Replay / PIT Audit").first()).toBeVisible();
  await expectNoRawTokenInput(page);
  await expectNoForbiddenPrimaryButtons(page);
  return;
  await expect(page.getByRole("region", { name: "Local API Provider Handoff" }).first()).toBeVisible();
  await expect(page.getByText("$env:SN_TWELVEDATA_API_KEY=\"<paste-key-only-in-your-local-shell>\"").first()).toBeVisible();
  await expect(page.getByRole("button", { name: /Copy local API provider placeholder command/i }).first()).toBeVisible();
  await expect(page.getByText("安全配置 Managed Proxy endpoint/token").first()).toBeVisible();
  await expect(page.getByText("不要把 token 粘贴到 ChatGPT").first()).toBeVisible();
  await expect(page.getByText("不要把 token 粘贴到 Codex").first()).toBeVisible();
  await expect(page.getByText("不要写入 commit").first()).toBeVisible();
  await expect(page.getByText("不要写入 log").first()).toBeVisible();
  const currentStep = page.locator(".next-action-stepper li[aria-current='step']").first();
  await expect(currentStep).toContainText("安全配置 Managed Proxy endpoint/token");
  await expect(currentStep).toHaveAttribute("data-status", "blocked");
  await currentStep.focus();
  await expect(currentStep).toBeFocused();
  const sampleFixtureButton = page.getByRole("button", { name: /run sample fixture contract/i }).first();
  await sampleFixtureButton.focus();
  await expect(sampleFixtureButton).toBeFocused();
  await sampleFixtureButton.click();
  await expect(page.locator("body")).toContainText("run sample fixture contract");
  const taskCenterButton = page.getByRole("button", { name: /Open Task Notification Center/ });
  await taskCenterButton.click();
  await expect(page.locator("#task-notification-center-drawer")).toContainText("safe setup action history");
  await expect(page.locator("#task-notification-center-drawer")).toContainText("run_sample_fixture_contract");
  await expect(page.locator("#task-notification-center-drawer")).not.toContainText("prediction failure");
  await page.getByRole("button", { name: /Close Task Notification Center/ }).click();
  await expect(page.getByRole("button", { name: /build feature store v12|train candidate|promote model|write active|generate customer prediction/i })).toHaveCount(0);
  await expectNoRawTokenInput(page);
  await expectNoForbiddenPrimaryButtons(page);

  await openByNavText(page, /Prediction Workspace/);
  await expect(page.getByRole("region", { name: "Prediction blocked empty state" })).toBeVisible();
  await expect(page.getByText("当前不能预测").first()).toBeVisible();
  await expect(page.getByText("没有 active model").first()).toBeVisible();
  await expect(page.getByText("Managed Proxy 未配置").first()).toBeVisible();
  await expect(page.getByText("candidate 尚未通过").first()).toBeVisible();
  await expect(page.getByText("禁用原因").first()).toBeVisible();
  await expect(page.getByRole("button", { name: /run sample fixture contract/i }).first()).toBeVisible();
  await expectNoRawTokenInput(page);
  await expectNoForbiddenPrimaryButtons(page);

  await openByNavText(page, /Data Onboarding/);
  await expect(page.getByRole("region", { name: "Managed Proxy setup guidance" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Secure Configuration Handoff" }).first()).toBeVisible();
  await expect(page.getByText("PowerShell placeholder commands").first()).toBeVisible();
  await expect(page.getByText("$env:SN_MANAGED_PROXY_BASE_URL=\"https://your-managed-proxy.example.com\"").first()).toBeVisible();
  await page.getByRole("button", { name: /Refresh secure configuration handoff/i }).first().click();
  await openByNavText(page, /Prediction Workspace/);
  await expect(page.getByRole("region", { name: "Prediction blocked empty state" })).toBeVisible();
  await openByNavText(page, /Data Onboarding/);
  await expect(page.getByText("Managed Proxy 还没有完成配置").first()).toBeVisible();
  await expect(page.getByText("配置后点哪里验证").first()).toBeVisible();
  await expect(page.getByText("Endpoint Smoke Test").first()).toBeVisible();
  await expect(page.getByText("PIT Replay / PIT Audit").first()).toBeVisible();
  await expectNoRawTokenInput(page);
  await expectNoForbiddenPrimaryButtons(page);
});

test("safe refresh disabled state exposes an accessible disabled reason", async ({ page }) => {
  await page.route("**/api/terminal/research/run-safe-readiness-checks", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 750));
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        status: "blocked",
        next_allowed_action: "configure_managed_proxy_endpoint_or_token",
        training_invoked: false,
        active_updated: false,
        customer_prediction_generated: false
      })
    });
  });

  await page.goto("./");
  await openByNavText(page, /Research Governance/);
  const button = page.getByRole("button", { name: "Run safe checks" }).first();
  await button.click();
  await expect(button).toBeDisabled();
  const reasonId = await button.getAttribute("aria-describedby");
  expect(reasonId).toBeTruthy();
  await expect(page.locator(`#${reasonId}`)).toContainText("刷新安全报告");
});

test("stale train candidate failure stays in task history instead of persistent overlay", async ({ page }) => {
  await page.goto("./");
  await openByNavText(page, /Terminal Overview/);

  const summary = page.locator(".global-task-bar__summary");
  await expect(summary).toBeVisible();
  await expect(summary).not.toContainText("train_candidate failed");
  await summary.click();
  const drawer = page.locator(".global-task-bar__drawer");
  await expect(drawer).toContainText("Task Notification Center");
  await expect(drawer).toContainText("stale failure moved to history");
  await expect(drawer).toContainText("latest failed research task");
  await expect(drawer).toContainText("train_candidate failed");
});

test("workspace navigation remains safe on narrow viewport", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("./");
  await openByNavText(page, /Prediction Workspace/);
  await expectWorkspaceGuard(page);
  await expectNoForbiddenPrimaryButtons(page);
  await openByNavText(page, /Data Onboarding/);
  await expectWorkspaceGuard(page);
  const sizes = await page.evaluate(() => ({
    html: document.documentElement.scrollWidth,
    body: document.body.scrollWidth,
    width: window.innerWidth
  }));
  expect(sizes.html).toBeLessThanOrEqual(sizes.width + 2);
  expect(sizes.body).toBeLessThanOrEqual(sizes.width + 2);
});
