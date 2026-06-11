import { expect, test, type Page, type Route } from "@playwright/test";

test.setTimeout(120_000);

type SmokeMode = "success" | "no_rows";
type RefreshMode = "success" | "blocked";
type MarketMode = "blocked" | "bars";
type ReportMode = "blocked" | "ready";

type MatrixState = {
  settingsConfigured: boolean;
  masked: string;
  readinessMode: "no-key" | "ready";
  smokeMode: SmokeMode;
  refreshMode: RefreshMode;
  marketMode: MarketMode;
  reportMode: ReportMode;
  taskPolls: number;
  savedBody?: unknown;
};

const RAW_SECRET = "super-secret-local-token";
const MASKED_SECRET = "lo****7890";

function createMatrixState(overrides: Partial<MatrixState> = {}): MatrixState {
  return {
    settingsConfigured: false,
    masked: "",
    readinessMode: "no-key",
    smokeMode: "success",
    refreshMode: "success",
    marketMode: "blocked",
    reportMode: "blocked",
    taskPolls: 0,
    ...overrides
  };
}

async function launchWithMocks(page: Page, state: MatrixState) {
  await page.addInitScript(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    window.localStorage.setItem("firstRunCompleted", "true");
    window.localStorage.removeItem("uiMode");
    window.localStorage.removeItem("SN_ENABLE_DEV_CONSOLE");
    window.localStorage.removeItem("sn_enable_dev_console");
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: {
        writeText: async (value: string) => {
          window.localStorage.setItem("publicTerminalCopiedDiagnostics", value);
        }
      }
    });
  });
  await installApiMocks(page, state);
  await page.goto("./");
}

async function launchWithDevMode(page: Page, state: MatrixState) {
  await page.addInitScript(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    window.localStorage.setItem("firstRunCompleted", "true");
    window.localStorage.setItem("SN_ENABLE_DEV_CONSOLE", "1");
    window.localStorage.setItem("uiMode", JSON.stringify("professional"));
  });
  await installApiMocks(page, state);
  await page.goto("./");
}

async function installApiMocks(page: Page, state: MatrixState) {
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    if (!path.startsWith("/api/")) return route.continue();

    if (path === "/api/terminal/snapshot-lite") {
      return json(route, {
        sample_mode: false,
        predictions: [],
        summary: {
          system_status: "no-key",
          current_signal: "no real prediction",
          data_quality_label: "insufficient data",
          last_update_time: "2026-06-10T10:00:00+08:00"
        },
        data_status: { sources: [] }
      });
    }
    if (path === "/api/terminal/task-notifications") {
      return json(route, {
        status: "success",
        toast_task: null,
        notification_center: { tasks: [], failed_tasks: [], active_tasks: [] }
      });
    }
    if (path === "/api/terminal/tasks/recent") return json(route, { tasks: [] });
    if (path === "/api/terminal/settings/status") return json(route, { configured: false, providers: {} });
    if (path === "/api/terminal/data-status") return json(route, { sources: [] });
    if (path === "/api/terminal/system-health") return json(route, { api_status: "ok", warnings: [] });

    if (path === "/api/public-terminal/readiness") return json(route, readinessPayload(state));
    if (path === "/api/public-terminal/prediction-status") return json(route, predictionStatusPayload(state));
    if (path === "/api/public-terminal/settings/status") {
      return json(route, {
        configured: state.settingsConfigured,
        masked: state.masked,
        sources: [{ id: "local_api_provider", label: "Local API Provider", configured: state.settingsConfigured, masked: state.masked }]
      });
    }
    if (path === "/api/public-terminal/settings/save") {
      state.savedBody = route.request().postDataJSON();
      state.settingsConfigured = true;
      state.masked = MASKED_SECRET;
      return json(route, { configured: true, masked: MASKED_SECRET, success: true });
    }
    if (path === "/api/public-terminal/settings/reset") {
      state.settingsConfigured = false;
      state.masked = "";
      return json(route, { configured: false, masked: "", success: true });
    }
    if (path === "/api/public-terminal/provider-smoke") {
      if (state.smokeMode === "success") {
        state.readinessMode = "ready";
        return json(route, {
          status: "success",
          row_count: 12,
          source_statuses: [{ provider: "local_api_provider", status: "success", row_count: 12 }],
          manifest: { provider_id: "local_api_provider", row_count: 12 },
          training_invoked: false,
          prediction_generated: false,
          backtest_invoked: false
        });
      }
      return json(route, {
        status: "blocked",
        error_code: "no_rows",
        row_count: 0,
        source_statuses: [{ provider: "local_api_provider", status: "blocked", error_code: "no_rows" }],
        manifest: { provider_id: "local_api_provider", row_count: 0 },
        blocking_reasons: ["no_rows"],
        training_invoked: false,
        prediction_generated: false,
        backtest_invoked: false
      });
    }
    if (path === "/api/public-terminal/refresh-data-status") {
      state.taskPolls = 0;
      if (state.refreshMode === "blocked") {
        return json(route, { task_id: "matrix-refresh-blocked", status: "queued" }, 202);
      }
      return json(route, { task_id: "matrix-refresh-success", status: "queued" }, 202);
    }
    if (path === "/api/public-terminal/tasks/matrix-refresh-success") {
      state.taskPolls += 1;
      if (state.taskPolls < 2) return json(route, { task_id: "matrix-refresh-success", status: "running", progress: 50 });
      state.readinessMode = "ready";
      return json(route, {
        task_id: "matrix-refresh-success",
        status: "success",
        progress: 100,
        result: { data_watermark_updated: true },
        training_invoked: false,
        prediction_generated: false,
        backtest_invoked: false
      });
    }
    if (path === "/api/public-terminal/tasks/matrix-refresh-blocked") {
      state.taskPolls += 1;
      return json(route, {
        task_id: "matrix-refresh-blocked",
        status: "blocked",
        reason: "no_active_provider_smoke_pass",
        missing_data: ["daily_bars"],
        training_invoked: false,
        prediction_generated: false,
        backtest_invoked: false
      });
    }
    if (path === "/api/public-terminal/market") {
      if (state.marketMode === "bars") {
        return json(route, {
          market: {
            status: "success",
            reason: "",
            chart: [
              { date: "2026-06-01", close: 250000 },
              { date: "2026-06-02", close: 251200 },
              { date: "2026-06-03", close: 249500 },
              { date: "2026-06-04", close: 252100 }
            ],
            latest_quote: { price: 252300, time: "2026-06-10T10:00:00+08:00" },
            sample_data_used: false,
            baseline_used: false,
            customer_prediction_generated: false
          }
        });
      }
      return json(route, {
        market: {
          status: "blocked",
          reason: "missing_daily_bars",
          chart: [],
          latest_quote: null,
          sample_data_used: false,
          baseline_used: false,
          customer_prediction_generated: false
        }
      });
    }
    if (path === "/api/public-terminal/report") {
      if (state.reportMode === "ready") {
        return json(route, {
          report: {
            status: "ready",
            reason: "",
            provider_status: "success",
            market_data_coverage: "daily_bars_available",
            event_coverage: "policy_rss_available",
            research_only: true,
            investment_advice: false,
            export_allowed: true
          }
        });
      }
      return json(route, {
        report: {
          status: "blocked",
          reason: "insufficient_data",
          provider_status: "not_configured",
          market_data_coverage: "empty",
          event_coverage: "empty",
          research_only: true,
          investment_advice: false,
          export_allowed: false
        }
      });
    }

    return json(route, { status: "mocked", path });
  });
}

