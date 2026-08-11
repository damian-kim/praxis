from __future__ import annotations

import json
import queue
import subprocess
import sys
import threading
from dataclasses import asdict

from .contracts import PolicyAction, PolicyObservation
from .policy import EpisodeContext


PROTOCOL_VERSION = "1.0"


class PolicyRuntimeError(RuntimeError):
    pass


class IsolatedPolicyClient:
    def __init__(self, policy_id: str, context: EpisodeContext, timeout_ms: int = 100):
        self.policy_id = policy_id
        self.context = context
        self.timeout_ms = timeout_ms
        self.process: subprocess.Popen | None = None
        self.messages: queue.Queue[str | None] = queue.Queue()
        self.stderr_tail: list[str] = []

    def start(self) -> None:
        self.process = subprocess.Popen(
            [sys.executable, "-m", "worldsim.policy_host", "--policy-id", self.policy_id],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", bufsize=1,
        )
        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=self._read_stderr, daemon=True).start()
        self._send({"type": "init", "protocol_version": PROTOCOL_VERSION, "context": asdict(self.context)})
        message = self._receive(timeout_ms=max(1000, self.timeout_ms * 10))
        if message.get("type") != "ready":
            self.close()
            raise PolicyRuntimeError(message.get("error", "Policy host failed to initialize"))

    def act(self, observation: PolicyObservation) -> PolicyAction:
        if not self.process:
            raise PolicyRuntimeError("Policy host is not started")
        self._send({"type": "step", "observation": observation.model_dump()})
        message = self._receive(self.timeout_ms)
        if message.get("type") == "error":
            raise PolicyRuntimeError(message.get("error", "Policy returned an error"))
        if message.get("type") != "action":
            raise PolicyRuntimeError(f"Unexpected policy message: {message.get('type')}")
        return PolicyAction.model_validate(message.get("action"))

    def close(self) -> None:
        process = self.process
        self.process = None
        if not process:
            return
        if process.poll() is None:
            try:
                if process.stdin:
                    process.stdin.write(json.dumps({"type": "close"}) + "\n")
                    process.stdin.flush()
                process.wait(timeout=1)
            except (BrokenPipeError, subprocess.TimeoutExpired):
                process.terminate()
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    process.kill()
        for stream in (process.stdin, process.stdout, process.stderr):
            if stream:
                stream.close()

    def _send(self, message: dict) -> None:
        if not self.process or not self.process.stdin or self.process.poll() is not None:
            details = " | ".join(self.stderr_tail[-3:])
            raise PolicyRuntimeError(f"Policy process exited unexpectedly{': ' + details if details else ''}")
        try:
            self.process.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
            self.process.stdin.flush()
        except BrokenPipeError as exc:
            raise PolicyRuntimeError("Policy process closed its input") from exc

    def _receive(self, timeout_ms: int) -> dict:
        try:
            line = self.messages.get(timeout=timeout_ms / 1000)
        except queue.Empty as exc:
            self.close()
            raise PolicyRuntimeError(f"Policy decision exceeded {timeout_ms} ms deadline") from exc
        if line is None:
            details = " | ".join(self.stderr_tail[-3:])
            raise PolicyRuntimeError(f"Policy process ended without a response{': ' + details if details else ''}")
        try:
            return json.loads(line)
        except json.JSONDecodeError as exc:
            raise PolicyRuntimeError("Policy host emitted invalid JSON") from exc

    def _read_stdout(self) -> None:
        assert self.process and self.process.stdout
        for line in self.process.stdout:
            self.messages.put(line)
        self.messages.put(None)

    def _read_stderr(self) -> None:
        assert self.process and self.process.stderr
        for line in self.process.stderr:
            self.stderr_tail.append(line.strip())
            if len(self.stderr_tail) > 50:
                del self.stderr_tail[:10]

    def __enter__(self) -> "IsolatedPolicyClient":
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

