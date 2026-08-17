import { expect, test } from "@playwright/test";

/**
 * The agent flow itself needs live LLM + Supabase credentials, so CI cannot run
 * it. What CI *can* prove is the next most valuable thing: that the dashboard
 * fails safe when the backend is unreachable — no crash, no infinite spinner,
 * and above all no UI that looks like a successful resolution when nothing ran.
 *
 * The full-stack flow is exercised by `scripts/capture-screenshots.mjs` against
 * a running stack.
 */
test.describe("backend unreachable", () => {
    test.beforeEach(async ({ page }) => {
        // Fail every backend call outright, simulating a dead API.
        await page.route("**/api/**", (route) => route.abort());
    });

    test("shell survives failed API calls", async ({ page }) => {
        await page.goto("/");

        await expect(page.getByRole("heading", { name: "Aegis", level: 1 })).toBeVisible();
        await expect(
            page.getByPlaceholder(/Describe the support issue/i)
        ).toBeVisible();

        // Give failing fetches time to settle, then confirm nothing crashed.
        await page.waitForTimeout(1500);
        await expect(page.locator("nextjs-portal")).toHaveCount(0);
        await expect(page.getByRole("heading", { name: "Aegis", level: 1 })).toBeVisible();
    });

    test("never claims a resolution that did not happen", async ({ page }) => {
        await page.goto("/");

        const input = page.getByPlaceholder(/Describe the support issue/i);
        await input.fill("Customer #8 was double-charged $49 for their Pro plan");
        await page.waitForTimeout(1500);

        // With every API call aborted, no approval modal and no executed-action
        // language may appear. A UI that shows success here would be lying.
        await expect(page.getByText(/Action executed/i)).toHaveCount(0);
        await expect(page.getByText(/Refund processed/i)).toHaveCount(0);
        await expect(page.getByText(/Awaiting human approval/i)).toHaveCount(0);
    });
});