function readinessPayload(state: MatrixState) {
  if (state.readinessMode === "ready") {
    return {
      status: "ready",
      summary: "ready for refresh",
      next_action: "refresh_data_status",
      provider_smoke_passed: true,
      ready_for_refresh: true,
      blocking_reasons: [],
      data_watermark: { status: "ready", reason: "", sample_data_used: false, baseline_used: false, customer_prediction_generated: false }
    };
  }
  return {
    status: "blocked",
    summary: "provider keys missing",
    next_action: "open_setup",
    provider_smoke_passed: false,
    ready_for_refresh: false,
    blocking_reasons: ["provider_keys_missing"],
    data_watermark: {
      status: "blocked",
      reason: "missing_daily_bars",
      sample_data_used: false,
      baseline_used: false,
      customer_prediction_generated: false
    }
  };
}

function predictionStatusPayload(state: MatrixState) {
  const ready = state.readinessMode === "ready";
  return {
    prediction_status: {
      status: ready ? "ready_to_predict" : "blocked",
      dry_run: true,
      can_predict: ready,
      reason: ready ? "" : "missing_daily_bars",
      blocking_reasons: ready ? [] : ["missing_daily_bars"],
      training_invoked: false,
      prediction_generated: false,
      backtest_invoked: false,
      customer_prediction_generated: false
    },
    training_invoked: false,
    prediction_generated: false,
    backtest_invoked: false,
    customer_prediction_generated: false
  };
}

async function json(route: Route, body: unknown, status = 200) {
  await route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
}

async function gotoPublic(page: Page, label: "Home" | "Setup" | "Data Status" | "Market" | "Reports" | "Diagnostics") {
  await page.getByRole("button", { name: new RegExp(`^${label}`, "i") }).click();
}

async function mainText(page: Page) {
  return page.locator("main").innerText();
}

async function assertPublicSafety(page: Page) {
  const text = await page.locator("body").innerText();
  expect(text).not.toContain(RAW_SECRET);
  expect(text).not.toMatch(/\b(buy|sell)\b/i);
  expect(text).not.toMatch(/sample prediction|fake prediction/i);
  await expect(page.locator(".prediction-card")).toHaveCount(0);
}

