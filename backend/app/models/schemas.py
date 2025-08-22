

from typing import Optional, List
from pydantic import BaseModel, Field

__all__ = [
    "RCARequest",
    "RCAResponse",
]


class RCARequest(BaseModel):
    """Input to the RCA pipeline.
    - repo: path or URL to the repository under analysis (workspace root or git URL)
    - path: optional file path to read and analyze on the server
    - log: optional logs/stack trace text (used if `path` is not provided)
    - screenshot_b64: optional UI screenshot (base64-encoded PNG/JPEG)
    - id: optional client-supplied identifier for the incident (server will derive one if absent)
    """

    repo: Optional[str] = None
    path: Optional[str] = None
    log: Optional[str] = None
    screenshot_b64: Optional[str] = None
    id: Optional[str] = None


class RCAResponse(BaseModel):
    """Structured result from the RCA pipeline.
    - rca: human-readable root cause analysis text
    - patch: unified diff string (optional)
    - test: minimal failing test or reproduction snippet (optional)
    - exception: parsed exception name/type (optional)
    - file: likely file:line location (optional)
    - context: a few nearby log lines (optional)
    - note: optional note (e.g., transformation/truncation info)
    """

    rca: str = Field(..., min_length=1)
    patch: Optional[str] = None
    test: Optional[str] = None

    exception: Optional[str] = None
    file: Optional[str] = None
    context: Optional[List[str]] = None
    note: Optional[str] = None