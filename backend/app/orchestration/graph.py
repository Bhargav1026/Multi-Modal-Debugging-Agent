from __future__ import annotations

from typing import Any, Dict, Optional, TypedDict, List
import re
import os

__all__ = ["build_graph"]


class State(TypedDict, total=False):
    """Pipeline state passed between steps.
    - incident: free-form description (repo path, error message, etc.)
    - log: optional raw log text
    - rca: human-readable analysis text
    - patch: unified diff string (optional)
    - test: minimal failing test or reproduction snippet (optional)
    - exception/file/context: structured fields the webview can show besides `rca`
    """
    incident: str
    log: Optional[str]
    rca: str
    patch: Optional[str]
    test: Optional[str]
    exception: Optional[str]
    file: Optional[str]
    context: Optional[List[str]]


# ------------------------- log parsing ---------------------------------------

def _summarize_log(log: str) -> Dict[str, Any]:
    """
    Parse a log string heuristically and produce:
      - exception name/message if present (Python-style)
      - likely file:line location (Python or JS-ish stack)
      - a short context block around the last error-like line
      - a ready-to-render summary string
    """
    lines = log.splitlines()
    if not lines:
        return {
            "exception": None,
            "file": None,
            "context": [],
            "summary": "- No log content provided.",
        }

    lowered = [ln.lower() for ln in lines]

    # Heuristics for error anchors
    keywords = ("traceback", "error", "exception", "fatal", "failed")
    anchor_idx = -1
    for idx in range(len(lines) - 1, -1, -1):
        if any(k in lowered[idx] for k in keywords):
            anchor_idx = idx
            break

    # Try to scrape an exception name (Python-style) from the tail
    exc = None
    exc_pat = re.compile(r"(?P<err>(?:[A-Za-z_][\w\.]*Error|Exception))(?:\: (?P<msg>.*))?$")
    for idx in range(len(lines) - 1, -1, -1):
        m = exc_pat.search(lines[idx])
        if m:
            err = m.group("err")
            msg = (m.group("msg") or "").strip()
            exc = f"{err}: {msg}" if msg else err
            break

    # File locations (Python)
    file_loc = None
    py_file_pat = re.compile(r'File\s+"([^"]+)",\s+line\s+(\d+)')
    for idx in range(len(lines) - 1, -1, -1):
        m = py_file_pat.search(lines[idx])
        if m:
            file_loc = f'{m.group(1)}:{m.group(2)}'
            break

    # Fallback: JS/TS/Py stack-ish "path:line:col"
    if not file_loc:
        js_loc_pat = re.compile(r"([A-Za-z]:)?[^\s:]+\.(?:js|ts|py|tsx|jsx|mjs|cjs):\d+(?::\d+)?")
        for idx in range(len(lines) - 1, -1, -1):
            m = js_loc_pat.search(lines[idx])
            if m:
                file_loc = m.group(0)
                break

    # Build a short context block around anchor
    ctx_idx = anchor_idx if anchor_idx != -1 else len(lines) - 1
    ctx_start = max(0, ctx_idx - 3)
    ctx_end = min(len(lines), ctx_idx + 3)
    context = lines[ctx_start:ctx_end]

    parts: List[str] = []
    if exc:
        parts.append(f"- Suspected exception: {exc}")
    if file_loc:
        parts.append(f"- Likely location: {file_loc}")
    if anchor_idx != -1:
        parts.append("- Context around last error:")
    else:
        parts.append("- Tail of log:")
    parts.extend([f"    {ln}" for ln in context])

    return {
        "exception": exc,
        "file": file_loc,
        "context": context,
        "summary": "\n".join(parts),
    }


# ------------------------- suggestions ---------------------------------------

def _lang_from_path(path: Optional[str]) -> str:
    if not path:
        return "python"
    p = path.lower()
    if p.endswith(('.ts', '.tsx')):
        return 'ts'
    if p.endswith(('.js', '.mjs', '.cjs', '.jsx')):
        return 'js'
    if p.endswith('.py'):
        return 'python'
    return 'python'


def _make_patch(file: Optional[str], exc: Optional[str], ctx: List[str]) -> Optional[str]:
    """Create a minimal unified diff suggestion based on exception heuristics."""
    if not exc and not file:
        return None
    lang = _lang_from_path(file)
    file_display = file or 'unknown_file.py'
    h = exc or 'Issue'

    # Generic suggestions by error family
    suggestion = None
    if exc and ('KeyError' in exc):
        if lang == 'python':
            suggestion = (
                "# Guard missing dict key and use .get() with default\n"
                "try:\n    value = payload.get('id')\n    if value is None:\n        raise KeyError('id')\nexcept KeyError:\n    value = generate_default_id(payload)\n"
            )
    elif exc and ('AttributeError' in exc and 'NoneType' in exc):
        suggestion = (
            "# Check for None before attribute access\n"
            "if obj is None:\n    return handle_none_case()\n# else safe to access obj.attr\n"
        )
    elif exc and ('TypeError' in exc and 'missing' in exc.lower()):
        suggestion = (
            "# Ensure caller provides required arguments or define defaults\n"
            "def func(required, optional=None):\n    ...\n"
        )
    elif exc and ('ModuleNotFoundError' in exc or 'ImportError' in exc):
        suggestion = (
            "# Fix import: check package name and add to requirements\n"
            "# e.g., pip install <package> and correct 'import x'\n"
        )
    elif exc and ('FileNotFoundError' in exc):
        suggestion = (
            "# Ensure directory exists before writing\n"
            "from pathlib import Path\nPath(path).parent.mkdir(parents=True, exist_ok=True)\n"
        )
    elif exc and ('ValueError' in exc):
        suggestion = (
            "# Validate inputs before casting/using\n"
            "if not is_valid(value):\n    raise ValueError('invalid value')\n"
        )

    if suggestion is None:
        suggestion = "# Apply appropriate guard/validation based on the exception and context\n"

    # We don't know the exact original line; provide an add-only patch block
    patch = (
        f"--- a/{file_display}\n"
        f"+++ b/{file_display}\n"
        f"@@\n"
        f"+{suggestion}"
    )
    return patch


