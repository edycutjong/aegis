import { ApiError } from "./api";

export type NoticeKind = "rate_limited" | "offline" | "rejected" | "agent";

/** What the UI shows when a run cannot start or finish. */
export interface RunNotice {
    kind: NoticeKind;
    title: string;
    detail: string;
    retryAfterSeconds?: number | null;
}

/** Translate any thrown value from the API client into a human-readable notice. */
export function describeError(err: unknown): RunNotice {
    if (err instanceof ApiError) {
        if (err.status === 429) {
            return {
                kind: "rate_limited",
                title: "The live demo is catching its breath",
                detail: err.detail ?? "Too many tickets in a short window. Give it a minute and try again.",
                retryAfterSeconds: err.retryAfterSeconds,
            };
        }
        if (err.status === 0) {
            return {
                kind: "offline",
                title: "Can't reach the Aegis backend",
                detail: "The agent API isn't responding. It may be waking up from sleep — try again in a few seconds.",
            };
        }
        if (err.status === 422 || err.status === 400) {
            return {
                kind: "rejected",
                title: "The ticket was rejected",
                detail: err.detail ?? "Keep it under 1,000 characters and try again.",
            };
        }
        return {
            kind: "agent",
            title: "The agent hit a server error",
            detail: err.detail ?? err.message,
        };
    }
    return {
        kind: "agent",
        title: "Something went wrong",
        detail: err instanceof Error ? err.message : String(err),
    };
}

/** Format seconds as "45s", "3m 20s" or "2h 1m" for retry hints. */
export function formatWait(seconds: number): string {
    if (seconds < 60) return `${seconds}s`;
    if (seconds >= 3600) {
        const h = Math.floor(seconds / 3600);
        const m = Math.floor((seconds % 3600) / 60);
        return m ? `${h}h ${m}m` : `${h}h`;
    }
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return s ? `${m}m ${s}s` : `${m}m`;
}

