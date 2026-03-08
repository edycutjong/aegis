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

async function captureDevMode(page, name) {
    try {
        // Button shows "👤 User" when dev mode is OFF — click it to enter dev mode
        const devToggle = page.locator('button:has-text("User")').first();
        if (await devToggle.isVisible({ timeout: 3000 }).catch(() => false)) {
            await devToggle.click({ timeout: 5000 });
            console.log("    ⚙ Switched to DEV mode");
            await sleep(1000);
            await captureAll(page, `${name}-dev`);
            // Button now shows "⚙ Dev" — click it to switch back to user mode
            const userToggle = page.locator('button:has-text("Dev")').first();
            if (await userToggle.isVisible({ timeout: 3000 }).catch(() => false)) {
                await userToggle.click({ timeout: 5000 });
                await sleep(500);
            }
        } else {
            console.log("    ⚠ DEV toggle not found — skipping dev capture");
        }
    } catch (err) {
        console.log(`    ⚠ DEV toggle error — ${err.message?.split('\n')[0] || err}`);
    }
}

/** Run a Quick Test ticket and capture result (approve/deny/auto-resolve) */
async function runTicketShot(page, { presetLabel, shotName, hitl, action }) {
    await clearCache();
    await resetDashboard(page);
    await clickPreset(page, presetLabel);

    const result = await waitForState(page, 60000);
    console.log(`    → State: ${result}`);

    if (result === "approval" && hitl) {
        // Wait for modal animation to stabilise before interacting
        try {
            await page.waitForSelector(".btn-success", { state: "visible", timeout: 10000 });
        } catch { /* proceed anyway */ }
        console.log(`    ✓ HITL modal ready — holding 1.5s`);
        await sleep(1500);

        if (action === "approve") {
            await page.locator(".btn-success:has-text('Approve')").first().click({ timeout: 5000 });
            console.log("    ✓ Clicked Approve");
            const post = await waitForState(page, 30000);
            console.log(`    → Post-approval: ${post}`);
            await sleep(3000);
        } else if (action === "deny") {
            await page.locator(".btn-danger:has-text('Deny')").first().click({ timeout: 5000 });
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
    await captureDevMode(page, shotName);
}

/**
 * Wait until the HITL modal is fully visible, then pause for the
 * entry animation — simple sequential waits, no async racing.
 */
async function waitForHitlModal(page, timeoutMs = 20000) {
    // 1. Wait for the modal heading to appear
    console.log("    ⏳ Waiting for HITL modal heading...");
    await page.waitForSelector("text=Human Approval Required", {
        state: "visible",
        timeout: timeoutMs,
    });
    console.log("    ✓ Modal heading visible");

    // 2. Wait for Deny button
    await page.waitForSelector(".btn-danger", { state: "visible", timeout: 5000 });
    console.log("    ✓ Deny button visible");

    // 3. Wait for Approve button
    await page.waitForSelector(".btn-success", { state: "visible", timeout: 5000 });
    console.log("    ✓ Approve button visible");

    // 4. Let the CSS entry animation finish before snapping
    await sleep(1500);
    console.log("    ✓ Modal ready — taking screenshot");
}


/**
 * All-in-one HITL capture — runs the preset twice:
 *   Pass 1: thinking → modal → deny    → deny-dev
 *   Pass 2: thinking → modal → approve → approve-dev
 *
 * Outputs: {base}-thinking, {base}-modal,
 *          {base}-deny,    {base}-deny-dev,
 *          {base}-approve, {base}-approve-dev
 */
async function runHitlModalShot(page, { presetLabel, shotBase }) {
    // ── Pass 1: Deny ──────────────────────────────────────────
    console.log("    [Pass 1] Starting deny run...");
    await clearCache();
    await resetDashboard(page);
    await clickPreset(page, presetLabel);

    // 1a. Thinking — capture a few seconds after submit
    console.log("    ⏳ Capturing thinking state...");
    await sleep(4000);
    await captureAll(page, `${shotBase}-thinking`);

    // 1b. Wait for HITL modal
    const r1 = await waitForState(page, 60000);
    console.log(`    → State: ${r1}`);

    if (r1 === "approval") {
        await waitForHitlModal(page);

        // 1c. Modal screenshot — modal is confirmed visible
        await captureAll(page, `${shotBase}-modal`);

        // 1d. Deny
        await page.locator(".btn-danger:has-text('Deny')").first().click({ timeout: 5000 }).catch(() => { });
        console.log("    ✗ Clicked Deny");
        await sleep(5000);

        // 1e. Deny result — user mode + dev mode
        await captureAll(page, `${shotBase}-deny`);
        await captureDevMode(page, `${shotBase}-deny`);
    } else {
        console.log(`    ⚠ Got ${r1} instead of HITL modal on Pass 1 — capturing anyway`);
        await sleep(2000);
        await captureAll(page, `${shotBase}-modal`);
    }

    // ── Pass 2: Approve ───────────────────────────────────────
    console.log("    [Pass 2] Starting approve run...");
    await clearCache();
    await resetDashboard(page);
    await clickPreset(page, presetLabel);

    // 2a. Thinking (re-run for approve session — skip re-capture, already done in pass 1)
    await sleep(4000);

    // 2b. Wait for HITL modal
    const r2 = await waitForState(page, 60000);
    console.log(`    → State: ${r2}`);

    if (r2 === "approval") {
        await waitForHitlModal(page);

        // 2c. Approve
        await page.locator(".btn-success:has-text('Approve')").first().click({ timeout: 5000 }).catch(() => { });
        console.log("    ✓ Clicked Approve");
        await waitForState(page, 30000);
        await sleep(2000);

        // 2d. Approve result — user mode + dev mode
        await captureAll(page, `${shotBase}-approve`);
        await captureDevMode(page, `${shotBase}-approve`);
    } else {
        console.log(`    ⚠ Got ${r2} instead of HITL modal on Pass 2 — capturing anyway`);
        await sleep(2000);
        await captureAll(page, `${shotBase}-approve`);
    }
}

/** Run an Edge Case and capture result */
async function runEdgeCaseShot(page, { edgeLabel, shotName }) {
    await clearCache();
    await resetDashboard(page);
    await clickEdgeCase(page, edgeLabel);

    const result = await waitForState(page, 60000);
    console.log(`    → State: ${result}`);

    if (result === "approval") {
        await sleep(2000);
        await page.locator(".btn-success:has-text('Approve')").first().click();
        const post = await waitForState(page, 30000);
        console.log(`    → Post-approval: ${post}`);
    }
    await sleep(3000);
    await captureAll(page, shotName);
    await captureDevMode(page, shotName);
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


    // ── Quick Test: Refund HITL (thinking + modal + approve/deny + dev modes) ──
    // Note: Both Refund and Reactivate presets auto-resolve (customer state already satisfied
    // in the DB). Suspend reliably triggers HITL regardless of prior runs.
    "refund-hitl": {
        name: "02-refund",
        title: "💳 Refund — Full HITL Suite",
        capture: async (page) => {
            await runHitlModalShot(page, { presetLabel: "Refund", shotBase: "02-refund" });
        },
    },

    // ── Quick Test: Technical (no HITL) ──
    "technical-hitl": {
        name: "03-technical-hitl",
        title: "🔧 Technical — Full HITL Suite",
        capture: async (page) => {
            await runHitlModalShot(page, { presetLabel: "Technical", shotBase: "03-technical-resolution" });
        },
    },

    // ── Quick Test: Billing (no HITL) ──
    "billing-resolution": {
        name: "04-billing-resolution",
        title: "📄 Billing — Resolution",
        capture: async (page) => {
            await runTicketShot(page, { presetLabel: "Billing", shotName: "04-billing-resolution", hitl: false });
        },
    },

    // ── Quick Test: Upgrade (no HITL) ──
    "upgrade-resolution": {
        name: "05-upgrade-resolution",
        title: "⬆️ Upgrade — Resolution",
        capture: async (page) => {
            await runHitlModalShot(page, { presetLabel: "Upgrade", shotBase: "05-upgrade-resolution" });
        },
    },

    // ── Quick Test: Reactivate — Full HITL Suite ──
    // Note: Uses Suspend preset since Reactivate auto-resolves when customer is already active.
    "reactivate-resolution": {
        name: "06-reactivate",
        title: "🔓 Reactivate — Resolution",
        capture: async (page) => {
            await runTicketShot(page, { presetLabel: "Reactivate", shotName: "06-reactivate", hitl: false });
        },
    },

    // ── Quick Test: Suspend — Full HITL Suite ──
    "suspend-hitl": {
        name: "07-suspend",
        title: "🔒 Suspend — Full HITL Suite",
        capture: async (page) => {
            await runTicketShot(page, { presetLabel: "Suspend", shotName: "07-suspend", hitl: false });
        },
    },

    // ── Semantic Cache ──
    "cache-hit": {
        name: "08-cache-hit",
        title: "⚡ Semantic Cache Hit",
        capture: async (page) => {
            // Warm the cache first
            await clearCache();
            await resetDashboard(page);
            await clickPreset(page, "Billing");
            const warmResult = await waitForState(page, 60000);
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
            await captureAll(page, "08-cache-hit");
        },
    },

    // ── Edge Cases ──
    "edge-notfound": {
        name: "09-edge-notfound",
        title: "👻 Edge Case — Customer Not Found",
        capture: async (page) => {
            await runEdgeCaseShot(page, { edgeLabel: "Not Found", shotName: "09-edge-notfound" });
        },
    },
    "edge-mismatch": {
        name: "10-edge-mismatch",
        title: "🔀 Edge Case — Name/ID Mismatch",
        capture: async (page) => {
            await runEdgeCaseShot(page, { edgeLabel: "Mismatch", shotName: "10-edge-mismatch" });
        },
    },
    "edge-typo": {
        name: "11-edge-typo",
        title: "✍️ Edge Case — Typo Correction",
        capture: async (page) => {
            await runEdgeCaseShot(page, { edgeLabel: "Typo", shotName: "11-edge-typo" });
        },
    },
    "edge-nameonly": {
        name: "12-edge-nameonly",
        title: "👤 Edge Case — Name Only Lookup",
        capture: async (page) => {
            await runEdgeCaseShot(page, { edgeLabel: "Name Only", shotName: "12-edge-nameonly" });
        },
    },
    "edge-cancelled": {
        name: "13-edge-cancelled",
        title: "🚫 Edge Case — Cancelled Account",
        capture: async (page) => {
            await runEdgeCaseShot(page, { edgeLabel: "Cancelled", shotName: "13-edge-cancelled" });
        },
    },

    // ── Observability ──
    metrics: {
        name: "14-metrics",
        title: "📊 Observability Metrics",
        capture: async (page) => {
            await resetDashboard(page);
            const metricsPanel = page.locator("text=Observability").first();
            if (await metricsPanel.isVisible().catch(() => false)) {
                await metricsPanel.scrollIntoViewIfNeeded();
                console.log("    ✓ Metrics panel visible");
            }
            await sleep(2000);
            await captureAll(page, "14-metrics");
        },
    },

    traces: {
        name: "15-traces",
        title: "🔭 LangSmith Traces",
        capture: async (page) => {
            await resetDashboard(page);
            // Wait for tracingStatus to resolve and button to appear
            await sleep(3000);
            const tracesBtn = page.locator("button:has-text('LangSmith Traces')").first();
            if (await tracesBtn.isVisible().catch(() => false)) {
                await tracesBtn.click({ timeout: 5000 });
                console.log("    ✓ Opened Traces panel");
                // Wait for traces to fully load — can take 30-60s on free tier
                try {
                    await page.waitForSelector("text=Loading traces…", { state: "hidden", timeout: 90000 });
                    console.log("    ✓ Traces loaded");
                } catch {
                    console.log("    ⚠ Traces still loading after 90s — capturing anyway");
                }
                // Let UI settle after load
                await sleep(2000);
            } else {
                console.log("    ⚠ LangSmith Traces button not visible (tracing may be disabled)");
            }
            await captureAll(page, "15-traces");

            // Expand each trace individually and capture a separate screenshot
            try {
                const traceRows = page.locator(".metric-card button.w-full");
                const count = await traceRows.count();
                for (let i = 0; i < count; i++) {
                    await traceRows.nth(i).click({ timeout: 3000 });
                    await sleep(800);
                    // Scroll expanded trace to top of panel
                    await traceRows.nth(i).evaluate(el => el.scrollIntoView({ block: "start", behavior: "instant" }));
                    await sleep(500);
                    console.log(`    ✓ Expanded trace ${i + 1}/${count}`);
                    await captureAll(page, `15-traces-${i + 1}`);
                    // Collapse before next
                    await traceRows.nth(i).click({ timeout: 3000 });
                    await sleep(300);
                }
            } catch (err) {
                console.log(`    ⚠ Could not expand traces — ${err.message?.split('\n')[0] || err}`);
            }

            // Close traces (use Escape — close button may be off-screen after layout changes)
            await page.keyboard.press("Escape");
            await sleep(1000);
        },
    },

    // ── Recent Tickets ──
    "recent-tickets": {
        name: "16-recent-tickets",
        title: "📋 Recent Tickets",
        capture: async (page) => {
            await resetDashboard(page);

            // Populate history with several diverse tickets
            const fills = ["Billing", "Technical", "Upgrade", "Billing", "Technical"];
            for (const preset of fills) {
                await clickPreset(page, preset);
                await waitForState(page, 30000);
                // Auto-approve any HITL that comes up so we don't block
                await page
                    .locator(".btn-success:has-text('Approve')")
                    .first()
                    .click({ timeout: 2000 })
                    .catch(() => { });
                await sleep(800);
            }
            await sleep(1000);

            // Expand the Recent Tickets accordion
            const header = page.locator(".ticket-history-header").first();
            if (await header.isVisible().catch(() => false)) {
                await header.click();
                console.log("    ✓ Ticket history expanded");
                await sleep(600); // let maxHeight transition finish
            } else {
                console.log("    ⚠ .ticket-history-header not found");
            }

            // Scroll it into view then take full-viewport screenshot
            await page.locator(".ticket-history-container").first()
                .scrollIntoViewIfNeeded().catch(() => { });
            await sleep(400);
            await captureAll(page, "16-recent-tickets");
        },
    },


    // ── Database ──
    database: {
        name: "17-database",
        title: "🗄️ Database Explorer",
        capture: async (page) => {
            await resetDashboard(page);

            // Scroll the DATABASE section into view so it's fully visible
            const dbSection = page.locator("text=DATABASE").first();
            if (await dbSection.isVisible().catch(() => false)) {
                await dbSection.scrollIntoViewIfNeeded();
                console.log("    ✓ Database section in view");
                await sleep(800);

                // Click Customers to expand the table
                const customersBtn = page.locator("text=Customers").first();
                if (await customersBtn.isVisible().catch(() => false)) {
                    await customersBtn.click();
                    console.log("    ✓ Expanded Customers table");
                    await sleep(2000);
                }

                // Scroll the expanded DB section back into view after expansion
                await dbSection.scrollIntoViewIfNeeded();
                await sleep(600);
            } else {
                console.log("    ⚠ DATABASE section not found");
            }
            await captureAll(page, "17-database");
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
