# PRD 001 — Durable World Test Lab

Status: implemented for review  
Sprint: 1  
Product codename: WorldSim

## What we are accomplishing

Build the first complete product loop for evaluating an embodied agent: configure a policy and deterministic seed, queue a warehouse scenario, observe the agent move through the world, inspect physical events and limits, replay every recorded frame, and retain evidence after the run finishes.

This sprint deliberately uses a deterministic mock simulator. It proves the product architecture and user workflow before we attach a heavyweight physics engine. The mock numbers are clearly a development fixture; they are not claims of real-world physical accuracy.

## Why this is necessary

A physics engine alone is not a product. The durable evaluation loop—scenario contract, orchestration, observation, evidence, thresholds, replay, and comparison—is the reusable layer customers interact with. Proving that loop first prevents the future Isaac integration from becoming an unobservable one-off demo.

The API and worker are separate processes. A browser refresh or API restart cannot own or erase a simulator job. This directly addresses the process-lifecycle failures encountered in earlier local tooling.

## User

An embodied-AI engineer who needs to answer: “Did this agent complete the task, what physically happened, and can I reproduce the result?”

## In scope

- Versioned `warehouse_v0` scenario and explicit physical limits.
- Persistent SQLite run queue with a state machine.
- Independent worker process polling and claiming jobs atomically.
- Deterministic safe and risky reference policies.
- Live top-down state visualization, event trace, metrics, and timeline replay.
- Immutable JSON evidence per completed run.
- Automated tests for persistence, success, failure, and evidence.
- One-command local supervisor after initial setup.

## Not in scope

- NVIDIA Isaac Sim/PhysX execution.
- Photorealistic rendering or learned world generation.
- User-authored policies, Python SDK, cloud scheduling, or multi-user auth.
- Claims that mock contact-force values are calibrated measurements.

## How it works

1. The web client posts a scenario, policy, and seed to FastAPI.
2. FastAPI persists a `queued` run in SQLite and immediately returns its ID.
3. The separately running worker atomically claims the next job.
4. It records state frames and semantic events throughout execution.
5. The browser polls the control plane and follows the latest frame live.
6. The evaluator applies completion, collision, and peak-force limits.
7. The worker writes `.worldsim/runs/<run-id>/evidence.json` and finalizes the verdict.
8. Finished runs remain selectable and replayable after any service restart.

## Requirements

### Functional

- A run must survive recreation of the API process.
- Duplicate workers must not claim the same queued run.
- A safe reference policy must complete with zero collisions.
- A risky reference policy must produce a visible unsafe contact and fail.
- Each completed run must contain its contract identifiers, seed, metrics, trajectory, and verdict.
- The replay scrubber must display each recorded world state.

### Quality

- One document scroll; no nested scrolling panels.
- API errors must remain visible and actionable.
- UI polling must never control worker lifetime.
- Runs must be deterministic for a given scenario, policy, and seed.

## Acceptance criteria

- `npm test` passes.
- `npm run setup` followed by `npm run dev` starts API, worker, and web client.
- The UI at `http://127.0.0.1:5173` can run both policies and replay them.
- Killing and restarting only the API does not remove queued or completed runs.
- A JSON evidence artifact exists after each completed run.

## Risks and mitigations

- **Mock physics mistaken for validation:** the UI and documentation call this a development backend; Sprint 2 replaces the execution adapter with Isaac.
- **SQLite write contention:** WAL mode, short transactions, one frame per transaction, and atomic claims are sufficient locally; PostgreSQL is the cloud migration target.
- **Supervisor exits:** components are independent processes with persisted state. It reports which child stopped rather than silently failing.
- **Scenario drift:** schema version, scenario ID, policy ID, and seed are embedded in every artifact.

## Next sprint

Build the simulator adapter boundary and Isaac worker: USD warehouse, differential-drive mobile manipulator, PhysX contacts, fixed-step execution, camera and state recordings, and calibrated threshold provenance. The existing API, queue, dashboard, and evidence contract remain intact.

