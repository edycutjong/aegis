import type { RecentRequest } from "@/lib/api";
import { AGENTS, agentForStep, shortModel } from "@/lib/trace";

const STEP_LABELS: Record<string, string> = {
    classify_intent: "Classify intent",
    write_sql: "Write SQL",
    fix_sql: "Repair SQL",
    search_docs: "Search docs",
    propose_action: "Propose action",
    generate_response: "Write reply",
};

function usd(n: number): string {
    if (n === 0) return "—";
    if (n < 0.0001) return "<$0.0001";
    return n < 0.01 ? `$${n.toFixed(4)}` : `$${n.toFixed(3)}`;
}

/**
 * Per-run receipt from the backend tracker: every LLM call, the model it was
 * routed to, its tokens and its cost. This is where model routing becomes
 * visible — cheap models on the easy steps, the smart one where it matters.
 */
export default function RunReceipt({ receipt }: { receipt: RecentRequest }) {
    const steps = receipt.steps ?? [];
    return (
        <section className="receipt" aria-label="Run receipt">
            <div className="receipt-head">
                <p className="eyebrow text-3">Run receipt</p>
                <dl className="receipt-totals">
                    <div>
                        <dt>Wall time</dt>
                        <dd className="tnum">{receipt.duration_seconds.toFixed(1)}s</dd>
                    </div>
                    {receipt.hitl_wait_seconds != null && (
                        <div>
                            <dt>Held for you</dt>
                            <dd className="tnum text-hold">{receipt.hitl_wait_seconds.toFixed(1)}s</dd>
                        </div>
                    )}
                    <div>
                        <dt>Tokens</dt>
                        <dd className="tnum">{receipt.total_tokens.toLocaleString("en-US")}</dd>
                    </div>
                    <div>
                        <dt>LLM cost</dt>
                        <dd className="tnum">{usd(receipt.total_cost_usd)}</dd>
                    </div>
                </dl>
            </div>
            {steps.length > 0 && (
                <table className="receipt-table">
                    <thead>
                        <tr>
                            <th scope="col">LLM call</th>
                            <th scope="col">Model</th>
                            <th scope="col" className="text-right col-tokens">Tokens</th>
                            <th scope="col" className="text-right">Cost</th>
                        </tr>
                    </thead>
                    <tbody>
                        {steps.map((s, i) => {
                            const agent = AGENTS.find((a) => a.id === agentForStep(s.step));
                            return (
                                <tr key={`${s.step}-${i}`}>
                                    <td>
                                        <span className="agent-dot" style={{ background: agent?.color ?? "var(--text-3)" }} aria-hidden="true" />
                                        {STEP_LABELS[s.step] ?? s.step}
                                    </td>
                                    <td className="font-mono">{shortModel(s.model)}</td>
                                    <td className="text-right tnum col-tokens">{(s.prompt_tokens + s.completion_tokens).toLocaleString("en-US")}</td>
                                    <td className="text-right tnum">{usd(s.cost_usd)}</td>
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            )}
        </section>
    );
}
