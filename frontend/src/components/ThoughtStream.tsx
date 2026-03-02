"use client";

interface ThoughtStreamProps {
    thoughts: string[];
    status: string;
}

export default function ThoughtStream({ thoughts, status }: ThoughtStreamProps) {
    const getIcon = (step: string) => {
        if (step.startsWith("✓")) return "✓";
        if (step.startsWith("✗")) return "✗";
        if (step.startsWith("⏸")) return "⏸";
        return "→";
    };

    const getColor = (step: string) => {
        if (step.startsWith("✓")) return "text-emerald-400";
        if (step.startsWith("✗")) return "text-red-400";
        if (step.startsWith("⏸")) return "text-amber-400";
        return "text-blue-400";
    };

    return (
        <div className="glass-panel p-6 h-full flex flex-col">
            {/* Header */}
            <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-blue-500/10 flex items-center justify-center">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#60a5fa" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
                        </svg>
                    </div>
                    <h2 className="text-sm font-semibold tracking-wide uppercase" style={{ color: "var(--aegis-text-muted)" }}>
                        Agent Thought Process
                    </h2>
                </div>
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

            {/* Thought Steps */}
            <div className="flex-1 overflow-y-auto space-y-2 pr-1">
                {thoughts.length === 0 ? (
                    <div className="flex items-center justify-center h-full">
                        <p className="text-sm" style={{ color: "var(--aegis-text-muted)" }}>
                            Submit a support ticket to see the agent&apos;s thought process...
                        </p>
                    </div>
                ) : (
                    thoughts.map((step, i) => (
                        <div key={i} className="thought-step flex items-start gap-3 py-2 px-3 rounded-lg hover:bg-white/[0.02] transition-colors" style={{ animationDelay: `${i * 50}ms` }}>
                            <span className={`text-lg font-bold mt-0.5 ${getColor(step)}`}>
                                {getIcon(step)}
                            </span>
                            <span className="text-sm leading-relaxed" style={{ fontFamily: "var(--font-mono)", color: "var(--aegis-text)" }}>
                                {step.replace(/^[✓✗⏸→]\s*/, "")}
                            </span>
                        </div>
                    ))
                )}
            </div>

            {/* Footer status bar */}
            {thoughts.length > 0 && (
                <div className="mt-4 pt-3 border-t flex items-center justify-between" style={{ borderColor: "var(--aegis-border)" }}>
                    <span className="text-xs" style={{ color: "var(--aegis-text-muted)" }}>
                        {thoughts.length} steps completed
                    </span>
                    <span className="text-xs" style={{ color: "var(--aegis-text-muted)" }}>
                        Thread active
                    </span>
                </div>
            )}
        </div>
    );
}
