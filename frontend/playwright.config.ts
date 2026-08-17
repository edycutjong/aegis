import { defineConfig, devices } from "@playwright/test";

/**
 * E2E configuration for the Aegis dashboard.
 *
 * These tests run the frontend with NO backend reachable. That is deliberate:
 * they verify the dashboard shell renders and degrades gracefully without
 * credentials, which is what CI can honestly assert. Full-stack agent flows
 * need live LLM + Supabase keys and are exercised by
 * `scripts/capture-screenshots.mjs` against a running stack.
 */
export default defineConfig({
    testDir: "./e2e",
    fullyParallel: true,
    forbidOnly: !!process.env.CI,
    retries: process.env.CI ? 2 : 0,
    workers: process.env.CI ? 1 : undefined,
    reporter: process.env.CI ? "html" : "list",
    use: {
        baseURL: "http://localhost:3000",
        trace: "on-first-retry",
        screenshot: "only-on-failure",
    },
    projects: [
        { name: "chromium", use: { ...devices["Desktop Chrome"] } },
        { name: "mobile-chrome", use: { ...devices["Pixel 7"] } },
    ],
    webServer: {
        command: "npm run start",
        url: "http://localhost:3000",
        reuseExistingServer: !process.env.CI,
        timeout: 60_000,
    },
});
