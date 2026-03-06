"use client";

import { useState } from "react";

interface ThoughtStreamProps {
    thoughts: string[];
    status: string;
}

// Agent color mapping for visual distinction (Dev Mode)
const AGENT_COLORS: Record<string, { text: string; bg: string; border: string }> = {
    Triage: { text: "text-purple-400", bg: "bg-purple-500/10", border: "border-purple-500/20" },
    Investigator: { text: "text-cyan-400", bg: "bg-cyan-500/10", border: "border-cyan-500/20" },
    Knowledge: { text: "text-amber-400", bg: "bg-amber-500/10", border: "border-amber-500/20" },
    Resolution: { text: "text-emerald-400", bg: "bg-emerald-500/10", border: "border-emerald-500/20" },
};

const AGENT_ICONS: Record<string, string> = {
    Triage: "🏷",
    Investigator: "🔍",
    Knowledge: "📚",
    Resolution: "⚡",
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

    return (
        <div className="glass-panel h-full min-h-0 flex flex-col overflow-hidden">
            {/* Header */}
            <div className="flex items-center justify-between mb-4 px-6 pt-6 shrink-0">
                <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-blue-500/10 flex items-center justify-center">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#60a5fa" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
                        </svg>
                    </div>
                    <h2 className="text-sm font-semibold tracking-wide uppercase" style={{ color: "var(--aegis-text-muted)" }}>
                        {devMode ? "Agent Internals" : "Progress"}
                    </h2>
                </div>
                <div className="flex items-center gap-3">
                    {/* Dev Mode Toggle */}
                    <button
                        onClick={() => setDevMode(!devMode)}
                        className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[10px] font-bold uppercase tracking-wider transition-all border ${devMode
                            ? "bg-violet-500/15 text-violet-400 border-violet-500/30 shadow-[0_0_8px_rgba(139,92,246,0.15)]"
                            : "bg-white/5 text-gray-500 border-white/10 hover:bg-white/10 hover:text-gray-400"
                            }`}
                        title={devMode ? "Switch to user-friendly view" : "Switch to developer view with agent details"}
                    >
                        <span>{devMode ? "⚙" : "👤"}</span>
                        {devMode ? "Dev" : "User"}
                    </button>
                    {/* Status badges */}
                    {status === "processing" && (
                        <div className="flex items-center gap-2">
                            <div className="spinner" />
                            <span className="text-xs font-medium text-blue-400">Processing</span>
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
                </div>
            </div>

            {/* Single scroll for all content */}
            <div className="flex-1 overflow-y-auto pl-6 pr-4 pb-6 space-y-2" style={{ scrollbarGutter: "stable" }}>
                {thoughts.length === 0 ? (
                    <div className="px-3 py-2.5">
                        {status === "processing" ? (
                            <div className="flex items-center gap-2">
                                <span className="text-sm" style={{ color: "var(--aegis-text-muted)" }}>Agent is thinking</span>
                                <div className="typing-indicator p-0!">
                                    <span></span><span></span><span></span>
                                </div>
                            </div>
                        ) : (
                            <p className="text-sm" style={{ color: "var(--aegis-text-muted)" }}>
                                Submit a support ticket to see the agent&apos;s thought process...
                            </p>
                        )}
                    </div>
                ) : (
                    thoughts.map((step, i) => {
                        const { agent, message } = parseAgentName(step);
                        const agentStyle = agent ? AGENT_COLORS[agent] : null;
                        const agentIcon = agent ? AGENT_ICONS[agent] : null;
                        const displayMessage = devMode ? message : simplifyForUser(message);

                        return (
                            <div key={i} className="thought-step flex items-start gap-3 px-3 py-2.5 rounded-lg transition-all hover:bg-white/2" style={{ animationDelay: `${i * 80}ms` }}>
                                <span className={`text-lg font-bold shrink-0 ${getColor(step)}`}>
                                    {getIcon(step)}
                                </span>
                                <div className="flex items-start gap-2 flex-1 min-w-0">
                                    {devMode && agentStyle && (
                                        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider shrink-0 border ${agentStyle.bg} ${agentStyle.text} ${agentStyle.border}`}>
                                            <span>{agentIcon}</span>
                                            {agent}
                                        </span>
                                    )}
                                    <span className="text-sm leading-relaxed" style={{ fontFamily: devMode ? "var(--font-mono)" : "inherit", color: "var(--aegis-text)" }}>
                                        {displayMessage}
                                    </span>
                                </div>
                            </div>
                        );
                    })
                )}
                {status === "processing" && (
                    <div className="typing-indicator" data-testid="typing-indicator">
                        <span /><span /><span />
                    </div>
                )}
            </div>

            {/* Footer — pinned outside scroll */}
            {thoughts.length > 0 && (
                <div className="pt-3 pb-6 px-6 border-t flex items-center justify-between shrink-0" style={{ borderColor: "var(--aegis-border)", background: "var(--aegis-surface-hover)" }}>
                    <span className="text-xs" style={{ color: "var(--aegis-text-muted)" }}>
                        {thoughts.length} steps {devMode ? "completed" : ""}
                    </span>
                    <span className="text-xs" style={{ color: "var(--aegis-text-muted)" }}>
                        {devMode ? "Thread active" : ""}
                    </span>
                </div>
            )}
        </div>
    );
}
