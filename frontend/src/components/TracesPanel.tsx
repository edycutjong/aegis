"use client";

import { useState, useEffect, useCallback } from "react";
import type { TraceRun, TracesResponse } from "@/lib/api";
import { getTraces } from "@/lib/api";

const NODE_META: Record<string, { icon: string; color: string }> = {
    classify_intent: { icon: "🏷️", color: "#34d399" },
    validate_customer: { icon: "🔍", color: "#3b82f6" },
    write_sql: { icon: "📝", color: "#3b82f6" },
    execute_sql: { icon: "⚡", color: "#22d3ee" },
    search_docs: { icon: "📚", color: "#a78bfa" },
    propose_action: { icon: "💡", color: "#f59e0b" },
    await_approval: { icon: "⏸️", color: "#f472b6" },
    execute_action: { icon: "🔧", color: "#22d3ee" },
    generate_response: { icon: "✉️", color: "#34d399" },
};

const DEFAULT_META = { icon: "⬜", color: "#94a3b8" };

function getMeta(name: string) {
    if (NODE_META[name]) return NODE_META[name];
    const key = Object.keys(NODE_META).find((k) => name.toLowerCase().includes(k));
    return key ? NODE_META[key] : DEFAULT_META;
}

function formatMs(ms: number): string {
    if (ms >= 1000) return `${(ms / 1000).toFixed(1)}s`;
    return `${ms}ms`;
}

function timeAgo(iso: string): string {
    const diff = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
}

interface TracesPanelProps {
    open: boolean;
    onClose: () => void;
}

