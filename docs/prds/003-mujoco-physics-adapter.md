# PRD 003 — MuJoCo Physics Adapter

Status: implemented for review  
Sprint: 3

## What we are accomplishing

Add the first genuine rigid-body simulator to WorldSim. Users can choose MuJoCo or the deterministic development fixture per run, see which type produced a result, and receive evidence containing the exact engine/version, compiled model, physics steps, measured contact samples, and forces.

## Why we need it

The product loop is useful, but a synthetic backend cannot validate physical behavior. Isaac Sim is not installed on the development machine, and PyBullet has no Python 3.14 wheel. MuJoCo 3.11 provides a native supported wheel and lets us exercise real collision detection, constraint solving, friction, gravity, and contact-force extraction immediately. This validates the multi-engine architecture without changing the later Isaac target.

## Requirements

- Engine choice is part of each immutable run request and survives database/API restarts.
- Existing databases migrate without deleting runs.
- MuJoCo compiles the seeded warehouse into a native model.
- The model contains gravity, friction, floor, shelves, movable obstruction, package, and robot collision geometry.
- The adapter executes fixed 20 ms physics steps and samples evidence at 10 Hz.
- Unsafe robot-to-shelf or robot-to-obstruction contacts are measured through MuJoCo's contact-force API.
- Every physics run writes `model.xml` alongside `evidence.json`.
- UI labels distinguish `RIGID-BODY PHYSICS` from `SYNTHETIC FIXTURE`.

## How it works

The worker reads `engine_id` from the claimed run and resolves the adapter. `mujoco_v1` compiles XML from the exact seeded scenario snapshot. Dynamic objects settle under gravity before episode time begins. A mocap-driven robot body follows the reference policy while MuJoCo solves contacts against dynamic and static collision geometry. Five 20 ms solver steps are executed per recorded frame.

The safe policy routes around the obstruction. The risky policy intersects it, producing native contact constraints and a measured force. The general evaluation layer applies the same threshold definitions to both engines, while engine capabilities state whether measurements are physical or synthetic.

## Current validity envelope

This adapter validates rigid-body navigation contacts in a simplified warehouse. Robot locomotion is kinematic, package attachment is state-controlled, object geometry is primitive, and material values are provisional. Therefore it is real rigid-body contact simulation, but it is not yet a calibrated digital twin or high-fidelity manipulation test.

## Acceptance criteria

- Safe MuJoCo reference run passes with zero forbidden contacts.
- Risky MuJoCo run produces at least one measured contact sample and a nonzero peak force.
- Physics evidence reports `physics: true`, engine version, fixed-step count, and compiled model.
- Mock evidence continues to report `physics: false`.
- UI offers both installed engines and identifies every historical run's engine class.
- Tests and production web build pass.

## Next sprint

Replace kinematic locomotion with a torque/velocity-controlled articulated mobile manipulator, add joint state and actuator telemetry to frame schema 2.0, validate material/contact parameters against documented references, and record RGB/depth/segmentation sensors. The Isaac adapter can then implement the same richer contract.

