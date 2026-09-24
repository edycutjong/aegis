import { Database, ShieldAlert } from "lucide-react";
import type { ReactNode } from "react";
import type { SqlAttempt } from "@/lib/api";

const KEYWORDS = new Set(
    "SELECT FROM WHERE AND OR NOT IN IS NULL AS ON JOIN LEFT RIGHT INNER OUTER FULL GROUP BY ORDER HAVING LIMIT OFFSET DISTINCT COUNT SUM AVG MIN MAX CASE WHEN THEN ELSE END LIKE ILIKE BETWEEN DESC ASC UNION ALL WITH EXISTS INTERVAL NOW CURRENT_DATE COALESCE".split(" ")
);

const TOKEN = /('(?:[^']|'')*'|\b\d+(?:\.\d+)?\b|\b[A-Za-z_][A-Za-z0-9_]*\b)/g;

/** Light SQL highlighting: keywords, strings and numbers. No dependency needed. */
export function highlightSql(sql: string): ReactNode[] {
    return sql.split(TOKEN).map((part, i) => {
        if (i % 2 === 0) return part;
        if (part.startsWith("'")) return <span key={i} className="sql-str">{part}</span>;
        if (/^\d/.test(part)) return <span key={i} className="sql-num">{part}</span>;
        if (KEYWORDS.has(part.toUpperCase())) return <span key={i} className="sql-kw">{part}</span>;
        return part;
    });
}

const GUARD_PREFIX = "Blocked by SQL guard:";

function Outcome({ attempt }: { attempt: SqlAttempt }) {
    if (attempt.error?.startsWith(GUARD_PREFIX)) {
        return (
            <span className="chip chip-guard">
                <ShieldAlert size={11} aria-hidden="true" /> SQL guard blocked
            </span>
        );
    }
    if (attempt.error) return <span className="chip chip-fail">Failed</span>;
    if (attempt.rows === null) return <span className="chip chip-release">Running…</span>;
    return <span className="chip chip-ok tnum">{attempt.rows} {attempt.rows === 1 ? "row" : "rows"}</span>;
}

/**
 * Every query the Investigator wrote, in order. Failed attempts stay visible
 * with their error, so the self-healing loop (and the SQL guard) can be seen.
 */
export default function SqlTrace({ attempts }: { attempts: SqlAttempt[] }) {
    if (attempts.length === 0) return null;
    const blocked = attempts.filter((a) => a.error?.startsWith(GUARD_PREFIX)).length;
    return (
        <details className="sql-trace" open>
            <summary>
                <Database size={13} aria-hidden="true" />
                <span className="font-semibold text-1">SQL the agent wrote</span>
                <span className="text-3 tnum">
                    {attempts.length} {attempts.length === 1 ? "attempt" : "attempts"}
                    {blocked > 0 && ` · ${blocked} blocked by guard`}
                </span>
            </summary>
            <ol className="sql-attempts">
                {attempts.map((a, i) => (
                    <li key={i}>
                        <div className="sql-attempt-head">
                            <span className="text-3 tnum">
                                Attempt {i + 1}
                                {i > 0 && <span className="chip chip-heal ml-2">Self-heal {i}/3</span>}
                            </span>
                            <Outcome attempt={a} />
                        </div>
                        <pre className="sql-code">
                            <code>{highlightSql(a.query)}</code>
                        </pre>
                        {a.error && (
                            <p className={`sql-error ${a.error.startsWith(GUARD_PREFIX) ? "sql-error-guard" : ""}`}>{a.error}</p>
                        )}
                    </li>
                ))}
            </ol>
        </details>
    );
}
