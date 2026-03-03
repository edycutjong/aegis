"use client";

import { useEffect, useState } from "react";
import type { DbStatus } from "@/lib/api";
import { getDbStatus, getTableData } from "@/lib/api";

const TABLE_META: Record<string, { label: string; icon: string; color: string; columns: string[] }> = {
    customers: { label: "Customers", icon: "👤", color: "#60a5fa", columns: ["id", "name", "email", "plan", "status", "company"] },
    billing: { label: "Billing", icon: "💳", color: "#4ade80", columns: ["id", "customer_id", "amount", "type", "status", "description"] },
    support_tickets: { label: "Tickets", icon: "🎫", color: "#fbbf24", columns: ["id", "customer_id", "subject", "priority", "status", "category"] },
    internal_docs: { label: "Docs", icon: "📄", color: "#a78bfa", columns: ["id", "title", "category"] },
};

function timeAgo(iso: string): { text: string; stale: boolean } {
    const diff = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return { text: "just now", stale: false };
    if (mins < 60) return { text: `${mins}m ago`, stale: false };
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return { text: `${hrs}h ago`, stale: hrs > 3 };
    const days = Math.floor(hrs / 24);
    return { text: `${days}d ago`, stale: true };
}

function truncate(val: unknown, max = 40): string {
    const s = String(val ?? "—");
    return s.length > max ? s.slice(0, max) + "…" : s;
}

export default function DatabaseStatus() {
    const [db, setDb] = useState<DbStatus | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [expanded, setExpanded] = useState<string | null>(null);
    const [tableRows, setTableRows] = useState<Record<string, unknown>[]>([]);
    const [tableLoading, setTableLoading] = useState(false);

    useEffect(() => {
        getDbStatus()
            .then(setDb)
            .catch((e) => setError(e.message))
            .finally(() => setLoading(false));
    }, []);

    const handleCardClick = async (tableName: string) => {
        if (expanded === tableName) {
            setExpanded(null);
            setTableRows([]);
            return;
        }
        setExpanded(tableName);
        setTableLoading(true);
        try {
            const data = await getTableData(tableName);
            setTableRows(data.rows || []);
        } catch {
            setTableRows([]);
        } finally {
            setTableLoading(false);
        }
    };

    // Find most recent timestamp across all tables
    const latestTimestamps = db
        ? Object.values(db).filter((t) => t.latest).map((t) => new Date(t.latest!).getTime())
        : [];
    const mostRecent = latestTimestamps.length > 0 ? new Date(Math.max(...latestTimestamps)).toISOString() : null;
    const freshness = mostRecent ? timeAgo(mostRecent) : null;

    const expandedMeta = expanded ? TABLE_META[expanded] : null;

    return (
        <div className="glass-panel" style={{ borderTop: "1px solid var(--aegis-border)" }}>
            {/* Summary row */}
            <div className="px-4 py-3">
                <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#60a5fa" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <ellipse cx="12" cy="5" rx="9" ry="3" /><path d="M3 5v14a9 3 0 0 0 18 0V5" /><path d="M3 12a9 3 0 0 0 18 0" />
                        </svg>
                        <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: "var(--aegis-text-muted)" }}>
                            Database
                        </span>
                    </div>
                    <div className="flex items-center gap-2">
                        {loading && (
                            <svg className="w-3 h-3 animate-spin" viewBox="0 0 24 24" fill="none" stroke="#60a5fa" strokeWidth="2">
                                <path d="M21 12a9 9 0 1 1-6.219-8.56" />
                            </svg>
                        )}
                        {error && <span className="text-xs text-red-400">Error</span>}
                        {freshness && (
                            <span className={`text-xs ${freshness.stale ? "text-amber-400" : "text-emerald-400"}`}>
                                {freshness.stale ? "⚠" : "✓"} {freshness.text}
                            </span>
                        )}
                    </div>
                </div>

                {db && (
                    <div className="grid grid-cols-4 gap-2">
                        {Object.entries(TABLE_META).map(([key, meta]) => {
                            const table = db[key];
                            if (!table) return null;
                            const isActive = expanded === key;
                            return (
                                <button
                                    key={key}
                                    onClick={() => handleCardClick(key)}
                                    className="rounded-lg px-3 py-2 text-center transition-all duration-200 cursor-pointer"
                                    style={{
                                        background: isActive ? `${meta.color}15` : "rgba(255,255,255,0.03)",
                                        border: `1px solid ${isActive ? meta.color + "40" : "var(--aegis-border)"}`,
                                        outline: "none",
                                    }}
                                >
                                    <span className="text-sm block">{meta.icon}</span>
                                    <span className="text-lg font-bold block" style={{ color: meta.color }}>
                                        {table.count}
                                    </span>
                                    <span className="text-[10px] block" style={{ color: "var(--aegis-text-muted)" }}>
                                        {meta.label}
                                    </span>
                                </button>
                            );
                        })}
                    </div>
                )}

                {!loading && !error && db && Object.values(db).every(t => t.count === 0) && (
                    <div className="text-xs text-center py-2" style={{ color: "var(--aegis-text-muted)" }}>
                        ⚠ No data found — run <code className="text-amber-400">seed.sql</code> in Supabase SQL Editor
                    </div>
                )}
            </div>

            {/* Expanded data table */}
            {expanded && expandedMeta && (
                <div
                    className="border-t px-4 py-3 overflow-x-auto"
                    style={{ borderColor: "var(--aegis-border)", maxHeight: "280px", overflowY: "auto" }}
                >
                    {tableLoading ? (
                        <div className="flex items-center justify-center py-4 gap-2">
                            <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none" stroke={expandedMeta.color} strokeWidth="2">
                                <path d="M21 12a9 9 0 1 1-6.219-8.56" />
                            </svg>
                            <span className="text-xs" style={{ color: "var(--aegis-text-muted)" }}>Loading {expandedMeta.label}…</span>
                        </div>
                    ) : tableRows.length === 0 ? (
                        <div className="text-xs text-center py-3" style={{ color: "var(--aegis-text-muted)" }}>No records</div>
                    ) : (
                        <table className="w-full text-xs" style={{ borderCollapse: "collapse" }}>
                            <thead>
                                <tr>
                                    {expandedMeta.columns.map((col) => (
                                        <th
                                            key={col}
                                            className="text-left px-2 py-1.5 font-semibold uppercase tracking-wider"
                                            style={{ color: "var(--aegis-text-muted)", borderBottom: "1px solid var(--aegis-border)", fontSize: "10px" }}
                                        >
                                            {col.replace(/_/g, " ")}
                                        </th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody>
                                {tableRows.map((row, i) => (
                                    <tr
                                        key={i}
                                        className="transition-colors hover:bg-white/5"
                                        style={{ borderBottom: "1px solid var(--aegis-border)" }}
                                    >
                                        {expandedMeta.columns.map((col) => (
                                            <td
                                                key={col}
                                                className="px-2 py-1.5"
                                                style={{ color: "var(--aegis-text)", whiteSpace: "nowrap" }}
                                                title={String(row[col] ?? "")}
                                            >
                                                {col === "amount" && typeof row[col] === "number"
                                                    ? `$${(row[col] as number).toFixed(2)}`
                                                    : truncate(row[col])}
                                            </td>
                                        ))}
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    )}
                </div>
            )}
        </div>
    );
}
