/**
 * Aegis Demo Recorder v5 — Full Capability Showcase
 *
 * Records ONE comprehensive video demonstrating every Aegis feature:
 *
 *   1.  Dashboard overview (clean state)
 *   2.  💳 Refund — HITL Deny          (type → agent → HITL modal → Deny)
 *   3.  💳 Refund — HITL Approve       (type → agent → HITL modal → Approve → resolve)
 *   4.  💳 Refund — Semantic Cache     (re-submit same → instant cache hit)
 *   5.  🔧 Technical — Agent Flow      (no HITL, auto-resolve)
 *   6.  📄 Billing — Agent Flow        (no HITL, auto-resolve)
 *   7.  ⬆️  Upgrade — Agent Flow       (no HITL, auto-resolve)
 *   8.  🔓 Reactivate — HITL Approve   (type → agent → HITL → Approve)
 *   9.  🔒 Suspend — HITL Approve      (type → agent → HITL → Approve)
 *  10.  📊 Observability Metrics       (scroll right panel)
 *  11.  🔭 LangSmith Traces Panel      (open → view → close)
 *  12.  🗄️  Database Explorer           (expand Customers table)
 *  13.  ✍️  Edge Case — Typo            (type → fuzzy name matching)
 *  14.  👻 Edge Case — Not Found        (type → customer #999)
 *  15.  🔀 Edge Case — Mismatch        (type → name/ID mismatch)
 *  16.  👤 Edge Case — Name Only        (type → name-only lookup)
 *  17.  🚫 Edge Case — Cancelled        (type → cancelled account)
 *  18.  📋 Ticket History + Closing     (scroll to history → back to top)
 *
 * Usage:
 *   docker compose up --build
 *   node scripts/record-demo.mjs
 *
 * Output: scripts/aegis-demo-v5.webm
 * Convert: ffmpeg -i scripts/aegis-demo-v5.webm -c:v libx264 -preset slow -crf 14 scripts/aegis-demo-v5.mp4
 */

import { chromium } from "playwright";
import { renameSync } from "fs";

const BASE_URL = "http://localhost:3000";
const API_URL = "http://localhost:8000";
const VIEWPORT = { width: 1920, height: 1080 };

function sleep(ms) {
    return new Promise((r) => setTimeout(r, ms));
}

// ═══════════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════════

/** Inject click-ripple visualizer */
async function injectClickRipple(page) {
    await page.addInitScript(() => {
        const style = document.createElement("style");
        style.textContent = `
            @keyframes click-ripple {
                0%   { transform: translate(-50%,-50%) scale(0.3); opacity: 0.7; }
                100% { transform: translate(-50%,-50%) scale(2.2);  opacity: 0; }
            }
            .click-ripple {
                position: fixed;
                width: 30px; height: 30px;
                border-radius: 50%;
                border: 2.5px solid #3b82f6;
                pointer-events: none;
                z-index: 999999;
                animation: click-ripple 0.5s ease-out forwards;
            }
        `;
        document.addEventListener("DOMContentLoaded", () => document.head.appendChild(style));
        document.addEventListener("mousedown", (e) => {
            const el = document.createElement("div");
            el.className = "click-ripple";
            el.style.left = e.clientX + "px";
            el.style.top = e.clientY + "px";
            document.body.appendChild(el);
            setTimeout(() => el.remove(), 600);
        }, true);
    });
}

/** Click Approve if the HITL modal is open */
async function approveIfModalOpen(page) {
    const btn = page.locator(".btn-success:has-text('Approve')").first();
    if (await btn.isVisible({ timeout: 500 }).catch(() => false)) {
        await btn.click();
        console.log("    ✓ Auto-approved HITL action");
        await sleep(3000);
        return true;
    }
    return false;
}

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

/** Type text character-by-character with human-like timing */
async function humanType(page, selector, text, speed = "normal") {
    const el = page.locator(selector);
    await el.click();
    await sleep(300);
    if (speed === "instant") {
        await el.fill(text);
    } else {
        const delay = speed === "fast"
            ? () => 3 + Math.random() * 5
            : () => 10 + Math.random() * 30;
        for (const char of text) {
            await el.pressSequentially(char, { delay: 0 });
            await sleep(delay());
        }
    }
}

