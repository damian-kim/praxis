# Praxis Worlds

Praxis Worlds is a development test lab for embodied agents. Its first task family is warehouse delivery: a mobile manipulator navigates an obstructed aisle, qualifies a physical grasp, and delivers a package while the system records policy decisions, motion, contacts, task events, metrics, and replayable evidence. Version 0.2 runs that task in nominal and low-friction physical conditions and combines their regression decisions into one durable suite verdict.

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
- Enter a built-in or `python:module:object` policy and inspect every observation and action.
- Cancel an active run and retain its partial, verifiable replay.
- Launch a 1–50 seed benchmark batch and monitor aggregate pass rate.
- Compare a candidate and baseline on identical seeds with explicit regression gates.
- Export paired results as JSON, CSV, or JUnit and open any candidate replay from the seed matrix.
- Run 3-, 10-, or 25-pair multi-world suites and inspect per-world gates and 95% confidence ranges.
- Navigate durable experiment history and see live worker/queue capacity in the header.
- Use isolated policy subprocesses with hard 100 ms action deadlines, or opt into a resource-limited Docker boundary for untrusted code.
- Restart the app; previous runs remain available because they are stored in `.worldsim/worldsim.db`.
- Inspect immutable evidence in `.worldsim/runs/<run-id>/evidence.json`.

## Commands

```powershell
npm test       # Python integration tests
npm run api    # API only, http://127.0.0.1:8010/docs
npm run worker # independent simulator worker only
npm run web    # UI only
npm run doctor # Installed worlds and policy-runner capabilities
npm run release:check # Tests, web build, durable two-world smoke, wheel

# In a second terminal while the API and worker are running
praxis evaluate --candidate baseline_risky --baseline baseline_safe --engine deterministic_mock_v1 --seeds 1..5
praxis suite-evaluate --suite warehouse_smoke --candidate baseline_safe --engine deterministic_mock_v1
```

For a stronger policy boundary, build the image and select it before starting the worker:

```powershell
docker build -f containers/policy-runner/Dockerfile -t praxis-policy-runner:local .
$env:WORLDSIM_POLICY_RUNNER = "docker"
npm run dev
```

Docker mode disables networking, uses a read-only root filesystem, drops Linux capabilities, prevents privilege escalation, and applies CPU, memory, PID, and temporary-filesystem limits. The default process mode is isolation for reliability and deadlines, not a security sandbox.

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
src/worldsim/policy.py          Python policy contract, loader, and references
src/worldsim/policy_runtime.py  Deadline-enforced subprocess client
src/worldsim/policy_host.py     JSON protocol policy process
src/worldsim/policy_sandbox.py  Process/Docker runner policy and diagnostics
src/worldsim/store.py           SQLite queue, state, frames, and events
worlds/*/scenario.json          Versioned physical-world contracts
containers/policy-runner/       Hardened policy image
docs/prds/                      Reviewable sprint specifications
docs/architecture-decisions/    Important technical decisions
tests/                           End-to-end vertical-slice tests
```

Review the sprint PRDs in [docs/prds](docs/prds), including [multi-world suites](docs/prds/009-multi-world-evaluation-suites.md), [hardened policy execution](docs/prds/010-hardened-policy-execution.md), and [v0.2 readiness](docs/prds/011-v02-release-readiness.md), for goals, acceptance criteria, risks, and validity boundaries. See the [Python Policy SDK](docs/sdk/python-policy.md), [process protocol](docs/sdk/policy-protocol.md), and [CI evaluation guide](docs/sdk/ci-evaluation.md) to connect and evaluate an external policy.
