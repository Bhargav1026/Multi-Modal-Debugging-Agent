

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional, Tuple
import json

__all__ = [
    "read_text_file",
]


def _clamp_text(text: str, limit: int) -> Tuple[str, bool]:
    """Clamp text to a byte limit (UTF‑8), returning (text, truncated?)."""
    if limit <= 0:
        return text, False
    b = text.encode("utf-8", errors="replace")
    if len(b) <= limit:
        return text, False
    # Truncate on a UTF‑8 boundary
    cut = limit
    while cut > 0 and (b[cut] & 0xC0) == 0x80:  # continuation byte
        cut -= 1
    return b[:cut].decode("utf-8", errors="replace"), True


def _extract_notebook_text(raw: str, mode: str = "cells") -> Optional[str]:
    """Return a readable plaintext from a .ipynb string or None on failure.

    mode="cells"  -> join code/markdown cell sources
    mode="raw"    -> return None (caller will use original JSON string)
    """
    if mode not in {"cells", "raw"}:
        mode = "cells"
    try:
        nb = json.loads(raw)
    except Exception:
        return None
    cells = nb.get("cells")
    if not isinstance(cells, list):
        return None

    pieces = []
    for cell in cells:
        ctype = cell.get("cell_type")
        src = cell.get("source")
        if isinstance(src, list):
            src = "".join(src)
        if not isinstance(src, str):
            continue
        tag = "md" if ctype == "markdown" else "code"
        pieces.append(f"\n# [{tag}]\n{src}")
    return "\n".join(pieces).strip()


def read_text_file(path: str, max_bytes: int = 2_097_152, notebook_strategy: str = "cells") -> Dict[str, Optional[str]]:
    """Read a text file safely.

    - Expands `~` and resolves the path.
    - If `.ipynb` and `notebook_strategy=="cells"`, converts cells to plaintext.
    - Clamps to `max_bytes` (UTF‑8 safe truncation).

    Returns a dict: {"text", "note", "path", "size", "truncated"}
    where size is the original byte size as string, and note may contain
    messages like "Converted from .ipynb" or "Truncated large input…".
    """
    p = Path(path).expanduser().resolve()
    raw_bytes = p.read_bytes()
    size = len(raw_bytes)
    raw_text = raw_bytes.decode("utf-8", errors="replace")

    notes = []
    text = raw_text

    if str(p).lower().endswith(".ipynb") and notebook_strategy == "cells":
        nb_text = _extract_notebook_text(raw_text, mode="cells")
        if nb_text:
            text = nb_text
            notes.append("Converted from .ipynb")

    text, truncated = _clamp_text(text, max_bytes)
    if truncated:
        notes.append("Truncated large input for performance")

    return {
        "text": text,
        "note": "; ".join(notes) if notes else None,
        "path": str(p),
        "size": str(size),
        "truncated": "true" if truncated else "false",
    }