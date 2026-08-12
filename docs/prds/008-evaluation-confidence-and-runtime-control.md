# PRD 008 — Evaluation Confidence and Runtime Control

Status: implemented for review  
Sprint: 8

## What we are accomplishing

Make paired experiments easier to repeat, harder to overinterpret, and safe to execute when multiple local worker processes exist. Praxis Lab now exposes reusable evaluation suites, durable experiment history, 95% uncertainty ranges, sample-size guidance, and a leased global concurrency boundary.

## Why we need it

A perfect result across two seeds is not equivalent to a perfect result across twenty-five seeds. Reporting both as “100%” without uncertainty encourages false confidence. Engineers also need stable seed cohorts so results from different days mean the same thing.

Separately, accidental duplicate worker processes can oversubscribe a laptop and make results contend for CPU. A worker that crashes after claiming a run can also leave the queue apparently active forever. Worker registration and expiring leases make both states visible and recoverable.

## Product requirements

- Provide named smoke, regression, and extended warehouse suites with immutable ordered seed cohorts.
- Let the user apply a suite from the regression launcher while retaining custom-seed support.
- Preserve and navigate durable experiment history without losing the current selection during polling.
- Report 95% Wilson intervals for candidate and baseline pass rates.
- Report descriptive 95% intervals for paired metric means when at least two samples exist.
- Clearly label fewer than ten pairs as a development signal rather than a regression-grade sample.
- Show active workers, active runs, and queued runs in the application header.
- Register each worker under a unique ID and heartbeat it during long simulations.
- Enforce a global active-run limit atomically at queue claim time.
- Mark a run interrupted when its owning worker lease expires, rather than leaving it stuck indefinitely.

## Statistical contract

Pass-rate intervals use the Wilson score method because it remains bounded and informative for small samples and extreme rates. Paired continuous deltas use a normal 95% interval around the sample mean. These intervals are descriptive engineering signals, not claims of formal model certification.

The default minimum guidance is ten paired runs. This does not alter the user-configured release gates: it labels evidence strength so a two-seed failure remains useful while a two-seed success cannot masquerade as broad reliability.

## Runtime contract

Each worker registers its process ID, start time, last heartbeat, and current run. Queue claims happen inside the existing SQLite immediate transaction. Before a claim, stale registrations are removed and their non-terminal runs are marked `interrupted`. A live worker refreshes its lease every two seconds, including while MuJoCo is executing.

`WORLDSIM_MAX_ACTIVE_RUNS` controls the shared concurrency budget and defaults to one. Multiple workers may remain alive, but no more than the configured number can hold claimed runs. This is a resource-control boundary, not a policy security sandbox.

## Acceptance criteria

- The API returns three versioned evaluation suites containing 3, 10, and 25 seeds.
- A completed experiment contains bounded pass-rate confidence intervals and paired-delta intervals.
- Samples below ten pairs are visibly labelled development-only.
- Experiment history remains selectable while live polling continues.
- A second registered worker cannot claim a run when the global limit is reached.
- Releasing a slot allows the next worker to claim atomically.
- An expired worker lease interrupts its claimed run and clears the capacity slot.
- Health reports worker, active-run, and queue counts.
- All integration tests and the production frontend build pass.

## Known limits

- The three suites currently cover deterministic layout variation inside `warehouse_v0`; they are not yet a multi-world benchmark.
- The paired-mean interval uses a normal approximation and does not replace power analysis or bootstrap analysis for a publication-grade benchmark.
- Interrupted runs retain their database trace but may lack a finalized evidence manifest if the process died abruptly.
- Worker leases control scheduling but do not constrain CPU, memory, filesystem, or network access.

## Next sprint

Add multiple versioned task scenarios and an aggregate suite-run entity, then introduce a container runner behind the existing policy protocol with explicit CPU, memory, filesystem, and network controls.
