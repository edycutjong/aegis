import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import RunPanel, { type RunPanelProps } from "../RunPanel";
import { FEATURED } from "@/lib/presets";

Element.prototype.scrollTo = vi.fn();

const LOG = [
    "✓ [Triage] Classified intent: account (confidence: 95%)",
    "🧠 Routed to gemini-2.5-flash",
    "✓ [Investigator] Customer validated: #20 William Allen (free, cancelled)",
    "plain untagged line",
];

function props(over: Partial<RunPanelProps> = {}): RunPanelProps {
    return {
        status: "idle",
        ticket: "",
        threadId: null,
        thoughts: [],
        times: [],
        pendingAction: null,
        approvalLoading: false,
        onApprove: vi.fn(),
        onDeny: vi.fn(),
        candidates: [],
        disambiguationMessage: null,
        onSelectCandidate: vi.fn(),
        finalResponse: null,
        notice: null,
        receipt: null,
        onRetry: vi.fn(),
        onPreset: vi.fn(),
        backendDown: false,
        ...over,
    };
}

afterEach(() => vi.useRealTimers());

describe("RunPanel", () => {
    it("teaches a first-time visitor and runs featured tickets", async () => {
        const p = props();
        render(<RunPanel {...p} />);
        expect(screen.getByText(/Pick a ticket and watch the agents work it/)).toBeInTheDocument();
        expect(screen.queryByRole("status")).not.toBeInTheDocument();
        expect(screen.queryByText(/offline right now/)).not.toBeInTheDocument();
        await userEvent.click(screen.getByRole("button", { name: new RegExp(FEATURED[1].label) }));
        expect(p.onPreset).toHaveBeenCalledWith(FEATURED[1]);
    });

    it("warns in the empty state when the backend is down", () => {
        render(<RunPanel {...props({ backendDown: true })} />);
        expect(screen.getByText(/offline right now/)).toBeInTheDocument();
    });

    it("streams grouped steps with timings while processing", () => {
        vi.useFakeTimers();
        render(<RunPanel {...props({ status: "processing", ticket: "Help", threadId: "abcdef123456", thoughts: LOG, times: [400, 500] })} />);
        expect(screen.getByText("Help")).toBeInTheDocument();
        expect(screen.getByText(/abcdef12/)).toBeInTheDocument();
        expect(screen.getByText("Running")).toBeInTheDocument();
        expect(screen.getByText("Investigator is working")).toBeInTheDocument();
        expect(screen.getByText("+0.4s")).toBeInTheDocument();
        act(() => {
            vi.advanceTimersByTime(350);
        });
        expect(screen.getByText(/^0\.[1-9]s$/)).toBeInTheDocument();
    });

    it("shows a starting indicator before any agent speaks, and a system group for untagged lines", () => {
        const { rerender } = render(<RunPanel {...props({ status: "processing", ticket: "x", thoughts: [] })} />);
        expect(screen.getByText("Triage is working")).toBeInTheDocument();
        rerender(<RunPanel {...props({ status: "processing", ticket: "x", thoughts: ["loose"] })} />);
        expect(screen.getByText("System")).toBeInTheDocument();
        expect(screen.getByText("Starting the run")).toBeInTheDocument();
    });

    it("toggles the raw log", async () => {
        render(<RunPanel {...props({ status: "completed", ticket: "x", threadId: "t", thoughts: LOG, times: [100, 200, 300, 400], finalResponse: "Done" })} />);
        const toggle = screen.getByRole("button", { name: "Raw log" });
        await userEvent.click(toggle);
        expect(toggle).toHaveAttribute("aria-pressed", "true");
        expect(screen.getByText(/\[Triage\] Classified intent/)).toBeInTheDocument();
        expect(screen.getByText("0.4s")).toBeInTheDocument();
    });

    it("hands control to the human at the gate", async () => {
        const p = props({
            status: "awaiting_approval",
            ticket: "x",
            threadId: "t",
            thoughts: LOG,
            pendingAction: { type: "suspend", amount: null, customer_id: 20, customer_name: "William Allen", description: "Suspend", reason: "ToS" },
        });
        render(<RunPanel {...p} />);
        expect(screen.getByText("Awaiting you")).toBeInTheDocument();
        await userEvent.click(screen.getByRole("button", { name: "Approve & execute" }));
        expect(p.onApprove).toHaveBeenCalledWith("");
    });

    it("asks which customer was meant", async () => {
        const p = props({
            status: "disambiguation",
            ticket: "x",
            thoughts: LOG,
            candidates: [
                { id: 4, name: "Robert Kim", email: "r@kim.io", plan: "enterprise", status: "active" },
                { id: 29, name: "Kayla Roberts", status: "cancelled" },
            ],
            disambiguationMessage: "Multiple customers match",
        });
        render(<RunPanel {...p} />);
        expect(screen.getByText("Multiple customers match")).toBeInTheDocument();
        const kayla = screen.getByRole("button", { name: /Kayla Roberts/ });
        expect(kayla).toHaveTextContent("cancelled");
        await userEvent.click(kayla);
        expect(p.onSelectCandidate).toHaveBeenCalledWith(expect.objectContaining({ id: 29 }));
    });

    it("shows the reply and the receipt once resolved", () => {
        render(
            <RunPanel
                {...props({
                    status: "completed",
                    ticket: "x",
                    threadId: "t",
                    thoughts: LOG,
                    finalResponse: "All sorted.",
                    receipt: { thread_id: "t", total_cost_usd: 0.002, total_tokens: 10, duration_seconds: 3, models_used: {}, cache_hit: false },
                })}
            />
        );
        expect(screen.getByText("Resolved")).toBeInTheDocument();
        expect(screen.getByText("Reply to the customer")).toBeInTheDocument();
        expect(screen.getByRole("region", { name: "Run receipt" })).toBeInTheDocument();
    });

    it("labels cached replies", () => {
        render(<RunPanel {...props({ status: "cached", ticket: "x", finalResponse: "From cache" })} />);
        expect(screen.getByText("Served from semantic cache")).toBeInTheDocument();
        expect(screen.getByText("Cache hit")).toBeInTheDocument();
    });

    it("explains a rate limit without offering a retry", () => {
        render(<RunPanel {...props({ status: "error", ticket: "x", notice: { kind: "rate_limited", title: "Busy", detail: "Wait", retryAfterSeconds: 90 } })} />);
        expect(screen.getByRole("alert")).toHaveTextContent("Busy");
        expect(screen.getByText("1m 30s")).toBeInTheDocument();
        expect(screen.getByText("Rate limited")).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /Try again/ })).not.toBeInTheDocument();
    });

    it("counts down to when another ticket is allowed", () => {
        vi.useFakeTimers();
        render(<RunPanel {...props({ status: "error", ticket: "x", notice: { kind: "rate_limited", title: "Busy", detail: "Wait", retryAfterSeconds: 2 } })} />);
        expect(screen.getByText("2s")).toBeInTheDocument();
        act(() => {
            vi.advanceTimersByTime(1000);
        });
        expect(screen.getByText("1s")).toBeInTheDocument();
        act(() => {
            vi.advanceTimersByTime(2000);
        });
        expect(screen.getByText("You can send another ticket now.")).toBeInTheDocument();
    });

    it("shows the SQL inside the Investigator's section, or on its own if there is none", () => {
        const sqlAttempts = [{ query: "SELECT 1", error: null, rows: 1 }];
        const { rerender, container } = render(<RunPanel {...props({ status: "processing", ticket: "x", thoughts: LOG, sqlAttempts })} />);
        const groups = container.querySelectorAll(".agent-group");
        expect(groups[1]).toHaveTextContent("SQL the agent wrote");
        rerender(<RunPanel {...props({ status: "processing", ticket: "x", thoughts: [LOG[0]], sqlAttempts })} />);
        expect(screen.getByText("SQL the agent wrote")).toBeInTheDocument();
        expect(container.querySelector(".agent-group .sql-trace")).toBeNull();
    });

    it("offers a retry when the backend is offline or the agent fails", async () => {
        const p = props({ status: "error", ticket: "x", notice: { kind: "offline", title: "Down", detail: "d" } });
        const { rerender } = render(<RunPanel {...p} />);
        expect(screen.getByText("Offline")).toBeInTheDocument();
        await userEvent.click(screen.getByRole("button", { name: /Try again/ }));
        expect(p.onRetry).toHaveBeenCalled();
        rerender(<RunPanel {...p} notice={{ kind: "agent", title: "Broke", detail: "d" }} />);
        expect(screen.getByText("Stopped")).toBeInTheDocument();
    });

    it("shows an empty-state-free panel when a notice arrives before a run", () => {
        render(<RunPanel {...props({ notice: { kind: "agent", title: "Broke", detail: "d" } })} />);
        expect(screen.queryByText(/Pick a ticket/)).not.toBeInTheDocument();
    });
});
