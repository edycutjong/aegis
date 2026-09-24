import { describe, it, expect } from "vitest";
import { agentForStep, derivePipeline, groupSteps, parseStep, shortModel } from "../trace";

const SUSPEND_LOG = [
    "✓ [Triage] Classified intent: account (confidence: 95%)",
    "🧠 Routed to gemini-2.5-flash",
    "✓ [Investigator] Customer validated: #20 William Allen (free, cancelled)",
    "⚠ [Investigator] Customer #20 William Allen account is CANCELLED",
    "✓ [Investigator] Generated SQL query for investigation",
    "✓ [Investigator] SQL executed successfully — found 1 records",
    "✓ [Knowledge] Found 5 relevant internal documents",
    "✓ [Resolution] Proposed action: escalate — Escalate due to conflicting information.",
];

describe("parseStep", () => {
    it.each([
        ["✓ [Triage] Classified intent: billing (confidence: 99%)", "intent", { intent: "billing", confidence: "99%" }, "ok"],
        ["⚡ Routed to Groq openai/gpt-oss-120b", "route", { model: "openai/gpt-oss-120b" }, "info"],
        ["🧠 Routed to gemini-2.5-flash", "route", { model: "gemini-2.5-flash" }, "info"],
        ['⚠ [Investigator] Name typo detected: "Davd Martines" → auto-corrected to "David Martinez" (similarity: 87%)', "typo", { from: "Davd Martines", to: "David Martinez", similarity: "87%" }, "warn"],
        ["✓ [Investigator] Customer found by name: #5 Emily Davis (enterprise, suspended)", "customer", { id: "5", name: "Emily Davis", plan: "enterprise", status: "suspended" }, "ok"],
        ["✗ [Investigator] SQL retry (attempt 2/3): column x does not exist", "sql_retry", { attempt: "2", max: "3", error: "column x does not exist" }, "heal"],
        ["✓ [Investigator] SQL executed successfully — found 3 records", "sql_rows", { rows: "3" }, "ok"],
        ["✓ [Investigator] Generated SQL query for investigation", "sql", {}, "ok"],
        ["✓ [Knowledge] Found 1 relevant internal document", "docs", { count: "1" }, "ok"],
        ["✓ [Resolution] Proposed action: refund — Refund $49", "proposal", { type: "refund", description: "Refund $49" }, "ok"],
        ["✓ [Resolution] Auto-approved: resolve is non-destructive", "auto", { type: "resolve" }, "ok"],
        ["✓ [Resolution] Human decision: approved", "decision", { decision: "approved" }, "ok"],
        ["✗ [Resolution] Human decision: denied — not enough evidence", "decision", { decision: "denied", reason: "not enough evidence" }, "fail"],
        ["✓ [Resolution] Action executed: Refund recommended", "executed", { result: "Refund recommended" }, "ok"],
        ["✓ [Resolution] Generated resolution summary", "summary", {}, "ok"],
        ["⏸ [Resolution] Waiting", "text", {}, "warn"],
        ["→ something else", "text", {}, "info"],
        ["✓ [Triage] Input screen clean (prompt-guard 0.000)", "screen_clean", { score: "prompt-guard 0.000" }, "ok"],
        ["✓ [Triage] Input screen clean", "screen_clean", {}, "ok"],
        ["🛡 [Triage] Input flagged: data-exfiltration, approval-bypass (prompt-guard 0.001) — will require human review", "screen_flagged", { flags: "data-exfiltration, approval-bypass", score: "prompt-guard 0.001" }, "guard"],
        ["🛡️ [Triage] Input flagged: jailbreak", "screen_flagged", { flags: "jailbreak" }, "guard"],
        ["🛡 [Investigator] SQL guard blocked query (attempt 1/3): schema 'auth' is not allowed", "sql_blocked", { attempt: "1", max: "3", reason: "schema 'auth' is not allowed" }, "guard"],
        ["✓ [Knowledge] Found 2 relevant internal documents: Refund Policy, SLA", "docs", { count: "2", titles: "Refund Policy, SLA" }, "ok"],
    ])("parses %s", (raw, kind, data, tone) => {
        const step = parseStep(raw);
        expect(step.kind).toBe(kind);
        expect(step.data).toEqual(data);
        expect(step.tone).toBe(tone);
    });

    it("keeps unknown agent tags as text and extracts known ones", () => {
        expect(parseStep("✓ [Bogus] hi").agent).toBeNull();
        expect(parseStep("✓ [Bogus] hi").text).toBe("[Bogus] hi");
        expect(parseStep("✓ [Knowledge] hi").agent).toBe("Knowledge");
    });
});

describe("groupSteps", () => {
    it("groups consecutive lines by agent and folds untagged lines into the previous agent", () => {
        const groups = groupSteps(SUSPEND_LOG);
        expect(groups.map((g) => g.agent)).toEqual(["Triage", "Investigator", "Knowledge", "Resolution"]);
        expect(groups[0].steps).toHaveLength(2);
        expect(groups[1].steps.map((s) => s.index)).toEqual([2, 3, 4, 5]);
    });

    it("puts leading untagged lines in a system group", () => {
        const groups = groupSteps(["plain note", "✓ [Triage] Classified intent: a (confidence: 1%)"]);
        expect(groups[0].agent).toBeNull();
        expect(groups[1].agent).toBe("Triage");
    });
});

