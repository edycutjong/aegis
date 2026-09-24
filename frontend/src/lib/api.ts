/**
 * Aegis API Client — Communicates with FastAPI backend
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/**
 * A failed API call, carrying what the UI needs to explain it:
 * `status` is 0 when the backend could not be reached at all, and `detail`
 * is the FastAPI `{"detail": "..."}` message when the server sent one.
 */
export class ApiError extends Error {
    readonly status: number;
    readonly detail: string | null;
    readonly retryAfterSeconds: number | null;

    constructor(message: string, status: number, detail: string | null = null, retryAfterSeconds: number | null = null) {
        super(message);
        this.name = "ApiError";
        this.status = status;
        this.detail = detail;
        this.retryAfterSeconds = retryAfterSeconds;
    }
}

/** Build an ApiError from a non-ok response, reading `detail` and `Retry-After` when present. */
async function toApiError(res: Response, label: string): Promise<ApiError> {
    let detail: string | null = null;
    try {
        const body = await res.json();
        if (typeof body?.detail === "string") detail = body.detail;
    } catch {
        // Non-JSON error body — fall back to the status text.
    }
    const retryHeader = res.headers?.get?.("Retry-After");
    const retry = retryHeader ? Number.parseInt(retryHeader, 10) : NaN;
    return new ApiError(`${label}: ${res.statusText}`, res.status, detail, Number.isFinite(retry) ? retry : null);
}

/** fetch() that turns network failures into ApiError(status 0). */
async function send(url: string, init: RequestInit | undefined, label: string): Promise<Response> {
    try {
        return init ? await fetch(url, init) : await fetch(url);
    } catch {
        throw new ApiError(`${label}: backend unreachable`, 0);
    }
}

export interface ChatResponse {
    thread_id: string;
    status: "processing" | "awaiting_approval" | "completed" | "cached" | "error";
    cache_hit: boolean;
}

export interface ApprovalResponse {
    thread_id: string;
    status: string;
    result: string | null;
}

export interface ActionProposal {
    type: string;
    amount: number | null;
    customer_id: number | null;
    customer_name: string;
    description: string;
    reason: string;
}

export interface CustomerCandidate {
    id: number;
    name: string;
    email?: string;
    plan?: string;
    status?: string;
}

export interface ThreadState {
    message: string;
    status: string;
    thought_log: string[];
    proposed_action: ActionProposal | null;
    final_response: string | null;
    customer_candidates?: CustomerCandidate[] | null;
    sql_attempts?: SqlAttempt[];
}

/** One SQL query the Investigator wrote, and what happened when it ran. */
export interface SqlAttempt {
    query: string;
    /** Database error, or "Blocked by SQL guard: …" when the guard refused it. */
    error: string | null;
    rows: number | null;
}

export interface AgentMetrics {
    total_requests: number;
    avg_cost_usd: number;
    avg_duration_seconds: number;
    total_cost_usd: number;
    total_tokens: number;
    model_distribution: Record<string, number>;
    hitl_approval_rate: number | null;
    avg_hitl_wait_seconds: number | null;
    cost_saved_by_cache: number;
    recent_requests: RecentRequest[];
}

/** One LLM call inside a run, as recorded by the backend tracker. */
export interface RequestStep {
    step: string;
    model: string;
    prompt_tokens: number;
    completion_tokens: number;
    cost_usd: number;
    timestamp: number;
}

/** A completed run's receipt from /api/metrics. */
export interface RecentRequest {
    thread_id: string;
    total_cost_usd: number;
    total_tokens: number;
    duration_seconds: number;
    models_used: Record<string, number>;
    cache_hit: boolean;
    steps?: RequestStep[];
    approved?: boolean | null;
    hitl_wait_seconds?: number | null;
}

export interface CacheMetrics {
    hits: number;
    misses: number;
    total_requests: number;
    hit_rate_percent: number;
    connected: boolean;
}

export interface Metrics {
    agent_metrics: AgentMetrics;
    cache_metrics: CacheMetrics;
}

/** Start a new agent workflow */
export async function startChat(message: string): Promise<ChatResponse> {
    const res = await send(`${API_URL}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
    }, "Chat failed");
    if (!res.ok) throw await toApiError(res, "Chat failed");
    return res.json();
}

/** Get current thread state */
export async function getThread(threadId: string): Promise<ThreadState> {
    const res = await send(`${API_URL}/api/thread/${threadId}`, undefined, "Thread fetch failed");
    if (!res.ok) throw await toApiError(res, "Thread fetch failed");
    return res.json();
}

/** Approve or deny an action */
export async function approveAction(
    threadId: string,
    approved: boolean,
    reason: string = ""
): Promise<ApprovalResponse> {
    const res = await send(`${API_URL}/api/approve/${threadId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ approved, reason }),
    }, "Approval failed");
    if (!res.ok) throw await toApiError(res, "Approval failed");
    return res.json();
}

