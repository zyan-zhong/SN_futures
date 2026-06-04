import { expect, test, type Page } from "@playwright/test";

test.setTimeout(180_000);

const pages = [
  { key: "market", navIndex: 0 },
  { key: "events", navIndex: 1 },
  { key: "factors", navIndex: 2 },
  { key: "training", navIndex: 3 },
  { key: "research", navIndex: 4 },
  { key: "backtest", navIndex: 6 },
  { key: "predictions", navIndex: 7 },
  { key: "reports", navIndex: 8 },
  { key: "data", navIndex: 9 },
  { key: "settings", navIndex: 10 }
] as const;

const safeButtonSelector = "main button:visible:not(.danger-button):not([disabled]):not([aria-disabled='true'])";

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    window.localStorage.setItem("firstRunCompleted", "true");
    window.localStorage.setItem("showSampleData", "true");
    window.localStorage.setItem("uiMode", JSON.stringify("professional"));
  });
  await installButtonActionMocks(page);
});

async function installButtonActionMocks(page: Page) {
  await page.route("**/api/terminal/**", async (route) => {
    const request = route.request();
    if (request.method() === "POST") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          status: "success",
          success: true,
          task_id: "button-audit-e2e",
          task_type: "e2e_mocked",
          message_zh: "E2E mocked task response",
          path: "outputs/diagnostics/e2e_mocked.txt",
          latest_txt_path: "outputs/reports/full_system_report_latest.txt",
          diagnostics_bundle_path: "outputs/reports/diagnostics_bundle.zip",
          markdown_path: "outputs/diagnostics/system_repair_plan.md",
          json_path: "outputs/diagnostics/system_repair_plan.json",
          issues: [],
          active_updated: false,
          customer_prediction_generated: false,
          generated_at: new Date().toISOString()
        })
      });
      return;
    }
    await route.continue();
  });
}

async function dismissFirstRunIfVisible(page: Page) {
  const backdrop = page.locator(".onboarding-backdrop").first();
  if (await backdrop.isVisible().catch(() => false)) {
    const button = page.locator(".onboarding-actions button").first();
    if (await button.isVisible().catch(() => false)) await button.click();
  }
}

async function openPage(page: Page, navIndex: number, key: string) {
  await dismissFirstRunIfVisible(page);
  const navItem = page.locator(".sidebar .nav-item").nth(navIndex);
  await expect(navItem, key).toBeVisible();
  await navItem.click();
  await expect(navItem).toHaveClass(/active/, { timeout: 5_000 });
  await expect(page.locator(".loading-state")).toHaveCount(0, { timeout: 15_000 }).catch(() => undefined);
  await expect(page.locator(".error-boundary")).toHaveCount(0);
  await expect(page.locator(".workspace")).toBeVisible();
}

async function layoutBox(page: Page) {
  return page.locator(".workspace").evaluate((node) => {
    const rect = node.getBoundingClientRect();
    return {
      height: Math.round(rect.height),
      width: Math.round(rect.width),
      htmlScrollWidth: document.documentElement.scrollWidth,
      bodyScrollWidth: document.body.scrollWidth,
      innerWidth: window.innerWidth
    };
  });
}

test("safe terminal buttons are wired, guarded, and keep layout stable", async ({ page }) => {
  const postCalls: string[] = [];
  page.on("request", (request) => {
    if (request.method() === "POST" && request.url().includes("/api/terminal/")) {
      postCalls.push(new URL(request.url()).pathname);
    }
  });

  await page.goto("./");
  for (const item of pages) {
    await openPage(page, item.navIndex, item.key);
    const layoutBefore = await layoutBox(page);
    const buttons = page.locator(safeButtonSelector);
    const count = Math.min(await buttons.count(), 3);
    for (let index = 0; index < count; index += 1) {
      const button = buttons.nth(index);
      if (!(await button.isVisible().catch(() => false))) continue;
      if (await button.isDisabled().catch(() => true)) continue;
      await button.click({ timeout: 5_000 }).catch(() => undefined);
      await expect(page.locator(".error-boundary")).toHaveCount(0);
      await expect(page.locator(".workspace")).toBeVisible();
    }
    const layoutAfter = await layoutBox(page);
    expect(Math.abs(layoutAfter.width - layoutBefore.width), `${item.key} width shift`).toBeLessThanOrEqual(24);
    expect(layoutAfter.htmlScrollWidth, `${item.key} document overflow`).toBeLessThanOrEqual(layoutAfter.innerWidth + 2);
    expect(layoutAfter.bodyScrollWidth, `${item.key} body overflow`).toBeLessThanOrEqual(layoutAfter.innerWidth + 2);
  }

  expect(postCalls.length).toBeGreaterThan(0);
  expect(postCalls.some((path) => path.includes("/system/shutdown"))).toBeFalsy();
});
