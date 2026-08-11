export type RunStatus = "queued" | "provisioning" | "loading" | "running" | "finalizing" | "succeeded" | "failed" | "cancelled" | "interrupted";

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
