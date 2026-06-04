import { expect, test, type Page } from "@playwright/test";

test.setTimeout(120_000);

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    window.localStorage.setItem("firstRunCompleted", "true");
    window.localStorage.setItem("showSampleData", "true");
    window.localStorage.removeItem("uiMode");
  });
  await installSimpleModeMocks(page);
});

async function installSimpleModeMocks(page: Page) {
  const snapshot = {
    summary: {
      main_contract: "SN0",
      latest_price: 251000,
      price_change_pct: 0.004,
      current_signal: "watch",
      system_status: "running",
      model_status: "no active",
      risk_level: "watch",
      data_quality_score: 0.92,
      last_update_time: "2026-05-31T09:30:00+08:00"
    },
    data_status: {
      sources: [
        { source_name: "market_history", enabled: true, success: true },
        { source_name: "fundamentals", enabled: true, success: false }
      ]
    },
    model_health: { active_model: false, promotion_status: "blocked" },
    learning_status: { backtest_status: "research empty" },
    predictions: [],
    sample_mode: false
  };

  await page.route("**/api/terminal/snapshot-lite", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(snapshot) });
  });
  await page.route("**/api/terminal/charts/price-history", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        schema_version: 1,
        points: [
          { time: "2026-05-29", close: 250000, volume: 9000 },
          { time: "2026-05-30", close: 251000, volume: 9500 }
        ],
        sample_mode: false
      })
    });
  });
  await page.route("**/api/terminal/task-notifications**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        status: "success",
        toast_task: null,
        stale_failure_suppressed: false,
        notification_center: { tasks: [], failed_tasks: [], active_tasks: [] }
      })
    });
  });
  await page.route("**/api/terminal/tasks/recent**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ tasks: [] }) });
  });
  await page.route("**/api/terminal/settings/status", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ alpha_vantage_configured: true, newsapi_configured: true })
    });
  });
  await page.route("**/api/terminal/data-status", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ sources: [] }) });
  });
  await page.route("**/api/terminal/system-health", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ status: "ok" }) });
  });
}

test("default simple mode shows six workspace entries and compact overview", async ({ page }) => {
  await page.goto("./");
  await expect(page.locator("[data-testid='simple-nav']")).toBeVisible();
  await expect(page.locator(".sidebar .nav-item")).toHaveCount(6);
  await expect(page.getByText("Terminal Overview").first()).toBeVisible();
  await expect(page.getByText("Prediction Workspace").first()).toBeVisible();
  await expect(page.getByText("Data Onboarding").first()).toBeVisible();
  await expect(page.getByText("Candidate Research").first()).toBeVisible();
  await expect(page.getByText("Governance Console").first()).toBeVisible();
  await expect(page.getByText("Settings").first()).toBeVisible();
  await expect(page.locator(".simple-dashboard-grid .metric-card")).toHaveCount(6);
  await expect(page.locator(".dashboard-extra-detail")).not.toBeVisible();
});

test("professional mode expands the full workbench plus split workspaces", async ({ page }) => {
  await page.goto("./");
  await page.getByRole("button", { name: "Professional" }).first().click();
  await expect(page.locator("[data-testid='professional-nav']")).toBeVisible();
  await expect(page.locator(".sidebar .nav-item")).toHaveCount(16);
  await expect(page.getByText("News and Events").first()).toBeVisible();
  await expect(page.getByText("Backtest Validation").first()).toBeVisible();
  await expect(page.getByText("Prediction Workspace").first()).toBeVisible();
  await expect(page.getByText("Research Archive").first()).toBeVisible();
  await expect(page.locator(".dashboard-extra-detail")).toBeVisible();
});

test("refresh task keeps layout stable and disables duplicate clicks", async ({ page }) => {
  await page.route("**/api/terminal/refresh/all", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 800));
    await route.fulfill({
      status: 202,
      contentType: "application/json",
      body: JSON.stringify({ status: "queued", task_id: "simple-mode-refresh", kind: "refresh_all", progress: 0, message_zh: "refresh queued" })
    });
  });

  await page.goto("./");
  await page.getByRole("button", { name: "Professional" }).first().click();
  const before = await page.locator(".workspace").boundingBox();
  const button = page.locator(".dashboard-extra-detail .primary-button").first();
  await button.click();
  await expect(button).toBeDisabled();
  await expect(page.locator(".global-task-bar")).toBeVisible();
  const after = await page.locator(".workspace").boundingBox();
  expect(Math.abs((after?.height || 0) - (before?.height || 0))).toBeLessThan(80);
  const text = await page.locator("body").innerText();
  expect(text).not.toContain("undefined");
  expect(text).not.toContain("null");
  expect(text).not.toContain("NaN");
});

test("mobile simple mode has no horizontal overflow", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("./");
  const sizes = await page.evaluate(() => ({
    html: document.documentElement.scrollWidth,
    body: document.body.scrollWidth,
    width: window.innerWidth
  }));
  expect(sizes.html).toBeLessThanOrEqual(sizes.width + 2);
  expect(sizes.body).toBeLessThanOrEqual(sizes.width + 2);
});
