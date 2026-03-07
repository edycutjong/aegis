/**
 * Aegis Screenshot Capture — README & Case Study Assets
 *
 * Captures polished screenshots of key Aegis UI states at two viewport sizes:
 *
 *   readme/    — 1280×800 @2×  (GitHub README, renders well at ~800px content width)
 *   casestudy/ — 1440×900 @2×  (Portfolio case study hero images)
 *
 * Captures:
 *   01-dashboard        — Clean dashboard overview
 *   02-agent-thinking   — Agent processing with ThoughtStream
 *   03-hitl-modal       — Human-in-the-Loop approval modal
 *   04-resolution       — Completed resolution state
 *   05-cache-hit        — Semantic cache instant response
 *   06-metrics          — Observability metrics panel
 *   07-traces           — LangSmith Traces overlay
 *   08-ticket-history   — Ticket history section
 *   09-edge-typo        — Edge case: fuzzy name matching
 *   10-database         — Database explorer expanded
 *
 * Usage:
 *   # Start the stack first
 *   docker compose up --build
 *   cd frontend && npm run dev
 *
 *   node scripts/capture-screenshots.mjs             # capture all
 *   node scripts/capture-screenshots.mjs dashboard    # capture one
 *   node scripts/capture-screenshots.mjs hitl metrics # capture specific
 *
 * Output: scripts/screenshots/readme/  and  scripts/screenshots/casestudy/
 */

import { chromium } from "playwright";
import { mkdirSync } from "fs";

const BASE_URL = "http://localhost:3000";
const API_URL = "http://localhost:8000";
const OUT_DIR = "scripts/screenshots";

const VIEWPORTS = {
    readme: { width: 1280, height: 800 },
    casestudy: { width: 1440, height: 900 },
};

function sleep(ms) {
    return new Promise((r) => setTimeout(r, ms));
}

// ═══════════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════════

/** Wait for a recognizable workflow state */
async function waitForState(page, timeoutMs = 120000) {
    const start = Date.now();
    while (Date.now() - start < timeoutMs) {
        if (await page.locator("text=Human Approval Required").isVisible().catch(() => false)) return "approval";
        if (await page.locator("text=Resolution Complete").isVisible().catch(() => false)) return "completed";
        if (await page.locator("text=Action denied").isVisible().catch(() => false)) return "denied";
        if (await page.locator("text=served from semantic cache").isVisible().catch(() => false)) return "cached";
        if (await page.locator("text=Select Customer").isVisible().catch(() => false)) return "disambiguation";
        await sleep(2000);
    }
    return "timeout";
}

/** Click a Quick Test preset button to submit a ticket */
async function clickPreset(page, label) {
    await page.locator(`button.demo-btn:has-text('${label}')`).first().click({ timeout: 5000 });
    console.log(`    ✓ Clicked ${label} preset`);
}

/** Reset to clean dashboard */
async function resetDashboard(page) {
    await page.goto(BASE_URL);
    await page.waitForLoadState("networkidle");
    await sleep(1500);
}

/** Clear the backend semantic cache */
async function clearCache() {
    try {
        await fetch(`${API_URL}/api/cache`, { method: "DELETE" });
    } catch { }
}

/** Capture screenshot at all viewport sizes */
async function captureAll(page, context, browser, name, label) {
    for (const [variant, viewport] of Object.entries(VIEWPORTS)) {
        const dir = `${OUT_DIR}/${variant}`;
        mkdirSync(dir, { recursive: true });

        // Resize viewport
        await page.setViewportSize(viewport);
        await sleep(500);

        const path = `${dir}/${name}.png`;
        await page.screenshot({ path, fullPage: false });
        console.log(`    📸 ${variant}: ${path}`);
    }
}

// ═══════════════════════════════════════════════════════════
// SCREENSHOT DEFINITIONS
// ═══════════════════════════════════════════════════════════

