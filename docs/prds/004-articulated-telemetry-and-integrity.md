# PRD 004 — Articulated Telemetry and Evidence Integrity

Status: implemented for review  
Sprint: 4

## What we are accomplishing

Upgrade the MuJoCo robot from a single collision body to a finite-scale articulated mobile manipulator and make its internal physical state observable. Version every recorded frame, visualize joint and actuator telemetry during live execution and replay, and add cryptographic manifests that detect missing or modified evidence.

## Why we need it

An embodied-agent evaluator cannot stop at position and collisions. Engineers need to see whether a controller is unstable, how the arm moved, how fast the base was traveling, and how much actuator work the episode consumed. Separately, evidence used for regression gates must be verifiable after it leaves the worker; a JSON report without integrity metadata can be silently changed or partially copied.

## Requirements

- Frame schema 2.0 records base speed, yaw rate, shoulder position, elbow position, gripper aperture, and cumulative actuator energy.
- Existing SQLite frame tables migrate in place without losing historical frames.
- MuJoCo model includes a two-joint arm, palm, and two actuated gripper fingers.
- Telemetry values come from MuJoCo generalized position, velocity, and actuator-force arrays.
- Three.js replay drives the visible shoulder and elbow from recorded joint positions.
- Dashboard displays synchronized state values and charts for speed, force, and energy.
- Each completed bundle contains `manifest.json` with SHA-256 and byte size for every artifact.
- API verifies evidence on demand and reports missing, modified, or valid files.

## How it works

The mobile base has two prismatic translation joints, a yaw joint, and damped position actuators. The arm adds shoulder and elbow hinges plus symmetric finger slides. Gravity compensation and damped control keep the arm in a compact carry pose. Generalized actuator force multiplied by generalized velocity is integrated over fixed 20 ms steps to estimate actuator work.

The physical model was corrected to industrial scale: a roughly 1.4-meter-wide base, sub-meter arm links, and a 0.7-meter package. This removed false contacts caused by the earlier six-meter-wide provisional robot. A terminal hold phase lets the finite-mass controller settle before final task measurements.

Once the worker writes artifacts, it hashes `evidence.json` and, for MuJoCo, `model.xml`. The manifest is deliberately outside its own hash set. `/api/runs/{id}/evidence/verify` recalculates hashes and sizes without trusting the report contents.

## Acceptance criteria

- A safe articulated episode completes with zero forbidden contacts.
- A risky episode completes the delivery but contacts the obstruction and fails its safety limits.
- Completed physics frames contain non-null joint, velocity, gripper, and energy values.
- Historical schema 1 frame rows remain readable with null telemetry.
- Altering one byte of evidence causes verification to fail.
- UI build and all backend tests pass.

## Validity envelope and remaining limitations

The base and arm have real finite-mass dynamics, actuator forces, gravity, collision geometry, and contacts. The reference controller is waypoint/position based rather than a learned policy. Package attachment is still state-controlled rather than a force-closure grasp. Energy is generalized actuator work, not battery draw. Material and force thresholds remain provisional until calibrated against a specific robot and warehouse surface.

## Next sprint

Introduce a policy SDK and action protocol so an external Python policy controls base velocity and arm targets at every step. Replace state-controlled attachment with contact-based grasp qualification, add timeout/cancellation, and record policy observations/actions alongside physical state.

