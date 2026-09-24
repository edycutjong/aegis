"use client";

import { useState, useEffect } from "react";
import { Activity, ArrowUpRight, Database, LoaderCircle, ServerOff, Trash2 } from "lucide-react";
import type { Metrics, DbStatus } from "@/lib/api";
import { clearCache, getDbStatus, getTableData, getTracingStatus } from "@/lib/api";
import { shortModel } from "@/lib/trace";
import type { BackendState } from "./TopBar";
import AnimatedNumber from "./AnimatedNumber";

interface MetricsPanelProps {
    metrics: Metrics | null;
    backend: BackendState;
    onCacheCleared?: () => void;
    onOpenTraces?: () => void;
}

const TABLE_META: Record<string, { label: string; columns: string[] }> = {
    customers: { label: "Customers", columns: ["id", "name", "email", "plan", "status", "company"] },
    billing: { label: "Billing", columns: ["id", "customer_id", "amount", "type", "status", "description"] },
    support_tickets: { label: "Tickets", columns: ["id", "customer_id", "subject", "priority", "status", "category"] },
    internal_docs: { label: "Policy docs", columns: ["id", "title", "category"] },
};

/** Provider hue for the routing bar, keyed by model-name prefix. */
const PROVIDERS: Array<{ match: RegExp; label: string; color: string }> = [
    { match: /gemini/, label: "Google", color: "#7cadfb" },
    { match: /gpt-oss|llama/, label: "Groq", color: "#f0abfc" },
    { match: /^(gpt|o\d)/, label: "OpenAI", color: "#34d399" },
    { match: /claude/, label: "Anthropic", color: "#fdba74" },
];

function providerFor(model: string) {
    const name = shortModel(model);
    return PROVIDERS.find((p) => p.match.test(name)) ?? { label: "Other", color: "#94a3b8" };
}

function formatCompact(n: number): string {
    if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
    if (n >= 10_000) return (n / 1_000).toFixed(1) + "K";
    return Math.round(n).toLocaleString("en-US");
}

function truncate(val: unknown, max = 28): string {
    const s = String(val ?? "—");
    return s.length > max ? s.slice(0, max) + "…" : s;
}

function Stat({ label, children, hint }: { label: string; children: React.ReactNode; hint?: string }) {
    return (
        <div className="stat" title={hint}>
            <dt className="stat-label">{label}</dt>
            <dd className="stat-value tnum">{children}</dd>
        </div>
    );
}

