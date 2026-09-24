import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import MetricsPanel from "../MetricsPanel";
import type { Metrics } from "@/lib/api";

vi.mock("@/lib/api", async (importOriginal) => {
    const actual = await importOriginal<typeof import("@/lib/api")>();
    return {
        ...actual,
        clearCache: vi.fn(),
        getDbStatus: vi.fn(),
        getTableData: vi.fn(),
        getTracingStatus: vi.fn(),
    };
});

import { clearCache, getDbStatus, getTableData, getTracingStatus } from "@/lib/api";

const FULL: Metrics = {
    agent_metrics: {
        total_requests: 42,
        avg_cost_usd: 0.03,
        avg_duration_seconds: 8.5,
        total_cost_usd: 1.3104,
        total_tokens: 125000,
        model_distribution: {
            "openai/gpt-oss-20b": 5,
            "gpt-4.1": 3,
            "models/gemini-2.5-flash": 1,
            "claude-sonnet-4": 1,
            "mystery-model": 1,
            o3: 1,
        },
        hitl_approval_rate: 85,
        avg_hitl_wait_seconds: 12.5,
        cost_saved_by_cache: 0,
        recent_requests: [],
    },
    cache_metrics: { hits: 12, misses: 30, total_requests: 42, hit_rate_percent: 28.6, connected: true },
};

const EMPTY: Metrics = {
    agent_metrics: {
        total_requests: 0,
        avg_cost_usd: 0,
        avg_duration_seconds: 0,
        total_cost_usd: 0,
        total_tokens: 0,
        model_distribution: {},
        hitl_approval_rate: null,
        avg_hitl_wait_seconds: null,
        cost_saved_by_cache: 0,
        recent_requests: [],
    },
    cache_metrics: { hits: 0, misses: 0, total_requests: 0, hit_rate_percent: 0, connected: false },
};

