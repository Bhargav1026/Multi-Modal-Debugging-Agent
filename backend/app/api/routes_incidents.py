from fastapi import APIRouter
from app.models.schemas import RCARequest, RCAResponse
from typing import Any, Dict, Optional
import hashlib
import traceback
from app.service.storage import read_text_file

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


def _derive_id(text: str) -> str:
    """Stable short id for ad‑hoc payloads (avoids KeyError: 'id')."""
    return hashlib.sha1((text or "").encode("utf-8")).hexdigest()[:10]


def _exc_to_rca(e: BaseException) -> str:
    """Create a readable RCA summary from an exception with location hints."""
    tb = traceback.extract_tb(e.__traceback__)
    last = tb[-1] if tb else None
    header = []
    header.append(f"• Exception: {e.__class__.__name__}: {getattr(e, 'args', [''])[0]!s}")
    if last:
        header.append(f"• Location: {last.filename}:{last.lineno}")
    lines = ["\n".join(header), "", "RCA:", "Initial RCA based on provided logs:"]
    # Include compact context around last frame
    if tb:
        lines.extend(
            [
                "– Suspected exception: "
                f"{e.__class__.__name__}: {getattr(e, 'args', [''])[0]!s}",
                f"– Likely location: {last.filename}:{last.lineno}" if last else "",
                "– Context around last error:",
                "    " + "".join(traceback.format_exception_only(e.__class__, e)).strip(),
                "    " + ("".join(traceback.format_list([last])) if last else "").rstrip(),
            ]
        )
    return "\n".join(l for l in lines if l)


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
    }

    # --- Preferred path: lightweight service handler ---
    if handle is not None:
        try:
            out = handle(event)  # expects dict
            if isinstance(out, dict):
                return RCAResponse(
                    rca=str(out.get("rca") or "Initial RCA produced"),
                    patch=out.get("patch"),
                    test=out.get("test"),
                    exception=out.get("exception"),
                    file=out.get("file"),
                    context=out.get("context"),
                    note=out.get("note") or note_from_read or None,
                )
            # If a non-dict is returned, still provide a usable response
            return RCAResponse(rca="RCA pipeline executed", patch=None, test=None)
        except KeyError as ke:
            # If downstream complained about 'id', ensure we have one and retry once.
            if "id" in str(ke) and not event.get("id"):
                event["id"] = _derive_id(event.get("log", "") or "")
                try:
                    out = handle(event)  # retry once
                    if isinstance(out, dict):
                        return RCAResponse(
                            rca=str(out.get("rca") or "Initial RCA produced (retry)"),
                            patch=out.get("patch"),
                            test=out.get("test"),
                            exception=out.get("exception"),
                            file=out.get("file"),
                            context=out.get("context"),
                            note=out.get("note") or note_from_read or None,
                        )
                except Exception as e2:
                    return RCAResponse(rca=_exc_to_rca(e2), patch=None, test=None)
            # Any other KeyError -> summarize rather than 500
            return RCAResponse(rca=_exc_to_rca(ke), patch=None, test=None)
        except Exception as e:
            # Summarize any failure coming from service handler
            return RCAResponse(rca=_exc_to_rca(e), patch=None, test=None)

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
                    return RCAResponse(
                        rca=result.get("rca") or "RCA pipeline executed",
                        patch=result.get("patch"),
                        test=result.get("test"),
                        exception=result.get("exception"),
                        file=result.get("file"),
                        context=result.get("context"),
                        note=result.get("_note") or result.get("note") or note_from_read or None,
                    )
            # If a non-dict is returned, still provide a usable response
            return RCAResponse(rca="RCA pipeline executed", patch=None, test=None)
        except Exception as e:
            # Fall through with a summarized response
            return RCAResponse(rca=_exc_to_rca(e), patch=None, test=None)

    # --- Safe stub: never fail the UI ---
    tail = event["log"][-800:] if event["log"] else ""
    return RCAResponse(
        rca=f"Initial RCA based on provided logs:\n{tail or '(no log provided)'}",
        patch=None,
        test=None,
        exception=None,
        file=None,
        context=None,
        note=note_from_read,
    )