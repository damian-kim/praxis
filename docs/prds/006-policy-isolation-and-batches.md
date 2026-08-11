# PRD 006 — Policy Isolation and Benchmark Batches

Status: implemented for review  
Sprint: 6

## What we are accomplishing

Execute every agent policy outside the physics worker process and add durable multi-seed benchmark batches. A policy that hangs, crashes, prints unexpected output, or misses its decision deadline must fail its own run without taking down MuJoCo, the queue, or another evaluation. Engineers can launch up to 50 deterministic seeds as one benchmark and monitor aggregate completion and pass rate.

## Why we need it

Loading user policy code directly into the simulator gives that code control over worker memory and lifecycle. It also makes a blocked `act` call indistinguishable from a stalled physics engine. Separating policy execution creates the first real isolation boundary and a transport contract that can later move into a container or remote GPU job.

Single episodes are insufficient for evaluating robustness. A behavior that passes seed 42 may fail when package or obstruction placement shifts. Batch entities make seed coverage reproducible, reviewable, and durable instead of relying on manual repeated clicks.

## Requirements

- Built-in and external policies execute in independent subprocesses.
- Parent and policy host communicate only with newline-delimited JSON protocol 1.0.
- Policy stdout cannot corrupt the protocol; user prints are redirected to stderr.
- Every decision has a hard scenario-defined deadline, currently 100 ms.
- Timeout or process failure terminates the child and creates a failed run with partial replay, trace, error event, and verified evidence.
- Policy subprocess closes after success, failure, or cancellation.
- Batch requests accept 1–50 seeds, deduplicate them, and create durable linked runs.
- Batch API reports status counts, completed-run pass rate, and member runs.
- Praxis Lab launches batches, displays aggregate progress, and drills into member runs.

## Protocol

The parent starts `python -m worldsim.policy_host --policy-id <id>`. It sends an `init` message containing the versioned episode context and waits for `ready`. Each `step` sends one schema-1.0 observation and expects one validated schema-1.0 action. `close` requests graceful shutdown. `error` messages carry policy-side validation or execution failures.

A dedicated reader thread is required on Windows because anonymous pipe reads cannot be portably polled with POSIX selectors. The physics thread waits on a bounded queue; a queue timeout terminates the policy process. Stderr is drained separately to prevent pipe backpressure and preserve a short diagnostic tail.

## Batch semantics

A batch stores scenario, policy, engine, ordered unique seeds, creation time, and run membership. Runs remain ordinary independent queue jobs and evidence bundles. Pass rate is calculated only over terminal members, so a running batch never treats queued jobs as failures.

## Acceptance criteria

- Reference safe policy still qualifies grasp and passes through the subprocess boundary.
- Deliberately slow policy exceeds 100 ms, is terminated, and produces an `error` verdict with valid partial evidence.
- External policy prints cannot alter protocol messages.
- Duplicate batch seeds create one run per unique seed.
- Completed safe mock batch aggregates to a 100% pass rate.
- Dashboard and API expose batch progress and results.
- All tests and the production web build pass.

## Current isolation limits

The subprocess has a separate address space and killable lifecycle, but it still runs under the same OS user with inherited filesystem and network permissions. This prevents accidental simulator corruption and enforces timeouts; it is not a security sandbox for hostile code.

## Next sprint

Add benchmark comparison across policies, per-seed delta matrices, batch cancellation, concurrency limits, and CSV/JSON export. For hosted execution, move the existing JSON protocol into restricted containers with CPU, memory, filesystem, and network policies.

