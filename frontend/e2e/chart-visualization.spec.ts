import { expect, test, type Page } from "@playwright/test";

test.setTimeout(180_000);

const forbiddenTerms = [
  "undefined",
  "null",
  "NaN",
  ["fake", "prediction"].join(" "),
  ["建议", "买入"].join(""),
  ["建议", "卖出"].join(""),
  ["保证", "盈利"].join(""),
  ["active", "live", "performance"].join(" ")
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

async function installChartMocks(page: Page) {
  await page.route("**/api/terminal/charts/price-history", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        schema_version: 1,
        chart_type: "price",
        x_field: "time",
        y_fields: ["open", "high", "low", "close"],
        units: { price: "CNY/ton" },
        source_files: ["sn_market_history.json"],
        points: [
          { time: "2026-05-20", open: 250000, high: 252000, low: 248000, close: 251000, volume: 9000 },
          { time: "2026-05-21", open: 251000, high: 253000, low: 250000, close: 252500, volume: 11000 },
          { time: "2026-05-22", open: 252500, high: 254000, low: 249500, close: 250500, volume: 10000 }
        ],
        status: "success",
        message_zh: "真实行情价格图表数据已读取。"
      })
    });
  });
  await page.route("**/api/terminal/market-analysis", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        status: "success",
        not_prediction: true,
        key_levels: { support_levels: [248000], resistance_levels: [254000], recent_high_20: 254000, recent_low_20: 248000 },
        trend: { short_term: "range", medium_term: "range", ma_structure: "mixed", momentum_score: 0.1 },
        volatility: { atr_14: 3200, realized_vol_20: 0.018, volatility_regime: "normal" },
        volume_liquidity: { volume_trend: "normal", volume_zscore: 0.3, open_interest_available: false },
        regime: { label: "RANGE", trend_score: 0.1, volatility_score: 0.4 },
        missing_fundamentals: ["basis", "inventory"],
        risk_flags: ["无 active 模型"],
        next_actions_zh: ["当前不生成预测"],
        disclaimer: "行情分析不构成投资建议，不代表预测。"
      })
    });
  });
  await page.route("**/api/terminal/providers/status-detail", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        market_provider_status: {
          final_status: "full_success",
          active_contract: "SN0",
          source: "akshare_history",
          realtime_attempts: [{ provider_name: "sina_realtime", symbol_used: "nf_SN0", success: true, row_count: 1 }],
          history_attempts: [{ provider_name: "akshare_history", symbol_used: "SN0", success: true, row_count: 3 }],
          shfe_attempts: [],
          cache_status: {}
        }
      })
    });
  });
  await page.route("**/api/terminal/research/equity-curve**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        schema_version: 1,
        research_only: true,
        chart_type: "equity_curve",
        points: [
          { ts: "2026-05-20", value: 1.0 },
          { ts: "2026-05-21", value: 1.01 },
          { ts: "2026-05-22", value: 1.005 }
        ],
        message_zh: "研究型 OOF 收益曲线已读取；不代表实盘表现。"
      })
    });
  });
  await page.route("**/api/terminal/research/backtest-report**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        status: "success",
        candidate_version: "v5",
        horizons: {
          "1d": {
            equity_curve: [
              { ts: "2026-05-20", value: 1.0 },
              { ts: "2026-05-21", value: 1.01 }
            ],
            drawdown_curve: [
              { ts: "2026-05-20", value: 0 },
              { ts: "2026-05-21", value: -0.01 }
            ],
            trades: [],
            metrics: { sharpe: 0.5, max_drawdown: -0.01 }
          }
        },
        markdown: "研究回测，不代表 live active 预测，不构成投资建议。"
      })
    });
  });
  await page.route("**/api/terminal/charts/forecast-path", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ schema_version: 1, points: [], message_zh: "暂无 active prediction path" })
    });
  });
  await page.route("**/api/terminal/models/active-status", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ exists: false, active: false, status: "missing", message_zh: "暂无 active model" })
    });
  });
}

async function clickNav(page: Page, index: number) {
  const item = page.locator(".sidebar .nav-item").nth(index);
  await expect(item).toBeVisible();
  await item.click();
  await expect(item).toHaveClass(/active/, { timeout: 5_000 });
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

async function expectNoBadText(page: Page) {
  const text = await page.locator("body").innerText();
  for (const term of forbiddenTerms) {
    expect(text).not.toContain(term);
  }
}

test("market chart renders real price and volume data with professional labels", async ({ page }) => {
  await installChartMocks(page);
  await page.goto("./");
  await clickNav(page, 0);

  await expect(page.locator("canvas, svg").first()).toBeVisible({ timeout: 20_000 });
  const text = await page.locator("body").innerText();
  expect(text).toMatch(/价格|行情|成交量|支撑|压力|Provider|SN0|琛屾儏/i);
  await expectNoBadText(page);
});

test("backtest chart renders research-only equity or professional empty state", async ({ page }) => {
  await installChartMocks(page);
  await page.goto("./");
  await clickNav(page, 6);

  await expect(page.locator("canvas, svg, .empty-state, .state-box").first()).toBeVisible({ timeout: 20_000 });
  const text = await page.locator("body").innerText();
  expect(text).toMatch(/研究回测|research|equity|收益曲线|回撤|DSR|PBO/i);
  expect(text).not.toContain(["active", "live", "performance"].join(" "));
  await expectNoBadText(page);
});

test("prediction chart stays empty without active model and no fake future line", async ({ page }) => {
  await installChartMocks(page);
  await page.goto("./");
  await clickNav(page, 7);

  const text = await page.locator("body").innerText();
  expect(text).toMatch(/active model|active prediction path|暂无|鏆傛棤/i);
  const forbiddenRegex = new RegExp(
    [
      ["fake", "prediction"].join(" "),
      ["建议", "买入"].join(""),
      ["建议", "卖出"].join(""),
      ["保证", "盈利"].join("")
    ].join("|"),
    "i"
  );
  expect(text).not.toMatch(forbiddenRegex);
});

test("chart pages do not horizontally overflow on mobile", async ({ page }) => {
  await installChartMocks(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("./");
  for (const index of [0, 4, 5]) {
    await clickNav(page, index);
    const sizes = await page.evaluate(() => ({
      html: document.documentElement.scrollWidth,
      body: document.body.scrollWidth,
      inner: window.innerWidth
    }));
    expect(sizes.html).toBeLessThanOrEqual(sizes.inner + 2);
    expect(sizes.body).toBeLessThanOrEqual(sizes.inner + 2);
  }
});
