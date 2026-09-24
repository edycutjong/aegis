import { ArrowUpRight } from "lucide-react";

export const REPO_URL = "https://github.com/edycutjong/aegis";

/**
 * The mark: a payload arrested on its rail by a gate bar it has not crossed.
 * Deliberately not a shield — Aegis pauses, it doesn't defend.
 */
export function BrandMark({ size = 28 }: { size?: number }) {
    return (
        <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true" className="shrink-0">
            <rect x="0.5" y="0.5" width="31" height="31" rx="8.5" fill="#0d1220" stroke="rgba(255,255,255,0.14)" />
            <line x1="5" y1="16" x2="13" y2="16" stroke="#3b82f6" strokeOpacity="0.6" strokeWidth="2" strokeLinecap="round" />
            <circle cx="14" cy="16" r="6.2" fill="none" stroke="#f59e0b" strokeWidth="1.6" />
            <circle cx="14" cy="16" r="3.6" fill="#3b82f6" />
            <rect x="21.5" y="8" width="3" height="16" rx="1.5" fill="#f59e0b" />
            <line x1="27" y1="16" x2="28.5" y2="16" stroke="#64748b" strokeWidth="2" strokeLinecap="round" />
        </svg>
    );
}

export type BackendState = "connecting" | "up" | "down";

const STATUS_COPY: Record<BackendState, { label: string; title: string }> = {
    connecting: { label: "Connecting", title: "Checking the agent API…" },
    up: { label: "Live", title: "Agent API is up — runs use real LLMs and a real database" },
    down: { label: "Offline", title: "Agent API is unreachable" },
};

export default function TopBar({ backend }: { backend: BackendState }) {
    const status = STATUS_COPY[backend];
    return (
        <header className="topbar">
            <div className="flex items-center gap-3 min-w-0">
                <BrandMark size={30} />
                <h1 className="wordmark" aria-label="Aegis">
                    Aeg<span className="wordmark-gate">i</span>s
                </h1>
                <span className="topbar-divider hidden sm:block" aria-hidden="true" />
                <span className="hidden sm:block text-[13px] truncate text-3">
                    Multi-agent support desk with a human approval gate
                </span>
            </div>
            <div className="flex items-center gap-2 shrink-0">
                <span className={`status-pill status-${backend}`} title={status.title} role="status" aria-live="polite">
                    <span className="status-dot" aria-hidden="true" />
                    <span className="sr-only">Backend status: </span>
                    {status.label}
                </span>
                <a href={REPO_URL} target="_blank" rel="noreferrer" className="btn-ghost" aria-label="Source code on GitHub (opens in a new tab)">
                    <svg width="15" height="15" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
                        <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" />
                    </svg>
                    <span className="hidden sm:inline">Source</span>
                    <ArrowUpRight size={13} className="hidden sm:inline opacity-60" aria-hidden="true" />
                </a>
            </div>
        </header>
    );
}
