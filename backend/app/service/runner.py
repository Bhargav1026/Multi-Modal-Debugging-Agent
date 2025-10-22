"""Lightweight test runner used by the RCA backend.

This module provides a single public entry point:

    run_pytest(repo: str = ".", target: Optional[str] = None, ...)

It can execute tests either locally (default) or inside Docker when
RUNNER_USE_DOCKER=1 or SANDBOX_MODE=docker. You can also control network via
RUNNER_NETWORK (none|bridge|host) and bootstrap pytest inside the container
with RUNNER_BOOTSTRAP_PYTEST=1 (default). The result is a compact,
JSON‑serializable dict that the API route can return directly to the extension.
"""
from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# --------------------------- summary parsing ---------------------------

_SUMMARY_KEYS = (
    "passed",
    "failed",
    "skipped",
    "errors",
    "warnings",
    "xfailed",
    "xpassed",
)


def _parse_pytest_summary(text: str) -> Dict[str, Any]:
    """Parse common pytest summary lines from stdout/stderr.

    Looks for tokens like "3 passed", "1 failed", etc., and the trailing
    "in 0.12s" duration. Works even with verbose plugins enabled.
    """
    s = text.lower()
    out: Dict[str, Any] = {k: 0 for k in _SUMMARY_KEYS}

    for key in _SUMMARY_KEYS:
        m = re.search(rf"(\d+)\s+{re.escape(key)}\b", s)
        if m:
            out[key] = int(m.group(1))

    # duration: "in 2.34s"
    tm = re.search(r"\bin\s+([0-9]+(?:\.[0-9]+)?)\s*s\b", s)
    if tm:
        try:
            out["time_sec"] = float(tm.group(1))
        except ValueError:
            pass

    # collected N items (helpful to show something even on error)
    cm = re.search(r"collected\s+(\d+)\s+items?", s)
    if cm:
        out["collected"] = int(cm.group(1))

    return out


# --------------------------- subprocess helpers ---------------------------

@dataclass
class RunResult:
    backend: str  # "local" | "docker"
    cmd: List[str]
    returncode: int
    stdout: str
    stderr: str
    duration_ms: int
    started_at: float
    finished_at: float
    summary: Dict[str, Any]

    @property
    def ok(self) -> bool:
        # pytest returns 0 when no tests failed/errored/skipped (skips don't fail)
        failed = int(self.summary.get("failed", 0))
        errors = int(self.summary.get("errors", 0))
        return self.returncode == 0 and failed == 0 and errors == 0

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["ok"] = self.ok
        return d


def _run(cmd: List[str], *, cwd: Path, timeout_sec: int, env: Optional[Dict[str, str]] = None) -> Tuple[int, str, str, int]:
    start = time.time()
    try:
        p = subprocess.run(
            cmd,
            cwd=str(cwd),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout_sec,
        )
        rc, out, err = p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired as e:
        rc, out, err = 124, e.stdout or "", (e.stderr or "") + "\n[runner] timeout exceeded"
    dur_ms = int((time.time() - start) * 1000)
    return rc, out, err, dur_ms


# --------------------------- docker selection ---------------------------

