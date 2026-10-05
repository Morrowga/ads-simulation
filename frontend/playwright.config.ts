import { defineConfig, devices } from "@playwright/test";

/**
 * E2E against a running stack: web on BASE_URL (default http://localhost:3000), API on API_URL
 * (default http://localhost:8000/api/v1) and Mailpit on MAILPIT_URL (default http://localhost:8025).
 * Locally: `docker compose up -d` in the project root, then `npm run e2e`.
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 180_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : [["list"]],
  use: {
    baseURL: process.env.BASE_URL ?? "http://localhost:3000",
    // CI images may pin a different Chromium; point at it with PLAYWRIGHT_CHROMIUM_PATH.
    launchOptions: process.env.PLAYWRIGHT_CHROMIUM_PATH
      ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_PATH }
      : undefined,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    viewport: { width: 1280, height: 900 },
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile", use: { ...devices["Pixel 7"] }, testMatch: /mobile\.spec\.ts/ },
  ],
});
