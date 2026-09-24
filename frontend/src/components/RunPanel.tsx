"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowRight, CircleCheck, CornerDownLeft, Hourglass, RotateCcw, ServerOff, TriangleAlert, UsersRound } from "lucide-react";
import ApprovalGate from "./ApprovalGate";
import PipelineRail from "./PipelineRail";
import RunReceipt from "./RunReceipt";
import SqlTrace from "./SqlTrace";
import StepLine from "./StepLine";
import type { ActionProposal, CustomerCandidate, RecentRequest, SqlAttempt } from "@/lib/api";
import type { RunNotice } from "@/lib/errors";
import { formatWait } from "@/lib/errors";
import type { Preset } from "@/lib/presets";
import { FEATURED } from "@/lib/presets";
import { AGENTS, derivePipeline, groupSteps, type RunStatus } from "@/lib/trace";

export interface RunPanelProps {
    status: RunStatus;
    ticket: string;
    threadId: string | null;
    thoughts: string[];
    /** ms since the run started, per thought (may be shorter than thoughts). */
    times: number[];
    pendingAction: ActionProposal | null;
    approvalLoading: boolean;
    onApprove: (note: string) => void;
    onDeny: (reason: string) => void;
    candidates: CustomerCandidate[];
    disambiguationMessage: string | null;
    onSelectCandidate: (c: CustomerCandidate) => void;
    finalResponse: string | null;
    notice: RunNotice | null;
    receipt: RecentRequest | null;
    onRetry: () => void;
    onPreset: (p: Preset) => void;
    backendDown: boolean;
    sqlAttempts?: SqlAttempt[];
}

const STATUS_BADGE: Record<RunStatus, { label: string; tone: string } | null> = {
    idle: null,
    processing: { label: "Running", tone: "release" },
    awaiting_approval: { label: "Awaiting you", tone: "hold" },
    releasing: { label: "Releasing", tone: "release" },
    completed: { label: "Resolved", tone: "ok" },
    cached: { label: "Cache hit", tone: "ok" },
    disambiguation: { label: "Needs a choice", tone: "hold" },
    error: { label: "Stopped", tone: "fail" },
};

function EmptyState({ onPreset, backendDown }: { onPreset: (p: Preset) => void; backendDown: boolean }) {
    return (
        <div className="empty">
            <p className="eyebrow text-3">Start here</p>
            <h3 className="empty-title">Pick a ticket and watch the agents work it.</h3>
            <p className="text-[14px] text-2 max-w-[46ch] leading-relaxed">
                Each run is live: real LLM calls, a real Postgres database. When the agent wants to change an account, it stops at the gate and waits for you.
            </p>
            {backendDown && (
                <p className="inline-note mt-4">
                    <ServerOff size={14} aria-hidden="true" /> The agent API is offline right now. Examples will run once it&apos;s back.
                </p>
            )}
            <ul className="featured">
                {FEATURED.map((p) => (
                    <li key={p.id}>
                        <button type="button" className="featured-card" onClick={() => onPreset(p)}>
                            <span className="featured-label">{p.label}</span>
                            <span className="featured-hint">{p.hint}</span>
                            <span className="featured-cta">
                                Run <ArrowRight size={13} aria-hidden="true" />
                            </span>
                        </button>
                    </li>
                ))}
            </ul>
            <ul className="legend" aria-label="Colour key">
                <li><span className="legend-swatch bg-release" aria-hidden="true" />Agents working</li>
                <li><span className="legend-swatch legend-hold" aria-hidden="true" />Held for a human</li>
                <li><span className="legend-swatch bg-ok" aria-hidden="true" />Released</li>
                <li><span className="legend-swatch bg-guard" aria-hidden="true" />Security control</li>
            </ul>
            <p className="text-[12px] text-3 mt-4 flex items-center gap-1.5">
                Or write your own ticket and press <kbd className="kbd"><CornerDownLeft size={11} aria-label="Enter" /></kbd>
            </p>
        </div>
    );
}

