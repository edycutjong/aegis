import { Check, Search, BookOpen, Gavel, Split, X, Zap, Minus } from "lucide-react";
import type { ComponentType } from "react";
import { STAGES, type StageId, type StageState } from "@/lib/trace";

const STAGE_META: Record<StageId, { label: string; short: string; sub: string; Icon: ComponentType<{ size?: number; "aria-hidden"?: boolean }> }> = {
    Triage: { label: "Triage", short: "Triage", sub: "screen · classify", Icon: Split },
    Investigator: { label: "Investigator", short: "Query", sub: "SQL · self-heal", Icon: Search },
    Knowledge: { label: "Knowledge", short: "Docs", sub: "policy docs", Icon: BookOpen },
    Resolution: { label: "Resolution", short: "Propose", sub: "one action", Icon: Gavel },
    Gate: { label: "Human gate", short: "Gate", sub: "you decide", Icon: Minus },
    Execute: { label: "Execute", short: "Execute", sub: "hand off", Icon: Zap },
};

const STATE_WORDS: Record<StageState, string> = {
    pending: "waiting",
    active: "running",
    done: "done",
    failed: "stopped",
    skipped: "skipped",
    held: "holding for your decision",
    denied: "denied",
};

function NodeGlyph({ id, state }: { id: StageId; state: StageState }) {
    const { Icon } = STAGE_META[id];
    if (id === "Gate") return <span className="gate-bar" aria-hidden="true" />;
    if (state === "failed") return <X size={14} aria-hidden={true} />;
    if (state === "done" && id !== "Execute") return <Check size={14} aria-hidden={true} />;
    return <Icon size={14} aria-hidden={true} />;
}

/**
 * The pipeline as a rail: blue runs through the agents, amber holds at the
 * gate, green marks the action that actually executed.
 */
export default function PipelineRail({ stages }: { stages: Record<StageId, StageState> }) {
    return (
        <ol className="pipeline" aria-label="Agent pipeline">
            {STAGES.map((id, i) => {
                const state = stages[id];
                const meta = STAGE_META[id];
                const prev = i > 0 ? stages[STAGES[i - 1]] : null;
                const lit = prev !== null && prev !== "pending" && prev !== "skipped" && state !== "pending" && state !== "skipped";
                return (
                    <li key={id} className={`pipe-stage pipe-${id.toLowerCase()}`} data-state={state} aria-label={`${meta.label}: ${STATE_WORDS[state]}`}>
                        {i > 0 && <span className={`pipe-link ${lit ? "lit" : ""} ${state === "active" || state === "held" ? "flowing" : ""}`} aria-hidden="true" />}
                        <span className="pipe-node" aria-hidden="true">
                            <NodeGlyph id={id} state={state} />
                        </span>
                        <span className="pipe-label" aria-hidden="true">
                            <span className="pipe-name">
                                <span className="hidden sm:inline">{meta.label}</span>
                                <span className="sm:hidden">{meta.short}</span>
                            </span>
                            <span className="pipe-sub">{state === "held" ? "awaiting you" : meta.sub}</span>
                        </span>
                    </li>
                );
            })}
        </ol>
    );
}
