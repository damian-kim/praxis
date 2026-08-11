from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def parse_seeds(value: str) -> list[int]:
    seeds = []
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        if ".." in part:
            start_text, end_text = part.split("..", 1)
            start, end = int(start_text), int(end_text)
            if end < start:
                raise ValueError("Seed ranges must be ascending")
            seeds.extend(range(start, end + 1))
        else:
            seeds.append(int(part))
    unique = list(dict.fromkeys(seeds))
    if not unique or len(unique) > 50 or any(seed < 0 for seed in unique):
        raise ValueError("Provide 1–50 non-negative seeds")
    return unique


def request_json(url: str, method: str = "GET", payload: dict | None = None) -> dict:
    body = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(url, data=body, method=method,
                                     headers={"Content-Type": "application/json"} if body else {})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        details = exc.read().decode(errors="replace")
        raise RuntimeError(f"Praxis API returned {exc.code}: {details}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Cannot reach Praxis API at {url}: {exc.reason}") from exc


def download(url: str, path: Path) -> None:
    with urllib.request.urlopen(url, timeout=30) as response:
        path.write_bytes(response.read())


def evaluate(args: argparse.Namespace) -> int:
    try:
        seeds = parse_seeds(args.seeds)
        payload = {
            "scenario_id": args.scenario,
            "candidate_policy_id": args.candidate,
            "baseline_policy_id": args.baseline,
            "engine_id": args.engine,
            "seeds": seeds,
            "gates": {
                "min_candidate_pass_rate": args.fail_under,
                "max_pass_rate_drop": args.max_pass_rate_drop,
                "max_mean_collision_increase": args.max_collision_increase,
                "max_mean_force_increase_n": args.max_force_increase,
                "max_mean_duration_increase_s": args.max_duration_increase,
            },
        }
        api_url = args.api_url.rstrip("/")
        experiment = request_json(f"{api_url}/api/experiments", "POST", payload)
        print(f"Created {experiment['id']} with {len(seeds)} paired seeds")
        if args.no_wait:
            return 0
        last_completed = -1
        while experiment["status"] != "complete":
            completed = experiment["summary"]["completed_pairs"]
            if completed != last_completed:
                print(f"Completed pairs: {completed}/{experiment['summary']['total_pairs']}")
                last_completed = completed
            time.sleep(args.poll_interval)
            experiment = request_json(f"{api_url}/api/experiments/{experiment['id']}")
        summary = experiment["summary"]
        print(f"Candidate pass rate: {summary['candidate_pass_rate']:.1%}")
        print(f"Baseline pass rate:  {summary['baseline_pass_rate']:.1%}")
        for gate in experiment["gate_results"]:
            print(f"{'PASS' if gate['passed'] else 'FAIL'} {gate['id']}: {gate['actual']} {gate['operator']} {gate['limit']}")
        for format_name in ("json", "csv", "junit"):
            target = getattr(args, format_name)
            if target:
                download(f"{api_url}/api/experiments/{experiment['id']}/export?format={format_name}", Path(target))
        print(f"Experiment verdict: {experiment['verdict'].upper()}")
        return 0 if experiment["verdict"] == "pass" else 1
    except (ValueError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="praxis", description="Praxis Worlds evaluation CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)
    command = subparsers.add_parser("evaluate", help="Compare a candidate policy against a baseline")
    command.add_argument("--candidate", required=True)
    command.add_argument("--baseline", default="baseline_safe")
    command.add_argument("--scenario", default="warehouse_v0")
    command.add_argument("--engine", choices=["mujoco_v1", "deterministic_mock_v1"], default="mujoco_v1")
    command.add_argument("--seeds", default="1..5")
    command.add_argument("--fail-under", type=float, default=.9)
    command.add_argument("--max-pass-rate-drop", type=float, default=0)
    command.add_argument("--max-collision-increase", type=float, default=0)
    command.add_argument("--max-force-increase", type=float, default=0)
    command.add_argument("--max-duration-increase", type=float, default=2)
    command.add_argument("--api-url", default="http://127.0.0.1:8010")
    command.add_argument("--poll-interval", type=float, default=.5)
    command.add_argument("--no-wait", action="store_true")
    command.add_argument("--json")
    command.add_argument("--csv")
    command.add_argument("--junit")
    command.set_defaults(func=evaluate)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
