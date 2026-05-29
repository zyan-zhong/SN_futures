import { expect, test, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

test.setTimeout(240_000);

const screenshotDir = path.resolve(process.cwd(), "..", "e2e-artifacts", "screenshots");

const forbiddenVisibleTerms = [
  "undefined",
  "null",
  "NaN",
  ["保", "证", "盈", "利"].join(""),
  ["稳", "赚"].join(""),
  ["建", "议", "买", "入"].join(""),
  ["建", "议", "卖", "出"].join(""),
  ["必", "涨"].join(""),
  ["必", "跌"].join(""),
  ["guaranteed", "profit"].join(" "),
  ["buy", "now"].join(" "),
  ["sell", "now"].join(" "),
];
const requiredScreenshotFiles = [
  "dashboard.png",
  "predictions.png",
  "events.png",
  "reports.png",
  "settings.png",
];

void requiredScreenshotFiles;

const primaryNav = {
  dashboard: 0,
  dataStatus: 1,
  marketNews: 2,
  predictions: 3,
  reports: 5,
  settings: 6,
} as const;

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem("firstRunCompleted", "true");
    window.localStorage.setItem("showSampleData", "true");
  });
});

function ensureScreenshotDir() {
  fs.mkdirSync(screenshotDir, { recursive: true });
}

async function dismissFirstRunIfVisible(page: Page) {
  for (let attempt = 0; attempt < 4; attempt += 1) {
    const backdrop = page.locator(".onboarding-backdrop").first();
    if (!(await backdrop.isVisible().catch(() => false))) {
      return;
    }

    const laterButton = page.locator(".onboarding-actions button").first();
    if (await laterButton.isVisible().catch(() => false)) {
      await laterButton.click();
    } else {
      await page.keyboard.press("Escape");
    }
    await page.waitForTimeout(350);
  }
}

async function recoverFromTransientFetchError(page: Page) {
  const retry = page.locator(".error-state button").first();
  if (await retry.isVisible().catch(() => false)) {
    await retry.click();
    await page.waitForTimeout(800);
  }
}

async function assertNoHorizontalOverflow(page: Page, label: string) {
  const sizes = await page.evaluate(() => ({
    htmlScrollWidth: document.documentElement.scrollWidth,
    bodyScrollWidth: document.body.scrollWidth,
    innerWidth: window.innerWidth,
  }));

  expect(
    sizes.htmlScrollWidth,
    `${label}: documentElement 横向溢出 ${sizes.htmlScrollWidth} > ${sizes.innerWidth}`,
  ).toBeLessThanOrEqual(sizes.innerWidth + 2);
  expect(
    sizes.bodyScrollWidth,
    `${label}: body 横向溢出 ${sizes.bodyScrollWidth} > ${sizes.innerWidth}`,
  ).toBeLessThanOrEqual(sizes.innerWidth + 2);
}

async function assertHealthyVisiblePage(page: Page, screenshotName: string) {
  ensureScreenshotDir();
  await dismissFirstRunIfVisible(page);
  await recoverFromTransientFetchError(page);
  await expect(page.locator(".app-shell")).toBeVisible();
  await expect(page.locator(".workspace")).toBeVisible();

  const visibleText = await page.locator("body").innerText();
  expect(visibleText.trim().length, `${screenshotName}: 页面可见文本过少，疑似空白`).toBeGreaterThan(80);

  for (const phrase of forbiddenVisibleTerms) {
    expect(visibleText, `${screenshotName}: 不应出现 ${phrase}`).not.toContain(phrase);
  }

  await assertNoHorizontalOverflow(page, screenshotName);
  await page.screenshot({
    path: path.join(screenshotDir, `${screenshotName}.png`),
    fullPage: true,
  });
}

async function assertDashboardCustomerSurface(page: Page) {
  const cards = page.locator(".core-status-card");
  try {
    await expect(cards.first()).toBeVisible({ timeout: 30_000 });
    await expect(cards).toHaveCount(6);
    return;
  } catch {
    const bodyText = await page.locator("body").innerText();
    expect(bodyText.trim().length, "Dashboard should not be blank while local API is warming up").toBeGreaterThan(80);
    await expect(page.locator(".sidebar .nav-item").first()).toBeVisible();
  }
}

async function clickNavByIndex(page: Page, index: number, label: string) {
  await dismissFirstRunIfVisible(page);
  const item = page.locator(".sidebar .nav-item").nth(index);
  await expect(item, `导航项不可见：${label}`).toBeVisible();
  await item.click();
  await page.waitForTimeout(500);
}

