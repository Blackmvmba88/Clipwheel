from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Dict, List, Optional

from .domain import ClipboardEntry
from .settings import load_settings


SCHEMA_VERSION = 1


class ClipboardStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=3000")
        return conn

    @staticmethod
    def _hash(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _init_db(self) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
            )
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
            columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(clipboard_entries)").fetchall()
            }
            if "content_hash" not in columns:
                conn.execute("ALTER TABLE clipboard_entries ADD COLUMN content_hash TEXT")
                for row in conn.execute("SELECT id, content FROM clipboard_entries").fetchall():
                    conn.execute(
                        "UPDATE clipboard_entries SET content_hash = ? WHERE id = ?",
                        (self._hash(row["content"]), row["id"]),
                    )
            conn.execute(
                "INSERT OR IGNORE INTO metadata(key, value) VALUES ('schema_version', ?)",
                (str(SCHEMA_VERSION),),
            )
            conn.execute(
                "INSERT OR IGNORE INTO metadata(key, value) VALUES ('max_content_chars', ?)",
                (str(load_settings(self.db_path).max_content_chars),),
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_clipboard_entries_created_at "
                "ON clipboard_entries(created_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_clipboard_entries_hash "
                "ON clipboard_entries(content_hash)"
            )

    def _content_limit(self, content: str) -> str:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT value FROM metadata WHERE key = 'max_content_chars'"
            ).fetchone()
        return content[: int(row["value"])] if row else content

    def add(self, content: str) -> bool:
        content = content.strip()
        if not content:
            return False
        content = self._content_limit(content)
        h = self._hash(content)
        with closing(self._connect()) as conn, conn:
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

    def list(self, limit: int = 50) -> List[ClipboardEntry]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT id, content, content_hash, created_at FROM clipboard_entries ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [ClipboardEntry(r["id"], r["content"], r["created_at"], r["content_hash"]) for r in rows]

    def list_all(self) -> List[ClipboardEntry]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT id, content, content_hash, created_at "
                "FROM clipboard_entries ORDER BY id DESC"
            ).fetchall()
        return [ClipboardEntry(r["id"], r["content"], r["created_at"], r["content_hash"]) for r in rows]

    def latest(self) -> Optional[ClipboardEntry]:
        rows = self.list(1)
        return rows[0] if rows else None

    def get(self, entry_id: int) -> Optional[ClipboardEntry]:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT id, content, content_hash, created_at FROM clipboard_entries WHERE id = ?",
                (entry_id,),
            ).fetchone()
        if not row:
            return None
        return ClipboardEntry(row["id"], row["content"], row["created_at"], row["content_hash"])

    def search(self, query: str, limit: int = 50) -> List[ClipboardEntry]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT id, content, content_hash, created_at FROM clipboard_entries WHERE content LIKE ? ORDER BY id DESC LIMIT ?",
                (f"%{query}%", limit),
            ).fetchall()
        return [ClipboardEntry(r["id"], r["content"], r["created_at"], r["content_hash"]) for r in rows]

    def update(self, entry_id: int, content: str) -> bool:
        content = content.strip()
        if not content:
            return False
        content = self._content_limit(content)
        with closing(self._connect()) as conn, conn:
            cur = conn.execute(
                "UPDATE clipboard_entries SET content = ?, content_hash = ? WHERE id = ?",
                (content, self._hash(content), entry_id),
            )
            return cur.rowcount > 0

    def delete(self, entry_id: int) -> bool:
        with closing(self._connect()) as conn, conn:
            cur = conn.execute("DELETE FROM clipboard_entries WHERE id = ?", (entry_id,))
            return cur.rowcount > 0

    def clear(self) -> int:
        with closing(self._connect()) as conn, conn:
            cur = conn.execute("DELETE FROM clipboard_entries")
            return cur.rowcount

    def count(self) -> int:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT COUNT(*) AS count FROM clipboard_entries").fetchone()
            return int(row["count"])

    def doctor(self) -> List[str]:
        warnings = []
        with closing(self._connect()) as conn, conn:
            version = conn.execute(
                "SELECT value FROM metadata WHERE key = 'schema_version'"
            ).fetchone()
            if not version:
                warnings.append("missing schema version marker")
            elif int(version["value"]) != SCHEMA_VERSION:
                warnings.append(
                    f"schema version is {version['value']}, expected {SCHEMA_VERSION}"
                )
            if self.count() == 0:
                warnings.append("clipboard history is empty")
            try:
                marker = "__cleepwheel_doctor__"
                conn.execute(
                    "INSERT INTO clipboard_entries(content, content_hash) VALUES (?, ?)",
                    (marker, self._hash(marker)),
                )
                conn.execute("DELETE FROM clipboard_entries WHERE content = ?", (marker,))
            except sqlite3.Error as exc:
                warnings.append(f"database write test failed: {exc}")
        return warnings

    def stats(self) -> Dict[str, int]:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT COUNT(*) entries, COUNT(DISTINCT content_hash) distinct_hashes "
                "FROM clipboard_entries"
            ).fetchone()
        return {"entries": int(row["entries"]), "distinct_hashes": int(row["distinct_hashes"])}

    def export_json(self, path: Path, limit: Optional[int] = None) -> int:
        rows = self.list_all() if limit is None else self.list(limit)
        payload = [
            {"id": e.id, "content": e.content, "content_hash": e.content_hash, "created_at": e.created_at}
            for e in rows
        ]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return len(payload)

    def export_csv(self, path: Path, limit: Optional[int] = None) -> int:
        rows = self.list_all() if limit is None else self.list(limit)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["id", "content", "content_hash", "created_at"])
            writer.writeheader()
            for e in rows:
                writer.writerow({"id": e.id, "content": e.content, "content_hash": e.content_hash, "created_at": e.created_at})
        return len(rows)
