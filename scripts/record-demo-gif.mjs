/**
 * Record the README demo GIF from a real run: ticket → agent trace → held at
 * the approval gate → approve → reply.
 *
 *   BASE_URL=https://aegis.edycu.dev node scripts/record-demo-gif.mjs
 *   BASE_URL=http://localhost:3000 node scripts/record-demo-gif.mjs   # unreleased UI, live API
 *
 * Needs Playwright's Chromium (`cd frontend && npx playwright install chromium`)
 * and ffmpeg. Costs one real ticket (~$0.003) against the target.
 */
import { execFileSync } from "node:child_process";
import { mkdtempSync, readdirSync, renameSync, rmSync } from "node:fs";
import { createRequire } from "node:module";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const { chromium } = createRequire(resolve(root, "frontend/package.json"))("playwright");

const BASE_URL = process.env.BASE_URL ?? "http://localhost:3000";
const OUT = resolve(root, "docs/demo.gif");
const SIZE = { width: 1280, height: 800 };
const RUN_TIMEOUT = 90_000;

const videoDir = mkdtempSync(join(tmpdir(), "aegis-gif-"));
const browser = await chromium.launch();
try {
    const context = await browser.newContext({ viewport: SIZE, recordVideo: { dir: videoDir, size: SIZE } });
    const page = await context.newPage();
    await page.goto(BASE_URL, { waitUntil: "networkidle" });
    await page.waitForTimeout(1200);

    await page.getByRole("button", { name: /^Double charge/i }).first().click();
    const approve = page.getByRole("button", { name: /approve/i });
    await approve.waitFor({ timeout: RUN_TIMEOUT });
    await approve.scrollIntoViewIfNeeded();
    await page.waitForTimeout(2500); // hold on the gate

    await approve.click();
    await page.locator("#result-title").waitFor({ timeout: RUN_TIMEOUT });
    await page.locator("#result-title").scrollIntoViewIfNeeded();
    await page.waitForTimeout(3000); // hold on the reply
    await context.close(); // flushes the video
} finally {
    await browser.close();
}

const webm = readdirSync(videoDir).find((f) => f.endsWith(".webm"));
const src = join(videoDir, webm);
const palette = join(videoDir, "palette.png");
const filters = "fps=8,scale=800:-1:flags=lanczos"; // keeps a ~20 s run near 5 MB
execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-i", src, "-vf", `${filters},palettegen=max_colors=128:stats_mode=diff`, palette]);
execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-i", src, "-i", palette,
    "-lavfi", `${filters} [x]; [x][1:v] paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle`, `${OUT}.tmp.gif`]);
renameSync(`${OUT}.tmp.gif`, OUT);
rmSync(videoDir, { recursive: true, force: true });
console.log(`✓ ${OUT}`);
