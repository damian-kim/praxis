# ADR 0002 — Use MuJoCo as the first physics adapter

Status: accepted

## Context

Isaac Sim is the intended high-fidelity production engine but is not installed locally and brings a large GPU/runtime dependency. PyBullet offers no native wheel for the machine's Python 3.14 runtime and would require an 80 MB source build. MuJoCo 3.11 supplies a native Windows/Python 3.14 wheel.

## Decision

Implement `mujoco_v1` first behind the existing simulation-engine interface. Keep Isaac as a separate future adapter rather than replacing the target architecture.

## Consequences

- WorldSim can produce real rigid-body contact evidence now.
- Engine selection becomes immutable run metadata.
- The evaluator and UI must explicitly distinguish physical measurement from synthetic fixtures.
- MuJoCo's initial robot may be simplified; its validity envelope must accompany every fidelity claim.
- Scenario, frame, and evidence contracts are exercised before the heavier Isaac integration.