describe("MetricsPanel", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        vi.mocked(getDbStatus).mockResolvedValue({});
        vi.mocked(getTracingStatus).mockResolvedValue({ enabled: false, project: "aegis", connected: false });
        vi.mocked(getTableData).mockResolvedValue({ table: "customers", rows: [] });
    });

    afterEach(() => vi.useRealTimers());

    it("shows a skeleton while connecting and an honest offline state when down", () => {
        const { rerender } = render(<MetricsPanel metrics={null} backend="connecting" />);
        expect(screen.getByLabelText("Loading metrics")).toBeInTheDocument();
        rerender(<MetricsPanel metrics={null} backend="down" />);
        expect(screen.getByText("Telemetry offline")).toBeInTheDocument();
        expect(screen.queryByText("Runs")).not.toBeInTheDocument();
    });

    it("renders live stats and the model routing split", async () => {
        render(<MetricsPanel metrics={FULL} backend="up" />);
        expect(screen.getByText("Runs")).toBeInTheDocument();
        expect(await screen.findByText("42")).toBeInTheDocument();
        expect(await screen.findByText("125.0K")).toBeInTheDocument();
        expect(await screen.findByText("$1.310")).toBeInTheDocument();
        expect(await screen.findByText("85%")).toBeInTheDocument();
        expect(await screen.findByText("12.5s")).toBeInTheDocument();
        expect(screen.getByText("gpt-oss-20b")).toBeInTheDocument();
        expect(screen.getByText("Groq")).toBeInTheDocument();
        expect(screen.getAllByText("OpenAI")).toHaveLength(2);
        expect(screen.getByText("Google")).toBeInTheDocument();
        expect(screen.getByText("Anthropic")).toBeInTheDocument();
        expect(screen.getByText("Other")).toBeInTheDocument();
        expect(screen.getByRole("img", { name: /gpt-oss-20b 42%/ })).toBeInTheDocument();
        expect(screen.getByText("Redis connected")).toBeInTheDocument();
    });

    it("uses dashes rather than fake numbers when nothing has run", () => {
        render(<MetricsPanel metrics={EMPTY} backend="up" />);
        expect(screen.getAllByText("—")).toHaveLength(3);
        expect(screen.getByText(/Run a ticket to see which model/)).toBeInTheDocument();
        expect(screen.getByText("Redis off")).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Clear semantic cache" })).toBeDisabled();
    });

    it("formats millions compactly", async () => {
        render(<MetricsPanel metrics={{ ...FULL, agent_metrics: { ...FULL.agent_metrics, total_tokens: 2_500_000 } }} backend="up" />);
        expect(await screen.findByText("2.5M")).toBeInTheDocument();
    });

    it("clears the cache and reports the result", async () => {
        vi.mocked(clearCache).mockResolvedValue({ status: "ok", keys_deleted: 3 });
        const onCacheCleared = vi.fn();
        render(<MetricsPanel metrics={FULL} backend="up" onCacheCleared={onCacheCleared} />);
        await userEvent.click(screen.getByRole("button", { name: "Clear semantic cache" }));
        expect(await screen.findByText("Cleared 3 keys")).toBeInTheDocument();
        expect(onCacheCleared).toHaveBeenCalled();
        await waitFor(() => expect(screen.queryByText("Cleared 3 keys")).not.toBeInTheDocument(), { timeout: 3000 });
    });

    it("reports a failed cache clear, even without a callback", async () => {
        vi.mocked(clearCache).mockRejectedValue(new Error("x"));
        render(<MetricsPanel metrics={FULL} backend="up" />);
        await userEvent.click(screen.getByRole("button", { name: "Clear semantic cache" }));
        expect(await screen.findByText("Couldn't clear")).toBeInTheDocument();
    });

    it("clears without a callback", async () => {
        vi.mocked(clearCache).mockResolvedValue({ status: "ok", keys_deleted: 0 });
        render(<MetricsPanel metrics={FULL} backend="up" />);
        await userEvent.click(screen.getByRole("button", { name: "Clear semantic cache" }));
        expect(await screen.findByText("Cleared 0 keys")).toBeInTheDocument();
    });

    it("previews live database tables and collapses them again", async () => {
        vi.mocked(getDbStatus).mockResolvedValue({
            customers: { count: 51 },
            billing: { count: 34 },
            support_tickets: { count: 30 },
        });
        vi.mocked(getTableData).mockResolvedValueOnce({
            table: "billing",
            rows: [{ id: 1, customer_id: 8, amount: 49, type: "charge", status: "paid", description: "A very long description that needs truncating here" }],
        });
        render(<MetricsPanel metrics={null} backend="down" />);
        const billing = await screen.findByRole("button", { name: /Billing/ });
        expect(screen.queryByRole("button", { name: /Policy docs/ })).not.toBeInTheDocument();
        await userEvent.click(billing);
        expect(billing).toHaveAttribute("aria-expanded", "true");
        expect(await screen.findByText("$49.00")).toBeInTheDocument();
        expect(screen.getByText(/A very long description that/)).toHaveTextContent("…");
        await userEvent.click(billing);
        expect(screen.queryByRole("table")).not.toBeInTheDocument();
    });

    it("shows loading, empty and failed table previews", async () => {
        vi.mocked(getDbStatus).mockResolvedValue({ customers: { count: 1 }, internal_docs: { count: 2 } });
        let resolve!: (v: { table: string; rows: Record<string, unknown>[] }) => void;
        vi.mocked(getTableData).mockReturnValueOnce(new Promise((r) => (resolve = r)));
        render(<MetricsPanel metrics={null} backend="down" />);
        await userEvent.click(await screen.findByRole("button", { name: /Customers/ }));
        expect(screen.getByText("Loading…")).toBeInTheDocument();
        await act(async () => resolve({ table: "customers", rows: undefined as unknown as [] }));
        expect(screen.getByText("No records")).toBeInTheDocument();

        vi.mocked(getTableData).mockRejectedValueOnce(new Error("x"));
        await userEvent.click(screen.getByRole("button", { name: /Policy docs/ }));
        expect(await screen.findByText("No records")).toBeInTheDocument();
    });

    it("renders null cells as dashes", async () => {
        vi.mocked(getDbStatus).mockResolvedValue({ internal_docs: { count: 1 } });
        vi.mocked(getTableData).mockResolvedValueOnce({ table: "internal_docs", rows: [{ id: 1, title: null }] });
        render(<MetricsPanel metrics={null} backend="down" />);
        await userEvent.click(await screen.findByRole("button", { name: /Policy docs/ }));
        expect(await screen.findAllByText("—")).not.toHaveLength(0);
    });

    it("links to LangSmith traces when tracing is on", async () => {
        vi.mocked(getTracingStatus).mockResolvedValue({ enabled: true, project: "aegis", connected: true });
        const onOpenTraces = vi.fn();
        render(<MetricsPanel metrics={FULL} backend="up" onOpenTraces={onOpenTraces} />);
        await userEvent.click(await screen.findByRole("button", { name: /LangSmith traces/ }));
        expect(onOpenTraces).toHaveBeenCalled();
    });

    it("hides traces when the tracing probe fails, and survives a db probe failure", async () => {
        vi.mocked(getTracingStatus).mockRejectedValue(new Error("x"));
        vi.mocked(getDbStatus).mockRejectedValue(new Error("x"));
        render(<MetricsPanel metrics={FULL} backend="up" />);
        await waitFor(() => expect(getTracingStatus).toHaveBeenCalled());
        expect(screen.queryByRole("button", { name: /LangSmith traces/ })).not.toBeInTheDocument();
        expect(screen.queryByText("Live database")).not.toBeInTheDocument();
    });
});
