import { expect, test } from "@playwright/test";

/**
 * Smoke test — the dashboard must load and stay usable with no backend and no
 * API keys. A blank page or a Next.js error overlay here means the shell is
 * coupled to a live backend, which would make the app unshippable as a demo.
 */
test.describe("dashboard shell (no backend)", () => {
    test("renders the core UI without a reachable API", async ({ page }) => {
        await page.goto("/");

        await expect(page).toHaveTitle(/Aegis/);
        await expect(page.getByRole("heading", { name: "Aegis", level: 1 })).toBeVisible();

        // The ticket input is the primary affordance — it must exist offline.
        await expect(
            page.getByPlaceholder(/Describe the support issue/i)
        ).toBeVisible();

        // Example tickets are static; they must not depend on the backend.
        await expect(page.getByRole("tab", { name: /Scenarios/i })).toBeVisible();
        await expect(page.getByRole("button", { name: /Double charge/i }).first()).toBeVisible();

        // First-run clarity: the pitch and the pipeline explain the product.
        await expect(page.getByRole("heading", { name: /You release the action/i })).toBeVisible();
        await expect(page.getByRole("list", { name: "Agent pipeline" })).toBeVisible();
    });

    test("shows no Next.js error overlay", async ({ page }) => {
        await page.goto("/");

        // Next.js dev/prod error overlays render in these portals.
        await expect(page.locator("nextjs-portal")).toHaveCount(0);
        await expect(page.getByText("Application error")).toHaveCount(0);
        await expect(page.getByText("Unhandled Runtime Error")).toHaveCount(0);
    });

    test("declares the metadata a shared link needs", async ({ page }) => {
        await page.goto("/");

        const description = page.locator('meta[name="description"]');
        await expect(description).toHaveAttribute("content", /.{40,}/);

        const ogTitle = page.locator('meta[property="og:title"]');
        await expect(ogTitle).toHaveAttribute("content", /Aegis/);

        // A large-image card needs an absolute image URL, or previews render blank.
        await expect(page.locator('meta[property="og:image"]')).toHaveAttribute("content", /^https:\/\/.+\/og\.png$/);
        await expect(page.locator('meta[name="twitter:image"]')).toHaveAttribute("content", /^https:\/\/.+\/og\.png$/);
        await expect(page.locator('link[rel="apple-touch-icon"]')).toHaveAttribute("href", /apple-touch-icon\.png/);
    });
});
