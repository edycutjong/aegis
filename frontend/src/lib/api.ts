/**
 * Aegis API Client — Communicates with FastAPI backend
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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
    recent_requests: Array<{
        thread_id: string;
        total_cost_usd: number;
        total_tokens: number;
        duration_seconds: number;
        models_used: Record<string, number>;
        cache_hit: boolean;
    }>;
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
    const res = await fetch(`${API_URL}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
    });
    if (!res.ok) throw new Error(`Chat failed: ${res.statusText}`);
    return res.json();
}

/** Get current thread state */
export async function getThread(threadId: string): Promise<ThreadState> {
    const res = await fetch(`${API_URL}/api/thread/${threadId}`);
    if (!res.ok) throw new Error(`Thread fetch failed: ${res.statusText}`);
    return res.json();
}

/** Approve or deny an action */
export async function approveAction(
    threadId: string,
    approved: boolean,
    reason: string = ""
): Promise<ApprovalResponse> {
    const res = await fetch(`${API_URL}/api/approve/${threadId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ approved, reason }),
    });
    if (!res.ok) throw new Error(`Approval failed: ${res.statusText}`);
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
    onDisambiguation?: (candidates: CustomerCandidate[], response: string) => void
): EventSource {
    const es = new EventSource(`${API_URL}/api/stream/${threadId}`);

    es.addEventListener("thought", (e) => {
        const data = JSON.parse(e.data);
        onThought(data.step);
    });

    es.addEventListener("approval_required", (e) => {
        const data = JSON.parse(e.data);
        onApprovalRequired(data.action);
        es.close();
    });

    es.addEventListener("completed", (e) => {
        const data = JSON.parse(e.data);
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
