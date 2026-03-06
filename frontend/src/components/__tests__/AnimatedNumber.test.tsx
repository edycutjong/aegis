import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import AnimatedNumber from "../AnimatedNumber";

describe("AnimatedNumber", () => {
    beforeEach(() => {
        vi.useFakeTimers();
        // Mock requestAnimationFrame to work predictably with fake timers
        let time = 0;
        vi.spyOn(window, "requestAnimationFrame").mockImplementation((cb: FrameRequestCallback) => {
            return setTimeout(() => {
                time += 16;
                cb(time);
            }, 16) as unknown as number;
        });
        vi.spyOn(window, "cancelAnimationFrame").mockImplementation((id: number) => {
            clearTimeout(id);
        });
    });

    afterEach(() => {
        vi.restoreAllMocks();
        vi.useRealTimers();
    });

    it("renders initial value", () => {
        render(<AnimatedNumber value={25} />);
        expect(screen.getByText("25")).toBeInTheDocument();
    });

    it("animates from start to end value", () => {
        const { rerender } = render(<AnimatedNumber value={0} duration={800} />);
        expect(screen.getByText("0")).toBeInTheDocument();

        // Change value to trigger animation
        rerender(<AnimatedNumber value={100} duration={800} />);

        act(() => {
            vi.advanceTimersByTime(400); // Advance halfway
        });

        const intermediateText = document.body.textContent;
        const num = parseInt(intermediateText || "0", 10);
        // It shouldn't be exactly 0 or 100 halfway through
        expect(num).toBeGreaterThan(0);
        expect(num).toBeLessThan(100);

        act(() => {
            vi.advanceTimersByTime(500); // Advance past duration
        });

        expect(screen.getByText("100")).toBeInTheDocument();
    });

    it("cancels animation frame on unmount", () => {
        const { rerender, unmount } = render(<AnimatedNumber value={0} duration={800} />);

        // Trigger animation
        rerender(<AnimatedNumber value={100} duration={800} />);
        act(() => {
            vi.advanceTimersByTime(16); // Start animation
        });

        // Unmount while animating should trigger cancelAnimationFrame
        const cancelSpy = vi.spyOn(window, "cancelAnimationFrame");
        unmount();

        expect(cancelSpy).toHaveBeenCalled();
    });

    it("uses custom format function", () => {
        render(<AnimatedNumber value={50.5} format={(val) => `~${val.toFixed(1)}~`} />);
        expect(screen.getByText("~50.5~")).toBeInTheDocument();
    });

    it("handles changing value while already animating", () => {
        const { rerender } = render(<AnimatedNumber value={0} duration={800} />);

        rerender(<AnimatedNumber value={100} duration={800} />);
        act(() => {
            vi.advanceTimersByTime(100); // Partially through animation
        });

        // Interrupt with a new value
        rerender(<AnimatedNumber value={50} duration={800} />);

        act(() => {
            vi.advanceTimersByTime(1000); // Finish animation
        });

        expect(screen.getByText("50")).toBeInTheDocument();
    });
});
