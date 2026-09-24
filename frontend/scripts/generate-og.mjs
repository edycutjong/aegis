// Renders the social card and PNG icons into public/ with Playwright.
//   node scripts/generate-og.mjs
// Outputs: public/og.png (1200×630), public/apple-touch-icon.png (180×180),
//          public/favicon-32.png (32×32). Re-run after brand or copy changes.
import { chromium } from "@playwright/test";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const pub = (f) => path.join(root, "public", f);
const icon = readFileSync(pub("icon.svg"), "utf8");

const FONTS = `<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Chakra+Petch:wght@600;700&family=Inter:wght@400;500;650&family=JetBrains+Mono:wght@500&display=block" rel="stylesheet">`;

const OG = `<!doctype html><html><head>${FONTS}<style>
  * { margin: 0; box-sizing: border-box; }
  body { width: 1200px; height: 630px; overflow: hidden; font-family: Inter, sans-serif; color: #eef2f8;
    background:
      radial-gradient(700px 380px at 8% -5%, rgba(59,130,246,.22), transparent 70%),
      radial-gradient(620px 360px at 100% 105%, rgba(245,158,11,.14), transparent 70%),
      repeating-linear-gradient(90deg, rgba(148,163,184,.045) 0 1px, transparent 1px 48px),
      repeating-linear-gradient(0deg, rgba(148,163,184,.045) 0 1px, transparent 1px 48px),
      #0a0e17; }
  .wrap { position: absolute; inset: 64px 72px; display: flex; flex-direction: column; }
  .brand { display: flex; align-items: center; gap: 18px; }
  .brand svg { width: 64px; height: 64px; }
  .word { font-family: "Chakra Petch"; font-weight: 700; font-size: 40px; letter-spacing: .2em; }
  .word b { color: #f59e0b; font-weight: 700; }
  .eyebrow { margin-top: 56px; font-family: "Chakra Petch"; font-weight: 600; font-size: 20px; letter-spacing: .14em; color: #8ab4ff; text-transform: uppercase; }
  h1 { margin-top: 16px; font-size: 62px; line-height: 1.08; font-weight: 650; letter-spacing: -.03em; max-width: 1000px; }
  h1 span { background: linear-gradient(90deg, #fcd34d, #f59e0b); -webkit-background-clip: text; color: transparent; }
  .foot { margin-top: auto; display: flex; flex-direction: column; gap: 18px; }
  .stats { display: flex; gap: 12px; }
  .pill { font-family: "JetBrains Mono", monospace; font-size: 21px; font-weight: 500; padding: 8px 16px; border-radius: 999px; border: 1px solid #2a3650; background: rgba(17,24,38,.8); color: #eef2f8; }
  .pill.ok { color: #6ee7b7; border-color: rgba(52,211,153,.4); background: rgba(52,211,153,.08); }
  .sub { font-size: 24px; color: #b3bfd2; display: flex; flex-wrap: wrap; gap: 10px 14px; align-items: center; }
  .sub i { width: 5px; height: 5px; border-radius: 50%; background: #475569; display: inline-block; }
  .rail { position: absolute; right: 72px; top: 76px; width: 330px; height: 40px; }
  .rail .track { position: absolute; left: 0; right: 0; top: 19px; height: 2px; background: #2a3650; }
  .rail .run { position: absolute; left: 0; width: 200px; top: 19px; height: 2px; background: linear-gradient(90deg, transparent, #3b82f6); }
  .rail .dot { position: absolute; left: 190px; top: 10px; width: 20px; height: 20px; border-radius: 50%; background: #3b82f6; box-shadow: 0 0 0 5px rgba(245,158,11,.9), 0 0 26px rgba(245,158,11,.6); }
  .rail .bar { position: absolute; left: 246px; top: 0; width: 6px; height: 40px; border-radius: 3px; background: #f59e0b; box-shadow: 0 0 18px #f59e0b; }
  .rail .beyond { position: absolute; left: 272px; right: 0; top: 19px; border-top: 3px dotted #2a3650; }
</style></head><body><div class="wrap">
  <div class="brand">${icon.replace("<svg", '<svg aria-hidden="true"')}<div class="word">AEG<b>I</b>S</div></div>
  <div class="eyebrow">A pause a human releases</div>
  <h1>The agents do the investigation. <span>You release the action.</span></h1>
  <div class="foot">
    <div class="sub">Multi-agent support engine <i></i> LangGraph <i></i> human approval gate</div>
    <div class="stats"><span class="pill ok">99.2% eval pass</span><span class="pill">0 safety violations</span></div>
  </div>
</div>
<div class="rail"><div class="track"></div><div class="run"></div><div class="dot"></div><div class="bar"></div><div class="beyond"></div></div>
</body></html>`;

const ICON = (size) => `<!doctype html><html><head><style>
  * { margin: 0; } body { width: ${size}px; height: ${size}px; background: #0a0e17; }
  svg { width: ${size}px; height: ${size}px; display: block; }
</style></head><body>${icon}</body></html>`;

const browser = await chromium.launch();
async function render(html, width, height, file) {
    const page = await browser.newPage({ viewport: { width, height }, deviceScaleFactor: 1 });
    await page.setContent(html, { waitUntil: "networkidle" });
    await page.evaluate(() => document.fonts.ready);
    await page.screenshot({ path: pub(file), omitBackground: false });
    await page.close();
    console.log("wrote public/" + file);
}
await render(OG, 1200, 630, "og.png");
await render(ICON(180), 180, 180, "apple-touch-icon.png");
await render(ICON(32), 32, 32, "favicon-32.png");
await browser.close();
