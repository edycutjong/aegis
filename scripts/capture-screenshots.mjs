/**
 * Aegis Screenshot Capture — Full Feature Coverage
 *
 * Captures polished screenshots of EVERY Aegis UI state at two viewport sizes:
 *
 *   readme/    — 1280×800 @2×  (GitHub README, renders well at ~800px content width)
 *   casestudy/ — 1440×900 @2×  (Portfolio case study hero images)
 *
 * Quick Test presets (6):
 *   01-dashboard              — Clean dashboard overview
 *   02-agent-thinking         — Agent processing with ThoughtStream
 *   03-refund-approve         — 💳 Refund HITL Approve flow
 *   04-refund-deny            — 💳 Refund HITL Deny flow
 *   05-technical-resolution   — 🔧 Technical auto-resolution
 *   06-billing-resolution     — 📄 Billing auto-resolution
 *   07-upgrade-resolution     — ⬆️  Upgrade auto-resolution
 *   08-reactivate-approve     — 🔓 Reactivate HITL Approve flow
 *   09-reactivate-deny        — 🔓 Reactivate HITL Deny flow
 *   10-suspend-approve        — 🔒 Suspend HITL Approve flow
 *   11-suspend-deny           — 🔒 Suspend HITL Deny flow
 *   12-cache-hit              — ⚡ Semantic cache instant response
 *
 * Edge Cases (5):
 *   13-edge-notfound          — 👻 Customer not found
 *   14-edge-mismatch          — 🔀 Name/ID mismatch
 *   15-edge-typo              — ✍️  Typo correction (fuzzy match)
 *   16-edge-nameonly           — 👤 Name-only lookup
 *   17-edge-cancelled         — 🚫 Cancelled account
 *
 * Observability & UI:
 *   18-metrics                — 📊 Observability panel
 *   19-traces                 — 🔭 LangSmith Traces overlay
 *   20-recent-tickets         — 📋 Ticket History with entries
 *   21-database               — 🗄️  Database explorer expanded
 *
 * Usage:
 *   docker compose up --build
 *   cd frontend && npm run dev
 *
 *   node scripts/capture-screenshots.mjs                    # capture all 21
 *   node scripts/capture-screenshots.mjs dashboard          # single shot
 *   node scripts/capture-screenshots.mjs refund-approve cache-hit metrics  # specific
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
    // Make sure we're on Quick Test tab
    const quickTestTab = page.locator("button:has-text('Quick Test')").first();
    if (await quickTestTab.isVisible().catch(() => false)) {
        await quickTestTab.click();
        await sleep(500);
    }
    await page.locator(`button.demo-btn:has-text('${label}')`).first().click({ timeout: 5000 });
    console.log(`    ✓ Clicked ${label} preset`);
}

/** Click an Edge Case preset button */
async function clickEdgeCase(page, label) {
    await page.locator("button:has-text('Edge Cases')").first().click({ timeout: 3000 });
    console.log("    ✓ Switched to Edge Cases tab");
    await sleep(1000);
    await page.locator(`button.demo-btn:has-text('${label}')`).first().click({ timeout: 5000 });
    console.log(`    ✓ Clicked ${label} edge case`);
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
async function captureAll(page, name) {
    for (const [variant, viewport] of Object.entries(VIEWPORTS)) {
        const dir = `${OUT_DIR}/${variant}`;
        mkdirSync(dir, { recursive: true });
        await page.setViewportSize(viewport);
        await sleep(500);
        const path = `${dir}/${name}.png`;
        await page.screenshot({ path, fullPage: false });
        console.log(`    📸 ${variant}: ${path}`);
    }
}

/** Run a Quick Test ticket and capture result (approve/deny/auto-resolve) */
async function runTicketShot(page, { presetLabel, shotName, hitl, action }) {
    await clearCache();
    await resetDashboard(page);
    await clickPreset(page, presetLabel);

    const result = await waitForState(page, 180000);
    console.log(`    → State: ${result}`);

    if (result === "approval" && hitl) {
        console.log(`    ✓ HITL modal visible — holding 2s`);
        await sleep(2000);

        if (action === "approve") {
            await page.locator(".btn-success:has-text('Approve')").first().click();
            console.log("    ✓ Clicked Approve");
            const post = await waitForState(page, 30000);
            console.log(`    → Post-approval: ${post}`);
            await sleep(3000);
        } else if (action === "deny") {
            await page.locator(".btn-danger:has-text('Deny')").first().click();
            console.log("    ✗ Clicked Deny");
            await sleep(5000);
        }
    } else if (result === "approval" && !hitl) {
        // Unexpected HITL — auto-approve so we can continue
        await page.locator(".btn-success:has-text('Approve')").first().click();
        const post = await waitForState(page, 30000);
        console.log(`    → Auto-approved: ${post}`);
        await sleep(3000);
    } else {
        await sleep(3000);
    }

    await captureAll(page, shotName);
}

/** Capture the HITL modal itself (before approve/deny) */
async function runHitlModalShot(page, { presetLabel, shotName }) {
    await clearCache();
    await resetDashboard(page);
    await clickPreset(page, presetLabel);

    const result = await waitForState(page, 180000);
    console.log(`    → State: ${result}`);

    if (result === "approval") {
        console.log("    ✓ HITL modal visible — capturing");
        await sleep(2000);
        await captureAll(page, shotName);
        // Approve so we leave clean state
        await page.locator(".btn-success:has-text('Approve')").first().click();
        await waitForState(page, 30000);
        await sleep(2000);
    } else {
        console.log(`    ⚠ Got ${result} instead of HITL modal — capturing anyway`);
        await sleep(2000);
        await captureAll(page, shotName);
    }
}

/** Run an Edge Case and capture result */
async function runEdgeCaseShot(page, { edgeLabel, shotName }) {
    await clearCache();
    await resetDashboard(page);
    await clickEdgeCase(page, edgeLabel);

    const result = await waitForState(page, 120000);
    console.log(`    → State: ${result}`);

    if (result === "approval") {
        await sleep(2000);
        await page.locator(".btn-success:has-text('Approve')").first().click();
        const post = await waitForState(page, 30000);
        console.log(`    → Post-approval: ${post}`);
    }
    await sleep(3000);
    await captureAll(page, shotName);
}

// ═══════════════════════════════════════════════════════════
// SCREENSHOT DEFINITIONS
// ═══════════════════════════════════════════════════════════

const SHOTS = {
    // ── Dashboard ──
    dashboard: {
        name: "01-dashboard",
        title: "Dashboard Overview",
        capture: async (page) => {
            await resetDashboard(page);
            console.log("    ✓ Dashboard loaded — clean state");
            await sleep(2000);
            await captureAll(page, "01-dashboard");
        },
    },

    // ── Agent Thinking ──
    "agent-thinking": {
        name: "02-agent-thinking",
        title: "Agent Processing (ThoughtStream)",
        capture: async (page) => {
            await clearCache();
            await resetDashboard(page);
            await clickPreset(page, "Technical");
            console.log("    ⏳ Waiting for agent to start thinking...");
            await sleep(5000);
            await captureAll(page, "02-agent-thinking");
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

    // ── Quick Test: Refund (HITL) ──
    "refund-hitl": {
        name: "03-refund-hitl",
        title: "💳 Refund — HITL Modal",
        capture: async (page) => {
            await runHitlModalShot(page, { presetLabel: "Refund", shotName: "03-refund-hitl" });
        },
    },
    "refund-approve": {
        name: "04-refund-approve",
        title: "💳 Refund — HITL Approve",
        capture: async (page) => {
            await runTicketShot(page, { presetLabel: "Refund", shotName: "04-refund-approve", hitl: true, action: "approve" });
        },
    },
    "refund-deny": {
        name: "05-refund-deny",
        title: "💳 Refund — HITL Deny",
        capture: async (page) => {
            await runTicketShot(page, { presetLabel: "Refund", shotName: "05-refund-deny", hitl: true, action: "deny" });
        },
    },

    // ── Quick Test: Technical (no HITL) ──
    "technical-resolution": {
        name: "06-technical-resolution",
        title: "🔧 Technical — Resolution",
        capture: async (page) => {
            await runTicketShot(page, { presetLabel: "Technical", shotName: "06-technical-resolution", hitl: false });
        },
    },

    // ── Quick Test: Billing (no HITL) ──
    "billing-resolution": {
        name: "07-billing-resolution",
        title: "📄 Billing — Resolution",
        capture: async (page) => {
            await runTicketShot(page, { presetLabel: "Billing", shotName: "07-billing-resolution", hitl: false });
        },
    },

    // ── Quick Test: Upgrade (no HITL) ──
    "upgrade-resolution": {
        name: "08-upgrade-resolution",
        title: "⬆️ Upgrade — Resolution",
        capture: async (page) => {
            await runTicketShot(page, { presetLabel: "Upgrade", shotName: "08-upgrade-resolution", hitl: false });
        },
    },

    // ── Quick Test: Reactivate (HITL) ──
    "reactivate-hitl": {
        name: "09-reactivate-hitl",
        title: "🔓 Reactivate — HITL Modal",
        capture: async (page) => {
            await runHitlModalShot(page, { presetLabel: "Reactivate", shotName: "09-reactivate-hitl" });
        },
    },
    "reactivate-approve": {
        name: "10-reactivate-approve",
        title: "🔓 Reactivate — HITL Approve",
        capture: async (page) => {
            await runTicketShot(page, { presetLabel: "Reactivate", shotName: "10-reactivate-approve", hitl: true, action: "approve" });
        },
    },
    "reactivate-deny": {
        name: "11-reactivate-deny",
        title: "🔓 Reactivate — HITL Deny",
        capture: async (page) => {
            await runTicketShot(page, { presetLabel: "Reactivate", shotName: "11-reactivate-deny", hitl: true, action: "deny" });
        },
    },

    // ── Quick Test: Suspend (HITL) ──
    "suspend-hitl": {
        name: "12-suspend-hitl",
        title: "🔒 Suspend — HITL Modal",
        capture: async (page) => {
            await runHitlModalShot(page, { presetLabel: "Suspend", shotName: "12-suspend-hitl" });
        },
    },
    "suspend-approve": {
        name: "13-suspend-approve",
        title: "🔒 Suspend — HITL Approve",
        capture: async (page) => {
            await runTicketShot(page, { presetLabel: "Suspend", shotName: "13-suspend-approve", hitl: true, action: "approve" });
        },
    },
    "suspend-deny": {
        name: "14-suspend-deny",
        title: "🔒 Suspend — HITL Deny",
        capture: async (page) => {
            await runTicketShot(page, { presetLabel: "Suspend", shotName: "14-suspend-deny", hitl: true, action: "deny" });
        },
    },

    // ── Semantic Cache ──
    "cache-hit": {
        name: "15-cache-hit",
        title: "⚡ Semantic Cache Hit",
        capture: async (page) => {
            // Warm the cache first
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

            // Re-submit for cache hit
            await resetDashboard(page);
            await clickPreset(page, "Billing");
            const result = await waitForState(page, 15000);
            console.log(`    → State: ${result}`);
            if (result === "cached") {
                console.log("    ⚡ Cache hit — capturing");
            }
            await sleep(2000);
            await captureAll(page, "15-cache-hit");
        },
    },

    // ── Edge Cases ──
    "edge-notfound": {
        name: "16-edge-notfound",
        title: "👻 Edge Case — Customer Not Found",
        capture: async (page) => {
            await runEdgeCaseShot(page, { edgeLabel: "Not Found", shotName: "13-edge-notfound" });
        },
    },
    "edge-mismatch": {
        name: "17-edge-mismatch",
        title: "🔀 Edge Case — Name/ID Mismatch",
        capture: async (page) => {
            await runEdgeCaseShot(page, { edgeLabel: "Mismatch", shotName: "14-edge-mismatch" });
        },
    },
    "edge-typo": {
        name: "18-edge-typo",
        title: "✍️ Edge Case — Typo Correction",
        capture: async (page) => {
            await runEdgeCaseShot(page, { edgeLabel: "Typo", shotName: "15-edge-typo" });
        },
    },
    "edge-nameonly": {
        name: "19-edge-nameonly",
        title: "👤 Edge Case — Name Only Lookup",
        capture: async (page) => {
            await runEdgeCaseShot(page, { edgeLabel: "Name Only", shotName: "16-edge-nameonly" });
        },
    },
    "edge-cancelled": {
        name: "20-edge-cancelled",
        title: "🚫 Edge Case — Cancelled Account",
        capture: async (page) => {
            await runEdgeCaseShot(page, { edgeLabel: "Cancelled", shotName: "17-edge-cancelled" });
        },
    },

    // ── Observability ──
    metrics: {
        name: "21-metrics",
        title: "📊 Observability Metrics",
        capture: async (page) => {
            await resetDashboard(page);
            const metricsPanel = page.locator("text=Observability").first();
            if (await metricsPanel.isVisible().catch(() => false)) {
                await metricsPanel.scrollIntoViewIfNeeded();
                console.log("    ✓ Metrics panel visible");
            }
            await sleep(2000);
            await captureAll(page, "18-metrics");
        },
    },

    traces: {
        name: "22-traces",
        title: "🔭 LangSmith Traces",
        capture: async (page) => {
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
            await captureAll(page, "19-traces");
            // Close traces
            const closeBtn = page.locator('[title="Close (Esc)"]').first();
            if (await closeBtn.isVisible().catch(() => false)) await closeBtn.click();
            else await page.keyboard.press("Escape");
            await sleep(1000);
        },
    },

    // ── Recent Tickets ──
    "recent-tickets": {
        name: "23-recent-tickets",
        title: "📋 Recent Tickets",
        capture: async (page) => {
            // By this point we've processed many tickets, so history should be populated
            await resetDashboard(page);
            await sleep(1000);

            // Scroll to the Ticket History section in the left panel
            const historySection = page.locator("text=Recent Tickets").first();
            if (await historySection.isVisible().catch(() => false)) {
                await historySection.scrollIntoViewIfNeeded();
                console.log("    ✓ Recent Tickets visible");
            } else {
                // Try alternate label
                const altHistory = page.locator("text=Ticket History").first();
                if (await altHistory.isVisible().catch(() => false)) {
                    await altHistory.scrollIntoViewIfNeeded();
                    console.log("    ✓ Ticket History visible");
                }
            }
            await sleep(2000);
            await captureAll(page, "20-recent-tickets");
        },
    },

    // ── Database ──
    database: {
        name: "24-database",
        title: "🗄️ Database Explorer",
        capture: async (page) => {
            await resetDashboard(page);
            const dbSection = page.locator("text=Database").first();
            if (await dbSection.isVisible().catch(() => false)) {
                await dbSection.scrollIntoViewIfNeeded();
                console.log("    ✓ Database section visible");
                await sleep(1000);
                const customersBtn = page.locator("text=Customers").first();
                if (await customersBtn.isVisible().catch(() => false)) {
                    await customersBtn.click();
                    console.log("    ✓ Expanded Customers table");
                    await sleep(2000);
                }
            }
            await captureAll(page, "21-database");
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

    console.log(`📸 Aegis Screenshot Capture — ${selected.length} of 24 shot(s)\n`);
    console.log(`   Viewports:`);
    for (const [name, vp] of Object.entries(VIEWPORTS)) {
        console.log(`     ${name}: ${vp.width}×${vp.height} @2×`);
    }
    console.log(`   Output: ${OUT_DIR}/\n`);

    // Ensure output directories
    for (const variant of Object.keys(VIEWPORTS)) {
        mkdirSync(`${OUT_DIR}/${variant}`, { recursive: true });
    }

    // Launch browser
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
            await shot.capture(page);
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
