import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import TopBar, { BrandMark, REPO_URL } from "../TopBar";
import PipelineRail from "../PipelineRail";
import StepLine from "../StepLine";
import RunReceipt from "../RunReceipt";
import { derivePipeline, parseStep, STAGES, type StageId, type StageState } from "@/lib/trace";

describe("TopBar", () => {
    it.each([
        ["connecting", "Connecting"],
        ["up", "Live"],
        ["down", "Offline"],
    ] as const)("shows the %s backend state", (state, label) => {
        render(<TopBar backend={state} />);
        expect(screen.getByRole("heading", { level: 1, name: "Aegis" })).toBeInTheDocument();
        expect(screen.getByRole("status")).toHaveTextContent(label);
        expect(screen.getByRole("link", { name: /Source code on GitHub/ })).toHaveAttribute("href", REPO_URL);
    });

    it("renders the mark at a custom size", () => {
        const { container } = render(<BrandMark size={40} />);
        expect(container.querySelector("svg")).toHaveAttribute("width", "40");
        const { container: c2 } = render(<BrandMark />);
        expect(c2.querySelector("svg")).toHaveAttribute("width", "28");
    });
});

describe("PipelineRail", () => {
    it("labels every stage with its state for screen readers", () => {
        render(<PipelineRail stages={derivePipeline([], "idle")} />);
        const items = screen.getAllByRole("listitem");
        expect(items).toHaveLength(6);
        expect(items[0]).toHaveAttribute("aria-label", "Triage: waiting");
    });

    it("renders every visual state, including a held gate", () => {
        const stages = Object.fromEntries(STAGES.map((s) => [s, "pending"])) as Record<StageId, StageState>;
        stages.Triage = "done";
        stages.Investigator = "failed";
        stages.Knowledge = "skipped";
        stages.Resolution = "active";
        stages.Gate = "held";
        stages.Execute = "done";
        const { container } = render(<PipelineRail stages={stages} />);
        expect(screen.getByLabelText("Human gate: holding for your decision")).toHaveAttribute("data-state", "held");
        expect(screen.getByText("awaiting you")).toBeInTheDocument();
        expect(screen.getByLabelText("Investigator: stopped")).toBeInTheDocument();
        expect(container.querySelectorAll(".pipe-link.lit").length).toBeGreaterThan(0);
        expect(container.querySelectorAll(".pipe-link.flowing")).toHaveLength(2);
    });

    it("shows the denied state", () => {
        const stages = derivePipeline(["✓ [Triage] a", "✗ [Resolution] Human decision: denied"], "completed");
        render(<PipelineRail stages={stages} />);
        expect(screen.getByLabelText("Human gate: denied")).toBeInTheDocument();
    });
});

