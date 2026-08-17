import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import DatabaseStatus from "../DatabaseStatus";
import type { DbStatus } from "@/lib/api";

// Mock the API module
vi.mock("@/lib/api", async (importOriginal) => {
    const actual = await importOriginal<typeof import("@/lib/api")>();
    return {
        ...actual,
        getDbStatus: vi.fn(),
        getTableData: vi.fn(),
    };
});

import { getDbStatus, getTableData } from "@/lib/api";

const FULL_DB: DbStatus = {
    customers: { count: 20, latest: new Date().toISOString() },
    billing: { count: 15, latest: new Date().toISOString() },
    support_tickets: { count: 8, latest: new Date().toISOString() },
    internal_docs: { count: 5, latest: null },
};

describe("DatabaseStatus", () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    // ── Loading state ──
    it("shows a loading spinner while fetching db status", async () => {
        let resolveFn: (value: DbStatus) => void = () => {};
        vi.mocked(getDbStatus).mockReturnValue(
            new Promise((resolve) => {
                resolveFn = resolve;
            })
        );

        render(<DatabaseStatus />);
        expect(screen.getByText("Database")).toBeInTheDocument();

        resolveFn(FULL_DB);
        await waitFor(() => {
            expect(screen.getByText("Customers")).toBeInTheDocument();
        });
    });

    // ── Error state ──
    it("shows an error indicator when getDbStatus rejects", async () => {
        vi.mocked(getDbStatus).mockRejectedValue(new Error("Network down"));

        render(<DatabaseStatus />);

        await waitFor(() => {
            expect(screen.getByText("Error")).toBeInTheDocument();
        });
    });

    // ── Success: renders all table cards ──
    it("renders all four table cards with counts", async () => {
        vi.mocked(getDbStatus).mockResolvedValue(FULL_DB);

        render(<DatabaseStatus />);

        await waitFor(() => {
            expect(screen.getByText("Customers")).toBeInTheDocument();
        });
        expect(screen.getByText("Billing")).toBeInTheDocument();
        expect(screen.getByText("Tickets")).toBeInTheDocument();
        expect(screen.getByText("Docs")).toBeInTheDocument();
        expect(screen.getByText("20")).toBeInTheDocument();
        expect(screen.getByText("15")).toBeInTheDocument();
    });

    // ── Missing table entry is skipped ──
    it("skips rendering a card when a known table is absent from the response", async () => {
        vi.mocked(getDbStatus).mockResolvedValue({
            customers: { count: 20, latest: new Date().toISOString() },
        });

        render(<DatabaseStatus />);

        await waitFor(() => {
            expect(screen.getByText("Customers")).toBeInTheDocument();
        });
        expect(screen.queryByText("Billing")).not.toBeInTheDocument();
    });

    // ── Empty database — seed.sql hint ──
    it("shows the seed.sql hint when every table count is zero", async () => {
        vi.mocked(getDbStatus).mockResolvedValue({
            customers: { count: 0, latest: null },
            billing: { count: 0, latest: null },
            support_tickets: { count: 0, latest: null },
            internal_docs: { count: 0, latest: null },
        });

        render(<DatabaseStatus />);

        await waitFor(() => {
            expect(screen.getByText(/run/i)).toBeInTheDocument();
        });
        expect(screen.getByText("seed.sql")).toBeInTheDocument();
    });

    it("does not show the seed.sql hint when at least one table has data", async () => {
        vi.mocked(getDbStatus).mockResolvedValue(FULL_DB);

        render(<DatabaseStatus />);

        await waitFor(() => {
            expect(screen.getByText("Customers")).toBeInTheDocument();
        });
        expect(screen.queryByText("seed.sql")).not.toBeInTheDocument();
    });

    // ── Freshness: just now / minutes / hours / stale hours / days ──
    it("shows 'just now' freshness for a very recent timestamp", async () => {
        vi.mocked(getDbStatus).mockResolvedValue({
            customers: { count: 1, latest: new Date().toISOString() },
        });

        render(<DatabaseStatus />);

        await waitFor(() => {
            expect(screen.getByText(/just now/)).toBeInTheDocument();
        });
    });

    it("shows minutes-ago freshness", async () => {
        const tenMinAgo = new Date(Date.now() - 10 * 60 * 1000).toISOString();
        vi.mocked(getDbStatus).mockResolvedValue({
            customers: { count: 1, latest: tenMinAgo },
        });

        render(<DatabaseStatus />);

        await waitFor(() => {
            expect(screen.getByText(/10m ago/)).toBeInTheDocument();
        });
    });

    it("shows non-stale hours-ago freshness (<= 3h) with a check icon", async () => {
        const twoHoursAgo = new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString();
        vi.mocked(getDbStatus).mockResolvedValue({
            customers: { count: 1, latest: twoHoursAgo },
        });

        render(<DatabaseStatus />);

        await waitFor(() => {
            expect(screen.getByText(/2h ago/)).toBeInTheDocument();
        });
        expect(screen.getByText(/✓/)).toBeInTheDocument();
    });

    it("shows stale hours-ago freshness (> 3h) with a warning icon", async () => {
        const fiveHoursAgo = new Date(Date.now() - 5 * 60 * 60 * 1000).toISOString();
        vi.mocked(getDbStatus).mockResolvedValue({
            customers: { count: 1, latest: fiveHoursAgo },
        });

        render(<DatabaseStatus />);

        await waitFor(() => {
            expect(screen.getByText(/5h ago/)).toBeInTheDocument();
        });
        expect(screen.getByText(/⚠/)).toBeInTheDocument();
    });

    it("shows days-ago freshness", async () => {
        const threeDaysAgo = new Date(Date.now() - 3 * 24 * 60 * 60 * 1000).toISOString();
        vi.mocked(getDbStatus).mockResolvedValue({
            customers: { count: 1, latest: threeDaysAgo },
        });

        render(<DatabaseStatus />);

        await waitFor(() => {
            expect(screen.getByText(/3d ago/)).toBeInTheDocument();
        });
    });

    it("shows no freshness indicator when no table has a latest timestamp", async () => {
        vi.mocked(getDbStatus).mockResolvedValue({
            internal_docs: { count: 5, latest: null },
        });

        render(<DatabaseStatus />);

        await waitFor(() => {
            expect(screen.getByText("Docs")).toBeInTheDocument();
        });
        expect(screen.queryByText(/ago/)).not.toBeInTheDocument();
    });

    // ── Expand / collapse a table card ──
    it("expands a card on click and loads its rows", async () => {
        const user = userEvent.setup();
        vi.mocked(getDbStatus).mockResolvedValue(FULL_DB);
        vi.mocked(getTableData).mockResolvedValue({
            table: "customers",
            rows: [
                { id: 1, name: "Alice", email: "alice@a.com", plan: "pro", status: "active", company: "Acme" },
            ],
        });

        render(<DatabaseStatus />);
        await waitFor(() => {
            expect(screen.getByText("Customers")).toBeInTheDocument();
        });

        await user.click(screen.getByText("Customers"));

        await waitFor(() => {
            expect(getTableData).toHaveBeenCalledWith("customers");
        });
        await waitFor(() => {
            expect(screen.getByText("Alice")).toBeInTheDocument();
        });
    });

    it("collapses an expanded card on second click", async () => {
        const user = userEvent.setup();
        vi.mocked(getDbStatus).mockResolvedValue(FULL_DB);
        vi.mocked(getTableData).mockResolvedValue({
            table: "customers",
            rows: [{ id: 1, name: "Alice", email: "a@a.com", plan: "pro", status: "active", company: "Acme" }],
        });

        render(<DatabaseStatus />);
        await waitFor(() => {
            expect(screen.getByText("Customers")).toBeInTheDocument();
        });

        await user.click(screen.getByText("Customers"));
        await waitFor(() => {
            expect(screen.getByText("Alice")).toBeInTheDocument();
        });

        await user.click(screen.getByText("Customers"));
        await waitFor(() => {
            expect(screen.queryByText("Alice")).not.toBeInTheDocument();
        });
    });

    it("switches expanded table when a different card is clicked", async () => {
        const user = userEvent.setup();
        vi.mocked(getDbStatus).mockResolvedValue(FULL_DB);
        vi.mocked(getTableData).mockImplementation(async (table: string) => {
            if (table === "customers") {
                return { table, rows: [{ id: 1, name: "Alice", email: "a@a.com", plan: "pro", status: "active", company: "Acme" }] };
            }
            return { table, rows: [{ id: 9, customer_id: 1, amount: 10, type: "charge", status: "paid", description: "Sub" }] };
        });

        render(<DatabaseStatus />);
        await waitFor(() => {
            expect(screen.getByText("Customers")).toBeInTheDocument();
        });

        await user.click(screen.getByText("Customers"));
        await waitFor(() => {
            expect(screen.getByText("Alice")).toBeInTheDocument();
        });

        await user.click(screen.getByText("Billing"));
        await waitFor(() => {
            expect(getTableData).toHaveBeenCalledWith("billing");
        });
        await waitFor(() => {
            expect(screen.queryByText("Alice")).not.toBeInTheDocument();
        });
    });

    it("shows 'No records' when the expanded table has zero rows", async () => {
        const user = userEvent.setup();
        vi.mocked(getDbStatus).mockResolvedValue(FULL_DB);
        vi.mocked(getTableData).mockResolvedValue({ table: "customers", rows: [] });

        render(<DatabaseStatus />);
        await waitFor(() => {
            expect(screen.getByText("Customers")).toBeInTheDocument();
        });

        await user.click(screen.getByText("Customers"));
        await waitFor(() => {
            expect(screen.getByText("No records")).toBeInTheDocument();
        });
    });

    it("shows 'No records' when getTableData resolves with no rows property", async () => {
        const user = userEvent.setup();
        vi.mocked(getDbStatus).mockResolvedValue(FULL_DB);
        vi.mocked(getTableData).mockResolvedValue({ table: "customers" } as any);

        render(<DatabaseStatus />);
        await waitFor(() => {
            expect(screen.getByText("Customers")).toBeInTheDocument();
        });

        await user.click(screen.getByText("Customers"));
        await waitFor(() => {
            expect(screen.getByText("No records")).toBeInTheDocument();
        });
    });

    it("shows 'No records' when getTableData rejects", async () => {
        const user = userEvent.setup();
        vi.mocked(getDbStatus).mockResolvedValue(FULL_DB);
        vi.mocked(getTableData).mockRejectedValue(new Error("boom"));

        render(<DatabaseStatus />);
        await waitFor(() => {
            expect(screen.getByText("Customers")).toBeInTheDocument();
        });

        await user.click(screen.getByText("Customers"));
        await waitFor(() => {
            expect(screen.getByText("No records")).toBeInTheDocument();
        });
    });

    it("formats the amount column as currency in the billing table", async () => {
        const user = userEvent.setup();
        vi.mocked(getDbStatus).mockResolvedValue(FULL_DB);
        vi.mocked(getTableData).mockResolvedValue({
            table: "billing",
            rows: [{ id: 1, customer_id: 8, amount: 49.5, type: "charge", status: "paid", description: "Sub" }],
        });

        render(<DatabaseStatus />);
        await waitFor(() => {
            expect(screen.getByText("Billing")).toBeInTheDocument();
        });

        await user.click(screen.getByText("Billing"));
        await waitFor(() => {
            expect(screen.getByText("$49.50")).toBeInTheDocument();
        });
    });

    it("renders an em-dash for null/undefined cell values", async () => {
        const user = userEvent.setup();
        vi.mocked(getDbStatus).mockResolvedValue(FULL_DB);
        vi.mocked(getTableData).mockResolvedValue({
            table: "customers",
            rows: [{ id: 1, name: "Alice" }], // email/plan/status/company missing
        });

        render(<DatabaseStatus />);
        await waitFor(() => {
            expect(screen.getByText("Customers")).toBeInTheDocument();
        });

        await user.click(screen.getByText("Customers"));
        await waitFor(() => {
            expect(screen.getAllByText("—").length).toBeGreaterThan(0);
        });
    });

    it("truncates long cell values beyond 40 characters", async () => {
        const user = userEvent.setup();
        vi.mocked(getDbStatus).mockResolvedValue(FULL_DB);
        const longName = "B".repeat(60);
        vi.mocked(getTableData).mockResolvedValue({
            table: "customers",
            rows: [{ id: 1, name: longName }],
        });

        render(<DatabaseStatus />);
        await waitFor(() => {
            expect(screen.getByText("Customers")).toBeInTheDocument();
        });

        await user.click(screen.getByText("Customers"));
        await waitFor(() => {
            const truncated = "B".repeat(40) + "…";
            expect(screen.getByText(truncated)).toBeInTheDocument();
        });
    });

    it("renders table column headers with underscores replaced by spaces", async () => {
        const user = userEvent.setup();
        vi.mocked(getDbStatus).mockResolvedValue(FULL_DB);
        vi.mocked(getTableData).mockResolvedValue({
            table: "billing",
            rows: [{ id: 1, customer_id: 8, amount: 10, type: "charge", status: "paid", description: "x" }],
        });

        render(<DatabaseStatus />);
        await waitFor(() => {
            expect(screen.getByText("Billing")).toBeInTheDocument();
        });

        await user.click(screen.getByText("Billing"));
        await waitFor(() => {
            expect(screen.getByText("customer id")).toBeInTheDocument();
        });
    });
});
