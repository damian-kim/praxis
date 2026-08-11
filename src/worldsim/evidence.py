from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_evidence_bundle(run_dir: Path, evidence: dict) -> dict:
    run_dir.mkdir(parents=True, exist_ok=True)
    evidence_path = run_dir / "evidence.json"
    evidence_path.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    files = {}
    for path in sorted(run_dir.iterdir(), key=lambda item: item.name):
        if path.is_file() and path.name != "manifest.json":
            files[path.name] = {"sha256": sha256_file(path), "bytes": path.stat().st_size}
    manifest = {
        "schema_version": "1.0",
        "run_id": evidence["run_id"],
        "created_at": datetime.now(UTC).isoformat(),
        "algorithm": "sha256",
        "files": files,
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def verify_evidence_bundle(run_dir: Path) -> tuple[bool, int, list[str]]:
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.exists():
        return False, 0, ["manifest.json is missing"]
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return False, 0, [f"manifest.json is invalid: {exc}"]
    errors = []
    checked = 0
    for name, expected in manifest.get("files", {}).items():
        path = run_dir / name
        if not path.exists():
            errors.append(f"{name} is missing")
            continue
        checked += 1
        actual_hash = sha256_file(path)
        if actual_hash != expected.get("sha256"):
            errors.append(f"{name} hash mismatch")
        if path.stat().st_size != expected.get("bytes"):
            errors.append(f"{name} size mismatch")
    return not errors and checked > 0, checked, errors

