import { expect, test } from "@playwright/test";

/**
 * Layout tests across the three breakpoints the dashboard is designed for.
 * The invariant that matters: the page never scrolls horizontally. Horizontal
 * overflow is the single most common way a dense dashboard breaks on mobile.
 */
const VIEWPORTS = [
    { name: "mobile", width: 375, height: 812 },
    { name: "tablet", width: 768, height: 1024 },
    { name: "desktop", width: 1440, height: 900 },
];

for (const viewport of VIEWPORTS) {
    test.describe(`${viewport.name} (${viewport.width}px)`, () => {
        test.use({ viewport: { width: viewport.width, height: viewport.height } });

        test("does not overflow horizontally", async ({ page }) => {
            await page.goto("/");

            const overflow = await page.evaluate(() => {
                const doc = document.documentElement;
                return doc.scrollWidth - doc.clientWidth;
            });

            // Allow 1px for sub-pixel rounding.
            expect(overflow).toBeLessThanOrEqual(1);
        });

        test("keeps the header and ticket input visible", async ({ page }) => {
            await page.goto("/");

            const heading = page.getByRole("heading", { name: "Aegis", level: 1 });
            await expect(heading).toBeVisible();

            const box = await heading.boundingBox();
            expect(box).not.toBeNull();
            expect(box!.x).toBeGreaterThanOrEqual(0);
            expect(box!.x + box!.width).toBeLessThanOrEqual(viewport.width + 1);

            await expect(
                page.getByPlaceholder(/Describe the support issue/i)
            ).toBeVisible();
        });

        test("submit control meets the minimum touch target", async ({ page }) => {
            await page.goto("/");

            const quickTest = page.getByRole("button", { name: /Quick Test/i });
            await expect(quickTest).toBeVisible();

            const box = await quickTest.boundingBox();
            expect(box).not.toBeNull();
            expect(box!.height).toBeGreaterThanOrEqual(28);
        });
    });
}
