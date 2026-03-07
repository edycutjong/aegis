"use client";


import { useState, useEffect } from "react";
import type { Metrics, DbStatus } from "@/lib/api";
import { clearCache, getDbStatus, getTableData, getTracingStatus } from "@/lib/api";
import AnimatedNumber from "./AnimatedNumber";

interface MetricsPanelProps {
    metrics: Metrics | null;
    onCacheCleared?: () => void;
    onOpenTraces?: () => void;
}

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

function formatCompact(n: number, decimals = 1): string {
    if (n >= 1_000_000_000) return (n / 1_000_000_000).toFixed(decimals) + "B";
    if (n >= 1_000_000) return (n / 1_000_000).toFixed(decimals) + "M";
    if (n >= 10_000) return (n / 1_000).toFixed(decimals) + "K";
    return n.toLocaleString();
}

function truncate(val: unknown, max = 32): string {
    const s = String(val ?? "—");
    return s.length > max ? s.slice(0, max) + "…" : s;
}

export default function MetricsPanel({ metrics, onCacheCleared, onOpenTraces }: MetricsPanelProps) {
    const agent = metrics?.agent_metrics;
    const cache = metrics?.cache_metrics;
    const [clearing, setClearing] = useState(false);
    const [clearMsg, setClearMsg] = useState<string | null>(null);
    const [tracingEnabled, setTracingEnabled] = useState(false);

    // Check if LangSmith tracing is enabled on mount
    useEffect(() => {
        getTracingStatus()
            .then((s) => setTracingEnabled(s.enabled))
            .catch(() => setTracingEnabled(false));
    }, []);

    // Database state
    const [db, setDb] = useState<DbStatus | null>(null);
    const [expanded, setExpanded] = useState<string | null>(null);
    const [tableRows, setTableRows] = useState<Record<string, unknown>[]>([]);
    const [tableLoading, setTableLoading] = useState(false);

    useEffect(() => {
        getDbStatus().then(setDb).catch(() => { });
    }, []);

    // Calculate model distribution percentages
    const modelTotal = agent?.model_distribution
        ? Object.values(agent.model_distribution).reduce((a, b) => a + b, 0)
        : 0;

    const handleClearCache = async () => {
        setClearing(true);
        setClearMsg(null);
        try {
            const result = await clearCache();
            setClearMsg(`Cleared! (${result.keys_deleted} keys)`);
            onCacheCleared?.();
            setTimeout(() => setClearMsg(null), 2000);
        } catch {
            setClearMsg("Failed to clear");
            setTimeout(() => setClearMsg(null), 2000);
        } finally {
            setClearing(false);
        }
    };

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

    // DB freshness
    const latestTimestamps = db
        ? Object.values(db).filter((t) => t.latest).map((t) => new Date(t.latest!).getTime())
        : [];
    const mostRecent = latestTimestamps.length > 0 ? new Date(Math.max(...latestTimestamps)).toISOString() : null;
    const freshness = mostRecent ? timeAgo(mostRecent) : null;
    const expandedMeta = expanded ? TABLE_META[expanded] : null;

    return (
        <div className="glass-panel h-full min-h-0 flex flex-col overflow-hidden">
            {/* Header */}
            <div className="flex items-center gap-3 mb-5 px-6 pt-6 shrink-0">
                <div className="w-8 h-8 rounded-lg bg-purple-500/10 flex items-center justify-center">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#a78bfa" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M18 20V10" /><path d="M12 20V4" /><path d="M6 20v-6" />
                    </svg>
                </div>
                <h2 className="text-sm font-semibold tracking-wide uppercase" style={{ color: "var(--aegis-text-muted)" }}>
                    Observability
                </h2>
            </div>

            <div className="flex-1 overflow-y-auto pl-6 pr-4 pb-6 space-y-4" style={{ scrollbarGutter: "stable" }}>
                {/* Primary Metrics */}
                <div className="grid grid-cols-2 gap-3 animate-slide-up-fade" style={{ animationDelay: "0.4s" }}>
                    <div className="metric-card">
                        <span className="metric-label text-xs block mb-1" style={{ color: "var(--aegis-text-muted)" }}>Avg Cost/Req</span>
                        <span className="text-xl font-bold text-emerald-400">
                            $<AnimatedNumber value={agent?.avg_cost_usd || 0} format={(v) => v.toFixed(4)} />
                        </span>
                    </div>
                    <div className="metric-card">
                        <span className="metric-label text-xs block mb-1" style={{ color: "var(--aegis-text-muted)" }}>Total Requests</span>
                        <span className="text-xl font-bold text-blue-400">
                            <AnimatedNumber value={agent?.total_requests || 0} format={(v) => formatCompact(Math.round(v))} />
                        </span>
                    </div>
                    <div className="metric-card">
                        <span className="metric-label text-xs block mb-1" style={{ color: "var(--aegis-text-muted)" }}>Total Cost</span>
                        <span className="text-xl font-bold text-amber-400">
                            $<AnimatedNumber value={agent?.total_cost_usd || 0} format={(v) => v.toFixed(4)} />
                        </span>
                    </div>
                    <div className="metric-card">
                        <span className="metric-label text-xs block mb-1" style={{ color: "var(--aegis-text-muted)" }}>Total Tokens</span>
                        <span className="text-xl font-bold text-purple-400">
                            <AnimatedNumber value={agent?.total_tokens || 0} format={(v) => formatCompact(Math.round(v))} />
                        </span>
                    </div>
                </div>

                {/* Production Metrics */}
                <div className="grid grid-cols-2 gap-3 animate-slide-up-fade" style={{ animationDelay: "0.5s" }}>
                    <div className="metric-card">
                        <span className="metric-label text-xs block mb-1" style={{ color: "var(--aegis-text-muted)" }}>HITL Approval</span>
                        <span className="text-xl font-bold" style={{ color: agent?.hitl_approval_rate != null ? (agent.hitl_approval_rate >= 80 ? "#4ade80" : "#f87171") : "var(--aegis-text-muted)" }}>
                            {agent?.hitl_approval_rate != null ? <AnimatedNumber value={agent.hitl_approval_rate} format={(v) => Math.round(v) + "%"} /> : "—"}
                        </span>
                    </div>
                    <div className="metric-card">
                        <span className="metric-label text-xs block mb-1" style={{ color: "var(--aegis-text-muted)" }}>Avg Resolution</span>
                        <span className="text-xl font-bold text-cyan-400">
                            {agent?.avg_duration_seconds ? <AnimatedNumber value={agent.avg_duration_seconds} format={(v) => v.toFixed(1) + "s"} /> : "—"}
                        </span>
                    </div>
                    <div className="metric-card">
                        <span className="metric-label text-xs block mb-1" style={{ color: "var(--aegis-text-muted)" }}>HITL Wait</span>
                        <span className="text-xl font-bold text-orange-400">
                            {agent?.avg_hitl_wait_seconds != null ? <AnimatedNumber value={agent.avg_hitl_wait_seconds} format={(v) => v.toFixed(1) + "s"} /> : "—"}
                        </span>
                    </div>
                    <div className="metric-card">
                        <span className="metric-label text-xs block mb-1" style={{ color: "var(--aegis-text-muted)" }}>Cache Savings</span>
                        <span className="text-xl font-bold text-emerald-400">
                            $<AnimatedNumber value={agent?.cost_saved_by_cache || 0} format={(v) => v.toFixed(4)} />
                        </span>
                    </div>
                </div>

                <div className="space-y-2 animate-slide-up-fade" style={{ animationDelay: "0.6s" }}>
                    <div className="flex items-center justify-between">
                        <h3 className="text-xs font-semibold uppercase tracking-wider" style={{ color: "var(--aegis-text-muted)" }}>
                            Semantic Cache
                        </h3>
                        <div className="flex items-center gap-2">
                            {clearMsg && (
                                <span className="text-xs text-emerald-400 animate-pulse">{clearMsg}</span>
                            )}
                            <button
                                id="clear-cache-btn"
                                onClick={handleClearCache}
                                disabled={clearing || !cache?.connected}
                                className="p-1 rounded-md transition-all duration-200 hover:bg-white/10 disabled:opacity-30 disabled:cursor-not-allowed"
                                title="Clear cache"
                            >
                                {clearing ? (
                                    <svg className="w-3.5 h-3.5 animate-spin" viewBox="0 0 24 24" fill="none" stroke="#a78bfa" strokeWidth="2">
                                        <path d="M21 12a9 9 0 1 1-6.219-8.56" />
                                    </svg>
                                ) : (
                                    <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="#a78bfa" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                        <path d="M3 6h18" /><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" /><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" />
                                    </svg>
                                )}
                            </button>
                        </div>
                    </div>
                    <div className="metric-card">
                        <div className="flex items-center justify-between mb-2">
                            <span className="text-xs" style={{ color: "var(--aegis-text-muted)" }}>Hit Rate</span>
                            <span className="text-sm font-bold" style={{ color: (cache?.hit_rate_percent || 0) > 50 ? "#4ade80" : "#60a5fa" }}>
                                <AnimatedNumber value={cache?.hit_rate_percent || 0} format={(v) => v.toFixed(1) + "%"} />
                            </span>
                        </div>
                        {/* Progress bar */}
                        <div className="w-full h-2 rounded-full" style={{ background: "var(--aegis-border)" }}>
                            <div
                                className="h-full rounded-full transition-all duration-500"
                                style={{
                                    width: `${cache?.hit_rate_percent || 0}%`,
                                    background: "linear-gradient(90deg, #3b82f6, #22c55e)",
                                }}
                            />
                        </div>
                        <div className="flex justify-between mt-2">
                            <span className="text-xs" style={{ color: "var(--aegis-text-muted)" }}>
                                <AnimatedNumber value={cache?.hits || 0} format={(v) => Math.round(v) + " hits"} />
                            </span>
                            <span className="text-xs" style={{ color: "var(--aegis-text-muted)" }}>
                                <AnimatedNumber value={cache?.misses || 0} format={(v) => Math.round(v) + " misses"} />
                            </span>
                        </div>
                    </div>
                    <div className="flex items-center gap-2 mt-1">
                        <div className={`w-2 h-2 rounded-full ${cache?.connected ? "bg-emerald-400" : "bg-red-400"}`} />
                        <span className="text-xs" style={{ color: "var(--aegis-text-muted)" }}>
                            Redis {cache?.connected ? "Connected" : "Disconnected"}
                        </span>
                    </div>
                </div>

                {/* Model Distribution */}
                {agent?.model_distribution && modelTotal > 0 && (() => {
                    // Compute provider-level aggregation
                    const providers: Record<string, { count: number; color: string; icon: string }> = {};
                    const providerMap: Record<string, { label: string; color: string; icon: string }> = {
                        gemini: { label: "Gemini", color: "#4285f4", icon: "🧠" },
                        llama: { label: "Groq", color: "#f97316", icon: "⚡" },
                        gpt: { label: "OpenAI", color: "#10b981", icon: "🟢" },
                        o: { label: "OpenAI", color: "#10b981", icon: "🟢" },
                        claude: { label: "Anthropic", color: "#d946ef", icon: "🟣" },
                    };

                    for (const [model, count] of Object.entries(agent.model_distribution)) {
                        const prefix = Object.keys(providerMap).find((p) => model.startsWith(p)) || "other";
                        const meta = providerMap[prefix] || { label: "Other", color: "#94a3b8", icon: "⬜" };
                        const key = meta.label;
                        if (!providers[key]) providers[key] = { count: 0, color: meta.color, icon: meta.icon };
                        providers[key].count += count;
                    }

                    return (
                        <div className="space-y-2 animate-slide-up-fade" style={{ animationDelay: "0.7s" }}>
                            <h3 className="text-xs font-semibold uppercase tracking-wider" style={{ color: "var(--aegis-text-muted)" }}>
                                Model Usage
                            </h3>

                            {/* Provider split bar */}
                            <div className="metric-card py-2 px-3">
                                <div className="flex items-center justify-between gap-2 mb-2 w-full">
                                    {Object.entries(providers).map(([label, { count, color, icon }]) => {
                                        const pct = ((count / modelTotal) * 100);
                                        return (
                                            <div key={label} className="flex items-center gap-1 text-xs font-semibold whitespace-nowrap" style={{ color }}>
                                                <span>{icon}</span>
                                                <span>{label}</span>
                                                <span><AnimatedNumber value={pct} format={(v) => Math.round(v) + "%"} /></span>
                                            </div>
                                        );
                                    })}
                                </div>
                                <div className="w-full h-2 rounded-full flex overflow-hidden" style={{ background: "var(--aegis-border)" }}>
                                    {Object.entries(providers).map(([label, { count, color }]) => (
                                        <div
                                            key={label}
                                            className="h-full transition-all duration-500"
                                            style={{
                                                width: `${((count / modelTotal) * 100).toFixed(1)}%`,
                                                background: color,
                                            }}
                                        />
                                    ))}
                                </div>
                            </div>

                            {/* Per-model detail removed — provider bar is sufficient */}
                        </div>
                    );
                })()}



                {/* ── LangSmith Traces trigger ── */}
                {tracingEnabled && (
                    <button
                        onClick={onOpenTraces}
                        className="w-full metric-card flex items-center justify-between px-4 py-3 transition-colors hover:bg-white/5 cursor-pointer group"
                    >
                        <div className="flex items-center gap-2">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#34d399" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
                            </svg>
                            <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: "var(--aegis-text-muted)" }}>
                                LangSmith Traces
                            </span>
                        </div>
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--aegis-text-muted)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="transition-transform group-hover:translate-y-[-2px]">
                            <path d="M7 17l9.2-9.2M17 17V7H7" />
                        </svg>
                    </button>
                )}
                {/* ── Database Section ── */}
                {db && (
                    <div className="space-y-2 animate-slide-up-fade" style={{ animationDelay: "0.8s" }}>
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#60a5fa" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                    <ellipse cx="12" cy="5" rx="9" ry="3" /><path d="M3 5v14a9 3 0 0 0 18 0V5" /><path d="M3 12a9 3 0 0 0 18 0" />
                                </svg>
                                <h3 className="text-xs font-semibold uppercase tracking-wider" style={{ color: "var(--aegis-text-muted)" }}>
                                    Database
                                </h3>
                            </div>
                            {freshness && (
                                <span className={`text-[10px] ${freshness.stale ? "text-amber-400" : "text-emerald-400"}`}>
                                    {freshness.stale ? "⚠" : "✓"} {freshness.text}
                                </span>
                            )}
                        </div>

                        <div className="grid grid-cols-2 gap-2">
                            {Object.entries(TABLE_META).map(([key, meta]) => {
                                const table = db[key];
                                if (!table) return null;
                                const isActive = expanded === key;
                                return (
                                    <button
                                        key={key}
                                        onClick={() => handleCardClick(key)}
                                        className="metric-card py-2 px-3 flex items-center gap-2 transition-all duration-200 cursor-pointer text-left"
                                        style={{
                                            border: isActive ? `1px solid ${meta.color}40` : undefined,
                                            background: isActive ? `${meta.color}10` : undefined,
                                        }}
                                    >
                                        <span className="text-sm">{meta.icon}</span>
                                        <div>
                                            <span className="text-sm font-bold block" style={{ color: meta.color }}>
                                                {table.count}
                                            </span>
                                            <span className="text-[10px] block" style={{ color: "var(--aegis-text-muted)" }}>
                                                {meta.label}
                                            </span>
                                        </div>
                                    </button>
                                );
                            })}
                        </div>

                        {/* Expanded data table */}
                        {expanded && expandedMeta && (
                            <div
                                className="metric-card overflow-x-auto"
                                style={{ maxHeight: "220px", overflowY: "auto", padding: 0 }}
                            >
                                {tableLoading ? (
                                    <div className="flex items-center justify-center py-4 gap-2">
                                        <svg className="w-3.5 h-3.5 animate-spin" viewBox="0 0 24 24" fill="none" stroke={expandedMeta.color} strokeWidth="2">
                                            <path d="M21 12a9 9 0 1 1-6.219-8.56" />
                                        </svg>
                                        <span className="text-[10px]" style={{ color: "var(--aegis-text-muted)" }}>Loading…</span>
                                    </div>
                                ) : tableRows.length === 0 ? (
                                    <div className="text-[10px] text-center py-3" style={{ color: "var(--aegis-text-muted)" }}>No records</div>
                                ) : (
                                    <table className="w-full" style={{ borderCollapse: "collapse", fontSize: "10px" }}>
                                        <thead>
                                            <tr>
                                                {expandedMeta.columns.map((col) => (
                                                    <th
                                                        key={col}
                                                        className="text-left px-2 py-1.5 font-semibold uppercase tracking-wider sticky top-0"
                                                        style={{ color: "var(--aegis-text-muted)", borderBottom: "1px solid var(--aegis-border)", background: "var(--aegis-panel)", fontSize: "9px" }}
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
                                                            className="px-2 py-1"
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
                )}
            </div>
        </div>
    );
}
