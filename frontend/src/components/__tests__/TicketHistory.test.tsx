import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import TicketHistory from "../TicketHistory";
import type { TicketHistoryEntry } from "@/hooks/useTicketHistory";

const NOW = Date.now();

const sampleEntries: TicketHistoryEntry[] = [
    {
        message: "Customer #8 David Martinez says he was charged $49 twice this month for his Pro plan.",
        timestamp: NOW - 30_000, // 30s ago
        status: "completed",
        responsePreview: "Refund processed successfully",
    },
    {
        message: "Customer #3 Maria Garcia reports 429 errors on her enterprise plan.",
        timestamp: NOW - 3_600_000, // 1h ago
        status: "error",
        responsePreview: "",
    },
];

describe("TicketHistory", () => {
    const onSelect = vi.fn();
    const onClear = vi.fn();

    beforeEach(() => {
        vi.clearAllMocks();
    });

    // ── Empty State ──
    it("returns null when entries is empty", () => {
        const { container } = render(
            <TicketHistory entries={[]} onSelect={onSelect} onClear={onClear} />
        );
        expect(container.innerHTML).toBe("");
    });

    // ── Header ──
    it("renders header with entry count badge", () => {
        render(
            <TicketHistory entries={sampleEntries} onSelect={onSelect} onClear={onClear} />
        );
        expect(screen.getByText("Recent Tickets")).toBeInTheDocument();
        expect(screen.getByText("2")).toBeInTheDocument(); // badge count
    });

    // ── Expand/Collapse ──
    it("expands and collapses entries on header click", async () => {
        const user = userEvent.setup();
        const { container } = render(
            <TicketHistory entries={sampleEntries} onSelect={onSelect} onClear={onClear} />
        );

        const body = container.querySelector(".ticket-history-body") as HTMLElement;
        expect(body.style.maxHeight).toBe("0px"); // collapsed initially

        // Click to expand
        await user.click(screen.getByText("Recent Tickets"));
        expect(body.style.maxHeight).not.toBe("0px"); // expanded

        // Click again to collapse
        await user.click(screen.getByText("Recent Tickets"));
        expect(body.style.maxHeight).toBe("0px");
    });

    // ── Entry Click ──
    it("calls onSelect with entry message when entry is clicked", async () => {
        const user = userEvent.setup();
        render(
            <TicketHistory entries={sampleEntries} onSelect={onSelect} onClear={onClear} />
        );

        // Expand first
        await user.click(screen.getByText("Recent Tickets"));

        // Click the first entry (truncated to 60 chars)
        const entryBtn = screen.getByText(/Customer #8 David Martinez/);
        await user.click(entryBtn);

        expect(onSelect).toHaveBeenCalledWith(sampleEntries[0].message);
    });

    // ── Clear Button ──
    it("calls onClear when clear button is clicked (without toggling expand)", async () => {
        const user = userEvent.setup();
        render(
            <TicketHistory entries={sampleEntries} onSelect={onSelect} onClear={onClear} />
        );

        const clearBtn = screen.getByTitle("Clear history");
        await user.click(clearBtn);

        expect(onClear).toHaveBeenCalledOnce();
    });

    // ── relativeTime coverage ──
    it("shows 'just now' for recent entries", () => {
        const recent: TicketHistoryEntry[] = [
            { message: "Recent", timestamp: NOW - 5_000, status: "completed", responsePreview: "" },
        ];
        render(<TicketHistory entries={recent} onSelect={onSelect} onClear={onClear} />);
        expect(screen.getByText("just now")).toBeInTheDocument();
    });

    it("shows minutes ago", () => {
        const minutesAgo: TicketHistoryEntry[] = [
            { message: "Minutes", timestamp: NOW - 180_000, status: "completed", responsePreview: "" }, // 3m
        ];
        render(<TicketHistory entries={minutesAgo} onSelect={onSelect} onClear={onClear} />);
        expect(screen.getByText("3m ago")).toBeInTheDocument();
    });

    it("shows hours ago", () => {
        const hoursAgo: TicketHistoryEntry[] = [
            { message: "Hours", timestamp: NOW - 7_200_000, status: "completed", responsePreview: "" }, // 2h
        ];
        render(<TicketHistory entries={hoursAgo} onSelect={onSelect} onClear={onClear} />);
        expect(screen.getByText("2h ago")).toBeInTheDocument();
    });

    it("shows days ago", () => {
        const daysAgo: TicketHistoryEntry[] = [
            { message: "Days", timestamp: NOW - 172_800_000, status: "completed", responsePreview: "" }, // 2d
        ];
        render(<TicketHistory entries={daysAgo} onSelect={onSelect} onClear={onClear} />);
        expect(screen.getByText("2d ago")).toBeInTheDocument();
    });

    // ── Response Preview ──
    it("shows response preview when present", async () => {
        const user = userEvent.setup();
        render(
            <TicketHistory entries={sampleEntries} onSelect={onSelect} onClear={onClear} />
        );
        await user.click(screen.getByText("Recent Tickets"));
        expect(screen.getByText("Refund processed successfully")).toBeInTheDocument();
    });

    // ── Status Dot Color ──
    it("renders green dot for completed and red dot for error", async () => {
        const user = userEvent.setup();
        const { container } = render(
            <TicketHistory entries={sampleEntries} onSelect={onSelect} onClear={onClear} />
        );
        await user.click(screen.getByText("Recent Tickets"));

        const dots = container.querySelectorAll(".ticket-history-status-dot");
        expect(dots.length).toBe(2);
        expect((dots[0] as HTMLElement).style.background).toBe("var(--aegis-success)");
        expect((dots[1] as HTMLElement).style.background).toBe("var(--aegis-danger)");
    });

    // ── Message Truncation ──
    it("truncates messages longer than 60 characters", async () => {
        const user = userEvent.setup();
        render(
            <TicketHistory entries={sampleEntries} onSelect={onSelect} onClear={onClear} />
        );
        await user.click(screen.getByText("Recent Tickets"));

        // The first entry message is > 60 chars, should be truncated with "…"
        // First 60 chars of the long message + "…"
        const firstMessage = sampleEntries[0].message;
        const truncatedText = firstMessage.slice(0, 60) + "\u2026";
        expect(screen.getByText(truncatedText)).toBeInTheDocument();
    });

    it("does not truncate short messages", async () => {
        const user = userEvent.setup();
        const short: TicketHistoryEntry[] = [
            { message: "Short message", timestamp: NOW, status: "completed", responsePreview: "" },
        ];
        render(<TicketHistory entries={short} onSelect={onSelect} onClear={onClear} />);
        await user.click(screen.getByText("Recent Tickets"));
        expect(screen.getByText("Short message")).toBeInTheDocument();
    });

    // ── Key Press Expand/Collapse ──
    it("expands and collapses on Enter/Space key press", async () => {
        const user = userEvent.setup();
        const { container } = render(
            <TicketHistory entries={sampleEntries} onSelect={onSelect} onClear={onClear} />
        );

        const body = container.querySelector(".ticket-history-body") as HTMLElement;
        const header = screen.getByText("Recent Tickets").closest(".ticket-history-header") as HTMLElement;

        header.focus();
        fireEvent.keyDown(header, { key: "Enter" });
        expect(body.style.maxHeight).not.toBe("0px"); // expanded

        fireEvent.keyDown(header, { key: " " });
        expect(body.style.maxHeight).toBe("0px"); // collapsed

        // Add unused key to test coverage (Escape)
        fireEvent.keyDown(header, { key: "Escape" });
        expect(body.style.maxHeight).toBe("0px"); // Remains collapsed
    });
});