def _make_test(file: Optional[str], exc: Optional[str], ctx: List[str]) -> Optional[str]:
    """Create a minimal reproduction test snippet."""
    lang = _lang_from_path(file)
    if lang == 'python':
        name = os.path.basename(file or 'module.py').replace('.', '_')
        lines = [
            "import pytest",
            "",
            f"def test_rca_smoke_{name}():",
            "    \"\"\"Minimal repro based on RCA. Fill in real inputs.\n"
            f"    Exception: {exc or 'n/a'}\n"
            + ("    Context: " + " | ".join(ctx[-3:]) if ctx else "") + "\n\n    \"\"\"",
            "    # TODO: Call the failing function with realistic inputs",
            "    # result = target_fn(...)",
            "    # assert result == expected",
            "    assert True  # Replace with real assertion",
            "",
        ]
        return "\n".join(lines)
    else:
        # JS/TS skeleton
        lines = [
            "import assert from 'node:assert'",
            "describe('rca-smoke', () => {",
            "  it('reproduces and asserts expected behavior', () => {",
            f"    // Exception: {exc or 'n/a'}",
            f"    // Context: {' | '.join(ctx[-3:]) if ctx else ''}",
            "    // TODO: call the function with realistic inputs",
            "    assert.ok(true)",
            "  })",
            "})",
            "",
        ]
        return "\n".join(lines)


# ------------------------- steps --------------------------------------------

def _analyze(state: State) -> State:
    incident = state.get("incident") or "<unknown>"
    log = state.get("log")

    if isinstance(log, str) and log.strip():
        parsed = _summarize_log(log)
        state["exception"] = parsed["exception"]
        state["file"] = parsed["file"]
        state["context"] = parsed["context"]
        # Add quick tips if we recognized something
        tips = []
        if parsed["exception"]:
            tips.append("- Consider adding guards/validation where the exception originates.")
        if parsed["file"]:
            tips.append(f"- Inspect the code around {parsed['file']}.")
        summary = parsed["summary"] + ("\n" + "\n".join(tips) if tips else "")
        state["rca"] = "Initial RCA based on provided logs:\n" + summary
    else:
        state["rca"] = f"Initial RCA: analyzed incident '{incident}'."
        state.setdefault("exception", None)
        state.setdefault("file", None)
        state.setdefault("context", [])

    return state


def _generate_patch(state: State) -> State:
    # If already provided, keep them
    if state.get("patch") is not None and state.get("test") is not None:
        return state

    exc = state.get("exception")
    file = state.get("file")
    ctx = state.get("context") or []

    patch = _make_patch(file, exc, ctx)
    test = _make_test(file, exc, ctx)

    # Only set if not already present
    if state.get("patch") is None:
        state["patch"] = patch
    if state.get("test") is None:
        state["test"] = test

    return state


def _verify(state: State) -> State:
    # Placeholder for future verification/sandbox run
    return state


# --- Minimal stub graph (used if LangGraph is unavailable) -------------------

class _StubGraph:
    def __init__(self) -> None:
        self._steps = (_analyze, _generate_patch, _verify)

    def invoke(self, state: Dict[str, Any]) -> Dict[str, Any]:
        s: State = dict(state)  # shallow copy
        for step in self._steps:
            s = step(s)
        return s  # type: ignore[return-value]


# --- Public factory ----------------------------------------------------------

def build_graph():  # -> CompiledGraph | _StubGraph
    """Return a runnable graph. Falls back to a stub if LangGraph isn't installed.

    The returned object exposes `.invoke(state_dict)` and yields an updated state.
    """
    try:
        from langgraph.graph import StateGraph, END  # type: ignore

        g = StateGraph(State)
        g.add_node("analyze", _analyze)
        g.add_node("generate_patch", _generate_patch)
        g.add_node("verify", _verify)
        g.set_entry_point("analyze")
        g.add_edge("analyze", "generate_patch")
        g.add_edge("generate_patch", "verify")
        g.add_edge("verify", END)
        return g.compile()
    except Exception:
        # No LangGraph (or it failed to import/compile): use the stub.
        return _StubGraph()