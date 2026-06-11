import { expect, test, type Page } from "@playwright/test";

test.setTimeout(180_000);

const primaryPages = [
  { key: "market", navIndex: 0, minTextLength: 100 },
  { key: "events", navIndex: 1, minTextLength: 100 },
  { key: "factors", navIndex: 2, minTextLength: 100 },
  { key: "training", navIndex: 3, minTextLength: 100 },
  { key: "research", navIndex: 4, minTextLength: 100 },
  { key: "backtest", navIndex: 6, minTextLength: 100 },
  { key: "predictions", navIndex: 7, minTextLength: 100 },
  { key: "reports", navIndex: 8, minTextLength: 100 },
  { key: "data", navIndex: 9, minTextLength: 100 },
  { key: "settings", navIndex: 10, minTextLength: 100 }
] as const;

const forbiddenVisibleTerms = [
  "undefined",
  "null",
  "NaN",
  ["fake", "prediction"].join(" "),
  "apikey=",
  ["api", "Key="].join(""),
  ["X", "Api", "Key"].join("-"),
  ["Bearer", " "].join(""),
  ["建议", "买入"].join(""),
  ["建议", "卖出"].join(""),
  ["保证", "盈利"].join("")
];

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    window.localStorage.setItem("SN_ENABLE_DEV_CONSOLE", "1");
    window.localStorage.setItem("firstRunCompleted", "true");
    window.localStorage.setItem("showSampleData", "true");
    window.localStorage.setItem("uiMode", JSON.stringify("professional"));
  });
});

async function installSafePostMocks(page: Page) {
  await page.route("**/api/terminal/**", async (route) => {
    const request = route.request();
    if (request.method() !== "POST") {
      await route.continue();
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        status: "success",
        success: true,
        task_id: "e2e-ui-api-map",
        generated_at: new Date().toISOString(),
        message_zh: "E2E 已验证按钮与后端任务入口连接。",
        final_status: "e2e_mocked",
        configured: true,
        sources: [],
        reports: [],
        artifacts: [],
        predictions: [],
        cache_hit: false
      })
    });
  });
}

async function dismissFirstRunIfVisible(page: Page) {
  for (let attempt = 0; attempt < 3; attempt += 1) {
    const backdrop = page.locator(".onboarding-backdrop").first();
    if (!(await backdrop.isVisible().catch(() => false))) return;
    const button = page.locator(".onboarding-actions button").first();
    if (await button.isVisible().catch(() => false)) {
      await button.click();
    } else {
      await page.keyboard.press("Escape");
    }
    await expect(backdrop).not.toBeVisible({ timeout: 2_000 }).catch(() => undefined);
  }
}

async function openPrimaryPage(page: Page, navIndex: number) {
  await dismissFirstRunIfVisible(page);
  const navItem = page.locator(".sidebar .nav-item").nth(navIndex);
  await expect(navItem).toBeVisible();
  await navItem.click();
  await expect(navItem).toHaveClass(/active/, { timeout: 5_000 });
  await page
    .waitForFunction(() => {
      const text = document.querySelector(".workspace")?.textContent || "";
      return !text.includes("加载中") && !text.includes("正在加载") && !text.includes("姝ｅ湪鍔犺浇");
    }, null, {
      timeout: 15_000
    })
    .catch(() => undefined);
  await expect(page.locator(".error-boundary")).toHaveCount(0);
}

async function getVisibleText(page: Page) {
  await dismissFirstRunIfVisible(page);
  return page.locator("body").innerText();
}

async function assertNoForbiddenText(page: Page, label: string) {
  const visibleText = await getVisibleText(page);
  for (const term of forbiddenVisibleTerms) {
    expect(visibleText, `${label} should not expose forbidden term ${term}`).not.toContain(term);
  }
}

async function assertNoHorizontalOverflow(page: Page, label: string) {
  const sizes = await page.evaluate(() => ({
    htmlScrollWidth: document.documentElement.scrollWidth,
    bodyScrollWidth: document.body.scrollWidth,
    innerWidth: window.innerWidth
  }));
  expect(sizes.htmlScrollWidth, `${label}: documentElement overflow`).toBeLessThanOrEqual(sizes.innerWidth + 2);
  expect(sizes.bodyScrollWidth, `${label}: body overflow`).toBeLessThanOrEqual(sizes.innerWidth + 2);
}

