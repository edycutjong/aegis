/**
 * Aegis Clip Recorder — Individual Scene Clips
 *
 * Records separate video clips for each feature/scene.
 * Each clip is its own .webm file in scripts/clips/.
 * Viewport: 1920×1080 (Loom-proportional 16:9).
 *
 * Usage:
 *   # Start the stack first (docker compose up, frontend dev server)
 *   curl -X DELETE http://localhost:8000/api/cache
 *   node scripts/record-clips.mjs                        # record all clips
 *   node scripts/record-clips.mjs dashboard              # record single clip
 *   node scripts/record-clips.mjs refund-deny metrics typo  # record specific clips
 *
 * Clips are saved to scripts/clips/<name>.webm
 * Convert:  ffmpeg -i scripts/clips/01-dashboard.webm -c:v libx264 -crf 18 scripts/clips/01-dashboard.mp4
 */

import { chromium } from "playwright";
import { mkdirSync, renameSync } from "fs";

const BASE_URL = "http://localhost:3000";
const API_URL = "http://localhost:8000";
const CLIPS_DIR = "scripts/clips";
const VIEWPORT = { width: 1920, height: 1080 };

function sleep(ms) {
    return new Promise((r) => setTimeout(r, ms));
}

/** Clear the backend semantic cache */
async function clearCache() {
    try { await fetch(`${API_URL}/api/cache`, { method: "DELETE" }); } catch { }
}

/** Reset to clean dashboard */
async function resetDashboard(page) {
    await page.goto(BASE_URL);
    await page.waitForLoadState("networkidle");
    await sleep(1500);
}

