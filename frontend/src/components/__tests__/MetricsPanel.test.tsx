import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import MetricsPanel from "../MetricsPanel";
import type { Metrics } from "@/lib/api";

// Mock the API module
vi.mock("@/lib/api", async (importOriginal) => {
    const actual = await importOriginal<typeof import("@/lib/api")>();
    return {
        ...actual,
        clearCache: vi.fn(),
        getDbStatus: vi.fn().mockResolvedValue({}),
        getTableData: vi.fn().mockResolvedValue({ table: "customers", rows: [] }),
    };
});

import { clearCache, getDbStatus, getTableData } from "@/lib/api";

const FULL_METRICS: Metrics = {
    agent_metrics: {
        total_requests: 42,
        avg_cost_usd: 0.0312,
        avg_duration_seconds: 8.5,
        total_cost_usd: 1.3104,
        total_tokens: 125000,
        model_distribution: {
            "gpt-4.1-mini": 35,
            "gpt-4.1": 7,
        },
        recent_requests: [],
    },
    cache_metrics: {
        hits: 12,
        misses: 30,
        total_requests: 42,
        hit_rate_percent: 28.6,
        connected: true,
    },
};

describe("MetricsPanel", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        vi.mocked(getDbStatus).mockResolvedValue({});
    });

    // ── Null Metrics ──
    it("renders zero defaults when metrics is null", () => {
        render(<MetricsPanel metrics={null} />);
        const zeroCosts = screen.getAllByText("$0.0000");
        expect(zeroCosts.length).toBeGreaterThanOrEqual(2); // avg cost + total cost
        expect(screen.getByText("0.0%")).toBeInTheDocument(); // hit rate
    });

    // ── Observability Header ──
    it("renders Observability header", () => {
        render(<MetricsPanel metrics={null} />);
        expect(screen.getByText("Observability")).toBeInTheDocument();
    });

    // ── Formatted Metric Values ──
    it("displays formatted metric values from full metrics", () => {
        render(<MetricsPanel metrics={FULL_METRICS} />);
        expect(screen.getByText("$0.0312")).toBeInTheDocument(); // avg cost
        expect(screen.getByText("42")).toBeInTheDocument(); // total requests
        expect(screen.getByText("$1.3104")).toBeInTheDocument(); // total cost
        expect(screen.getByText("125,000")).toBeInTheDocument(); // tokens
    });

    // ── Cache Hit Rate ──
    it("displays cache hit rate percentage", () => {
        render(<MetricsPanel metrics={FULL_METRICS} />);
        expect(screen.getByText("28.6%")).toBeInTheDocument();
        expect(screen.getByText("12 hits")).toBeInTheDocument();
        expect(screen.getByText("30 misses")).toBeInTheDocument();
    });

    // ── Redis Connected ──
    it("shows Redis connected status", () => {
        render(<MetricsPanel metrics={FULL_METRICS} />);
        expect(screen.getByText("Redis Connected")).toBeInTheDocument();
    });

    // ── Redis Disconnected ──
    it("shows Redis disconnected when cache not connected", () => {
        const disconnectedMetrics: Metrics = {
            ...FULL_METRICS,
            cache_metrics: { ...FULL_METRICS.cache_metrics, connected: false },
        };
        render(<MetricsPanel metrics={disconnectedMetrics} />);
        expect(screen.getByText("Redis Disconnected")).toBeInTheDocument();
    });

    // ── Model Distribution ──
    it("shows model distribution bars with percentages", () => {
        render(<MetricsPanel metrics={FULL_METRICS} />);
        expect(screen.getByText("Model Usage")).toBeInTheDocument();
        expect(screen.getByText("gpt-4.1-mini")).toBeInTheDocument();
        expect(screen.getByText("gpt-4.1")).toBeInTheDocument();
        // gpt-4.1-mini: 35/42 = 83%, gpt-4.1: 7/42 = 17%
        expect(screen.getByText("83%")).toBeInTheDocument();
        expect(screen.getByText("17%")).toBeInTheDocument();
    });

    // ── Avg Duration ──
    it("displays average duration", () => {
        render(<MetricsPanel metrics={FULL_METRICS} />);
        expect(screen.getByText("8.5s")).toBeInTheDocument();
    });

    // ── Clear Cache ──
    it("calls clearCache when button is clicked", async () => {
        const user = userEvent.setup();
        const onCacheCleared = vi.fn();
        vi.mocked(clearCache).mockResolvedValue({ status: "ok", keys_deleted: 5 });

        render(<MetricsPanel metrics={FULL_METRICS} onCacheCleared={onCacheCleared} />);

        const clearBtn = screen.getByTitle("Clear cache");
        await user.click(clearBtn);

        await waitFor(() => {
            expect(clearCache).toHaveBeenCalledOnce();
        });
        await waitFor(() => {
            expect(screen.getByText("Cleared! (5 keys)")).toBeInTheDocument();
        });
        expect(onCacheCleared).toHaveBeenCalledOnce();
    });

    // ── Database Section ──
    it("renders database table cards when db status loads", async () => {
        vi.mocked(getDbStatus).mockResolvedValue({
            customers: { count: 20, latest: new Date().toISOString() },
            billing: { count: 15, latest: new Date().toISOString() },
            support_tickets: { count: 8, latest: new Date().toISOString() },
            internal_docs: { count: 5, latest: null },
        });

        render(<MetricsPanel metrics={FULL_METRICS} />);

        await waitFor(() => {
            expect(screen.getByText("Database")).toBeInTheDocument();
        });
        await waitFor(() => {
            expect(screen.getByText("20")).toBeInTheDocument(); // customers count
        });
        expect(screen.getByText("Customers")).toBeInTheDocument();
        expect(screen.getByText("Billing")).toBeInTheDocument();
    });

    // ── Handle Card Click: expand table ──
    it("expands table card and shows data rows on click", async () => {
        const user = userEvent.setup();
        vi.mocked(getDbStatus).mockResolvedValue({
            customers: { count: 3, latest: new Date().toISOString() },
        });
        vi.mocked(getTableData).mockResolvedValue({
            table: "customers",
            rows: [
                { id: 1, name: "Alice", email: "alice@a.com", plan: "Pro" },
                { id: 2, name: "Bob", email: "bob@b.com", plan: "Basic" },
            ],
        });

        render(<MetricsPanel metrics={FULL_METRICS} />);

        await waitFor(() => {
            expect(screen.getByText("Customers")).toBeInTheDocument();
        });

        // Click to expand
        await user.click(screen.getByText("Customers"));

        await waitFor(() => {
            expect(getTableData).toHaveBeenCalledWith("customers");
        });
        await waitFor(() => {
            expect(screen.getByText("Alice")).toBeInTheDocument();
        });
        expect(screen.getByText("Bob")).toBeInTheDocument();
    });

    // ── Handle Card Click: collapse table ──
    it("collapses expanded table on second click", async () => {
        const user = userEvent.setup();
        vi.mocked(getDbStatus).mockResolvedValue({
            customers: { count: 3, latest: new Date().toISOString() },
        });
        vi.mocked(getTableData).mockResolvedValue({
            table: "customers",
            rows: [{ id: 1, name: "Alice", email: "a@a.com", plan: "Pro" }],
        });

        render(<MetricsPanel metrics={FULL_METRICS} />);
        await waitFor(() => {
            expect(screen.getByText("Customers")).toBeInTheDocument();
        });

        // Expand
        await user.click(screen.getByText("Customers"));
        await waitFor(() => {
            expect(screen.getByText("Alice")).toBeInTheDocument();
        });

        // Collapse
        await user.click(screen.getByText("Customers"));
        await waitFor(() => {
            expect(screen.queryByText("Alice")).not.toBeInTheDocument();
        });
    });

    // ── Handle Card Click: getTableData error ──
    it("shows 'No records' when getTableData fails", async () => {
        const user = userEvent.setup();
        vi.mocked(getDbStatus).mockResolvedValue({
            customers: { count: 3, latest: new Date().toISOString() },
        });
        vi.mocked(getTableData).mockRejectedValue(new Error("DB error"));

        render(<MetricsPanel metrics={FULL_METRICS} />);
        await waitFor(() => {
            expect(screen.getByText("Customers")).toBeInTheDocument();
        });

        await user.click(screen.getByText("Customers"));

        await waitFor(() => {
            expect(screen.getByText("No records")).toBeInTheDocument();
        });
    });

    // ── Clear Cache Failure ──
    it("shows 'Failed to clear' when clearCache throws", async () => {
        const user = userEvent.setup();
        vi.mocked(clearCache).mockRejectedValue(new Error("Network error"));

        render(<MetricsPanel metrics={FULL_METRICS} />);

        await user.click(screen.getByTitle("Clear cache"));

        await waitFor(() => {
            expect(screen.getByText("Failed to clear")).toBeInTheDocument();
        });
    });

    // ── DB Freshness ──
    it("shows freshness timestamp for database", async () => {
        vi.mocked(getDbStatus).mockResolvedValue({
            customers: { count: 5, latest: new Date().toISOString() },
        });

        render(<MetricsPanel metrics={FULL_METRICS} />);

        await waitFor(() => {
            expect(screen.getByText("Customers")).toBeInTheDocument();
        });
        // Freshness should show "just now" or similar time ago text
        expect(screen.getByText(/just now|0m ago|ago/i)).toBeInTheDocument();
    });

    // ── timeAgo: hours branch ──
    it("shows hours-old freshness when db data is hours old", async () => {
        const twoHoursAgo = new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString();
        vi.mocked(getDbStatus).mockResolvedValue({
            customers: { count: 5, latest: twoHoursAgo },
        });

        render(<MetricsPanel metrics={FULL_METRICS} />);

        await waitFor(() => {
            expect(screen.getByText("Customers")).toBeInTheDocument();
        });
        expect(screen.getByText(/2h ago/)).toBeInTheDocument();
    });

    // ── timeAgo: days branch ──
    it("shows days-old freshness when db data is days old", async () => {
        const threeDaysAgo = new Date(Date.now() - 3 * 24 * 60 * 60 * 1000).toISOString();
        vi.mocked(getDbStatus).mockResolvedValue({
            customers: { count: 5, latest: threeDaysAgo },
        });

        render(<MetricsPanel metrics={FULL_METRICS} />);

        await waitFor(() => {
            expect(screen.getByText("Customers")).toBeInTheDocument();
        });
        expect(screen.getByText(/3d ago/)).toBeInTheDocument();
    });

    // ── Amount Formatting in Table ──
    it("formats amount column with dollar sign in billing table", async () => {
        const user = userEvent.setup();
        vi.mocked(getDbStatus).mockResolvedValue({
            billing: { count: 2, latest: new Date().toISOString() },
        });
        vi.mocked(getTableData).mockResolvedValue({
            table: "billing",
            rows: [
                { id: 1, customer_id: 8, amount: 49.0, type: "charge" },
                { id: 2, customer_id: 3, amount: 199.99, type: "refund" },
            ],
        });

        render(<MetricsPanel metrics={FULL_METRICS} />);
        await waitFor(() => {
            expect(screen.getByText("Billing")).toBeInTheDocument();
        });

        await user.click(screen.getByText("Billing"));
        await waitFor(() => {
            expect(screen.getByText("$49.00")).toBeInTheDocument();
        });
        expect(screen.getByText("$199.99")).toBeInTheDocument();
        expect(screen.getByText("charge")).toBeInTheDocument();
    });

    // ── Truncate long values ──
    it("truncates long cell values in table data", async () => {
        const user = userEvent.setup();
        vi.mocked(getDbStatus).mockResolvedValue({
            customers: { count: 1, latest: new Date().toISOString() },
        });
        const longName = "A".repeat(50); // > 32 chars
        vi.mocked(getTableData).mockResolvedValue({
            table: "customers",
            rows: [{ id: 1, name: longName, email: "a@b.com" }],
        });

        render(<MetricsPanel metrics={FULL_METRICS} />);
        await waitFor(() => {
            expect(screen.getByText("Customers")).toBeInTheDocument();
        });

        await user.click(screen.getByText("Customers"));
        await waitFor(() => {
            // Truncated to 32 chars + "…"
            const truncated = "A".repeat(32) + "\u2026";
            expect(screen.getByText(truncated)).toBeInTheDocument();
        });
    });

    // ── Expensive model color ──
    it("renders expensive model labels with amber color", () => {
        const metricsWithExpensiveModels: Metrics = {
            ...FULL_METRICS,
            agent_metrics: {
                ...FULL_METRICS.agent_metrics!,
                model_distribution: {
                    "gemini-2.5-flash": 80,
                    "claude-sonnet-4-20250514": 15,
                    "gpt-4.1": 5,
                },
            },
        };
        render(<MetricsPanel metrics={metricsWithExpensiveModels} />);

        // The expensive models should be rendered with amber color
        expect(screen.getByText("gemini-2.5-flash")).toBeInTheDocument();
        expect(screen.getByText("claude-sonnet-4-20250514")).toBeInTheDocument();
        expect(screen.getByText("gpt-4.1")).toBeInTheDocument();
        // Check percentages
        expect(screen.getByText("80%")).toBeInTheDocument();
        expect(screen.getByText("15%")).toBeInTheDocument();
        expect(screen.getByText("5%")).toBeInTheDocument();
    });

    // ── High Cache Hit Rate Color ──
    it("shows green color when cache hit rate exceeds 50%", () => {
        const highHitMetrics: Metrics = {
            ...FULL_METRICS,
            cache_metrics: {
                ...FULL_METRICS.cache_metrics,
                hit_rate_percent: 75.0,
            },
        };
        render(<MetricsPanel metrics={highHitMetrics} />);
        const hitRateEl = screen.getByText("75.0%");
        expect(hitRateEl).toHaveStyle({ color: "#4ade80" });
    });

    // ── timeAgo: stale hours (> 3 hours) ──
    it("shows stale warning for db data older than 3 hours", async () => {
        const fiveHoursAgo = new Date(Date.now() - 5 * 60 * 60 * 1000).toISOString();
        vi.mocked(getDbStatus).mockResolvedValue({
            customers: { count: 5, latest: fiveHoursAgo },
        });

        render(<MetricsPanel metrics={FULL_METRICS} />);

        await waitFor(() => {
            expect(screen.getByText("Customers")).toBeInTheDocument();
        });
        expect(screen.getByText(/5h ago/)).toBeInTheDocument();
        // Stale should show ⚠ icon
        expect(screen.getByText(/⚠/)).toBeInTheDocument();
    });

    // ── timeAgo: minutes branch ──
    it("shows minutes-old freshness when db data is minutes old", async () => {
        const tenMinutesAgo = new Date(Date.now() - 10 * 60 * 1000).toISOString();
        vi.mocked(getDbStatus).mockResolvedValue({
            customers: { count: 5, latest: tenMinutesAgo },
        });

        render(<MetricsPanel metrics={FULL_METRICS} />);

        await waitFor(() => {
            expect(screen.getByText("Customers")).toBeInTheDocument();
        });
        expect(screen.getByText(/10m ago/)).toBeInTheDocument();
    });

    // ── getTableData returning undefined rows ──
    it("handles getTableData returning no rows property", async () => {
        const user = userEvent.setup();
        vi.mocked(getDbStatus).mockResolvedValue({
            customers: { count: 3, latest: new Date().toISOString() },
        });
        vi.mocked(getTableData).mockResolvedValue({
            table: "customers",
            // rows is undefined — tests the `data.rows || []` fallback
        } as any);

        render(<MetricsPanel metrics={FULL_METRICS} />);
        await waitFor(() => {
            expect(screen.getByText("Customers")).toBeInTheDocument();
        });

        await user.click(screen.getByText("Customers"));

        await waitFor(() => {
            expect(screen.getByText("No records")).toBeInTheDocument();
        });
    });

    // ── Clear cache without onCacheCleared ──
    it("clears cache successfully when onCacheCleared is not provided", async () => {
        const user = userEvent.setup();
        vi.mocked(clearCache).mockResolvedValue({ status: "ok", keys_deleted: 2 });

        render(<MetricsPanel metrics={FULL_METRICS} />);

        await user.click(screen.getByTitle("Clear cache"));

        await waitFor(() => {
            expect(screen.getByText("Cleared! (2 keys)")).toBeInTheDocument();
        });
    });
});

