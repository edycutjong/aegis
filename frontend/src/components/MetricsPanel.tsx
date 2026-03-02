"use client";

import type { Metrics } from "@/lib/api";

interface MetricsPanelProps {
    metrics: Metrics | null;
}

export default function MetricsPanel({ metrics }: MetricsPanelProps) {
    const agent = metrics?.agent_metrics;
    const cache = metrics?.cache_metrics;

    // Calculate model distribution percentages
    const modelTotal = agent?.model_distribution
        ? Object.values(agent.model_distribution).reduce((a, b) => a + b, 0)
        : 0;

    return (
        <div className="glass-panel p-6 h-full flex flex-col">
            {/* Header */}
            <div className="flex items-center gap-3 mb-5">
                <div className="w-8 h-8 rounded-lg bg-purple-500/10 flex items-center justify-center">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#a78bfa" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M18 20V10" /><path d="M12 20V4" /><path d="M6 20v-6" />
                    </svg>
                </div>
                <h2 className="text-sm font-semibold tracking-wide uppercase" style={{ color: "var(--aegis-text-muted)" }}>
                    Observability
                </h2>
            </div>

            <div className="flex-1 overflow-y-auto space-y-4">
                {/* Primary Metrics */}
                <div className="grid grid-cols-2 gap-3">
                    <div className="metric-card">
                        <span className="text-xs block mb-1" style={{ color: "var(--aegis-text-muted)" }}>Avg Cost/Request</span>
                        <span className="text-xl font-bold text-emerald-400">
                            ${agent?.avg_cost_usd?.toFixed(4) || "0.0000"}
                        </span>
                    </div>
                    <div className="metric-card">
                        <span className="text-xs block mb-1" style={{ color: "var(--aegis-text-muted)" }}>Total Requests</span>
                        <span className="text-xl font-bold text-blue-400">
                            {agent?.total_requests || 0}
                        </span>
                    </div>
                    <div className="metric-card">
                        <span className="text-xs block mb-1" style={{ color: "var(--aegis-text-muted)" }}>Total Cost</span>
                        <span className="text-xl font-bold text-amber-400">
                            ${agent?.total_cost_usd?.toFixed(4) || "0.0000"}
                        </span>
                    </div>
                    <div className="metric-card">
                        <span className="text-xs block mb-1" style={{ color: "var(--aegis-text-muted)" }}>Total Tokens</span>
                        <span className="text-xl font-bold text-purple-400">
                            {agent?.total_tokens?.toLocaleString() || "0"}
                        </span>
                    </div>
                </div>

                {/* Cache Stats */}
                <div className="space-y-2">
                    <h3 className="text-xs font-semibold uppercase tracking-wider" style={{ color: "var(--aegis-text-muted)" }}>
                        Semantic Cache
                    </h3>
                    <div className="metric-card">
                        <div className="flex items-center justify-between mb-2">
                            <span className="text-xs" style={{ color: "var(--aegis-text-muted)" }}>Hit Rate</span>
                            <span className="text-sm font-bold" style={{ color: (cache?.hit_rate_percent || 0) > 50 ? "#4ade80" : "#60a5fa" }}>
                                {cache?.hit_rate_percent?.toFixed(1) || "0.0"}%
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
                                {cache?.hits || 0} hits
                            </span>
                            <span className="text-xs" style={{ color: "var(--aegis-text-muted)" }}>
                                {cache?.misses || 0} misses
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
                {agent?.model_distribution && modelTotal > 0 && (
                    <div className="space-y-2">
                        <h3 className="text-xs font-semibold uppercase tracking-wider" style={{ color: "var(--aegis-text-muted)" }}>
                            Model Usage
                        </h3>
                        <div className="space-y-2">
                            {Object.entries(agent.model_distribution).map(([model, count]) => {
                                const pct = ((count / modelTotal) * 100).toFixed(0);
                                const isExpensive = model.includes("gpt-4o") || model.includes("claude") || model.includes("pro");
                                return (
                                    <div key={model} className="metric-card py-2 px-3">
                                        <div className="flex items-center justify-between mb-1">
                                            <span className="text-xs font-mono truncate" style={{ color: "var(--aegis-text)" }}>
                                                {model}
                                            </span>
                                            <span className="text-xs font-semibold ml-2" style={{ color: isExpensive ? "#fbbf24" : "#4ade80" }}>
                                                {pct}%
                                            </span>
                                        </div>
                                        <div className="w-full h-1.5 rounded-full" style={{ background: "var(--aegis-border)" }}>
                                            <div
                                                className="h-full rounded-full transition-all duration-500"
                                                style={{
                                                    width: `${pct}%`,
                                                    background: isExpensive
                                                        ? "linear-gradient(90deg, #f59e0b, #ef4444)"
                                                        : "linear-gradient(90deg, #22c55e, #3b82f6)",
                                                }}
                                            />
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    </div>
                )}

                {/* Avg Duration */}
                <div className="metric-card">
                    <span className="text-xs block mb-1" style={{ color: "var(--aegis-text-muted)" }}>Avg Duration</span>
                    <span className="text-lg font-bold" style={{ color: "var(--aegis-text)" }}>
                        {agent?.avg_duration_seconds?.toFixed(1) || "0.0"}s
                    </span>
                </div>
            </div>
        </div>
    );
}
