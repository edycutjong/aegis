"use client";

import { useState } from "react";
import { ChevronDown, History, Trash2 } from "lucide-react";
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

/**
 * Tickets this browser has run (localStorage — private to this visitor,
 * unlike the Observability panel, which aggregates everyone).
 */
export default function TicketHistory({ entries, onSelect, onClear }: TicketHistoryProps) {
    const [expanded, setExpanded] = useState(false);

    if (entries.length === 0) return null;

    return (
        <div className="ticket-history-container">
            <div className="ticket-history-header">
                <button
                    type="button"
                    className="ticket-history-toggle"
                    aria-expanded={expanded}
                    aria-controls="ticket-history-list"
                    onClick={() => setExpanded((v) => !v)}
                    title="Stored in this browser only"
                >
                    <History size={13} aria-hidden="true" className="text-3 shrink-0" />
                    <span className="text-xs font-semibold uppercase tracking-wider text-3 whitespace-nowrap">Recent Tickets</span>
                    <span className="ticket-history-badge">{entries.length}</span>
                    <span className="sr-only">, stored in this browser only</span>
                    <ChevronDown
                        size={14}
                        aria-hidden="true"
                        className="ml-auto text-3 transition-transform duration-200"
                        style={{ transform: expanded ? "rotate(180deg)" : "none" }}
                    />
                </button>
                <button type="button" onClick={onClear} className="ticket-history-clear-btn" aria-label="Clear ticket history" title="Clear history">
                    <Trash2 size={12} aria-hidden="true" />
                </button>
            </div>

            <div
                id="ticket-history-list"
                className="ticket-history-body"
                hidden={!expanded}
                style={{ maxHeight: expanded ? `${entries.length * 64 + 8}px` : "0px" }}
            >
                <div className="space-y-1 pt-1 pb-1">
                    {entries.map((entry, i) => (
                        <button
                            key={`${entry.timestamp}-${i}`}
                            type="button"
                            onClick={() => onSelect(entry.message)}
                            className="ticket-history-entry"
                        >
                            <div className="flex items-start gap-2 flex-1 min-w-0">
                                <span
                                    className="ticket-history-status-dot"
                                    style={{ background: entry.status === "completed" ? "var(--ok)" : "var(--fail)" }}
                                    aria-hidden="true"
                                />
                                <span className="sr-only">{entry.status === "completed" ? "Resolved: " : "Stopped: "}</span>
                                <div className="flex-1 min-w-0">
                                    <p className="text-xs truncate text-1">
                                        {entry.message.length > 60 ? entry.message.slice(0, 60) + "…" : entry.message}
                                    </p>
                                    {entry.responsePreview && <p className="text-xs truncate mt-0.5 text-3">{entry.responsePreview}</p>}
                                </div>
                            </div>
                            <span className="ticket-history-time">{relativeTime(entry.timestamp)}</span>
                        </button>
                    ))}
                </div>
            </div>
        </div>
    );
}