describe("derivePipeline", () => {
    it("is all pending before anything runs, with Triage active once processing starts", () => {
        expect(Object.values(derivePipeline([], "idle")).every((s) => s === "pending")).toBe(true);
        expect(derivePipeline([], "processing").Triage).toBe("active");
        expect(derivePipeline([], "error").Gate).toBe("pending");
    });

    it("marks earlier agents done and the latest one active while processing", () => {
        const p = derivePipeline(SUSPEND_LOG.slice(0, 4), "processing");
        expect(p.Triage).toBe("done");
        expect(p.Investigator).toBe("active");
        expect(p.Knowledge).toBe("pending");
        expect(p.Gate).toBe("pending");
        expect(p.Execute).toBe("pending");
    });

    it("holds the gate while awaiting approval and activates it while releasing", () => {
        const held = derivePipeline(SUSPEND_LOG, "awaiting_approval");
        expect(held.Resolution).toBe("done");
        expect(held.Gate).toBe("held");
        expect(held.Execute).toBe("pending");
        const releasing = derivePipeline(SUSPEND_LOG, "releasing");
        expect(releasing.Gate).toBe("active");
        expect(releasing.Execute).toBe("active");
    });

    it("opens the gate and executes after approval", () => {
        const log = [...SUSPEND_LOG, "✓ [Resolution] Human decision: approved", "✓ [Resolution] Action executed: done"];
        const p = derivePipeline(log, "completed");
        expect(p.Gate).toBe("done");
        expect(p.Execute).toBe("done");
    });

    it("counts an approval as executed even without an executed line", () => {
        const p = derivePipeline([...SUSPEND_LOG, "✓ [Resolution] Human decision: approved"], "completed");
        expect(p.Execute).toBe("done");
    });

    it("marks the gate denied and skips execution when a human says no", () => {
        const p = derivePipeline([...SUSPEND_LOG, "✗ [Resolution] Human decision: denied — no"], "completed");
        expect(p.Gate).toBe("denied");
        expect(p.Execute).toBe("skipped");
        expect(p.Resolution).toBe("done");
    });

    it("skips the gate for auto-approved actions", () => {
        const log = ["✓ [Triage] Classified intent: general (confidence: 90%)", "✓ [Resolution] Auto-approved: resolve is non-destructive"];
        const p = derivePipeline(log, "completed");
        expect(p.Gate).toBe("skipped");
        expect(p.Execute).toBe("done");
        expect(p.Investigator).toBe("skipped");
    });

    it("marks the agent that stopped the run as failed and skips the rest", () => {
        const log = [
            "✓ [Triage] Classified intent: billing (confidence: 99%)",
            "✗ [Investigator] Customer #999 not found in database — stopping",
            "✓ [Resolution] Response already set by validation — skipping LLM generation",
        ];
        const p = derivePipeline(log, "completed");
        expect(p.Investigator).toBe("failed");
        expect(p.Knowledge).toBe("skipped");
        expect(p.Gate).toBe("skipped");
        expect(p.Execute).toBe("skipped");
    });

    it("holds (not fails) the Investigator while a human picks between matching customers", () => {
        const log = [
            "✓ [Triage] Classified intent: billing (confidence: 95%)",
            '✗ [Investigator] Ambiguous name "Rob Robert" — 2 matches found, need disambiguation',
            "✓ [Resolution] Response already set by validation — skipping LLM generation",
        ];
        expect(parseStep(log[1])).toMatchObject({ kind: "ambiguous", tone: "warn" });
        const p = derivePipeline(log, "disambiguation");
        expect(p.Investigator).toBe("held");
        expect(derivePipeline(log, "completed").Investigator).toBe("done");
    });

    it("leaves the gate pending when a proposal exists but the run ended without a decision", () => {
        expect(derivePipeline(SUSPEND_LOG, "completed").Gate).toBe("pending");
    });

    it("blames the last agent when the run errors", () => {
        const p = derivePipeline(SUSPEND_LOG.slice(0, 3), "error");
        expect(p.Investigator).toBe("failed");
        expect(p.Triage).toBe("done");
        expect(p.Knowledge).toBe("pending");
    });

    it("ignores untagged lines before any agent spoke", () => {
        const p = derivePipeline(["plain"], "processing");
        expect(p.Triage).toBe("pending");
    });
});

describe("helpers", () => {
    it("maps tracker step names to agents", () => {
        expect(agentForStep("classify_intent")).toBe("Triage");
        expect(agentForStep("write_sql")).toBe("Investigator");
        expect(agentForStep("validate_customer")).toBe("Investigator");
        expect(agentForStep("search_docs")).toBe("Knowledge");
        expect(agentForStep("propose_action")).toBe("Resolution");
        expect(agentForStep("generate_response")).toBe("Resolution");
        expect(agentForStep("execute_action")).toBe("Resolution");
        expect(agentForStep("mystery")).toBeNull();
    });

    it("strips provider prefixes from model names", () => {
        expect(shortModel("models/gemini-2.5-flash")).toBe("gemini-2.5-flash");
        expect(shortModel("openai/gpt-oss-20b")).toBe("gpt-oss-20b");
        expect(shortModel("gpt-4.1")).toBe("gpt-4.1");
        expect(shortModel("gpt-4.1-mini-2025-04-14")).toBe("gpt-4.1-mini");
    });
});
