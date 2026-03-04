"use client";

import { useState, useCallback } from "react";

export interface TicketHistoryEntry {
    message: string;
    timestamp: number;
    status: "completed" | "error";
    responsePreview: string;
}

const STORAGE_KEY = "aegis-ticket-history";
const MAX_ENTRIES = 10;

function loadEntries(): TicketHistoryEntry[] {
    /* v8 ignore start: unreachable in jsdom */
    if (typeof window === "undefined") return [];
    /* v8 ignore stop */
    try {
        const raw = localStorage.getItem(STORAGE_KEY);
        return raw ? JSON.parse(raw) : [];
    } catch {
        return [];
    }
}

function persistEntries(entries: TicketHistoryEntry[]) {
    try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(entries));
    } catch {
        // Storage full or unavailable — silently ignore
    }
}

export function useTicketHistory() {
    const [entries, setEntries] = useState<TicketHistoryEntry[]>(loadEntries);

    const addEntry = useCallback(
        (entry: Omit<TicketHistoryEntry, "timestamp">) => {
            setEntries((prev) => {
                const next = [
                    { ...entry, timestamp: Date.now() },
                    ...prev,
                ].slice(0, MAX_ENTRIES);
                persistEntries(next);
                return next;
            });
        },
        []
    );

    const clearHistory = useCallback(() => {
        setEntries([]);
        try {
            localStorage.removeItem(STORAGE_KEY);
        } catch {
            // ignore
        }
    }, []);

    return { entries, addEntry, clearHistory };
}
