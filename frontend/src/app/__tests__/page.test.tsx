import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, act, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Dashboard from "../page";
import type { ActionProposal, CustomerCandidate, Metrics, SqlAttempt } from "@/lib/api";

Element.prototype.scrollTo = vi.fn();

const METRICS: Metrics = {
    agent_metrics: {
        total_requests: 1,
        avg_cost_usd: 0.002,
        avg_duration_seconds: 5,
        total_cost_usd: 0.002,
        total_tokens: 100,
        hitl_approval_rate: 100,
        avg_hitl_wait_seconds: 3,
        cost_saved_by_cache: 0,
        model_distribution: { "gpt-4.1": 1 },
        recent_requests: [
            { total_cost_usd: 0.0021, total_tokens: 1234, duration_seconds: 4.2, models_used: {}, cache_hit: false },
        ],
    },
    cache_metrics: { hits: 0, misses: 0, total_requests: 0, hit_rate_percent: 0, connected: false },
};

vi.mock("@/lib/api", async (importOriginal) => {
    const actual = await importOriginal<typeof import("@/lib/api")>();
    return {
        ...actual,
        startChat: vi.fn(),
        connectSSE: vi.fn(),
        approveAction: vi.fn(),
        getThread: vi.fn(),
        getMetrics: vi.fn(),
        getDbStatus: vi.fn().mockResolvedValue({}),
        clearCache: vi.fn().mockResolvedValue({ status: "ok", keys_deleted: 0 }),
        getTableData: vi.fn().mockResolvedValue({ table: "customers", rows: [] }),
        getTraces: vi.fn().mockResolvedValue({ traces: [], error: null }),
        getTracingStatus: vi.fn().mockResolvedValue({ enabled: true, project: "aegis", connected: true }),
    };
});

import { ApiError, startChat, connectSSE, approveAction, getMetrics, getThread } from "@/lib/api";

type Callbacks = {
    onThought: (s: string) => void;
    onApproval: (a: ActionProposal) => void;
    onCompleted: (r: string, log: string[]) => void;
    onError: (e: string) => void;
    onDisambiguation: (c: CustomerCandidate[], r: string) => void;
    onSql: (a: SqlAttempt[]) => void;
};

let cb: Callbacks;
const close = vi.fn();

const ACTION: ActionProposal = {
    type: "refund",
    amount: 49,
    customer_id: 8,
    customer_name: "David Martinez",
    description: "Refund the duplicate charge",
    reason: "Two identical charges",
};

async function startRun(label = /Double charge/) {
    await userEvent.click(screen.getAllByRole("button", { name: label })[0]);
    await waitFor(() => expect(connectSSE).toHaveBeenCalled());
}

