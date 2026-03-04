import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ApprovalModal from "../ApprovalModal";
import type { ActionProposal } from "@/lib/api";

const baseAction: ActionProposal = {
    type: "refund",
    amount: 49.0,
    customer_id: 8,
    customer_name: "David Martinez",
    description: "Refund $49 for duplicate charge",
    reason: "Duplicate billing confirmed",
};

describe("ApprovalModal", () => {
    it("renders header and action details", () => {
        render(
            <ApprovalModal action={baseAction} onApprove={vi.fn()} onDeny={vi.fn()} isLoading={false} />
        );
        expect(screen.getByText("Human Approval Required")).toBeInTheDocument();
        expect(screen.getByText("David Martinez")).toBeInTheDocument();
        expect(screen.getByText("#8")).toBeInTheDocument();
        expect(screen.getByText("Refund $49 for duplicate charge")).toBeInTheDocument();
        expect(screen.getByText("Duplicate billing confirmed")).toBeInTheDocument();
    });

    it("shows formatted amount for actions with amount", () => {
        render(
            <ApprovalModal action={baseAction} onApprove={vi.fn()} onDeny={vi.fn()} isLoading={false} />
        );
        expect(screen.getByText(/refund — \$49\.00/i)).toBeInTheDocument();
    });

    it("shows action type without amount when amount is null", () => {
        const noAmountAction = { ...baseAction, amount: null };
        render(
            <ApprovalModal action={noAmountAction} onApprove={vi.fn()} onDeny={vi.fn()} isLoading={false} />
        );
        expect(screen.getByText("refund")).toBeInTheDocument();
    });

    it("hides customer_name when empty", () => {
        const noName = { ...baseAction, customer_name: "" };
        render(
            <ApprovalModal action={noName} onApprove={vi.fn()} onDeny={vi.fn()} isLoading={false} />
        );
        expect(screen.queryByText("Customer")).not.toBeInTheDocument();
    });

    it("hides customer_id when null", () => {
        const noId = { ...baseAction, customer_id: null };
        render(
            <ApprovalModal action={noId} onApprove={vi.fn()} onDeny={vi.fn()} isLoading={false} />
        );
        expect(screen.queryByText(/^#\d+$/)).not.toBeInTheDocument();
    });

    // ── getActionIcon coverage ──
    it.each([
        ["refund", "💰"],
        ["credit", "🎁"],
        ["tier_change", "📊"],
        ["escalate", "🚨"],
        ["suspend", "🔒"],
        ["reactivate", "🔓"],
        ["unknown_type", "⚡"],
    ])("shows correct icon for action type '%s'", (type, icon) => {
        render(
            <ApprovalModal
                action={{ ...baseAction, type }}
                onApprove={vi.fn()}
                onDeny={vi.fn()}
                isLoading={false}
            />
        );
        expect(screen.getByText(icon)).toBeInTheDocument();
    });

    // ── getActionColor coverage ──
    it.each([
        ["refund", "border-amber-500/30"],
        ["credit", "border-emerald-500/30"],
        ["tier_change", "border-blue-500/30"],
        ["escalate", "border-red-500/30"],
        ["suspend", "border-orange-500/30"],
        ["reactivate", "border-teal-500/30"],
        ["unknown_type", "border-purple-500/30"],
    ])("applies correct border class for action type '%s'", (type, expectedClass) => {
        const { container } = render(
            <ApprovalModal
                action={{ ...baseAction, type }}
                onApprove={vi.fn()}
                onDeny={vi.fn()}
                isLoading={false}
            />
        );
        const actionCard = container.querySelector(`.${expectedClass.replace(/\//g, "\\/")}`);
        expect(actionCard).toBeTruthy();
    });

    // ── Approve/Deny with fake timers ──
    describe("with fake timers", () => {
        beforeEach(() => {
            vi.useFakeTimers();
        });

        afterEach(() => {
            vi.useRealTimers();
        });

        it("calls onApprove after animation delay when Approve is clicked", async () => {
            const onApprove = vi.fn();
            render(
                <ApprovalModal action={baseAction} onApprove={onApprove} onDeny={vi.fn()} isLoading={false} />
            );

            const approveBtn = screen.getByRole("button", { name: /approve/i });
            await act(async () => {
                approveBtn.click();
            });

            // Should be closing now, callback not yet called
            expect(onApprove).not.toHaveBeenCalled();

            act(() => {
                vi.advanceTimersByTime(300);
            });

            expect(onApprove).toHaveBeenCalledOnce();
        });

        it("calls onDeny with reason after animation delay when Deny is clicked", async () => {
            const onDeny = vi.fn();
            render(
                <ApprovalModal action={baseAction} onApprove={vi.fn()} onDeny={onDeny} isLoading={false} />
            );

            const denyBtn = screen.getByRole("button", { name: /deny/i });
            await act(async () => {
                denyBtn.click();
            });

            expect(onDeny).not.toHaveBeenCalled();

            act(() => {
                vi.advanceTimersByTime(300);
            });

            expect(onDeny).toHaveBeenCalledWith("Manager denied the proposed action");
        });

        it("disables buttons during closing animation", async () => {
            render(
                <ApprovalModal action={baseAction} onApprove={vi.fn()} onDeny={vi.fn()} isLoading={false} />
            );

            const approveBtn = screen.getByRole("button", { name: /approve/i });
            await act(async () => {
                approveBtn.click();
            });

            // During animation, closing = true, so buttons should be disabled
            expect(screen.getByRole("button", { name: /approve/i })).toBeDisabled();
            expect(screen.getByRole("button", { name: /deny/i })).toBeDisabled();

            act(() => {
                vi.advanceTimersByTime(300);
            });
        });

        it("applies modal-exit classes when closing", async () => {
            const { container } = render(
                <ApprovalModal action={baseAction} onApprove={vi.fn()} onDeny={vi.fn()} isLoading={false} />
            );

            const approveBtn = screen.getByRole("button", { name: /approve/i });
            await act(async () => {
                approveBtn.click();
            });

            const backdrop = container.querySelector(".modal-backdrop-exit");
            expect(backdrop).toBeTruthy();
            const panel = container.querySelector(".modal-exit");
            expect(panel).toBeTruthy();

            act(() => {
                vi.advanceTimersByTime(300);
            });
        });
    });

    it("disables buttons when isLoading is true", () => {
        render(
            <ApprovalModal action={baseAction} onApprove={vi.fn()} onDeny={vi.fn()} isLoading={true} />
        );
        expect(screen.getByRole("button", { name: /approve/i })).toBeDisabled();
        expect(screen.getByRole("button", { name: /deny/i })).toBeDisabled();
    });
});
