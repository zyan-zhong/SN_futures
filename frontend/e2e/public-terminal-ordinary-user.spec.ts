import { expect, test, type Page } from "@playwright/test";

test.setTimeout(120_000);

const technicalTerms = [
  "provider",
  "smoke",
  "watermark",
  "manifest",
  "blocked",
  "baseline",
  "calibration",
  "feature store",
  "backtest",
  "Candidate Research",
  "Governance Console",
  "Managed Proxy",
  "v12"
];

async function installPublicTerminalMocks(page: Page) {
  const readiness = {
    status: "blocked",
    summary: "需要先配置或跳过数据源。",
    next_action: "open_setup",
    provider_smoke_passed: false,
    ready_for_refresh: false,
    blocking_reasons: ["provider_keys_missing"],
    data_watermark: {
      status: "blocked",
      reason: "missing_daily_bars",
      sample_data_used: false,
      baseline_used: false,
      customer_prediction_generated: false
    }
  };

  await page.route("**/api/terminal/snapshot-lite", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        sample_mode: false,
        predictions: [],
        summary: {
          system_status: "缺少数据源",
          current_signal: "暂无真实预测",
          data_quality_label: "数据不足",
          last_update_time: "2026-06-09T10:00:00+08:00"
        },
        data_status: { sources: [] }
      })
    });
  });
  await page.route("**/api/public-terminal/readiness", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(readiness) });
  });
  await page.route("**/api/public-terminal/prediction-status", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        prediction_status: {
          status: "blocked",
          dry_run: true,
          can_predict: false,
          reason: "missing_daily_bars",
          blocking_reasons: ["missing_daily_bars"],
          training_invoked: false,
          prediction_generated: false,
          backtest_invoked: false,
          customer_prediction_generated: false
        },
        training_invoked: false,
        prediction_generated: false,
        backtest_invoked: false,
        customer_prediction_generated: false
      })
    });
  });
  await page.route("**/api/public-terminal/settings/status", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        configured: false,
        masked: "",
        sources: [
          { id: "local_api_provider", label: "本地数据接口", configured: false, masked: "" },
          { id: "tushare", label: "Tushare", configured: false, masked: "" }
        ]
      })
    });
  });
  await page.route("**/api/public-terminal/settings/save", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ configured: true, masked: "tu****7890", raw_secret_returned: false })
    });
  });
  await page.route("**/api/public-terminal/provider-smoke", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        status: "blocked",
        error_code: "local_provider_not_configured",
        row_count: 0,
        source_statuses: [],
        manifest: { provider_id: "local_api_provider", row_count: 0 },
        training_invoked: false,
        prediction_generated: false,
        backtest_invoked: false
      })
    });
  });
  await page.route("**/api/public-terminal/refresh-data-status", async (route) => {
    await route.fulfill({
      status: 202,
      contentType: "application/json",
      body: JSON.stringify({ task_id: "ordinary-user-refresh", status: "queued" })
    });
  });
  await page.route("**/api/public-terminal/tasks/ordinary-user-refresh", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        task_id: "ordinary-user-refresh",
        status: "blocked",
        reason: "missing_daily_bars",
        training_invoked: false,
        prediction_generated: false,
        backtest_invoked: false
      })
    });
  });
  await page.route("**/api/public-terminal/market", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        market: {
          status: "blocked",
          reason: "missing_daily_bars",
          chart: [],
          latest_quote: null,
          sample_data_used: false,
          baseline_used: false,
          customer_prediction_generated: false
        }
      })
    });
  });
  await page.route("**/api/public-terminal/report", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        report: {
          status: "blocked",
          reason: "insufficient_data",
          provider_status: "not_configured",
          market_data_coverage: "empty",
          event_coverage: "empty",
          research_only: true,
          investment_advice: false,
          export_allowed: false
        }
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
}

async function launchAsFirstUser(page: Page) {
  await page.addInitScript(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    window.localStorage.setItem("firstRunCompleted", "true");
    window.localStorage.removeItem("uiMode");
    window.localStorage.removeItem("SN_ENABLE_DEV_CONSOLE");
    window.localStorage.removeItem("sn_enable_dev_console");
  });
  await installPublicTerminalMocks(page);
  await page.goto("./");
}

