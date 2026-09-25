/**
 * Turns the backend's plain-text thought log into structured steps, and
 * derives which pipeline stage is running, done, held or skipped.
 *
 * The backend emits lines like:
 *   "✓ [Triage] Classified intent: billing (confidence: 99%)"
 *   "↪ [Resolution] gpt-4.1-mini unavailable, answered by backup openai/gpt-oss-120b"
 *   "✗ [Investigator] SQL retry (attempt 2/3): column \"x\" does not exist"
 * Everything here is pure so it can be tested without rendering.
 */

export type AgentId = "Triage" | "Investigator" | "Knowledge" | "Resolution";

export interface AgentMeta {
    id: AgentId;
    /** Short verb phrase shown under the agent name. */
    role: string;
    /** Identity hue — used for the avatar dot only, never for text. */
    color: string;
}

export const AGENTS: AgentMeta[] = [
    { id: "Triage", role: "Screen & classify", color: "#a78bfa" },
    { id: "Investigator", role: "Validate · SQL · self-heal", color: "#22d3ee" },
    { id: "Knowledge", role: "Search policy docs", color: "#f472b6" },
    { id: "Resolution", role: "Propose one action", color: "#60a5fa" },
];

const AGENT_IDS = new Set<string>(AGENTS.map((a) => a.id));

export type Tone = "ok" | "warn" | "fail" | "heal" | "guard" | "info";

export type StepKind =
    | "screen_clean"
    | "screen_flagged"
    | "sql_blocked"
    | "intent"
    | "backup"
    | "customer"
    | "typo"
    | "sql"
    | "sql_rows"
    | "sql_retry"
    | "docs"
    | "proposal"
    | "auto"
    | "decision"
    | "executed"
    | "summary"
    | "ambiguous"
    | "text";

export interface ParsedStep {
    raw: string;
    agent: AgentId | null;
    tone: Tone;
    kind: StepKind;
    text: string;
    /** Structured fields extracted for the richer renderings. */
    data: Record<string, string>;
}

const MARKERS: Record<string, Tone> = { "✓": "ok", "✗": "fail", "⚠": "warn", "⏸": "warn", "↪": "warn" };