const SHOTS = {
    dashboard: {
        name: "01-dashboard",
        title: "Dashboard Overview",
        capture: async (page, context, browser) => {
            await resetDashboard(page);
            console.log("    ✓ Dashboard loaded — clean state");
            await sleep(2000);
            await captureAll(page, context, browser, "01-dashboard", "Dashboard");
        },
    },

    thinking: {
        name: "02-agent-thinking",
        title: "Agent Processing (ThoughtStream)",
        capture: async (page, context, browser) => {
            await clearCache();
            await resetDashboard(page);
            await clickPreset(page, "Technical");

            // Wait a few seconds for the agent to start processing
            console.log("    ⏳ Waiting for agent to start thinking...");
            await sleep(5000);

            await captureAll(page, context, browser, "02-agent-thinking", "Agent Thinking");

            // Wait for completion so next shot starts clean
            const result = await waitForState(page, 120000);
            console.log(`    → State: ${result}`);
            if (result === "approval") {
                await page.locator(".btn-success:has-text('Approve')").first().click();
                await waitForState(page, 30000);
            }
            await sleep(2000);
        },
    },

    hitl: {
        name: "03-hitl-modal",
        title: "HITL Approval Modal",
        capture: async (page, context, browser) => {
            await clearCache();
            await resetDashboard(page);
            await clickPreset(page, "Refund");

            console.log("    ⏳ Waiting for HITL modal...");
            const result = await waitForState(page, 180000);
            console.log(`    → State: ${result}`);

            if (result === "approval") {
                console.log("    ✓ HITL modal visible — capturing");
                await sleep(1500);
                await captureAll(page, context, browser, "03-hitl-modal", "HITL Modal");

                // Approve to continue
                await page.locator(".btn-success:has-text('Approve')").first().click();
                await waitForState(page, 30000);
                await sleep(2000);
            } else {
                console.log(`    ⚠ Got ${result} instead of approval — capturing anyway`);
                await captureAll(page, context, browser, "03-hitl-modal", "HITL Modal");
            }
        },
    },

    resolution: {
        name: "04-resolution",
        title: "Completed Resolution",
        capture: async (page, context, browser) => {
            await clearCache();
            await resetDashboard(page);
            await clickPreset(page, "Billing");

            console.log("    ⏳ Waiting for resolution...");
            const result = await waitForState(page, 180000);
            console.log(`    → State: ${result}`);

            if (result === "approval") {
                await page.locator(".btn-success:has-text('Approve')").first().click();
                const post = await waitForState(page, 30000);
                console.log(`    → Post-approval: ${post}`);
            }

            await sleep(3000);
            console.log("    ✓ Resolution state — capturing");
            await captureAll(page, context, browser, "04-resolution", "Resolution");
        },
    },

    cache: {
        name: "05-cache-hit",
        title: "Semantic Cache Hit",
        capture: async (page, context, browser) => {
            // First warm the cache
            await clearCache();
            await resetDashboard(page);
            await clickPreset(page, "Billing");
            const warmResult = await waitForState(page, 120000);
            if (warmResult === "approval") {
                await page.locator(".btn-success:has-text('Approve')").first().click();
                await waitForState(page, 30000);
            }
            console.log("    ✓ Cache warmed");
            await sleep(2000);

            // Now re-submit for cache hit
            await resetDashboard(page);
            await clickPreset(page, "Billing");
            const result = await waitForState(page, 15000);
            console.log(`    → State: ${result}`);

            if (result === "cached") {
                console.log("    ⚡ Cache hit — capturing");
            }
            await sleep(2000);
            await captureAll(page, context, browser, "05-cache-hit", "Cache Hit");
        },
    },

    metrics: {
        name: "06-metrics",
        title: "Observability Metrics",
        capture: async (page, context, browser) => {
            await resetDashboard(page);

            // Scroll the right panel to show metrics
            const metricsPanel = page.locator("text=Observability").first();
            if (await metricsPanel.isVisible().catch(() => false)) {
                await metricsPanel.scrollIntoViewIfNeeded();
                console.log("    ✓ Metrics panel visible");
            }
            await sleep(2000);
            await captureAll(page, context, browser, "06-metrics", "Metrics");
        },
    },

    traces: {
        name: "07-traces",
        title: "LangSmith Traces",
        capture: async (page, context, browser) => {
            await resetDashboard(page);

            const tracesBtn = page.locator("text=LangSmith Traces").first();
            if (await tracesBtn.isVisible().catch(() => false)) {
                await tracesBtn.click({ timeout: 5000 });
                console.log("    ✓ Opened Traces panel");

                try {
                    await page.waitForSelector("text=Loading traces…", { state: "hidden", timeout: 30000 });
                    console.log("    ✓ Traces loaded");
                } catch {
                    console.log("    ⚠ Traces may still be loading");
                }
                await sleep(3000);
            }
            await captureAll(page, context, browser, "07-traces", "Traces");

            // Close traces panel
            const closeBtn = page.locator('[title="Close (Esc)"]').first();
            if (await closeBtn.isVisible().catch(() => false)) await closeBtn.click();
            else await page.keyboard.press("Escape");
            await sleep(1000);
        },
    },

    history: {
        name: "08-ticket-history",
        title: "Ticket History",
        capture: async (page, context, browser) => {
            await resetDashboard(page);

            const section = page.locator("text=Ticket History").first();
            if (await section.isVisible().catch(() => false)) {
                await section.scrollIntoViewIfNeeded();
                console.log("    ✓ Ticket History visible");
            }
            await sleep(2000);
            await captureAll(page, context, browser, "08-ticket-history", "Ticket History");
        },
    },

    typo: {
        name: "09-edge-typo",
        title: "Edge Case — Typo Correction",
        capture: async (page, context, browser) => {
            await clearCache();
            await resetDashboard(page);

            await page.locator("button:has-text('Edge Cases')").first().click({ timeout: 3000 });
            console.log("    ✓ Switched to Edge Cases tab");
            await sleep(1500);

            await page.locator("button.demo-btn:has-text('Typo')").first().click({ timeout: 5000 });
            console.log("    ✓ Clicked Typo edge case");

            const result = await waitForState(page, 120000);
            console.log(`    → State: ${result}`);
            if (result === "approval") {
                await sleep(2000);
                await page.locator(".btn-success:has-text('Approve')").first().click();
                await waitForState(page, 30000);
            }
            await sleep(3000);
            await captureAll(page, context, browser, "09-edge-typo", "Typo Correction");
        },
    },

    database: {
        name: "10-database",
        title: "Database Explorer",
        capture: async (page, context, browser) => {
            await resetDashboard(page);

            // Scroll to database section and expand a table
            const dbSection = page.locator("text=Database").first();
            if (await dbSection.isVisible().catch(() => false)) {
                await dbSection.scrollIntoViewIfNeeded();
                console.log("    ✓ Database section visible");
                await sleep(1000);

                // Click on Customers table to expand
                const customersBtn = page.locator("text=Customers").first();
                if (await customersBtn.isVisible().catch(() => false)) {
                    await customersBtn.click();
                    console.log("    ✓ Expanded Customers table");
                    await sleep(2000);
                }
            }
            await captureAll(page, context, browser, "10-database", "Database Explorer");
        },
    },
};

