"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import dynamic from "next/dynamic";
import ThoughtStream from "@/components/ThoughtStream";
import ApprovalModal from "@/components/ApprovalModal";
import MetricsPanel from "@/components/MetricsPanel";
import TracesPanel from "@/components/TracesPanel";
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
        message: "Customer #8 David Martinez says he was charged $49 twice this month for his Pro plan. Please investigate and process a refund if confirmed.",
    },
    {
        label: "Technical",
        message: "Customer #3 Maria Garcia reports getting 429 API rate limiting errors. Their enterprise plan should support 10K requests/min but they're hitting limits at 5K.",
    },
    {
        label: "Billing",
        message: "Customer #1 Sarah Chen asks if there's a discount for switching from monthly to annual billing on her Enterprise plan.",
    },
    {
        label: "Upgrade",
        message: "Customer #17 Sophia Lewis wants to upgrade from the Free plan to Pro. She wants to know if she'll lose any existing data during the upgrade.",
    },
    {
        label: "Reactivate",
        message: "Customer #5 Emily Davis reports her enterprise account was suspended after a failed payment. She has updated her payment method and needs reactivation.",
    },
    {
        label: "Suspend",
        message: "Customer #20 William Allen has violated our terms of service by sharing his API keys publicly. Please suspend his account immediately.",
    },
];

// Edge Case presets — validation and error scenarios
const EDGE_CASES = [
    {
        label: "Not Found",
        message: "Customer #999 John Phantom wants a refund for the duplicate $49 charge on their Pro subscription from 2 days ago.",
    },
    {
        label: "Mismatch",
        message: "Customer #8 Sarah Chen says she was charged $49 twice this month for her Pro plan. Please investigate.",
    },
    {
        label: "Typo",
        message: "Customer #8 Davd Martines says he was charged $49 twice this month for his Pro plan. Please investigate and resolve.",
    },
    {
        label: "Name Only",
        message: "Emily Davis reports her enterprise account was suspended after a failed payment. She has updated her payment method and needs reactivation.",
    },
    {
        label: "Cancelled",
        message: "Customer #20 William Allen wants to know why his account was cancelled. He says he never requested cancellation and needs access restored.",
    },
];

