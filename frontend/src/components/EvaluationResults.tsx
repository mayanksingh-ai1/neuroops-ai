import type { Comparison, Evaluation, Metric, Summary } from '../api/evaluation';

export const readable = (text: string) => text.replace(/_/g, ' ');
const score = (value: number | null) => value === null ? 'Not assessed' : `${Math.round(value * 100)}%`;

function MetricTable({ title, values }: { title: string; values: Record<string, Metric> }) {
  return <section><h4>{title}</h4><div className="eval-table-scroll"><table>
    <thead><tr><th>Metric</th><th>Score</th><th>Reason</th></tr></thead><tbody>
      {Object.entries(values).map(([name, metric]) => <tr key={name}>
        <td>{readable(name)}</td><td>{score(metric.score)}</td><td>{metric.reason}</td>
      </tr>)}
    </tbody></table></div></section>;
}

export function EvaluationResults({ evaluation }: { evaluation: Evaluation }) {
  return <article className="eval-results" aria-label="Automated evaluation">
    <h3>Automated evaluation · {evaluation.status}</h3>
    <p>{new Date(evaluation.created_at * 1000).toLocaleString()} · Rubric {String(evaluation.rubric.version ?? 'eval-v1')}</p>
    {evaluation.error_code && <p className="kb-error">Judge error: {readable(evaluation.error_code)}. Deterministic checks remain available.</p>}
    <MetricTable title="Deterministic checks — limited proxies" values={evaluation.deterministic} />
    <MetricTable title="LLM judgments — unverified assessments" values={evaluation.judged} />
    <details><summary>Evaluator and rubric</summary><pre>{JSON.stringify({ evaluator: evaluation.evaluator, rubric: evaluation.rubric }, null, 2)}</pre></details>
    <h4>Human review history</h4>
    {!evaluation.reviews.length && <p>No human reviews yet.</p>}
    {evaluation.reviews.map(item => <section key={item.id} className="eval-review">
      <p><strong>{item.reviewer_id}</strong> · {item.decision} · {new Date(item.created_at * 1000).toLocaleString()}</p>
      <p>{item.feedback}</p>
      {Object.entries(item.corrections).map(([name, correction]) => <p key={name}>
        Human correction — {readable(name)}: {score(correction.score)}. {correction.reason}
      </p>)}
    </section>)}
  </article>;
}

export function EvaluationSummary({ data }: { data: Summary }) {
  return <section className="panel p-6" aria-label="Evaluation dashboard">
    <h2>Measured evaluation activity</h2><p>{data.label}</p>
    <div className="eval-stat-grid">
      {[['Evaluations', data.evaluations], ['Distinct cases', data.distinct_cases], ['Completed', data.completed], ['Failed', data.failed]].map(([title, value]) =>
        <div key={title} className="eval-stat"><span>{title}</span><strong>{value}</strong></div>)}
    </div>
    {!data.evaluations ? <p>No evaluations match these filters. Create a case and run checks to begin.</p> : <>
      <h3>Metric distributions</h3><p>No combined quality score. Missing scores are excluded from means; repeated attempts are included.</p>
      <div className="eval-table-scroll"><table><thead><tr><th>Method / metric</th><th>Mean</th><th>Assessed</th><th>Not assessed</th><th>Zero / partial / full</th></tr></thead>
        <tbody>{data.metrics.map(item => <tr key={`${item.method}:${item.metric}`}>
          <td>{readable(item.method)} / {readable(item.metric)}</td><td>{score(item.mean)}</td><td>{item.assessed}</td><td>{item.not_assessed}</td>
          <td>{item.distribution.zero} / {item.distribution.partial} / {item.distribution.one}</td>
        </tr>)}</tbody></table></div>
      <div className="eval-two-columns"><section><h3>Common failure indicators</h3>
        {!data.common_failures.length && <p>No failure indicators in these results. This does not prove correctness or safety.</p>}
        <ul>{data.common_failures.map(item => <li key={item.type}>{readable(item.type)}: {item.count}</li>)}</ul>
      </section><section><h3>Supplied model labels</h3><ul>{data.models.map(item => <li key={item.model}>
        {item.model}: {item.evaluations} evaluations / {item.distinct_cases} cases
      </li>)}</ul></section></div>
    </>}
  </section>;
}

export function ComparisonResults({ comparison }: { comparison: Comparison }) {
  const preference = comparison.pairwise.preference;
  const preferred = comparison.items.find(item => item.case.id === preference);
  return <section className="panel p-6" aria-label="Model comparison">
    <h2>Response comparison</h2><p>{comparison.limitation}</p>
    <p>Pairwise judge: {readable(comparison.pairwise.status)}{preference ? ` · ${preferred ? `Preference for ${preferred.case.model} on this case only` : readable(preference)}` : ''}</p>
    {comparison.pairwise.error_code && <p className="kb-error">{readable(comparison.pairwise.error_code)}</p>}
    {comparison.pairwise.judgments?.map((judgment, index) => <p key={index}>Order {index + 1}: {judgment.reason}</p>)}
    <div className="eval-comparison-grid">{comparison.items.map(item => <section key={item.case.id} className="eval-comparison-card">
      <h3>{item.case.model}</h3><p>Supplied provider: {item.case.provider}</p><h4>Question</h4><p>{item.case.question}</p>
      <h4>Supplied response</h4><pre>{item.case.response}</pre>
      {item.evaluation ? <EvaluationResults evaluation={item.evaluation} /> : <p>Not evaluated. Run checks for this case to obtain metric results, then create a new comparison.</p>}
    </section>)}</div>
    <p>Comparison is an immutable snapshot. Later evaluations and reviews do not rewrite it.</p>
  </section>;
}
