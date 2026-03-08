/**
 * Aegis — DB Reset & Reseed
 *
 * Truncates all tables, resets sequences, and reseeds fresh data
 * directly via the Supabase REST API. Zero extra dependencies —
 * uses Node 18+ built-in fetch.
 *
 * Usage:
 *   node scripts/db-reset.mjs
 *   make db-reset            ← called automatically by make restart
 */

import { readFileSync } from "fs";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";

const __dir = dirname(fileURLToPath(import.meta.url));
const root = resolve(__dir, "..");

// ── Read backend/.env (no dotenv needed) ─────────────────────
function loadEnv() {
    const lines = readFileSync(resolve(root, "backend/.env"), "utf8").split("\n");
    const env = {};
    for (const line of lines) {
        const t = line.trim();
        if (!t || t.startsWith("#")) continue;
        const idx = t.indexOf("=");
        if (idx === -1) continue;
        env[t.slice(0, idx).trim()] = t.slice(idx + 1).trim().replace(/^["']|["']$/g, "");
    }
    return env;
}

// ── Run SQL via Supabase pg REST proxy ────────────────────────
// POST /rest/v1/rpc/<fn> doesn't allow arbitrary DDL, so we use the
// undocumented /pg endpoint that accepts raw SQL with a service-role key.
// Format: POST https://<project>.supabase.co/rest/v1/  → not available
//
// We use the Supabase "sql" management endpoint instead:
// POST https://api.supabase.com/v1/projects/<ref>/database/query
async function execSQL(projectRef, managementKey, sql) {
    const res = await fetch(
        `https://api.supabase.com/v1/projects/${projectRef}/database/query`,
        {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                Authorization: `Bearer ${managementKey}`,
            },
            body: JSON.stringify({ query: sql }),
        }
    );
    if (!res.ok) {
        const body = await res.text();
        throw new Error(`SQL error (${res.status}): ${body.slice(0, 200)}`);
    }
    return res.json().catch(() => null);
}

// ── Split SQL file into individual statements ─────────────────
// Must be dollar-quote aware: semicolons inside $$...$$ are NOT
// statement terminators and must not split the function body.
function splitStatements(sql) {
    const stmts = [];
    let current = "";
    let inDollarQuote = false;
    let dollarTag = "";
    const lines = sql.split("\n");

    for (const rawLine of lines) {
        // Strip single-line comments (outside dollar-quotes only)
        const line = inDollarQuote ? rawLine : rawLine.replace(/--.*$/, "");

        let i = 0;
        while (i < line.length) {
            // Check for dollar-quote open/close (e.g. $$ or $body$)
            if (!inDollarQuote && line[i] === "$") {
                const rest = line.slice(i);
                const match = rest.match(/^\$([A-Za-z_]*)\$/);
                if (match) {
                    dollarTag = match[0]; // e.g. "$$" or "$body$"
                    inDollarQuote = true;
                    current += dollarTag;
                    i += dollarTag.length;
                    continue;
                }
            } else if (inDollarQuote && line[i] === "$") {
                const rest = line.slice(i);
                if (rest.startsWith(dollarTag)) {
                    current += dollarTag;
                    i += dollarTag.length;
                    inDollarQuote = false;
                    dollarTag = "";
                    continue;
                }
            }

            // Semicolon outside a dollar-quote = statement boundary
            if (!inDollarQuote && line[i] === ";") {
                const stmt = current.trim();
                if (stmt.length > 0) stmts.push(stmt);
                current = "";
                i++;
                continue;
            }

            current += line[i];
            i++;
        }

        current += "\n"; // preserve newlines (needed inside function bodies)
    }

    // Flush any trailing content
    const last = current.trim();
    if (last.length > 0) stmts.push(last);

    return stmts.filter((s) => !/^--/.test(s) && s.trim().length > 0);
}

// ── Main ──────────────────────────────────────────────────────
async function main() {
    console.log("\n🗄️  Aegis — DB Reset & Reseed\n");

    const env = loadEnv();
    const url = env.SUPABASE_URL; // https://xxxx.supabase.co
    const projectRef = url.replace("https://", "").split(".")[0];
    const managementKey = env.SUPABASE_MANAGEMENT_KEY;

    if (!managementKey) {
        // Fallback: use TRUNCATE via the execute_readonly_query workaround isn't possible,
        // so we guide the user to add their management key or use psql.
        console.error(
            "⚠  SUPABASE_MANAGEMENT_KEY not set in backend/.env\n" +
            "   Add it from: https://supabase.com/dashboard/account/tokens\n" +
            "   OR run manually:\n" +
            `     psql "$DATABASE_URL" -f reset.sql\n` +
            `     psql "$DATABASE_URL" -f seed.sql\n`
        );
        process.exit(1);
    }

    const resetSQL = readFileSync(resolve(root, "reset.sql"), "utf8");
    const seedSQL = readFileSync(resolve(root, "seed.sql"), "utf8");

    // Run reset (ignore "does not exist" errors — idempotent)
    console.log("  Step 1/2 — Dropping tables...");
    for (const stmt of splitStatements(resetSQL)) {
        try {
            await execSQL(projectRef, managementKey, stmt);
        } catch (e) {
            if (e.message.includes("does not exist")) continue; // idempotent
            console.warn(`    ⚠ ${e.message.slice(0, 100)}`);
        }
    }
    console.log("  ✓ Reset done");

    // Run seed
    console.log("  Step 2/2 — Seeding fresh data...");
    for (const stmt of splitStatements(seedSQL)) {
        try {
            await execSQL(projectRef, managementKey, stmt);
        } catch (e) {
            console.warn(`    ⚠ ${e.message.slice(0, 100)}`);
        }
    }
    console.log("  ✓ Seed done");

    console.log("\n✅ DB reset & reseed complete\n");
}

main().catch((e) => { console.error("✗ Fatal:", e.message); process.exit(1); });
