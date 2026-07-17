from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
from pathlib import Path

from .domain import ClipboardEntry


class ClipboardStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _hash(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS clipboard_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
                """
            )

    def add(self, content: str) -> bool:
        content = content.strip()
        if not content:
            return False
        h = self._hash(content)
        with self._connect() as conn:
            latest = conn.execute(
                "SELECT content_hash FROM clipboard_entries ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if latest and latest["content_hash"] == h:
                return False
            conn.execute(
                "INSERT INTO clipboard_entries(content, content_hash) VALUES (?, ?)",
                (content, h),
            )
            return True

    def list(self, limit: int = 50) -> list[ClipboardEntry]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, content, content_hash, created_at FROM clipboard_entries ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [ClipboardEntry(r["id"], r["content"], r["created_at"], r["content_hash"]) for r in rows]

    def latest(self) -> ClipboardEntry | None:
        rows = self.list(1)
        return rows[0] if rows else None

    def get(self, entry_id: int) -> ClipboardEntry | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, content, content_hash, created_at FROM clipboard_entries WHERE id = ?",
                (entry_id,),
            ).fetchone()
        if not row:
            return None
        return ClipboardEntry(row["id"], row["content"], row["created_at"], row["content_hash"])

    def search(self, query: str, limit: int = 50) -> list[ClipboardEntry]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, content, content_hash, created_at FROM clipboard_entries WHERE content LIKE ? ORDER BY id DESC LIMIT ?",
                (f"%{query}%", limit),
            ).fetchall()
        return [ClipboardEntry(r["id"], r["content"], r["created_at"], r["content_hash"]) for r in rows]

    def update(self, entry_id: int, content: str) -> bool:
        content = content.strip()
        if not content:
            return False
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE clipboard_entries SET content = ?, content_hash = ? WHERE id = ?",
                (content, self._hash(content), entry_id),
            )
            return cur.rowcount > 0

    def delete(self, entry_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM clipboard_entries WHERE id = ?", (entry_id,))
            return cur.rowcount > 0

    def clear(self) -> int:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM clipboard_entries")
            return cur.rowcount

    def count(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS count FROM clipboard_entries").fetchone()
            return int(row["count"])

    def doctor(self) -> list[str]:
        warnings: list[str] = []
        if self.count() == 0:
            warnings.append("clipboard history is empty")
        return warnings

    def export_json(self, path: Path) -> int:
        rows = self.list(10**9)
        payload = [
            {"id": e.id, "content": e.content, "content_hash": e.content_hash, "created_at": e.created_at}
            for e in rows
        ]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return len(payload)

    def export_csv(self, path: Path) -> int:
        rows = self.list(10**9)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["id", "content", "content_hash", "created_at"])
            writer.writeheader()
            for e in rows:
                writer.writerow({"id": e.id, "content": e.content, "content_hash": e.content_hash, "created_at": e.created_at})
        return len(rows)
