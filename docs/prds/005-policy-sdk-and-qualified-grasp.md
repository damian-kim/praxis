# PRD 005 — Policy SDK and Contact-Qualified Grasp

Status: implemented for review  
Sprint: 5

## What we are accomplishing

Turn Praxis Worlds from a fixed trajectory demonstration into a controllable agent-evaluation runtime. A policy receives a versioned observation at 10 Hz, returns a validated action, and has every decision recorded beside the physical evidence. Runs can be cancelled durably, and package delivery is gated by physical contact from both gripper fingers.

## Why we need it

Customers ultimately need to test their own agents, not Praxis-authored paths. The simulator therefore needs a stable boundary between policy code and world execution. That boundary must be reproducible, observable, time-bounded, and independent from the dashboard. Grasp success must also represent an interaction with collision geometry rather than a predetermined waypoint transition.

## Requirements

- Observation schema 1.0 includes pose, velocity, package and goal positions, contact force, carrying state, and grasp qualification.
- Action schema 1.0 includes base target, heading, arm targets, gripper target, grasp request, and completion signal.
- Built-in and external Python policies implement the same `reset` and `act` protocol.
- External policies load with `python:module:object` identifiers and only execute in the worker.
- Observation, action, and decision latency are persisted for every control step.
- Policy trace is written as an immutable, hashed artifact and exposed through the API and dashboard.
- Queued and active runs can be cancelled; active workers emit partial replay and verifiable evidence.
- A grasp qualifies only after both gripper collision geometries contact the package.
- Scenario verdicts explicitly require a qualified grasp.

## How it works

At each 100 ms control interval, the MuJoCo worker constructs a `PolicyObservation` from native simulator state. It times `policy.act`, validates the result as `PolicyAction`, persists the decision, and applies bounded actuator targets for five 20 ms physics steps. Policies never write directly to simulator state or evidence storage.

The reference safe and risky behaviors are now policies, not branches in the physics loop. The safe policy follows a clearance-aware route, positions the articulated arm, closes both fingers around the package, and only begins delivery after the observation reports `grasp_qualified`. The risky policy deliberately crosses the obstruction and typically cannot finish its grasp after impact.

Cancellation is stored on the run row. The worker checks it before every policy decision, writes an acknowledgement event, finalizes any accumulated frames and trace, hashes the partial bundle, and marks the run `cancelled`. Browser or API process lifetime remains irrelevant.

## Security boundary

`python:` policies execute trusted local Python code with the worker's permissions. This is appropriate for the local developer product but is not a hosted multi-tenant sandbox. A cloud product must isolate policy processes or containers, apply CPU/memory/network limits, and communicate over a serialized action protocol.

## Acceptance criteria

- Safe reference policy records decisions, qualifies dual-finger contact, completes delivery, and passes.
- Risky reference policy records decisions, contacts the obstruction, and fails.
- An example external policy loads without changing Praxis source.
- Invalid action output fails visibly rather than silently coercing simulator state.
- Cancellation prevents further decisions and produces replayable, hash-verified partial evidence.
- Policy trace UI updates during execution and shows targets, observations, grasp intent, and latency.
- Tests and production web build pass.

## Next sprint

Move external policies into isolated subprocesses with a JSON-RPC or gRPC transport, enforce decision deadlines, add observation/action space discovery, support user-supplied wheel/torque commands, and implement benchmark batches across multiple seeds.

