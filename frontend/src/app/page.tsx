"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import dynamic from "next/dynamic";
import TopBar, { type BackendState } from "@/components/TopBar";
import Composer from "@/components/Composer";
import RunPanel from "@/components/RunPanel";
import MetricsPanel from "@/components/MetricsPanel";
import TracesPanel from "@/components/TracesPanel";
import { useTicketHistory } from "@/hooks/useTicketHistory";
import {
    startChat,
    connectSSE,
    approveAction,
    getMetrics,
    getThread,
    type ActionProposal,
    type Metrics,
    type CustomerCandidate,
    type SqlAttempt,
} from "@/lib/api";
import { describeError, type RunNotice } from "@/lib/errors";
import type { Preset } from "@/lib/presets";
import type { RunStatus } from "@/lib/trace";

const TicketHistory = dynamic(() => import("@/components/TicketHistory"), { ssr: false });

const METRICS_POLL_MS = 8000;

export default function Dashboard() {
    // Ticket + run state
    const [message, setMessage] = useState("");
    const [ticket, setTicket] = useState("");
    const [threadId, setThreadId] = useState<string | null>(null);
    const [thoughts, setThoughts] = useState<string[]>([]);
    const [times, setTimes] = useState<number[]>([]);
    const [status, setStatus] = useState<RunStatus>("idle");
    const [finalResponse, setFinalResponse] = useState<string | null>(null);
    const [notice, setNotice] = useState<RunNotice | null>(null);
    const [sqlAttempts, setSqlAttempts] = useState<SqlAttempt[]>([]);
    const startedAt = useRef(0);
    const stream = useRef<EventSource | null>(null);

    // Human-in-the-loop
    const [pendingAction, setPendingAction] = useState<ActionProposal | null>(null);
    const [approvalLoading, setApprovalLoading] = useState(false);
    const [candidates, setCandidates] = useState<CustomerCandidate[]>([]);
    const [disambiguationMessage, setDisambiguationMessage] = useState<string | null>(null);

    // Telemetry
    const [metrics, setMetrics] = useState<Metrics | null>(null);
    const [backendUp, setBackendUp] = useState<boolean | null>(null);
    const [tracesOpen, setTracesOpen] = useState(false);

    const { entries: historyEntries, addEntry: addHistoryEntry, clearHistory } = useTicketHistory();
    const lastRecordedStatus = useRef<RunStatus>("idle");

    const refreshMetrics = useCallback(async () => {
        try {
            setMetrics(await getMetrics());
            setBackendUp(true);
        } catch {
            setBackendUp(false);
        }
    }, []);

    useEffect(() => {
        const first = setTimeout(refreshMetrics, 0);
        const interval = setInterval(refreshMetrics, METRICS_POLL_MS);
        return () => {
            clearTimeout(first);
            clearInterval(interval);
        };
    }, [refreshMetrics]);

    // Close any open stream when the page goes away.
    useEffect(() => () => stream.current?.close(), []);

    // Record finished tickets in the local history.
    useEffect(() => {
        // `ticket` is always set by the time a run finishes; an error always carries a notice.
        if ((status === "completed" || status === "error") && lastRecordedStatus.current !== status) {
            const preview = ((status === "completed" ? finalResponse : notice!.title) ?? "").slice(0, 100);
            addHistoryEntry({ message: ticket, status, responsePreview: preview });
        }
        lastRecordedStatus.current = status;
    }, [status, ticket, finalResponse, notice, addHistoryEntry]);

    const elapsed = () => Date.now() - startedAt.current;

    /** Replace the log with the server's authoritative copy, timing any new lines now. */
    const adoptLog = useCallback((log: string[]) => {
        setThoughts(log);
        setTimes((prev) => {
            const at = Date.now() - startedAt.current;
            return log.map((_, i) => prev[i] ?? at);
        });
    }, []);

    const handleSubmit = useCallback(async (msg?: string) => {
        const text = (msg ?? message).trim();
        if (!text) return;

        stream.current?.close();
        setThoughts([]);
        setTimes([]);
        setSqlAttempts([]);
        setFinalResponse(null);
        setPendingAction(null);
        setCandidates([]);
        setDisambiguationMessage(null);
        setNotice(null);
        setThreadId(null);
        setTicket(text);
        setStatus("processing");
        startedAt.current = Date.now();
        // On narrow screens the run panel sits below the composer — bring it into view.
        if (window.matchMedia?.("(max-width: 1023px)").matches) {
            // Deferred so the scroll isn't cancelled by the re-render this submit triggers.
            setTimeout(() => {
                const run = document.getElementById("run");
                if (run) window.scrollTo({ top: run.getBoundingClientRect().top + window.scrollY - 64, behavior: "smooth" });
            }, 60);
        }

        try {
            const res = await startChat(text);
            setThreadId(res.thread_id);

            if (res.cache_hit) {
                try {
                    const cached = await getThread(res.thread_id);
                    adoptLog(cached.thought_log);
                    setSqlAttempts(cached.sql_attempts ?? []);
                    setFinalResponse(cached.final_response ?? "Served from the semantic cache.");
                } catch {
                    setFinalResponse("This exact ticket was answered recently, so the cached reply was served instantly with no LLM calls.");
                }
                setStatus("cached");
                return;
            }

            stream.current = connectSSE(
                res.thread_id,
                (step) => {
                    setThoughts((prev) => [...prev, step]);
                    setTimes((prev) => [...prev, elapsed()]);
                },
                (action) => {
                    setPendingAction(action);
                    setStatus("awaiting_approval");
                },
                (response, log) => {
                    adoptLog(log);
                    setFinalResponse(response);
                    setStatus("completed");
                    setTimeout(refreshMetrics, 800);
                },
                (error) => {
                    // The backend sends a sanitized, human-readable reason.
                    setNotice({
                        kind: "agent",
                        title: "The run stopped before it finished",
                        detail: error === "Connection lost" ? "Lost the live connection to the agent. The backend may have restarted." : error,
                    });
                    setStatus("error");
                },
                (customerCandidates, response) => {
                    setCandidates(customerCandidates);
                    setDisambiguationMessage(response);
                    setStatus("disambiguation");
                },
                setSqlAttempts
            );
        } catch (err) {
            setNotice(describeError(err));
            setStatus("error");
            if (describeError(err).kind === "offline") setBackendUp(false);
        }
    }, [message, adoptLog, refreshMetrics]);

    const decide = useCallback(async (approved: boolean, reason: string) => {
        /* v8 ignore start -- the gate only renders once a thread exists */
        if (!threadId) return;
        /* v8 ignore stop */
        setApprovalLoading(true);
        setNotice(null);
        setStatus("releasing");
        try {
            const res = await approveAction(threadId, approved, reason);
            try {
                const thread = await getThread(threadId);
                adoptLog(thread.thought_log);
                if (thread.sql_attempts) setSqlAttempts(thread.sql_attempts);
            } catch {
                setThoughts((prev) => [...prev, `${approved ? "✓" : "✗"} [Resolution] Human decision: ${approved ? "approved" : "denied"}${reason ? ` — ${reason}` : ""}`]);
                setTimes((prev) => [...prev, elapsed()]);
            }
            setFinalResponse(res.result || (approved ? "Action released." : "Action denied. No changes were made."));
            setPendingAction(null);
            setStatus("completed");
            setTimeout(refreshMetrics, 800);
        } catch (err) {
            setNotice(describeError(err));
            setStatus("awaiting_approval");
        }
        setApprovalLoading(false);
    }, [threadId, adoptLog, refreshMetrics]);

    const handleSelectCustomer = useCallback((candidate: CustomerCandidate) => {
        const corrected = /[Cc]ustomer\s*#?\d*\s*[A-Z]/.test(ticket)
            ? ticket.replace(/[Cc]ustomer\s*#?\d*\s*[A-Z][a-z]*(?:\s+[A-Z][a-z]*)*/, `Customer #${candidate.id} ${candidate.name}`)
            : `Customer #${candidate.id} ${candidate.name}: ${ticket}`;
        setMessage(corrected);
        handleSubmit(corrected);
    }, [ticket, handleSubmit]);

    const runPreset = useCallback((p: Preset) => {
        setMessage(p.message);
        handleSubmit(p.message);
    }, [handleSubmit]);

    const busy = status === "processing" || status === "releasing";
    const backend: BackendState = backendUp === null ? "connecting" : backendUp ? "up" : "down";
    const receipt = metrics?.agent_metrics.recent_requests?.find((r) => r.thread_id === threadId) ?? null;

    return (
        <div className="app" data-held={status === "awaiting_approval" ? "true" : undefined}>
            <a href="#ticket-input" className="skip-link">Skip to the ticket input</a>
            <TopBar backend={backend} />
            <div className={`progress-line progress-${notice?.kind === "rate_limited" ? "idle" : status}`} aria-hidden="true" />

            <main className="shell">
                <section className={`hero ${status === "idle" ? "" : "hero-compact"}`} aria-labelledby="hero-title">
                    <div className="min-w-0">
                        <p className="eyebrow text-release">LangGraph · four agents · one human gate</p>
                        <h2 id="hero-title" className="hero-title">
                            The agents do the investigation. <span className="text-hold-grad">You release the action.</span>
                        </h2>
                        <p className="hero-sub">
                            Send a support ticket. Aegis triages it, queries a live database, checks policy, and proposes one action.
                            Anything that touches money or access pauses until a human approves it.
                        </p>
                    </div>
                    <ul className="hero-facts" aria-label="What to look for">
                        <li><span className="fact-dot bg-release" aria-hidden="true" />Model routing per step</li>
                        <li><span className="fact-dot bg-heal" aria-hidden="true" />Self-healing SQL</li>
                        <li><span className="fact-dot bg-guard" aria-hidden="true" />Injection screen + SQL guard</li>
                        <li><span className="fact-bar" aria-hidden="true" />Human approval gate</li>
                    </ul>
                </section>

                <div className="workspace">
                    <Composer message={message} onChange={setMessage} onSubmit={() => handleSubmit()} onPreset={runPreset} busy={busy}>
                        <TicketHistory entries={historyEntries} onSelect={setMessage} onClear={clearHistory} />
                    </Composer>

                    <RunPanel
                        status={status}
                        ticket={ticket}
                        threadId={threadId}
                        thoughts={thoughts}
                        times={times}
                        pendingAction={pendingAction}
                        approvalLoading={approvalLoading}
                        onApprove={(note) => decide(true, note)}
                        onDeny={(reason) => decide(false, reason)}
                        candidates={candidates}
                        disambiguationMessage={disambiguationMessage}
                        onSelectCandidate={handleSelectCustomer}
                        finalResponse={finalResponse}
                        notice={notice}
                        receipt={receipt}
                        onRetry={() => handleSubmit(ticket)}
                        onPreset={runPreset}
                        backendDown={backend === "down"}
                        sqlAttempts={sqlAttempts}
                    />

                    <MetricsPanel metrics={metrics} backend={backend} onCacheCleared={refreshMetrics} onOpenTraces={() => setTracesOpen(true)} />
                </div>
            </main>

            <TracesPanel open={tracesOpen} onClose={() => setTracesOpen(false)} />
        </div>
    );
}
