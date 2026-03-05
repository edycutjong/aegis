import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import TracesPanel from "../TracesPanel";
import type { TracesResponse } from "@/lib/api";

// Mock the API module
vi.mock("@/lib/api", () => ({
    getTraces: vi.fn(),
}));

import { getTraces } from "@/lib/api";
const mockGetTraces = vi.mocked(getTraces);

const MOCK_TRACES: TracesResponse = {
    traces: [
        {
            id: "trace-1",
            name: "aegis-support-workflow",
            status: "success",
            latency_ms: 3200,
            total_tokens: 4218,
            total_cost: 0.0091,
            start_time: new Date().toISOString(),
            child_runs: [
                {
                    id: "child-1",
                    name: "classify_intent",
                    status: "success",
                    latency_ms: 180,
                    total_tokens: 312,
                    model: "groq/llama-3.3-70b",
                    total_cost: 0.0003,
                },
                {
                    id: "child-2",
                    name: "execute_sql",
                    status: "success",
                    latency_ms: 45,
                    total_tokens: 0,
                    model: "supabase/postgres",
                    total_cost: 0.0,
                },
            ],
        },
    ],
    error: null,
};

const noop = () => { };

describe("TracesPanel", () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it("shows loading state when open", () => {
        mockGetTraces.mockReturnValue(new Promise(() => { })); // never resolves
        render(<TracesPanel open onClose={noop} />);
        expect(screen.getByText("Loading traces…")).toBeInTheDocument();
    });

    it("renders trace data after loading", async () => {
        mockGetTraces.mockResolvedValue(MOCK_TRACES);
        render(<TracesPanel open onClose={noop} />);

        await waitFor(() => {
            expect(screen.getByText("aegis-support-workflow")).toBeInTheDocument();
        });

        expect(screen.getByText("$0.0091")).toBeInTheDocument();
    });

    it("expands a trace to show child runs", async () => {
        mockGetTraces.mockResolvedValue(MOCK_TRACES);
        render(<TracesPanel open onClose={noop} />);

        await waitFor(() => {
            expect(screen.getByText("aegis-support-workflow")).toBeInTheDocument();
        });

        fireEvent.click(screen.getByText("aegis-support-workflow"));

        await waitFor(() => {
            expect(screen.getByText("classify_intent")).toBeInTheDocument();
            expect(screen.getByText("execute_sql")).toBeInTheDocument();
        });

        expect(screen.getByText("groq/llama-3.3-70b")).toBeInTheDocument();
    });

    it("shows empty state when no traces", async () => {
        mockGetTraces.mockResolvedValue({ traces: [], error: null });
        render(<TracesPanel open onClose={noop} />);

        await waitFor(() => {
            expect(screen.getByText("No traces yet — submit a ticket to generate one")).toBeInTheDocument();
        });
    });

    it("shows error state", async () => {
        mockGetTraces.mockResolvedValue({ traces: [], error: "API unreachable" });
        render(<TracesPanel open onClose={noop} />);

        await waitFor(() => {
            expect(screen.getByText(/API unreachable/)).toBeInTheDocument();
        });
    });

    it("shows error when fetch throws", async () => {
        mockGetTraces.mockRejectedValue(new Error("Network error"));
        render(<TracesPanel open onClose={noop} />);

        await waitFor(() => {
            expect(screen.getByText(/Failed to connect/)).toBeInTheDocument();
        });
    });

    it("does not fetch when closed", () => {
        mockGetTraces.mockResolvedValue(MOCK_TRACES);
        render(<TracesPanel open={false} onClose={noop} />);
        expect(mockGetTraces).not.toHaveBeenCalled();
    });

    it("calls onClose when backdrop is clicked", async () => {
        const onClose = vi.fn();
        mockGetTraces.mockResolvedValue(MOCK_TRACES);
        render(<TracesPanel open onClose={onClose} />);

        // Click the backdrop
        const backdrop = document.querySelector(".traces-backdrop");
        if (backdrop) fireEvent.click(backdrop);

        expect(onClose).toHaveBeenCalled();
    });

    it("calls onClose on Escape key", async () => {
        const onClose = vi.fn();
        mockGetTraces.mockResolvedValue(MOCK_TRACES);
        render(<TracesPanel open onClose={onClose} />);

        fireEvent.keyDown(window, { key: "Escape" });

        expect(onClose).toHaveBeenCalled();
    });
});
