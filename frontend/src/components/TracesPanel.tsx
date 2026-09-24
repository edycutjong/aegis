"use client";

import { useState, useEffect, useCallback } from "react";
import type { TraceRun, TracesResponse } from "@/lib/api";
import { getTraces } from "@/lib/api";

const NODE_META: Record<string, { color: string }> = {
    classify_intent: { color: "#34d399" },
    validate_customer: { color: "#3b82f6" },
    write_sql: { color: "#3b82f6" },
    execute_sql: { color: "#22d3ee" },
    search_docs: { color: "#a78bfa" },
    propose_action: { color: "#f59e0b" },
    await_approval: { color: "#f59e0b" },
    execute_action: { color: "#22d3ee" },
    generate_response: { color: "#34d399" },
};

const DEFAULT_META = { color: "#94a3b8" };

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
    const [expandedTraceIds, setExpandedTraceIds] = useState<Set<string>>(new Set());

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

    // LangSmith also records isolated helper calls (0 ms, no tokens, no child
    // runs). They carry nothing to inspect, so they never render as rows.
    const useful = traces.filter((t) => t.child_runs.length > 0 || t.latency_ms > 0 || t.total_tokens > 0);
    const hidden = traces.length - useful.length;

    const toggleTrace = (id: string) => {
        setExpandedTraceIds((prev) => {
            const next = new Set(prev);
            if (next.has(id)) next.delete(id); else next.add(id);
            return next;
        });
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
                role="dialog"
                aria-label="LangSmith traces"
                aria-hidden={!open}
                inert={!open}
                style={{ transform: open ? "translateY(0)" : "translateY(100%)", visibility: open ? "visible" : "hidden", transition: open ? undefined : "transform 0.35s cubic-bezier(0.32, 0.72, 0, 1), visibility 0s 0.35s" }}
            >
                {/* Header */}
                <div className="flex items-center justify-between px-5 py-3.5" style={{ borderBottom: "1px solid var(--aegis-border)" }}>
                    <div className="flex items-center gap-3">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--aegis-text-muted)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
                        </svg>
                        <h2 className="text-[11px] font-semibold tracking-[0.08em] uppercase" style={{ color: "var(--aegis-text)" }}>
                            LangSmith Traces
                        </h2>
                        <span className="text-[10px] px-2 py-0.5 rounded-full font-mono" style={{ background: "var(--aegis-surface-2)", border: "1px solid var(--aegis-border)", color: "var(--aegis-text-muted)" }}>
                            {useful.length} trace{useful.length !== 1 ? "s" : ""}
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
                        <div className="flex items-center justify-center py-12 gap-2" style={{ color: "var(--aegis-text-muted)" }}>
                            <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                <path d="M21 12a9 9 0 1 1-6.219-8.56" />
                            </svg>
                            <span className="text-xs">Fetching recent runs from LangSmith — the first load can take up to a minute…</span>
                        </div>
                    ) : error && traces.length === 0 ? (
                        <div className="offline-state max-w-md mx-auto my-8">
                            <p className="text-[13px] font-medium mb-1" style={{ color: "var(--hold-text)" }}>⚠ {error}</p>
                            <p className="text-[11px]" style={{ color: "var(--aegis-text-muted)" }}>
                                Traces come from LangSmith via the backend — check the API connection.
                            </p>
                        </div>
                    ) : useful.length === 0 ? (
                        <div className="offline-state max-w-md mx-auto my-8">
                            <p className="text-[13px] font-medium mb-1" style={{ color: "var(--aegis-text-2)" }}>
                                No full agent runs in LangSmith yet
                            </p>
                            <p className="text-[12px] leading-relaxed" style={{ color: "var(--aegis-text-muted)" }}>
                                Tracing is connected, but LangSmith hasn&apos;t recorded a complete run to show here
                                {hidden > 0 ? ` (${hidden} empty helper ${hidden === 1 ? "call" : "calls"} hidden)` : ""}. The run receipt under
                                every finished ticket shows the same breakdown: each LLM call, its model, tokens and cost.
                            </p>
                        </div>
                    ) : (
                        <div className="space-y-3">
                            {useful.map((trace) => {
                                const isOpen = expandedTraceIds.has(trace.id);
                                const expandable = trace.child_runs.length > 0;
                                const maxChildLatency = Math.max(...trace.child_runs.map((c) => c.latency_ms), 1);

                                return (
                                    <div key={trace.id} className="metric-card p-0 overflow-hidden">
                                        {/* Trace header */}
                                        <button
                                            type="button"
                                            onClick={() => toggleTrace(trace.id)}
                                            disabled={!expandable}
                                            aria-expanded={expandable ? isOpen : undefined}
                                            className="w-full flex items-center justify-between px-4 py-3 transition-colors enabled:hover:bg-white/5 disabled:cursor-default"
                                        >
                                            <div className="flex items-center gap-3">
                                                <div
                                                    className="w-2.5 h-2.5 rounded-full shrink-0"
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
                                                {expandable && <svg
                                                    width="12" height="12" viewBox="0 0 24 24" fill="none"
                                                    stroke="var(--aegis-text-muted)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
                                                    className="transition-transform duration-200"
                                                    style={{ transform: isOpen ? "rotate(180deg)" : "rotate(0deg)" }}
                                                >
                                                    <path d="M6 9l6 6 6-6" />
                                                </svg>}
                                            </div>
                                        </button>

                                        {/* Child runs — full width waterfall */}
                                        {isOpen && expandable && (
                                            <div className="overflow-x-auto" style={{ borderTop: "1px solid var(--aegis-border)" }}>
                                                {/* Column headers */}
                                                <div
                                                    className="grid px-4 py-1.5 text-[10px] uppercase tracking-wider font-medium"
                                                    style={{
                                                        color: "var(--aegis-text-muted)",
                                                        gridTemplateColumns: "28px 1fr 180px 80px 80px 80px 100px",
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
                                                                gridTemplateColumns: "28px 1fr 180px 80px 80px 80px 100px",
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
                                                            <div className="flex items-center gap-1.5 min-w-0">
                                                                <span className="text-xs font-medium font-mono truncate" style={{ color: "var(--aegis-text)" }}>
                                                                    {child.name}
                                                                </span>
                                                            </div>

                                                            {/* Model */}
                                                            <div>
                                                                {child.model && (
                                                                    <span
                                                                        className="text-[10px] px-1.5 py-0.5 rounded whitespace-nowrap"
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
