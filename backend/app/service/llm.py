from __future__ import annotations
"""
Provider‑agnostic LLM wrapper for RCA generation.

Usage (env‑driven):
  LLM_BACKEND   = none | openai | gemini
  # OpenAI
  OPENAI_API_KEY= ...
  OPENAI_MODEL  = gpt-4o-mini (default)
  # Gemini
  GOOGLE_API_KEY= ...
  GEMINI_MODEL  = gemini-1.5-flash (default)

Call generate_rca(log_text, repo, code_hint=None, *, path=None) -> dict with keys:
  { rca: str, patch?: str|None, test?: str|None, context?: list[str], file?: str|None, exception?: str|None }

If no keys/API are configured, we return a safe heuristic stub instead of erroring.
"""

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


# ----------------------------- utils -----------------------------

def _truthy(s: Optional[str]) -> bool:
    return str(s or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _shorten(s: str, limit: int = 6000) -> str:
    if len(s) <= limit:
        return s
    head = s[: limit // 2]
    tail = s[-limit // 2 :]
    return head + "\n…\n" + tail


def _extract_exception(log_text: str) -> str:
    # Try to extract the last error line (e.g., Python Traceback or "Error: message")
    lines = [ln.strip() for ln in (log_text or "").splitlines()]
    last_err = ""
    for ln in reversed(lines):
        if not ln:
            continue
        if (
            ln.lower().startswith("error:")
            or ln.lower().startswith("exception:")
            or "traceback" in ln.lower()
            or re.search(r"(error|exception|keyerror|valueerror|typeerror|assertionerror)[: ]", ln, re.I)
        ):
            last_err = ln
            break
    return last_err or (lines[-1] if lines else "")


def _coerce_context(x: Any) -> List[str]:
    if x is None:
        return []
    if isinstance(x, list):
        return [str(v) for v in x if v is not None]
    return [str(x)]


# --------------------------- config model -------------------------

@dataclass
class LLMConfig:
    backend: str = os.environ.get("LLM_BACKEND", "none").strip().lower()
    # OpenAI
    openai_api_key: Optional[str] = os.environ.get("OPENAI_API_KEY")
    openai_model: str = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    # Gemini
    google_api_key: Optional[str] = os.environ.get("GOOGLE_API_KEY")
    gemini_model: str = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")


CFG = LLMConfig()


# --------------------------- prompt maker -------------------------

def _prompt_for_rca(log_text: str, repo: Optional[str] = None, code_hint: Optional[str] = None, file_hint: Optional[str] = None) -> str:
    log_text = _shorten(log_text or "", 8000)
    code_hint = _shorten(code_hint or "", 4000)
    repo_hint = repo or "."
    file_hint = (file_hint or "").strip() or None
    return (
        "You are a senior debugging assistant. Read the log and produce a compact RCA.\n"
        "Return STRICT JSON with keys: rca (string), patch (string or null), test (string or null), context (array of strings).\n"
        "Do not include markdown fences.\n\n"
        f"REPO_HINT: {repo_hint}\n"
        + (f"FILE_HINT: {file_hint}\n" if file_hint else "")
        + (f"CODE_HINT:\n{code_hint}\n" if code_hint else "")
        + f"LOG:\n{log_text}\n"
        "JSON ONLY:"
    )


def _parse_json_or_text(s: str) -> Dict[str, Any]:
    s = s.strip()
    # Best effort: find first JSON block
    try:
        return json.loads(s)
    except Exception:
        pass
    m = re.search(r"\{[\s\S]*\}$", s)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    # Fallback to plain text as RCA
    return {"rca": s}


# ---------------------------- backends ----------------------------

class _OpenAIClient:
    def __init__(self, api_key: str):
        try:
            from openai import OpenAI  # type: ignore
            self.client = OpenAI(api_key=api_key)
            self.mode = "responses" if hasattr(self.client, "responses") else "chat"
        except Exception:  # library missing or incompatible
            raise RuntimeError("openai python package not available")

    def generate(self, model: str, prompt: str) -> str:
        # Prefer modern Responses API; fallback to chat.completions
        try:
            if self.mode == "responses":
                resp = self.client.responses.create(model=model, input=prompt)
                # unify text extraction
                try:
                    return resp.output_text  # type: ignore[attr-defined]
                except Exception:
                    pass
                # Older shapes: pull from content
                c = getattr(resp, "output", None) or getattr(resp, "data", None)
                return str(c)
            else:
                cc = self.client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": "You return JSON only."},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.2,
                )
                return cc.choices[0].message.content or ""
        except Exception as e:
            raise RuntimeError(f"OpenAI call failed: {e}")


class _GeminiClient:
    def __init__(self, api_key: str):
        try:
            import google.generativeai as genai  # type: ignore
            genai.configure(api_key=api_key)
            self.genai = genai
        except Exception:
            raise RuntimeError("google-generativeai package not available")

    def generate(self, model: str, prompt: str) -> str:
        try:
            mdl = self.genai.GenerativeModel(model)
            resp = mdl.generate_content(
                prompt,
                generation_config={
                    "temperature": 0.2,
                    "response_mime_type": "application/json",  # prefer strict JSON
                },
            )
            return getattr(resp, "text", None) or ""
        except Exception as e:
            raise RuntimeError(f"Gemini call failed: {e}")


# --------------------------- public API ---------------------------

def generate_rca(
    log_text: str,
    repo: Optional[str] = None,
    code_hint: Optional[str] = None,
    *,
    path: Optional[str] = None,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """Return an RCA dict using the configured LLM, with safe fallbacks.

    The returned dict always contains at least `rca: str` and may include
    `patch`, `test`, `context: list[str]`, `file`, and `exception`.
    """
    backend = (CFG.backend or "none").lower()

    # If disabled, return a heuristic explanation (never error)
    if backend in {"", "none", "off", "false"}:
        exc = _extract_exception(log_text)
        return {
            "rca": (
                "LLM disabled. Heuristic summary:\n"
                f"Likely failure around: {exc or '(unknown)'}\n"
                "Check the last stack frame and ensure required keys/files exist."
            ),
            "patch": None,
            "test": None,
            "context": [ln for ln in (log_text or "").splitlines()[-12:]],
            "file": path,
            "exception": exc or None,
        }

    prompt = _prompt_for_rca(log_text, repo=repo, code_hint=code_hint, file_hint=path)

    # Route to selected backend
    try:
        if backend == "openai":
            key = CFG.openai_api_key or os.environ.get("OPENAI_API_KEY")
            if not key:
                raise RuntimeError("Missing OPENAI_API_KEY")
            client = _OpenAIClient(key)
            text = client.generate(model or CFG.openai_model, prompt)
        elif backend == "gemini":
            key = CFG.google_api_key or os.environ.get("GOOGLE_API_KEY")
            if not key:
                raise RuntimeError("Missing GOOGLE_API_KEY")
            client = _GeminiClient(key)
            text = client.generate(model or CFG.gemini_model, prompt)
        else:
            # Unknown backend string -> act as disabled
            return {
                "rca": "Unsupported LLM_BACKEND; using heuristic summary.",
                "patch": None,
                "test": None,
                "context": [ln for ln in (log_text or "").splitlines()[-12:]],
                "file": path,
                "exception": _extract_exception(log_text) or None,
            }
    except Exception as e:
        # Never crash the API: degrade gracefully
        exc = _extract_exception(log_text)
        return {
            "rca": f"LLM error ({backend}): {e}.\nHeuristic summary: likely failure around: {exc}",
            "patch": None,
            "test": None,
            "context": [ln for ln in (log_text or "").splitlines()[-12:]],
            "file": path,
            "exception": exc or None,
        }

    # Try to parse model output as JSON; fall back to text as RCA
    data = _parse_json_or_text(text or "")

    # Normalize shape
    rca = str(data.get("rca") or data.get("summary") or "").strip()
    if not rca:
        # fall back to raw model text, then a heuristic if still empty
        rca = (text or "").strip() or f"Heuristic: likely failure around: {_extract_exception(log_text)}"
    patch = data.get("patch")
    test = data.get("test")
    context = _coerce_context(data.get("context"))
    if not context:
        # ensure non-empty list so Pydantic validation never sees a bare string
        context = [ln for ln in (log_text or "").splitlines()[-12:]] or ["(no context)"]

    return {
        "rca": rca,
        "patch": patch if (patch is None or isinstance(patch, str)) else json.dumps(patch, indent=2),
        "test": test if (test is None or isinstance(test, str)) else json.dumps(test, indent=2),
        "context": context,
        "file": path,
        "exception": _extract_exception(log_text) or None,
    }


__all__ = ["generate_rca", "LLMConfig"]
