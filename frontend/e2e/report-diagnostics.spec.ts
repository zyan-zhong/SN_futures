import { expect, test, type Page } from "@playwright/test";

test.setTimeout(120_000);

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    window.localStorage.setItem("SN_ENABLE_DEV_CONSOLE", "1");
    window.localStorage.setItem("firstRunCompleted", "true");
    window.localStorage.setItem("showSampleData", "true");
    window.localStorage.setItem("uiMode", JSON.stringify("professional"));
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: {
        writeText: async (value: string) => {
          window.sessionStorage.setItem("e2eClipboard", value);
        }
      }
    });
  });
  await installSettingsMocks(page);
});

async function installSettingsMocks(page: Page) {
  await page.route("**/api/terminal/snapshot-lite", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        summary: { main_contract: "SN0", system_status: "E2E stable", current_signal: "观望" },
        predictions: [],
        sample_mode: false
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
      body: JSON.stringify({
        alpha_vantage_configured: false,
        newsapi_configured: false,
        managed_data_proxy_configured: false,
        managed_data_proxy_endpoint_configured: false,
        api_base_url: "http://127.0.0.1:8765",
        terminal_url: "http://127.0.0.1:5173/terminal"
      })
    });
  });
  await page.route("**/api/terminal/training-dataset/status**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ status: "missing", message_zh: "暂无训练数据集" }) });
  });
}

async function openSettingsPage(page: Page) {
  await page.goto("./");
  const navItem = page.locator(".sidebar .nav-item").nth(10);
  await expect(navItem).toBeVisible();
  await navItem.click();
  await expect(navItem).toHaveClass(/active/, { timeout: 5_000 });
  await expect(page.getByRole("heading", { name: "完整系统 TXT 报告" })).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText(/加载中|正在加载/)).toHaveCount(0, { timeout: 15_000 });
  await expect(page.locator(".error-boundary")).toHaveCount(0);
}

test("settings report diagnostics actions use mocked APIs and remain stable", async ({ page }) => {
  const postCalls: string[] = [];
  const repairPlanCalls: string[] = [];
  await page.route("**/api/terminal/reports/full-system-txt", async (route) => {
    postCalls.push(route.request().url());
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        status: "success",
        latest_txt_path: "outputs/reports/full_system_report_latest.txt",
        json_path: "outputs/reports/full_system_report_latest.json",
        diagnostics_bundle_path: "outputs/reports/diagnostics_bundle.zip"
      })
    });
  });
  await page.route("**/api/terminal/reports/full-system-txt/latest", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        status: "success",
        txt_path: "outputs/reports/full_system_report_latest.txt",
        json_path: "outputs/reports/full_system_report_latest.json",
        diagnostics_bundle_path: "outputs/reports/diagnostics_bundle.zip",
        text_preview: "SNInsightTerminal full system report preview"
      })
    });
  });
  await page.route("**/api/terminal/diagnostics/build-repair-plan", async (route) => {
    repairPlanCalls.push(route.request().url());
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        status: "success",
        overall_status: "blocked_for_prediction",
        markdown_path: "outputs/diagnostics/system_repair_plan.md",
        json_path: "outputs/diagnostics/system_repair_plan.json",
        issues: [
          {
            id: "MODEL-001",
            priority: "P0",
            category: "model",
            title: "No active model is available",
            evidence: "active_status=none",
            impact: "Prediction delivery stays blocked.",
            fix_plan: "Fix promotion blockers.",
            owner: "model",
            expected_gain: "Restores promotion path."
          },
          {
            id: "DATA-002",
            priority: "P1",
            category: "data",
            title: "Data freshness needs cleanup",
            evidence: "missing_watermarks=news_updated_at",
            impact: "Diagnostics can be stale.",
            fix_plan: "Refresh real data artifacts.",
            owner: "data",
            expected_gain: "Improves lineage."
          },
          {
            id: "SECURITY-002",
            priority: "P2",
            category: "security",
            title: "Runtime secret scan is not current",
            evidence: "secret_scan.status=not_run",
            impact: "Release evidence is incomplete.",
            fix_plan: "Run existing runtime scan.",
            owner: "release",
            expected_gain: "Improves evidence completeness."
          }
        ],
        next_prompts: ["Run a TDD data-coverage repair pass without training or publishing active."],
        active_updated: false,
        customer_prediction_generated: false
      })
    });
  });

  await openSettingsPage(page);
  await page.getByRole("button", { name: "生成完整系统 TXT 报告" }).click();

  await expect(page.getByText("完整系统 TXT 报告已生成。")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("outputs/reports/full_system_report_latest.txt")).toBeVisible();
  await expect(page.getByText("outputs/reports/diagnostics_bundle.zip")).toBeVisible();
  expect(postCalls).toHaveLength(1);

  await page.getByRole("button", { name: "下载 TXT" }).click();
  await expect(page.getByText(/下载 TXT：outputs\/reports\/full_system_report_latest\.txt/)).toBeVisible();

  await page.getByRole("button", { name: "复制摘要" }).click();
  await expect(page.getByText("报告摘要已复制。")).toBeVisible();
  const copied = await page.evaluate(() => window.sessionStorage.getItem("e2eClipboard"));
  expect(copied).toContain("SNInsightTerminal full system report preview");

  await page.getByRole("button", { name: "生成系统修复计划" }).click();
  await expect(page.getByText("系统修复计划已生成。")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("outputs/diagnostics/system_repair_plan.md")).toBeVisible();
  await expect(page.getByText("MODEL-001")).toBeVisible();
  await expect(page.getByText("DATA-002")).toBeVisible();
  await expect(page.getByText("SECURITY-002")).toBeVisible();
  expect(repairPlanCalls).toHaveLength(1);

  await page.getByRole("button", { name: "下载 repair_plan.md" }).click();
  await expect(page.getByText(/下载 repair_plan\.md：outputs\/diagnostics\/system_repair_plan\.md/)).toBeVisible();

  await page.getByRole("button", { name: "复制修复摘要" }).click();
  await expect(page.getByText("修复摘要已复制。")).toBeVisible();
  const copiedRepairPlan = await page.evaluate(() => window.sessionStorage.getItem("e2eClipboard"));
  expect(copiedRepairPlan).toContain("MODEL-001");
  expect(copiedRepairPlan).toContain("P0");

  const visibleText = await page.locator("body").innerText();
  expect(visibleText).not.toContain("undefined");
  expect(visibleText).not.toContain("null");
  expect(visibleText).not.toContain("NaN");
  await expect(page.locator(".error-boundary")).toHaveCount(0);
});
