"use client";

import { useState, useCallback, useEffect } from "react";
import ThoughtStream from "@/components/ThoughtStream";
import ApprovalModal from "@/components/ApprovalModal";
import MetricsPanel from "@/components/MetricsPanel";
import {
    startChat,
    connectSSE,
    approveAction,
    getMetrics,
    type ActionProposal,
    type Metrics,
    type ChatResponse,
} from "@/lib/api";

// Demo ticket presets for quick testing
const DEMO_TICKETS = [
    {
        label: "Double Charge",
        icon: "💳",
        message: "Customer #8 David Martinez says he was charged $49 twice this month for his Pro plan. Please investigate and resolve.",
    },
    {
        label: "Account Suspended",
        icon: "🔒",
        message: "Customer #5 Emily Davis reports her enterprise account was suspended after a failed payment. She has updated her payment method and needs reactivation.",
    },
    {
        label: "API Rate Limit",
        icon: "⚡",
        message: "Customer #3 Maria Garcia from DataForge Analytics is hitting API rate limits at 5000 requests per minute. Their enterprise plan should support 10000. Can you investigate?",
    },
    {
        label: "Refund Request",
        icon: "💰",
        message: "Customer #10 Chris Johnson wants a refund for the duplicate $49 charge on their Pro subscription from 2 days ago.",
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
    const [heldAction, setHeldAction] = useState<ActionProposal | null>(null);
    const [approvalLoading, setApprovalLoading] = useState(false);

    // Metrics state
    const [metrics, setMetrics] = useState<Metrics | null>(null);

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

    // Submit a support ticket
    const handleSubmit = useCallback(async (msg?: string) => {
        const ticketMessage = msg || message;
        if (!ticketMessage.trim()) return;

        setThoughts([]);
        setFinalResponse(null);
        setPendingAction(null);
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
                }
            );
        } catch (err) {
            setStatus("error");
            setThoughts(["✗ Failed to connect to Aegis backend. Is it running on port 8000?"]);
        }
    }, [message]);

    // Handle HITL approval
    const handleApprove = useCallback(async () => {
        if (!threadId) return;
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
        if (!threadId) return;
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

    // Handle HITL hold (defer decision)
    const handleHold = useCallback(() => {
        setHeldAction(pendingAction);
        setPendingAction(null);
        setStatus("on_hold");
        setThoughts((prev) => [...prev, "⏸ Decision deferred — action held for review"]);
    }, [pendingAction]);

    // Resume a held action
    const handleResume = useCallback(() => {
        if (heldAction) {
            setPendingAction(heldAction);
            setHeldAction(null);
            setStatus("awaiting_approval");
            setThoughts((prev) => [...prev, "Resuming review of held action"]);
        }
    }, [heldAction]);

    return (
        <div className="min-h-screen flex flex-col" style={{ background: "var(--aegis-bg)" }}>
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
            <div className="flex-1 p-4 grid gap-4" style={{ gridTemplateColumns: "1fr 1.2fr 320px", gridTemplateRows: "1fr auto" }}>

                {/* Left Panel: Ticket Submission */}
                <div className="glass-panel p-6 flex flex-col">
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

                    {/* Demo Presets */}
                    <div className="mb-4">
                        <span className="text-xs font-medium mb-2 block" style={{ color: "var(--aegis-text-muted)" }}>Quick Test:</span>
                        <div className="flex flex-wrap gap-2">
                            {DEMO_TICKETS.map((t, i) => (
                                <button
                                    key={i}
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

                    {/* Text Input */}
                    <div className="flex-1 flex flex-col">
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
                            className="flex-1 w-full rounded-xl p-4 text-sm leading-relaxed resize-none outline-none transition-all focus:border-blue-500/30 disabled:opacity-50"
                            style={{
                                background: "var(--aegis-surface)",
                                border: "1px solid var(--aegis-border)",
                                color: "var(--aegis-text)",
                                fontFamily: "var(--font-sans)",
                                minHeight: "120px",
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

                    {/* Final Response */}
                    {finalResponse && (
                        <div className="response-card mt-4">
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
                </div>

                {/* Center Panel: Thought Stream */}
                <ThoughtStream thoughts={thoughts} status={status} />

                {/* Right Panel: Metrics */}
                <MetricsPanel metrics={metrics} />
            </div>

            {/* ── Footer ── */}
            <footer className="px-6 py-3 flex items-center justify-between text-xs" style={{ borderTop: "1px solid var(--aegis-border)", color: "var(--aegis-text-muted)" }}>
                <span>Aegis v1.0 — Autonomous Enterprise Action Engine</span>
                <div className="flex items-center gap-4">
                    {heldAction && (
                        <button
                            onClick={handleResume}
                            className="px-3 py-1.5 rounded-lg text-xs font-semibold transition-all hover:brightness-110"
                            style={{ background: "rgba(245, 158, 11, 0.15)", border: "1px solid rgba(245, 158, 11, 0.4)", color: "#fbbf24" }}
                        >
                            ⏸ Resume Review ({heldAction.type})
                        </button>
                    )}
                    <span>FastAPI + LangGraph + Next.js</span>
                    {threadId && <span className="font-mono">Thread: {threadId.slice(0, 8)}...</span>}
                </div>
            </footer>

            {/* ── HITL Approval Modal ── */}
            {pendingAction && (
                <ApprovalModal
                    action={pendingAction}
                    onApprove={handleApprove}
                    onDeny={handleDeny}
                    onHold={handleHold}
                    isLoading={approvalLoading}
                />
            )}
        </div>
    );
}
