"use client";

import { useRef, useState, type KeyboardEvent } from "react";
import { ArrowRight, CornerDownLeft, LoaderCircle } from "lucide-react";
import { EDGE_CASES, SCENARIOS, type Preset } from "@/lib/presets";

export const MAX_CHARS = 1000;

interface ComposerProps {
    message: string;
    onChange: (v: string) => void;
    onSubmit: () => void;
    onPreset: (p: Preset) => void;
    busy: boolean;
    children?: React.ReactNode;
}

const TABS = [
    { id: "scenarios", label: "Scenarios", items: SCENARIOS },
    { id: "edge", label: "Edge cases", items: EDGE_CASES },
] as const;

export default function Composer({ message, onChange, onSubmit, onPreset, busy, children }: ComposerProps) {
    const [tab, setTab] = useState<(typeof TABS)[number]["id"]>("scenarios");
    const tabRefs = useRef<Array<HTMLButtonElement | null>>([]);
    const active = TABS.find((t) => t.id === tab)!;
    const over = message.length > MAX_CHARS;

    // Arrow keys move between tabs, per the WAI-ARIA tabs pattern.
    const onTabKey = (e: KeyboardEvent<HTMLButtonElement>, i: number) => {
        if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
        e.preventDefault();
        const next = (i + (e.key === "ArrowRight" ? 1 : -1) + TABS.length) % TABS.length;
        setTab(TABS[next].id);
        tabRefs.current[next]?.focus();
    };

    return (
        <section className="panel panel-compose" aria-labelledby="compose-heading">
            <div className="panel-head">
                <h2 id="compose-heading" className="panel-title">New ticket</h2>
                <span className="text-[12px] text-3">one click runs it</span>
            </div>

            <div className="panel-body compose-body">
                <div role="tablist" aria-label="Example tickets" className="segmented">
                    {TABS.map((t, i) => (
                        <button
                            key={t.id}
                            ref={(el) => { tabRefs.current[i] = el; }}
                            role="tab"
                            id={`tab-${t.id}`}
                            aria-selected={tab === t.id}
                            aria-controls={`panel-${t.id}`}
                            tabIndex={tab === t.id ? 0 : -1}
                            className="segment"
                            onClick={() => setTab(t.id)}
                            onKeyDown={(e) => onTabKey(e, i)}
                        >
                            {t.label} <span className="segment-count">{t.items.length}</span>
                        </button>
                    ))}
                </div>

                {/* The panel role lives on a wrapper: on the <ul> it would erase list semantics. */}
                <div role="tabpanel" id={`panel-${active.id}`} aria-labelledby={`tab-${active.id}`}>
                    <ul className="preset-list">
                        {active.items.map((p) => (
                            <li key={p.id}>
                                <button type="button" className="preset" disabled={busy} onClick={() => onPreset(p)} title={p.message}>
                                    <span className="min-w-0">
                                        <span className="preset-label">{p.label}</span>
                                        <span className="preset-hint">{p.hint}</span>
                                    </span>
                                    <ArrowRight size={14} className="preset-arrow" aria-hidden="true" />
                                </button>
                            </li>
                        ))}
                    </ul>
                </div>

                {children}
            </div>

            <form
                className="composer"
                onSubmit={(e) => {
                    e.preventDefault();
                    onSubmit();
                }}
            >
                <label htmlFor="ticket-input" className="sr-only">Support ticket</label>
                <textarea
                    id="ticket-input"
                    className="field ticket-input"
                    value={message}
                    onChange={(e) => onChange(e.target.value)}
                    onKeyDown={(e) => {
                        if (e.key === "Enter" && !e.shiftKey) {
                            e.preventDefault();
                            onSubmit();
                        }
                    }}
                    placeholder="Describe the support issue… e.g. “Customer #8 was double-charged $49 for Pro”"
                    disabled={busy}
                    rows={3}
                    aria-describedby="ticket-help"
                    title="Enter to run · Shift+Enter for a new line"
                    aria-invalid={over}
                />
                <div className="composer-foot">
                    <span id="ticket-help" className={`text-[12px] tnum ${over ? "text-fail" : "text-3"}`}>
                        {message.length}/{MAX_CHARS}
                    </span>
                    <button type="submit" className="btn btn-primary" disabled={busy || !message.trim() || over}>
                        {busy ? <LoaderCircle size={14} className="animate-spin" aria-hidden="true" /> : null}
                        {busy ? "Running" : "Run agents"}
                        {!busy && <CornerDownLeft size={13} className="opacity-70" aria-hidden="true" />}
                    </button>
                </div>
            </form>
        </section>
    );
}
