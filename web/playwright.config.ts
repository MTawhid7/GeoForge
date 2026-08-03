import { defineConfig, devices } from "@playwright/test";

// The e2e run serves the *fixture* bank, not whatever `make bank` last produced: a happy-path
// test that changes meaning when the generator's seed corpus moves is not a test. It is served
// over real HTTP by `vite preview` so the manifest → shard fetch chain is genuinely exercised,
// which is the part jsdom cannot check.
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? "github" : "list",
  use: { baseURL: "http://127.0.0.1:4173", trace: "on-first-retry" },
  projects: [
    { name: "mobile", use: { ...devices["Pixel 7"] } },
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
  ],
  webServer: {
    command: "npm run bank:fixture && npm run build && npm run preview -- --port 4173",
    url: "http://127.0.0.1:4173",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