describe("Dashboard", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        vi.mocked(getThread).mockReset();
        // Fake timers everywhere so receipt polls can't leak into the next test.
        vi.useFakeTimers({ shouldAdvanceTime: true });
        vi.mocked(getMetrics).mockResolvedValue(METRICS);
        vi.mocked(startChat).mockResolvedValue({ thread_id: "t1", status: "processing", cache_hit: false });
        vi.mocked(connectSSE).mockImplementation((_id, onThought, onApproval, onCompleted, onError, onDisambiguation, onSql) => {
            cb = { onThought, onApproval, onCompleted, onError, onDisambiguation: onDisambiguation!, onSql: onSql! };
            return { close } as unknown as EventSource;
        });
        localStorage.clear();
    });

    afterEach(() => {
        vi.clearAllTimers();
        vi.useRealTimers();
    });

    it("explains itself on first paint and reports the backend as live", async () => {
        render(<Dashboard />);
        expect(screen.getByRole("heading", { level: 1, name: "Aegis" })).toBeInTheDocument();
        expect(screen.getByText(/You release the action/)).toBeInTheDocument();
        expect(screen.getByText("Connecting")).toBeInTheDocument();
        expect(await screen.findByText("Live")).toBeInTheDocument();
    });

    it("reports the backend offline when the metrics probe fails", async () => {
        vi.mocked(getMetrics).mockRejectedValue(new Error("down"));
        render(<Dashboard />);
        expect(await screen.findByText("Offline")).toBeInTheDocument();
        expect(screen.getByText("Telemetry offline")).toBeInTheDocument();
        expect(screen.getByText(/offline right now/)).toBeInTheDocument();
    });

    it("polls metrics on an interval", async () => {
        vi.useFakeTimers({ shouldAdvanceTime: true });
        render(<Dashboard />);
        await waitFor(() => expect(getMetrics).toHaveBeenCalledTimes(1));
        await act(async () => {
            vi.advanceTimersByTime(8000);
        });
        expect(getMetrics).toHaveBeenCalledTimes(2);
    });

    it("runs a preset, streams steps, holds at the gate and releases on approval", async () => {
        vi.mocked(approveAction).mockResolvedValue({ thread_id: "t1", status: "completed", result: "Refund recommended." });
        vi.mocked(getThread).mockResolvedValue({
            message: "m",
            status: "completed",
            thought_log: [
                "✓ [Triage] Classified intent: billing (confidence: 99%)",
                "✓ [Resolution] Human decision: approved — ok",
                "✓ [Resolution] Action executed: Refund recommended",
            ],
            proposed_action: null,
            final_response: "Refund recommended.",
            sql_attempts: [{ query: "SELECT * FROM billing", error: null, rows: 3 }],
            receipt: METRICS.agent_metrics.recent_requests[0],
        });
        render(<Dashboard />);
        await startRun();
        expect(startChat).toHaveBeenCalledWith(expect.stringContaining("Customer #10 Chris Johnson"));
        expect((screen.getByLabelText("Support ticket") as HTMLTextAreaElement).value).toContain("charged $49 twice");

        act(() => cb.onThought("✓ [Triage] Classified intent: billing (confidence: 99%)"));
        expect(screen.getByText("billing")).toBeInTheDocument();
        act(() => cb.onSql([{ query: "SELECT * FROM billing", error: null, rows: 2 }]));
        expect(screen.getByText("2 rows")).toBeInTheDocument();

        act(() => cb.onApproval(ACTION));
        expect(screen.getByText("Awaiting you")).toBeInTheDocument();
        expect(document.querySelector(".app")).toHaveAttribute("data-held", "true");

        await userEvent.type(screen.getByLabelText(/Note for the audit log/), "ok");
        await userEvent.click(screen.getByRole("button", { name: "Approve & execute" }));
        expect(approveAction).toHaveBeenCalledWith("t1", true, "ok");
        expect((await screen.findAllByText("Refund recommended.")).length).toBeGreaterThan(0);
        expect(screen.getByText(/Released: Refund recommended/)).toBeInTheDocument();
        expect(screen.getByText("Resolved")).toBeInTheDocument();
        expect(screen.getByText("3 rows")).toBeInTheDocument();
        // The receipt comes from the tracker's record of this thread.
        expect(await screen.findByRole("region", { name: "Run receipt" }, { timeout: 3000 })).toBeInTheDocument();
    });

    it("falls back to a local log line and default copy when the thread can't be re-read", async () => {
        vi.mocked(approveAction).mockResolvedValue({ thread_id: "t1", status: "completed", result: null });
        vi.mocked(getThread).mockRejectedValue(new Error("gone"));
        render(<Dashboard />);
        await startRun();
        act(() => cb.onApproval(ACTION));
        await userEvent.click(screen.getByRole("button", { name: "Deny" }));
        expect(approveAction).toHaveBeenCalledWith("t1", false, "Manager denied the proposed action");
        expect((await screen.findAllByText("Action denied. No changes were made.")).length).toBeGreaterThan(0);
        expect(screen.getByText(/You denied/)).toBeInTheDocument();
    });

    it("uses default approve copy and logs approval without a note", async () => {
        vi.mocked(approveAction).mockResolvedValue({ thread_id: "t1", status: "completed", result: null });
        vi.mocked(getThread).mockRejectedValue(new Error("gone"));
        render(<Dashboard />);
        await startRun();
        act(() => cb.onApproval(ACTION));
        await userEvent.click(screen.getByRole("button", { name: "Approve & execute" }));
        expect((await screen.findAllByText("Action released.")).length).toBeGreaterThan(0);
        expect(screen.getAllByRole("listitem").some((li) => /You approved the action(\+[0-9.]+s)?$/.test(li.textContent ?? ""))).toBe(true);
    });

    it("keeps the streamed SQL when the re-read thread has none", async () => {
        vi.mocked(approveAction).mockResolvedValue({ thread_id: "t1", status: "completed", result: "ok" });
        vi.mocked(getThread).mockResolvedValue({ message: "m", status: "completed", thought_log: ["✓ [Investigator] Generated SQL query for investigation"], proposed_action: null, final_response: "ok" });
        render(<Dashboard />);
        await startRun();
        act(() => cb.onSql([{ query: "SELECT 1", error: null, rows: 9 }]));
        act(() => cb.onApproval(ACTION));
        await userEvent.click(screen.getByRole("button", { name: "Approve & execute" }));
        expect((await screen.findAllByText("ok")).length).toBeGreaterThan(0);
        expect(screen.getByText("9 rows")).toBeInTheDocument();
    });

    it("labels a deny in flight as denying, not releasing", async () => {
        let resolve!: (v: { thread_id: string; status: string; result: string | null }) => void;
        vi.mocked(approveAction).mockReturnValue(new Promise((r) => (resolve = r)));
        vi.mocked(getThread).mockRejectedValue(new Error("gone"));
        render(<Dashboard />);
        await startRun();
        act(() => cb.onApproval(ACTION));
        await userEvent.click(screen.getByRole("button", { name: "Deny" }));
        expect(screen.getByRole("button", { name: /Denying/ })).toBeInTheDocument();
        expect(screen.queryByText(/Releasing/)).not.toBeInTheDocument();
        expect(screen.getByText("Denying", { selector: ".badge" })).toBeInTheDocument();
        await act(async () => resolve({ thread_id: "t1", status: "completed", result: "Denied." }));
        expect((await screen.findAllByText("Denied.")).length).toBeGreaterThan(0);
    });

    it("polls briefly for the receipt, and drops it if a new run started", async () => {
        vi.useFakeTimers({ shouldAdvanceTime: true });
        vi.mocked(getThread)
            .mockResolvedValueOnce({ message: "m", status: "completed", thought_log: [], proposed_action: null, final_response: "a", receipt: null })
            .mockResolvedValueOnce({ message: "m", status: "completed", thought_log: [], proposed_action: null, final_response: "a", receipt: METRICS.agent_metrics.recent_requests[0] });
        render(<Dashboard />);
        await startRun();
        act(() => cb.onCompleted("done", []));
        await act(async () => {
            await vi.advanceTimersByTimeAsync(900);
        });
        await act(async () => {
            await vi.advanceTimersByTimeAsync(900);
        });
        expect(await screen.findByRole("region", { name: "Run receipt" })).toBeInTheDocument();
        expect(getThread).toHaveBeenCalledTimes(2);
    });

    it("gives up on the receipt after a few tries or on error, and ignores stale runs", async () => {
        vi.useFakeTimers({ shouldAdvanceTime: true });
        vi.mocked(getThread).mockResolvedValue({ message: "m", status: "completed", thought_log: [], proposed_action: null, final_response: "a" });
        render(<Dashboard />);
        await startRun();
        act(() => cb.onCompleted("done", []));
        for (let i = 0; i < 4; i++) {
            await act(async () => {
                await vi.advanceTimersByTimeAsync(900);
            });
        }
        expect(getThread).toHaveBeenCalledTimes(3);
        expect(screen.queryByRole("region", { name: "Run receipt" })).not.toBeInTheDocument();

        // A receipt fetch that fails is swallowed.
        vi.mocked(getThread).mockRejectedValueOnce(new Error("x"));
        await userEvent.click(screen.getAllByRole("button", { name: /Double charge/ })[0]);
        await waitFor(() => expect(startChat).toHaveBeenCalledTimes(2));
        act(() => cb.onCompleted("done", []));
        await act(async () => {
            await vi.advanceTimersByTimeAsync(900);
        });

        // A receipt for an old thread never lands on the new run.
        vi.mocked(getThread).mockResolvedValue({ message: "m", status: "completed", thought_log: [], proposed_action: null, final_response: "a", receipt: METRICS.agent_metrics.recent_requests[0] });
        await userEvent.click(screen.getAllByRole("button", { name: /Double charge/ })[0]);
        await waitFor(() => expect(startChat).toHaveBeenCalledTimes(3));
        act(() => cb.onCompleted("done", []));
        vi.mocked(startChat).mockReturnValueOnce(new Promise(() => {}));
        await userEvent.click(screen.getAllByRole("button", { name: /Double charge/ })[0]);
        await act(async () => {
            await vi.advanceTimersByTimeAsync(900);
        });
        expect(screen.queryByRole("region", { name: "Run receipt" })).not.toBeInTheDocument();
    });

    it("keeps the gate open and explains when the decision fails", async () => {
        vi.mocked(approveAction).mockRejectedValue(new ApiError("x", 500, "resume failed"));
        render(<Dashboard />);
        await startRun();
        act(() => cb.onApproval(ACTION));
        await userEvent.click(screen.getByRole("button", { name: "Approve & execute" }));
        expect(await screen.findByText("resume failed")).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Approve & execute" })).toBeEnabled();
    });

    it("shows the reply when the run completes without a gate, and records it in history", async () => {
        render(<Dashboard />);
        await startRun();
        act(() => cb.onCompleted("Here is your answer", ["✓ [Triage] Classified intent: general (confidence: 90%)"]));
        expect(screen.getAllByText("Here is your answer").length).toBeGreaterThan(0);
        expect(await screen.findByText("Recent Tickets")).toBeInTheDocument();
    });

    it("reports a lost stream and lets the visitor retry", async () => {
        render(<Dashboard />);
        await startRun();
        act(() => cb.onError("Connection lost"));
        expect(screen.getByText(/Lost the live connection/)).toBeInTheDocument();
        await userEvent.click(screen.getByRole("button", { name: /Try again/ }));
        expect(startChat).toHaveBeenCalledTimes(2);
        expect(close).toHaveBeenCalled();
    });

    it("records a completed run even when the backend sent no reply text", async () => {
        render(<Dashboard />);
        await startRun();
        act(() => cb.onCompleted(null as unknown as string, []));
        expect(await screen.findByText("Recent Tickets")).toBeInTheDocument();
    });

    it("shows other stream errors verbatim", async () => {
        render(<Dashboard />);
        await startRun();
        act(() => cb.onError("Agent workflow failed"));
        expect(screen.getByText("Agent workflow failed")).toBeInTheDocument();
    });

    it("explains a rate limit without faking a run", async () => {
        vi.mocked(startChat).mockRejectedValue(new ApiError("x", 429, "Easy there.", null));
        render(<Dashboard />);
        await userEvent.click(screen.getAllByRole("button", { name: /Double charge/ })[0]);
        expect(await screen.findByText("Easy there.")).toBeInTheDocument();
        expect(screen.getByText("Rate limited")).toBeInTheDocument();
        expect(connectSSE).not.toHaveBeenCalled();
    });

    it("marks the backend offline when the ticket can't be sent", async () => {
        vi.mocked(startChat).mockRejectedValue(new ApiError("x", 0));
        render(<Dashboard />);
        await screen.findByText("Live");
        await userEvent.click(screen.getAllByRole("button", { name: /Double charge/ })[0]);
        expect((await screen.findAllByText(/Can't reach the Aegis backend/)).length).toBeGreaterThan(0);
        expect(screen.getAllByText("Offline").length).toBeGreaterThan(0);
    });

    it("serves cache hits from the stored thread", async () => {
        vi.mocked(startChat).mockResolvedValue({ thread_id: "c1", status: "cached", cache_hit: true });
        vi.mocked(getThread).mockResolvedValueOnce({ message: "m", status: "cached", thought_log: ["✓ [Triage] Classified intent: billing (confidence: 99%)"], proposed_action: null, final_response: "Cached reply", sql_attempts: [{ query: "SELECT 1", error: null, rows: 7 }], receipt: METRICS.agent_metrics.recent_requests[0] });
        render(<Dashboard />);
        await userEvent.click(screen.getAllByRole("button", { name: /Double charge/ })[0]);
        expect(await screen.findByText("Cached reply")).toBeInTheDocument();
        expect(screen.getByText("7 rows")).toBeInTheDocument();
        expect(screen.getByRole("region", { name: "Run receipt" })).toBeInTheDocument();
        expect(screen.getByText("Cache hit")).toBeInTheDocument();
    });

    it("uses fallback copy for cache hits with no stored reply or no stored thread", async () => {
        vi.mocked(startChat).mockResolvedValue({ thread_id: "c1", status: "cached", cache_hit: true });
        vi.mocked(getThread).mockResolvedValueOnce({ message: "m", status: "completed", thought_log: [], proposed_action: null, final_response: null });
        render(<Dashboard />);
        await userEvent.click(screen.getAllByRole("button", { name: /Double charge/ })[0]);
        expect(await screen.findByText("Served from the response cache.")).toBeInTheDocument();

        vi.mocked(getThread).mockRejectedValueOnce(new Error("evicted"));
        await userEvent.click(screen.getAllByRole("button", { name: /Double charge/ })[0]);
        expect(await screen.findByText(/answered recently/)).toBeInTheDocument();
    });

    it("lets the human pick the right customer and re-runs with the correction", async () => {
        render(<Dashboard />);
        await userEvent.click(screen.getByRole("tab", { name: /Edge cases/ }));
        await startRun(/Ambiguous name/);
        act(() => cb.onDisambiguation([{ id: 4, name: "Robert Kim" }], "Multiple customers match"));
        await userEvent.click(screen.getByRole("button", { name: /Robert Kim/ }));
        expect(startChat).toHaveBeenLastCalledWith(expect.stringMatching(/^Customer #4 Robert Kim emailed/));
    });

    it("prefixes the chosen customer when the ticket didn't name one in the usual form", async () => {
        render(<Dashboard />);
        await userEvent.type(screen.getByLabelText("Support ticket"), "someone was double charged");
        fireEvent.keyDown(screen.getByLabelText("Support ticket"), { key: "Enter" });
        await waitFor(() => expect(connectSSE).toHaveBeenCalled());
        act(() => cb.onDisambiguation([{ id: 29, name: "Kayla Roberts" }], "Pick one"));
        await userEvent.click(screen.getByRole("button", { name: /Kayla Roberts/ }));
        expect(startChat).toHaveBeenLastCalledWith("Customer #29 Kayla Roberts: someone was double charged");
    });

    it("ignores empty submissions and records failed runs in history", async () => {
        vi.mocked(startChat).mockRejectedValue(new Error("boom"));
        render(<Dashboard />);
        fireEvent.keyDown(screen.getByLabelText("Support ticket"), { key: "Enter" });
        expect(startChat).not.toHaveBeenCalled();
        await userEvent.type(screen.getByLabelText("Support ticket"), "hello");
        await userEvent.click(screen.getByRole("button", { name: /Run agents/ }));
        expect((await screen.findAllByText("Something went wrong")).length).toBeGreaterThan(0);
        expect(await screen.findByText("Recent Tickets")).toBeInTheDocument();
    });

    it("scrolls the run into view on narrow screens", async () => {
        vi.useFakeTimers({ shouldAdvanceTime: true });
        const scrollTo = vi.fn();
        window.scrollTo = scrollTo as unknown as typeof window.scrollTo;
        window.matchMedia = vi.fn().mockReturnValue({ matches: true }) as unknown as typeof window.matchMedia;
        render(<Dashboard />);
        await startRun();
        await act(async () => {
            vi.advanceTimersByTime(100);
        });
        expect(scrollTo).toHaveBeenCalled();
        window.matchMedia = vi.fn().mockReturnValue({ matches: false }) as unknown as typeof window.matchMedia;
        scrollTo.mockClear();
        await userEvent.click(screen.getByRole("button", { name: /Try again|Double charge/ }));
        await act(async () => {
            vi.advanceTimersByTime(100);
        });
        expect(scrollTo).not.toHaveBeenCalled();
    });

    it("tolerates the run panel vanishing before the deferred scroll", async () => {
        vi.useFakeTimers({ shouldAdvanceTime: true });
        window.matchMedia = vi.fn().mockReturnValue({ matches: true }) as unknown as typeof window.matchMedia;
        const getById = vi.spyOn(document, "getElementById").mockReturnValue(null);
        render(<Dashboard />);
        await startRun();
        await act(async () => {
            vi.advanceTimersByTime(100);
        });
        getById.mockRestore();
        window.matchMedia = vi.fn().mockReturnValue({ matches: false }) as unknown as typeof window.matchMedia;
    });

    it("opens and closes the traces drawer, and closes the stream on unmount", async () => {
        const { unmount } = render(<Dashboard />);
        await userEvent.click(await screen.findByRole("button", { name: /LangSmith traces/ }));
        expect(screen.getByRole("dialog", { name: "LangSmith traces" })).toHaveAttribute("aria-hidden", "false");
        await userEvent.click(screen.getByTitle("Close (Esc)"));
        expect(document.querySelector(".traces-overlay")).toHaveAttribute("aria-hidden", "true");
        await startRun();
        unmount();
        expect(close).toHaveBeenCalled();
    });

    it("refreshes metrics after the cache is cleared", async () => {
        vi.mocked(getMetrics).mockResolvedValue({ ...METRICS, cache_metrics: { ...METRICS.cache_metrics, connected: true } });
        render(<Dashboard />);
        await screen.findByText("Live");
        const before = vi.mocked(getMetrics).mock.calls.length;
        await userEvent.click(screen.getByRole("button", { name: "Clear response cache" }));
        await waitFor(() => expect(vi.mocked(getMetrics).mock.calls.length).toBeGreaterThan(before));
    });

    it("fills the input from ticket history", async () => {
        localStorage.setItem("aegis-ticket-history", JSON.stringify([{ message: "old ticket", timestamp: Date.now(), status: "completed", responsePreview: "ok" }]));
        render(<Dashboard />);
        await userEvent.click(await screen.findByText("Recent Tickets"));
        await userEvent.click(screen.getByRole("button", { name: /old ticket/ }));
        expect(screen.getByLabelText("Support ticket")).toHaveValue("old ticket");
    });
});
