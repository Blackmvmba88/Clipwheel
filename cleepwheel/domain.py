from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ClipboardEntry:
    id: int
    content: str
    created_at: str
    content_hash: str
    pinned: bool = False


@dataclass(frozen=True)
class ActionResult:
    ok: bool
    evidence: str
    warnings: tuple[str, ...] = ()
    fallback_reason: str = ""