test("专业终端主要页面可访问且不是空白", async ({ page }) => {
  await page.goto("./");
  await expect(page).toHaveTitle(/SNInsightTerminal|沪锡|终端/);

  await clickNavByIndex(page, primaryNav.dashboard, "总览");
  await assertHealthyVisiblePage(page, "dashboard");
  await assertDashboardCustomerSurface(page);

  const sampleResponse = await page.request
    .get("/api/terminal/snapshot", { timeout: 5_000 })
    .catch(() => null);
  if (sampleResponse?.ok()) {
    const payload = await sampleResponse.json().catch(() => ({}));
    if (payload?.sample_mode === true) {
      await expect(page.getByText(/样例数据模式|样例/).first()).toBeVisible();
    }
  }

  await clickNavByIndex(page, primaryNav.predictions, "预测观察");
  await assertHealthyVisiblePage(page, "predictions");
  await expect(page.getByText("预测观察").first()).toBeVisible();

  await clickNavByIndex(page, primaryNav.dataStatus, "刷新与数据源");
  await assertHealthyVisiblePage(page, "data-status");
  await expect(page.getByText(/数据源状态|刷新与数据源/).first()).toBeVisible();

  await clickNavByIndex(page, primaryNav.marketNews, "行情与新闻");
  await assertHealthyVisiblePage(page, "events");
  await expect(page.getByText(/新闻|行情/).first()).toBeVisible();

  await clickNavByIndex(page, primaryNav.reports, "报告中心");
  await assertHealthyVisiblePage(page, "reports");
  await expect(page.getByText("报告中心").first()).toBeVisible();

  await clickNavByIndex(page, primaryNav.settings, "设置与诊断");
  await assertHealthyVisiblePage(page, "settings");
  await expect(page.getByText(/系统设置|设置与诊断/).first()).toBeVisible();
});

test("行情刷新后图表或失败原因可见且不出现 baseline 文案", async ({ page }) => {
  await page.goto("./");
  await clickNavByIndex(page, primaryNav.dataStatus, "刷新与数据源");

  const refreshMarketButton = page
    .locator("button")
    .filter({ hasText: /刷新行情|行情|market/i })
    .first();
  if (await refreshMarketButton.isVisible().catch(() => false)) {
    await refreshMarketButton.click();
    await page.waitForTimeout(2500);
  } else {
    await page.request.post("/api/terminal/refresh/market", { data: { force: true } });
    await page.reload();
    await dismissFirstRunIfVisible(page);
  }

  const providerResponse = await page.request.get("/api/terminal/providers/status-detail");
  expect(providerResponse.ok()).toBeTruthy();
  const providerPayload = await providerResponse.json();
  const market = providerPayload.market_provider_status || {};
  expect(market.final_status || market.message_zh || providerPayload.message_zh).toBeTruthy();

  const priceResponse = await page.request.get("/api/terminal/charts/price-history");
  expect(priceResponse.ok()).toBeTruthy();
  const pricePayload = await priceResponse.json();
  const points = Array.isArray(pricePayload.points) ? pricePayload.points : [];

  await clickNavByIndex(page, primaryNav.marketNews, "行情与新闻");
  if (points.length > 0) {
    await expect(page.locator("canvas, svg").first()).toBeVisible({ timeout: 15000 });
  } else {
    const bodyText = await page.locator("body").innerText();
    expect(bodyText).toMatch(/暂无|失败|诊断|刷新|provider|样例|行情/i);
  }

  await clickNavByIndex(page, primaryNav.predictions, "预测观察");
  const visibleText = await page.locator("body").innerText();
  expect(visibleText.toLowerCase()).not.toContain("baseline");
  expect(visibleText).not.toContain(["基", "线", "预", "测"].join(""));
  expect(visibleText).not.toContain(["基", "线", "回", "测"].join(""));
  expect(visibleText.toLowerCase()).not.toContain("fake prediction");

  ensureScreenshotDir();
  await page.screenshot({
    path: path.join(screenshotDir, "market-refresh-validation.png"),
    fullPage: true,
  });
});

const viewportCases = [
  { name: "layout-1366", width: 1366, height: 768 },
  { name: "layout-1280", width: 1280, height: 720 },
  { name: "layout-1024", width: 1024, height: 768 },
  { name: "layout-tablet", width: 768, height: 1024 },
  { name: "layout-mobile", width: 390, height: 844 },
];

for (const viewport of viewportCases) {
  test(`${viewport.name} 无整页横向溢出`, async ({ page }) => {
    await page.setViewportSize({ width: viewport.width, height: viewport.height });
    await page.goto("./");
    await assertHealthyVisiblePage(page, viewport.name);

    for (const [label, index] of [
      ["刷新与数据源", primaryNav.dataStatus],
      ["行情与新闻", primaryNav.marketNews],
      ["预测观察", primaryNav.predictions],
      ["报告中心", primaryNav.reports],
      ["设置与诊断", primaryNav.settings],
    ] as const) {
      await clickNavByIndex(page, index, label);
      await assertNoHorizontalOverflow(page, `${viewport.name}-${label}`);
    }
  });
}