/** Type a message into the prompt box and click Submit Ticket */
async function typeAndSubmit(page, msg, speed = "normal") {
    const textarea = "textarea";
    console.log("    ✓ Focusing on prompt box...");
    await page.locator(textarea).click();
    await sleep(500);
    console.log(`    ⌨ Typing message... [${speed}]`);
    await humanType(page, textarea, msg, speed);
    await sleep(speed === "instant" ? 800 : 1500);
    await page.locator("button:has-text('Submit Ticket')").click();
    console.log("    ✓ Clicked Submit Ticket");
}

/** Reset page to fresh state — navigate back to dashboard */
async function resetToDashboard(page) {
    await page.goto(BASE_URL);
    await page.waitForLoadState("networkidle");
    console.log("    ✓ Dashboard reset");
    await sleep(1500);
}

// ═══════════════════════════════════════════════════════════
// TICKET MESSAGES (match frontend presets exactly)
// ═══════════════════════════════════════════════════════════

const MSG = {
    refund: "Customer #8 David Martinez says he was charged $49 twice this month for his Pro plan. Please investigate and process a refund if confirmed.",
    technical: "Customer #3 Maria Garcia reports getting 429 API rate limiting errors. Their enterprise plan should support 10K requests/min but they're hitting limits at 5K.",
    billing: "Customer #1 Sarah Chen asks if there's a discount for switching from monthly to annual billing on her Enterprise plan.",
    upgrade: "Customer #17 Sophia Lewis wants to upgrade from the Free plan to Pro. She wants to know if she'll lose any existing data during the upgrade.",
    reactivate: "Customer #5 Emily Davis reports her enterprise account was suspended after a failed payment. She has updated her payment method and needs reactivation.",
    suspend: "Customer #20 William Allen has violated our terms of service by sharing his API keys publicly. Please suspend his account immediately.",
};

// Edge Case messages (typed to look like real work)
const EDGE_MSG = {
    typo: "Customer #8 Davd Martines says he was charged $49 twice this month for his Pro plan. Please investigate and resolve.",
    notfound: "Customer #999 John Phantom wants a refund for the duplicate $49 charge on their Pro subscription from 2 days ago.",
    mismatch: "Customer #8 Sarah Chen says she was charged $49 twice this month for her Pro plan. Please investigate.",
    nameonly: "Emily Davis reports her enterprise account was suspended after a failed payment. She has updated her payment method and needs reactivation.",
    cancelled: "Customer #20 William Allen wants to know why his account was cancelled. He says he never requested cancellation and needs access restored.",
};

// ═══════════════════════════════════════════════════════════
// MAIN RECORDING
// ═══════════════════════════════════════════════════════════