test("public functional matrix covers no-key home, setup save, smoke success, refresh success, market bars, reports ready, and diagnostics copy", async ({ page }) => {
  const state = createMatrixState({ marketMode: "bars", reportMode: "ready" });
  await launchWithMocks(page, state);

  await expect(page.locator("[data-testid='simple-nav']")).toBeVisible();
  await expect(page.locator(".sidebar .nav-item")).toHaveCount(7);
  await expect(page.locator("[data-testid='professional-nav']")).toHaveCount(0);
  for (const forbidden of ["Candidate Research", "Governance Console", "Training Data", "Feature Store", "Managed Proxy"]) {
    await expect(page.getByText(forbidden)).toHaveCount(0);
  }
  await expect(page.locator("main .metric-card").first()).toBeVisible();
  expect(await mainText(page)).toContain("Setup");

  await gotoPublic(page, "Setup");
  await page.locator("main input[type='url']").fill("http://127.0.0.1:9999/mock-provider");
  await page.locator("main input[type='password']").fill(RAW_SECRET);
  await page.locator("main button.primary-button").click();
  await expect(page.locator("main")).toContainText(MASKED_SECRET);
  await expect(page.locator("main")).not.toContainText(RAW_SECRET);
  expect(state.savedBody).toMatchObject({ provider: "local_api_provider" });

  await page.locator("main button.secondary-button").click();
  await expect(page.locator("main")).toContainText(MASKED_SECRET);
  await page.locator("main details summary").click();
  await expect(page.locator("main pre.diagnostics-pre")).toContainText('"row_count": 12');
  await assertPublicSafety(page);

  await gotoPublic(page, "Data Status");
  await page.locator("main button.primary-button").click();
  await expect(page.locator("main pre.diagnostics-pre")).toContainText('"status": "success"', { timeout: 8_000 });
  await expect(page.locator("main pre.diagnostics-pre")).toContainText('"data_watermark_updated": true');

  await gotoPublic(page, "Market");
  await expect(page.locator("main .simple-chart")).toBeVisible();
  await expect(page.locator("main .simple-chart span")).toHaveCount(4);
  await expect(page.locator("main canvas")).toHaveCount(0);

  await gotoPublic(page, "Reports");
  const exportButton = page.locator("main button.primary-button");
  await expect(exportButton).toBeEnabled();
  await exportButton.click();
  await expect(page.locator("main [role='status']")).toContainText(/export|导出|瀵煎嚭/i);
  await assertPublicSafety(page);

  await gotoPublic(page, "Diagnostics");
  await page.locator("main button.primary-button").click();
  await page.locator("main button.secondary-button").click();
  await expect(page.locator("main [role='status']")).toBeVisible();
  const copied = await page.evaluate(() => window.localStorage.getItem("publicTerminalCopiedDiagnostics") || "");
  expect(copied).toContain("readiness");
  expect(copied).not.toContain(RAW_SECRET);
});

test("public functional matrix covers smoke no_rows, refresh blocked, market blocked, reports insufficient data, and safety copy", async ({ page }) => {
  const state = createMatrixState({ smokeMode: "no_rows", refreshMode: "blocked", marketMode: "blocked", reportMode: "blocked" });
  await launchWithMocks(page, state);

  await gotoPublic(page, "Setup");
  await page.locator("main button.secondary-button").click();
  await page.locator("main details summary").click();
  await expect(page.locator("main pre.diagnostics-pre")).toContainText('"error_code": "no_rows"');
  await expect(page.locator("main pre.diagnostics-pre")).toContainText('"row_count": 0');

  await gotoPublic(page, "Data Status");
  await page.locator("main button.primary-button").click();
  await expect(page.locator("main pre.diagnostics-pre")).toContainText('"status": "blocked"', { timeout: 8_000 });
  await expect(page.locator("main pre.diagnostics-pre")).toContainText('"reason": "no_active_provider_smoke_pass"');

  await gotoPublic(page, "Market");
  await expect(page.locator("main .simple-chart")).toHaveCount(0);
  await expect(page.locator("main canvas")).toHaveCount(0);
  await expect(page.locator("main")).toContainText("0");

  await gotoPublic(page, "Reports");
  await expect(page.locator("main button.primary-button")).toBeDisabled();
  await expect(page.locator("main")).toContainText(/暂无|鏆傛棤|no real/i);

  await assertPublicSafety(page);
});

test("dev mode remains hidden by default and only explicit dev flag shows legacy entries", async ({ page }) => {
  await launchWithMocks(page, createMatrixState());
  await expect(page.locator("[data-testid='simple-nav']")).toBeVisible();
  await expect(page.locator("[data-testid='professional-nav']")).toHaveCount(0);
  for (const label of ["Candidate Research", "Governance Console", "Training Data", "Feature Store", "Managed Proxy"]) {
    await expect(page.getByText(label)).toHaveCount(0);
  }

  const devPage = await page.context().newPage();
  await launchWithDevMode(devPage, createMatrixState());
  await expect(devPage.locator("[data-testid='professional-nav']")).toBeVisible();
  for (const label of ["Candidate Research", "Training Data", "Feature Store", "Backtest Validation", "Managed Proxy"]) {
    await expect(devPage.getByText(label).first()).toBeVisible();
  }
});
