

"""
Service Handlers (optional)
--------------------------
This module keeps the service boundary stable. It normalizes any inbound
payload so downstream code never crashes on missing keys (e.g. KeyError: 'id')
and so all events share the same shape.

If you decide to build a richer service layer later, extend `handle()` and
route your API calls through here.
"""
from __future__ import annotations

from typing import Any, Dict
import uuid
from datetime import datetime, timezone


def _now_iso() -> str:
  """UTC timestamp in ISO-8601 (seconds precision)."""
  return datetime.now(timezone.utc).isoformat(timespec="seconds")


def tail(text: str, lines: int = 60) -> str:
  """Return the last `lines` lines of text for quick context."""
  try:
    return "\n".join(str(text).splitlines()[-int(lines):])
  except Exception:
    return str(text)


def normalize_event(event: Dict[str, Any] | None) -> Dict[str, Any]:
  """
  Create a consistent event shape with fields:
    - id: stable id string
    - text: the log/content body (always a str)
    - source: optional file/path the content came from
    - created_at: UTC ISO timestamp
    - tail: last N lines (helps fast RCA)
  Also supports common aliases from the extension/UI:
    * text/body/content => text
    * path/file/source  => source
  """
  e: Dict[str, Any] = dict(event or {})

  # id is guaranteed
  e.setdefault("id", str(uuid.uuid4()))

  # normalize content
  raw = e.get("text") or e.get("body") or e.get("content") or ""
  if isinstance(raw, bytes):
    try:
      raw = raw.decode("utf-8", "replace")
    except Exception:
      raw = str(raw)
  e["text"] = str(raw)

  # normalize source/path
  src = e.get("path") or e.get("file") or e.get("source")
  if src:
    e["source"] = src

  # timestamps & quick context
  e.setdefault("created_at", _now_iso())
  e["tail"] = tail(e.get("text", ""), 80)
  return e


def handle(event: Dict[str, Any]) -> Dict[str, Any]:
  """
  Pass-through that normalizes the incoming event.
  Downstream code can rely on keys: id, text, (optional) source, created_at, tail.
  """
  return normalize_event(event)