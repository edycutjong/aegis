import { describe, it, expect, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ThoughtStream from "../ThoughtStream";

describe("ThoughtStream", () => {
    // ── Empty State ──
    it("shows placeholder when no thoughts and not processing", () => {
        render(<ThoughtStream thoughts={[]} status="idle" />);
        expect(screen.getByText(/submit a support ticket/i)).toBeInTheDocument();
        expect(screen.queryByTestId("typing-indicator")).not.toBeInTheDocument();
    });

    it("shows 'Agent is thinking...' when processing but no thoughts", () => {
        render(<ThoughtStream thoughts={[]} status="processing" />);
        expect(screen.getByText(/agent is thinking/i)).toBeInTheDocument();
        expect(screen.getByTestId("typing-indicator")).toBeInTheDocument();
        expect(screen.queryByText(/submit a support ticket/i)).not.toBeInTheDocument();
    });

    it("shows error state when status is error but no thoughts", () => {
        render(<ThoughtStream thoughts={[]} status="error" />);
        expect(screen.getByText(/an error occurred/i)).toBeInTheDocument();
    });

    it("shows completed state when status is completed but no thoughts", () => {
        render(<ThoughtStream thoughts={[]} status="completed" />);
        expect(screen.getByText(/agent completed the task without generating any output/i)).toBeInTheDocument();
    });

    it("shows cached state when status is cached but no thoughts", () => {
        render(<ThoughtStream thoughts={[]} status="cached" />);
        expect(screen.getByText(/loaded from cache/i)).toBeInTheDocument();
    });

    // ── Rendering Thoughts ──
    it("renders thought steps with count in footer", () => {
        const thoughts = [
            "✓ [Triage] Classified intent: refund",
            "→ [Investigator] Customer validated: #8 David Martinez (Pro, active)",
        ];
        render(<ThoughtStream thoughts={thoughts} status="completed" />);
        expect(screen.getByText("2 steps")).toBeInTheDocument();
    });

    // ── Dev/User Mode Toggle ──
    it("toggles between User and Dev mode", async () => {
        const user = userEvent.setup();
        render(
            <ThoughtStream
                thoughts={["→ [Triage] Classified intent: refund"]}
                status="completed"
            />
        );

        // Default is User mode
        expect(screen.getByText("Progress")).toBeInTheDocument();
        const toggleBtn = screen.getByTitle(/switch to developer view/i);

        // Switch to Dev mode
        await user.click(toggleBtn);
        expect(screen.getByText("Agent Internals")).toBeInTheDocument();
    });

    // ── Icon Mapping ──
    it.each([
        ["✓ Step done", "✓"],
        ["✗ Step failed", "✗"],
        ["⏸ Paused step", "⏸"],
        ["⚠ Warning step", "⚠"],
        ["→ Normal step", "→"],
        ["Some default step", "→"],
    ])("maps '%s' to icon '%s'", (thought, expectedIcon) => {
        render(<ThoughtStream thoughts={[thought]} status="idle" />);
        expect(screen.getByText(expectedIcon)).toBeInTheDocument();
    });

    // ── Color Mapping ──
    it("applies correct CSS class for step icons", () => {
        render(
            <ThoughtStream
                thoughts={[
                    "✓ success",
                    "✗ failure",
                    "⏸ paused",
                    "⚠ warning",
                    "→ default",
                ]}
                status="idle"
            />
        );
        const icons = screen.getAllByText(/^[✓✗⏸⚠→]$/);
        expect(icons[0]).toHaveClass("text-emerald-400"); // ✓
        expect(icons[1]).toHaveClass("text-red-400"); // ✗
        expect(icons[2]).toHaveClass("text-amber-400"); // ⏸
        expect(icons[3]).toHaveClass("text-orange-400"); // ⚠
        expect(icons[4]).toHaveClass("text-blue-400"); // →
    });

    // ── simplifyForUser Patterns ──
    describe("simplifyForUser", () => {
        it("simplifies classified intent", () => {
            render(
                <ThoughtStream
                    thoughts={["→ [Triage] Classified intent: refund with high confidence"]}
                    status="idle"
                />
            );
            // In user mode (default), should show simplified message
            expect(screen.getByText("Analyzing your request...")).toBeInTheDocument();
        });

        it("simplifies customer validated", () => {
            render(
                <ThoughtStream
                    thoughts={["✓ [Investigator] Customer validated: #8 David Martinez (Pro, active)"]}
                    status="idle"
                />
            );
            expect(screen.getByText("Found customer: David Martinez")).toBeInTheDocument();
        });

        it("simplifies name typo auto-correct", () => {
            render(
                <ThoughtStream
                    thoughts={['✓ [Investigator] Name typo detected — auto-corrected to "David Martinez"']}
                    status="idle"
                />
            );
            expect(screen.getByText("Customer identified: David Martinez")).toBeInTheDocument();
        });

        it("simplifies SQL results", () => {
            render(
                <ThoughtStream
                    thoughts={["✓ [Investigator] SQL executed successfully — found 3 records"]}
                    status="idle"
                />
            );
            expect(screen.getByText("Found 3 matching records")).toBeInTheDocument();
        });

        it("simplifies proposed action", () => {
            render(
                <ThoughtStream
                    thoughts={["→ [Resolution] Proposed action: refund — Process $49 refund for duplicate charge"]}
                    status="idle"
                />
            );
            expect(
                screen.getByText("Recommendation: Process $49 refund for duplicate charge")
            ).toBeInTheDocument();
        });

        it("simplifies not found in database", () => {
            render(
                <ThoughtStream
                    thoughts={["✗ [Investigator] not found in database — stopping"]}
                    status="idle"
                />
            );
            expect(
                screen.getByText("Customer not found in our records")
            ).toBeInTheDocument();
        });

        it("passes through unknown messages unchanged", () => {
            render(
                <ThoughtStream
                    thoughts={["→ Some completely unknown message"]}
                    status="idle"
                />
            );
            expect(screen.getByText("Some completely unknown message")).toBeInTheDocument();
        });
    });

    // ── Agent Badge (Dev Mode) ──
    it("shows agent badge in dev mode but not in user mode", async () => {
        const user = userEvent.setup();
        render(
            <ThoughtStream
                thoughts={["✓ [Triage] Classified intent: refund"]}
                status="idle"
            />
        );

        // User mode (default) — no agent badge
        expect(screen.queryByText("Triage", { selector: "span" })).not.toBeInTheDocument();

        // Switch to dev mode
        await user.click(screen.getByTitle(/switch to developer view/i));

        // Dev mode — badge visible
        expect(screen.getByText("Triage")).toBeInTheDocument();
        expect(screen.getByText("🏷")).toBeInTheDocument();
    });

    // ── Status Badges ──
    it.each([
        ["processing", "Processing"],
        ["awaiting_approval", "⏸ Awaiting Approval"],
        ["completed", "✓ Completed"],
        ["cached", "⚡ Cached"],
    ])("shows status badge for '%s'", (status, badgeText) => {
        render(<ThoughtStream thoughts={["→ step"]} status={status} />);
        expect(screen.getByText(badgeText)).toBeInTheDocument();
    });

    // ── Typing Indicator ──
    it("shows typing indicator when processing", () => {
        render(<ThoughtStream thoughts={["→ step"]} status="processing" />);
        expect(screen.getByTestId("typing-indicator")).toBeInTheDocument();
    });

    it("hides typing indicator when not processing", () => {
        render(<ThoughtStream thoughts={["→ step"]} status="completed" />);
        expect(screen.queryByTestId("typing-indicator")).not.toBeInTheDocument();
    });
});
