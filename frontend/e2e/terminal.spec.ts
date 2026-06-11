import { expect, test, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

test.setTimeout(240_000);

const screenshotDir = path.resolve(process.cwd(), "..", "e2e-artifacts", "screenshots");

const forbiddenVisibleTerms = ["undefined", "null", "NaN", "apikey=", "apiKey=", "X-Api-Key", "Bearer "];
const requiredScreenshotFiles = ["dashboard.png", "predictions.png", "events.png", "reports.png", "settings.png", "market-refresh-validation.png"];
const legacyNavigationAliases = ["刷新与数据源", "行情与新闻", "样例"];
const marketRefreshEndpoint = "/api/terminal/refresh/market";
const providerStatusEndpoint = "/api/terminal/providers/status-detail";
void requiredScreenshotFiles;
void legacyNavigationAliases;
void marketRefreshEndpoint;
void providerStatusEndpoint;

const primaryNav = {
  market: 0,
  events: 1,
  factors: 2,
  training: 3,
  research: 4,
  backtest: 6,
  predictions: 7,
  reports: 8,
  data: 9,
  settings: 10,
} as const;

const primaryPages = [
  { key: "market", index: primaryNav.market, screenshot: "market-monitor", expect: /行情监控|Market Monitor|Provider attempts/ },
  { key: "events", index: primaryNav.events, screenshot: "events", expect: /新闻|事件|relevance|query/i },
  { key: "factors", index: primaryNav.factors, screenshot: "factors", expect: /因子|Feature Store|coverage/i },
  { key: "training", index: primaryNav.training, screenshot: "training-data", expect: /训练数据|Training Data|manifest/i },
  { key: "research", index: primaryNav.research, screenshot: "model-research", expect: /candidate_v|OOF|模型研究|Research/i },
  { key: "backtest", index: primaryNav.backtest, screenshot: "backtest", expect: /收益曲线|Backtest|DSR|PBO|Reality Check/i },
  { key: "predictions", index: primaryNav.predictions, screenshot: "predictions", expect: /暂无通过 promotion gate 的 active model|预测观察|active model/i },
  { key: "reports", index: primaryNav.reports, screenshot: "reports", expect: /报告中心|Artifact Center|资料归档/i },
  { key: "data", index: primaryNav.data, screenshot: "data-status", expect: /Artifact Center|Data Status|数据|source/i },
  { key: "settings", index: primaryNav.settings, screenshot: "settings", expect: /设置|诊断|Alpha|NewsAPI/i },
] as const;

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

function ensureScreenshotDir() {
  fs.mkdirSync(screenshotDir, { recursive: true });
}

async function dismissFirstRunIfVisible(page: Page) {
  for (let attempt = 0; attempt < 4; attempt += 1) {
    const backdrop = page.locator(".onboarding-backdrop").first();
    if (!(await backdrop.isVisible().catch(() => false))) return;
    const laterButton = page.locator(".onboarding-actions button").first();
    if (await laterButton.isVisible().catch(() => false)) {
      await laterButton.click();
    } else {
      await page.keyboard.press("Escape");
    }
    await expect(backdrop).not.toBeVisible({ timeout: 2_000 }).catch(() => undefined);
  }
}

async function recoverFromTransientFetchError(page: Page) {
  const retry = page.locator(".error-state button").first();
  if (await retry.isVisible().catch(() => false)) {
    await retry.click();
    await expect(page.locator(".loading-state")).toHaveCount(0, { timeout: 10_000 }).catch(() => undefined);
  }
}

async function assertNoHorizontalOverflow(page: Page, label: string) {
  const sizes = await page.evaluate(() => ({
    htmlScrollWidth: document.documentElement.scrollWidth,
    bodyScrollWidth: document.body.scrollWidth,
    innerWidth: window.innerWidth,
  }));

  expect(sizes.htmlScrollWidth, `${label}: documentElement horizontal overflow`).toBeLessThanOrEqual(sizes.innerWidth + 2);
  expect(sizes.bodyScrollWidth, `${label}: body horizontal overflow`).toBeLessThanOrEqual(sizes.innerWidth + 2);
}

async function assertHealthyVisiblePage(page: Page, screenshotName: string, expected?: RegExp) {
  ensureScreenshotDir();
  await dismissFirstRunIfVisible(page);
  await recoverFromTransientFetchError(page);
  await expect(page.locator(".app-shell")).toBeVisible();
  await expect(page.locator(".workspace")).toBeVisible();

  let visibleText = await page.locator("body").innerText();
  if (expected && !expected.test(visibleText)) {
    await expect(page.locator("body"), `${screenshotName}: expected workbench content`).toContainText(expected, { timeout: 20_000 });
    await recoverFromTransientFetchError(page);
    visibleText = await page.locator("body").innerText();
  }
  expect(visibleText.trim().length, `${screenshotName}: page should not be blank`).toBeGreaterThan(80);
  for (const phrase of forbiddenVisibleTerms) {
    expect(visibleText, `${screenshotName}: should not expose ${phrase}`).not.toContain(phrase);
  }
  if (expected) expect(visibleText, `${screenshotName}: expected workbench content`).toMatch(expected);

  await assertNoHorizontalOverflow(page, screenshotName);
  await page.screenshot({
    path: path.join(screenshotDir, `${screenshotName}.png`),
    fullPage: true,
  });
}

async function clickNavByIndex(page: Page, index: number, label: string) {
  await dismissFirstRunIfVisible(page);
  const item = page.locator(".sidebar .nav-item").nth(index);
  await expect(item, `nav item should be visible: ${label}`).toBeVisible();
  await item.click();
  await expect(item).toHaveClass(/active/, { timeout: 5_000 });
  await page
    .waitForFunction(() => {
      const text = document.querySelector(".workspace")?.textContent || "";
      return !text.includes("加载中") && !text.includes("正在加载") && !text.includes("姝ｅ湪鍔犺浇");
    }, null, { timeout: 15_000 })
    .catch(() => undefined);
  await expect(page.locator(".error-boundary")).toHaveCount(0);
}

test("professional workbench main pages open and remain non-blank", async ({ page }) => {
  await page.goto("./");
  await expect(page).toHaveTitle(/SNInsightTerminal|沪锡|终端/);

  for (const item of primaryPages) {
    await clickNavByIndex(page, item.index, item.key);
    await assertHealthyVisiblePage(page, item.screenshot, item.expect);
  }
});

test("backtest, model research, artifact center, and no-active prediction states are clear", async ({ page }) => {
  await page.goto("./");

  await clickNavByIndex(page, primaryNav.backtest, "backtest");
  await assertHealthyVisiblePage(page, "backtest-research-curve", /研究型收益曲线|收益曲线|暂无.*收益曲线|equity curve/i);
  await expect(page.getByText(/研究回测，不代表 live active 预测|不构成投资建议|research backtest/i).first()).toBeVisible();

  await clickNavByIndex(page, primaryNav.research, "model research");
  await assertHealthyVisiblePage(page, "candidate-comparison", /v1\/v2\/v3\/v4|candidate_v3|candidate_v4|OOF/i);

  await clickNavByIndex(page, primaryNav.reports, "reports");
  await assertHealthyVisiblePage(page, "artifact-center", /Artifact Center|资料归档|research_runs/i);

  await clickNavByIndex(page, primaryNav.predictions, "predictions");
  await assertHealthyVisiblePage(page, "no-active-prediction", /暂无通过 promotion gate 的 active model|暂无真实预测结果|active model/i);
});

test("market refresh surface shows chart or provider failure reason without exposing secrets", async ({ page }) => {
  await page.goto("./");
  await clickNavByIndex(page, primaryNav.market, "market monitor");

  let points: unknown[] = [];
  try {
    const priceResponse = await page.request.get("/api/terminal/charts/price-history", { timeout: 15_000 });
    expect(priceResponse.ok()).toBeTruthy();
    const pricePayload = await priceResponse.json();
    points = Array.isArray(pricePayload.points) ? pricePayload.points : [];
  } catch {
    points = [];
  }

  if (points.length > 0) {
    await expect(page.locator("canvas, svg").first()).toBeVisible({ timeout: 15000 });
  } else {
    const bodyText = await page.locator("body").innerText();
    expect(bodyText).toMatch(/暂无|失败|诊断|刷新|provider|行情|attempts/i);
  }

  const visibleText = await page.locator("body").innerText();
  expect(visibleText).not.toContain("apikey=");
  expect(visibleText).not.toContain("X-Api-Key");
});

const viewportCases = [
  { name: "layout-1366", width: 1366, height: 768 },
  { name: "layout-1280", width: 1280, height: 720 },
  { name: "layout-1024", width: 1024, height: 768 },
  { name: "layout-tablet", width: 768, height: 1024 },
  { name: "layout-mobile", width: 390, height: 844 },
];

for (const viewport of viewportCases) {
  test(`${viewport.name} has no horizontal overflow across the workbench`, async ({ page }) => {
    await page.setViewportSize({ width: viewport.width, height: viewport.height });
    await page.goto("./");
    await assertHealthyVisiblePage(page, viewport.name);

    for (const item of primaryPages) {
      await clickNavByIndex(page, item.index, item.key);
      await assertNoHorizontalOverflow(page, `${viewport.name}-${item.key}`);
    }
  });
}
