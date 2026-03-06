/**
 * Aegis Demo Recorder v3 — All Features
 *
 * Records a comprehensive screen demo showcasing every feature:
 * 1. Dashboard overview (clean state)
 * 2. Refund workflow (Triage → Validation → SQL → Knowledge → HITL → Resolve)
 * 3. Observability metrics
 * 4. LangSmith Traces Panel
 * 5. Semantic Cache demo
 * 6. Edge Case: Typo correction
 * 7. Edge Case: Customer not found
 * 8. Ticket History
 * 9. Closing shot
 *
 * Usage:
 *   curl -X DELETE http://localhost:8000/api/cache
 *   node scripts/record-demo.mjs
 */

import { chromium } from "playwright";

const BASE_URL = "http://localhost:3000";
const API_URL = "http://localhost:8000";

function sleep(ms) {
    return new Promise((r) => setTimeout(r, ms));
}

/** Click Approve if the HITL modal is open */
async function approveIfModalOpen(page) {
    const approveBtn = page.locator(".btn-success:has-text('Approve')").first();
    if (await approveBtn.isVisible({ timeout: 500 }).catch(() => false)) {
        await approveBtn.click();
        console.log("  ✓ Auto-approved pending HITL action");
        await sleep(3000);
        return true;
    }
    return false;
}

/** Wait for the full workflow to reach a recognizable state */
async function waitForWorkflowState(page, timeoutMs = 120000) {
    const start = Date.now();
    while (Date.now() - start < timeoutMs) {
        // Check: HITL approval modal?
        const hitl = await page.locator("text=Human Approval Required").isVisible().catch(() => false);
        if (hitl) return "approval";

        // Check: Resolution Complete?
        const done = await page.locator("text=Resolution Complete").isVisible().catch(() => false);
        if (done) return "completed";

        // Check: Semantic cache hit?
        const cached = await page.locator("text=served from semantic cache").isVisible().catch(() => false);
        if (cached) return "cached";

        // Check: Disambiguation?
        const disambig = await page.locator("text=Select Customer").isVisible().catch(() => false);
        if (disambig) return "disambiguation";

        await sleep(2000);
    }
    return "timeout";
}

