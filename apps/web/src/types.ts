export type RunStatus = "queued" | "provisioning" | "loading" | "running" | "cancelling" | "finalizing" | "succeeded" | "failed" | "cancelled" | "interrupted";

export interface Frame {
  schema_version: string;
  sequence: number;
  sim_time: number;
  robot_x: number;
  robot_y: number;
  heading: number;
  package_x: number;
  package_y: number;
  carrying: boolean;
  contact_force: number;
  linear_speed_m_s: number | null;
  angular_speed_rad_s: number | null;
  shoulder_angle_rad: number | null;
  elbow_angle_rad: number | null;
  gripper_width_m: number | null;
  energy_j: number | null;
}

export interface Event {
  sequence: number;
  kind: string;
  message: string;
  sim_time: number;
  created_at: string;
}

export interface Run {
  id: string;
  scenario_id: string;
  policy_id: string;
  engine_id: string;
  seed: number;
  status: RunStatus;
  progress: number;
  phase: string;
  verdict: string | null;
  error: string | null;
  metrics: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  events?: Event[];
  frames?: Frame[];
}

export interface Scenario {
  schema_version: string;
  episode_seed: number;
  world: { width_m: number; height_m: number; gravity_m_s2: number; floor_friction: number };
  agent: { spawn: [number, number]; mass_kg: number };
  task: {
    package_spawn: [number, number];
    delivery_zone: [number, number];
    obstruction: { position: [number, number]; size: [number, number, number]; rotation_deg: number };
  };
  layout: { shelves: Array<{ position: [number, number]; size: [number, number, number] }> };
  limits: Record<string, { value: number | boolean; unit: string; source: string; calibration_status: string; rationale: string }>;
}

export interface Comparison {
  primary_run_id: string;
  comparison_run_id: string;
  metrics: Array<{ metric: string; primary: number | boolean | null; comparison: number | boolean | null; delta: number | null }>;
}

export interface EngineInfo {
  id: string;
  name: string;
  available: boolean;
  physics: boolean;
  description: string;
}

export interface EvidenceVerification {
  run_id: string;
  valid: boolean;
  files_checked: number;
  errors: string[];
}

export interface PolicyObservation {
  step: number; sim_time: number; robot_x: number; robot_y: number; heading: number;
  linear_speed_m_s: number; angular_speed_rad_s: number; package_x: number; package_y: number;
  goal_x: number; goal_y: number; carrying: boolean; grasp_qualified: boolean; contact_force_n: number;
}

export interface PolicyAction {
  target_x: number; target_y: number; target_heading: number; shoulder_target_rad: number;
  elbow_target_rad: number; gripper_target_m: number; request_grasp: boolean; done: boolean;
}

export interface PolicyStep {
  sequence: number; observation: PolicyObservation; action: PolicyAction; decision_ms: number;
}

export interface Batch {
  id: string; scenario_id: string; policy_id: string; engine_id: string; seeds: number[];
  created_at: string; counts: Record<string, number>; pass_rate: number | null; runs: Run[];
}

export interface GateResult { id: string; actual: number; operator: string; limit: number; passed: boolean; }
export interface ConfidenceInterval { estimate: number | null; lower: number | null; upper: number | null; n: number; }
export interface ExperimentSummary {
  candidate_pass_rate: number | null; baseline_pass_rate: number | null; pass_rate_delta: number | null;
  mean_collision_delta: number | null; mean_force_delta_n: number | null; mean_duration_delta_s: number | null;
  mean_energy_delta_j: number | null; completed_pairs: number; total_pairs: number;
  confidence: null | { level: number; method: string; candidate_pass_rate: ConfidenceInterval; baseline_pass_rate: ConfidenceInterval;
    paired_mean_deltas: Record<string, ConfidenceInterval>; sample_size: number; recommended_minimum_pairs: number;
    sample_guidance: "development_signal_only" | "sufficient_for_regression_screen" };
}
export interface SeedComparison {
  seed: number; candidate_run: Run; baseline_run: Run;
  metric_deltas: Record<string, number | null>; failure_reasons: string[];
}
export interface Experiment {
  id: string; scenario_id: string; candidate_policy_id: string; baseline_policy_id: string; engine_id: string;
  seeds: number[]; candidate_batch_id: string; baseline_batch_id: string; created_at: string;
  status: "running" | "complete"; verdict: "pending" | "pass" | "fail";
  summary: ExperimentSummary; gate_results: GateResult[]; pairs: SeedComparison[];
}

export interface ScenarioInfo { id: string; name: string; objective: string; schema_version: string; }
export interface SuiteCase { scenario_id: string; seeds: number[]; }
export interface EvaluationSuite {
  id: string; name: string; description: string; cases: SuiteCase[]; pair_count: number;
  scenario_id: string; seeds: number[]; purpose: string;
}
export interface SuiteEvaluation {
  id: string; suite_id: string; candidate_policy_id: string; baseline_policy_id: string; engine_id: string;
  experiment_ids: string[]; created_at: string; status: "running" | "complete";
  verdict: "pending" | "pass" | "fail"; completed_pairs: number; total_pairs: number;
  scenario_results: Experiment[];
}
export interface Health { status: string; database: string; worker_seen_at: string | null; active_workers: number; active_runs: number; queued_runs: number; }