// ═══════════════════════════════════════════════════════════
// MAIN
// ═══════════════════════════════════════════════════════════

async function main() {
    const args = process.argv.slice(2);
    const selected = args.length > 0
        ? args.filter((a) => SHOTS[a])
        : Object.keys(SHOTS);

    if (args.length > 0) {
        const invalid = args.filter((a) => !SHOTS[a]);
        if (invalid.length) {
            console.log(`⚠ Unknown shots: ${invalid.join(", ")}`);
            console.log(`  Available: ${Object.keys(SHOTS).join(", ")}`);
        }
    }

    console.log(`📸 Aegis Screenshot Capture — ${selected.length} shot(s)\n`);
    console.log(`   Viewports:`);
    for (const [name, vp] of Object.entries(VIEWPORTS)) {
        console.log(`     ${name}: ${vp.width}×${vp.height} @2×`);
    }
    console.log(`   Output: ${OUT_DIR}/\n`);

    // Ensure output directories
    for (const variant of Object.keys(VIEWPORTS)) {
        mkdirSync(`${OUT_DIR}/${variant}`, { recursive: true });
    }

    // Launch browser — start with readme viewport, will resize per-capture
    const browser = await chromium.launch({ headless: false });
    const context = await browser.newContext({
        viewport: VIEWPORTS.readme,
        deviceScaleFactor: 2,
        colorScheme: "dark",
    });
    const page = await context.newPage();

    let captured = 0;

    for (const key of selected) {
        const shot = SHOTS[key];
        console.log(`\n═══ ${shot.title} ═══`);
        try {
            await shot.capture(page, context, browser);
            captured++;
        } catch (err) {
            console.log(`  ✗ Failed: ${err.message?.slice(0, 120)}\n`);
        }
    }

    await context.close();
    await browser.close();

    console.log(`\n═══════════════════════════════════════`);
    console.log(`✅ Done! ${captured}/${selected.length} shots captured\n`);
    console.log(`   README screenshots:     ${OUT_DIR}/readme/`);
    console.log(`   Case study screenshots: ${OUT_DIR}/casestudy/`);
}

main().catch((err) => {
    console.error("Failed:", err);
    process.exit(1);
});
