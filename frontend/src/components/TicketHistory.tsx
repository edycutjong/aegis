"use client";

import { useState } from "react";
import type { TicketHistoryEntry } from "@/hooks/useTicketHistory";

interface TicketHistoryProps {
    entries: TicketHistoryEntry[];
    onSelect: (message: string) => void;
    onClear: () => void;
}

function relativeTime(ts: number): string {
    const diff = Math.floor((Date.now() - ts) / 1000);
    if (diff < 60) return "just now";
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return `${Math.floor(diff / 86400)}d ago`;
}

export default function TicketHistory({ entries, onSelect, onClear }: TicketHistoryProps) {
    const [expanded, setExpanded] = useState(false);

    if (entries.length === 0) return null;

    return (
        <div className="ticket-history-container mb-4">
            {/* Header — always visible */}
            <button
                onClick={() => setExpanded((v) => !v)}
                className="ticket-history-header"
            >
                <div className="flex items-center gap-2">
                    <svg
                        width="12"
                        height="12"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        style={{ color: "var(--aegis-text-muted)" }}
                    >
                        <circle cx="12" cy="12" r="10" />
                        <polyline points="12 6 12 12 16 14" />
                    </svg>
                    <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: "var(--aegis-text-muted)" }}>
                        Recent Tickets
                    </span>
                    <span className="ticket-history-badge">{entries.length}</span>
                </div>
                <div className="flex items-center gap-2">
                    <button
                        onClick={(e) => {
                            e.stopPropagation();
                            onClear();
                        }}
                        className="ticket-history-clear-btn"
                        title="Clear history"
                    >
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <polyline points="3 6 5 6 21 6" />
                            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                        </svg>
                    </button>
                    <svg
                        width="14"
                        height="14"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        className="ticket-history-chevron"
                        style={{
                            color: "var(--aegis-text-muted)",
                            transform: expanded ? "rotate(180deg)" : "rotate(0deg)",
                            transition: "transform 0.2s ease",
                        }}
                    >
                        <polyline points="6 9 12 15 18 9" />
                    </svg>
                </div>
            </button>

            {/* Entries — collapsible */}
            <div
                className="ticket-history-body"
                style={{
                    maxHeight: expanded ? `${entries.length * 64 + 8}px` : "0px",
                }}
            >
                <div className="space-y-1 pt-2">
                    {entries.map((entry, i) => (
                        <button
                            key={`${entry.timestamp}-${i}`}
                            onClick={() => onSelect(entry.message)}
                            className="ticket-history-entry"
                        >
                            <div className="flex items-start gap-2 flex-1 min-w-0">
                                <span
                                    className="ticket-history-status-dot"
                                    style={{
                                        background: entry.status === "completed" ? "var(--aegis-success)" : "var(--aegis-danger)",
                                    }}
                                />
                                <div className="flex-1 min-w-0">
                                    <p className="text-xs truncate" style={{ color: "var(--aegis-text)" }}>
                                        {entry.message.length > 60 ? entry.message.slice(0, 60) + "…" : entry.message}
                                    </p>
                                    {entry.responsePreview && (
                                        <p className="text-xs truncate mt-0.5" style={{ color: "var(--aegis-text-muted)", opacity: 0.7 }}>
                                            {entry.responsePreview}
                                        </p>
                                    )}
                                </div>
                            </div>
                            <span className="ticket-history-time">
                                {relativeTime(entry.timestamp)}
                            </span>
                        </button>
                    ))}
                </div>
            </div>
        </div>
    );
}