const PATTERNS: Array<[StepKind, RegExp, string[]]> = [
    ["screen_clean", /^Input screen clean(?: \((.+)\))?/, ["score"]],
    ["screen_flagged", /^Input flagged: (.+?)(?: \(([^()]*)\))?(?: — .*)?$/, ["flags", "score"]],
    ["sql_blocked", /^SQL guard blocked query \(attempt (\d+)\/(\d+)\): ?(.*)$/, ["attempt", "max", "reason"]],
    ["intent", /^Classified intent: (\w+) \(confidence: (\d+%)\)/, ["intent", "confidence"]],
    ["backup", /^(\S+) unavailable, answered by backup (.+)$/, ["primary", "model"]],
    ["typo", /^Name typo detected: "(.+?)" → auto-corrected to "(.+?)" \(similarity: (\d+%)\)/, ["from", "to", "similarity"]],
    ["customer", /^Customer (?:validated|found by name): #(\d+) (.+?) \((\w+), (\w+)\)/, ["id", "name", "plan", "status"]],
    ["sql_retry", /^SQL retry \(attempt (\d+)\/(\d+)\): ?(.*)$/, ["attempt", "max", "error"]],
    ["sql_rows", /^SQL executed successfully — found (\d+) records?/, ["rows"]],
    ["sql", /^Generated SQL query/, []],
    ["docs", /^Found (\d+) relevant internal documents?(?:: (.+))?/, ["count", "titles"]],
    ["proposal", /^Proposed action: (\w+) — (.*)$/, ["type", "description"]],
    ["auto", /^Auto-approved: (\w+)/, ["type"]],
    ["decision", /^Human decision: (approved|denied)(?: — (.*))?$/, ["decision", "reason"]],
    ["executed", /^Action executed: (.*)$/, ["result"]],
    ["summary", /^Generated resolution summary/, []],
];

/** Parse one raw thought-log line. */
export function parseStep(raw: string): ParsedStep {
    let rest = raw.trim();
    let tone: Tone = "info";

    const marker = rest.charAt(0);
    if (MARKERS[marker]) {
        tone = MARKERS[marker];
        rest = rest.slice(1).trim();
    } else if (/^🛡/u.test(rest)) {
        // The shield marks a security control acting: input screen or SQL guard.
        tone = "guard";
        rest = rest.replace(/^🛡\uFE0F?\s*/u, "");
    } else if (rest.startsWith("→")) {
        rest = rest.slice(1).trim();
    }

    let agent: AgentId | null = null;
    const tag = rest.match(/^\[(\w+)\]\s*(.*)$/);
    if (tag && AGENT_IDS.has(tag[1])) {
        agent = tag[1] as AgentId;
        rest = tag[2];
    }

    for (const [kind, re, keys] of PATTERNS) {
        const m = rest.match(re);
        if (m) {
            const data: Record<string, string> = {};
            keys.forEach((k, i) => {
                if (m[i + 1] !== undefined) data[k] = m[i + 1];
            });
            // A retried query is the self-heal loop working, not a failure.
            const finalTone = kind === "sql_retry" ? "heal" : tone;
            return { raw, agent, tone: finalTone, kind, text: rest, data };
        }
    }
    // An ambiguous name pauses for a human choice — it's a hold, not a failure.
    if (/^Ambiguous name/.test(rest)) return { raw, agent, tone: "warn", kind: "ambiguous", text: rest, data: {} };
    return { raw, agent, tone, kind: "text", text: rest, data: {} };
}

export interface StepGroup {
    agent: AgentId | null;
    steps: Array<ParsedStep & { index: number }>;
}

/**
 * Group consecutive steps by agent. Untagged lines (e.g. the model-routing
 * note) belong to whichever agent spoke last.
 */
export function groupSteps(thoughts: string[]): StepGroup[] {
    const groups: StepGroup[] = [];
    thoughts.forEach((raw, index) => {
        const step = { ...parseStep(raw), index };
        const last = groups[groups.length - 1];
        const agent = step.agent ?? last?.agent ?? null;
        if (last && last.agent === agent) {
            last.steps.push(step);
        } else {
            groups.push({ agent, steps: [step] });
        }
    });
    return groups;
}

export type StageId = AgentId | "Gate" | "Execute";
export type StageState = "pending" | "active" | "done" | "failed" | "skipped" | "held" | "denied";

export const STAGES: StageId[] = ["Triage", "Investigator", "Knowledge", "Resolution", "Gate", "Execute"];

/** Run status as tracked by the page. */
export type RunStatus =
    | "idle"
    | "processing"
    | "awaiting_approval"
    | "releasing"
    | "denying"
    | "completed"
    | "cached"
    | "disambiguation"
    | "error";

const TERMINAL: RunStatus[] = ["completed", "cached", "disambiguation"];

/** Derive every pipeline stage's state from the log and the run status. */
export function derivePipeline(thoughts: string[], status: RunStatus): Record<StageId, StageState> {
    const steps = thoughts.map(parseStep);
    const seen: AgentId[] = [];
    const failed = new Set<AgentId>();
    let lastAgent: AgentId | null = null;
    let pausedAt: AgentId | null = null;

    for (const s of steps) {
        const agent: AgentId | null = s.agent ?? lastAgent;
        if (!agent) continue;
        if (!seen.includes(agent)) seen.push(agent);
        if (s.tone === "fail" && s.kind !== "decision") failed.add(agent);
        if (s.kind === "ambiguous") pausedAt = agent;
        lastAgent = agent;
    }

    const proposal = steps.find((s) => s.kind === "proposal");
    const decision = steps.find((s) => s.kind === "decision");
    const auto = steps.some((s) => s.kind === "auto");
    const executed = steps.some((s) => s.kind === "executed");

    const result = {} as Record<StageId, StageState>;
    if (steps.length === 0) {
        for (const id of STAGES) result[id] = "pending";
        if (status === "processing") result.Triage = "active";
        return result;
    }
    const finished = TERMINAL.includes(status) || status === "awaiting_approval" || status === "releasing" || status === "denying";

    for (const a of AGENTS) {
        const id = a.id;
        if (failed.has(id)) result[id] = "failed";
        else if (!seen.includes(id)) {
            result[id] = finished ? "skipped" : "pending";
        } else if (status === "processing" && id === lastAgent) result[id] = "active";
        else if (status === "error" && id === lastAgent) result[id] = "failed";
        else result[id] = "done";
    }

    if (status === "disambiguation" && pausedAt) result[pausedAt] = "held";

    // Resolution keeps working after the gate (it writes the summary), but the
    // gate is the story there — so once the gate is involved Resolution is done.
    if (status === "awaiting_approval" || status === "releasing" || status === "denying") result.Resolution = "done";

    if (status === "awaiting_approval") result.Gate = "held";
    else if (status === "releasing" || status === "denying") result.Gate = "active";
    else if (decision?.data.decision === "denied") result.Gate = "denied";
    else if (decision) result.Gate = "done";
    else if (auto) result.Gate = "skipped";
    else if (TERMINAL.includes(status) || status === "error") result.Gate = proposal ? "pending" : "skipped";
    else result.Gate = "pending";

    if (executed || (decision?.data.decision === "approved" && TERMINAL.includes(status)) || (auto && TERMINAL.includes(status))) result.Execute = "done";
    else if (status === "releasing") result.Execute = "active";
    else if (TERMINAL.includes(status) || result.Gate === "denied") result.Execute = "skipped";
    else result.Execute = "pending";

    return result;
}

/** Map a tracker step name (e.g. "write_sql") to the agent that ran it. */
export function agentForStep(step: string): AgentId | null {
    if (step.startsWith("classify")) return "Triage";
    if (step.includes("sql") || step.startsWith("validate")) return "Investigator";
    if (step.includes("doc")) return "Knowledge";
    if (step.startsWith("propose") || step.startsWith("generate") || step.startsWith("execute")) return "Resolution";
    return null;
}

/**
 * "models/gemini-2.5-flash" → "gemini-2.5-flash", "openai/gpt-oss-20b" → "gpt-oss-20b",
 * "gpt-4.1-mini-2025-04-14" → "gpt-4.1-mini" (dated snapshot ids).
 */
export function shortModel(model: string): string {
    return model.replace(/^(models|openai|meta-llama|google|anthropic)\//, "").replace(/-\d{4}-\d{2}-\d{2}$/, "");
}