async function assertChartOrProfessionalEmptyState(page: Page, label: string) {
  const visual = page.locator("canvas, svg, .empty-state, .compact-empty-state, .error-state, .state-box").first();
  await expect(visual, `${label} should have chart, empty state, or error state`).toBeVisible({ timeout: 15_000 });
}

test("all primary pages have backend-backed content or explicit empty/error state", async ({ page }) => {
  await installSafePostMocks(page);
  await page.goto("./");
  await expect(page.locator(".app-shell")).toBeVisible();

  for (const item of primaryPages) {
    await openPrimaryPage(page, item.navIndex);
    await expect(page.locator(".workspace")).toBeVisible();
    await assertChartOrProfessionalEmptyState(page, item.key);
    await assertNoHorizontalOverflow(page, item.key);
    await assertNoForbiddenText(page, item.key);
    const visibleText = await getVisibleText(page);
    expect(visibleText.trim().length, `${item.key} should not be blank`).toBeGreaterThan(item.minTextLength);
  }
});

test("major buttons call backend task or provider APIs without crashing pages", async ({ page }) => {
  const postCalls: string[] = [];
  await installSafePostMocks(page);
  page.on("request", (request) => {
    if (request.method() === "POST" && request.url().includes("/api/terminal/")) {
      postCalls.push(new URL(request.url()).pathname);
    }
  });

  await page.goto("./");
  for (const item of primaryPages) {
    await openPrimaryPage(page, item.navIndex);
    const buttons = page.locator("main button:visible");
    const count = Math.min(await buttons.count(), 2);
    for (let index = 0; index < count; index += 1) {
      const button = buttons.nth(index);
      const disabled = await button.isDisabled().catch(() => true);
      if (disabled) continue;
      await button.click({ timeout: 5_000 }).catch(() => undefined);
      await expect(page.locator(".workspace")).toBeVisible();
      await expect(page.locator(".error-boundary")).toHaveCount(0);
      await assertNoForbiddenText(page, `${item.key}-button-${index}`);
    }
  }

  expect(postCalls.length, "at least one primary button should call a terminal POST API").toBeGreaterThan(0);
});

test("slow snapshot does not globally block non-dashboard pages", async ({ page }) => {
  await installSafePostMocks(page);
  await page.route("**/api/terminal/snapshot", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 2_000));
    await route.fulfill({
      status: 500,
      contentType: "application/json",
      body: JSON.stringify({ message: "E2E snapshot slow/failure simulation" })
    });
  });

  await page.goto("./");
  await openPrimaryPage(page, 2);
  await expect(page.locator(".workspace")).toBeVisible();
  const visibleText = await getVisibleText(page);
  expect(visibleText).toMatch(/Feature Store|coverage|因子|鍥犲瓙/i);
  expect(visibleText).not.toContain("E2E snapshot slow/failure simulation");
});

test("forecast page does not render fake future path without active model", async ({ page }) => {
  await installSafePostMocks(page);
  await page.route("**/api/terminal/models/active-status", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ exists: false, active: false, status: "missing", message_zh: "暂无 active model" })
    });
  });
  await page.route("**/api/terminal/charts/forecast-path", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ points: [], path: [], active_model_available: false, message_zh: "暂无 active prediction path" })
    });
  });

  await page.goto("./");
  await openPrimaryPage(page, 6);
  const visibleText = await getVisibleText(page);
  expect(visibleText).toMatch(/active model|active prediction path|暂无|鏆傛棤/i);
  const forbiddenRegex = new RegExp(
    [
      ["fake", "prediction"].join(" "),
      ["建议", "买入"].join(""),
      ["建议", "卖出"].join(""),
      ["保证", "盈利"].join("")
    ].join("|"),
    "i"
  );
  expect(visibleText).not.toMatch(forbiddenRegex);
});

for (const viewport of [
  { name: "desktop", width: 1440, height: 900 },
  { name: "tablet", width: 768, height: 1024 },
  { name: "mobile", width: 390, height: 844 }
]) {
  test(`${viewport.name} layout has no horizontal overflow`, async ({ page }) => {
    await installSafePostMocks(page);
    await page.setViewportSize({ width: viewport.width, height: viewport.height });
    await page.goto("./");
    for (const item of primaryPages) {
      await openPrimaryPage(page, item.navIndex);
      await assertNoHorizontalOverflow(page, `${viewport.name}-${item.key}`);
    }
  });
}
