"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import type { ActionProposal } from "@/lib/api";

interface ApprovalModalProps {
    action: ActionProposal;
    onApprove: () => void;
    onDeny: (reason: string) => void;
    isLoading: boolean;
}

const ESCAPE_DENY_REASON = "Manager dismissed the approval request";

/** Line-icon per action type. Each branch returns a distinct, testable node. */
function ActionIcon({ type }: { type: string }) {
    const common = {
        width: 18,
        height: 18,
        viewBox: "0 0 24 24",
        fill: "none",
        stroke: "currentColor",
        strokeWidth: 2,
        strokeLinecap: "round" as const,
        strokeLinejoin: "round" as const,
    };
    switch (type) {
        case "refund":
            return (
                <svg {...common} data-testid="action-icon-refund">
                    <path d="M3 10h18" /><rect x="3" y="5" width="18" height="14" rx="2" /><path d="M7 15h4" />
                </svg>
            );
        case "credit":
            return (
                <svg {...common} data-testid="action-icon-credit">
                    <circle cx="12" cy="12" r="9" /><path d="M12 7v10M15.5 9.5h-5a1.75 1.75 0 0 0 0 3.5h3a1.75 1.75 0 0 1 0 3.5h-5" />
                </svg>
            );
        case "tier_change":
            return (
                <svg {...common} data-testid="action-icon-tier_change">
                    <path d="M7 17l5-5 5 5" /><path d="M7 11l5-5 5 5" />
                </svg>
            );
        case "escalate":
            return (
                <svg {...common} data-testid="action-icon-escalate">
                    <path d="M10.3 3.9L1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" /><path d="M12 9v4" /><path d="M12 17h.01" />
                </svg>
            );
        case "suspend":
            return (
                <svg {...common} data-testid="action-icon-suspend">
                    <rect x="4" y="11" width="16" height="10" rx="2" /><path d="M8 11V7a4 4 0 0 1 8 0v4" />
                </svg>
            );
        case "reactivate":
            return (
                <svg {...common} data-testid="action-icon-reactivate">
                    <rect x="4" y="11" width="16" height="10" rx="2" /><path d="M8 11V7a4 4 0 0 1 7.7-1.5" />
                </svg>
            );
        default:
            return (
                <svg {...common} data-testid="action-icon-default">
                    <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
                </svg>
            );
    }
}

