import { expect, test, type Page, type Route } from "@playwright/test";

async function json(route: Route, body: unknown, status = 200) {
  await route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
}

function eventPayload() {
  return {
    event_center: {
      status: "ready",
      summary: {
        total_count: 3,
        eligible_count: 1,
        rejected_count: 2,
        categories: { china_policy: 1, global_news: 1, exchange_notice: 1 },
        regions: { CN: 2, global: 1 },
        languages: { zh: 2, en: 1 }
      },
      categories: { china_policy: 1, global_news: 1, exchange_notice: 1 },
      events: [
        {
          event_id: "eligible-policy",
          title: "China policy supports SHFE tin warehouse supply",
          source_name: "public_policy_rss",
          source_published_at: "2026-06-10T08:00:00+08:00",
          fetched_at: "2026-06-11T09:00:00+08:00",
          category: "china_policy",
          region: "CN",
          language: "zh",
          relevance_score: 0.92,
          relevance_to_shfe_sn: true,
          used_in_model: true,
          eligible_for_event_factor: true,
          blocking_reasons: []
        },
        {
          event_id: "missing-time",
          title: "SHFE tin notice missing publish time",
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
          event_id: "unrelated",
          title: "Coffee harvest outlook improves",
          source_name: "newsapi",
          source_published_at: "2026-06-10T12:00:00+08:00",
          fetched_at: "2026-06-11T09:03:00+08:00",
          category: "global_news",
          region: "global",
          language: "en",
          relevance_score: 0.08,
          relevance_to_shfe_sn: false,
          used_in_model: false,
          eligible_for_event_factor: false,
          blocking_reasons: ["unrelated_to_shfe_sn"]
        }
      ],
      training_invoked: false,
      prediction_generated: false,
      backtest_invoked: false
    },
    training_invoked: false,
    prediction_generated: false,
    backtest_invoked: false
  };
}

async function launch(page: Page) {
  await page.addInitScript(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    window.localStorage.setItem("firstRunCompleted", "true");
  });
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (!path.startsWith("/api/")) return route.continue();
    if (path === "/api/public-terminal/events") return json(route, eventPayload());
    if (path === "/api/public-terminal/readiness") {
      return json(route, { status: "ready", provider_smoke_passed: true, ready_for_refresh: true, data_watermark: {} });
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
  await page.getByRole("button", { name: /^Events/i }).click();
}

test("event center shows source time category relevance and block reasons", async ({ page }) => {
  await launch(page);

  await expect(page.getByRole("heading", { name: "Events" })).toBeVisible();
  await expect(page.getByTestId("event-summary")).toContainText("3");
  await expect(page.getByTestId("event-summary")).toContainText("1 eligible");

  const eligible = page.getByTestId("event-card-eligible-policy");
  await expect(eligible).toContainText("public_policy_rss");
  await expect(eligible).toContainText("china_policy");
  await expect(eligible).toContainText("CN");
  await expect(eligible).toContainText("zh");
  await expect(eligible).toContainText("2026-06-10T08:00:00+08:00");
  await expect(eligible).toContainText("fetched 2026-06-11T09:00:00+08:00");
  await expect(eligible).toContainText(/relevance 0\.92/i);
  await expect(eligible).toContainText("used in model");

  const missingTime = page.getByTestId("event-card-missing-time");
  await expect(missingTime).toContainText("missing_source_published_at");
  await expect(missingTime).toContainText("not used in model");

  const unrelated = page.getByTestId("event-card-unrelated");
  await expect(unrelated).toContainText("unrelated_to_shfe_sn");
  await expect(unrelated).toContainText(/relevance 0\.08/i);

  const body = await page.locator("body").innerText();
  expect(body).not.toMatch(/sample prediction|fake prediction/i);
  await expect(page.locator(".prediction-card")).toHaveCount(0);
});