function NoticeCard({ notice, onRetry }: { notice: RunNotice; onRetry: () => void }) {
    const Icon = notice.kind === "rate_limited" ? Hourglass : notice.kind === "offline" ? ServerOff : TriangleAlert;
    return (
        <div className={`notice notice-${notice.kind}`} role="alert">
            <Icon size={18} aria-hidden="true" className="shrink-0 mt-0.5" />
            <div className="min-w-0">
                <p className="notice-title">{notice.title}</p>
                <p className="text-[13px] text-2 leading-relaxed mt-1">{notice.detail}</p>
                {notice.retryAfterSeconds ? <Countdown seconds={notice.retryAfterSeconds} /> : null}
                {notice.kind !== "rate_limited" && (
                    <button type="button" className="btn btn-quiet mt-3" onClick={onRetry}>
                        <RotateCcw size={13} aria-hidden="true" /> Try again
                    </button>
                )}
            </div>
        </div>
    );
}

/** Live "try again in" timer for a 429, driven by the server's Retry-After. */
function Countdown({ seconds }: { seconds: number }) {
    const [left, setLeft] = useState(seconds);
    useEffect(() => {
        const id = setInterval(() => setLeft((s) => Math.max(0, s - 1)), 1000);
        return () => clearInterval(id);
    }, []);
    return left > 0 ? (
        <p className="text-[12px] text-3 mt-1.5">
            You can send another ticket in <span className="font-mono tnum text-1">{formatWait(left)}</span>.
        </p>
    ) : (
        <p className="text-[12px] text-ok mt-1.5">You can send another ticket now.</p>
    );
}

function CandidatePicker({ candidates, message, onSelect }: { candidates: CustomerCandidate[]; message: string | null; onSelect: (c: CustomerCandidate) => void }) {
    return (
        <section className="pick-card" aria-labelledby="pick-title">
            <p className="eyebrow text-hold flex items-center gap-1.5">
                <UsersRound size={13} aria-hidden="true" /> Paused · which customer?
            </p>
            <h3 id="pick-title" className="text-[15px] font-semibold text-1 mt-2">{message}</h3>
            <ul className="mt-3 space-y-2">
                {candidates.map((c) => (
                    <li key={c.id}>
                        <button type="button" className="pick-row" onClick={() => onSelect(c)}>
                            <span className="min-w-0">
                                <span className="font-medium text-1">{c.name}</span>{" "}
                                <span className="font-mono text-3 text-[12px]">#{c.id}</span>
                                {c.email && <span className="block text-[12px] text-3 truncate">{c.email}</span>}
                            </span>
                            <span className="flex items-center gap-1.5 shrink-0">
                                {c.plan && <span className="chip chip-neutral">{c.plan}</span>}
                                {c.status && c.status !== "active" && <span className="chip chip-fail">{c.status}</span>}
                                <ArrowRight size={14} aria-hidden="true" className="text-3" />
                            </span>
                        </button>
                    </li>
                ))}
            </ul>
        </section>
    );
}

function Elapsed({ running, lastAt }: { running: boolean; lastAt: number }) {
    const started = useRef<number | null>(null);
    const [now, setNow] = useState(0);
    useEffect(() => {
        if (!running) return;
        started.current ??= Date.now();
        const id = setInterval(() => setNow(Date.now() - (started.current as number)), 100);
        return () => clearInterval(id);
    }, [running]);
    const ms = running ? now : lastAt;
    return <span className="font-mono tnum text-3 text-[12px]">{(ms / 1000).toFixed(1)}s</span>;
}

