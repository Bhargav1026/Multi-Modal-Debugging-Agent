from typing import Any, Dict, Optional, List, Sequence, Union
import traceback

from app.models.schemas import RCAResponse

def _exc_to_rca(e: BaseException) -> str:
    """Create a readable RCA summary from an exception with location hints."""
    tb = traceback.extract_tb(e.__traceback__)
    last = tb[-1] if tb else None

    # Some exceptions (e.g., pydantic validation) can have empty args; fall back safely.
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

def _mk_response(out: Dict[str, Any], tail: str) -> RCAResponse:
    return RCAResponse(
        rca=out.get("rca", ""),
        patch=out.get("patch"),
        test=out.get("test"),
        exception=out.get("exception"),
        file=out.get("file"),
        context=_as_list_context(out.get("context"), tail),
        note=out.get("note"),
    )

# inside run_rca function's except Exception as e: block
# ...
# return RCAResponse(
#     rca=_exc_to_rca(e),
#     patch=None,
#     test=None,
#     exception=None,
#     file=None,
#     context=_as_list_context(None, tail),
#     note=None,
# )