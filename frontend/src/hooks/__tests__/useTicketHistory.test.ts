import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useTicketHistory } from "../useTicketHistory";

describe("useTicketHistory", () => {
    beforeEach(() => {
        localStorage.clear();
        vi.clearAllMocks();
    });

    it("starts with empty entries", () => {
        const { result } = renderHook(() => useTicketHistory());
        expect(result.current.entries).toEqual([]);
    });

    it("adds an entry with timestamp", () => {
        const { result } = renderHook(() => useTicketHistory());

        act(() => {
            result.current.addEntry({
                message: "test ticket",
                status: "completed",
                responsePreview: "done",
            });
        });

        expect(result.current.entries).toHaveLength(1);
        expect(result.current.entries[0].message).toBe("test ticket");
        expect(result.current.entries[0].timestamp).toBeGreaterThan(0);
    });

    it("prepends new entries (most recent first)", () => {
        const { result } = renderHook(() => useTicketHistory());

        act(() => {
            result.current.addEntry({ message: "first", status: "completed", responsePreview: "" });
        });
        act(() => {
            result.current.addEntry({ message: "second", status: "completed", responsePreview: "" });
        });

        expect(result.current.entries[0].message).toBe("second");
        expect(result.current.entries[1].message).toBe("first");
    });

    it("limits to 10 entries max", () => {
        const { result } = renderHook(() => useTicketHistory());

        act(() => {
            for (let i = 0; i < 12; i++) {
                result.current.addEntry({ message: `entry-${i}`, status: "completed", responsePreview: "" });
            }
        });

        expect(result.current.entries).toHaveLength(10);
        expect(result.current.entries[0].message).toBe("entry-11");
    });

    it("persists to localStorage", () => {
        const { result } = renderHook(() => useTicketHistory());

        act(() => {
            result.current.addEntry({ message: "persisted", status: "completed", responsePreview: "" });
        });

        const stored = JSON.parse(localStorage.getItem("aegis-ticket-history")!);
        expect(stored).toHaveLength(1);
        expect(stored[0].message).toBe("persisted");
    });

    it("loads from localStorage on mount", () => {
        const existing = [
            { message: "loaded", timestamp: Date.now(), status: "completed", responsePreview: "yes" },
        ];
        localStorage.setItem("aegis-ticket-history", JSON.stringify(existing));

        const { result } = renderHook(() => useTicketHistory());
        // After useEffect, entries should load from localStorage
        expect(result.current.entries).toHaveLength(1);
        expect(result.current.entries[0].message).toBe("loaded");
    });

    it("clears entries and localStorage", () => {
        const { result } = renderHook(() => useTicketHistory());

        act(() => {
            result.current.addEntry({ message: "to-clear", status: "completed", responsePreview: "" });
        });
        expect(result.current.entries).toHaveLength(1);

        act(() => {
            result.current.clearHistory();
        });

        expect(result.current.entries).toHaveLength(0);
        expect(localStorage.getItem("aegis-ticket-history")).toBeNull();
    });

    it("handles corrupted localStorage gracefully", () => {
        localStorage.setItem("aegis-ticket-history", "NOT_VALID_JSON");
        const { result } = renderHook(() => useTicketHistory());
        // Should fall back to empty array
        expect(result.current.entries).toEqual([]);
    });

    it("handles localStorage.removeItem failure silently in clearHistory", () => {
        const originalRemove = Storage.prototype.removeItem;
        Storage.prototype.removeItem = () => { throw new Error("Storage error"); };

        const { result } = renderHook(() => useTicketHistory());
        act(() => {
            result.current.addEntry({ message: "test", status: "completed", responsePreview: "" });
        });

        // Should not throw
        act(() => {
            result.current.clearHistory();
        });
        expect(result.current.entries).toHaveLength(0);

        Storage.prototype.removeItem = originalRemove;
    });

    it("handles localStorage.setItem failure silently in persistEntries", () => {
        const originalSet = Storage.prototype.setItem;
        Storage.prototype.setItem = () => { throw new Error("Quota exceeded"); };

        const { result } = renderHook(() => useTicketHistory());

        // Should not throw even if storage fails
        act(() => {
            result.current.addEntry({ message: "no-persist", status: "completed", responsePreview: "" });
        });
        expect(result.current.entries).toHaveLength(1);

        Storage.prototype.setItem = originalSet;
    });

    it("returns empty entries when localStorage.getItem throws (SSR-like)", () => {
        // Simulates the SSR path — when window/localStorage is inaccessible,
        // loadEntries() catches and returns []
        const spy = vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
            throw new Error("window is not defined");
        });

        const { result } = renderHook(() => useTicketHistory());
        expect(result.current.entries).toEqual([]);

        spy.mockRestore();
    });
});
