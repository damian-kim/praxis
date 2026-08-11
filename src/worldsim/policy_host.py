from __future__ import annotations

import argparse
import contextlib
import json
import sys
import traceback

from .contracts import PolicyAction, PolicyObservation
from .policy import EpisodeContext, load_policy
from .policy_runtime import PROTOCOL_VERSION


def emit(message: dict) -> None:
    sys.stdout.write(json.dumps(message, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy-id", required=True)
    args = parser.parse_args()
    try:
        policy = load_policy(args.policy_id)
        for line in sys.stdin:
            message = json.loads(line)
            message_type = message.get("type")
            if message_type == "init":
                if message.get("protocol_version") != PROTOCOL_VERSION:
                    raise ValueError("Unsupported policy protocol version")
                context = EpisodeContext(**message["context"])
                with contextlib.redirect_stdout(sys.stderr):
                    policy.reset(context)
                emit({"type": "ready", "protocol_version": PROTOCOL_VERSION})
            elif message_type == "step":
                observation = PolicyObservation.model_validate(message["observation"])
                with contextlib.redirect_stdout(sys.stderr):
                    action = PolicyAction.model_validate(policy.act(observation))
                emit({"type": "action", "action": action.model_dump()})
            elif message_type == "close":
                return 0
            else:
                raise ValueError(f"Unknown protocol message: {message_type}")
    except Exception as exc:
        emit({"type": "error", "error": f"{type(exc).__name__}: {exc}"})
        traceback.print_exc(file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

