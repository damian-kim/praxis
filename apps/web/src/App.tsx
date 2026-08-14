import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import type { Batch, Comparison, EngineInfo, EvaluationSuite, EvidenceVerification, Experiment, Health, PolicyStep, Run, Scenario, ScenarioInfo, SuiteEvaluation } from "./types";
import Telemetry from "./Telemetry";
import PolicyTrace from "./PolicyTrace";
import ExperimentPanel from "./ExperimentPanel";

const WorldView3D = lazy(() => import("./WorldView3D"));

const activeStatuses = new Set(["queued", "provisioning", "loading", "running", "cancelling", "finalizing"]);

async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(path, options);
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return response.json();
}

function Status({ run }: { run: Run }) {
  return <span className={`status ${run.status}`}>{run.status.replace("_", " ")}</span>;
}

interface Check {
  id: string; actual: number | boolean; operator: string; limit: number | boolean; unit: string;
  passed: boolean; source: string; calibration_status: string; rationale: string;
}

export default function App() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [batches, setBatches] = useState<Batch[]>([]);
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [selectedExperimentId, setSelectedExperimentId] = useState<string | null>(null);
  const [suites, setSuites] = useState<EvaluationSuite[]>([]);
  const [suiteEvaluations, setSuiteEvaluations] = useState<SuiteEvaluation[]>([]);
  const [selectedSuiteId, setSelectedSuiteId] = useState("warehouse_smoke");
  const [scenarios, setScenarios] = useState<ScenarioInfo[]>([]);
  const [scenarioId, setScenarioId] = useState("warehouse_v0");
  const [health, setHealth] = useState<Health>();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<Run | null>(null);
  const [scenario, setScenario] = useState<Scenario>();
  const [engines, setEngines] = useState<EngineInfo[]>([]);
  const [engineId, setEngineId] = useState("mujoco_v1");
  const [policy, setPolicy] = useState("baseline_safe");
  const [seed, setSeed] = useState(42);
  const [batchSeeds, setBatchSeeds] = useState("1, 2, 3, 4, 5");
  const [baselinePolicy, setBaselinePolicy] = useState("baseline_safe");
  const [cursor, setCursor] = useState(0);
  const [followLive, setFollowLive] = useState(true);
  const [compareId, setCompareId] = useState("");
  const [comparison, setComparison] = useState<Comparison>();
  const [verification, setVerification] = useState<EvidenceVerification>();
  const [policySteps, setPolicySteps] = useState<PolicyStep[]>([]);
  const [error, setError] = useState<string | null>(null);

  const refresh = async () => {
    try {
      const [nextRuns, nextBatches, nextExperiments, nextSuiteEvaluations, nextHealth] = await Promise.all([api<Run[]>("/api/runs"), api<Batch[]>("/api/batches"), api<Experiment[]>("/api/experiments"), api<SuiteEvaluation[]>("/api/suite-evaluations"), api<Health>("/health")]);
      setRuns(nextRuns); setBatches(nextBatches); setExperiments(nextExperiments); setError(null);
      setSuiteEvaluations(nextSuiteEvaluations);
      setHealth(nextHealth);
      if (!selectedId && nextRuns.length) setSelectedId(nextRuns[0].id);
      setSelectedExperimentId(current => current ?? nextExperiments[0]?.id ?? null);
      if (selectedId) {
        const nextDetail = await api<Run>(`/api/runs/${selectedId}`);
        setDetail(nextDetail);
        if (followLive && nextDetail.frames?.length) setCursor(nextDetail.frames.length - 1);
      }
    } catch (reason) { setError(reason instanceof Error ? reason.message : "API unavailable"); }
  };

  useEffect(() => { refresh(); const timer = window.setInterval(refresh, 500); return () => window.clearInterval(timer); }, [selectedId, followLive]);
  useEffect(() => { api<EngineInfo[]>("/api/engines").then(setEngines).catch(() => setEngines([])); }, []);
  useEffect(() => { api<EvaluationSuite[]>("/api/suites").then(setSuites).catch(() => setSuites([])); }, []);
  useEffect(() => { api<ScenarioInfo[]>("/api/scenarios").then(setScenarios).catch(() => setScenarios([])); }, []);
  useEffect(() => { if (selectedId) { setDetail(null); setCursor(0); setFollowLive(true); setCompareId(""); setComparison(undefined); setVerification(undefined); setPolicySteps([]); } }, [selectedId]);
  useEffect(() => {
    if (!detail) return;
    api<{ definition: Scenario }>(`/api/scenarios/${detail.scenario_id}?seed=${detail.seed}`).then(result => setScenario(result.definition)).catch(() => setScenario(undefined));
  }, [detail?.scenario_id, detail?.seed]);
  useEffect(() => {
    if (!selectedId || !compareId) { setComparison(undefined); return; }
    api<Comparison>(`/api/runs/${selectedId}/compare/${compareId}`).then(setComparison).catch(() => setComparison(undefined));
  }, [selectedId, compareId, detail?.updated_at]);
  useEffect(() => {
    if (!detail || activeStatuses.has(detail.status)) { setVerification(undefined); return; }
    api<EvidenceVerification>(`/api/runs/${detail.id}/evidence/verify`).then(setVerification).catch(() => setVerification(undefined));
  }, [detail?.id, detail?.status]);
  useEffect(() => {
    if (!detail) return;
    api<PolicyStep[]>(`/api/runs/${detail.id}/policy-trace`).then(setPolicySteps).catch(() => setPolicySteps([]));
  }, [detail?.id, detail?.updated_at]);

  const startRun = async () => {
    try {
      const created = await api<Run>("/api/runs", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ scenario_id: scenarioId, policy_id: policy, engine_id: engineId, seed }) });
      setSelectedId(created.id); setError(null);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not start run"); }
  };
  const cancelRun = async () => {
    if (!detail) return;
    try { const cancelled = await api<Run>(`/api/runs/${detail.id}/cancel`, { method: "POST" }); setDetail(current => current ? { ...current, ...cancelled } : current); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Could not cancel run"); }
  };
  const startBatch = async () => {
    const seeds = [...new Set(batchSeeds.split(",").map(value => Number(value.trim())).filter(value => Number.isInteger(value) && value >= 0))];
    if (!seeds.length || seeds.length > 50) { setError("Enter between 1 and 50 comma-separated integer seeds"); return; }
    try {
      const batch = await api<Batch>("/api/batches", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ scenario_id: scenarioId, policy_id: policy, engine_id: engineId, seeds }) });
      setBatches(current => [batch, ...current]); if (batch.runs.length) setSelectedId(batch.runs[0].id); setError(null);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not start batch"); }
  };
  const startExperiment = async () => {
    const seeds = [...new Set(batchSeeds.split(",").map(value => Number(value.trim())).filter(value => Number.isInteger(value) && value >= 0))];
    if (!seeds.length || seeds.length > 50) { setError("Enter between 1 and 50 comma-separated integer seeds"); return; }
    try {
      const experiment = await api<Experiment>("/api/experiments", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ scenario_id: scenarioId, candidate_policy_id: policy, baseline_policy_id: baselinePolicy, engine_id: engineId, seeds }) });
      setExperiments(current => [experiment, ...current]); setSelectedExperimentId(experiment.id); setError(null);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not start experiment"); }
  };
  const startSuiteEvaluation = async () => {
    try {
      const evaluation = await api<SuiteEvaluation>("/api/suite-evaluations", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ suite_id: selectedSuiteId, candidate_policy_id: policy, baseline_policy_id: baselinePolicy, engine_id: engineId }) });
      setSuiteEvaluations(current => [evaluation, ...current]); setError(null);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not start suite"); }
  };
  const cancelExperiment = async (id: string) => {
    try { const experiment = await api<Experiment>(`/api/experiments/${id}/cancel`, { method: "POST" }); setExperiments(current => current.map(item => item.id === id ? experiment : item)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Could not cancel experiment"); }
  };

  const frames = detail?.frames ?? [];
  const frame = frames[Math.min(cursor, Math.max(0, frames.length - 1))];
  const visibleFrames = frames.slice(0, Math.min(cursor + 1, frames.length));
  const progress = detail ? Math.round(detail.progress * 100) : 0;
  const finished = detail && !activeStatuses.has(detail.status);
  const checks = Array.isArray(detail?.metrics.checks) ? detail.metrics.checks as Check[] : [];
  const metricCards = useMemo(() => detail ? [
    ["Completion", detail.metrics.task_completed === undefined ? "—" : detail.metrics.task_completed ? "Yes" : "No"],
    ["Grasp", detail.metrics.grasp_qualified === undefined ? "—" : detail.metrics.grasp_qualified ? "Qualified" : "No"],
    ["Collisions", detail.metrics.collisions ?? "—"],
    ["Peak force", detail.metrics.max_contact_force_n === undefined ? "—" : `${detail.metrics.max_contact_force_n} N`],
    ["Sim time", frame ? `${frame.sim_time.toFixed(1)} s` : "—"]
  ] : [], [detail, frame]);
  const comparableRuns = runs.filter(run => run.id !== selectedId && !activeStatuses.has(run.status) &&
    run.scenario_id === detail?.scenario_id && run.engine_id === detail?.engine_id && run.seed === detail?.seed);
  const selectedExperiment = experiments.find(experiment => experiment.id === selectedExperimentId) ?? experiments[0];

  return <div className="app">
    <header><div className="brand-mark">P</div><div><strong>Praxis Lab</strong><small>Praxis Worlds · embodied-agent evaluation</small></div><div className="local-pill"><i /> {health ? `${health.active_workers} WORKER · ${health.active_runs} ACTIVE · ${health.queued_runs} QUEUED` : "Local runtime"}</div></header>
    <main>
      <section className="hero">
        <div><p className="eyebrow">WAREHOUSE BENCHMARK / V0.1</p><h1>Watch an agent act.<br/><em>Measure what physically happens.</em></h1><p className="lede">A reproducible 3D test world for navigation, contact, manipulation, and recovery—not a prerecorded animation.</p></div>
        <div className="launch-card"><label>World<select value={scenarioId} onChange={event => setScenarioId(event.target.value)}>{scenarios.length ? scenarios.map(item => <option key={item.id} value={item.id}>{item.name}</option>) : <option value="warehouse_v0">Warehouse</option>}</select></label><label className="engine-select">Engine<select value={engineId} onChange={event => setEngineId(event.target.value)}>{engines.length ? engines.map(engine => <option key={engine.id} value={engine.id} disabled={!engine.available}>{engine.name}{engine.physics ? " · PHYSICS" : " · SYNTHETIC"}{!engine.available ? " · NOT INSTALLED" : ""}</option>) : <option value="mujoco_v1">MuJoCo 3.11 · PHYSICS</option>}</select></label><label>Policy<input list="policy-options" value={policy} onChange={event => setPolicy(event.target.value)} /><datalist id="policy-options"><option value="baseline_safe"/><option value="baseline_risky"/><option value="python:examples.policies.hold_position:HoldPositionPolicy"/></datalist></label><label>Seed<input type="number" min="0" value={seed} onChange={event => setSeed(Number(event.target.value))} /></label><button onClick={startRun}>Run simulation <span>→</span></button></div>
      </section>
      {error && <div className="error"><strong>Runtime unavailable.</strong> {error}. Keep <code>npm run dev</code> open and reload.</div>}
      <section className="batch-bar"><div><p className="eyebrow">BENCHMARK BATCH</p><strong>Evaluate this policy across deterministic seeds</strong></div><label>Seeds<input value={batchSeeds} onChange={event => setBatchSeeds(event.target.value)} placeholder="1, 2, 3, 4, 5" /></label><button onClick={startBatch}>Run batch</button></section>
      <section className="experiment-launch"><div><p className="eyebrow">REGRESSION EXPERIMENT</p><strong>Compare candidate and baseline in {scenarios.find(item => item.id === scenarioId)?.name ?? scenarioId}</strong></div><label>Baseline<input list="policy-options" value={baselinePolicy} onChange={event => setBaselinePolicy(event.target.value)} /></label><button onClick={startExperiment}>Compare policies</button></section>
      <section className="experiment-launch"><div><p className="eyebrow">MULTI-WORLD SUITE</p><strong>Run one durable release gate across every included world</strong></div><label>Suite<select value={selectedSuiteId} onChange={event => setSelectedSuiteId(event.target.value)}>{suites.map(suite => <option key={suite.id} value={suite.id}>{suite.name} · {suite.pair_count} pairs / {suite.cases.length} worlds</option>)}</select></label><button onClick={startSuiteEvaluation}>Run suite</button></section>
      {suiteEvaluations.length > 0 && <section className="experiment-history"><div className="section-title"><span>Suite history</span><small>Aggregate release decisions</small></div><div>{suiteEvaluations.map(item => <button key={item.id} onClick={() => item.scenario_results[0] && setSelectedExperimentId(item.scenario_results[0].id)}><span>{item.suite_id.replaceAll("_", " ")}</span><small>{item.completed_pairs}/{item.total_pairs} PAIRS · {item.scenario_results.length} WORLDS</small><strong className={item.verdict}>{item.verdict}</strong></button>)}</div></section>}
      {batches.length > 0 && <section className="batch-list">{batches.slice(0, 3).map(batch => { const completed = (batch.counts.succeeded ?? 0) + (batch.counts.failed ?? 0) + (batch.counts.cancelled ?? 0); return <div key={batch.id}><button onClick={() => batch.runs[0] && setSelectedId(batch.runs[0].id)}><span>{batch.policy_id}</span><small>{batch.seeds.length} SEEDS · {completed}/{batch.runs.length} COMPLETE</small></button><div className="batch-progress"><i style={{ width: `${batch.runs.length ? completed / batch.runs.length * 100 : 0}%` }} /></div><strong>{batch.pass_rate === null ? "RUNNING" : `${Math.round(batch.pass_rate * 100)}% PASS`}</strong></div>; })}</section>}
      {experiments.length > 0 && <section className="experiment-history"><div className="section-title"><span>Experiment history</span><small>{experiments.length} durable comparisons</small></div><div>{experiments.map(experiment => <button className={selectedExperiment?.id === experiment.id ? "selected" : ""} key={experiment.id} onClick={() => setSelectedExperimentId(experiment.id)}><span>{experiment.candidate_policy_id.replace("baseline_", "")} vs {experiment.baseline_policy_id.replace("baseline_", "")}</span><small>{experiment.seeds.length} PAIRS · {new Date(experiment.created_at).toLocaleString()}</small><strong className={experiment.verdict}>{experiment.verdict}</strong></button>)}</div></section>}
      {selectedExperiment && <ExperimentPanel experiment={selectedExperiment} selectRun={setSelectedId} cancel={() => cancelExperiment(selectedExperiment.id)} />}

      <section className="lab-grid">
        <aside className="runs-panel"><div className="section-title"><span>Recent runs</span><small>{runs.length} recorded</small></div><div className="run-list">{runs.length ? runs.map(run => <button key={run.id} className={`run-row ${selectedId === run.id ? "selected" : ""}`} onClick={() => setSelectedId(run.id)}><div><Status run={run} /><strong>{run.policy_id.replace("baseline_", "")}</strong></div><small>{run.engine_id === "mujoco_v1" ? "PHYSICS" : "SYNTHETIC"} · {run.id.slice(-8)} · seed {run.seed}</small></button>) : <p className="empty">No simulations yet.</p>}</div></aside>
        <section className="viewer-panel">
          <div className="viewer-head"><div><p className="eyebrow">3D WORLD STATE · SEED {detail?.seed ?? "—"}</p><h2>{detail?.phase ?? "Ready for a run"}</h2></div>{detail && <div className="viewer-badges">{activeStatuses.has(detail.status) && detail.status !== "cancelling" && <button className="cancel-button" onClick={cancelRun}>Cancel</button>}<span className={`engine-badge ${detail.engine_id === "mujoco_v1" ? "physics" : "synthetic"}`}>{detail.engine_id === "mujoco_v1" ? "RIGID-BODY PHYSICS" : "SYNTHETIC FIXTURE"}</span><Status run={detail} /></div>}</div>
          <Suspense fallback={<div className="world-shell world-3d"><div className="world-empty">Loading 3D observer…</div></div>}><WorldView3D frame={frame} frames={visibleFrames} scenario={scenario} /></Suspense>
          <div className="timeline"><button className={`live-toggle ${followLive ? "on" : ""}`} onClick={() => setFollowLive(!followLive)}>{followLive ? "● LIVE" : "FOLLOW LIVE"}</button><input aria-label="Replay timeline" type="range" min="0" max={Math.max(0, frames.length - 1)} value={Math.min(cursor, Math.max(0, frames.length - 1))} onChange={event => { setCursor(Number(event.target.value)); setFollowLive(false); }} /><span>{frame?.sim_time.toFixed(1) ?? "0.0"}s</span></div>
          <div className="progress"><i style={{ width: `${progress}%` }} /><span>{progress}%</span></div>
        </section>
      </section>

      {detail && <>
        <section className="evidence-grid"><div className="metrics"><div className="section-title"><span>Measured evidence</span><small className={verification?.valid ? "verified" : verification ? "unverified" : ""}>{verification ? verification.valid ? `SHA-256 VERIFIED · ${verification.files_checked} FILES` : "EVIDENCE UNVERIFIED" : finished ? "Checking evidence" : "Streaming"}</small></div><div className="metric-grid">{metricCards.map(([label, value]) => <div className="metric" key={String(label)}><small>{String(label)}</small><strong>{String(value)}</strong></div>)}</div></div><div className="event-log"><div className="section-title"><span>Event trace</span><small>Simulation time</small></div>{detail.events?.slice().reverse().map(event => <div className="event" key={event.sequence}><time>{event.sim_time.toFixed(1)}s</time><span>{event.message}</span></div>)}</div></section>
        <Telemetry frames={frames} cursor={cursor} />
        <PolicyTrace steps={policySteps} />
        <section className="analysis-grid">
          <div className="limits-panel"><div className="section-title"><span>Limit decisions</span><small>{checks.length ? `${checks.filter(check => check.passed).length}/${checks.length} passed` : "Pending"}</small></div>{checks.map(check => <details className={`limit-row ${check.passed ? "limit-pass" : "limit-fail"}`} key={check.id}><summary><span>{check.id.replaceAll("_", " ")}</span><strong>{String(check.actual)} {check.unit} {check.operator} {String(check.limit)} {check.unit}</strong><i>{check.passed ? "PASS" : "FAIL"}</i></summary><p>{check.rationale}</p><small>Source: {check.source} · Calibration: {check.calibration_status}</small></details>)}</div>
          <div className="compare-panel"><div className="section-title"><span>Compare run</span><small>Same metrics, explicit delta</small></div><select value={compareId} onChange={event => setCompareId(event.target.value)}><option value="">Choose a completed run</option>{comparableRuns.map(run => <option key={run.id} value={run.id}>{run.policy_id.replace("baseline_", "")} · seed {run.seed} · {run.id.slice(-8)}</option>)}</select>{comparison ? <div className="comparison-table">{comparison.metrics.map(metric => <div key={metric.metric}><span>{metric.metric.replaceAll("_", " ")}</span><strong>{String(metric.primary ?? "—")}</strong><span className="versus">vs {String(metric.comparison ?? "—")}</span><i>{metric.delta === null ? "—" : `${metric.delta > 0 ? "+" : ""}${metric.delta.toFixed(1)}`}</i></div>)}</div> : <p className="compare-empty">Select another run to reveal regressions and improvements.</p>}</div>
        </section>
      </>}
    </main>
    <footer>Praxis Worlds · local development build · policy schema 1.0 · frame schema 2.0 · evidence schema 2.0</footer>
  </div>;
}
