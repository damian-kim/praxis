# Policy Process Protocol 1.0

Transport: UTF-8 newline-delimited JSON over subprocess stdin/stdout.

## Lifecycle

1. Parent sends `{"type":"init","protocol_version":"1.0","context":...}`.
2. Host responds `{"type":"ready","protocol_version":"1.0"}`.
3. Parent sends one `step` message per 10 Hz control interval.
4. Host responds with exactly one `action` before the configured deadline.
5. Parent sends `{"type":"close"}` after any terminal state.

Errors use `{"type":"error","error":"..."}`. Policy stdout is redirected to stderr while `reset` and `act` execute.

The protocol has two transports:

- `process` is the default zero-setup reliability boundary. It isolates crashes and enforces the action deadline, but it is not a hostile-code sandbox.
- `docker` preserves the same stdin/stdout protocol inside a no-network, read-only, resource-limited container. Select it with `WORLDSIM_POLICY_RUNNER=docker` after building `praxis-policy-runner:local`.

Run `praxis doctor` to distinguish a missing Docker CLI from an installed client whose daemon is stopped. The selected transport is recorded as `policy_runner_mode` in physics evidence.
