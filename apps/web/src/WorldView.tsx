import type { Frame } from "./types";

function Robot({ frame }: { frame: Frame }) {
  return <g transform={`translate(${frame.robot_x} ${frame.robot_y}) rotate(${frame.heading * 180 / Math.PI})`}>
    <circle r="4.5" fill="#d9ff62" stroke="#10130b" strokeWidth="1" />
    <path d="M 1 -2 L 6 0 L 1 2 Z" fill="#10130b" />
    <circle r="7" fill="none" stroke="#d9ff62" opacity=".18" />
  </g>;
}

export default function WorldView({ frame }: { frame?: Frame }) {
  return <div className="world-shell">
    <svg className="world" viewBox="0 0 100 100" role="img" aria-label="Top-down warehouse simulation">
      <defs>
        <pattern id="grid" width="5" height="5" patternUnits="userSpaceOnUse">
          <path d="M 5 0 L 0 0 0 5" fill="none" stroke="#202627" strokeWidth=".25" />
        </pattern>
      </defs>
      <rect width="100" height="100" rx="2" fill="#111516" />
      <rect width="100" height="100" fill="url(#grid)" />
      <g fill="#293031" stroke="#3c4647" strokeWidth=".5">
        <rect x="17" y="12" width="8" height="35" rx="1" />
        <rect x="36" y="10" width="8" height="28" rx="1" />
        <rect x="56" y="10" width="8" height="22" rx="1" />
        <rect x="17" y="60" width="8" height="26" rx="1" />
        <rect x="43" y="64" width="8" height="23" rx="1" />
      </g>
      <rect x="82" y="14" width="12" height="12" rx="2" fill="#162d27" stroke="#51d7a3" strokeWidth=".7" />
      <text x="88" y="30" textAnchor="middle" fill="#51d7a3" fontSize="2.5">OUTBOUND</text>
      <rect x="42" y="48" width="12" height="5" rx="1" fill="#653f2e" stroke="#e98a5a" strokeWidth=".6" transform="rotate(-18 48 50.5)" />
      <polyline points="10,78 30,62 47,52 68,32 86,20" fill="none" stroke="#d9ff62" strokeWidth=".6" strokeDasharray="2 2" opacity=".25" />
      {frame && <>
        <rect x={frame.package_x - 2.5} y={frame.package_y - 2.5} width="5" height="5" rx=".8" fill="#ffb557" stroke="#fff0cc" strokeWidth=".5" />
        {frame.contact_force > 0 && <circle cx={frame.robot_x} cy={frame.robot_y} r="10" fill="none" stroke="#ff6d5f" strokeWidth="1.5" />}
        <Robot frame={frame} />
      </>}
    </svg>
    {!frame && <div className="world-empty">Start a run to stream the world state.</div>}
    <div className="legend"><span><i className="robot-dot" /> Robot</span><span><i className="package-dot" /> Package</span><span><i className="zone-dot" /> Goal</span></div>
  </div>;
}

