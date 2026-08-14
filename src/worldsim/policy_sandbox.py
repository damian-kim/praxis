from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass


class PolicyRunnerConfigurationError(ValueError):
    pass


@dataclass(frozen=True)
class PolicyRunnerConfig:
    mode: str = "process"
    docker_image: str = "praxis-policy-runner:local"
    cpu_limit: float = 1.0
    memory_mb: int = 512
    pids_limit: int = 64

    @classmethod
    def from_env(cls) -> "PolicyRunnerConfig":
        config = cls(
            mode=os.getenv("WORLDSIM_POLICY_RUNNER", "process").lower(),
            docker_image=os.getenv("WORLDSIM_POLICY_DOCKER_IMAGE", "praxis-policy-runner:local"),
            cpu_limit=float(os.getenv("WORLDSIM_POLICY_CPU_LIMIT", "1")),
            memory_mb=int(os.getenv("WORLDSIM_POLICY_MEMORY_MB", "512")),
            pids_limit=int(os.getenv("WORLDSIM_POLICY_PIDS_LIMIT", "64")),
        )
        if config.mode not in {"process", "docker"}:
            raise PolicyRunnerConfigurationError("WORLDSIM_POLICY_RUNNER must be 'process' or 'docker'")
        if config.cpu_limit <= 0 or config.memory_mb < 64 or config.pids_limit < 16:
            raise PolicyRunnerConfigurationError("Policy runner limits must be positive and memory must be at least 64 MB")
        return config

    def command(self, policy_id: str, python_executable: str) -> list[str]:
        host_args = ["-m", "worldsim.policy_host", "--policy-id", policy_id]
        if self.mode == "process":
            return [python_executable, *host_args]
        if not shutil.which("docker"):
            raise PolicyRunnerConfigurationError(
                "Docker policy runner requested but the docker CLI is unavailable. Install/start Docker or set WORLDSIM_POLICY_RUNNER=process."
            )
        return [
            "docker", "run", "--rm", "-i", "--network", "none", "--read-only",
            "--cpus", str(self.cpu_limit), "--memory", f"{self.memory_mb}m",
            "--pids-limit", str(self.pids_limit), "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges", "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
            self.docker_image, "python", *host_args,
        ]

    def diagnostics(self) -> dict:
        docker_cli = shutil.which("docker")
        daemon_available = False
        daemon_error = None
        if docker_cli:
            try:
                result = subprocess.run([docker_cli, "info", "--format", "{{.ServerVersion}}"],
                                        capture_output=True, text=True, timeout=4, check=False)
                daemon_available = result.returncode == 0
                if not daemon_available:
                    daemon_error = (result.stderr or result.stdout).strip().splitlines()[-1]
            except (OSError, subprocess.TimeoutExpired) as exc:
                daemon_error = str(exc)
        return {
            "configured_mode": self.mode,
            "process": {"available": True, "security_boundary": False, "description": "Separate OS process with a hard decision deadline"},
            "docker": {
                "available": bool(docker_cli) and daemon_available, "cli_available": bool(docker_cli),
                "daemon_available": daemon_available, "error": daemon_error,
                "cli": docker_cli, "image": self.docker_image,
                "security_boundary": True, "network": "none", "read_only": True,
                "cpu_limit": self.cpu_limit, "memory_mb": self.memory_mb, "pids_limit": self.pids_limit,
            },
        }
