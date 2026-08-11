# PRD 002 — Engine-Neutral 3D Evaluation

Status: implemented for review  
Sprint: 2

## What we are accomplishing

Turn the Sprint 1 product loop into an extensible evaluation system rather than a hard-coded animation. The sprint introduces a simulation-engine interface, seeded scenario compilation, a fully interactive 3D warehouse observer, transparent threshold decisions, and run-to-run comparison.

## Why we need it

Isaac Sim integration will be expensive and operationally heavy. The product needs a stable boundary so Isaac can replace the development simulator without rewriting orchestration, evidence, replay, or the user interface. Meanwhile, engineers need to distinguish measured physics from synthetic fixtures and understand exactly why a run passed or failed.

## What is required

- An engine capability contract that declares whether a backend provides physics, contacts, rendering, and deterministic replay.
- Scenario schema 1.1 with deterministic variation envelopes, physical layout, and structured limits.
- Limit provenance: value, unit, source, rationale, and calibration status.
- A 3D warehouse observer driven exclusively by recorded frames.
- Camera orbit and zoom, live following, replay scrubbing, route trails, payload state, and contact visualization.
- A comparison endpoint and UI for task completion, collisions, peak force, and duration.
- Evidence snapshots of the exact compiled scenario and engine capabilities.

## How we are doing it

The worker resolves `WORLDSIM_ENGINE` through an engine registry. `deterministic_mock_v1` is the only installed adapter and explicitly declares `physics: false`. A future Isaac adapter implements the same `execute` method and writes the same frame/event/evidence contract.

Scenario compilation uses the run seed to vary package and obstruction placement inside declared envelopes. The exact compiled definition is stored with evidence. A standalone evaluator applies structured limits and records every check, including failed values and calibration status.

The React client renders the warehouse in Three.js using an evidence-driven robot, package, route, shelves, contact pulse, shadows, fog, and user-controlled camera. The same state is used for live viewing and historical replay.

## Non-goals

- Claiming synthetic contact values are real physics.
- Adding Isaac before its runtime and GPU environment are installed and verified.
- Photorealism, deformables, fluids, learned policies, or multiplayer worlds.
- Cloud infrastructure or authentication.

## Acceptance criteria

- Same seed produces an identical compiled episode; different seeds vary task placement.
- Every evidence file identifies engine capabilities and contains the compiled scenario.
- Every verdict contains individual limit decisions and provenance.
- Users can orbit and zoom a 3D warehouse while a run streams.
- Users can scrub the route and see payload/contact state at any frame.
- Users can compare two completed runs with explicit metric deltas.
- Backend tests and production TypeScript/Vite build pass.

## Risks

- **3D viewer implies physics:** engine capability metadata and synthetic calibration labels explicitly distinguish observation from validation.
- **Scenario/frontend drift:** the viewer consumes the compiled scenario API rather than duplicating seeded positions.
- **Engine contract too narrow:** frames remain minimal in this sprint; Isaac integration will version the contract before adding joints, sensors, and RGB/depth streams.
- **Rendering performance:** geometry is modest, pixel ratio is capped, resources are disposed, and rendering remains independent from the worker.

## Next sprint

Implement the first genuine physics adapter. If Isaac Sim is available, build the USD warehouse, PhysX materials, fixed timestep, rigid contacts, and ground-truth state exporter. If it is unavailable, add a local PyBullet adapter first so the physics/evidence contract can be exercised immediately, then keep Isaac as the production target.