/** Brand mark: the payload arrested at the bar — blue runs, amber holds. */
function RailMark() {
    return (
        <svg width="36" height="36" viewBox="0 0 36 36" fill="none" aria-hidden="true">
            <rect x="0.5" y="0.5" width="35" height="35" rx="8.5" fill="var(--aegis-surface-2)" stroke="var(--aegis-border-strong)" />
            <line x1="7" y1="18" x2="29" y2="18" stroke="var(--aegis-border-strong)" strokeWidth="1.5" />
            <line x1="9" y1="18" x2="18" y2="18" stroke="#3b82f6" strokeWidth="2" strokeLinecap="round" />
            <circle cx="19" cy="18" r="3.2" fill="#3b82f6" />
            <rect x="24" y="10.5" width="2.5" height="15" rx="1.25" fill="#f59e0b" />
        </svg>
    );
}

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
    // Backend reachability: null = first probe in flight, then true/false
    const [backendUp, setBackendUp] = useState<boolean | null>(null);

    // Disambiguation state
    const [candidates, setCandidates] = useState<CustomerCandidate[]>([]);
    const [disambiguationMessage, setDisambiguationMessage] = useState<string | null>(null);
    const [originalMessage, setOriginalMessage] = useState<string>("");

    // Tab state for demo presets
    const [activeTab, setActiveTab] = useState<"intents" | "edge">("intents");

    // Traces overlay
    const [tracesOpen, setTracesOpen] = useState(false);

    // Ticket history
    const { entries: historyEntries, addEntry: addHistoryEntry, clearHistory } = useTicketHistory();
    const lastRecordedStatus = useRef<string>("idle");

    // Fetch metrics periodically
    useEffect(() => {
        const fetchMetrics = async () => {
            try {
                const m = await getMetrics();
                setMetrics(m);
                setBackendUp(true);
            } catch {
                setBackendUp(false);
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
        } catch {
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
        } catch {
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
        } catch {
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

    const backendStatus = backendUp === null
        ? { label: "Connecting", color: "var(--aegis-text-muted)", pulse: true }
        : backendUp
            ? { label: "Operational", color: "var(--aegis-success)", pulse: false }
            : { label: "Backend Offline", color: "var(--aegis-danger)", pulse: false };

    return (
        <div className="app-root">
            {/* ── Top Navigation ── */}
            <nav className="flex items-center justify-between px-4 sm:px-5 py-3 shrink-0" style={{ borderBottom: "1px solid var(--aegis-border)" }}>
                <div className="flex items-center gap-3 min-w-0">
                    <RailMark />
                    <div className="min-w-0">
                        <div className="flex items-baseline gap-2.5">
                            <h1 className="text-base font-bold tracking-tight leading-tight" style={{ color: "var(--aegis-text)" }}>Aegis</h1>
                            <span className="hidden sm:inline text-[11px] font-medium truncate" style={{ color: "var(--aegis-text-muted)" }}>
                                Autonomous Enterprise Action Engine
                            </span>
                        </div>
                        <p className="hidden sm:block text-[11px] leading-tight truncate" style={{ color: "var(--aegis-text-muted)" }}>
                            AI works the queue — humans hold the pen
                        </p>
                    </div>
                </div>
                <div
                    className="flex items-center gap-2 px-2.5 py-1 rounded-full shrink-0"
                    style={{ border: "1px solid var(--aegis-border)", background: "var(--aegis-surface)" }}
                >
                    <span
                        className={`w-1.5 h-1.5 rounded-full ${backendStatus.pulse ? "animate-pulse" : ""}`}
                        style={{ background: backendStatus.color }}
                    />
                    <span className="text-[11px] font-medium whitespace-nowrap" style={{ color: "var(--aegis-text-2)" }}>
                        {backendStatus.label}
                    </span>
                </div>
            </nav>

            {/* ── The rail: blue while moving, locked amber when arrested ── */}
            <div className="status-bar">
                <div className={`status-bar-fill ${status}`} />
            </div>

            {/* ── Main Dashboard ── */}
            <div className="dashboard-grid">

                {/* Left Panel: Ticket Submission */}
                <div className="glass-panel min-h-0 flex flex-col overflow-hidden animate-slide-up-fade" style={{ animationDelay: "0.05s" }}>
                    <div className="panel-header">
                        <h2 className="panel-title">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                            </svg>
                            Support Ticket
                        </h2>
                    </div>

                    {/* Scrollable content */}
                    <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4" style={{ scrollbarGutter: "stable" }}>
                        {/* Demo Presets — Tabbed */}
                        <div>
                            <div className="flex gap-1 mb-2.5">
                                <button
                                    onClick={() => setActiveTab("intents")}
                                    className={`preset-tab ${activeTab === "intents" ? "active-release" : ""}`}
                                >
                                    Quick Test
                                </button>
                                <button
                                    onClick={() => setActiveTab("edge")}
                                    className={`preset-tab ${activeTab === "edge" ? "active-hold" : ""}`}
                                >
                                    Edge Cases
                                </button>
                            </div>
                            <div className="flex flex-wrap gap-1.5">
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

                        {/* Disambiguation Selector — the run is held for a human choice */}
                        {candidates.length > 0 && (
                            <div className="response-card hold-card">
                                <div className="flex items-center gap-2 mb-2.5">
                                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="var(--hold-text)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                                        <circle cx="12" cy="12" r="10" />
                                        <path d="M12 16v-4" />
                                        <path d="M12 8h.01" />
                                    </svg>
                                    <span className="text-[11px] font-bold uppercase tracking-wider" style={{ color: "var(--hold-text)" }}>Select Customer</span>
                                </div>
                                <p className="text-[13px] mb-3" style={{ color: "var(--aegis-text-2)" }}>{disambiguationMessage}</p>
                                <div className="space-y-1.5">
                                    {candidates.map((c) => (
                                        <button
                                            key={c.id}
                                            onClick={() => handleSelectCustomer(c)}
                                            className="w-full text-left rounded-lg px-3 py-2.5 transition-colors"
                                            style={{
                                                background: "var(--aegis-surface)",
                                                border: "1px solid var(--aegis-border-strong)",
                                            }}
                                        >
                                            <div className="flex items-center justify-between gap-2">
                                                <div className="min-w-0">
                                                    <span className="text-[13px] font-semibold" style={{ color: "var(--aegis-text)" }}>#{c.id} {c.name}</span>
                                                    {c.email && <span className="text-xs ml-2" style={{ color: "var(--aegis-text-muted)" }}>{c.email}</span>}
                                                </div>
                                                <div className="flex items-center gap-1.5 shrink-0">
                                                    {c.plan && <span className="text-[11px] px-2 py-0.5 rounded-full" style={{ background: "rgba(59,130,246,0.14)", color: "var(--release-text)" }}>{c.plan}</span>}
                                                    {c.status && c.status !== "active" && (
                                                        <span className="text-[11px] px-2 py-0.5 rounded-full" style={{ background: "rgba(248,113,113,0.12)", color: "var(--aegis-danger)" }}>{c.status}</span>
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
                                <div className="flex items-center gap-2 mb-2.5">
                                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="var(--aegis-success)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                                        <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                                        <path d="M22 4L12 14.01l-3-3" />
                                    </svg>
                                    <span className="text-[11px] font-bold uppercase tracking-wider" style={{ color: "var(--aegis-success)" }}>Resolution Complete</span>
                                </div>
                                <p className="text-[13px] leading-relaxed" style={{ color: "var(--aegis-text)" }}>{finalResponse}</p>
                            </div>
                        )}

                        {/* Textarea + Submit */}
                        <div className="pt-1">
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
                                className="ticket-input"
                                aria-label="Support ticket description"
                            />
                            <button
                                onClick={() => handleSubmit()}
                                disabled={!message.trim() || status === "processing"}
                                className="btn-primary mt-2.5 w-full flex items-center justify-center gap-2 disabled:opacity-40"
                            >
                                {status === "processing" ? (
                                    <>
                                        <div className="spinner" />
                                        Agent Processing...
                                    </>
                                ) : (
                                    <>
                                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
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
                <div className="panel-stream min-h-0 animate-slide-up-fade" style={{ animationDelay: "0.1s" }}>
                    <ThoughtStream thoughts={thoughts} status={status} />
                </div>

                {/* Right Panel: Metrics */}
                <div className="panel-metrics min-h-0 flex flex-col animate-slide-up-fade" style={{ animationDelay: "0.15s" }}>
                    <MetricsPanel metrics={metrics} onCacheCleared={async () => {
                        try { setMetrics(await getMetrics()); } catch { }
                    }} onOpenTraces={() => setTracesOpen(true)} />
                </div>
            </div>

            {/* ── Footer ── */}
            <footer className="px-4 sm:px-5 py-3 flex items-center justify-between gap-3 text-[11px] shrink-0" style={{ borderTop: "1px solid var(--aegis-border)", color: "var(--aegis-text-muted)" }}>
                <span className="truncate">Aegis v{require("../../package.json").version} — Autonomous Enterprise Action Engine</span>
                <span className="font-mono whitespace-nowrap" title={threadId ? `Thread: ${threadId}` : undefined}>
                    FastAPI + LangGraph + Next.js
                </span>
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

            {/* ── Traces Overlay ── */}
            <TracesPanel open={tracesOpen} onClose={() => setTracesOpen(false)} />
        </div>
    );
}