def _truthy(s: Optional[str]) -> bool:
    return str(s or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _have_docker() -> bool:
    return shutil.which("docker") is not None


def _docker_image() -> str:
    # You can override with DOCKER_IMAGE. Default keeps it very small.
    return os.environ.get("DOCKER_IMAGE", "python:3.11-alpine")


def _select_use_docker(user_choice: Optional[bool]) -> bool:
    """
    Determine whether to use docker, in this order of precedence:
    1) explicit function arg (user_choice)
    2) SANDBOX_MODE env ("docker" or "local")
    3) RUNNER_USE_DOCKER env (truthy/falsey)
    Defaults to local if nothing is set.
    """
    if user_choice is not None:
        return bool(user_choice)
    mode = (os.environ.get("SANDBOX_MODE") or "").strip().lower()
    if mode in {"docker", "container"}:
        return True
    if mode in {"local", "venv"}:
        return False
    return _truthy(os.environ.get("RUNNER_USE_DOCKER"))


# --------------------------- public API ---------------------------

def run_pytest(
    repo: str = ".",
    target: Optional[str] = None,
    k: Optional[str] = None,
    extra: Optional[List[str]] = None,
    *,
    timeout_sec: int = 300,
    use_docker: Optional[bool] = None,
    env: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Run pytest for the given repository.

    Parameters
    ----------
    repo : str
        Path to the workspace root containing tests.
    target : Optional[str]
        A specific test path (e.g., "backend/tests/test_rca.py::test_name"). If None, runs default discovery.
    k : Optional[str]
        A pytest -k expression to filter tests.
    extra : Optional[List[str]]
        Additional pytest CLI args (e.g., ["-q"]).
    timeout_sec : int
        Hard timeout for the whole run.
    use_docker : Optional[bool]
        Force docker or local. If None, uses RUNNER_USE_DOCKER env (default False).
    env : Optional[Dict[str, str]]
        Extra environment vars for the process.

    Returns
    -------
    Dict[str, Any]
        JSON‑serializable summary including stdout/stderr and parsed counts.
    """
    repo_path = Path(repo).resolve()
    if not repo_path.exists():
        raise FileNotFoundError(f"repo not found: {repo_path}")

    # Decide backend (arg → SANDBOX_MODE → RUNNER_USE_DOCKER)
    use_docker = _select_use_docker(use_docker)

    # Always include -q unless the caller overrides
    pytest_args: List[str] = ["-q"]
    if extra:
        pytest_args = extra + pytest_args

    if target:
        pytest_args.append(target)
    if k:
        pytest_args += ["-k", k]

    if use_docker and _have_docker():
        backend = "docker"
        image = _docker_image()
        workdir = "/work"

        # We install pytest in-container if missing (fast for alpine, cached after first pull).
        bootstrap = _truthy(os.environ.get("RUNNER_BOOTSTRAP_PYTEST", "1"))

        # Network strategy:
        # - if RUNNER_NETWORK is set, use it verbatim
        # - otherwise: use "bridge" when bootstrapping (pip install), else "none"
        network = os.environ.get("RUNNER_NETWORK")
        if network is None:
            network = "bridge" if bootstrap else "none"
        net_args: List[str] = ["--network", network] if network and network != "default" else []

        inner_cmd = [
            "sh",
            "-lc",
            (
                ("pip install -q pytest >/dev/null 2>&1 || true; " if bootstrap else "")
                + "pytest "
                + " ".join(shlex.quote(a) for a in pytest_args)
            ),
        ]

        cmd = [
            "docker",
            "run",
            "--rm",
            "-t",
            "-v",
            f"{str(repo_path)}:{workdir}",
            "-w",
            workdir,
            *net_args,
            "--cpus",
            "1",
            "--memory",
            "1g",
            "--pids-limit",
            "512",
            image,
            *inner_cmd,
        ]

        rc, out, err, dur_ms = _run(cmd, cwd=repo_path, timeout_sec=timeout_sec, env=os.environ.copy())
        summary = _parse_pytest_summary(out + "\n" + err)
        result = RunResult(
            backend=backend,
            cmd=cmd,
            returncode=rc,
            stdout=out,
            stderr=err,
            duration_ms=dur_ms,
            started_at=time.time() - (dur_ms / 1000.0),
            finished_at=time.time(),
            summary=summary,
        )
        return result.to_dict()

    # Fallback: local run (preferred for MVP because it uses the user's venv)
    backend = "local"
    cmd = [sys.executable, "-m", "pytest", *pytest_args]
    env_vars = os.environ.copy()
    if env:
        env_vars.update(env)

    rc, out, err, dur_ms = _run(cmd, cwd=repo_path, timeout_sec=timeout_sec, env=env_vars)
    summary = _parse_pytest_summary(out + "\n" + err)

    result = RunResult(
        backend=backend,
        cmd=cmd,
        returncode=rc,
        stdout=out,
        stderr=err,
        duration_ms=dur_ms,
        started_at=time.time() - (dur_ms / 1000.0),
        finished_at=time.time(),
        summary=summary,
    )
    return result.to_dict()


__all__ = ["run_pytest"]
