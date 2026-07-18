from __future__ import annotations

import json
import threading
import webbrowser
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .clipboard import write_clipboard_text
from .storage import ClipboardStore
from .settings import load_settings


def _html_page() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>CleepWheel WebUI</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #0b1020;
      --panel: #11182b;
      --panel2: #151f35;
      --text: #eff4ff;
      --muted: #8ea1ca;
      --accent: #5ad7ff;
      --accent2: #8c6cff;
      --danger: #ff6b86;
      --line: rgba(90, 215, 255, 0.25);
    }
    body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: radial-gradient(circle at top, #121a33, var(--bg)); color: var(--text); }
    header { padding: 18px 22px 10px; border-bottom: 1px solid var(--line); background: rgba(10, 15, 31, 0.72); backdrop-filter: blur(14px); position: sticky; top: 0; z-index: 5; }
    h1 { margin: 0; font-size: 20px; letter-spacing: 0.4px; }
    .sub { color: var(--muted); font-size: 13px; margin-top: 4px; }
    .toolbar { display: flex; gap: 10px; margin-top: 14px; flex-wrap: wrap; }
    input, button, textarea { border-radius: 12px; border: 1px solid rgba(255,255,255,0.08); background: var(--panel); color: var(--text); }
    input, textarea { padding: 10px 12px; }
    button { padding: 10px 14px; cursor: pointer; }
    button:hover { border-color: var(--accent); }
    main { display: grid; grid-template-columns: minmax(260px, 420px) minmax(320px, 1fr); gap: 14px; padding: 14px; }
    .card { background: rgba(17, 24, 43, 0.88); border: 1px solid rgba(255,255,255,0.06); border-radius: 18px; overflow: hidden; box-shadow: 0 30px 60px rgba(0,0,0,0.28); }
    .card h2 { margin: 0; padding: 14px 16px; font-size: 15px; border-bottom: 1px solid rgba(255,255,255,0.06); }
    #entries { list-style: none; margin: 0; padding: 0; max-height: calc(100vh - 220px); overflow: auto; }
    .entry { padding: 12px 14px; border-bottom: 1px solid rgba(255,255,255,0.06); cursor: pointer; transition: background 120ms ease; }
    .entry:hover, .entry.selected { background: rgba(90,215,255,0.09); }
    .meta { display: flex; justify-content: space-between; gap: 12px; font-size: 12px; color: var(--muted); margin-bottom: 6px; }
    .content { white-space: pre-wrap; word-break: break-word; line-height: 1.45; }
    #detail { padding: 16px; }
    .detail-top { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 14px; }
    .detail-meta { color: var(--muted); font-size: 13px; margin-bottom: 10px; }
    textarea { width: 100%; min-height: 300px; resize: vertical; box-sizing: border-box; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
    .actions { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 12px; }
    .primary { background: linear-gradient(135deg, var(--accent), var(--accent2)); color: #04111f; border: none; font-weight: 700; }
    .danger { background: rgba(255, 107, 134, 0.14); color: #ffd3da; }
    .status { margin-left: auto; color: var(--muted); font-size: 13px; padding: 10px 0 0; }
    .stats { display: flex; gap: 18px; color: var(--muted); font-size: 13px; }
    @media (max-width: 980px) { main { grid-template-columns: 1fr; } #entries { max-height: 300px; } }
  </style>
</head>
<body>
  <header>
    <h1>CleepWheel WebUI</h1>
    <div class="sub">Historial local de texto copiado. Copiar, editar y borrar desde el navegador.</div>
    <div class="toolbar">
      <input id="query" placeholder="Search clipboard..." size="26" />
      <button class="primary" id="refresh">Refresh</button>
      <button id="copySelected">Copy selected</button>
      <button id="pinSelected">Pin / unpin</button>
      <button id="editSelected">Edit selected</button>
      <button class="danger" id="deleteSelected">Delete selected</button>
      <div class="status" id="status">Ready</div>
    </div>
    <div class="stats" style="margin-top:10px">
      <div id="count">0 entries</div>
      <div>Tip: click an item to inspect it</div>
    </div>
  </header>
  <main>
    <section class="card">
      <h2>History</h2>
      <ul id="entries"></ul>
    </section>
    <section class="card">
      <h2>Detail</h2>
      <div id="detail">
        <div class="detail-meta" id="detailMeta">No item selected</div>
        <textarea id="editor" placeholder="Select an entry to view or edit it..."></textarea>
        <div class="actions">
          <button class="primary" id="saveEdit">Save edit</button>
          <button id="copyDetail">Copy text</button>
        </div>
      </div>
    </section>
  </main>
  <script>
    let selectedId = null;
    let selectedEntry = null;

    const els = {
      query: document.getElementById('query'),
      entries: document.getElementById('entries'),
      detailMeta: document.getElementById('detailMeta'),
      editor: document.getElementById('editor'),
      status: document.getElementById('status'),
      count: document.getElementById('count'),
    };

    function setStatus(text) { els.status.textContent = text; }
    function escapeHtml(text) {
      return text.replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
    }

    async function api(path, options = {}) {
      const res = await fetch(path, {
        headers: { 'Content-Type': 'application/json' },
        ...options,
      });
      if (!res.ok) throw new Error(await res.text());
      const type = res.headers.get('content-type') || '';
      return type.includes('application/json') ? res.json() : res.text();
    }

    function render(entries) {
      els.entries.innerHTML = '';
      els.count.textContent = `${entries.length} entries`;
      for (const entry of entries) {
        const li = document.createElement('li');
        li.className = 'entry' + (selectedId === entry.id ? ' selected' : '');
        li.innerHTML = `
          <div class="meta">
            <span>${entry.pinned ? '★ ' : ''}#${entry.id}</span>
            <span>${escapeHtml(entry.created_at)}</span>
          </div>
          <div class="content">${escapeHtml(entry.content.slice(0, 220))}${entry.content.length > 220 ? '...' : ''}</div>
        `;
        li.addEventListener('click', () => selectEntry(entry));
        els.entries.appendChild(li);
      }
    }

    function selectEntry(entry) {
      selectedId = entry.id;
      selectedEntry = entry;
      els.editor.value = entry.content;
      els.detailMeta.textContent = `ID ${entry.id} · ${entry.created_at} · ${entry.content_hash.slice(0, 16)}…`;
      setStatus(`Selected #${entry.id}`);
      load();
    }

    async function load() {
      const query = els.query.value.trim();
      const data = await api(`/api/entries?query=${encodeURIComponent(query)}`);
      render(data.entries);
      if (!selectedEntry && data.entries.length) {
        selectEntry(data.entries[0]);
      } else if (selectedId) {
        const updated = data.entries.find(e => e.id === selectedId);
        if (updated) {
          selectedEntry = updated;
          els.editor.value = updated.content;
          els.detailMeta.textContent = `ID ${updated.id} · ${updated.created_at} · ${updated.content_hash.slice(0, 16)}…`;
        }
      }
    }

    async function copySelected() {
      if (!selectedEntry) return;
      await navigator.clipboard.writeText(selectedEntry.content);
      await api(`/api/entries/${selectedEntry.id}/copy`, { method: 'POST' });
      setStatus(`Copied #${selectedEntry.id}`);
    }

    async function saveEdit() {
      if (!selectedEntry) return;
      const content = els.editor.value;
      await api(`/api/entries/${selectedEntry.id}`, {
        method: 'POST',
        body: JSON.stringify({ content }),
      });
      setStatus(`Saved edit #${selectedEntry.id}`);
      selectedEntry.content = content;
      await load();
    }

    async function togglePin() {
      if (!selectedEntry) return;
      await api(`/api/entries/${selectedEntry.id}/pin`, {
        method: 'POST',
        body: JSON.stringify({ pinned: !selectedEntry.pinned }),
      });
      setStatus(`${selectedEntry.pinned ? 'Unpinned' : 'Pinned'} #${selectedEntry.id}`);
      await load();
    }

    async function deleteSelected() {
      if (!selectedEntry) return;
      if (!confirm(`Delete entry #${selectedEntry.id}?`)) return;
      await api(`/api/entries/${selectedEntry.id}`, { method: 'DELETE' });
      setStatus(`Deleted #${selectedEntry.id}`);
      selectedEntry = null;
      selectedId = null;
      els.editor.value = '';
      els.detailMeta.textContent = 'No item selected';
      await load();
    }

    document.getElementById('refresh').addEventListener('click', load);
    document.getElementById('copySelected').addEventListener('click', copySelected);
    document.getElementById('editSelected').addEventListener('click', saveEdit);
    document.getElementById('pinSelected').addEventListener('click', togglePin);
    document.getElementById('deleteSelected').addEventListener('click', deleteSelected);
    document.getElementById('copyDetail').addEventListener('click', copySelected);
    document.getElementById('saveEdit').addEventListener('click', saveEdit);
    els.query.addEventListener('input', () => load());
    load().catch(err => setStatus(err.message));
  </script>
</body>
</html>"""


class WebUIHandler(BaseHTTPRequestHandler):
    store: ClipboardStore
    history_view_limit = 10000

    @staticmethod
    def _entry_id_from_path(path: str) -> tuple[int | None, bool]:
        parsed = urlparse(path)
        segments = [segment for segment in parsed.path.split("/") if segment]
        if len(segments) >= 3 and segments[0] == "api" and segments[1] == "entries" and segments[2].isdigit():
            is_copy = len(segments) == 4 and segments[3] == "copy"
            return int(segments[2]), is_copy
        return None, False

    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/":
            body = _html_page().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/api/entries":
            query = parse_qs(parsed.query).get("query", [""])[0]
            entries = (
                self.store.search(query, self.history_view_limit)
                if query
                else self.store.list(self.history_view_limit)
            )
            self._send_json(
                {
                    "entries": [asdict(entry) for entry in entries],
                    "stats": self.store.stats(),
                }
            )
            return
        if parsed.path == "/api/stats":
            self._send_json(self.store.stats())
            return
        self._send_json({"error": "not found"}, 404)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        segments = [segment for segment in parsed.path.split("/") if segment]
        if len(segments) == 4 and segments[:2] == ["api", "entries"] and segments[2].isdigit() and segments[3] == "pin":
            entry_id = int(segments[2])
            payload = self._read_json()
            if not self.store.set_pinned(entry_id, bool(payload.get("pinned", True))):
                self._send_json({"error": "entry not found"}, 404)
                return
            entry = self.store.get(entry_id)
            self._send_json({"ok": True, "entry": asdict(entry) if entry else None})
            return
        entry_id, is_copy = self._entry_id_from_path(parsed.path)
        if entry_id is not None:
            if is_copy:
                entry = self.store.get(entry_id)
                if not entry:
                    self._send_json({"error": "entry not found"}, 404)
                    return
                write_clipboard_text(entry.content)
                self._send_json({"ok": True, "id": entry_id})
                return
            payload = self._read_json()
            content = str(payload.get("content", ""))
            if not self.store.update(entry_id, content):
                self._send_json({"error": "update failed"}, 400)
                return
            updated = self.store.get(entry_id)
            self._send_json({"ok": True, "entry": asdict(updated) if updated else None})
            return
        self._send_json({"error": "not found"}, 404)

    def do_DELETE(self) -> None:  # noqa: N802
        entry_id, is_copy = self._entry_id_from_path(self.path)
        if entry_id is not None and not is_copy:
            if not self.store.delete(entry_id):
                self._send_json({"error": "delete failed"}, 404)
                return
            self._send_json({"ok": True, "id": entry_id})
            return
        self._send_json({"error": "not found"}, 404)


def serve_webui(db_path: Path, host: str = "127.0.0.1", port: int = 8765, open_browser: bool = True) -> int:
    handler = type("CleepWheelWebUIHandler", (WebUIHandler,), {})
    handler.store = ClipboardStore(db_path)
    handler.history_view_limit = load_settings(db_path).history_view_limit
    server = ThreadingHTTPServer((host, port), handler)

    if open_browser:
        threading.Thread(target=lambda: webbrowser.open(f"http://{host}:{port}"), daemon=True).start()

    try:
        print(f"WebUI running at http://{host}:{port}")
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0