async function record() {
    console.log("🎬 Aegis Demo v5 — Full Capability Showcase\n");

    // Clear cache
    try {
        await fetch(`${API_URL}/api/cache`, { method: "DELETE" });
        console.log("✓ Cache cleared\n");
    } catch {
        console.log("⚠ Could not clear cache (backend not running?)\n");
    }

    const browser = await chromium.launch({ headless: false });
    const context = await browser.newContext({
        viewport: VIEWPORT,
        deviceScaleFactor: 2,
        recordVideo: { dir: "scripts/", size: { width: VIEWPORT.width * 2, height: VIEWPORT.height * 2 } },
        colorScheme: "dark",
    });
    const page = await context.newPage();
    await injectClickRipple(page);

    let sceneNum = 0;
    const scene = (title) => console.log(`\n═══ Scene ${++sceneNum}: ${title} ═══`);

    // ──────────────────────────────────────────────────────
    // SCENE 1: Dashboard Overview
    // ──────────────────────────────────────────────────────
    scene("Dashboard Overview");
    await page.goto(BASE_URL);
    await page.waitForLoadState("networkidle");
    console.log("    ✓ Dashboard loaded");
    await sleep(4000);

    // ──────────────────────────────────────────────────────
    // SCENE 2: 💳 Refund — HITL Deny
    // ──────────────────────────────────────────────────────
    scene("💳 Refund — HITL Deny");
    await resetToDashboard(page);
    try { await fetch(`${API_URL}/api/cache`, { method: "DELETE" }); } catch { }
    await typeAndSubmit(page, MSG.refund, "normal");

    const denyResult = await waitForState(page, 180000);
    console.log(`    → State: ${denyResult}`);

    if (denyResult === "approval") {
        console.log("    ✓ HITL modal — holding 5s");
        await sleep(5000);
        await page.locator(".btn-danger:has-text('Deny')").first().click();
        console.log("    ✗ Clicked Deny");
        const postDeny = await waitForState(page, 15000);
        console.log(`    → Post-deny: ${postDeny}`);
        await sleep(5000);
    } else {
        console.log(`    ⚠ Got ${denyResult} instead of approval`);
        await sleep(3000);
    }

    // ──────────────────────────────────────────────────────
    // SCENE 3: 💳 Refund — HITL Approve
    // ──────────────────────────────────────────────────────
    scene("💳 Refund — HITL Approve");
    await resetToDashboard(page);
    try { await fetch(`${API_URL}/api/cache`, { method: "DELETE" }); } catch { }
    await typeAndSubmit(page, MSG.refund, "fast");

    const approveResult = await waitForState(page, 180000);
    console.log(`    → State: ${approveResult}`);

    if (approveResult === "approval") {
        console.log("    ✓ HITL modal — holding 5s");
        await sleep(5000);
        await page.locator(".btn-success:has-text('Approve')").first().click();
        console.log("    ✓ Clicked Approve");
        const postApprove = await waitForState(page, 30000);
        console.log(`    → Post-approval: ${postApprove}`);
        await sleep(5000);
    } else {
        console.log(`    ⚠ Got ${approveResult} instead of approval`);
        await sleep(3000);
    }

    // ──────────────────────────────────────────────────────
    // SCENE 4: 💳 Refund — Semantic Cache (instant)
    // ──────────────────────────────────────────────────────
    scene("💳 Refund — Semantic Cache");
    await resetToDashboard(page);
    // Cache should be warm from scene 3
    await typeAndSubmit(page, MSG.refund, "instant");

    const cacheResult = await waitForState(page, 15000);
    console.log(`    → State: ${cacheResult}`);
    if (cacheResult === "cached") {
        console.log("    ⚡ Cache hit — instant response!");
    }
    await sleep(5000);

    // ──────────────────────────────────────────────────────
    // SCENE 5: 🔧 Technical — Agent Flow (no HITL)
    // ──────────────────────────────────────────────────────
    scene("🔧 Technical — Agent Flow");
    await resetToDashboard(page);
    try { await fetch(`${API_URL}/api/cache`, { method: "DELETE" }); } catch { }
    await typeAndSubmit(page, MSG.technical, "normal");

    const techResult = await waitForState(page, 180000);
    console.log(`    → State: ${techResult}`);
    if (techResult === "approval") {
        await sleep(3000);
        await approveIfModalOpen(page);
        const post = await waitForState(page, 30000);
        console.log(`    → Post-approval: ${post}`);
    }
    await sleep(5000);

    // ──────────────────────────────────────────────────────
    // SCENE 6: 📄 Billing — Agent Flow (no HITL)
    // ──────────────────────────────────────────────────────
    scene("📄 Billing — Agent Flow");
    await resetToDashboard(page);
    try { await fetch(`${API_URL}/api/cache`, { method: "DELETE" }); } catch { }
    await typeAndSubmit(page, MSG.billing, "fast");

    const billResult = await waitForState(page, 180000);
    console.log(`    → State: ${billResult}`);
    if (billResult === "approval") {
        await sleep(3000);
        await approveIfModalOpen(page);
        const post = await waitForState(page, 30000);
        console.log(`    → Post-approval: ${post}`);
    }
    await sleep(5000);

    // ──────────────────────────────────────────────────────
    // SCENE 7: ⬆️ Upgrade — Agent Flow (no HITL)
    // ──────────────────────────────────────────────────────
    scene("⬆️ Upgrade — Agent Flow");
    await resetToDashboard(page);
    try { await fetch(`${API_URL}/api/cache`, { method: "DELETE" }); } catch { }
    await typeAndSubmit(page, MSG.upgrade, "fast");

    const upgradeResult = await waitForState(page, 180000);
    console.log(`    → State: ${upgradeResult}`);
    if (upgradeResult === "approval") {
        await sleep(3000);
        await approveIfModalOpen(page);
        const post = await waitForState(page, 30000);
        console.log(`    → Post-approval: ${post}`);
    }
    await sleep(5000);

    // ──────────────────────────────────────────────────────
    // SCENE 8: 🔓 Reactivate — HITL Approve
    // ──────────────────────────────────────────────────────
    scene("🔓 Reactivate — HITL Approve");
    await resetToDashboard(page);
    try { await fetch(`${API_URL}/api/cache`, { method: "DELETE" }); } catch { }
    await typeAndSubmit(page, MSG.reactivate, "fast");

    const reactResult = await waitForState(page, 180000);
    console.log(`    → State: ${reactResult}`);
    if (reactResult === "approval") {
        console.log("    ✓ HITL modal — holding 5s");
        await sleep(5000);
        await page.locator(".btn-success:has-text('Approve')").first().click();
        console.log("    ✓ Clicked Approve");
        const post = await waitForState(page, 30000);
        console.log(`    → Post-approval: ${post}`);
        await sleep(5000);
    } else {
        console.log(`    ⚠ Got ${reactResult} instead of approval`);
        await sleep(3000);
    }

    // ──────────────────────────────────────────────────────
    // SCENE 9: 🔒 Suspend — HITL Approve
    // ──────────────────────────────────────────────────────
    scene("🔒 Suspend — HITL Approve");
    await resetToDashboard(page);
    try { await fetch(`${API_URL}/api/cache`, { method: "DELETE" }); } catch { }
    await typeAndSubmit(page, MSG.suspend, "fast");

    const suspendResult = await waitForState(page, 180000);
    console.log(`    → State: ${suspendResult}`);
    if (suspendResult === "approval") {
        console.log("    ✓ HITL modal — holding 5s");
        await sleep(5000);
        await page.locator(".btn-success:has-text('Approve')").first().click();
        console.log("    ✓ Clicked Approve");
        const post = await waitForState(page, 30000);
        console.log(`    → Post-approval: ${post}`);
        await sleep(5000);
    } else {
        console.log(`    ⚠ Got ${suspendResult} instead of approval`);
        await sleep(3000);
    }

    // ──────────────────────────────────────────────────────
    // SCENE 10: 📊 Observability Metrics
    // ──────────────────────────────────────────────────────
    scene("📊 Observability Metrics");
    await resetToDashboard(page);
    const metricsPanel = page.locator("text=Observability").first();
    if (await metricsPanel.isVisible().catch(() => false)) {
        await metricsPanel.scrollIntoViewIfNeeded();
        console.log("    ✓ Metrics panel visible");
    }
    await sleep(8000);

    // ──────────────────────────────────────────────────────
    // SCENE 11: 🔭 LangSmith Traces Panel
    // ──────────────────────────────────────────────────────
    scene("🔭 LangSmith Traces");
    const tracesBtn = page.locator("text=LangSmith Traces").first();
    if (await tracesBtn.isVisible().catch(() => false)) {
        await tracesBtn.click({ timeout: 5000 });
        console.log("    ✓ Opened Traces panel");

        try {
            await page.waitForSelector("text=Loading traces…", { state: "hidden", timeout: 30000 });
            console.log("    ✓ Traces loaded");
        } catch {
            console.log("    ⚠ Traces still loading");
        }
        await sleep(8000);

        const closeBtn = page.locator('[title="Close (Esc)"]').first();
        if (await closeBtn.isVisible().catch(() => false)) await closeBtn.click();
        else await page.keyboard.press("Escape");
        console.log("    ✓ Closed Traces panel");
        await sleep(2000);
    }

    // ──────────────────────────────────────────────────────
    // SCENE 12: 🗄️ Database Explorer
    // ──────────────────────────────────────────────────────
    scene("🗄️ Database Explorer");
    await resetToDashboard(page);
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
    await sleep(5000);

    // ──────────────────────────────────────────────────────
    // SCENE 13: ✍️ Edge Case — Typo Correction (typed)
    // ──────────────────────────────────────────────────────
    scene("✍️ Edge Case — Typo Correction");
    await resetToDashboard(page);
    try { await fetch(`${API_URL}/api/cache`, { method: "DELETE" }); } catch { }
    await typeAndSubmit(page, EDGE_MSG.typo, "normal");

    const typoResult = await waitForState(page, 120000);
    console.log(`    → State: ${typoResult}`);
    if (typoResult === "approval") {
        await sleep(4000);
        await approveIfModalOpen(page);
        const post = await waitForState(page, 30000);
        console.log(`    → Post-approval: ${post}`);
    }
    await sleep(5000);

    // ──────────────────────────────────────────────────────
    // SCENE 14: 👻 Edge Case — Customer Not Found (typed)
    // ──────────────────────────────────────────────────────
    scene("👻 Edge Case — Customer Not Found");
    await resetToDashboard(page);
    try { await fetch(`${API_URL}/api/cache`, { method: "DELETE" }); } catch { }
    await typeAndSubmit(page, EDGE_MSG.notfound, "normal");

    const nfResult = await waitForState(page, 90000);
    console.log(`    → State: ${nfResult}`);
    await sleep(5000);

    // ──────────────────────────────────────────────────────
    // SCENE 15: 🔀 Edge Case — Name/ID Mismatch (typed)
    // ──────────────────────────────────────────────────────
    scene("🔀 Edge Case — Name/ID Mismatch");
    await resetToDashboard(page);
    try { await fetch(`${API_URL}/api/cache`, { method: "DELETE" }); } catch { }
    await typeAndSubmit(page, EDGE_MSG.mismatch, "normal");

    const mmResult = await waitForState(page, 120000);
    console.log(`    → State: ${mmResult}`);
    if (mmResult === "approval") {
        await sleep(4000);
        await approveIfModalOpen(page);
        const post = await waitForState(page, 30000);
        console.log(`    → Post-approval: ${post}`);
    }
    await sleep(5000);

    // ──────────────────────────────────────────────────────
    // SCENE 16: 👤 Edge Case — Name Only Lookup (typed)
    // ──────────────────────────────────────────────────────
    scene("👤 Edge Case — Name Only Lookup");
    await resetToDashboard(page);
    try { await fetch(`${API_URL}/api/cache`, { method: "DELETE" }); } catch { }
    await typeAndSubmit(page, EDGE_MSG.nameonly, "normal");

    const noResult = await waitForState(page, 120000);
    console.log(`    → State: ${noResult}`);
    if (noResult === "approval") {
        await sleep(4000);
        await approveIfModalOpen(page);
        const post = await waitForState(page, 30000);
        console.log(`    → Post-approval: ${post}`);
    }
    await sleep(5000);

    // ──────────────────────────────────────────────────────
    // SCENE 17: 🚫 Edge Case — Cancelled Account (typed)
    // ──────────────────────────────────────────────────────
    scene("🚫 Edge Case — Cancelled Account");
    await resetToDashboard(page);
    try { await fetch(`${API_URL}/api/cache`, { method: "DELETE" }); } catch { }
    await typeAndSubmit(page, EDGE_MSG.cancelled, "normal");

    const caResult = await waitForState(page, 120000);
    console.log(`    → State: ${caResult}`);
    if (caResult === "approval") {
        await sleep(4000);
        await approveIfModalOpen(page);
        const post = await waitForState(page, 30000);
        console.log(`    → Post-approval: ${post}`);
    }
    await sleep(5000);

    // ──────────────────────────────────────────────────────
    // SCENE 18: 📋 Ticket History + Closing
    // ──────────────────────────────────────────────────────
    scene("📋 Ticket History + Closing");
    await resetToDashboard(page);

    const historySection = page.locator("text=Ticket History").first();
    if (await historySection.isVisible().catch(() => false)) {
        await historySection.scrollIntoViewIfNeeded();
        console.log("    ✓ Ticket History visible");
    }
    await sleep(5000);

    // Scroll back to top for closing shot
    await page.evaluate(() => window.scrollTo(0, 0));
    await sleep(4000);

    // ── Done ──
    console.log(`\n⏱  Recording complete (${sceneNum} scenes)`);

    await page.close();
    const video = page.video();
    const outputFile = "scripts/aegis-demo-v5.webm";
    if (video) {
        const tmpPath = await video.path();
        await context.close();
        renameSync(tmpPath, outputFile);
        console.log(`🎬 Saved: ${outputFile}`);
        console.log(`\nConvert to MP4:`);
        console.log(`  ffmpeg -i ${outputFile} -c:v libx264 -preset slow -crf 14 scripts/aegis-demo-v5.mp4`);
    } else {
        await context.close();
    }

    await browser.close();
    console.log("✅ Done!");
}

record().catch((err) => {
    console.error("Failed:", err);
    process.exit(1);
});
