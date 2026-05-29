import { defineConfig, devices } from "@playwright/test";

const skipWebServer = process.env.SN_E2E_SKIP_WEBSERVER === "1";
const baseURL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:5173/terminal/";

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  reporter: [["list"], ["html", { outputFolder: "../e2e-artifacts/playwright-report", open: "never" }]],
  use: {
    baseURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off"
  },
  webServer: skipWebServer
    ? undefined
    : [
        {
          command:
            "powershell -NoProfile -ExecutionPolicy Bypass -Command \"$env:PYTHONPATH=(Resolve-Path '../src'); Set-Location ..; python app_launcher.py --api-server\"",
          url: "http://127.0.0.1:8765/api/terminal/docs",
          reuseExistingServer: true,
          timeout: 120_000
        },
        {
          command:
            "powershell -NoProfile -ExecutionPolicy Bypass -Command \"& 'C:\\Program Files\\nodejs\\node.exe' .\\node_modules\\vite\\bin\\vite.js --host 127.0.0.1 --port 5173\"",
          url: "http://127.0.0.1:5173/terminal/",
          reuseExistingServer: true,
          timeout: 120_000
        }
      ],
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        channel: "chrome",
        viewport: { width: 1440, height: 960 }
      }
    }
  ]
});
