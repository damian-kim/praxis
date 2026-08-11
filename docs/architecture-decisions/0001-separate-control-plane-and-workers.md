# ADR 0001 — Separate control plane from simulation workers

Status: accepted

## Decision

The API accepts and reports runs; it never performs a simulation and never owns a simulator subprocess. Independent workers atomically claim persisted jobs and write observations back to the run store.

For the local MVP, the durable queue is SQLite in WAL mode and evidence is stored on the filesystem. The cloud equivalents are PostgreSQL and object storage. The boundary is intentionally engine-neutral: the current mock worker and future Isaac worker consume the same run contract.

## Consequences

- Browser and API restarts do not interrupt simulator ownership or erase state.
- Workers can later run on GPU machines without moving the API.
- Run status and heartbeats expose failures instead of presenting an endless “running” state.
- Local startup has three processes, so a small supervisor provides one command and names any component that exits.

