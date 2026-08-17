"use client";

import { useState, useRef, useEffect } from "react";

interface ThoughtStreamProps {
    thoughts: string[];
    status: string;
}

// Agent identity colors for the Dev Mode badges — shown as dots, text stays neutral
const AGENT_COLORS: Record<string, string> = {
    Triage: "#a78bfa",
    Investigator: "#22d3ee",
    Knowledge: "#fbbf24",
    Resolution: "#34d399",
};

// User-friendly message simplification (User Mode)
const USER_MODE_PATTERNS: [RegExp, string][] = [
    [/Classified intent: (\w+).*/, "Analyzing your request..."],
    [/Customer validated: #(\d+) (.+?) \((.+?),\s*(.+?)\)/, "Found customer: $2"],
    [/Name typo detected.*auto-corrected to "(.+?)".*/, "Customer identified: $1"],
    [/Customer found by name: #\d+ (.+?) \(.*/, "Found customer: $1"],
    [/Customer #\d+ .+ is currently SUSPENDED/, "Note: This account is currently suspended"],
    [/Customer #\d+ .+ account is CANCELLED/, "Note: This account has been cancelled"],
    [/Generated SQL query.*/, "Searching account records..."],
    [/SQL executed successfully — found (\d+) records/, "Found $1 matching records"],
    [/SQL retry \(attempt (\d+).*/, "Refining search (attempt $1)..."],
    [/Found (\d+) relevant internal documents/, "Checking company policies..."],
    [/No specific internal docs found.*/, "Reviewing with general guidelines..."],
    [/Proposed action: (\w+) — (.+)/, "Recommendation: $2"],
    [/Auto-approved.*/, "Processing resolution..."],
    [/Human decision: approved.*/, "✓ Manager approved"],
    [/Human decision: denied.*/, "✗ Manager declined"],
    [/Action executed: (.+)/, "$1"],
    [/Generated resolution summary/, "Preparing your summary..."],
    [/Response already set.*/, "Ready."],
    [/No records found.*/, "No matching records found"],
    [/No specific customer.*proceeding.*/, "Searching broadly..."],
    [/Name mismatch.*stopping/, "Customer identity could not be verified"],
    [/not found in database.*stopping/, "Customer not found in our records"],
    [/No customer found matching.*stopping/, "No matching customer found"],
    [/Ambiguous name.*matches found.*/, "Multiple customers match — clarification needed"],
    [/No SQL query to execute/, "No data search needed"],
    [/Proceeding with investigation/, "Starting investigation..."],
];

function simplifyForUser(rawMessage: string): string {
    for (const [pattern, replacement] of USER_MODE_PATTERNS) {
        if (pattern.test(rawMessage)) {
            return rawMessage.replace(pattern, replacement);
        }
    }
    return rawMessage;
}

function parseAgentName(step: string): { agent: string | null; message: string } {
    const cleaned = step.replace(/^[✓✗⏸⚠→]\s*/, "");
    const match = cleaned.match(/^\[(\w+)\]\s*(.*)/);
    if (match && AGENT_COLORS[match[1]]) {
        return { agent: match[1], message: match[2] };
    }
    return { agent: null, message: cleaned };
}

export default function ThoughtStream({ thoughts, status }: ThoughtStreamProps) {
    const [devMode, setDevMode] = useState(false);
    const scrollRef = useRef<HTMLDivElement>(null);

    // Auto-scroll to bottom when new thoughts arrive
    useEffect(() => {
        scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
    }, [thoughts.length, status]);

    const getIcon = (step: string) => {
        if (step.startsWith("✓")) return "✓";
        if (step.startsWith("✗")) return "✗";
        if (step.startsWith("⏸")) return "⏸";
        if (step.startsWith("⚠")) return "⚠";
        return "→";
    };

    const getColor = (step: string) => {
        if (step.startsWith("✓")) return "text-emerald-400";
        if (step.startsWith("✗")) return "text-red-400";
        if (step.startsWith("⏸")) return "text-amber-400";
        if (step.startsWith("⚠")) return "text-orange-400";
        return "text-blue-400";
    };

    const held = status === "awaiting_approval";

    return (
        <div className={`glass-panel h-full min-h-0 flex flex-col overflow-hidden ${held ? "held" : ""}`}>
            {/* Header */}
            <div className="panel-header">
                <h2 className="panel-title">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
                    </svg>
                    {devMode ? "Agent Internals" : "Progress"}
                </h2>
                <div className="flex items-center gap-3">
                    {/* Status badges */}
                    {status === "processing" && (
                        <div className="flex items-center gap-2" style={{ color: "var(--release-text)" }}>
                            <div className="spinner" />
                            <span className="text-xs font-medium">Processing</span>
                        </div>
                    )}
                    {status === "awaiting_approval" && (
                        <span className="badge badge-awaiting">⏸ Awaiting Approval</span>
                    )}
                    {status === "completed" && (
                        <span className="badge badge-completed">✓ Completed</span>
                    )}
                    {status === "cached" && (
                        <span className="badge badge-cached">⚡ Cached</span>
                    )}
                    {/* Dev Mode Toggle */}
                    <button
                        onClick={() => setDevMode(!devMode)}
                        className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[10px] font-bold uppercase tracking-wider transition-colors border"
                        style={devMode
                            ? { background: "rgba(59,130,246,0.12)", color: "var(--release-text)", borderColor: "rgba(59,130,246,0.4)" }
                            : { background: "transparent", color: "var(--aegis-text-muted)", borderColor: "var(--aegis-border-strong)" }}
                        title={devMode ? "Switch to user-friendly view" : "Switch to developer view with agent details"}
                    >
                        <span
                            className="w-1.5 h-1.5 rounded-full"
                            style={{ background: devMode ? "var(--release)" : "var(--aegis-text-muted)" }}
                        />
                        {devMode ? "Dev" : "User"}
                    </button>
                </div>
            </div>

            {/* Single scroll for all content */}
            <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-4" style={{ scrollbarGutter: "stable" }}>

                {/* 1. Empty States (No thoughts generated yet) */}
                {thoughts.length === 0 && (
                    <div className="h-full flex flex-col items-center justify-center gap-3 py-8 text-center">
                        {status === "processing" && (
                            <>
                                <p className="text-[13px]" style={{ color: "var(--aegis-text-2)" }}>
                                    Agent is thinking
                                </p>
                                <div className="typing-indicator" data-testid="typing-indicator">
                                    <span /><span /><span />
                                </div>
                            </>
                        )}
                        {status === "error" && (
                            <p className="text-[13px]" style={{ color: "var(--aegis-error)" }}>
                                ✗ An error occurred while connecting to the agent.
                            </p>
                        )}
                        {status === "completed" && (
                            <p className="text-[13px]" style={{ color: "var(--aegis-text-2)" }}>
                                Agent completed the task without generating any output.
                            </p>
                        )}
                        {status === "cached" && (
                            <p className="text-[13px]" style={{ color: "var(--aegis-text-2)" }}>
                                Loaded from cache. Processing skipped.
                            </p>
                        )}
                        {(status === "idle" || status === "awaiting_approval") && (
                            <>
                                {/* Pipeline preview: the run this panel will trace, gate included */}
                                <div className="flex items-center gap-0 mb-1 select-none" aria-hidden="true">
                                    {["Triage", "Investigate", "Propose"].map((stage) => (
                                        <div key={stage} className="flex items-center">
                                            <div className="flex flex-col items-center gap-1.5 w-[64px]">
                                                <span className="w-2 h-2 rounded-full" style={{ background: "var(--release)" }} />
                                                <span className="text-[9px] font-semibold uppercase tracking-[0.08em]" style={{ color: "var(--aegis-text-muted)" }}>
                                                    {stage}
                                                </span>
                                            </div>
                                            <span className="w-3 h-px -mt-4" style={{ background: "var(--aegis-border-strong)" }} />
                                        </div>
                                    ))}
                                    <div className="flex flex-col items-center gap-1.5 w-[52px]">
                                        <span className="w-[3px] h-3.5 rounded-full -my-[3px]" style={{ background: "var(--hold)" }} />
                                        <span className="text-[9px] font-bold uppercase tracking-[0.08em]" style={{ color: "var(--hold-text)" }}>
                                            Hold
                                        </span>
                                    </div>
                                    <span className="w-3 h-px -mt-4" style={{ background: "var(--aegis-border-strong)" }} />
                                    <div className="flex flex-col items-center gap-1.5 w-[64px]">
                                        <span className="w-2 h-2 rounded-full border" style={{ borderColor: "var(--aegis-border-strong)" }} />
                                        <span className="text-[9px] font-semibold uppercase tracking-[0.08em]" style={{ color: "var(--aegis-text-muted)" }}>
                                            Execute
                                        </span>
                                    </div>
                                </div>
                                <p className="text-[13px] max-w-[320px]" style={{ color: "var(--aegis-text-2)" }}>
                                    Submit a support ticket to see the agent&apos;s thought process...
                                </p>
                                <p className="text-[11px] max-w-[300px]" style={{ color: "var(--aegis-text-muted)" }}>
                                    Proposed actions stop at the amber gate until a human approves.
                                </p>
                            </>
                        )}
                    </div>
                )}

                {/* 2. Thought Stream — the rail */}
                {thoughts.length > 0 && (
                    <div className="stream-rail">
                        {thoughts.map((step, i) => {
                            const { agent, message } = parseAgentName(step);
                            const agentColor = agent ? AGENT_COLORS[agent] : null;
                            const displayMessage = devMode ? message : simplifyForUser(message);

                            return (
                                <div key={i} className="thought-step" style={{ animationDelay: `${Math.min(i * 60, 480)}ms` }}>
                                    <span className={`step-marker ${getColor(step)}`}>
                                        {getIcon(step)}
                                    </span>
                                    <div className="flex items-baseline gap-2 flex-1 min-w-0 flex-wrap">
                                        {devMode && agentColor && (
                                            <span
                                                data-testid={`agent-badge-${agent}`}
                                                className="inline-flex items-center gap-1.5 px-1.5 py-px rounded text-[10px] font-bold uppercase tracking-wider shrink-0 border"
                                                style={{ borderColor: "var(--aegis-border-strong)", color: "var(--aegis-text-2)", background: "var(--aegis-surface-2)" }}
                                            >
                                                <span className="w-1.5 h-1.5 rounded-full" style={{ background: agentColor }} />
                                                {agent}
                                            </span>
                                        )}
                                        <span
                                            className="text-[13px] leading-relaxed min-w-0"
                                            style={{ fontFamily: devMode ? "var(--font-mono)" : "inherit", fontSize: devMode ? "12px" : undefined, color: "var(--aegis-text)", overflowWrap: "anywhere" }}
                                        >
                                            {displayMessage}
                                        </span>
                                    </div>
                                </div>
                            );
                        })}

                        {/* 3. Trailing indicators */}
                        {status === "processing" && (
                            <div className="pl-8 typing-indicator" data-testid="typing-indicator">
                                <span /><span /><span />
                            </div>
                        )}
                        {status === "awaiting_approval" && (
                            <div className="stream-gate">
                                <span className="gate-dot" />
                                <div className="min-w-0">
                                    <p className="text-[12px] font-semibold" style={{ color: "var(--hold-text)" }}>
                                        Action held at the gate
                                    </p>
                                    <p className="text-[11px]" style={{ color: "var(--aegis-text-2)" }}>
                                        Nothing executes until you approve or deny.
                                    </p>
                                </div>
                            </div>
                        )}
                    </div>
                )}
            </div>

            {/* Footer — pinned outside scroll */}
            {thoughts.length > 0 && (
                <div className="py-2.5 px-4 border-t flex items-center justify-between shrink-0" style={{ borderColor: "var(--aegis-border)" }}>
                    <span className="text-[11px] font-mono" style={{ color: "var(--aegis-text-muted)" }}>
                        {thoughts.length} steps {devMode ? "completed" : ""}
                    </span>
                    <span className="text-[11px] font-mono" style={{ color: "var(--aegis-text-muted)" }}>
                        {devMode ? "Thread active" : ""}
                    </span>
                </div>
            )}
        </div>
    );
}
