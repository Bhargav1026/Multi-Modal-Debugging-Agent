from fastapi import APIRouter
from app.models.schemas import RCARequest, RCAResponse
from typing import Any, Dict, Optional, List, Sequence, Union
import hashlib
import traceback
import datetime as _dt
from app.service.storage import read_text_file
# backend/app/api/routes_incidents.py
from app.service.llm import generate_rca as llm_generate_rca

# Final router for Incidents/RCA
router = APIRouter(tags=["incidents"])

# Try optional backends. We prefer the lightweight service handler if present.
try:  # pragma: no cover
    from app.service.handlers import handle  # type: ignore
except Exception:  # pragma: no cover
    handle = None  # type: ignore

# Optional orchestration graph (when you wire LangGraph/agents later)
try:  # pragma: no cover
    from app.orchestration.graph import build_graph  # type: ignore
except Exception:  # pragma: no cover
    build_graph = None  # type: ignore

# Optional LLM RCA (OpenAI/Gemini) if configured
try:  # pragma: no cover
    from app.service.llm import generate_rca as llm_generate_rca  # type: ignore
except Exception:  # pragma: no cover
    llm_generate_rca = None  # type: ignore


def _derive_id(text: str) -> str:
    """Stable short id for ad‑hoc payloads (avoids KeyError: 'id')."""
    return hashlib.sha1((text or "").encode("utf-8")).hexdigest()[:10]


def _exc_to_rca(e: BaseException) -> str:
    """Create a readable RCA summary from an exception with location hints."""
    tb = traceback.extract_tb(e.__traceback__)
    last = tb[-1] if tb else None

    # Some exceptions (e.g., validation) have empty args; be defensive.
    try:
        msg = e.args[0] if getattr(e, "args", ()) else ""
    except Exception:
        msg = ""

    header: List[str] = []
    header.append(f"• Exception: {e.__class__.__name__}" + (f": {msg}" if msg else ""))
    if last:
        header.append(f"• Location: {last.filename}:{last.lineno}")
    return "\n".join(header) if header else e.__class__.__name__


def _as_list_context(value: Optional[Union[str, Sequence[str]]], tail: str) -> Optional[List[str]]:
    """Coerce context into List[str] as required by the schema."""
    if isinstance(value, list):
        return [str(x) for x in value if x is not None and str(x).strip()]
    if isinstance(value, tuple):
        return [str(x) for x in value if x is not None and str(x).strip()]
    if isinstance(value, str):
        s = value.strip()
        return [s] if s else ([tail] if tail else None)
    return [tail] if tail else None


def _mk_response(out: Dict[str, Any], *, fallback_file: Optional[str], note_from_read: Optional[str], tail: str) -> RCAResponse:
    """Uniform mapping from a handler/graph dict to RCAResponse with sensible fallbacks."""
    return RCAResponse(
        rca=str(out.get("rca") or "Initial RCA produced"),
        patch=out.get("patch"),
        test=out.get("test"),
        exception=out.get("exception"),
        file=out.get("file") or fallback_file,
        context=_as_list_context(out.get("context"), tail),
        note=out.get("note") or note_from_read or None,
    )


@router.post("/rca", response_model=RCAResponse)
def run_rca(req: RCARequest) -> RCAResponse:
    """Run the RCA pipeline.

    This endpoint is resilient:
    - Never assumes `id` exists (derives one from log if missing).
    - Prefers `app.service.handlers.handle(event)` if available.
    - Falls back to `orchestration.graph.build_graph()` if present.
    - Always returns a safe RCAResponse instead of raising 500s.
    """
    # Prefer reading from a file path if provided; otherwise use the raw `log`
    note_from_read: Optional[str] = None
    log_text = getattr(req, "log", "") or ""
    req_path = getattr(req, "path", None)
    if req_path:
        try:
            info = read_text_file(req_path, max_bytes=2_097_152, notebook_strategy="cells")
            log_text = info.get("text") or ""
            note_from_read = info.get("note")
        except Exception as e:
            note_from_read = f"Failed to read path {req_path}: {e!s}"

    # Normalize incoming request into an internal event dict
    event: Dict[str, Any] = {
        "id": getattr(req, "id", None) or _derive_id(log_text or ""),
        "repo": getattr(req, "repo", None) or ".",
        "log": log_text,
        "screenshot_b64": getattr(req, "screenshot_b64", None),
        "path": req_path,
        "created_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    }

    tail = (log_text[-800:] if log_text else "")

    # --- Preferred path: lightweight service handler ---
    if handle is not None:
        try:
            out = handle(event)  # expects dict
            if isinstance(out, dict):
                return _mk_response(out, fallback_file=req_path, note_from_read=note_from_read, tail=tail)
            # If a non-dict is returned, still provide a usable response
            return RCAResponse(rca="RCA pipeline executed", patch=None, test=None, file=req_path, context=_as_list_context(None, tail), note=note_from_read)
        except Exception as e:
            # Summarize any failure coming from service handler
            return RCAResponse(rca=_exc_to_rca(e), patch=None, test=None, file=req_path, context=_as_list_context(None, tail), note=note_from_read)

    # --- Optional orchestration path (e.g., LangGraph) ---
    if build_graph is not None:
        try:
            graph = build_graph()
            state = {
                "incident": event["repo"],
                "log": event["log"],
                "screenshot_b64": event["screenshot_b64"],
                "patch": None,
                "test": None,
            }
            if hasattr(graph, "invoke"):
                result = graph.invoke(state)
                if isinstance(result, dict):
                    return _mk_response(result, fallback_file=req_path, note_from_read=note_from_read, tail=tail)
            # If a non-dict is returned, still provide a usable response
            return RCAResponse(rca="RCA pipeline executed", patch=None, test=None, file=req_path, context=_as_list_context(None, tail), note=note_from_read)
        except Exception as e:
            # Fall through with a summarized response
            return RCAResponse(rca=_exc_to_rca(e), patch=None, test=None, file=req_path, context=_as_list_context(None, tail), note=note_from_read)

    # --- Optional LLM RCA path (OpenAI/Gemini; supports multi-backend) ---
    if llm_generate_rca is not None:
        try:
            llm_out = llm_generate_rca(log_text or "", repo=event["repo"], path=req_path)
            if isinstance(llm_out, dict):
                return _mk_response(llm_out, fallback_file=req_path, note_from_read=note_from_read, tail=tail)
        except Exception as e:
            # Fall through with summarized response
            return RCAResponse(rca=_exc_to_rca(e), patch=None, test=None, file=req_path, context=_as_list_context(None, tail), note=note_from_read)

    # --- Safe stub: never fail the UI ---
    return RCAResponse(
        rca=f"Initial RCA based on provided logs:\n{tail or '(no log provided)'}",
        patch=None,
        test=None,
        exception=None,
        file=req_path,
        context=_as_list_context(None, tail),
        note=note_from_read,
    )