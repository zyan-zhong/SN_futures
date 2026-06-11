import { expect, test, type Page } from "@playwright/test";

test.setTimeout(120_000);

async function installUsabilityMocks(page: Page) {
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
      last_update_time: "2026-06-01T09:30:00+08:00"
    },
    data_status: {
      sources: [
        { source_name: "market_history", enabled: true, success: true, status: "success" },
        { source_name: "tushare_warehouse", enabled: true, success: false, status: "no_sn_rows", row_count: 0 }
      ],
      tushare_subinterfaces: [
        { source_name: "tushare_warehouse", status: "no_sn_rows", row_count: 0, error_message_zh: "no SN warehouse rows" }
      ]
    },
    model_health: { active_model: false, promotion_status: "blocked" },
    sample_mode: false
  };

  await page.route("**/api/terminal/snapshot-lite", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(snapshot) });
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
  await page.route("**/api/terminal/settings/status", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ alpha_vantage_configured: true, newsapi_configured: true })
    });
  });
  await page.route("**/api/terminal/data-status", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(snapshot.data_status) });
  });
  await page.route("**/api/terminal/system-health", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ health: { status: "ok", warnings: [] } }) });
  });
  await page.route("**/api/terminal/system/process-status", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ status: "running", pid: 1234 }) });
  });
  await page.route("**/api/terminal/feature-store/status**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        version: "v7",
        status: "success",
        row_count: 100,
        usable_fields: ["inventory_missing_flag", "warehouse_data_quality_score"],
        warehouse_policy_features: ["inventory_missing_flag", "warehouse_data_quality_score"],
        warehouse_missing_policy: {
          warehouse_receipt_available: false,
          reason: "tushare_fut_wsr_no_sn_rows",
          message_zh: "No real SN warehouse receipt rows are available; the system uses a missing-risk marker only."
        }
      })
    });
  });
  await page.route("**/api/terminal/predictions", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ predictions: [] }) });
  });
  await page.route("**/api/terminal/reports/full-system-txt", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        status: "success",
        latest_txt_path: "outputs/reports/full_system_report_latest.txt",
        diagnostics_bundle_path: "outputs/reports/diagnostics_bundle.zip",
        message_zh: "report generated"
      })
    });
  });
  await page.route("**/api/terminal/diagnostics/export", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ success: true, path: "outputs/diagnostics/diagnostics_bundle.zip", bundle: { files: 3 } })
    });
  });
  await page.route("**/api/terminal/**", async (route) => {
    const request = route.request();
    if (request.method() === "POST") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          status: "success",
          task_id: "usability-second-pass",
          kind: "mocked",
          active_updated: false,
          customer_prediction_generated: false,
          message_zh: "mocked"
        })
      });
      return;
    }
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ status: "success" }) });
  });
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    window.localStorage.setItem("SN_ENABLE_DEV_CONSOLE", "1");
    window.localStorage.setItem("firstRunCompleted", "true");
    window.localStorage.setItem("showSampleData", "true");
  });
  await installUsabilityMocks(page);
});

test("simple mode defaults to seven workspace entries and renders clean operational copy", async ({ page }) => {
  await page.goto("./");

  await expect(page.locator("[data-testid='simple-nav']")).toBeVisible();
  await expect(page.locator(".sidebar .nav-item")).toHaveCount(7);
  await expect(page.getByText("Home").first()).toBeVisible();
  await expect(page.getByText("Setup").first()).toBeVisible();
  await expect(page.getByText("Data Status").first()).toBeVisible();
  await expect(page.getByText("Market").first()).toBeVisible();
  await expect(page.getByText("Events").first()).toBeVisible();
  await expect(page.getByText("Reports").first()).toBeVisible();
  await expect(page.getByText("Diagnostics").first()).toBeVisible();
  await expect(page.locator("main").getByText("当前状态").first()).toBeVisible();

  const text = await page.locator("body").innerText();
  expect(text).not.toContain("undefined");
  expect(text).not.toContain("null");
  expect(text).not.toContain("NaN");
  expect(text.toLowerCase()).not.toContain("fake prediction");
});

test("professional mode exposes full workbench and one-click operations export", async ({ page }) => {
  await page.goto("./");
  await page.getByRole("button", { name: "Professional" }).first().click();
  await expect(page.locator("[data-testid='professional-nav']")).toBeVisible();
  await expect(page.locator(".sidebar .nav-item")).toHaveCount(16);
  await expect(page.getByText("Research Archive").first()).toBeVisible();

  await page.locator(".sidebar .nav-item").nth(10).click();
  await expect(page.locator(".workspace")).toBeVisible();

  const reportButton = page.getByRole("button", { name: /report|TXT/i }).first();
  if (await reportButton.isVisible().catch(() => false)) {
    await reportButton.click();
    await expect(page.locator(".error-boundary")).toHaveCount(0);
  }

  const diagnosticsButton = page.getByRole("button", { name: /diagnostics|export|copy/i }).first();
  if (await diagnosticsButton.isVisible().catch(() => false)) {
    await diagnosticsButton.click();
    await expect(page.locator(".error-boundary")).toHaveCount(0);
  }

  await page.locator(".sidebar .nav-item").nth(2).click();
  await expect(page.getByText("warehouse_missing_policy").first()).toBeVisible();
  await expect(page.getByText("inventory_missing_flag").first()).toBeVisible();
});