export default function TracesPanel({ open, onClose }: TracesPanelProps) {
    const [traces, setTraces] = useState<TraceRun[]>([]);
    const [error, setError] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);
    const [expandedTraceId, setExpandedTraceId] = useState<string | null>(null);

    const fetchTraces = useCallback(async () => {
        try {
            const data: TracesResponse = await getTraces();
            setTraces(data.traces);
            setError(data.error);
        } catch {
            setError("Failed to connect");
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        if (!open) return;
        fetchTraces();
        const interval = setInterval(fetchTraces, 120000);
        return () => clearInterval(interval);
    }, [open, fetchTraces]);

    // Close on Escape
    useEffect(() => {
        if (!open) return;
        const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
        window.addEventListener("keydown", handler);
        return () => window.removeEventListener("keydown", handler);
    }, [open, onClose]);

    const toggleTrace = (id: string) => {
        setExpandedTraceId((prev) => (prev === id ? null : id));
    };

    return (
        <>
            {/* Backdrop */}
            <div
                className="traces-backdrop"
                style={{ opacity: open ? 1 : 0, pointerEvents: open ? "auto" : "none" }}
                onClick={onClose}
            />

            {/* Slide-up panel */}
            <div
                className="traces-overlay"
                style={{ transform: open ? "translateY(0)" : "translateY(100%)" }}
            >
                {/* Header */}
                <div className="flex items-center justify-between px-6 py-4" style={{ borderBottom: "1px solid var(--aegis-border)" }}>
                    <div className="flex items-center gap-3">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#34d399" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
                        </svg>
                        <h2 className="text-sm font-semibold tracking-wide uppercase" style={{ color: "var(--aegis-text)" }}>
                            LangSmith Traces
                        </h2>
                        <span className="text-[10px] px-2 py-0.5 rounded-full" style={{ background: "var(--aegis-border)", color: "var(--aegis-text-muted)" }}>
                            {traces.length} trace{traces.length !== 1 ? "s" : ""}
                        </span>
                    </div>
                    <button
                        onClick={onClose}
                        className="p-1.5 rounded-lg transition-colors hover:bg-white/10"
                        title="Close (Esc)"
                    >
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--aegis-text-muted)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M18 6L6 18" /><path d="M6 6l12 12" />
                        </svg>
                    </button>
                </div>

                {/* Content */}
                <div className="flex-1 overflow-y-auto px-6 py-4">
                    {loading ? (
                        <div className="flex items-center justify-center py-12 gap-2">
                            <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none" stroke="#34d399" strokeWidth="2">
                                <path d="M21 12a9 9 0 1 1-6.219-8.56" />
                            </svg>
                            <span className="text-xs" style={{ color: "var(--aegis-text-muted)" }}>Loading traces…</span>
                        </div>
                    ) : error && traces.length === 0 ? (
                        <div className="text-center py-12">
                            <span className="text-sm" style={{ color: "var(--aegis-text-muted)" }}>⚠ {error}</span>
                        </div>
                    ) : traces.length === 0 ? (
                        <div className="text-center py-12">
                            <span className="text-sm" style={{ color: "var(--aegis-text-muted)" }}>
                                No traces yet — submit a ticket to generate one
                            </span>
                        </div>
                    ) : (
                        <div className="space-y-3">
                            {traces.map((trace) => {
                                const isOpen = expandedTraceId === trace.id;
                                const maxChildLatency = Math.max(...trace.child_runs.map((c) => c.latency_ms), 1);

                                return (
                                    <div key={trace.id} className="metric-card p-0 overflow-hidden">
                                        {/* Trace header */}
                                        <button
                                            onClick={() => toggleTrace(trace.id)}
                                            className="w-full flex items-center justify-between px-4 py-3 transition-colors hover:bg-white/5"
                                        >
                                            <div className="flex items-center gap-3">
                                                <div
                                                    className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                                                    style={{ background: trace.status === "success" ? "#34d399" : trace.status === "error" ? "#f87171" : "#f59e0b" }}
                                                />
                                                <span className="text-sm font-medium" style={{ color: "var(--aegis-text)" }}>
                                                    {trace.name}
                                                </span>
                                                {trace.start_time && (
                                                    <span className="text-xs" style={{ color: "var(--aegis-text-muted)" }}>
                                                        {timeAgo(trace.start_time)}
                                                    </span>
                                                )}
                                            </div>
                                            <div className="flex items-center gap-4">
                                                <span className="text-xs font-mono" style={{ color: "var(--aegis-text-muted)" }}>
                                                    {formatMs(trace.latency_ms)}
                                                </span>
                                                <span className="text-xs font-mono" style={{ color: "var(--aegis-text-muted)" }}>
                                                    {trace.total_tokens.toLocaleString()} tok
                                                </span>
                                                <span className="text-xs font-mono font-semibold" style={{ color: "#34d399" }}>
                                                    ${trace.total_cost.toFixed(4)}
                                                </span>
                                                <svg
                                                    width="12" height="12" viewBox="0 0 24 24" fill="none"
                                                    stroke="var(--aegis-text-muted)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
                                                    className="transition-transform duration-200"
                                                    style={{ transform: isOpen ? "rotate(180deg)" : "rotate(0deg)" }}
                                                >
                                                    <path d="M6 9l6 6 6-6" />
                                                </svg>
                                            </div>
                                        </button>

                                        {/* Child runs — full width waterfall */}
                                        {isOpen && trace.child_runs.length > 0 && (
                                            <div style={{ borderTop: "1px solid var(--aegis-border)" }}>
                                                {/* Column headers */}
                                                <div
                                                    className="grid px-4 py-1.5 text-[10px] uppercase tracking-wider font-medium"
                                                    style={{
                                                        color: "var(--aegis-text-muted)",
                                                        gridTemplateColumns: "28px 1fr 120px 80px 80px 80px 100px",
                                                        background: "var(--aegis-surface)",
                                                    }}
                                                >
                                                    <span />
                                                    <span>Node</span>
                                                    <span>Model</span>
                                                    <span className="text-right">Tokens</span>
                                                    <span className="text-right">Latency</span>
                                                    <span className="text-right">Cost</span>
                                                    <span>Timeline</span>
                                                </div>

                                                {trace.child_runs.map((child, i) => {
                                                    const meta = getMeta(child.name);
                                                    const barWidth = Math.max((child.latency_ms / maxChildLatency) * 100, 3);
                                                    const isLast = i === trace.child_runs.length - 1;

                                                    return (
                                                        <div
                                                            key={child.id}
                                                            className="trace-node-row grid items-center px-4 py-2"
                                                            style={{
                                                                borderBottom: isLast ? "none" : "1px solid var(--aegis-border)",
                                                                animationDelay: `${i * 40}ms`,
                                                                gridTemplateColumns: "28px 1fr 120px 80px 80px 80px 100px",
                                                            }}
                                                        >
                                                            {/* Dot */}
                                                            <div className="flex justify-center">
                                                                <div
                                                                    className="rounded-full"
                                                                    style={{ width: "8px", height: "8px", background: meta.color }}
                                                                />
                                                            </div>

                                                            {/* Node name */}
                                                            <div className="flex items-center gap-1.5">
                                                                <span className="text-xs">{meta.icon}</span>
                                                                <span className="text-xs font-medium" style={{ color: "var(--aegis-text)" }}>
                                                                    {child.name}
                                                                </span>
                                                            </div>

                                                            {/* Model */}
                                                            <div>
                                                                {child.model && (
                                                                    <span
                                                                        className="text-[10px] px-1.5 py-0.5 rounded"
                                                                        style={{ background: "var(--aegis-border)", color: "var(--aegis-text-muted)" }}
                                                                    >
                                                                        {child.model}
                                                                    </span>
                                                                )}
                                                            </div>

                                                            {/* Tokens */}
                                                            <span className="text-xs font-mono text-right" style={{ color: "var(--aegis-text-muted)" }}>
                                                                {child.total_tokens > 0 ? child.total_tokens.toLocaleString() : "—"}
                                                            </span>

                                                            {/* Latency */}
                                                            <span className="text-xs font-mono text-right" style={{ color: "var(--aegis-text-muted)" }}>
                                                                {formatMs(child.latency_ms)}
                                                            </span>

                                                            {/* Cost */}
                                                            <span className="text-xs font-mono text-right font-semibold" style={{ color: "#34d399" }}>
                                                                ${child.total_cost.toFixed(4)}
                                                            </span>

                                                            {/* Latency bar */}
                                                            <div className="h-1.5 rounded-full" style={{ background: "var(--aegis-border)" }}>
                                                                <div
                                                                    className="h-full rounded-full transition-all duration-500"
                                                                    style={{
                                                                        width: `${barWidth}%`,
                                                                        background: `linear-gradient(90deg, ${meta.color}, ${meta.color}80)`,
                                                                    }}
                                                                />
                                                            </div>
                                                        </div>
                                                    );
                                                })}

                                                {/* Summary */}
                                                <div
                                                    className="flex items-center justify-end gap-6 px-4 py-2"
                                                    style={{ background: "var(--aegis-surface)", borderTop: "1px solid var(--aegis-border)" }}
                                                >
                                                    <span className="text-[10px]" style={{ color: "var(--aegis-text-muted)" }}>
                                                        {trace.child_runs.length} steps
                                                    </span>
                                                    <span className="text-[10px] font-mono" style={{ color: "var(--aegis-text-muted)" }}>
                                                        {trace.total_tokens.toLocaleString()} tok
                                                    </span>
                                                    <span className="text-[10px] font-mono font-bold" style={{ color: "#34d399" }}>
                                                        ${trace.total_cost.toFixed(4)}
                                                    </span>
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                );
                            })}
                        </div>
                    )}
                </div>
            </div>
        </>
    );
}
