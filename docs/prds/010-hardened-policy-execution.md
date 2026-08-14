# PRD 010: Hardened policy execution

## Outcome

Preserve the current fast process runner while adding a selectable Docker boundary for untrusted policy code.

## Why

The existing subprocess enforces a decision deadline but is not a security sandbox. User policy code can otherwise access the host filesystem and network.

## Scope

- Keep NDJSON policy protocol 1.0 unchanged.
- Select `process` or `docker` with `WORLDSIM_POLICY_RUNNER`.
- Run Docker policies without network, capabilities, writable root, or privilege escalation.
- Apply explicit CPU, memory, process-count, and temporary-filesystem limits.
- Expose diagnostics through the API and `praxis doctor`.
- Record the selected runner mode in physics evidence.

## Acceptance criteria

- Command construction is tested for every security flag.
- An unavailable Docker CLI produces a direct remediation error.
- Process mode remains the zero-setup local default.
- Docker mode uses an image containing Praxis plus the candidate policy.

## Known external gate

Docker isolation requires Docker Desktop or another compatible daemon. Automated local tests validate the boundary contract; a release operator must build and exercise the image with `scripts/release-readiness.ps1 -BuildPolicyImage`.
