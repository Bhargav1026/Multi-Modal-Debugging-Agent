from __future__ import annotations
from typing import Optional, List, Union
import os
import shlex
import subprocess

from fastapi import APIRouter
from pydantic import BaseModel, Field

# -------------------- models --------------------
class PytestRequest(BaseModel):
    repo: str = Field(default=".", description="Repository/workdir to run from")
    path: Union[str, List[str]] = Field(
        default="tests",
        description="File(s) or directory(ies) to pass to pytest (string or list)"
    )
    extra: Optional[str] = Field(default=None, description="Extra CLI flags for pytest (e.g. '-k smoke')")
    quiet: Optional[bool] = Field(default=False, description="Append -q to pytest flags")
    useDocker: Optional[bool] = Field(default=None, description="Override Docker usage for this call")
    timeoutSec: int = Field(default=600, ge=1, description="Timeout in seconds")

class PytestResponse(BaseModel):
    ok: bool
    returncode: int
    stdout: str
    stderr: str
    cmd: str
    cwd: str

# -------------------- core runner --------------------

def run_pytest(
    repo: str,
    target: Union[str, List[str]] = ".",
    timeout_sec: int = 600,
    extra: str = "",
    use_docker: Optional[bool] = None,
) -> dict:
    """Run pytest locally or inside Docker.

    * `extra` is a string of CLI flags (e.g. "-q -k smoke").
    * Decides Docker usage from env unless `use_docker` is explicitly passed.
    """
    # ---- decide whether to use docker ----
    if use_docker is None:
        mode = os.getenv("SANDBOX_MODE", "local").strip().lower()
        use_docker = mode == "docker" or str(os.getenv("RUNNER_USE_DOCKER", "")).lower() in {"1", "true", "yes", "on"}

    repo_abs = os.path.abspath(repo or ".")

    # Normalize targets: accept "tests backend/tests" or ["tests", "backend/tests"]
    if isinstance(target, list):
        target_args = [str(t) for t in target if str(t).strip()]
    elif isinstance(target, str):
        target_args = shlex.split(target or ".")
    else:
        target_args = [str(target)]

    # Always work with a *list* of args; never mix str + list.
    extra_args = shlex.split(extra or "")

    if use_docker:
        image = os.getenv("DOCKER_IMAGE", "python:3.11")
        network = os.getenv("RUNNER_NETWORK", "bridge")
        bootstrap = str(os.getenv("RUNNER_BOOTSTRAP_PYTEST", "")).lower() in {"1", "true", "yes", "on"}

        # Decide what to mount as /workspace:
        # - If API runs from .../backend but targets include "backend/...", mount the project root.
        mount_root = repo_abs
        if os.path.basename(repo_abs) == "backend" and any(str(t).startswith("backend/") for t in target_args):
            mount_root = os.path.dirname(repo_abs)

        # Base docker invocation: mount the chosen root, run from /workspace
        base = [
            "docker", "run", "--rm",
            "-v", f"{mount_root}:/workspace",
            "-w", "/workspace",
            "--network", network,
            image,
        ]

        # Determine a requirements file to install (if any)
        req_env = os.getenv("RUNNER_REQUIREMENTS", "").strip()
        candidates = [req_env] if req_env else ["backend/requirements.txt", "requirements.txt"]
        req_path = next((c for c in candidates if c and os.path.exists(os.path.join(mount_root, c))), None)

        # Ensure our backend package is importable inside the container
        env_prefix = 'export PYTHONPATH="/workspace/backend:$PYTHONPATH";'
        run_py = " ".join(shlex.quote(a) for a in (["pytest"] + extra_args + target_args))

        if bootstrap:
            # Upgrade pip, install requirements (if found), then pytest, and run
            steps = [
                "python -m pip install -q --upgrade pip",
            ]
            if req_path:
                # Resolve against mount_root so a relative "backend/requirements.txt"
                # does not get interpreted relative to the server's CWD (which is
                # often ".../backend"), which caused "backend/backend/requirements.txt"
                # to appear inside the container.
                req_abs = req_path if os.path.isabs(req_path) else os.path.join(mount_root, req_path)
                req_rel = os.path.relpath(req_abs, mount_root)  # path visible from /workspace
                req_in_container = shlex.quote(req_rel)
                steps.append(f"pip install -q -r {req_in_container}")
            steps.append("pip install -q pytest")
            inner = " && ".join(steps + [env_prefix + " " + run_py])
            argv = base + ["bash", "-lc", inner]
        else:
            # No bootstrap: rely on image having deps; still set PYTHONPATH
            inner = env_prefix + " " + run_py
            argv = base + ["bash", "-lc", inner]
    else:
        argv = ["pytest", *extra_args, *target_args]

    cmd_str = " ".join(shlex.quote(a) for a in argv)

    completed = subprocess.run(
        argv,
        cwd=repo_abs,
        capture_output=True,
        text=True,
        timeout=int(timeout_sec),
        shell=False,
        env=os.environ.copy(),
    )

    return {
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "cmd": cmd_str,
        "cwd": repo_abs,
    }

# -------------------- router & endpoints --------------------

router = APIRouter(prefix="/runner", tags=["runner"])

@router.get("/ping")
async def ping() -> dict:
    return {"ok": True, "service": "runner"}

@router.get("/env")
async def env_info() -> dict:
    return {
        "sandbox_mode": os.getenv("SANDBOX_MODE", "local"),
        "runner_use_docker": os.getenv("RUNNER_USE_DOCKER"),
        "runner_network": os.getenv("RUNNER_NETWORK", "bridge"),
        "docker_image": os.getenv("DOCKER_IMAGE", "python:3.11"),
        "runner_requirements": os.getenv("RUNNER_REQUIREMENTS"),
        "bootstrap_pytest": os.getenv("RUNNER_BOOTSTRAP_PYTEST"),
    }

@router.post("/pytest", response_model=PytestResponse)
async def api_run_pytest(req: PytestRequest) -> PytestResponse:
    # Combine flags safely
    extra = req.extra or ""
    if req.quiet:
        parts = shlex.split(extra)
        if "-q" not in parts:
            parts.append("-q")
        extra = " ".join(parts)

    # Normalize path into a list of pytest targets
    if isinstance(req.path, list):
        targets = [str(p) for p in req.path if str(p).strip()]
    else:
        targets = shlex.split(req.path or "tests")

    out = run_pytest(
        repo=req.repo or ".",
        target=targets,
        timeout_sec=req.timeoutSec,
        extra=extra,
        use_docker=req.useDocker,
    )
    return PytestResponse(**out)