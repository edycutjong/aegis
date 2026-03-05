"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import dynamic from "next/dynamic";
import ThoughtStream from "@/components/ThoughtStream";
import ApprovalModal from "@/components/ApprovalModal";
import MetricsPanel from "@/components/MetricsPanel";
const TicketHistory = dynamic(() => import("@/components/TicketHistory"), { ssr: false });
import { useTicketHistory } from "@/hooks/useTicketHistory";
import {
    startChat,
    connectSSE,
    approveAction,
    getMetrics,
    type ActionProposal,
    type Metrics,
    type ChatResponse,
    type CustomerCandidate,
} from "@/lib/api";

// Quick Test presets — real intents matching seed data, most common first
const REAL_INTENTS = [
    {
        label: "Refund",
        icon: "💳",
        message: "Customer #8 David Martinez says he was charged $49 twice this month for his Pro plan. Please investigate and process a refund if confirmed.",
    },
    {
        label: "Technical",
        icon: "🔧",
        message: "Customer #3 Maria Garcia reports getting 429 API rate limiting errors. Their enterprise plan should support 10K requests/min but they're hitting limits at 5K.",
    },
    {
        label: "Billing",
        icon: "📄",
        message: "Customer #1 Sarah Chen asks if there's a discount for switching from monthly to annual billing on her Enterprise plan.",
    },
    {
        label: "Upgrade",
        icon: "⬆️",
        message: "Customer #17 Sophia Lewis wants to upgrade from the Free plan to Pro. She wants to know if she'll lose any existing data during the upgrade.",
    },
    {
        label: "Reactivate",
        icon: "🔓",
        message: "Customer #5 Emily Davis reports her enterprise account was suspended after a failed payment. She has updated her payment method and needs reactivation.",
    },
    {
        label: "Suspend",
        icon: "🔒",
        message: "Customer #20 William Allen has violated our terms of service by sharing his API keys publicly. Please suspend his account immediately.",
    },
];

// Edge Case presets — validation and error scenarios
const EDGE_CASES = [
    {
        label: "Not Found",
        icon: "👻",
        message: "Customer #999 John Phantom wants a refund for the duplicate $49 charge on their Pro subscription from 2 days ago.",
    },
    {
        label: "Mismatch",
        icon: "🔀",
        message: "Customer #8 Sarah Chen says she was charged $49 twice this month for her Pro plan. Please investigate.",
    },
    {
        label: "Typo",
        icon: "✍️",
        message: "Customer #8 Davd Martines says he was charged $49 twice this month for his Pro plan. Please investigate and resolve.",
    },
    {
        label: "Name Only",
        icon: "👤",
        message: "Emily Davis reports her enterprise account was suspended after a failed payment. She has updated her payment method and needs reactivation.",
    },
    {
        label: "Cancelled",
        icon: "🚫",
        message: "Customer #20 William Allen wants to know why his account was cancelled. He says he never requested cancellation and needs access restored.",
    },
];

