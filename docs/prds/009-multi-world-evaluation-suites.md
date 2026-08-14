# PRD 009: Multi-world evaluation suites

## Outcome

Turn a seed preset into a durable benchmark job that evaluates one candidate against one baseline across multiple versioned physical worlds.

## Why

A policy that passes one warehouse layout is not robust evidence. Release decisions need scenario boundaries, independent results, and a single aggregate verdict that survives API restarts.

## Scope

- Discover installed scenarios from `worlds/*/scenario.json` and remove `warehouse_v0` hard-coding.
- Add a low-friction warehouse condition with independent variation and limits.
- Persist suite-to-experiment relationships in SQLite.
- Report progress and verdict both per world and for the complete suite.
- Let the API, CLI, worker, and dashboard launch and observe the same suite entity.

## Acceptance criteria

- A smoke suite creates paired experiments in at least two scenarios.
- Each run resolves its own scenario definition in the worker.
- A restarted API returns the same suite and aggregate state.
- The aggregate passes only when every scenario gate passes.
- Unknown or path-like scenario IDs are rejected.

## Non-goals

This sprint does not claim that two warehouse conditions constitute a broad world-model benchmark. It establishes the versioned structure needed to add more task families.
