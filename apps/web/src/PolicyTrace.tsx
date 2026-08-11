import type { PolicyStep } from "./types";

export default function PolicyTrace({ steps }: { steps: PolicyStep[] }) {
  const recent = steps.slice(-6).reverse();
  const latest = steps.at(-1);
  const mean = steps.length ? steps.reduce((sum, step) => sum + step.decision_ms, 0) / steps.length : 0;
  return <section className="policy-panel"><div className="section-title"><span>Policy trace</span><small>OBSERVATION → ACTION · 10 HZ</small></div><div className="policy-summary"><div><small>Decisions</small><strong>{steps.length}</strong></div><div><small>Mean latency</small><strong>{mean.toFixed(3)} ms</strong></div><div><small>Grasp</small><strong>{latest?.observation.grasp_qualified ? "QUALIFIED" : latest?.action.request_grasp ? "ATTEMPTING" : "—"}</strong></div><div><small>Target</small><strong>{latest ? `${latest.action.target_x.toFixed(1)}, ${latest.action.target_y.toFixed(1)}` : "—"}</strong></div></div><div className="policy-table"><div className="policy-table-head"><span>STEP</span><span>OBSERVATION</span><span>ACTION</span><span>LATENCY</span></div>{recent.map(step => <div key={step.sequence}><time>{step.sequence}</time><span>pose {step.observation.robot_x.toFixed(1)}, {step.observation.robot_y.toFixed(1)} · {step.observation.linear_speed_m_s.toFixed(2)} m/s</span><span>target {step.action.target_x.toFixed(1)}, {step.action.target_y.toFixed(1)}{step.action.request_grasp ? " · GRASP" : ""}</span><i>{step.decision_ms.toFixed(3)} ms</i></div>)}</div></section>;
}
