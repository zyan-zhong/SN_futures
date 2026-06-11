import { expect, test, type Page, type Route } from "@playwright/test";

test.setTimeout(120_000);

const RAW_SECRET = "acceptance-raw-secret";
const MASKED_SECRET = "ac****cret";

type AcceptanceState = {
  settingsConfigured: boolean;
  refreshPolls: number;
};

function createState(): AcceptanceState {
  return { settingsConfigured: false, refreshPolls: 0 };
}

async function json(route: Route, body: unknown, status = 200) {
  await route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
}

function predictionStatusPayload(canPredict = false) {
  return {
    prediction_status: {
      status: canPredict ? "ready_to_predict" : "blocked",
      dry_run: true,
      can_predict: canPredict,
      reason: canPredict ? "" : "active_model_missing",
      blocking_reasons: canPredict ? [] : ["active_model_missing"],
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

async function installAcceptanceMocks(page: Page, state: AcceptanceState) {
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (!path.startsWith("/api/")) return route.continue();

    if (path === "/api/terminal/snapshot-lite") {
      return json(route, { sample_mode: false, predictions: [], summary: { current_signal: "no real prediction" }, data_status: { sources: [] } });
    }
    if (path === "/api/terminal/task-notifications") return json(route, { status: "success", toast_task: null, notification_center: { tasks: [] } });
    if (path === "/api/terminal/tasks/recent") return json(route, { tasks: [] });
    if (path === "/api/terminal/settings/status") return json(route, { configured: false, providers: {} });
    if (path === "/api/terminal/data-status") return json(route, { sources: [] });
    if (path === "/api/terminal/system-health") return json(route, { api_status: "ok", warnings: [] });

    if (path === "/api/public-terminal/readiness") {
      return json(route, {
        status: state.settingsConfigured ? "ready" : "blocked",
        summary: state.settingsConfigured ? "ready for refresh" : "setup required",
        next_action: state.settingsConfigured ? "refresh_data_status" : "open_setup",
        provider_smoke_passed: state.settingsConfigured,
        ready_for_refresh: state.settingsConfigured,
        blocking_reasons: state.settingsConfigured ? [] : ["provider_keys_missing"],
        data_watermark: {
          status: state.settingsConfigured ? "ready" : "blocked",
          reason: state.settingsConfigured ? "" : "missing_daily_bars",
          sample_data_used: false,
          baseline_used: false,
          customer_prediction_generated: false
        },
        prediction_core_readiness: {
          status: "blocked",
          can_predict: false,
          reason: "active_model_missing",
          active_release_safe: false,
          missing_evidence: ["active_model"],
          blocking_reasons: ["active_model_missing"]
        },
        training_invoked: false,
        prediction_generated: false,
        backtest_invoked: false
      });
    }
    if (path === "/api/public-terminal/prediction-status") return json(route, predictionStatusPayload(false));
    if (path === "/api/public-terminal/settings/status") {
      return json(route, {
        configured: state.settingsConfigured,
        masked: state.settingsConfigured ? MASKED_SECRET : "",
        sources: [{ id: "local_api_provider", label: "Local API Provider", configured: state.settingsConfigured, masked: state.settingsConfigured ? MASKED_SECRET : "" }]
      });
    }
    if (path === "/api/public-terminal/settings/save") {
      state.settingsConfigured = true;
      return json(route, { configured: true, masked: MASKED_SECRET, success: true });
    }
    if (path === "/api/public-terminal/provider-smoke") {
      return json(route, {
        status: "success",
        row_count: 8,
        source_statuses: [{ provider: "local_api_provider", status: "success", row_count: 8 }],
        manifest: { provider_id: "local_api_provider", row_count: 8 },
        training_invoked: false,
        prediction_generated: false,
        backtest_invoked: false
      });
    }
    if (path === "/api/public-terminal/refresh-data-status") {
      state.refreshPolls = 0;
      return json(route, { task_id: "acceptance-refresh", status: "queued" }, 202);
    }
    if (path === "/api/public-terminal/tasks/acceptance-refresh") {
      state.refreshPolls += 1;
      if (state.refreshPolls < 2) return json(route, { task_id: "acceptance-refresh", status: "running", progress: 50 });
      return json(route, {
        task_id: "acceptance-refresh",
        status: "success",
        progress: 100,
        result: { data_watermark_updated: true },
        training_invoked: false,
        prediction_generated: false,
        backtest_invoked: false
      });
    }
    if (path === "/api/public-terminal/market") {
      return json(route, {
        market: {
          status: "ready",
          reason: "",
          chart: [
            { date: "2026-06-08", close: 250000 },
            { date: "2026-06-09", close: 251000 },
            { date: "2026-06-10", close: 252000 }
          ],
          kline: {
            status: "ready",
            bars: [
              { date: "2026-06-08", open: 249000, high: 251000, low: 248500, close: 250000, volume: 1000 },
              { date: "2026-06-09", open: 250000, high: 252000, low: 249500, close: 251000, volume: 1100 },
              { date: "2026-06-10", open: 251000, high: 253000, low: 250500, close: 252000, volume: 1200 }
            ]
          },
          watch_header: { status: "ready", symbol: "SN", latest_price: 252100, latest_quote_display_only: true },
          indicators: {
            status: "ready",
            values: { sma_5: 251000, rsi_14: 60.5, macd: 120, volatility_20: 0.01 },
            blocking_reasons: [],
            manifest: { allowed_for_prediction: false, sample_data_used: false }
          },
          data_watermark_panel: { display_allowed: true, prediction_allowed: false, stale_status: "fresh" },
          missing_data: { reasons: [] },
          sample_data_used: false,
          baseline_used: false,
          customer_prediction_generated: false
        },
        training_invoked: false,
        prediction_generated: false,
        backtest_invoked: false
      });
    }
    if (path === "/api/public-terminal/events") {
      return json(route, {
        event_center: {
          status: "ready",
          summary: { total_count: 2, eligible_count: 1, rejected_count: 1 },
          events: [
            {
              event_id: "acceptance-policy",
              title: "Policy update relevant to SHFE tin",
              source_name: "public_policy_rss",
              source_published_at: "2026-06-10T08:00:00+08:00",
              fetched_at: "2026-06-11T09:00:00+08:00",
              category: "china_policy",
              region: "CN",
              language: "zh",
              relevance_score: 0.91,
              used_in_model: true,
              blocking_reasons: []
            },
            {
              event_id: "acceptance-rejected",
              title: "Unrelated commodity update",
              source_name: "newsapi",
              source_published_at: "2026-06-10T09:00:00+08:00",
              fetched_at: "2026-06-11T09:01:00+08:00",
              category: "global_news",
              region: "global",
              language: "en",
              relevance_score: 0.05,
              used_in_model: false,
              blocking_reasons: ["unrelated_to_shfe_sn"]
            }
          ],
          sample_data_used: false,
          baseline_used: false,
          customer_prediction_generated: false
        },
        training_invoked: false,
        prediction_generated: false,
        backtest_invoked: false
      });
    }
    if (path === "/api/public-terminal/report") {
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
        },
        training_invoked: false,
        prediction_generated: false,
        backtest_invoked: false
      });
    }
    return json(route, { status: "mocked", path });
  });
}

