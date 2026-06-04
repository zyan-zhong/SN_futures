import { expect, test, type Page } from "@playwright/test";

test.setTimeout(120_000);

const forbiddenVisibleTerms = ["undefined", "null", "NaN"];

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    window.localStorage.setItem("firstRunCompleted", "true");
    window.localStorage.setItem("showSampleData", "true");
    window.localStorage.setItem("uiMode", JSON.stringify("professional"));
  });
  await installBaseMocks(page);
});

async function installBaseMocks(page: Page) {
  await page.route("**/api/terminal/snapshot-lite", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        summary: {
          main_contract: "SN0",
          system_status: "E2E stable",
          current_signal: "观望",
          data_quality_label: "测试数据"
        },
        predictions: [],
        sample_mode: false
      })
    });
  });
  await page.route("**/api/terminal/tasks/recent**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ tasks: [] }) });
  });
  await page.route("**/api/terminal/backtest-diagnostics**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        horizon: "tomorrow",
        walk_forward_metrics: null,
        cost_sensitivity: null,
        by_regime: null,
        failure_reasons: null,
        promotion_gate_result: null
      })
    });
  });
  await page.route("**/api/terminal/validation/report**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(null) });
  });
}

async function openBacktestPage(page: Page) {
  await page.goto("./");
  const navItem = page.locator(".sidebar .nav-item").nth(6);
  await expect(navItem).toBeVisible();
  await navItem.click();
  await expect(navItem).toHaveClass(/active/, { timeout: 5_000 });
  await expect(page.getByText("回测验证 Backtest Validation")).toBeVisible({ timeout: 15_000 });
  await expect(page.locator(".chart-loading")).toHaveCount(0, { timeout: 15_000 });
  await expect(page.getByText(/加载中|正在加载/)).toHaveCount(0, { timeout: 15_000 });
  await expect(page.locator(".error-boundary")).toHaveCount(0);
}

async function expectNoBadText(page: Page) {
  const visibleText = await page.locator("body").innerText();
  for (const term of forbiddenVisibleTerms) {
    expect(visibleText).not.toContain(term);
  }
  await expect(page.locator(".error-boundary")).toHaveCount(0);
}

test("empty research backtest response renders a professional empty state", async ({ page }) => {
  await page.route("**/api/terminal/research/backtest-report**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(null) });
  });

  await openBacktestPage(page);

  await expect(page.getByText("暂无研究回测数据")).toBeVisible();
  await expect(page.getByText("暂无可用图表数据")).toBeVisible();
  await expectNoBadText(page);
});

test("partial research backtest response renders metrics or an equity curve", async ({ page }) => {
  await page.route("**/api/terminal/research/backtest-report**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        status: "success",
        candidate_version: "v4",
        horizons: {
          "1d": {
            status: "success",
            metrics: {
              trade_count: null,
              total_return: 0.012,
              max_drawdown: -0.02,
              sharpe: null,
              deflated_sharpe_ratio: null,
              probability_of_backtest_overfitting: null
            },
            equity_curve: [
              { ts: "2026-05-29", value: 1 },
              { ts: "2026-05-30", value: 1.012 }
            ],
            drawdown_curve: null
          },
          "5d": null
        },
        report_path: null
      })
    });
  });

  await openBacktestPage(page);

  await expect(page.getByRole("img", { name: "权益曲线图" })).toBeVisible({ timeout: 20_000 });
  await expect(page.locator(".data-table").first().getByText("1d")).toBeVisible();
  await expect(page.locator(".data-table").first().getByText("0.012")).toBeVisible();
  await expect(page.getByText("暂无可用回撤图数据")).toBeVisible();
  await expectNoBadText(page);
});