export default function Dashboard() {
    // Core state
    const [message, setMessage] = useState("");
    const [threadId, setThreadId] = useState<string | null>(null);
    const [thoughts, setThoughts] = useState<string[]>([]);
    const [status, setStatus] = useState<string>("idle");
    const [finalResponse, setFinalResponse] = useState<string | null>(null);

    // HITL state
    const [pendingAction, setPendingAction] = useState<ActionProposal | null>(null);

    const [approvalLoading, setApprovalLoading] = useState(false);

    // Metrics state
    const [metrics, setMetrics] = useState<Metrics | null>(null);

    // Disambiguation state
    const [candidates, setCandidates] = useState<CustomerCandidate[]>([]);
    const [disambiguationMessage, setDisambiguationMessage] = useState<string | null>(null);
    const [originalMessage, setOriginalMessage] = useState<string>("");

    // Tab state for demo presets
    const [activeTab, setActiveTab] = useState<"intents" | "edge">("intents");

    // Ticket history
    const { entries: historyEntries, addEntry: addHistoryEntry, clearHistory } = useTicketHistory();
    const lastRecordedStatus = useRef<string>("idle");

    // Fetch metrics periodically
    useEffect(() => {
        const fetchMetrics = async () => {
            try {
                const m = await getMetrics();
                setMetrics(m);
            } catch {
                // Backend not available yet
            }
        };
        fetchMetrics();
        const interval = setInterval(fetchMetrics, 5000);
        return () => clearInterval(interval);
    }, []);

    // Record ticket to history when status transitions to completed/error
    useEffect(() => {
        if (
            (status === "completed" || status === "error") &&
            lastRecordedStatus.current !== status &&
            originalMessage.trim()
        ) {
            const preview =
                status === "completed" && finalResponse
                    ? finalResponse.slice(0, 100)
                    : status === "error" && thoughts.length > 0
                        ? thoughts[thoughts.length - 1].slice(0, 100)
                        : /* v8 ignore next */ "";
            addHistoryEntry({
                message: originalMessage,
                status: status as "completed" | "error",
                responsePreview: preview,
            });
        }
        lastRecordedStatus.current = status;
    }, [status, originalMessage, finalResponse, thoughts, addHistoryEntry]);

    // Submit a support ticket
    const handleSubmit = useCallback(async (msg?: string) => {
        const ticketMessage = msg || message;
        if (!ticketMessage.trim()) return;

        setThoughts([]);
        setFinalResponse(null);
        setPendingAction(null);
        setCandidates([]);
        setDisambiguationMessage(null);
        setOriginalMessage(ticketMessage);
        setStatus("processing");

        try {
            const res: ChatResponse = await startChat(ticketMessage);
            setThreadId(res.thread_id);

            if (res.cache_hit) {
                setStatus("cached");
                setThoughts(["⚡ Response served from semantic cache (cost: $0.00)"]);
                setFinalResponse("Cached response — identical query was processed recently.");
                return;
            }

            // Connect SSE to stream agent thoughts
            connectSSE(
                res.thread_id,
                (step) => setThoughts((prev) => [...prev, step]),
                (action) => {
                    setPendingAction(action);
                    setStatus("awaiting_approval");
                },
                (response, thoughtLog) => {
                    setThoughts(thoughtLog);
                    setFinalResponse(response);
                    setStatus("completed");
                },
                (error) => {
                    setThoughts((prev) => [...prev, `✗ Error: ${error}`]);
                    setStatus("error");
                },
                (customerCandidates, response) => {
                    setCandidates(customerCandidates);
                    setDisambiguationMessage(response);
                    setStatus("disambiguation");
                }
            );
        } catch (err) {
            setStatus("error");
            setThoughts(["✗ Failed to connect to Aegis backend. Is it running on port 8000?"]);
        }
    }, [message]);

    // Handle HITL approval
    const handleApprove = useCallback(async () => {
        /* v8 ignore start: threadId is always set before approval UI shows */
        if (!threadId) return;
        /* v8 ignore stop */
        setApprovalLoading(true);
        try {
            const res = await approveAction(threadId, true);
            setThoughts((prev) => [...prev, "✓ Action approved by human manager"]);
            setFinalResponse(res.result || "Action executed successfully.");
            setPendingAction(null);
            setStatus("completed");
        } catch (err) {
            setThoughts((prev) => [...prev, "✗ Approval failed"]);
        }
        setApprovalLoading(false);
    }, [threadId]);

    // Handle HITL denial
    const handleDeny = useCallback(async (reason: string) => {
        /* v8 ignore start: threadId is always set before approval UI shows */
        if (!threadId) return;
        /* v8 ignore stop */
        setApprovalLoading(true);
        try {
            const res = await approveAction(threadId, false, reason);
            setThoughts((prev) => [...prev, `✗ Action denied: ${reason}`]);
            setFinalResponse(res.result || "Action denied. No changes were made.");
            setPendingAction(null);
            setStatus("completed");
        } catch (err) {
            setThoughts((prev) => [...prev, "✗ Denial submission failed"]);
        }
        setApprovalLoading(false);
    }, [threadId]);



    // Handle customer disambiguation selection
    const handleSelectCustomer = useCallback((candidate: CustomerCandidate) => {
        // Replace any Customer #ID in the original message with the selected one
        const correctedMessage = originalMessage.replace(
            /[Cc]ustomer\s*#?\d+\s*[A-Za-z ]*/,
            `Customer #${candidate.id} ${candidate.name}`
        );
        setCandidates([]);
        setDisambiguationMessage(null);
        setMessage(correctedMessage);
        handleSubmit(correctedMessage);
    }, [originalMessage, handleSubmit]);

    return (
        <div className="h-screen flex flex-col overflow-hidden" style={{ background: "var(--aegis-bg)" }}>
            {/* ── Top Navigation ── */}
            <nav className="flex items-center justify-between px-6 py-4" style={{ borderBottom: "1px solid var(--aegis-border)" }}>
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: "linear-gradient(135deg, #1e3a5f, #3b82f6)" }}>
                        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" fill="rgba(59,130,246,0.2)" />
                            <path d="M9 11.5l2.5 2.5 4-4.5" />
                        </svg>
                    </div>
                    <div>
                        <h1 className="text-lg font-bold tracking-tight" style={{ color: "var(--aegis-text)" }}>Aegis</h1>
                        <p className="text-xs" style={{ color: "var(--aegis-text-muted)" }}>Autonomous Enterprise Action Engine</p>
                    </div>
                </div>
                <div className="flex items-center gap-4">
                    <div className="flex items-center gap-2">
                        <div className="w-2 h-2 rounded-full bg-emerald-400" />
                        <span className="text-xs font-medium" style={{ color: "var(--aegis-text-muted)" }}>System Online</span>
                    </div>
                </div>
            </nav>

            {/* ── Status Bar ── */}
            <div className="status-bar">
                <div className={`status-bar-fill ${status}`} />
            </div>

            {/* ── Main Dashboard ── */}
            <div className="flex-1 min-h-0 p-4 grid gap-4 dashboard-grid">

                {/* Left Panel: Ticket Submission */}
                <div className="glass-panel p-6 h-full min-h-0 flex flex-col">
                    <div className="flex items-center gap-3 mb-5">
                        <div className="w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#4ade80" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                            </svg>
                        </div>
                        <h2 className="text-sm font-semibold tracking-wide uppercase" style={{ color: "var(--aegis-text-muted)" }}>
                            Support Ticket
                        </h2>
                    </div>

                    {/* Scrollable content */}
                    <div className="flex-1 overflow-y-auto space-y-4">
                        {/* Demo Presets — Tabbed */}
                        <div>
                            <div className="flex gap-1 mb-3">
                                <button
                                    onClick={() => setActiveTab("intents")}
                                    className="text-xs font-semibold px-3 py-1.5 rounded-lg transition-all"
                                    style={{
                                        background: activeTab === "intents" ? "rgba(59,130,246,0.15)" : "transparent",
                                        color: activeTab === "intents" ? "#60a5fa" : "var(--aegis-text-muted)",
                                        border: activeTab === "intents" ? "1px solid rgba(59,130,246,0.3)" : "1px solid transparent",
                                    }}
                                >
                                    Quick Test
                                </button>
                                <button
                                    onClick={() => setActiveTab("edge")}
                                    className="text-xs font-semibold px-3 py-1.5 rounded-lg transition-all"
                                    style={{
                                        background: activeTab === "edge" ? "rgba(245,158,11,0.15)" : "transparent",
                                        color: activeTab === "edge" ? "#fbbf24" : "var(--aegis-text-muted)",
                                        border: activeTab === "edge" ? "1px solid rgba(245,158,11,0.3)" : "1px solid transparent",
                                    }}
                                >
                                    Edge Cases
                                </button>
                            </div>
                            <div className="flex flex-wrap gap-2">
                                {(activeTab === "intents" ? REAL_INTENTS : EDGE_CASES).map((t, i) => (
                                    <button
                                        key={`${activeTab}-${i}`}
                                        onClick={() => {
                                            setMessage(t.message);
                                            handleSubmit(t.message);
                                        }}
                                        disabled={status === "processing"}
                                        className="demo-btn"
                                    >
                                        <span>{t.icon}</span>
                                        {t.label}
                                    </button>
                                ))}
                            </div>
                        </div>

                        <TicketHistory
                            entries={historyEntries}
                            onSelect={setMessage}
                            onClear={clearHistory}
                        />

                        {/* Disambiguation Selector */}
                        {candidates.length > 0 && (
                            <div className="response-card">
                                <div className="flex items-center gap-2 mb-3">
                                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#f59e0b" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                                        <circle cx="12" cy="12" r="10" />
                                        <path d="M12 16v-4" />
                                        <path d="M12 8h.01" />
                                    </svg>
                                    <span className="text-xs font-bold uppercase tracking-wider" style={{ color: "#f59e0b" }}>Select Customer</span>
                                </div>
                                <p className="text-sm mb-3" style={{ color: "var(--aegis-text-muted)" }}>{disambiguationMessage}</p>
                                <div className="space-y-2">
                                    {candidates.map((c) => (
                                        <button
                                            key={c.id}
                                            onClick={() => handleSelectCustomer(c)}
                                            className="w-full text-left rounded-lg p-3 transition-all hover:brightness-125"
                                            style={{
                                                background: "var(--aegis-surface)",
                                                border: "1px solid var(--aegis-border)",
                                            }}
                                        >
                                            <div className="flex items-center justify-between">
                                                <div>
                                                    <span className="text-sm font-semibold" style={{ color: "var(--aegis-text)" }}>#{c.id} {c.name}</span>
                                                    {c.email && <span className="text-xs ml-2" style={{ color: "var(--aegis-text-muted)" }}>{c.email}</span>}
                                                </div>
                                                <div className="flex items-center gap-2">
                                                    {c.plan && <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: "rgba(59,130,246,0.15)", color: "#60a5fa" }}>{c.plan}</span>}
                                                    {c.status && c.status !== "active" && (
                                                        <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: "rgba(239,68,68,0.15)", color: "#f87171" }}>{c.status}</span>
                                                    )}
                                                </div>
                                            </div>
                                        </button>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Final Response */}
                        {finalResponse && (
                            <div className="response-card">
                                <div className="flex items-center gap-2 mb-3">
                                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#4ade80" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                                        <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                                        <path d="M22 4L12 14.01l-3-3" />
                                    </svg>
                                    <span className="text-xs font-bold uppercase tracking-wider" style={{ color: "#4ade80" }}>Resolution Complete</span>
                                </div>
                                <p className="text-sm leading-relaxed" style={{ color: "var(--aegis-text)" }}>{finalResponse}</p>
                            </div>
                        )}

                        {/* Textarea + Submit */}
                        <div className="pt-2">
                            <textarea
                                value={message}
                                onChange={(e) => setMessage(e.target.value)}
                                onKeyDown={(e) => {
                                    if (e.key === "Enter" && !e.shiftKey) {
                                        e.preventDefault();
                                        handleSubmit();
                                    }
                                }}
                                placeholder="Describe the support issue... e.g. 'Customer #8 says they were double-charged $49 for their Pro plan'"
                                disabled={status === "processing"}
                                className="w-full rounded-xl p-4 text-sm leading-relaxed resize-none outline-none transition-all focus:border-blue-500/30 disabled:opacity-50"
                                style={{
                                    background: "var(--aegis-surface)",
                                    border: "1px solid var(--aegis-border)",
                                    color: "var(--aegis-text)",
                                    fontFamily: "var(--font-sans)",
                                    minHeight: "100px",
                                }}
                            />
                            <button
                                onClick={() => handleSubmit()}
                                disabled={!message.trim() || status === "processing"}
                                className="btn-primary mt-3 w-full flex items-center justify-center gap-2 disabled:opacity-40"
                            >
                                {status === "processing" ? (
                                    <>
                                        <div className="spinner" />
                                        Agent Processing...
                                    </>
                                ) : (
                                    <>
                                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                                            <path d="M22 2L11 13" /><path d="M22 2l-7 20-4-9-9-4 20-7z" />
                                        </svg>
                                        Submit Ticket
                                    </>
                                )}
                            </button>
                        </div>
                    </div>
                </div>

                {/* Center Panel: Thought Stream */}
                <ThoughtStream thoughts={thoughts} status={status} />

                {/* Right Panel: Metrics */}
                <MetricsPanel metrics={metrics} onCacheCleared={async () => {
                    try { setMetrics(await getMetrics()); } catch { }
                }} />
            </div>

            {/* ── Footer ── */}
            <footer className="px-6 py-4 flex items-center justify-between text-xs shrink-0" style={{ borderTop: "1px solid var(--aegis-border)", color: "var(--aegis-text-muted)" }}>
                <span>Aegis v{require("../../package.json").version} — Autonomous Enterprise Action Engine</span>
                <div className="flex items-center gap-4">

                    <span title={threadId ? `Thread: ${threadId}` : undefined}>FastAPI + LangGraph + Next.js</span>
                </div>
            </footer>

            {/* ── HITL Approval Modal ── */}
            {pendingAction && (
                <ApprovalModal
                    action={pendingAction}
                    onApprove={handleApprove}
                    onDeny={handleDeny}

                    isLoading={approvalLoading}
                />
            )}
        </div>
    );
}
