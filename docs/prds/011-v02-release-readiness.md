# PRD 011: v0.2 release readiness

## Outcome

Make the current MVP reproducibly verifiable from a clean checkout and honest about its remaining fidelity limits.

## Why

Passing unit tests in one prepared environment is not enough. Packaging, frontend compilation, restart durability, multi-world execution, and evidence verification must fail together before a release is labeled ready.

## Scope

- Fix clean-install dependency metadata and bump the MVP to 0.2.0.
- Add a one-command readiness script.
- Exercise an aggregate suite through API creation, worker execution, API restart, and evidence verification.
- Build the Python wheel and production web bundle.
- Document current capabilities, commands, and external gates.

## Acceptance criteria

- Backend tests and TypeScript production build pass.
- A deterministic two-world release smoke passes after an API restart.
- Every smoke-run evidence bundle verifies by SHA-256.
- A wheel is produced in `.worldsim/release`.
- Docker and browser checks are reported accurately rather than silently treated as passes.

## Remaining fidelity work

The v0.2 robot is still a simplified mobile manipulator in MuJoCo. Camera/sensor simulation, deformables, richer task families, calibrated robot limits, distributed scheduling, and container-image execution remain future work.
