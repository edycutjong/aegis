import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ApprovalGate, { DEFAULT_DENY_REASON, ESCAPE_DENY_REASON } from "../ApprovalGate";
import type { ActionProposal } from "@/lib/api";

const REFUND: ActionProposal = {
    type: "refund",
    amount: 49,
    customer_id: 8,
    customer_name: "David Martinez",
    description: "Refund the duplicate $49 charge",
    reason: "Two identical charges on the same day",
};

function setup(action: Partial<ActionProposal> = {}, isLoading = false) {
    const onApprove = vi.fn();
    const onDeny = vi.fn();
    render(<ApprovalGate action={{ ...REFUND, ...action }} onApprove={onApprove} onDeny={onDeny} isLoading={isLoading} />);
    return { onApprove, onDeny };
}

describe("ApprovalGate", () => {
    it("presents the held action with amount, customer and reasoning", () => {
        setup();
        expect(screen.getByRole("region", { name: /Refund/ })).toBeInTheDocument();
        expect(screen.getByText("$49.00")).toBeInTheDocument();
        expect(screen.getByText("David Martinez")).toBeInTheDocument();
        expect(screen.getByText("· #8")).toBeInTheDocument();
        expect(screen.getByText(/Two identical charges/)).toBeInTheDocument();
        expect(screen.getByText(/nothing has executed/i)).toBeInTheDocument();
        expect(screen.getByTestId("action-icon-refund")).toBeInTheDocument();
    });

    it("explains a force-escalation from the input screen", () => {
        setup({ type: "escalate", amount: null, description: "Escalated for human review — ticket flagged by input screening (jailbreak)." });
        expect(screen.getByText(/Flagged by the prompt-injection screen/)).toBeInTheDocument();
    });

    it("focuses Deny — the safe choice — on arrival", () => {
        setup();
        expect(screen.getByRole("button", { name: "Deny" })).toHaveFocus();
    });

    it.each(["credit", "tier_change", "suspend", "reactivate", "escalate"])("has a title and icon for %s", (type) => {
        setup({ type, amount: null });
        expect(screen.getByTestId(`action-icon-${type}`)).toBeInTheDocument();
        expect(screen.queryByText("$49.00")).not.toBeInTheDocument();
    });

    it("falls back gracefully for unknown actions and unverified customers", () => {
        setup({ type: "custom_thing", customer_name: "Not Found", customer_id: null, amount: 0 });
        expect(screen.getByRole("heading", { name: "custom thing" })).toBeInTheDocument();
        expect(screen.getByText("Unverified customer")).toBeInTheDocument();
        expect(screen.getByTestId("action-icon-custom_thing")).toBeInTheDocument();
    });

    it("approves with the audit note", async () => {
        const { onApprove } = setup();
        await userEvent.type(screen.getByLabelText(/Note for the audit log/), "  checked invoice  ");
        await userEvent.click(screen.getByRole("button", { name: "Approve & execute" }));
        expect(onApprove).toHaveBeenCalledWith("checked invoice");
    });

    it("denies with the note, or a default reason", async () => {
        const { onDeny } = setup();
        await userEvent.click(screen.getByRole("button", { name: "Deny" }));
        expect(onDeny).toHaveBeenCalledWith(DEFAULT_DENY_REASON);
        await userEvent.type(screen.getByLabelText(/Note for the audit log/), "no evidence");
        await userEvent.click(screen.getByRole("button", { name: "Deny" }));
        expect(onDeny).toHaveBeenLastCalledWith("no evidence");
    });

    it("treats Escape as a deny, but not while a decision is in flight", () => {
        const { onDeny } = setup();
        fireEvent.keyDown(screen.getByRole("region"), { key: "Enter" });
        expect(onDeny).not.toHaveBeenCalled();
        fireEvent.keyDown(screen.getByRole("region"), { key: "Escape" });
        expect(onDeny).toHaveBeenCalledWith(ESCAPE_DENY_REASON);
    });

    it("shows progress on the decision actually taken", () => {
        const onDeny = vi.fn();
        const { rerender } = render(<ApprovalGate action={REFUND} onApprove={vi.fn()} onDeny={onDeny} isLoading pending="deny" />);
        expect(screen.getByRole("button", { name: /Denying/ })).toBeDisabled();
        expect(screen.getByRole("button", { name: "Approve & execute" })).toBeDisabled();
        expect(screen.queryByText(/Releasing/)).not.toBeInTheDocument();
        rerender(<ApprovalGate action={REFUND} onApprove={vi.fn()} onDeny={onDeny} isLoading pending="approve" />);
        expect(screen.getByRole("button", { name: /Releasing/ })).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Deny" })).toBeDisabled();
    });

    it("locks the controls while a decision is in flight", () => {
        const { onDeny } = setup({}, true);
        expect(screen.getByRole("button", { name: "Approve & execute" })).toBeDisabled();
        expect(screen.getByRole("button", { name: "Deny" })).toBeDisabled();
        fireEvent.keyDown(screen.getByRole("region"), { key: "Escape" });
        expect(onDeny).not.toHaveBeenCalled();
    });
});
