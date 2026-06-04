import { defineConfig, devices } from "@playwright/test";

const skipWebServer = process.env.SN_E2E_SKIP_WEBSERVER === "1";
const skipApiServer = process.env.SN_E2E_SKIP_API_SERVER === "1";
const apiPort = process.env.SN_E2E_API_PORT || "8765";
const vitePort = process.env.SN_E2E_VITE_PORT || "5173";
const reuseExistingServer = process.env.CI ? false : process.env.SN_E2E_REUSE_SERVER !== "0";
const baseURL = process.env.PLAYWRIGHT_BASE_URL || `http://127.0.0.1:${vitePort}/terminal/`;
const webServers = [
  ...(!skipApiServer
    ? [
        {
          command: `powershell -NoProfile -ExecutionPolicy Bypass -Command "$env:PYTHONPATH=(Resolve-Path '../src'); $env:SN_TERMINAL_API_PORT='${apiPort}'; Set-Location ..; python app_launcher.py --api-server --api-port ${apiPort}"`,
          url: `http://127.0.0.1:${apiPort}/api/terminal/docs`,
          reuseExistingServer,
          timeout: 180_000
        }
      ]
    : []),
  {
    command: `powershell -NoProfile -ExecutionPolicy Bypass -Command "$env:VITE_API_BASE_URL='http://127.0.0.1:${apiPort}'; & 'C:\\Program Files\\nodejs\\node.exe' .\\node_modules\\vite\\bin\\vite.js --host 127.0.0.1 --port ${vitePort} --strictPort"`,
    url: `http://127.0.0.1:${vitePort}/terminal/`,
    reuseExistingServer,
    timeout: 150_000
  }
];

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
  webServer: skipWebServer ? undefined : webServers,
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
