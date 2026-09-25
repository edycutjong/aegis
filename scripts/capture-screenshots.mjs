/**
 * Aegis — README screenshots from a running deployment.
 *
 * Drives the real UI through real agent runs (real LLM calls, ~$0.01 total)
 * and writes the images the README embeds to docs/screenshots/.
 *
 * Usage:
 *   node scripts/capture-screenshots.mjs                       # http://localhost:3000
 *   BASE_URL=https://aegis.edycu.dev make screenshots # the live demo
 *
 * Needs Playwright's Chromium (installed by `cd frontend && npx playwright install chromium`).
 */

import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const { chromium } = createRequire(resolve(root, "frontend/package.json"))("playwright");

const BASE_URL = process.env.BASE_URL ?? "http://localhost:3000";
const OUT = resolve(root, "docs/screenshots");
const RUN_TIMEOUT = 120_000;
const DESKTOP = { width: 1440, height: 900 };
const MOBILE = { width: 390, height: 844 };

mkdirSync(OUT, { recursive: true });

async function open(browser, viewport) {
    const page = await browser.newPage({ viewport, deviceScaleFactor: 2 });
    await page.goto(BASE_URL, { waitUntil: "networkidle" });
    return page;
}

async function runPreset(page, name) {
    await page.getByRole("button", { name: new RegExp(`^${name}`, "i") }).first().click();
}

const approveButton = (page) => page.getByRole("button", { name: /approve/i });

async function shot(page, file) {
    await page.waitForTimeout(900); // let motion settle
    await page.screenshot({ path: resolve(OUT, file) });
    console.log(`  ✓ ${file}`);
}

const browser = await chromium.launch();
try {
    console.log(`Capturing from ${BASE_URL}`);

    // 1. First impression.
    let page = await open(browser, DESKTOP);
    await shot(page, "01-overview.png");

    // 2. The pause: a real refund held at the human gate. Then release it.
    await runPreset(page, "Double charge");
    await approveButton(page).waitFor({ timeout: RUN_TIMEOUT });
    await shot(page, "02-approval-gate.png");
    await approveButton(page).click();
    await page.locator("#result-title").waitFor({ timeout: RUN_TIMEOUT });
    await page.waitForTimeout(2500); // metrics poll
    await shot(page, "03-released.png");
    await page.close();

    // 3. SQL exfiltration: input screen flags it, the SQL guard blocks it.
    page = await open(browser, DESKTOP);
    await runPreset(page, "SQL exfiltration");
    await approveButton(page).waitFor({ timeout: RUN_TIMEOUT });
    const sql = page.getByText("SQL the agent wrote").first();
    await sql.scrollIntoViewIfNeeded();
    await page.evaluate(() => {
        const el = [...document.querySelectorAll("*")].find((n) => n.textContent?.trim().startsWith("SQL the agent wrote"));
        el?.scrollIntoView({ block: "start" });
    });
    await shot(page, "04-sql-guard.png");
    await approveButton(page).scrollIntoViewIfNeeded();
    await shot(page, "05-injection-escalated.png");
    await page.close();

    // 4. Mobile, held at the gate.
    page = await open(browser, MOBILE);
    await runPreset(page, "Prompt injection");
    await approveButton(page).waitFor({ timeout: RUN_TIMEOUT });
    await approveButton(page).scrollIntoViewIfNeeded();
    await shot(page, "06-mobile-gate.png");
    await page.close();
} finally {
    await browser.close();
}