describe("StepLine", () => {
    const renderStep = (raw: string, at?: number) =>
        render(
            <ul>
                <StepLine step={parseStep(raw)} at={at} />
            </ul>
        );

    it.each([
        ["✓ [Triage] Classified intent: billing (confidence: 99%)", /99% confidence/],
        ["↪ [Resolution] gpt-4.1-mini unavailable, answered by backup openai/gpt-oss-120b", /was unavailable/],
        ["✓ [Investigator] Customer validated: #8 David Martinez (pro, active)", /David Martinez/],
        ["✓ [Investigator] Customer validated: #5 Emily Davis (enterprise, suspended)", /suspended/],
        ['⚠ [Investigator] Name typo detected: "Davd" → auto-corrected to "David" (similarity: 87%)', /87% match/],
        ["✓ [Investigator] Generated SQL query for investigation", /read-only SQL query/],
        ["✓ [Investigator] SQL executed successfully — found 1 records", /1 row$/],
        ["✓ [Investigator] SQL executed successfully — found 4 records", /4 rows/],
        ["✗ [Investigator] SQL retry (attempt 1/3): bad column", /Self-heal 1\/3/],
        ["✗ [Investigator] SQL retry (attempt 2/3):", /rewriting the query/],
        ["✓ [Knowledge] Found 1 relevant internal document", /policy doc$/],
        ["✓ [Knowledge] Found 5 relevant internal documents", /policy docs/],
        ["✓ [Resolution] Proposed action: refund — Refund $49", /Refund \$49/],
        ["✓ [Resolution] Auto-approved: resolve is non-destructive", /skips the gate/],
        ["✓ [Resolution] Human decision: approved — verified", /You approved.*verified/],
        ["✓ [Resolution] Human decision: approved", /You approved the action$/],
        ["✗ [Resolution] Human decision: denied — no", /You denied.*no/],
        ["✗ [Resolution] Human decision: denied", /You denied the action$/],
        ["✓ [Resolution] Action executed: Refund recommended", /Released: Refund recommended/],
        ["✓ [Resolution] Generated resolution summary", /reply to the customer/],
        ["→ custom", /custom/],
        ["✓ [Triage] Input screen clean (prompt-guard 0.000)", /clean.*prompt-guard 0\.000/],
        ["✓ [Triage] Input screen clean", /injection: clean$/],
        ["🛡 [Triage] Input flagged: data-exfiltration, approval-bypass (prompt-guard 0.001) — will require human review", /flagged this ticket.*data-exfiltration.*approval-bypass.*prompt-guard 0\.001.*human will have to sign off/],
        ["🛡 [Triage] Input flagged: jailbreak", /jailbreak/],
        ["🛡 [Investigator] SQL guard blocked query (attempt 1/3): schema 'auth' is not allowed", /SQL guard blocked.*attempt 1\/3.*schema 'auth'/],
        ["🛡 [Investigator] SQL guard blocked query (attempt 2/3):", /SQL guard blocked.*attempt 2\/3$/],
        ["✓ [Knowledge] Found 2 relevant internal documents: Refund Policy, SLA", /2 internal policy docs.*Refund Policy.*SLA/],
    ])("renders %s", (raw, text) => {
        renderStep(raw);
        expect(screen.getByRole("listitem")).toHaveTextContent(text);
    });

    it("announces failures and warnings, and shows timing when known", () => {
        renderStep("✗ [Investigator] Customer #9 not found in database — stopping", 1234);
        expect(screen.getByText("Failed:")).toBeInTheDocument();
        expect(screen.getByText("+1.2s")).toBeInTheDocument();
    });

    it("folds very long lines (like raw provider errors) behind a disclosure", () => {
        const long = "✗ Error: 429 You exceeded your current quota " + "x".repeat(400);
        renderStep(long);
        const details = screen.getByRole("group");
        expect(details.querySelector("summary")!.textContent!.length).toBeLessThan(160);
        expect(details).toHaveTextContent("x".repeat(400));
    });

    it("announces security controls", () => {
        renderStep("🛡 [Investigator] SQL guard blocked query (attempt 1/3): nope");
        expect(screen.getByText("Security control:")).toBeInTheDocument();
    });

    it("announces warnings", () => {
        renderStep("⚠ [Investigator] heads up");
        expect(screen.getByText("Warning:")).toBeInTheDocument();
    });
});

describe("RunReceipt", () => {
    const base = {
        total_cost_usd: 0.0019,
        total_tokens: 2567,
        duration_seconds: 30.93,
        models_used: {},
        cache_hit: false,
    };

    it("itemises each LLM call with its model, tokens and cost", () => {
        render(
            <RunReceipt
                receipt={{
                    ...base,
                    hitl_wait_seconds: 9.66,
                    steps: [
                        { step: "classify_intent", model: "openai/gpt-oss-20b", prompt_tokens: 198, completion_tokens: 126, cost_usd: 0.000053, timestamp: 1 },
                        { step: "write_sql", model: "gpt-4.1", prompt_tokens: 293, completion_tokens: 156, cost_usd: 0.0183, timestamp: 2 },
                        { step: "propose_action", model: "models/gemini-2.5-flash", prompt_tokens: 878, completion_tokens: 134, cost_usd: 0, timestamp: 3 },
                        { step: "mystery_step", model: "x", prompt_tokens: 1, completion_tokens: 1, cost_usd: 0, timestamp: 4 },
                        { step: "generate_response", model: "x", prompt_tokens: 1, completion_tokens: 1, cost_usd: 0.00002, timestamp: 5 },
                    ],
                }}
            />
        );
        expect(screen.getByText("30.9s")).toBeInTheDocument();
        expect(screen.getByText("9.7s")).toBeInTheDocument();
        expect(screen.getByText("2,567")).toBeInTheDocument();
        expect(screen.getByText("$0.0019")).toBeInTheDocument();
        expect(screen.getByText("Classify intent")).toBeInTheDocument();
        expect(screen.getByText("gpt-oss-20b")).toBeInTheDocument();
        expect(screen.getByText("$0.018")).toBeInTheDocument();
        expect(screen.getByText("gemini-2.5-flash")).toBeInTheDocument();
        expect(screen.getByText("mystery_step")).toBeInTheDocument();
        expect(screen.getAllByText("—").length).toBe(2);
        expect(screen.getAllByText("<$0.0001")).toHaveLength(2);
    });

    it("omits the table and human wait when not recorded", () => {
        render(<RunReceipt receipt={base} />);
        expect(screen.queryByRole("table")).not.toBeInTheDocument();
        expect(screen.queryByText("Held for you")).not.toBeInTheDocument();
    });
});
