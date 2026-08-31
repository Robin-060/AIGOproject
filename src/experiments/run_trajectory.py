"""Actual execution trajectory writer for the formal A reproduction run."""

from __future__ import annotations

import json
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from src.trust_engine.config_loader import canonical_sha256


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def git_state(root: Path) -> dict:
    def run(*args: str) -> str:
        try:
            return subprocess.run(
                ["git", *args], cwd=root, check=True, capture_output=True,
                text=True,
            ).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            return "UNKNOWN"

    status = run("status", "--porcelain")
    return {
        "commit": run("rev-parse", "HEAD"),
        "branch": run("branch", "--show-current"),
        "dirty_at_start": bool(status and status != "UNKNOWN"),
        "dirty_paths_at_start": status.splitlines() if status not in ("", "UNKNOWN") else [],
    }


class RunTrajectory:
    def __init__(self, root: Path, frozen, command: str):
        self.root = root
        self.frozen = frozen
        self.command = command
        self.run_id = f"formal-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{uuid4().hex[:8]}"
        self.events: list[dict] = []
        self.started_monotonic = time.monotonic()
        self.started_utc = utc_now()
        self.git = git_state(root)
        self.events.append({
            "type": "run_start",
            "run_id": self.run_id,
            "timestamp_utc": self.started_utc,
            "command": command,
            "git": self.git,
            "config_version": frozen.version,
            "config_hash": frozen.sha256,
            "parent_config": frozen.parent,
            "selected_profile": frozen.selected_profile,
            "seeds": {
                "global": int(frozen.raw["seeds"]["global_seed"]),
                "random_baseline": frozen.random_seeds,
                "bootstrap": frozen.bootstrap_seed,
            },
            "run_controls": dict(frozen.raw["run_controls"]),
            "expected_frozen_artifact_hashes": dict(frozen.raw["frozen_artifacts"]),
            "environment": {
                "python": sys.version.split()[0],
                "platform": platform.platform(),
            },
        })

    def run_step(self, step_number: int, name: str, function, outputs: list[str]):
        started = time.monotonic()
        self.events.append({
            "type": "step_start",
            "run_id": self.run_id,
            "step": step_number,
            "name": name,
            "timestamp_utc": utc_now(),
        })
        try:
            function()
        except Exception as exc:
            self.events.append({
                "type": "step_end",
                "run_id": self.run_id,
                "step": step_number,
                "name": name,
                "status": "FAILED",
                "duration_s": round(time.monotonic() - started, 3),
                "error_type": type(exc).__name__,
                "error": str(exc),
                "timestamp_utc": utc_now(),
            })
            raise

        artifacts = {}
        missing = []
        for rel in outputs:
            path = self.root / rel
            if path.is_file():
                artifacts[rel] = canonical_sha256(path)
            else:
                missing.append(rel)
        if missing:
            raise FileNotFoundError(
                f"Step {step_number} did not produce: {', '.join(missing)}"
            )
        self.events.append({
            "type": "step_end",
            "run_id": self.run_id,
            "step": step_number,
            "name": name,
            "status": "COMPLETED",
            "duration_s": round(time.monotonic() - started, 3),
            "output_hashes": artifacts,
            "timestamp_utc": utc_now(),
        })

    def finish(self, path: Path, final_outputs: list[str]) -> None:
        output_hashes = {}
        for rel in final_outputs:
            artifact = self.root / rel
            if not artifact.is_file():
                raise FileNotFoundError(f"Formal run output missing: {rel}")
            output_hashes[rel] = canonical_sha256(artifact)
        self.events.append({
            "type": "run_end",
            "run_id": self.run_id,
            "status": "COMPLETED",
            "duration_s": round(time.monotonic() - self.started_monotonic, 3),
            "timestamp_utc": utc_now(),
            "output_hashes": output_hashes,
            "human_intervention": bool(
                self.frozen.raw["run_controls"]["human_intervention_during_run"]
            ),
            "best_of_n": bool(self.frozen.raw["run_controls"]["best_of_n"]),
            "retries": int(self.frozen.raw["run_controls"]["retries"]),
            "selected_from_multiple_runs": bool(
                self.frozen.raw["run_controls"]["multiple_formal_runs_selected"]
            ),
        })
        path.write_text(
            "\n".join(json.dumps(event, ensure_ascii=False) for event in self.events)
            + "\n",
            encoding="utf-8",
        )