async function visibleText(page: Page) {
  return page.locator("body").innerText();
}

async function expectNoTechnicalTerms(page: Page, scope = page.locator("body")) {
  const text = (await scope.innerText()).toLowerCase();
  for (const term of technicalTerms) {
    expect(text, `visible copy should hide technical term: ${term}`).not.toContain(term.toLowerCase());
  }
}

test("ordinary user first launch shows customer shell, plain status, and next step", async ({ page }) => {
  await launchAsFirstUser(page);

  await expect(page.locator("[data-testid='simple-nav']")).toBeVisible();
  await expect(page.locator(".sidebar .nav-item")).toHaveCount(7);
  for (const label of ["Home", "Setup", "Data Status", "Market", "Events", "Reports", "Diagnostics"]) {
    await expect(page.getByRole("button", { name: new RegExp(label, "i") })).toBeVisible();
  }
  for (const forbidden of ["Candidate Research", "Governance Console", "Training Data", "Feature Store", "Managed Proxy"]) {
    await expect(page.getByText(forbidden)).toHaveCount(0);
  }

  const main = page.locator("main");
  await expect(main.getByText("当前状态").first()).toBeVisible();
  await expect(main.getByText("暂无真实预测").first()).toBeVisible();
  await expect(main.getByText("下一步").first()).toBeVisible();
  await expect(main.getByText("数据源检查").first()).toBeVisible();
  await expectNoTechnicalTerms(page);
});

test("setup path can be skipped and keeps key terms understandable", async ({ page }) => {
  await launchAsFirstUser(page);

  await page.getByRole("button", { name: /^Setup/i }).click();
  await expect(page.getByRole("heading", { name: "设置数据源" })).toBeVisible();
  await expect(page.getByLabel("数据源地址")).toBeVisible();
  await expect(page.getByLabel("访问密钥")).toBeVisible();
  await expect(page.getByRole("button", { name: "保存设置" })).toBeVisible();
  await expect(page.getByRole("button", { name: "运行数据源检查" })).toBeVisible();
  await expect(page.getByRole("button", { name: "跳过，稍后配置" })).toBeVisible();

  await page.getByRole("button", { name: "跳过，稍后配置" }).click();
  await expect(page.getByText("已跳过配置")).toBeVisible();
  await expect(page.getByText("下一步").first()).toBeVisible();
  await expectNoTechnicalTerms(page);
});

test("market and reports explain no-data state without sample chart or advice", async ({ page }) => {
  await launchAsFirstUser(page);

  await page.getByRole("button", { name: /^Market/i }).click();
  await expect(page.getByRole("heading", { name: "市场数据" })).toBeVisible();
  await expect(page.getByText("暂时没有可展示的行情图")).toBeVisible();
  await expect(page.getByText("缺少历史行情数据").first()).toBeVisible();
  await expect(page.locator("main canvas")).toHaveCount(0);

  await page.getByRole("button", { name: /^Reports/i }).click();
  await expect(page.getByRole("heading", { name: "报告" })).toBeVisible();
  await expect(page.getByText("数据不足").first()).toBeVisible();
  await expect(page.getByText("暂无真实预测").first()).toBeVisible();
  await expect(page.getByText("仅供研究参考").first()).toBeVisible();
  await expect(page.getByRole("button", { name: "导出报告" })).toBeDisabled();

  const text = await visibleText(page);
  expect(text).not.toMatch(/buy|sell|买入|卖出/i);
  await expectNoTechnicalTerms(page);
});

test("diagnostic details are collapsed until the user asks for them", async ({ page }) => {
  await launchAsFirstUser(page);

  const detailsSummary = page.locator("main").getByText("诊断详情").first();
  await expect(detailsSummary).toBeVisible();
  await expectNoTechnicalTerms(page);

  await detailsSummary.click();
  const text = (await visibleText(page)).toLowerCase();
  expect(text).toContain("provider");
  expect(text).toContain("smoke");
  expect(text).toContain("watermark");
});
