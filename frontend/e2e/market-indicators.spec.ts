import { expect, test, type Page, type Route } from "@playwright/test";

type MarketMode = "ready" | "blocked" | "stale" | "sample";

async function json(route: Route, body: unknown, status = 200) {
  await route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
}

function marketPayload(mode: MarketMode) {
  if (mode === "blocked") {
    return {
      market: {
        status: "blocked",
        reason: "missing_daily_bars",
        chart: [],
        kline: { status: "blocked", bars: [] },
        watch_header: { status: "blocked", latest_price: null, latest_quote_display_only: true },
        indicators: {
          status: "blocked",
          values: {},
          blocking_reasons: ["missing_daily_bars"],
          manifest: { allowed_for_prediction: false, sample_data_used: false }
        },
        data_watermark_panel: { display_allowed: false, prediction_allowed: false, stale_status: "missing" },
        missing_data: { reasons: ["missing_daily_bars"] },
        sample_data_used: false,
        baseline_used: false,
        customer_prediction_generated: false
      },
      training_invoked: false,
      prediction_generated: false,
      backtest_invoked: false
    };
  }
  if (mode === "sample") {
    return {
      market: {
        status: "blocked",
        reason: "no_demo_public_firewall",
        chart: [],
        kline: { status: "blocked", bars: [] },
        watch_header: { status: "blocked", latest_price: null, latest_quote_display_only: true },
        indicators: { status: "blocked", values: {}, blocking_reasons: ["no_demo_public_firewall"] },
        data_watermark_panel: { display_allowed: false, prediction_allowed: false, stale_status: "blocked" },
        missing_data: { reasons: ["no_demo_public_firewall"] },
        sample_data_used: false,
        baseline_used: false,
        customer_prediction_generated: false
      },
      prediction_generated: false
    };
  }
  return {
    market: {
      status: mode === "stale" ? "stale" : "ready",
      reason: mode === "stale" ? "stale_daily_bars" : "",
      chart: [
        { date: "2026-06-06", open: 248000, high: 250000, low: 247000, close: 249000, volume: 1000, open_interest: 5000 },
        { date: "2026-06-07", open: 249000, high: 251000, low: 248000, close: 250200, volume: 1100, open_interest: 5050 },
        { date: "2026-06-08", open: 250200, high: 252000, low: 249800, close: 251300, volume: 1200, open_interest: 5080 },
        { date: "2026-06-09", open: 251300, high: 253000, low: 250900, close: 252100, volume: 1300, open_interest: 5110 }
      ],
      kline: {
        status: "ready",
        bars: [
          { date: "2026-06-06", open: 248000, high: 250000, low: 247000, close: 249000, volume: 1000, open_interest: 5000 },
          { date: "2026-06-07", open: 249000, high: 251000, low: 248000, close: 250200, volume: 1100, open_interest: 5050 },
          { date: "2026-06-08", open: 250200, high: 252000, low: 249800, close: 251300, volume: 1200, open_interest: 5080 },
          { date: "2026-06-09", open: 251300, high: 253000, low: 250900, close: 252100, volume: 1300, open_interest: 5110 }
        ]
      },
      watch_header: {
        status: mode === "stale" ? "stale" : "ready",
        symbol: "SN",
        latest_price: 252300,
        daily_close: 252100,
        latest_quote_display_only: true,
        volume: 1300,
        open_interest: 5110
      },
      inventory: { warehouse_warrant: 820, inventory: 1880 },
      indicators: {
        status: "ready",
        values: { sma_5: 251000, sma_20: 248900, rsi_14: 61.2, macd: 310, macd_signal: 240, volatility_20: 0.012 },
        blocking_reasons: [],
        manifest: { allowed_for_prediction: false, sample_data_used: false }
      },
      data_watermark_panel: {
        display_allowed: true,
        prediction_allowed: false,
        cache_status: "remote",
        stale_status: mode === "stale" ? "stale" : "fresh",
        source_published_at: "2026-06-09T15:00:00+08:00"
      },
      missing_data: { reasons: mode === "stale" ? ["stale_daily_bars"] : [] },
      sample_data_used: false,
      baseline_used: false,
      customer_prediction_generated: false
    },
    training_invoked: false,
    prediction_generated: false,
    backtest_invoked: false
  };
}

async function launch(page: Page, mode: MarketMode) {
  await page.addInitScript(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    window.localStorage.setItem("firstRunCompleted", "true");
  });
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (!path.startsWith("/api/")) return route.continue();
    if (path === "/api/public-terminal/market") return json(route, marketPayload(mode));
    if (path === "/api/public-terminal/readiness") {
      return json(route, {
        status: "ready",
        provider_smoke_passed: true,
        ready_for_refresh: true,
        data_watermark: { status: "ready", sample_data_used: false, baseline_used: false }
      });
    }
    if (path === "/api/terminal/snapshot-lite") {
      return json(route, { sample_mode: false, predictions: [], summary: {}, data_status: { sources: [] } });
    }
    if (path === "/api/terminal/task-notifications") return json(route, { toast_task: null, notification_center: { tasks: [] } });
    if (path === "/api/terminal/tasks/recent") return json(route, { tasks: [] });
    if (path === "/api/terminal/settings/status") return json(route, { configured: false, providers: {} });
    if (path === "/api/terminal/data-status") return json(route, { sources: [] });
    if (path === "/api/terminal/system-health") return json(route, { api_status: "ok", warnings: [] });
    return json(route, { status: "mocked", path });
  });
  await page.goto("./");
  await page.getByRole("button", { name: /^Market/i }).click();
}

test("market page renders watch board, kline, indicators, and watermark from public API", async ({ page }) => {
  await launch(page, "ready");

  await expect(page.getByTestId("watch-header")).toBeVisible();
  await expect(page.getByTestId("watch-latest-price")).toContainText(/252,?300/);
  await expect(page.getByTestId("kline-panel")).toBeVisible();
  await expect(page.getByTestId("kline-panel").locator("[data-kline-bar]")).toHaveCount(4);
  await expect(page.getByTestId("indicator-panel")).toContainText(/RSI|MACD|SMA|Volatility/i);
  await expect(page.getByTestId("data-watermark-panel")).toContainText(/fresh|display/i);
  await expect(page.getByTestId("missing-data-panel")).toHaveCount(0);

  const bodyText = await page.locator("body").innerText();
  expect(bodyText).not.toMatch(/sample chart|sample prediction|fake prediction/i);
  await expect(page.locator(".prediction-card")).toHaveCount(0);
});

test("market page keeps stale bars visible but clearly denies prediction use", async ({ page }) => {
  await launch(page, "stale");

  await expect(page.getByTestId("kline-panel").locator("[data-kline-bar]")).toHaveCount(4);
  await expect(page.getByTestId("data-watermark-panel")).toContainText(/stale/i);
  await expect(page.getByTestId("data-watermark-panel")).toContainText(/prediction.*denied|denied/i);
  await expect(page.getByTestId("missing-data-panel")).toContainText("stale_daily_bars");
});

test("market page blocks missing or sample chart data", async ({ page }) => {
  await launch(page, "blocked");

  await expect(page.getByTestId("kline-panel")).toHaveCount(0);
  await expect(page.getByTestId("indicator-panel")).toHaveCount(0);
  await expect(page.getByTestId("missing-data-panel")).toContainText("missing_daily_bars");

  const samplePage = await page.context().newPage();
  await launch(samplePage, "sample");
  await expect(samplePage.getByTestId("kline-panel")).toHaveCount(0);
  await expect(samplePage.getByTestId("missing-data-panel")).toContainText("no_demo_public_firewall");
});
