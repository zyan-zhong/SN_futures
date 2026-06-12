import { expect, test, type Page, type Route } from "@playwright/test";

async function json(route: Route, body: unknown, status = 200) {
  await route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
}

function readyMarketPayload() {
  const bars = [
    { date: "2026-06-06", open: 248000, high: 250000, low: 247000, close: 249000, volume: 1000, open_interest: 5000, warehouse_warrant: 817, inventory: 1871 },
    { date: "2026-06-07", open: 249000, high: 251000, low: 248000, close: 250200, volume: 1100, open_interest: 5050, warehouse_warrant: 818, inventory: 1874 },
    { date: "2026-06-08", open: 250200, high: 252000, low: 249800, close: 251300, volume: 1200, open_interest: 5080, warehouse_warrant: 819, inventory: 1877 },
    { date: "2026-06-09", open: 251300, high: 253000, low: 250900, close: 252100, volume: 1300, open_interest: 5110, warehouse_warrant: 820, inventory: 1880 }
  ];
  return {
    market: {
      status: "ready",
      reason: "",
      chart: bars,
      kline: { status: "ready", timeframe: "daily", bars },
      watch_header: {
        status: "ready",
        symbol: "SN",
        latest_price: 252300,
        daily_close: 252100,
        latest_quote_display_only: true,
        quote_time: "2026-06-11T09:31:00+08:00",
        trade_date: "2026-06-09",
        volume: 1300,
        open_interest: 5110
      },
      inventory: { warehouse_warrant: 820, inventory: 1880, volume: 1300, open_interest: 5110 },
      latest_quote: { latest_price: 252300, latest_quote_display_only: true },
      intraday_status: {
        status: "blocked",
        reason: "missing_intraday_bars",
        interval: "",
        row_count: 0,
        latest_bar_time: "",
        latest_quote_used_as_intraday_bar: false,
        daily_bar_used_as_intraday: false,
        blocking_reasons: ["missing_intraday_bars"]
      },
      indicators: {
        status: "ready",
        values: {
          sma_5: 251000,
          sma_20: 248900,
          ema_12: 250450,
          ema_26: 249800,
          rsi_14: 61.2,
          macd: 310,
          macd_signal: 240,
          atr_14: 1850,
          volatility_20: 0.012,
          volume_change_1: 0.0833,
          open_interest_change_1: 0.0059
        },
        inventory_summary: {
          warehouse_warrant_latest: 820,
          inventory_latest: 1880,
          warehouse_warrant_change_1: 1,
          inventory_change_1: 3
        },
        blocking_reasons: [],
        manifest: { allowed_for_prediction: false, sample_data_used: false }
      },
      data_watermark_panel: {
        display_allowed: true,
        prediction_allowed: false,
        cache_status: "remote",
        stale_status: "fresh",
        source_published_at: "2026-06-09T15:00:00+08:00"
      },
      missing_data: { reasons: [] },
      sample_data_used: false,
      baseline_used: false,
      customer_prediction_generated: false
    },
    training_invoked: false,
    prediction_generated: false,
    backtest_invoked: false
  };
}

function blockedPayload(reason: string) {
  return {
    market: {
      status: "blocked",
      reason,
      chart: [],
      kline: { status: "blocked", timeframe: "daily", bars: [] },
      watch_header: { status: "blocked", symbol: "SN", latest_price: null, latest_quote_display_only: true },
      intraday_status: { status: "blocked", reason, row_count: 0, latest_quote_used_as_intraday_bar: false },
      indicators: {
        status: "blocked",
        values: {},
        blocking_reasons: [reason],
        manifest: { allowed_for_prediction: false, sample_data_used: false }
      },
      data_watermark_panel: { display_allowed: false, prediction_allowed: false, stale_status: "blocked" },
      missing_data: { reasons: [reason] },
      sample_data_used: false,
      baseline_used: false,
      customer_prediction_generated: false
    },
    prediction_generated: false
  };
}

async function launch(page: Page, marketPayload: unknown) {
  await page.addInitScript(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    window.localStorage.setItem("firstRunCompleted", "true");
  });
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (!path.startsWith("/api/")) return route.continue();
    if (path === "/api/public-terminal/market") return json(route, marketPayload);
    if (path === "/api/public-terminal/readiness") {
      return json(route, { status: "ready", provider_smoke_passed: true, data_watermark: { status: "ready", sample_data_used: false } });
    }
    if (path === "/api/terminal/snapshot-lite") return json(route, { sample_mode: false, predictions: [], summary: {}, data_status: { sources: [] } });
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

test("public market shows full indicator set with simple labels and collapsed technical details", async ({ page }) => {
  await launch(page, readyMarketPayload());

  await expect(page.getByTestId("watch-header")).toContainText(/Latest|Daily close|Volume/i);
  await expect(page.getByTestId("watch-header")).toContainText(/display-only quote/i);
  await expect(page.getByTestId("watch-header")).toContainText(/Minute line/i);
  await expect(page.getByTestId("watch-header")).toContainText(/missing_intraday_bars/i);
  await expect(page.getByTestId("kline-panel").locator("[data-kline-bar]")).toHaveCount(4);
  await expect(page.getByTestId("indicator-panel")).toContainText(/EMA 12/i);
  await expect(page.getByTestId("indicator-panel")).toContainText(/ATR 14/i);
  await expect(page.getByTestId("indicator-panel")).toContainText(/Volume change/i);
  await expect(page.getByTestId("indicator-panel")).toContainText(/Open interest change/i);
  await expect(page.getByTestId("indicator-panel")).toContainText(/Warehouse warrant/i);
  await expect(page.getByTestId("data-watermark-panel")).toContainText(/prediction denied/i);
  await expect(page.locator("details.technical-details-drawer")).not.toHaveAttribute("open", "");
});

test("public market never renders a sample chart", async ({ page }) => {
  await launch(page, blockedPayload("no_demo_public_firewall"));

  await expect(page.getByTestId("kline-panel")).toHaveCount(0);
  await expect(page.getByTestId("indicator-panel")).toHaveCount(0);
  await expect(page.getByTestId("missing-data-panel")).toContainText("no_demo_public_firewall");
  await expect(page.locator("body")).not.toContainText(/sample chart|demo chart|fake prediction/i);
});
