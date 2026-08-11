import type { Frame } from "./types";

interface Props { frames: Frame[]; cursor: number; }

function Sparkline({ values, color }: { values: number[]; color: string }) {
  if (values.length < 2) return <div className="spark-empty">Waiting for samples</div>;
  const max = Math.max(...values, .0001); const width = 300; const height = 58;
  const points = values.map((value, index) => `${index / (values.length - 1) * width},${height - value / max * (height - 4)}`).join(" ");
  return <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none"><polyline points={points} fill="none" stroke={color} strokeWidth="2" vectorEffect="non-scaling-stroke" /></svg>;
}

export default function Telemetry({ frames, cursor }: Props) {
  const visible = frames.slice(0, Math.min(cursor + 1, frames.length));
  const current = visible.at(-1);
  const speed = visible.map(frame => frame.linear_speed_m_s ?? 0);
  const force = visible.map(frame => frame.contact_force);
  const energy = visible.map(frame => frame.energy_j ?? 0);
  const values = [
    ["Base speed", current?.linear_speed_m_s, "m/s"],
    ["Yaw rate", current?.angular_speed_rad_s, "rad/s"],
    ["Shoulder", current?.shoulder_angle_rad, "rad"],
    ["Elbow", current?.elbow_angle_rad, "rad"],
    ["Gripper", current?.gripper_width_m, "m"],
    ["Actuator energy", current?.energy_j, "J"],
  ];
  return <section className="telemetry-panel"><div className="section-title"><span>Robot telemetry</span><small>FRAME SCHEMA 2.0 · {visible.length} SAMPLES</small></div><div className="telemetry-values">{values.map(([label, value, unit]) => <div key={String(label)}><small>{label}</small><strong>{typeof value === "number" ? value.toFixed(2) : "—"}</strong><i>{unit}</i></div>)}</div><div className="chart-grid"><div><span>BASE SPEED</span><Sparkline values={speed} color="#d9ff62" /></div><div><span>CONTACT FORCE</span><Sparkline values={force} color="#ff7468" /></div><div><span>CUMULATIVE ENERGY</span><Sparkline values={energy} color="#58d7ac" /></div></div></section>;
}
