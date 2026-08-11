# Policy Process Protocol 1.0

Transport: UTF-8 newline-delimited JSON over subprocess stdin/stdout.

## Lifecycle

1. Parent sends `{"type":"init","protocol_version":"1.0","context":...}`.
2. Host responds `{"type":"ready","protocol_version":"1.0"}`.
3. Parent sends one `step` message per 10 Hz control interval.
4. Host responds with exactly one `action` before the configured deadline.
5. Parent sends `{"type":"close"}` after any terminal state.

Errors use `{"type":"error","error":"..."}`. Policy stdout is redirected to stderr while `reset` and `act` execute. The current local subprocess is a reliability boundary, not a hostile-code sandbox.

