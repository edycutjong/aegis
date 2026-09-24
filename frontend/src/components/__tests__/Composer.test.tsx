import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import Composer, { MAX_CHARS } from "../Composer";
import { EDGE_CASES, SCENARIOS } from "@/lib/presets";

function Harness({ busy = false, initial = "", onSubmit = vi.fn(), onPreset = vi.fn() }) {
    const [msg, setMsg] = useState(initial);
    return (
        <Composer message={msg} onChange={setMsg} onSubmit={onSubmit} onPreset={onPreset} busy={busy}>
            <p>child slot</p>
        </Composer>
    );
}

describe("Composer", () => {
    it("lists scenarios by default and switches to edge cases", async () => {
        render(<Harness />);
        expect(screen.getByRole("tab", { name: /Scenarios/ })).toHaveAttribute("aria-selected", "true");
        expect(screen.getByRole("button", { name: new RegExp(SCENARIOS[0].label) })).toBeInTheDocument();
        await userEvent.click(screen.getByRole("tab", { name: /Edge cases/ }));
        expect(screen.getByRole("button", { name: /Prompt injection/ })).toBeInTheDocument();
        expect(screen.getByText("child slot")).toBeInTheDocument();
    });

    it("covers every required example type", () => {
        const all = [...SCENARIOS, ...EDGE_CASES].map((p) => p.id);
        for (const id of ["refund", "technical", "suspend", "reactivate", "ambiguous", "typo", "injection", "exfiltration"]) {
            expect(all).toContain(id);
        }
    });

    it("moves between tabs with arrow keys and ignores other keys", () => {
        render(<Harness />);
        const scenarios = screen.getByRole("tab", { name: /Scenarios/ });
        fireEvent.keyDown(scenarios, { key: "ArrowRight" });
        expect(screen.getByRole("tab", { name: /Edge cases/ })).toHaveAttribute("aria-selected", "true");
        expect(screen.getByRole("tab", { name: /Edge cases/ })).toHaveFocus();
        fireEvent.keyDown(screen.getByRole("tab", { name: /Edge cases/ }), { key: "ArrowLeft" });
        expect(scenarios).toHaveAttribute("aria-selected", "true");
        fireEvent.keyDown(scenarios, { key: "ArrowLeft" });
        expect(screen.getByRole("tab", { name: /Edge cases/ })).toHaveAttribute("aria-selected", "true");
        fireEvent.keyDown(screen.getByRole("tab", { name: /Edge cases/ }), { key: "a" });
        expect(screen.getByRole("tab", { name: /Edge cases/ })).toHaveAttribute("aria-selected", "true");
    });

    it("runs a preset in one click", async () => {
        const onPreset = vi.fn();
        render(<Harness onPreset={onPreset} />);
        await userEvent.click(screen.getByRole("button", { name: /Double charge/ }));
        expect(onPreset).toHaveBeenCalledWith(SCENARIOS[0]);
    });

    it("submits with the button and with Enter, but Shift+Enter adds a line", async () => {
        const onSubmit = vi.fn();
        render(<Harness onSubmit={onSubmit} />);
        const input = screen.getByLabelText("Support ticket");
        expect(screen.getByRole("button", { name: /Run agents/ })).toBeDisabled();
        await userEvent.type(input, "hello");
        expect(screen.getByText("5/1000")).toBeInTheDocument();
        await userEvent.click(screen.getByRole("button", { name: /Run agents/ }));
        fireEvent.keyDown(input, { key: "Enter" });
        fireEvent.keyDown(input, { key: "Enter", shiftKey: true });
        expect(onSubmit).toHaveBeenCalledTimes(2);
    });

    it("blocks tickets over the backend's length limit", () => {
        render(<Harness initial={"x".repeat(MAX_CHARS + 1)} />);
        expect(screen.getByLabelText("Support ticket")).toHaveAttribute("aria-invalid", "true");
        expect(screen.getByRole("button", { name: /Run agents/ })).toBeDisabled();
    });

    it("locks presets and input while a run is in flight", () => {
        render(<Harness busy initial="x" />);
        expect(screen.getByRole("button", { name: /Running/ })).toBeDisabled();
        expect(screen.getByRole("button", { name: /Double charge/ })).toBeDisabled();
        expect(screen.getByLabelText("Support ticket")).toBeDisabled();
    });
});
