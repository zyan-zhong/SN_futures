import { expect, test, type Page, type Route } from "@playwright/test";

async function json(route: Route, body: unknown, status = 200) {
  await route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
}

function eventsPayload() {
  return {
    event_center: {
      status: "ready",
      reason: "",
      summary: {
        total_count: 3,
        eligible_count: 1,
        rejected_count: 2,
        categories: { china_news: 1, global_policy: 1, exchange_notice: 1 },
        regions: { CN: 2, global: 1 },
        languages: { zh: 2, en: 1 },
        latest_source_published_at: "2026-06-10T12:00:00+08:00",
        latest_fetched_at: "2026-06-11T09:03:00+08:00"
      },
      categories: { china_news: 1, global_policy: 1, exchange_notice: 1 },
      events: [
        {
          event_id: "china-news",
          title: "China news: SHFE tin inventory changes",
          summary: "Inventory and warehouse warrant update.",
          source_name: "newsapi",
          source_published_at: "2026-06-10T08:00:00+08:00",
          fetched_at: "2026-06-11T09:00:00+08:00",
          category: "china_news",
          region: "CN",
          language: "zh",
          relevance_score: 0.84,
          relevance_to_shfe_sn: true,
          used_in_model: true,
          eligible_for_event_factor: true,
          blocking_reasons: []
        },
        {
          event_id: "missing-time",
          title: "SHFE notice missing source publish time",
          source_name: "shfe_public",
          source_published_at: "",
          fetched_at: "2026-06-11T09:02:00+08:00",
          category: "exchange_notice",
          region: "CN",
          language: "zh",
          relevance_score: 0.78,
          relevance_to_shfe_sn: true,
          used_in_model: false,
          eligible_for_event_factor: false,
          blocking_reasons: ["missing_source_published_at"]
        },
        {
          event_id: "unrelated-policy",
          title: "Global policy briefing unrelated to metals",
          source_name: "public_policy_rss",
          source_published_at: "2026-06-10T12:00:00+08:00",
          fetched_at: "2026-06-11T09:03:00+08:00",
          category: "global_policy",
          region: "global",
          language: "en",
          relevance_score: 0.08,
          relevance_to_shfe_sn: false,
          used_in_model: false,
          eligible_for_event_factor: false,
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
  };
}

function emptyEventsPayload() {
  return {
    event_center: {
      status: "blocked",
      reason: "missing_events",
      events: [],
      summary: { total_count: 0, eligible_count: 0, rejected_count: 0, categories: {}, regions: {}, languages: {} },
      categories: {},
      regions: {},
      languages: {},
      sample_data_used: false,
      baseline_used: false,
      customer_prediction_generated: false
    },
    training_invoked: false,
    prediction_generated: false,
    backtest_invoked: false
  };
}

function reportPayload() {
  const summary = eventsPayload().event_center.summary;
  return {
    report: {
      status: "blocked",
      reason: "missing_daily_bars",
      market_data_coverage: "empty",
      event_coverage: "ready",
      event_count: 3,
      timed_event_count: 1,
      event_summary: summary,
      event_section: {
        status: "ready",
        total_count: 3,
        eligible_count: 1,
        rejected_count: 2,
        categories: summary.categories,
        latest_source_published_at: summary.latest_source_published_at,
        latest_fetched_at: summary.latest_fetched_at,
        investment_advice: false,
        used_for_customer_prediction: false
      },
      research_only: true,
      investment_advice: false,
      export_allowed: false
    },
    training_invoked: false,
    prediction_generated: false,
    backtest_invoked: false
  };
}

async function launch(page: Page, mode: "ready" | "empty" = "ready") {
  await page.addInitScript(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    window.localStorage.setItem("firstRunCompleted", "true");
  });
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (!path.startsWith("/api/")) return route.continue();
    if (path === "/api/public-terminal/events") return json(route, mode === "empty" ? emptyEventsPayload() : eventsPayload());
    if (path === "/api/public-terminal/report") return json(route, reportPayload());
    if (path === "/api/public-terminal/readiness") return json(route, { status: "ready", provider_smoke_passed: true, data_watermark: {} });
    if (path === "/api/terminal/snapshot-lite") return json(route, { sample_mode: false, predictions: [], summary: {}, data_status: { sources: [] } });
    if (path === "/api/terminal/task-notifications") return json(route, { toast_task: null, notification_center: { tasks: [] } });
    if (path === "/api/terminal/tasks/recent") return json(route, { tasks: [] });
    if (path === "/api/terminal/settings/status") return json(route, { configured: false, providers: {} });
    if (path === "/api/terminal/data-status") return json(route, { sources: [] });
    if (path === "/api/terminal/system-health") return json(route, { api_status: "ok", warnings: [] });
    return json(route, { status: "mocked", path });
  });
  await page.goto("./");
}

test("public event center shows event cards with provenance relevance and eligibility", async ({ page }) => {
  await launch(page);
  await page.getByRole("button", { name: /^Events/i }).click();

  await expect(page.getByRole("heading", { name: "Events" })).toBeVisible();
  await expect(page.getByTestId("event-summary-section")).toContainText("3");
  await expect(page.getByTestId("event-summary-section")).toContainText("1 eligible");
  await expect(page.getByTestId("event-summary-section")).toContainText("china_news");
  await expect(page.getByTestId("event-card-china-news")).toContainText("newsapi");
  await expect(page.getByTestId("event-card-china-news")).toContainText("published 2026-06-10T08:00:00+08:00");
  await expect(page.getByTestId("event-card-china-news")).toContainText("fetched 2026-06-11T09:00:00+08:00");
  await expect(page.getByTestId("event-card-china-news")).toContainText(/relevance 0\.84/i);
  await expect(page.getByTestId("event-card-china-news")).toContainText("used in model");

  await expect(page.getByTestId("event-card-missing-time")).toContainText("missing_source_published_at");
  await expect(page.getByTestId("event-card-unrelated-policy")).toContainText("unrelated_to_shfe_sn");

  const body = await page.locator("body").innerText();
  expect(body).not.toMatch(/buy|sell|long|short|买入|卖出|做多|做空|investment advice/i);
});

test("public event center has empty state when no events exist", async ({ page }) => {
  await launch(page, "empty");
  await page.getByRole("button", { name: /^Events/i }).click();

  await expect(page.getByTestId("event-summary-section")).toContainText("0");
  await expect(page.getByTestId("event-empty-state")).toContainText("missing_events");
  await expect(page.locator("[data-testid^='event-card-']")).toHaveCount(0);
});

test("public reports show event summary section without advice", async ({ page }) => {
  await launch(page);
  await page.getByRole("button", { name: /^Reports/i }).click();

  await expect(page.getByTestId("report-event-summary-section")).toContainText("3");
  await expect(page.getByTestId("report-event-summary-section")).toContainText("1 eligible");
  await expect(page.getByTestId("report-event-summary-section")).toContainText("china_news");
  await expect(page.getByTestId("report-event-summary-section")).toContainText("global_policy");
  const body = await page.locator("body").innerText();
  expect(body).not.toMatch(/buy|sell|long|short|买入|卖出|做多|做空/i);
});
