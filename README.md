# WorldSim

WorldSim is a development test lab for embodied agents. Its first world is a warehouse task where a mobile manipulator navigates an obstructed aisle, collects a package, and delivers it while the system records motion, contacts, task events, metrics, and a replayable evidence trail.

The default backend is MuJoCo 3.11 and executes native rigid-body dynamics and contacts. A deterministic mock remains available for fast product development. The current physics validity envelope covers simplified warehouse navigation contacts; locomotion and package attachment are not yet high-fidelity robotics models. NVIDIA Isaac Sim/PhysX remains a later adapter target.

## Run locally

From `E:\Anima\worldsim`:

```powershell
npm run setup
npm run dev
```

Open `http://127.0.0.1:5173`. Keep the terminal open. Stop all three development processes with Ctrl+C.

The first command installs the editable Python package and web dependencies. Later sessions only need `npm run dev`.

## What to try

- Run **Baseline safe** to watch a successful package delivery.
- Run **Baseline risky** to see a contact-force violation and failed verdict.
- Switch between **MuJoCo physics** and the clearly labelled **synthetic fixture**.
- Drag the 3D world to orbit the camera and scroll to zoom.
- Turn off **LIVE** and drag the timeline to replay every recorded state.
- Compare two completed runs to inspect metric deltas.
- Inspect synchronized base speed, yaw rate, arm joints, gripper aperture, contact force, and actuator energy.
- Confirm the SHA-256 evidence badge after a run completes.
- Restart the app; previous runs remain available because they are stored in `.worldsim/worldsim.db`.
- Inspect immutable evidence in `.worldsim/runs/<run-id>/evidence.json`.

## Commands

```powershell
npm test       # Python integration tests
npm run api    # API only, http://127.0.0.1:8010/docs
npm run worker # independent simulator worker only
npm run web    # UI only
```

## Repository map

```text
apps/web/                       React observation and replay lab
src/worldsim/api.py             FastAPI control plane
src/worldsim/worker.py          Independent durable job worker
src/worldsim/simulator.py       Replaceable mock simulator adapter
src/worldsim/mujoco_engine.py   Native rigid-body/contact adapter
src/worldsim/engines.py         Shared simulation-engine boundary
src/worldsim/evaluator.py       Limits, decisions, and provenance
src/worldsim/evidence.py        SHA-256 bundle writing and verification
src/worldsim/store.py           SQLite queue, state, frames, and events
worlds/warehouse_v0/            Versioned scenario contract
docs/prds/                      Reviewable sprint specifications
docs/architecture-decisions/    Important technical decisions
tests/                           End-to-end vertical-slice tests
```

Review [Sprint 1](docs/prds/001-durable-world-test-lab.md), [Sprint 2](docs/prds/002-engine-neutral-3d-evaluation.md), [Sprint 3](docs/prds/003-mujoco-physics-adapter.md), and [Sprint 4](docs/prds/004-articulated-telemetry-and-integrity.md) for goals, designs, acceptance criteria, risks, and validity boundaries.