export default function MetricsPanel({ metrics, backend, onCacheCleared, onOpenTraces }: MetricsPanelProps) {
    const agent = metrics?.agent_metrics;
    const cache = metrics?.cache_metrics;
    const [clearing, setClearing] = useState(false);
    const [clearMsg, setClearMsg] = useState<string | null>(null);
    const [tracingEnabled, setTracingEnabled] = useState(false);
    const [db, setDb] = useState<DbStatus | null>(null);
    const [expanded, setExpanded] = useState<string | null>(null);
    const [tableRows, setTableRows] = useState<Record<string, unknown>[]>([]);
    const [tableLoading, setTableLoading] = useState(false);

    useEffect(() => {
        getTracingStatus()
            .then((s) => setTracingEnabled(s.enabled))
            .catch(() => setTracingEnabled(false));
        getDbStatus().then(setDb).catch(() => { });
    }, []);

    const handleClearCache = async () => {
        setClearing(true);
        setClearMsg(null);
        try {
            const result = await clearCache();
            setClearMsg(`Cleared ${result.keys_deleted} keys`);
            onCacheCleared?.();
        } catch {
            setClearMsg("Couldn't clear");
        } finally {
            setClearing(false);
            setTimeout(() => setClearMsg(null), 2000);
        }
    };

    const handleTableClick = async (tableName: string) => {
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

    const models = Object.entries(agent?.model_distribution ?? {}).sort((a, b) => b[1] - a[1]);
    const modelTotal = models.reduce((sum, [, n]) => sum + n, 0);
    const expandedMeta = expanded ? TABLE_META[expanded] : null;

    return (
        <aside className="panel panel-metrics" aria-labelledby="metrics-heading">
            <div className="panel-head">
                <h2 id="metrics-heading" className="panel-title">Observability</h2>
                <span className="text-[12px] text-3">this server, live</span>
            </div>

            <div className="panel-body space-y-5">
                {metrics === null ? (
                    backend === "connecting" ? (
                        <div className="space-y-2" aria-label="Loading metrics">
                            <div className="skeleton h-[118px]" />
                            <div className="skeleton h-[72px]" />
                        </div>
                    ) : (
                        <div className="offline">
                            <ServerOff size={18} aria-hidden="true" className="text-3" />
                            <p className="text-[13px] font-medium text-2 mt-2">Telemetry offline</p>
                            <p className="text-[12px] text-3 leading-relaxed mt-1">
                                Cost, latency and routing stream in here once the agent API is reachable.
                            </p>
                        </div>
                    )
                ) : (
                    <>
                        <dl className="stat-grid">
                            <Stat label="Runs">
                                <AnimatedNumber value={agent?.total_requests || 0} format={(v) => formatCompact(v)} />
                            </Stat>
                            <Stat label="Avg wall time">
                                {agent?.avg_duration_seconds ? <AnimatedNumber value={agent.avg_duration_seconds} format={(v) => v.toFixed(1) + "s"} /> : "—"}
                            </Stat>
                            <Stat label="Tokens">
                                <AnimatedNumber value={agent?.total_tokens || 0} format={(v) => formatCompact(v)} />
                            </Stat>
                            <Stat label="Total LLM spend" hint="Measured from real token usage on this server since it started">
                                $<AnimatedNumber value={agent?.total_cost_usd || 0} format={(v) => v.toFixed(3)} />
                            </Stat>
                            <Stat label="Approved at gate">
                                {agent?.hitl_approval_rate != null ? <AnimatedNumber value={agent.hitl_approval_rate} format={(v) => Math.round(v) + "%"} /> : "—"}
                            </Stat>
                            <Stat label="Avg human wait">
                                {agent?.avg_hitl_wait_seconds != null ? <AnimatedNumber value={agent.avg_hitl_wait_seconds} format={(v) => v.toFixed(1) + "s"} /> : "—"}
                            </Stat>
                        </dl>

                        <div>
                            <h3 className="section-label">Model routing</h3>
                            {modelTotal > 0 ? (
                                <div className="mt-2">
                                    <div className="route-bar" role="img" aria-label={models.map(([m, n]) => `${shortModel(m)} ${Math.round((n / modelTotal) * 100)}%`).join(", ")}>
                                        {models.map(([m, n]) => (
                                            <span key={m} style={{ width: `${(n / modelTotal) * 100}%`, background: providerFor(m).color }} />
                                        ))}
                                    </div>
                                    <ul className="route-list">
                                        {models.map(([m, n]) => (
                                            <li key={m}>
                                                <span className="agent-dot" style={{ background: providerFor(m).color }} aria-hidden="true" />
                                                <span className="font-mono truncate">{shortModel(m)}</span>
                                                <span className="text-3 ml-auto shrink-0">{providerFor(m).label}</span>
                                                <span className="tnum w-9 text-right shrink-0">{Math.round((n / modelTotal) * 100)}%</span>
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            ) : (
                                <p className="text-[12px] text-3 mt-2">Run a ticket to see which model each step was routed to.</p>
                            )}
                        </div>

                        <div>
                            <div className="flex items-center justify-between">
                                <h3 className="section-label">Semantic cache</h3>
                                <div className="flex items-center gap-2">
                                    {clearMsg && <span className="text-[12px] text-2" role="status">{clearMsg}</span>}
                                    <button
                                        id="clear-cache-btn"
                                        type="button"
                                        onClick={handleClearCache}
                                        disabled={clearing || !cache?.connected}
                                        className="icon-btn"
                                        aria-label="Clear semantic cache"
                                        title="Clear cache"
                                    >
                                        {clearing ? <LoaderCircle size={14} className="animate-spin" aria-hidden="true" /> : <Trash2 size={14} aria-hidden="true" />}
                                    </button>
                                </div>
                            </div>
                            <div className="meter mt-2" role="img" aria-label={`Cache hit rate ${(cache?.hit_rate_percent || 0).toFixed(0)}%`}>
                                <span style={{ width: `${cache?.hit_rate_percent || 0}%` }} />
                            </div>
                            <div className="flex justify-between text-[12px] text-3 mt-1.5 tnum">
                                <span>
                                    <AnimatedNumber value={cache?.hit_rate_percent || 0} format={(v) => v.toFixed(0) + "% hit rate"} />
                                </span>
                                <span className="flex items-center gap-1.5">
                                    <span className={`w-1.5 h-1.5 rounded-full ${cache?.connected ? "bg-ok" : "bg-fail"}`} aria-hidden="true" />
                                    Redis {cache?.connected ? "connected" : "off"}
                                </span>
                            </div>
                        </div>
                    </>
                )}

                {db && (
                    <div>
                        <h3 className="section-label flex items-center gap-1.5">
                            <Database size={12} aria-hidden="true" /> Live database
                        </h3>
                        <div className="db-grid mt-2">
                            {Object.entries(TABLE_META).map(([key, meta]) => {
                                const table = db[key];
                                if (!table) return null;
                                return (
                                    <button
                                        key={key}
                                        type="button"
                                        onClick={() => handleTableClick(key)}
                                        className="db-cell"
                                        aria-expanded={expanded === key}
                                        aria-controls="db-preview"
                                    >
                                        <span className="text-[12px] text-2">{meta.label}</span>
                                        <span className="font-mono tnum text-[13px] text-1">{table.count}</span>
                                    </button>
                                );
                            })}
                        </div>
                        {expanded && expandedMeta && (
                            <div id="db-preview" className="db-preview">
                                {tableLoading ? (
                                    <p className="text-[12px] text-3 p-3 flex items-center gap-2">
                                        <LoaderCircle size={13} className="animate-spin" aria-hidden="true" /> Loading…
                                    </p>
                                ) : tableRows.length === 0 ? (
                                    <p className="text-[12px] text-3 p-3 text-center">No records</p>
                                ) : (
                                    <table>
                                        <caption className="sr-only">{expandedMeta.label} table preview</caption>
                                        <thead>
                                            <tr>
                                                {expandedMeta.columns.map((col) => (
                                                    <th key={col} scope="col">{col.replace(/_/g, " ")}</th>
                                                ))}
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {tableRows.map((row, i) => (
                                                <tr key={i}>
                                                    {expandedMeta.columns.map((col) => (
                                                        <td key={col} title={String(row[col] ?? "")}>
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

                {tracingEnabled && (
                    <button type="button" onClick={onOpenTraces} className="link-row">
                        <Activity size={14} aria-hidden="true" />
                        <span>LangSmith traces</span>
                        <ArrowUpRight size={14} aria-hidden="true" className="ml-auto" />
                    </button>
                )}
            </div>
        </aside>
    );
}
