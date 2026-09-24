"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowUpCircle, Ban, CircleDollarSign, Coins, LoaderCircle, LockOpen, ShieldAlert, Siren, Zap } from "lucide-react";
import type { ComponentType } from "react";
import type { ActionProposal } from "@/lib/api";

interface ApprovalGateProps {
    action: ActionProposal;
    onApprove: (note: string) => void;
    onDeny: (reason: string) => void;
    isLoading: boolean;
    /** Which decision is in flight, so the right button shows progress. */
    pending?: "approve" | "deny" | null;
}

export const DEFAULT_DENY_REASON = "Manager denied the proposed action";
export const ESCAPE_DENY_REASON = "Manager dismissed the approval request";

type IconType = ComponentType<{ size?: number; "aria-hidden"?: boolean; "data-testid"?: string }>;

const ACTIONS: Record<string, { title: string; Icon: IconType }> = {
    refund: { title: "Refund", Icon: CircleDollarSign },
    credit: { title: "Account credit", Icon: Coins },
    tier_change: { title: "Change plan", Icon: ArrowUpCircle },
    suspend: { title: "Suspend account", Icon: Ban },
    reactivate: { title: "Reactivate account", Icon: LockOpen },
    escalate: { title: "Escalate to a specialist", Icon: Siren },
};

function actionMeta(type: string) {
    return ACTIONS[type] ?? { title: type.replace(/_/g, " "), Icon: Zap };
}

const money = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });

/**
 * The centrepiece: the agent has finished its work and stopped one step short
 * of executing. Nothing moves until a person decides. Focus lands on Deny —
 * the safe choice — and Escape takes the fail-safe path too.
 */
export default function ApprovalGate({ action, onApprove, onDeny, isLoading, pending = null }: ApprovalGateProps) {
    const [note, setNote] = useState("");
    const rootRef = useRef<HTMLElement>(null);
    const denyRef = useRef<HTMLButtonElement>(null);
    const meta = actionMeta(action.type);

    useEffect(() => {
        rootRef.current?.scrollIntoView?.({ behavior: "smooth", block: "start" });
        denyRef.current?.focus({ preventScroll: true });
    }, []);

    const deny = (fallback: string) => onDeny(note.trim() || fallback);

    return (
        <section
            ref={rootRef}
            className="gate-card"
            role="region"
            aria-labelledby="gate-title"
            aria-describedby="gate-desc"
            onKeyDown={(e) => {
                if (e.key === "Escape" && !isLoading) {
                    e.preventDefault();
                    deny(ESCAPE_DENY_REASON);
                }
            }}
        >
            <div className="gate-rail" aria-hidden="true">
                <span className="gate-rail-track" />
                <span className="gate-rail-run" />
                <span className="gate-rail-payload" />
                <span className="gate-rail-bar" />
                <span className="gate-rail-beyond" />
            </div>

            <div className="gate-body">
                <p className="eyebrow text-hold">
                    <span className="gate-pulse" aria-hidden="true" />
                    Held at the gate · nothing has executed
                </p>

                <div className="flex items-start gap-3.5 mt-3">
                    <span className="gate-icon">
                        <meta.Icon size={20} aria-hidden={true} data-testid={`action-icon-${action.type}`} />
                    </span>
                    <div className="min-w-0 flex-1">
                        <h3 id="gate-title" className="gate-title">
                            {meta.title}
                            {action.amount != null && action.amount > 0 && (
                                <span className="gate-amount tnum">{money.format(action.amount)}</span>
                            )}
                        </h3>
                        <p className="text-[13px] text-2 mt-0.5">
                            {action.customer_name && action.customer_name !== "Not Found" ? action.customer_name : "Unverified customer"}
                            {action.customer_id != null && <span className="font-mono text-3"> · #{action.customer_id}</span>}
                        </p>
                    </div>
                </div>

                {action.description.includes("flagged by input screening") && (
                    <p className="gate-flag">
                        <ShieldAlert size={15} aria-hidden="true" className="shrink-0 mt-0.5" />
                        <span>
                            <strong>Flagged by the prompt-injection screen.</strong> The agents were not allowed to act on this ticket
                            by themselves, so it is escalated to you.
                        </span>
                    </p>
                )}

                <p id="gate-desc" className="text-[14px] leading-relaxed text-1 mt-4">{action.description}</p>

                <div className="gate-reason">
                    <p className="eyebrow text-3 mb-1.5">Why the agent wants this</p>
                    <p className="text-[13px] leading-relaxed text-2">{action.reason}</p>
                </div>

                <label htmlFor="gate-note" className="eyebrow text-3 block mt-4 mb-1.5">
                    Note for the audit log <span className="normal-case tracking-normal font-normal">(optional)</span>
                </label>
                <input
                    id="gate-note"
                    className="field"
                    value={note}
                    onChange={(e) => setNote(e.target.value)}
                    placeholder="e.g. Confirmed duplicate charge on the invoice"
                    disabled={isLoading}
                    maxLength={300}
                />

                <div className="gate-actions">
                    <button ref={denyRef} type="button" className="btn btn-deny" onClick={() => deny(DEFAULT_DENY_REASON)} disabled={isLoading}>
                        {isLoading && pending === "deny" ? <LoaderCircle size={15} className="animate-spin" aria-hidden={true} /> : null}
                        {isLoading && pending === "deny" ? "Denying…" : "Deny"}
                    </button>
                    <button type="button" className="btn btn-release" onClick={() => onApprove(note.trim())} disabled={isLoading}>
                        {isLoading && pending === "approve" ? <LoaderCircle size={15} className="animate-spin" aria-hidden={true} /> : null}
                        {isLoading && pending === "approve" ? "Releasing…" : "Approve & execute"}
                    </button>
                </div>
                <p className="text-[12px] text-3 mt-3">
                    Demo safety: approved actions are handed off as recommendations; the database is read-only.
                    <span className="hidden sm:inline"> <kbd className="kbd">Esc</kbd> denies.</span>
                </p>
            </div>
        </section>
    );
}