export default function ApprovalModal({ action, onApprove, onDeny, isLoading }: ApprovalModalProps) {
    const [closing, setClosing] = useState(false);
    const denyRef = useRef<HTMLButtonElement>(null);
    const approveRef = useRef<HTMLButtonElement>(null);

    const animateOut = useCallback((callback: () => void) => {
        setClosing(true);
        setTimeout(callback, 200); // match CSS exit animation duration
    }, []);

    // The gate demands a decision: focus lands on the safe action first.
    useEffect(() => {
        denyRef.current?.focus();
    }, []);

    // Focus trap + Escape. Escape takes the fail-safe path: deny, nothing executes.
    const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
        if (e.key === "Escape") {
            e.preventDefault();
            if (!isLoading && !closing) {
                animateOut(() => onDeny(ESCAPE_DENY_REASON));
            }
            return;
        }
        if (e.key === "Tab") {
            // Only two tab stops exist; Tab and Shift+Tab both toggle between them.
            e.preventDefault();
            const target = document.activeElement === denyRef.current ? approveRef : denyRef;
            target.current?.focus();
        }
    }, [isLoading, closing, animateOut, onDeny]);

    const getActionColor = (type: string) => {
        switch (type) {
            case "refund": return "border-amber-500/30 bg-amber-500/5";
            case "credit": return "border-emerald-500/30 bg-emerald-500/5";
            case "tier_change": return "border-blue-500/30 bg-blue-500/5";
            case "escalate": return "border-red-500/30 bg-red-500/5";
            case "suspend": return "border-orange-500/30 bg-orange-500/5";
            case "reactivate": return "border-teal-500/30 bg-teal-500/5";
            default: return "border-purple-500/30 bg-purple-500/5";
        }
    };

    return (
        <div
            className={`fixed inset-0 z-50 flex items-center justify-center p-4 ${closing ? "modal-backdrop-exit" : "modal-backdrop"}`}
            style={{ background: "rgba(3, 5, 10, 0.75)", backdropFilter: "blur(6px)" }}
            onKeyDown={handleKeyDown}
        >
            <div
                role="dialog"
                aria-modal="true"
                aria-labelledby="approval-modal-title"
                className={`gate-modal max-w-lg w-full overflow-hidden ${closing ? "modal-exit" : "modal-enter"}`}
            >
                {/* Header — the payload ran blue down the rail and locked at the bar */}
                <div className="px-6 pt-5 pb-4" style={{ borderBottom: "1px solid var(--aegis-border)" }}>
                    <div className="gate-rail mb-3" aria-hidden="true">
                        <div className="gate-rail-track" />
                        <div className="gate-rail-run" />
                        <div className="gate-rail-payload" />
                        <div className="gate-rail-bar" />
                    </div>
                    <p className="text-[10px] font-bold uppercase tracking-[0.14em] mb-1 font-mono" style={{ color: "var(--hold-text)" }}>
                        Action held
                    </p>
                    <h3 id="approval-modal-title" className="text-lg font-bold leading-tight" style={{ color: "var(--aegis-text)" }}>
                        Human Approval Required
                    </h3>
                    <p className="text-[12px] mt-1" style={{ color: "var(--aegis-text-2)" }}>
                        The agent finished its investigation and stopped one step short of executing. Nothing moves until you decide.
                    </p>
                </div>

                {/* Action Details */}
                <div className="px-6 py-4 space-y-3">
                    {/* Action Type Card */}
                    <div className={`rounded-lg p-4 border ${getActionColor(action.type)}`}>
                        <div className="flex items-center gap-3 mb-2">
                            <span
                                className="w-9 h-9 rounded-lg inline-flex items-center justify-center shrink-0"
                                style={{ background: "rgba(245,158,11,0.12)", color: "var(--hold-text)" }}
                            >
                                <ActionIcon type={action.type} />
                            </span>
                            <div className="min-w-0">
                                <span className="text-[10px] font-semibold uppercase tracking-[0.1em]" style={{ color: "var(--aegis-text-muted)" }}>
                                    Proposed Action
                                </span>
                                <p className="text-base font-bold capitalize leading-snug" style={{ color: "var(--aegis-text)" }}>
                                    {action.type.replace("_", " ")}
                                    {action.amount ? ` — $${action.amount.toFixed(2)}` : ""}
                                </p>
                            </div>
                        </div>
                        <p className="text-[13px] leading-relaxed" style={{ color: "var(--aegis-text)" }}>
                            {action.description}
                        </p>
                    </div>

                    {/* Details Grid */}
                    <div className="grid grid-cols-2 gap-2.5">
                        {action.customer_name && (
                            <div className="metric-card">
                                <span className="text-[11px] block mb-0.5" style={{ color: "var(--aegis-text-muted)" }}>Customer</span>
                                <span className="text-[13px] font-semibold" style={{ color: "var(--aegis-text)" }}>{action.customer_name}</span>
                            </div>
                        )}
                        {action.customer_id && (
                            <div className="metric-card">
                                <span className="text-[11px] block mb-0.5" style={{ color: "var(--aegis-text-muted)" }}>Customer ID</span>
                                <span className="text-[13px] font-semibold font-mono" style={{ color: "var(--aegis-text)" }}>#{action.customer_id}</span>
                            </div>
                        )}
                    </div>

                    {/* Reason */}
                    <div className="metric-card">
                        <span className="text-[11px] block mb-1" style={{ color: "var(--aegis-text-muted)" }}>Agent Reasoning</span>
                        <p className="text-[13px] leading-relaxed" style={{ color: "var(--aegis-text-2)" }}>{action.reason}</p>
                    </div>
                </div>

                {/* Decision — deny holds the line, approve releases the action */}
                <div className="px-6 py-4" style={{ borderTop: "1px solid var(--aegis-border)", background: "var(--aegis-surface-2)" }}>
                    <div className="flex gap-2.5">
                        <button
                            ref={denyRef}
                            onClick={() => animateOut(() => onDeny("Manager denied the proposed action"))}
                            disabled={isLoading || closing}
                            className="btn-danger flex-1 flex items-center justify-center gap-2 disabled:opacity-50"
                        >
                            {isLoading ? <div className="spinner" /> : "✗"} Deny
                        </button>
                        <button
                            ref={approveRef}
                            onClick={() => animateOut(onApprove)}
                            disabled={isLoading || closing}
                            className="btn-success flex-[1.4] flex items-center justify-center gap-2 disabled:opacity-50"
                        >
                            {isLoading ? <div className="spinner" /> : "✓"} Approve &amp; Execute
                        </button>
                    </div>
                    <p className="text-[11px] mt-2.5 text-center" style={{ color: "var(--aegis-text-muted)" }}>
                        Approving executes immediately — <kbd className="px-1 py-px rounded text-[10px]" style={{ border: "1px solid var(--aegis-border-strong)" }}>Esc</kbd> denies without changes
                    </p>
                </div>
            </div>
        </div>
    );
}