/** Click a Quick Test preset button to submit a ticket */
async function clickPreset(page, label) {
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

/**
 * Wait until the HITL modal is fully visible + entry animation done.
 */
async function waitForHitlModal(page, timeoutMs = 20000) {
    console.log("    ⏳ Waiting for HITL modal...");
    await page.waitForSelector("text=Human Approval Required", { state: "visible", timeout: timeoutMs });
    await page.waitForSelector(".btn-danger", { state: "visible", timeout: 5000 });
    await page.waitForSelector(".btn-success", { state: "visible", timeout: 5000 });
    await sleep(1500);
    console.log("    ✓ HITL modal ready");
}

/** Inject click-ripple visualizer into page */
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

/** Auto-approve HITL modal if open */
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

/** Create a new recording context + page (each clip = its own context for separate video) */
async function createClipContext(browser) {
    const context = await browser.newContext({
        viewport: VIEWPORT,
        deviceScaleFactor: 2, // Retina 2× — renders crisp text and UI
        recordVideo: { dir: CLIPS_DIR, size: { width: VIEWPORT.width * 2, height: VIEWPORT.height * 2 } },
        colorScheme: "dark",
    });
    const page = await context.newPage();
    await injectClickRipple(page);
    return { context, page };
}

/** Finalize a clip: close page, save video with proper name */
async function saveClip(context, page, filename) {
    await page.close();
    const video = page.video();
    if (video) {
        const tmpPath = await video.path();
        const finalPath = `${CLIPS_DIR}/${filename}.webm`;
        await context.close();
        renameSync(tmpPath, finalPath);
        console.log(`  💾 Saved: ${finalPath}\n`);
        return finalPath;
    }
    await context.close();
    return null;
}

// ═══════════════════════════════════════════════════════════
// TICKET TYPES — data-driven clip generation
// ═══════════════════════════════════════════════════════════

const TICKETS = [
    { key: "refund", label: "Refund", icon: "💳", hitl: true },
    { key: "technical", label: "Technical", icon: "🔧", hitl: false },
    { key: "billing", label: "Billing", icon: "📄", hitl: false },
    { key: "upgrade", label: "Upgrade", icon: "⬆️", hitl: false },
    { key: "reactivate", label: "Reactivate", icon: "🔓", hitl: true },
    { key: "suspend", label: "Suspend", icon: "🔒", hitl: true },
];

/** Generate clips for a single ticket type */
function makeTicketClips(ticket, startNum) {
    const clips = {};
    const { key, label, hitl } = ticket;
    let num = startNum;

    if (hitl) {
        // — DENY clip
        const denyId = `${key}-deny`;
        const denyNum = String(num++).padStart(2, "00");
        clips[denyId] = {
            name: `${denyNum}-${key}-deny`,
            title: `${label} — HITL Deny`,
            record: async (browser) => {
                await clearCache();
                const { context, page } = await createClipContext(browser);
                await resetDashboard(page);
                console.log("    ✓ Dashboard loaded");
                await sleep(1000);

                await clickPreset(page, label);
                const result = await waitForState(page, 180000);
                console.log(`    → State: ${result}`);

                if (result === "approval") {
                    await waitForHitlModal(page);
                    await page.locator(".btn-danger:has-text('Deny')").first().click({ timeout: 5000 });
                    console.log("    ✗ Clicked Deny");
                    const postDeny = await waitForState(page, 15000);
                    console.log(`    → Post-deny: ${postDeny}`);
                    await sleep(5000);
                } else {
                    console.log(`    ⚠ Got ${result} instead of approval`);
                    await sleep(3000);
                }
                return saveClip(context, page, `${denyNum}-${key}-deny`);
            },
        };

        // — APPROVE clip
        const approveId = `${key}-approve`;
        const approveNum = String(num++).padStart(2, "00");
        clips[approveId] = {
            name: `${approveNum}-${key}-approve`,
            title: `${label} — HITL Approve`,
            record: async (browser) => {
                await clearCache();
                const { context, page } = await createClipContext(browser);
                await resetDashboard(page);
                console.log("    ✓ Dashboard loaded");
                await sleep(1000);

                await clickPreset(page, label);
                const result = await waitForState(page, 180000);
                console.log(`    → State: ${result}`);

                if (result === "approval") {
                    await waitForHitlModal(page);
                    await page.locator(".btn-success:has-text('Approve')").first().click({ timeout: 5000 });
                    console.log("    ✓ Clicked Approve");
                    const post = await waitForState(page, 30000);
                    console.log(`    → Post-approval: ${post}`);
                    await sleep(5000);
                } else {
                    console.log(`    ⚠ Got ${result} instead of approval`);
                    await sleep(3000);
                }
                return saveClip(context, page, `${approveNum}-${key}-approve`);
            },
        };
    } else {
        // — FLOW clip (no HITL — just click preset and show result)
        const flowId = `${key}-flow`;
        const flowNum = String(num++).padStart(2, "00");
        clips[flowId] = {
            name: `${flowNum}-${key}-flow`,
            title: `${label} — Agent Flow`,
            record: async (browser) => {
                await clearCache();
                const { context, page } = await createClipContext(browser);
                await resetDashboard(page);
                console.log("    ✓ Dashboard loaded");
                await sleep(1000);

                await clickPreset(page, label);
                const result = await waitForState(page, 180000);
                console.log(`    → State: ${result}`);

                if (result === "approval") {
                    await sleep(3000);
                    await approveIfModalOpen(page);
                    const post = await waitForState(page, 30000);
                    console.log(`    → Post-approval: ${post}`);
                }
                await sleep(5000);
                return saveClip(context, page, `${flowNum}-${key}-flow`);
            },
        };
    }

    // — CACHED clip (all types get one)
    const cachedId = `${key}-cached`;
    const cachedNum = String(num++).padStart(2, "00");
    clips[cachedId] = {
        name: `${cachedNum}-${key}-cached`,
        title: `${label} — Cached`,
        record: async (browser) => {
            // Warm-up: build cache entry using preset button
            const { context: warmCtx, page: warmPage } = await createClipContext(browser);
            await resetDashboard(warmPage);
            await clickPreset(warmPage, label);
            console.log("    ↻ Warming cache...");
            const warmResult = await waitForState(warmPage, 180000);
            if (warmResult === "approval") {
                await approveIfModalOpen(warmPage);
                await waitForState(warmPage, 30000);
            }
            await warmPage.close();
            await warmCtx.close();
            console.log("    ✓ Cache primed");
            await sleep(1000);

            // Record the cache-hit clip — preset button fires instantly from cache
            const { context, page } = await createClipContext(browser);
            await resetDashboard(page);
            console.log("    ✓ Dashboard loaded");
            await sleep(1000);

            await clickPreset(page, label);
            const result = await waitForState(page, 15000);
            console.log(`    → State: ${result}`);
            if (result === "cached") {
                console.log("    ⚡ Cache hit!");
            } else {
                console.log(`    → Got: ${result}`);
            }
            await sleep(5000);
            return saveClip(context, page, `${cachedNum}-${key}-cached`);
        },
    };

    return { clips, nextNum: num };
}

// ═══════════════════════════════════════════════════════════
// BUILD ALL CLIPS
// ═══════════════════════════════════════════════════════════

let clipNum = 1;
const CLIPS = {};

// Generate ticket clips (deny/approve/cached or flow/cached)
for (const ticket of TICKETS) {
    const { clips, nextNum } = makeTicketClips(ticket, clipNum);
    Object.assign(CLIPS, clips);
    clipNum = nextNum;
}

// ═══ STANDALONE CLIPS ═══

Object.assign(CLIPS, {
    dashboard: {
        name: `${String(clipNum++).padStart(2, "0")}-dashboard`,
        title: "Dashboard Overview",
        record: async (browser) => {
            const { context, page } = await createClipContext(browser);
            await resetDashboard(page);
            console.log("    ✓ Dashboard loaded");
            await sleep(5000);
            return saveClip(context, page, `${CLIPS.dashboard.name}`);
        },
    },

    metrics: {
        name: `${String(clipNum++).padStart(2, "0")}-metrics`,
        title: "Observability Metrics",
        record: async (browser) => {
            const { context, page } = await createClipContext(browser);
            await resetDashboard(page);
            await sleep(2000);
            const panel = page.locator("text=Observability").first();
            if (await panel.isVisible().catch(() => false)) {
                await panel.scrollIntoViewIfNeeded();
                console.log("    ✓ Metrics panel visible");
            }
            await sleep(8000);
            return saveClip(context, page, `${CLIPS.metrics.name}`);
        },
    },

    traces: {
        name: `${String(clipNum++).padStart(2, "0")}-traces`,
        title: "LangSmith Traces Panel",
        record: async (browser) => {
            const { context, page } = await createClipContext(browser);
            await resetDashboard(page);
            await sleep(3000);
            const btn = page.locator("button:has-text('LangSmith Traces')").first();
            if (await btn.isVisible().catch(() => false)) {
                await btn.click({ timeout: 5000 });
                console.log("    ✓ Opened Traces panel");
                try {
                    await page.waitForSelector("text=Loading traces…", { state: "hidden", timeout: 90000 });
                    console.log("    ✓ Traces loaded");
                } catch {
                    console.log("    ⚠ Traces still loading after 90s — continuing");
                }
                await sleep(8000);
                const close = page.locator('[title="Close (Esc)"]').first();
                if (await close.isVisible().catch(() => false)) await close.click();
                else await page.keyboard.press("Escape");
                console.log("    ✓ Closed Traces");
                await sleep(2000);
            }
            return saveClip(context, page, `${CLIPS.traces.name}`);
        },
    },

    history: {
        name: `${String(clipNum++).padStart(2, "0")}-history`,
        title: "Ticket History",
        record: async (browser) => {
            const { context, page } = await createClipContext(browser);
            await resetDashboard(page);

            // Populate history with several diverse tickets
            const fills = ["Billing", "Technical", "Upgrade", "Billing", "Technical"];
            for (const preset of fills) {
                await clickPreset(page, preset);
                await waitForState(page, 30000);
                // Auto-approve any HITL that comes up
                await page.locator(".btn-success:has-text('Approve')")
                    .first().click({ timeout: 2000 }).catch(() => { });
                await sleep(800);
            }
            await sleep(1000);

            // Expand the Ticket History accordion
            const header = page.locator(".ticket-history-header").first();
            if (await header.isVisible().catch(() => false)) {
                await header.click();
                console.log("    ✓ Ticket history expanded");
                await sleep(600);
            }

            // Scroll into view and record
            await page.locator(".ticket-history-container").first()
                .scrollIntoViewIfNeeded().catch(() => { });
            await sleep(5000);
            return saveClip(context, page, `${CLIPS.history.name}`);
        },
    },
});

// ═══ EDGE CASE CLIPS — click Edge Cases tab presets ═══

const EDGE_CASES = [
    { key: "typo", label: "Typo", title: "Typo Correction" },
    { key: "notfound", label: "Not Found", title: "Customer Not Found" },
    { key: "mismatch", label: "Mismatch", title: "Name/ID Mismatch" },
    { key: "nameonly", label: "Name Only", title: "Name Only Lookup" },
    { key: "cancelled", label: "Cancelled", title: "Cancelled Account" },
];

/** Record an edge case clip using the Edge Cases tab button */
function makeEdgeCaseClip(edgeCase, num) {
    const { key, label, title } = edgeCase;
    const padded = String(num).padStart(2, "00");
    return {
        name: `${padded}-edge-${key}`,
        title: `Edge Case — ${title}`,
        record: async (browser) => {
            await clearCache();
            const { context, page } = await createClipContext(browser);
            await resetDashboard(page);
            console.log("    ✓ Dashboard loaded");
            await sleep(1000);

            await clickEdgeCase(page, label);
            const result = await waitForState(page, 120000);
            console.log(`    → State: ${result}`);
            if (result === "approval") {
                await sleep(3000);
                await approveIfModalOpen(page);
                const post = await waitForState(page, 30000);
                console.log(`    → Post-approval: ${post}`);
            }
            await sleep(5000);
            return saveClip(context, page, `${padded}-edge-${key}`);
        },
    };
}

for (const edgeCase of EDGE_CASES) {
    CLIPS[edgeCase.key] = makeEdgeCaseClip(edgeCase, clipNum++);
}

// ═══ DATABASE CLIP ═══

Object.assign(CLIPS, {
    database: {
        name: `${String(clipNum++).padStart(2, "0")}-database`,
        title: "Database Explorer",
        record: async (browser) => {
            const { context, page } = await createClipContext(browser);
            await resetDashboard(page);
            const dbSection = page.locator("text=DATABASE").first();
            if (await dbSection.isVisible().catch(() => false)) {
                await dbSection.scrollIntoViewIfNeeded();
                console.log("    ✓ Database section visible");
                await sleep(800);
                const customersBtn = page.locator("text=Customers").first();
                if (await customersBtn.isVisible().catch(() => false)) {
                    await customersBtn.click();
                    console.log("    ✓ Expanded Customers table");
                    await sleep(2000);
                }
                // Scroll back into view after expansion
                await dbSection.scrollIntoViewIfNeeded();
                await sleep(600);
            }
            await sleep(5000);
            return saveClip(context, page, `${CLIPS.database.name}`);
        },
    },
});

// ═══════════════════════════════════════════════════════════
// MAIN — record selected clips or all
// ═══════════════════════════════════════════════════════════

async function main() {
    const args = process.argv.slice(2);
    const selected = args.length > 0
        ? args.filter((a) => CLIPS[a]).map((a) => a)
        : Object.keys(CLIPS);

    if (args.length > 0) {
        const invalid = args.filter((a) => !CLIPS[a]);
        if (invalid.length) {
            console.log(`⚠ Unknown clips: ${invalid.join(", ")}`);
            console.log(`  Available: ${Object.keys(CLIPS).join(", ")}`);
        }
    }

    console.log(`🎬 Aegis Clip Recorder — ${selected.length} clip(s)\n`);
    console.log(`   Viewport: ${VIEWPORT.width}×${VIEWPORT.height} (Loom 16:9)`);
    console.log(`   Output:   ${CLIPS_DIR}/\n`);

    // Ensure output directory
    mkdirSync(CLIPS_DIR, { recursive: true });

    // Clear cache before recording
    try {
        await fetch(`${API_URL}/api/cache`, { method: "DELETE" });
        console.log("✓ Cache cleared\n");
    } catch {
        console.log("⚠ Could not clear cache (backend not running?)\n");
    }

    const browser = await chromium.launch({ headless: false });
    const saved = [];

    for (const key of selected) {
        const clip = CLIPS[key];
        console.log(`═══ ${clip.title} ═══`);
        try {
            const path = await clip.record(browser);
            if (path) saved.push(path);
        } catch (err) {
            console.log(`  ✗ Failed: ${err.message?.slice(0, 100)}\n`);
        }
    }

    await browser.close();

    console.log("═══════════════════════════════════════");
    console.log(`✅ Done! ${saved.length}/${selected.length} clips saved:\n`);
    saved.forEach((p) => console.log(`   ${p}`));
    console.log(`\nConvert all to MP4:`);
    console.log(`   for f in ${CLIPS_DIR}/*.webm; do ffmpeg -i "$f" -c:v libx264 -crf 18 "\${f%.webm}.mp4"; done`);
}

main().catch((err) => {
    console.error("Failed:", err);
    process.exit(1);
});