async function launch(page: Page, state = createState()) {
  await page.addInitScript(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    window.localStorage.setItem("firstRunCompleted", "true");
    window.localStorage.removeItem("SN_ENABLE_DEV_CONSOLE");
    window.localStorage.removeItem("sn_enable_dev_console");
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: {
        writeText: async (value: string) => {
          window.localStorage.setItem("acceptanceDiagnostics", value);
        }
      }
    });
  });
  await installAcceptanceMocks(page, state);
  await page.goto("./");
}

async function mainText(page: Page) {
  return page.locator("main").innerText();
}

async function assertSafePublicSurface(page: Page) {
  const text = await page.locator("body").innerText();
  expect(text).not.toContain(RAW_SECRET);
  expect(text).not.toMatch(/sample prediction|fake prediction|demo forecast/i);
  expect(text).not.toMatch(/\b(buy|sell)\b|买入|卖出/i);
  await expect(page.locator(".prediction-card")).toHaveCount(0);
}

test("system acceptance matrix public journey has no ambiguous states", async ({ page }) => {
  // install_start
  const state = createState();
  await launch(page, state);
  await expect(page.locator("[data-testid='simple-nav']")).toBeVisible();
  await expect(page.locator("[data-testid='professional-nav']")).toHaveCount(0);

  // no_key and prediction_blocked
  await expect(page.locator("main")).toContainText(/暂无真实预测|暂不预测/);
  expect(await mainText(page)).toMatch(/Setup|设置|下一步/);
  await assertSafePublicSurface(page);

  // setup
  await page.getByRole("button", { name: /^Setup/i }).click();
  await page.locator("main input[type='url']").fill("http://127.0.0.1:9999/local-provider");
  await page.locator("main input[type='password']").fill(RAW_SECRET);
  await page.locator("main button.primary-button").click();
  await expect(page.locator("main")).toContainText(MASKED_SECRET);
  await expect(page.locator("main")).not.toContainText(RAW_SECRET);

  // provider_smoke
  await page.locator("main button.secondary-button").click();
  await page.locator("main details summary").click();
  await expect(page.locator("main pre.diagnostics-pre")).toContainText('"row_count": 8');

  // refresh
  await page.getByRole("button", { name: /^Data Status/i }).click();
  await page.locator("main button.primary-button").click();
  await expect(page.locator("main pre.diagnostics-pre")).toContainText('"status": "success"', { timeout: 8_000 });

  // market and indicators
  await page.getByRole("button", { name: /^Market/i }).click();
  await expect(page.getByTestId("watch-header")).toBeVisible();
  await expect(page.getByTestId("indicator-panel")).toContainText(/RSI|MACD|SMA/i);

  // news_events
  await page.getByRole("button", { name: /^Events/i }).click();
  await expect(page.getByTestId("event-summary")).toContainText("2");
  await expect(page.getByTestId("event-card-acceptance-rejected")).toContainText("unrelated_to_shfe_sn");

  // reports
  await page.getByRole("button", { name: /^Reports/i }).click();
  await expect(page.locator("main button.primary-button")).toBeEnabled();
  await expect(page.locator("main")).toContainText(/research|研究|仅供/i);

  // diagnostics
  await page.getByRole("button", { name: /^Diagnostics/i }).click();
  await page.locator("main button.primary-button").click();
  await page.locator("main button.secondary-button").click();
  const copied = await page.evaluate(() => window.localStorage.getItem("acceptanceDiagnostics") || "");
  expect(copied).toContain("readiness");
  expect(copied).not.toContain(RAW_SECRET);

  // dev_mode_hidden, no_demo_fake, no_raw_secrets, no_buy_sell_advice
  for (const forbidden of ["Candidate Research", "Governance Console", "Training Data", "Feature Store", "Managed Proxy"]) {
    await expect(page.getByText(forbidden)).toHaveCount(0);
  }
  await assertSafePublicSurface(page);
});
