import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Dashboard from "../page";
import type { ActionProposal, ChatResponse } from "@/lib/api";

// ── Mock API module ──
vi.mock("@/lib/api", () => ({
    startChat: vi.fn(),
    connectSSE: vi.fn(),
    approveAction: vi.fn(),
    getMetrics: vi.fn().mockResolvedValue({
        agent_metrics: {
            total_requests: 0,
            avg_cost_usd: 0,
            avg_duration_seconds: 0,
            total_cost_usd: 0,
            total_tokens: 0,
            model_distribution: {},
            recent_requests: [],
        },
        cache_metrics: {
            hits: 0,
            misses: 0,
            total_requests: 0,
            hit_rate_percent: 0,
            connected: false,
        },
    }),
    getDbStatus: vi.fn().mockResolvedValue({}),
    clearCache: vi.fn().mockResolvedValue({ status: "ok", keys_deleted: 0 }),
    getTableData: vi.fn().mockResolvedValue({ table: "customers", rows: [] }),
}));

import { startChat, connectSSE, approveAction, getMetrics, clearCache } from "@/lib/api";

describe("Dashboard (page.tsx)", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        vi.useFakeTimers({ shouldAdvanceTime: true });
    });

    afterEach(() => {
        vi.useRealTimers();
    });

    // ── Page Structure ──
    it("renders the Aegis title and support ticket section", () => {
        render(<Dashboard />);
        expect(screen.getByText("Aegis")).toBeInTheDocument();
        expect(screen.getByText("Support Ticket")).toBeInTheDocument();
        expect(screen.getByText("System Online")).toBeInTheDocument();
    });

    it("renders textarea and submit button", () => {
        render(<Dashboard />);
        expect(screen.getByPlaceholderText(/describe the support issue/i)).toBeInTheDocument();
        expect(screen.getByText("Submit Ticket")).toBeInTheDocument();
    });

    // ── Submit Disabled When Empty ──
    it("disables submit button when textarea is empty", () => {
        render(<Dashboard />);
        const submitBtn = screen.getByText("Submit Ticket").closest("button")!;
        expect(submitBtn).toBeDisabled();
    });

    // ── Tab Switching ──
    it("switches between Quick Test and Edge Cases tabs", async () => {
        const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
        render(<Dashboard />);

        // Quick Test tab is active by default — should show "Refund" button
        expect(screen.getByText("Refund")).toBeInTheDocument();
        expect(screen.getByText("Technical")).toBeInTheDocument();

        // Switch to Edge Cases
        await user.click(screen.getByText("Edge Cases"));
        expect(screen.getByText("Not Found")).toBeInTheDocument();
        expect(screen.getByText("Mismatch")).toBeInTheDocument();
        expect(screen.getByText("Typo")).toBeInTheDocument();

        // Switch back to Quick Test
        await user.click(screen.getByText("Quick Test"));
        expect(screen.getByText("Refund")).toBeInTheDocument();
    });

    // ── Form Submission ──
    it("calls startChat + connectSSE on form submission", async () => {
        const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
        const mockResponse: ChatResponse = {
            thread_id: "test-thread-123",
            status: "processing",
            cache_hit: false,
        };
        vi.mocked(startChat).mockResolvedValue(mockResponse);
        vi.mocked(connectSSE).mockImplementation(() => ({}) as unknown as EventSource);

        render(<Dashboard />);

        const textarea = screen.getByPlaceholderText(/describe the support issue/i);
        await user.type(textarea, "Test ticket message");
        await user.click(screen.getByText("Submit Ticket").closest("button")!);

        await waitFor(() => {
            expect(startChat).toHaveBeenCalledWith("Test ticket message");
        });
        await waitFor(() => {
            expect(connectSSE).toHaveBeenCalledWith(
                "test-thread-123",
                expect.any(Function), // onThought
                expect.any(Function), // onApprovalRequired
                expect.any(Function), // onCompleted
                expect.any(Function), // onError
                expect.any(Function), // onDisambiguation
            );
        });
    });

    // ── Demo Button Click ──
    it("submits preset message when demo button is clicked", async () => {
        const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
        vi.mocked(startChat).mockResolvedValue({
            thread_id: "demo-thread",
            status: "processing",
            cache_hit: false,
        });
        vi.mocked(connectSSE).mockImplementation(() => ({}) as unknown as EventSource);

        render(<Dashboard />);

        await user.click(screen.getByText("Refund"));

        await waitFor(() => {
            expect(startChat).toHaveBeenCalledWith(
                expect.stringContaining("David Martinez")
            );
        });
    });

    // ── Cache Hit Path ──
    it("shows cached status when cache hit occurs", async () => {
        const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
        vi.mocked(startChat).mockResolvedValue({
            thread_id: "cached-thread",
            status: "cached",
            cache_hit: true,
        });

        render(<Dashboard />);

        await user.click(screen.getByText("Refund"));

        await waitFor(() => {
            expect(
                screen.getByText(/response served from semantic cache/i)
            ).toBeInTheDocument();
        });
        // connectSSE should NOT be called for cache hits
        expect(connectSSE).not.toHaveBeenCalled();
    });

    // ── Approval Modal Flow ──
    it("shows approval modal when SSE sends approval_required", async () => {
        const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
        const mockAction: ActionProposal = {
            type: "refund",
            amount: 49.0,
            customer_id: 8,
            customer_name: "David Martinez",
            description: "Refund $49 for duplicate charge",
            reason: "Duplicate billing confirmed",
        };

        vi.mocked(startChat).mockResolvedValue({
            thread_id: "approval-thread",
            status: "processing",
            cache_hit: false,
        });
        vi.mocked(connectSSE).mockImplementation(
            (_threadId, _onThought, onApprovalRequired) => {
                // Trigger the approval callback synchronously
                Promise.resolve().then(() => onApprovalRequired(mockAction));
                return {} as unknown as EventSource;
            }
        );

        render(<Dashboard />);
        await user.click(screen.getByText("Refund"));

        // Wait for modal to appear
        await waitFor(() => {
            expect(screen.getByText("Human Approval Required")).toBeInTheDocument();
        });
        expect(screen.getByText("David Martinez")).toBeInTheDocument();
        expect(screen.getByText("Refund $49 for duplicate charge")).toBeInTheDocument();
    });

    it("calls approveAction with true when Approve is clicked", async () => {
        const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
        const mockAction: ActionProposal = {
            type: "refund",
            amount: 49.0,
            customer_id: 8,
            customer_name: "David Martinez",
            description: "Refund $49",
            reason: "Confirmed",
        };

        vi.mocked(startChat).mockResolvedValue({
            thread_id: "approve-thread",
            status: "processing",
            cache_hit: false,
        });
        vi.mocked(connectSSE).mockImplementation(
            (_threadId, _onThought, onApprovalRequired) => {
                setTimeout(() => onApprovalRequired(mockAction), 0);
                return {} as unknown as EventSource;
            }
        );
        vi.mocked(approveAction).mockResolvedValue({
            thread_id: "approve-thread",
            status: "completed",
            result: "Refund processed",
        });

        render(<Dashboard />);
        await user.click(screen.getByText("Refund"));

        await waitFor(() => {
            expect(screen.getByText("Human Approval Required")).toBeInTheDocument();
        });

        // Click Approve — the ApprovalModal uses animateOut with 200ms timeout
        const approveBtn = screen.getByRole("button", { name: /approve/i });
        await user.click(approveBtn);

        // Advance past the 200ms animation delay
        vi.advanceTimersByTime(300);

        await waitFor(() => {
            expect(approveAction).toHaveBeenCalledWith("approve-thread", true);
        });
    });

    it("calls approveAction with false when Deny is clicked", async () => {
        const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
        const mockAction: ActionProposal = {
            type: "suspend",
            amount: null,
            customer_id: 20,
            customer_name: "William Allen",
            description: "Suspend account",
            reason: "TOS violation",
        };

        vi.mocked(startChat).mockResolvedValue({
            thread_id: "deny-thread",
            status: "processing",
            cache_hit: false,
        });
        vi.mocked(connectSSE).mockImplementation(
            (_threadId, _onThought, onApprovalRequired) => {
                setTimeout(() => onApprovalRequired(mockAction), 0);
                return {} as unknown as EventSource;
            }
        );
        vi.mocked(approveAction).mockResolvedValue({
            thread_id: "deny-thread",
            status: "completed",
            result: "Action denied",
        });

        render(<Dashboard />);
        await user.click(screen.getByText("Refund"));

        await waitFor(() => {
            expect(screen.getByText("Human Approval Required")).toBeInTheDocument();
        });

        const denyBtn = screen.getByRole("button", { name: /deny/i });
        await user.click(denyBtn);

        vi.advanceTimersByTime(300);

        await waitFor(() => {
            expect(approveAction).toHaveBeenCalledWith(
                "deny-thread",
                false,
                "Manager denied the proposed action"
            );
        });
    });

    // ── Enter Key Submission ──
    it("submits on Enter key (without Shift)", async () => {
        const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
        vi.mocked(startChat).mockResolvedValue({
            thread_id: "enter-thread",
            status: "processing",
            cache_hit: false,
        });
        vi.mocked(connectSSE).mockImplementation(() => ({}) as unknown as EventSource);

        render(<Dashboard />);

        const textarea = screen.getByPlaceholderText(/describe the support issue/i);
        await user.type(textarea, "Enter test");
        await user.keyboard("{Enter}");

        await waitFor(() => {
            expect(startChat).toHaveBeenCalledWith("Enter test");
        });
    });

    // ── Error Path ──
    it("shows error status when startChat throws", async () => {
        const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
        vi.mocked(startChat).mockRejectedValue(new Error("Connection refused"));

        render(<Dashboard />);
        const textarea = screen.getByPlaceholderText(/describe the support issue/i);
        await user.type(textarea, "error test");
        await user.click(screen.getByText("Submit Ticket").closest("button")!);

        await waitFor(() => {
            const matches = screen.getAllByText(/failed to connect/i);
            expect(matches.length).toBeGreaterThanOrEqual(1);
        });
    });

    // ── SSE Error Event ──
    it("shows error thought when SSE emits error", async () => {
        const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
        vi.mocked(startChat).mockResolvedValue({
            thread_id: "sse-err-thread",
            status: "processing",
            cache_hit: false,
        });
        vi.mocked(connectSSE).mockImplementation(
            (_threadId, _onThought, _onApproval, _onCompleted, onError) => {
                Promise.resolve().then(() => onError("Agent crashed"));
                return {} as unknown as EventSource;
            }
        );

        render(<Dashboard />);
        await user.click(screen.getByText("Refund"));

        await waitFor(() => {
            expect(screen.getByText(/Error: Agent crashed/)).toBeInTheDocument();
        });
    });

    // ── SSE Completed Event ──
    it("shows final response when SSE completes", async () => {
        const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
        vi.mocked(startChat).mockResolvedValue({
            thread_id: "complete-thread",
            status: "processing",
            cache_hit: false,
        });
        vi.mocked(connectSSE).mockImplementation(
            (_threadId, _onThought, _onApproval, onCompleted) => {
                Promise.resolve().then(() =>
                    onCompleted("Refund of $49 processed.", ["Step 1", "Step 2"])
                );
                return {} as unknown as EventSource;
            }
        );

        render(<Dashboard />);
        await user.click(screen.getByText("Refund"));

        await waitFor(() => {
            expect(screen.getByText("Refund of $49 processed.")).toBeInTheDocument();
        });
        expect(screen.getByText("Resolution Complete")).toBeInTheDocument();
    });

    // ── Disambiguation Flow ──
    it("shows customer selection when SSE sends disambiguation", async () => {
        const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
        vi.mocked(startChat).mockResolvedValue({
            thread_id: "disambig-thread",
            status: "processing",
            cache_hit: false,
        });
        const candidates = [
            { id: 101, name: "Alice Tanaka", email: "alice@test.com", plan: "Pro", status: "active" },
            { id: 102, name: "Bob Nakamura", email: "bob@test.com", plan: "Basic", status: "suspended" },
        ];
        vi.mocked(connectSSE).mockImplementation(
            (_threadId, _onThought, _onApproval, _onCompleted, _onError, onDisambiguation) => {
                Promise.resolve().then(() =>
                    onDisambiguation!(candidates, "Multiple customers found")
                );
                return {} as unknown as EventSource;
            }
        );

        render(<Dashboard />);
        const textarea = screen.getByPlaceholderText(/describe the support issue/i);
        await user.type(textarea, "Alice needs help");
        await user.click(screen.getByText("Submit Ticket").closest("button")!);

        await waitFor(() => {
            expect(screen.getByText("Select Customer")).toBeInTheDocument();
        });
        expect(screen.getByText("Multiple customers found")).toBeInTheDocument();
        expect(screen.getByText(/#101 Alice Tanaka/)).toBeInTheDocument();
        expect(screen.getByText(/#102 Bob Nakamura/)).toBeInTheDocument();
        // Should show plan badges
        expect(screen.getByText("Pro")).toBeInTheDocument();
        expect(screen.getByText("Basic")).toBeInTheDocument();
        // Should show non-active status
        expect(screen.getByText("suspended")).toBeInTheDocument();
    });

    it("re-submits with corrected customer when disambiguation candidate is selected", async () => {
        const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

        let callCount = 0;
        vi.mocked(startChat).mockImplementation(async () => {
            callCount++;
            return { thread_id: `thread-${callCount}`, status: "processing", cache_hit: false };
        });

        const candidates = [
            { id: 1, name: "David Martinez", email: "d@t.com", plan: "Pro", status: "active" },
        ];
        vi.mocked(connectSSE).mockImplementation(
            (_threadId, _onThought, _onApproval, _onCompleted, _onError, onDisambiguation) => {
                if (callCount === 1 && onDisambiguation) {
                    Promise.resolve().then(() =>
                        onDisambiguation(candidates, "Pick one")
                    );
                }
                return {} as unknown as EventSource;
            }
        );

        render(<Dashboard />);
        const textarea = screen.getByPlaceholderText(/describe the support issue/i);
        await user.type(textarea, "Customer #8 David needs help");
        await user.click(screen.getByText("Submit Ticket").closest("button")!);

        await waitFor(() => {
            expect(screen.getByText("Select Customer")).toBeInTheDocument();
        });

        // Select the candidate
        await user.click(screen.getByText(/#1 David Martinez/));

        await waitFor(() => {
            expect(startChat).toHaveBeenCalledWith(
                expect.stringContaining("Customer #1 David Martinez")
            );
        });
    });

    // ── Approve Failure ──
    it("shows failure thought when approveAction throws", async () => {
        const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
        const mockAction: ActionProposal = {
            type: "refund",
            amount: 49.0,
            customer_id: 8,
            customer_name: "David",
            description: "Refund",
            reason: "ok",
        };

        vi.mocked(startChat).mockResolvedValue({
            thread_id: "fail-approve-thread",
            status: "processing",
            cache_hit: false,
        });
        vi.mocked(connectSSE).mockImplementation(
            (_threadId, _onThought, onApprovalRequired) => {
                Promise.resolve().then(() => onApprovalRequired(mockAction));
                return {} as unknown as EventSource;
            }
        );
        vi.mocked(approveAction).mockRejectedValue(new Error("Network error"));

        render(<Dashboard />);
        await user.click(screen.getByText("Refund"));

        await waitFor(() => {
            expect(screen.getByText("Human Approval Required")).toBeInTheDocument();
        });

        await user.click(screen.getByRole("button", { name: /approve/i }));
        vi.advanceTimersByTime(300);

        await waitFor(() => {
            expect(screen.getByText(/Approval failed/i)).toBeInTheDocument();
        });
    });

    // ── Deny Failure ──
    it("shows failure thought when deny approveAction throws", async () => {
        const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
        const mockAction: ActionProposal = {
            type: "suspend",
            amount: null,
            customer_id: 20,
            customer_name: "Test",
            description: "Suspend",
            reason: "TOS",
        };

        vi.mocked(startChat).mockResolvedValue({
            thread_id: "fail-deny-thread",
            status: "processing",
            cache_hit: false,
        });
        vi.mocked(connectSSE).mockImplementation(
            (_threadId, _onThought, onApprovalRequired) => {
                Promise.resolve().then(() => onApprovalRequired(mockAction));
                return {} as unknown as EventSource;
            }
        );
        vi.mocked(approveAction).mockRejectedValue(new Error("Server error"));

        render(<Dashboard />);
        await user.click(screen.getByText("Refund"));

        await waitFor(() => {
            expect(screen.getByText("Human Approval Required")).toBeInTheDocument();
        });

        await user.click(screen.getByRole("button", { name: /deny/i }));
        vi.advanceTimersByTime(300);

        await waitFor(() => {
            expect(screen.getByText(/Denial submission failed/i)).toBeInTheDocument();
        });
    });

    // ── Empty Submit Guard ──
    it("does not call startChat when message is empty on submit", async () => {
        const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
        render(<Dashboard />);

        // Try keyboard Enter on empty textarea
        const textarea = screen.getByPlaceholderText(/describe the support issue/i);
        await user.click(textarea);
        await user.keyboard("{Enter}");

        expect(startChat).not.toHaveBeenCalled();
    });

    // ── SSE Thought Streaming ──
    it("displays streamed thoughts from SSE onThought callback", async () => {
        const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
        vi.mocked(startChat).mockResolvedValue({
            thread_id: "thought-thread",
            status: "processing",
            cache_hit: false,
        });
        vi.mocked(connectSSE).mockImplementation(
            (_threadId, onThought) => {
                Promise.resolve().then(() => {
                    onThought("🔍 Identifying customer...");
                    onThought("📋 Checking billing records...");
                });
                return {} as unknown as EventSource;
            }
        );

        render(<Dashboard />);
        await user.click(screen.getByText("Refund"));

        await waitFor(() => {
            expect(screen.getByText(/Identifying customer/)).toBeInTheDocument();
        });
        expect(screen.getByText(/Checking billing records/)).toBeInTheDocument();
    });

    // ── onCacheCleared error catch ──
    it("handles getMetrics error in onCacheCleared callback silently", async () => {
        const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

        // First call ok (initial render), second call rejects (after cache clear)
        vi.mocked(getMetrics)
            .mockResolvedValueOnce({
                agent_metrics: {
                    total_requests: 0,
                    avg_cost_usd: 0,
                    avg_duration_seconds: 0,
                    total_cost_usd: 0,
                    total_tokens: 0,
                    model_distribution: {},
                    recent_requests: [],
                },
                cache_metrics: {
                    hits: 0,
                    misses: 0,
                    total_requests: 0,
                    hit_rate_percent: 0,
                    connected: true,
                },
            })
            .mockRejectedValueOnce(new Error("Metrics unavailable"));

        vi.mocked(clearCache).mockResolvedValue({ status: "cleared", keys_deleted: 3 });

        render(<Dashboard />);

        // Wait for metrics to load, then click the clear cache button
        await waitFor(() => {
            expect(screen.getByTitle("Clear cache")).toBeInTheDocument();
        });

        await user.click(screen.getByTitle("Clear cache"));

        // The cache clear should succeed even though getMetrics rejects
        await waitFor(() => {
            expect(screen.getByText(/Cleared/)).toBeInTheDocument();
        });
    });
});

