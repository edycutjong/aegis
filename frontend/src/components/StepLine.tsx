import { Check, Info, ShieldAlert, TriangleAlert, Wrench, X } from "lucide-react";
import type { ParsedStep, Tone } from "@/lib/trace";
import { shortModel } from "@/lib/trace";

const TONE_ICON: Record<Tone, typeof Check> = {
    ok: Check,
    fail: X,
    warn: TriangleAlert,
    heal: Wrench,
    guard: ShieldAlert,
    info: Info,
};

const LONG_TEXT = 140;

const STATUS_RISK = new Set(["suspended", "cancelled"]);

function Chip({ children, tone = "neutral", mono = false }: { children: React.ReactNode; tone?: "neutral" | "release" | "hold" | "ok" | "fail" | "heal" | "guard"; mono?: boolean }) {
    return <span className={`chip chip-${tone} ${mono ? "font-mono" : ""}`}>{children}</span>;
}

/** Rich rendering for the step kinds we understand; plain text otherwise. */
function StepBody({ step }: { step: ParsedStep }) {
    const d = step.data;
    switch (step.kind) {
        case "screen_clean":
            return (
                <>
                    Screened the ticket for prompt injection: <strong>clean</strong>{d.score && <> <Chip mono>{d.score}</Chip></>}
                </>
            );
        case "screen_flagged":
            return (
                <span className="screen-flag">
                    <strong className="screen-flag-title">Prompt-injection screen flagged this ticket</strong>
                    <span className="flex flex-wrap gap-1.5 mt-1.5">
                        {d.flags.split(/,\s*/).map((f) => (
                            <Chip key={f} tone="fail" mono>{f}</Chip>
                        ))}
                        {d.score && <Chip mono>{d.score}</Chip>}
                    </span>
                    <span className="block mt-1.5 text-2">Whatever the agents propose, a human will have to sign off.</span>
                </span>
            );
        case "sql_blocked":
            return (
                <span className="block">
                    <Chip tone="guard">SQL guard blocked</Chip> <span className="text-3 tnum">attempt {d.attempt}/{d.max}</span>
                    {d.reason && <code className="step-code step-code-guard">{d.reason}</code>}
                </span>
            );
        case "intent":
            return (
                <>
                    Classified as <strong>{d.intent}</strong> <Chip mono>{d.confidence} confidence</Chip>
                </>
            );
        case "route": {
            const fast = step.raw.includes("⚡");
            return (
                <>
                    Routed to <Chip mono tone="release">{shortModel(d.model)}</Chip>{" "}
                    <span className="text-3">{fast ? "fast, low-cost lane" : "reasoning lane"}</span>
                </>
            );
        }
        case "customer":
            return (
                <>
                    Verified <strong>{d.name}</strong> <Chip mono>#{d.id}</Chip> <Chip>{d.plan}</Chip>{" "}
                    <Chip tone={STATUS_RISK.has(d.status) ? "fail" : "ok"}>{d.status}</Chip>
                </>
            );
        case "typo":
            return (
                <>
                    Corrected a typo: <del className="text-3">{d.from}</del> → <strong>{d.to}</strong> <Chip mono>{d.similarity} match</Chip>
                </>
            );
        case "sql":
            return <>Wrote a read-only SQL query</>;
        case "sql_rows":
            return (
                <>
                    Query returned <strong className="tnum">{d.rows} {d.rows === "1" ? "row" : "rows"}</strong>
                </>
            );
        case "sql_retry":
            return (
                <span className="block">
                    <Chip tone="heal">Self-heal {d.attempt}/{d.max}</Chip> SQL failed, rewriting the query
                    {d.error && <code className="step-code">{d.error}</code>}
                </span>
            );
        case "docs":
            return (
                <>
                    Read <strong className="tnum">{d.count}</strong> internal policy {d.count === "1" ? "doc" : "docs"}
                    {d.titles && (
                        <span className="flex flex-wrap gap-1.5 mt-1.5">
                            {d.titles.split(/,\s*/).map((t) => (
                                <Chip key={t}>{t}</Chip>
                            ))}
                        </span>
                    )}
                </>
            );
        case "proposal":
            return (
                <>
                    Proposed <Chip tone="hold" mono>{d.type}</Chip> {d.description}
                </>
            );
        case "auto":
            return (
                <>
                    <Chip tone="ok" mono>{d.type}</Chip> is non-destructive, so it skips the gate
                </>
            );
        case "decision":
            return d.decision === "approved" ? (
                <>
                    <strong>You approved</strong> the action{d.reason ? <span className="text-2">: {d.reason}</span> : null}
                </>
            ) : (
                <>
                    <strong>You denied</strong> the action{d.reason ? <span className="text-2">: {d.reason}</span> : null}
                </>
            );
        case "executed":
            return <>Released: {d.result}</>;
        case "summary":
            return <>Wrote the reply to the customer</>;
        default:
            // Provider errors can be kilobytes of JSON — keep the headline, fold the rest.
            if (step.text.length > LONG_TEXT) {
                return (
                    <details className="step-details">
                        <summary>{step.text.slice(0, LONG_TEXT).trimEnd()}…</summary>
                        <code className="step-code">{step.text}</code>
                    </details>
                );
            }
            return <>{step.text}</>;
    }
}

export default function StepLine({ step, at }: { step: ParsedStep; at?: number }) {
    const Icon = TONE_ICON[step.tone];
    return (
        <li className={`step step-${step.tone}`}>
            <span className="step-icon" aria-hidden="true">
                <Icon size={11} strokeWidth={2.75} />
            </span>
            <span className="sr-only">{step.tone === "fail" ? "Failed: " : step.tone === "warn" ? "Warning: " : step.tone === "guard" ? "Security control: " : ""}</span>
            <span className="step-text">
                <StepBody step={step} />
            </span>
            {at !== undefined && <span className="step-time tnum">+{(at / 1000).toFixed(1)}s</span>}
        </li>
    );
}