export default function RunPanel(props: RunPanelProps) {
    const { status, thoughts, times } = props;
    const stages = derivePipeline(thoughts, status);
    const groups = groupSteps(thoughts);
    const badge =
        props.notice?.kind === "rate_limited" ? { label: "Rate limited", tone: "release" }
            : props.notice?.kind === "offline" ? { label: "Offline", tone: "fail" }
                : STATUS_BADGE[status];
    const scrollRef = useRef<HTMLDivElement>(null);
    const [raw, setRaw] = useState(false);
    const activeAgent = AGENTS.find((a) => stages[a.id] === "active");

    // Follow the log as it grows — except at the gate, which positions itself.
    useEffect(() => {
        if (status === "awaiting_approval" || status === "releasing") return;
        const el = scrollRef.current;
        el?.scrollTo?.({ top: el.scrollHeight, behavior: "smooth" });
    }, [thoughts.length, status]);

    const started = status !== "idle";
    const sql = props.sqlAttempts ?? [];
    const sqlGroup = groups.map((g) => g.agent).lastIndexOf("Investigator");

    return (
        <section id="run" className="panel panel-run" aria-labelledby="run-heading">
            <div className="panel-head">
                <h2 id="run-heading" className="panel-title">Live run</h2>
                <div className="flex items-center gap-2.5">
                    {started && props.threadId && <Elapsed key={props.threadId} running={status === "processing" || status === "releasing"} lastAt={times[times.length - 1] ?? 0} />}
                    {badge && (
                        <span className={`badge badge-${badge.tone}`} role="status">
                            {badge.label}
                        </span>
                    )}
                    {thoughts.length > 0 && (
                        <button type="button" className="toggle" aria-pressed={raw} onClick={() => setRaw((v) => !v)}>
                            Raw log
                        </button>
                    )}
                </div>
            </div>

            <div className="rail-wrap">
                <PipelineRail stages={stages} />
            </div>

            <div ref={scrollRef} className="panel-body" aria-live="polite" aria-busy={status === "processing"}>
                {!started && !props.notice && <EmptyState onPreset={props.onPreset} backendDown={props.backendDown} />}

                {props.ticket && started && (
                    <div className="ticket-echo">
                        <p className="eyebrow text-3">Ticket{props.threadId && <span className="font-mono normal-case tracking-normal"> · {props.threadId.slice(0, 8)}</span>}</p>
                        <p className="text-[14px] text-1 leading-relaxed mt-1">{props.ticket}</p>
                    </div>
                )}

                {raw ? (
                    <ol className="raw-log">
                        {thoughts.map((t, i) => (
                            <li key={i}>
                                <span className="text-3 select-none">{String(i + 1).padStart(2, "0")}</span> {t}
                            </li>
                        ))}
                    </ol>
                ) : (
                    groups.map((g, gi) => {
                        const meta = AGENTS.find((a) => a.id === g.agent);
                        return (
                            <div key={gi} className="agent-group">
                                <div className="agent-head">
                                    <span className="agent-avatar" style={{ ["--agent" as string]: meta?.color ?? "var(--text-3)" }} aria-hidden="true">
                                        {(g.agent ?? "S").charAt(0)}
                                    </span>
                                    <span className="text-[13px] font-semibold text-1">{g.agent ?? "System"}</span>
                                    {meta && <span className="text-[12px] text-3">{meta.role}</span>}
                                </div>
                                <ul className="steps">
                                    {g.steps.map((s) => (
                                        <StepLine key={s.index} step={s} at={times[s.index]} />
                                    ))}
                                </ul>
                                {gi === sqlGroup && <SqlTrace attempts={sql} />}
                            </div>
                        );
                    })
                )}

                {!raw && sqlGroup === -1 && <SqlTrace attempts={sql} />}

                {status === "processing" && (
                    <div className="working" data-testid="typing-indicator">
                        <span className="working-dots" aria-hidden="true"><span /><span /><span /></span>
                        {activeAgent ? `${activeAgent.id} is working` : "Starting the run"}
                    </div>
                )}

                {(status === "awaiting_approval" || status === "releasing") && props.pendingAction && (
                    <ApprovalGate action={props.pendingAction} onApprove={props.onApprove} onDeny={props.onDeny} isLoading={props.approvalLoading} />
                )}

                {status === "disambiguation" && props.candidates.length > 0 && (
                    <CandidatePicker candidates={props.candidates} message={props.disambiguationMessage} onSelect={props.onSelectCandidate} />
                )}

                {props.finalResponse && (status === "completed" || status === "cached") && (
                    <section className="result-card" aria-labelledby="result-title">
                        <p id="result-title" className="eyebrow text-ok flex items-center gap-1.5">
                            <CircleCheck size={13} aria-hidden="true" /> {status === "cached" ? "Served from semantic cache" : "Reply to the customer"}
                        </p>
                        <p className="text-[14px] text-1 leading-relaxed mt-2 whitespace-pre-line">{props.finalResponse}</p>
                    </section>
                )}

                {props.receipt && status === "completed" && <RunReceipt receipt={props.receipt} />}

                {props.notice && <NoticeCard key={props.notice.title + props.notice.detail} notice={props.notice} onRetry={props.onRetry} />}
            </div>
        </section>
    );
}
