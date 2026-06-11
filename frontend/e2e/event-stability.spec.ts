import { expect, test, type Page } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    window.localStorage.setItem("SN_ENABLE_DEV_CONSOLE", "1");
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
          latest_price: 250000,
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
  await page.route("**/api/terminal/charts/price-history", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ status: "empty", points: [], message_zh: "暂无可用图表数据" })
    });
  });
  await page.route("**/api/terminal/events/relevance-diagnostics", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        query_groups: {
          supply: { returned_count: 1, used_in_model_count: 1, avg_relevance: 0.91 }
        }
      })
    });
  });
  await page.route("**/api/terminal/events/source-quality-report", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        domains: [{ domain: "example.com", article_count: 1, used_in_model_count: 1, avg_source_reliability: 0.8 }]
      })
    });
  });
}

test("news event page tolerates scalar keyword hit fields from live providers", async ({ page }) => {
  await page.route("**/api/terminal/events/news", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        message_zh: "新闻事件已读取。",
        events: [
          {
            title: "锡供应扰动验证样本",
            source: "Example",
            published_at: "2026-05-31T10:00:00",
            category: "supply",
            impact_score: 0.7,
            sentiment_score: -0.2,
            relevance_score: 0.91,
            used_in_model: true,
            query_group: "supply",
            keyword_hits: "tin,supply",
            negative_keyword_hits: "rumor"
          }
        ]
      })
    });
  });

  await page.goto("./");
  const eventsNav = page.locator(".sidebar .nav-item").nth(1);
  await expect(eventsNav).toBeVisible();
  await eventsNav.click();
  await expect(eventsNav).toHaveClass(/active/, { timeout: 5_000 });

  await expect(page.getByText("锡供应扰动验证样本")).toBeVisible({ timeout: 15_000 });
  await expect(page.locator(".error-boundary")).toHaveCount(0);
  await expect(page.locator("body")).not.toContainText("join is not a function");
});
