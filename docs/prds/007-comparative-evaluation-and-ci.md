# PRD 007 — Comparative Evaluation and CI

Status: implemented for review  
Sprint: 7

## What we are accomplishing

Turn isolated simulation runs into a repeatable regression test. An experiment executes one candidate policy and one locked baseline policy against the same scenario, engine, and ordered seed set. Praxis then pairs the results by seed, explains every failure, applies explicit release gates, and produces machine-readable evidence for continuous integration.

## Why we need it

A candidate passing one run does not show that it is safer or more reliable than the version it replaces. Unpaired seed sets also confound policy changes with changes in initial conditions. Paired experiments hold the world constant, expose regressions directly, and make the decision criteria visible before a release is accepted.

## Requirements

- Persist experiments independently of the browser and link immutable candidate and baseline batches.
- Use the same deduplicated 1–50 seeds, scenario version, and engine for both policies.
- Pair candidate and baseline runs by seed.
- Report pass rate, pass-rate delta, completed pairs, and paired mean metric deltas.
- Include collision count, peak contact force, simulated duration, and actuator energy.
- Explain failures using failed evaluator checks and runtime errors.
- Apply configurable gates only after every pair reaches a terminal state.
- Allow an active experiment or batch to be cancelled without discarding partial evidence.
- Export the complete result as JSON, tabular per-seed data as CSV, and CI failures as JUnit XML.
- Provide a `praxis evaluate` command whose exit code is zero only when all gates pass.
- Show verdicts, gates, and per-seed rows in Praxis Lab; selecting a row opens its candidate replay.

## Experiment contract

The experiment stores policy IDs, scenario ID, engine ID, ordered seeds, gate configuration, candidate batch ID, baseline batch ID, and creation time. These inputs do not change after creation. Derived status, summaries, pairs, gates, and verdict are calculated from the linked runs so polling always reflects durable queue state.

Default gates:

- Candidate pass rate must be at least 90%.
- Candidate pass rate may not fall below baseline.
- Mean collisions may not increase.
- Mean peak contact force may not increase.
- Mean simulated duration may increase by at most two seconds.

Each threshold is an experiment input and is preserved with the result. A pending or partially cancelled experiment has no release verdict; it cannot accidentally pass.

## CLI and CI behavior

`praxis evaluate` creates an experiment through the same public API used by the dashboard, polls until it is terminal, prints gates, and optionally writes JSON, CSV, and JUnit files. Exit codes are stable: `0` means all gates passed, `1` means the experiment completed but failed a gate, and `2` means the request, polling, or export failed.

## Acceptance criteria

- Safe-versus-safe paired evaluation passes.
- Risky-versus-safe paired evaluation fails and identifies the failed safety checks.
- Candidate and baseline members have identical seed sets.
- A regression produces non-zero CLI exit status and a failing JUnit testsuite.
- CSV contains one record per seed with both run IDs and metric deltas.
- Cancellation prevents queued members from starting and retains terminal/partial records.
- Dashboard and API expose the same verdict and gate values.
- Python tests and production web build pass.

## Validity and current limits

The current gates compare deterministic paired samples and paired arithmetic means. They do not yet calculate confidence intervals, account for multiple scenarios, or determine statistical power. A five-seed run is useful during development but is not evidence of broad policy reliability. Policies remain process-isolated rather than security-sandboxed, and the current warehouse physics validity envelope remains simplified.

## Next sprint

Add experiment history and comparison, scenario suites, concurrency controls, confidence intervals with minimum sample guidance, and a first containerized policy runner. Then calibrate task-specific gates against recorded failures instead of relying only on engineering defaults.
