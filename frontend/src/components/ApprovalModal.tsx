"use client";

import type { ActionProposal } from "@/lib/api";

interface ApprovalModalProps {
    action: ActionProposal;
    onApprove: () => void;
    onDeny: (reason: string) => void;
    onHold: () => void;
    isLoading: boolean;
}

export default function ApprovalModal({ action, onApprove, onDeny, onHold, isLoading }: ApprovalModalProps) {
    const getActionIcon = (type: string) => {
        switch (type) {
            case "refund": return "💰";
            case "credit": return "🎁";
            case "tier_change": return "📊";
            case "escalate": return "🚨";
            default: return "⚡";
        }
    };

    const getActionColor = (type: string) => {
        switch (type) {
            case "refund": return "border-amber-500/30 bg-amber-500/5";
            case "credit": return "border-emerald-500/30 bg-emerald-500/5";
            case "tier_change": return "border-blue-500/30 bg-blue-500/5";
            case "escalate": return "border-red-500/30 bg-red-500/5";
            default: return "border-purple-500/30 bg-purple-500/5";
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: "rgba(0,0,0,0.7)", backdropFilter: "blur(8px)" }}>
            <div className="glass-panel p-0 max-w-lg w-full pulse-glow overflow-hidden" style={{ border: "1px solid rgba(59, 130, 246, 0.3)" }}>
                {/* Header */}
                <div className="px-6 py-4 flex items-center gap-3" style={{ borderBottom: "1px solid var(--aegis-border)", background: "rgba(59, 130, 246, 0.05)" }}>
                    <div className="w-10 h-10 rounded-xl bg-amber-500/10 flex items-center justify-center text-xl">
                        ⚠️
                    </div>
                    <div>
                        <h3 className="text-base font-bold" style={{ color: "var(--aegis-text)" }}>Human Approval Required</h3>
                        <p className="text-xs" style={{ color: "var(--aegis-text-muted)" }}>The AI agent has proposed an action that needs your authorization</p>
                    </div>
                </div>

                {/* Action Details */}
                <div className="px-6 py-5 space-y-4">
                    {/* Action Type Card */}
                    <div className={`rounded-xl p-4 border ${getActionColor(action.type)}`}>
                        <div className="flex items-center gap-3 mb-2">
                            <span className="text-2xl">{getActionIcon(action.type)}</span>
                            <div>
                                <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: "var(--aegis-text-muted)" }}>
                                    Proposed Action
                                </span>
                                <p className="text-base font-bold capitalize" style={{ color: "var(--aegis-text)" }}>
                                    {action.type.replace("_", " ")}
                                    {action.amount ? ` — $${action.amount.toFixed(2)}` : ""}
                                </p>
                            </div>
                        </div>
                        <p className="text-sm leading-relaxed" style={{ color: "var(--aegis-text)" }}>
                            {action.description}
                        </p>
                    </div>

                    {/* Details Grid */}
                    <div className="grid grid-cols-2 gap-3">
                        {action.customer_name && (
                            <div className="metric-card">
                                <span className="text-xs block mb-1" style={{ color: "var(--aegis-text-muted)" }}>Customer</span>
                                <span className="text-sm font-semibold">{action.customer_name}</span>
                            </div>
                        )}
                        {action.customer_id && (
                            <div className="metric-card">
                                <span className="text-xs block mb-1" style={{ color: "var(--aegis-text-muted)" }}>Customer ID</span>
                                <span className="text-sm font-semibold">#{action.customer_id}</span>
                            </div>
                        )}
                    </div>

                    {/* Reason */}
                    <div className="rounded-lg p-3" style={{ background: "var(--aegis-surface)", border: "1px solid var(--aegis-border)" }}>
                        <span className="text-xs font-medium block mb-1" style={{ color: "var(--aegis-text-muted)" }}>AI Reasoning</span>
                        <p className="text-sm leading-relaxed" style={{ color: "var(--aegis-text)" }}>{action.reason}</p>
                    </div>
                </div>

                {/* Action Buttons */}
                <div className="px-6 py-4 flex gap-3" style={{ borderTop: "1px solid var(--aegis-border)", background: "rgba(0,0,0,0.2)" }}>
                    <button
                        onClick={() => onDeny("Manager denied the proposed action")}
                        disabled={isLoading}
                        className="btn-danger flex-1 flex items-center justify-center gap-2 disabled:opacity-50"
                    >
                        {isLoading ? <div className="spinner" /> : "✗"} Deny
                    </button>
                    <button
                        onClick={onHold}
                        disabled={isLoading}
                        className="flex-1 flex items-center justify-center gap-2 rounded-lg py-2.5 font-semibold text-sm transition-all hover:brightness-110 disabled:opacity-50"
                        style={{ background: "rgba(245, 158, 11, 0.15)", border: "1px solid rgba(245, 158, 11, 0.4)", color: "#fbbf24" }}
                    >
                        ⏸ Hold
                    </button>
                    <button
                        onClick={onApprove}
                        disabled={isLoading}
                        className="btn-success flex-1 flex items-center justify-center gap-2 disabled:opacity-50"
                    >
                        {isLoading ? <div className="spinner" /> : "✓"} Approve
                    </button>
                </div>
            </div>
        </div>
    );
}