async function record() {
    console.log("🎬 Aegis Demo v3 — All Features\n");

    // Clear cache
    try {
        await fetch(`${API_URL}/api/cache`, { method: "DELETE" });
        console.log("✓ Cache cleared\n");
    } catch {
        console.log("⚠ Could not clear cache\n");
    }

    const browser = await chromium.launch({ headless: false });
    const context = await browser.newContext({
        viewport: { width: 1920, height: 1080 },
        recordVideo: { dir: "scripts/", size: { width: 1920, height: 1080 } },
        colorScheme: "dark",
    });
    const page = await context.newPage();

    // ═══════════════════════════════════════════════════
    // SCENE 1: DASHBOARD OVERVIEW [~5s]
    // ═══════════════════════════════════════════════════
    console.log("═══ Scene 1: Dashboard Overview ═══");
    await page.goto(BASE_URL);
    await page.waitForLoadState("networkidle");
    console.log("  ✓ Dashboard loaded");
    await sleep(5000);

    // ═══════════════════════════════════════════════════
    // SCENE 2: REFUND WORKFLOW [agent processing time]
    // ═══════════════════════════════════════════════════
    console.log("\n═══ Scene 2: Refund Workflow ═══");
    const refundBtn = page.locator("button.demo-btn").first();
    await refundBtn.click();
    console.log("  ✓ Clicked Refund preset");

    // Wait for the workflow to reach any state
    const refundResult = await waitForWorkflowState(page, 180000);
    console.log(`  → State: ${refundResult}`);

    if (refundResult === "approval") {
        console.log("  ✓ HITL Approval modal visible — holding for 6s");
        await sleep(6000);

        // Click Approve
        const approved = await approveIfModalOpen(page);
        if (approved) {
            // Wait for resolution after approval
            const postApproval = await waitForWorkflowState(page, 30000);
            console.log(`  → Post-approval state: ${postApproval}`);
        }
    }
    await sleep(5000);

    // ═══════════════════════════════════════════════════
    // SCENE 3: OBSERVABILITY METRICS [~8s]
    // ═══════════════════════════════════════════════════
    console.log("\n═══ Scene 3: Observability Metrics ═══");
    // Clear any stale modal first
    await approveIfModalOpen(page);

    const metricsSection = page.locator("text=Observability").first();
    if (await metricsSection.isVisible().catch(() => false)) {
        await metricsSection.scrollIntoViewIfNeeded();
        console.log("  ✓ Metrics panel visible");
    }
    await sleep(8000);

    // ═══════════════════════════════════════════════════
    // SCENE 4: LANGSMITH TRACES PANEL [~10s]
    // ═══════════════════════════════════════════════════
    console.log("\n═══ Scene 4: LangSmith Traces ═══");
    await approveIfModalOpen(page);

    const tracesBtn = page.locator("text=LangSmith Traces").first();
    if (await tracesBtn.isVisible().catch(() => false)) {
        try {
            await tracesBtn.click({ timeout: 5000 });
            console.log("  ✓ Opened Traces panel");

            // Wait for traces to finish loading
            try {
                await page.waitForSelector("text=Loading traces…", { state: "hidden", timeout: 30000 });
                console.log("  ✓ Traces loaded");
            } catch {
                console.log("  ⚠ Traces still loading after 30s");
            }

            // Hold on the loaded traces panel
            await sleep(8000);

            // Close with the close button
            const closeBtn = page.locator('[title="Close (Esc)"]').first();
            if (await closeBtn.isVisible().catch(() => false)) {
                await closeBtn.click();
            } else {
                await page.keyboard.press("Escape");
            }
            console.log("  ✓ Closed Traces panel");
            await sleep(2000);
        } catch (e) {
            console.log(`  ⚠ Could not click Traces: ${e.message?.slice(0, 60)}`);
        }
    } else {
        console.log("  ⚠ LangSmith Traces button not visible");
    }

    // ═══════════════════════════════════════════════════
    // SCENE 5: SEMANTIC CACHE [~10s]
    // ═══════════════════════════════════════════════════
    console.log("\n═══ Scene 5: Semantic Cache ═══");
    await approveIfModalOpen(page);

    // Ensure Quick Test tab is active
    const quickTab = page.locator("button:has-text('Quick Test')").first();
    if (await quickTab.isVisible().catch(() => false)) {
        await quickTab.click({ timeout: 3000 }).catch(() => { });
        await sleep(500);
    }

    // Try clicking Refund again with force to bypass any overlays
    try {
        const refundBtn2 = page.locator("button.demo-btn").first();
        await refundBtn2.click({ timeout: 5000 });
        console.log("  ✓ Re-submitted same ticket (cache demo)");

        const cacheResult = await waitForWorkflowState(page, 15000);
        console.log(`  → State: ${cacheResult}`);
    } catch (e) {
        console.log(`  ⚠ Could not click Refund: ${e.message?.slice(0, 60)}`);
    }
    await sleep(5000);

    // ═══════════════════════════════════════════════════
    // SCENE 6: EDGE CASE — Typo Correction [~40s]
    // ═══════════════════════════════════════════════════
    console.log("\n═══ Scene 6: Edge Case — Typo ═══");
    await approveIfModalOpen(page);

    const edgeTab = page.locator("button:has-text('Edge Cases')").first();
    try {
        await edgeTab.click({ timeout: 3000 });
        console.log("  ✓ Switched to Edge Cases tab");
        await sleep(2000);

        const typoBtn = page.locator("button.demo-btn:has-text('Typo')").first();
        await typoBtn.click({ timeout: 5000 });
        console.log("  ✓ Clicked Typo edge case");

        const typoResult = await waitForWorkflowState(page, 120000);
        console.log(`  → State: ${typoResult}`);

        if (typoResult === "approval") {
            await sleep(4000);
            await approveIfModalOpen(page);
            const postApproval = await waitForWorkflowState(page, 30000);
            console.log(`  → Post-approval: ${postApproval}`);
        }
        await sleep(5000);
    } catch (e) {
        console.log(`  ⚠ Edge case error: ${e.message?.slice(0, 80)}`);
    }

    // ═══════════════════════════════════════════════════
    // SCENE 7: EDGE CASE — Not Found [~30s]
    // ═══════════════════════════════════════════════════
    console.log("\n═══ Scene 7: Edge Case — Not Found ═══");
    await approveIfModalOpen(page);

    try {
        const notFoundBtn = page.locator("button.demo-btn:has-text('Not Found')").first();
        await notFoundBtn.click({ timeout: 5000 });
        console.log("  ✓ Clicked Not Found edge case");

        const nfResult = await waitForWorkflowState(page, 90000);
        console.log(`  → State: ${nfResult}`);
        await sleep(5000);
    } catch (e) {
        console.log(`  ⚠ Not Found error: ${e.message?.slice(0, 80)}`);
    }

    // ═══════════════════════════════════════════════════
    // SCENE 8: TICKET HISTORY [~5s]
    // ═══════════════════════════════════════════════════
    console.log("\n═══ Scene 8: Ticket History ═══");
    await approveIfModalOpen(page);

    const historySection = page.locator("text=Ticket History").first();
    if (await historySection.isVisible().catch(() => false)) {
        await historySection.scrollIntoViewIfNeeded();
        console.log("  ✓ Ticket History visible");
    }
    await sleep(5000);

    // ═══════════════════════════════════════════════════
    // SCENE 9: CLOSING SHOT [~5s]
    // ═══════════════════════════════════════════════════
    console.log("\n═══ Scene 9: Closing Shot ═══");
    await approveIfModalOpen(page);

    const qt = page.locator("button:has-text('Quick Test')").first();
    try { await qt.click({ timeout: 2000 }); } catch { }
    await page.evaluate(() => window.scrollTo(0, 0));
    await sleep(5000);

    // ── Done ──
    console.log("\n⏱  Recording complete (9 scenes)");

    await page.close();
    const video = page.video();
    if (video) {
        const path = await video.path();
        console.log(`🎬 Saved: ${path}`);
        console.log(`\nConvert:\n  ffmpeg -i ${path} -c:v libx264 -crf 18 scripts/aegis-demo-v3.mp4`);
    }

    await context.close();
    await browser.close();
    console.log("✅ Done!");
}

record().catch((err) => {
    console.error("Failed:", err);
    process.exit(1);
});