/** Get observability metrics */
export async function getMetrics(): Promise<Metrics> {
    const res = await fetch(`${API_URL}/api/metrics`);
    if (!res.ok) throw new Error(`Metrics fetch failed: ${res.statusText}`);
    return res.json();
}

/** Clear semantic cache */
export async function clearCache(): Promise<{ status: string; keys_deleted: number }> {
    const res = await fetch(`${API_URL}/api/cache`, { method: "DELETE" });
    if (!res.ok) throw new Error(`Cache clear failed: ${res.statusText}`);
    return res.json();
}

/** Database status types */
export interface TableStatus {
    count: number;
    latest?: string | null;
    error?: string;
}
export type DbStatus = Record<string, TableStatus>;

/** Get database record counts and freshness */
export async function getDbStatus(): Promise<DbStatus> {
    const res = await fetch(`${API_URL}/api/db-status`);
    if (!res.ok) throw new Error(`DB status fetch failed: ${res.statusText}`);
    return res.json();
}

/** Get rows from a database table */
export async function getTableData(table: string): Promise<{ table: string; rows: Record<string, unknown>[] }> {
    const res = await fetch(`${API_URL}/api/tables/${table}`);
    if (!res.ok) throw new Error(`Table fetch failed: ${res.statusText}`);
    return res.json();
}

/** Create SSE connection to stream agent thoughts */
export function connectSSE(
    threadId: string,
    onThought: (step: string) => void,
    onApprovalRequired: (action: ActionProposal) => void,
    onCompleted: (response: string, thoughtLog: string[]) => void,
    onError: (error: string) => void,
    onDisambiguation?: (candidates: CustomerCandidate[], response: string) => void,
    onSql?: (attempts: SqlAttempt[]) => void
): EventSource {
    const es = new EventSource(`${API_URL}/api/stream/${threadId}`);

    es.addEventListener("thought", (e) => {
        const data = JSON.parse(e.data);
        onThought(data.step);
    });

    const emitSql = (attempts: SqlAttempt[] | undefined) => {
        if (attempts && onSql) onSql(attempts);
    };

    es.addEventListener("sql", (e) => {
        emitSql(JSON.parse(e.data).attempts);
    });

    es.addEventListener("approval_required", (e) => {
        const data = JSON.parse(e.data);
        emitSql(data.sql_attempts);
        onApprovalRequired(data.action);
        es.close();
    });

    es.addEventListener("completed", (e) => {
        const data = JSON.parse(e.data);
        emitSql(data.sql_attempts);
        if (data.customer_candidates && data.customer_candidates.length > 0 && onDisambiguation) {
            onDisambiguation(data.customer_candidates, data.response);
        } else {
            onCompleted(data.response, data.thought_log);
        }
        es.close();
    });

    es.addEventListener("error", (e) => {
        if (e instanceof MessageEvent) {
            const data = JSON.parse(e.data);
            onError(data.error);
        } else {
            onError("Connection lost");
        }
        es.close();
    });

    return es;
}

/** Trace types from /api/traces */
export interface TraceChildRun {
    id: string;
    name: string;
    status: string;
    latency_ms: number;
    total_tokens: number;
    model: string;
    total_cost: number;
}

export interface TraceRun {
    id: string;
    name: string;
    status: string;
    latency_ms: number;
    total_tokens: number;
    total_cost: number;
    start_time: string | null;
    child_runs: TraceChildRun[];
}

export interface TracesResponse {
    traces: TraceRun[];
    error: string | null;
}

/** Fetch recent LangSmith traces */
export async function getTraces(): Promise<TracesResponse> {
    const res = await fetch(`${API_URL}/api/traces`);
    if (!res.ok) throw new Error(`Traces fetch failed: ${res.statusText}`);
    return res.json();
}

/** Tracing status from /api/tracing-status */
export interface TracingStatus {
    enabled: boolean;
    project: string;
    connected: boolean;
}

/** Check if LangSmith tracing is enabled */
export async function getTracingStatus(): Promise<TracingStatus> {
    const res = await fetch(`${API_URL}/api/tracing-status`);
    if (!res.ok) throw new Error(`Tracing status failed: ${res.statusText}`);
    return res.json();
}
