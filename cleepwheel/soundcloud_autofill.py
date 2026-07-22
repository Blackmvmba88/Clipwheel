from __future__ import annotations

import json
import threading
import webbrowser
from dataclasses import asdict, dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


@dataclass(frozen=True)
class SoundCloudAutofillProfile:
    main_artist: str = "Iyary Gomez"
    songwriter: str = "Iyary Cancino Gomez"
    label: str = "BlackMamba RECORDS"
    explicit: bool = False
    wrote_song: bool = True
    has_isrc: bool = False
    confirm_rights: bool = True


def generate_autofill_script(profile: SoundCloudAutofillProfile) -> str:
    data = json.dumps(asdict(profile), ensure_ascii=False)
    return f"""(() => {{
  const DATA = {data};
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const visible = (el) => el && !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
  const norm = (s) => (s || "").replace(/\\s+/g, " ").trim();
  const text = (el) => norm(el?.innerText || el?.textContent || el?.value || "");
  const allVisible = (selector) => [...document.querySelectorAll(selector)].filter(visible);
  const buttons = (pattern) => allVisible("button, a, [role='button']").filter((el) => pattern.test(text(el)));
  const setValue = (el, value) => {{
    if (!el || el.disabled) return false;
    const setter = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(el), "value")?.set;
    setter ? setter.call(el, value) : (el.value = value);
    el.dispatchEvent(new Event("input", {{ bubbles: true }}));
    el.dispatchEvent(new Event("change", {{ bubbles: true }}));
    el.blur?.();
    return true;
  }};
  const clickText = (pattern) => {{
    const el = allVisible("button, [role='button'], label, div, span, input")
      .find((node) => pattern.test(text(node)));
    if (!el) return false;
    el.click();
    return true;
  }};
  const fieldByNearbyText = (pattern) => {{
    for (const label of allVisible("label, div, span, p").filter((el) => pattern.test(text(el)))) {{
      const id = label.getAttribute("for");
      if (id) {{
        const byId = document.getElementById(id);
        if (byId && visible(byId)) return byId;
      }}
      const block = label.closest("div, section, fieldset, form") || label.parentElement;
      const input = block?.querySelector?.("input:not([type='hidden']):not([type='checkbox']):not([type='radio']), textarea");
      if (input && visible(input)) return input;
    }}
    return null;
  }};
  const fillInputs = async () => {{
    const inputs = allVisible("input:not([type='hidden']):not([type='checkbox']):not([type='radio']), textarea")
      .filter((el) => !el.disabled && el.value !== "Automatically generated");
    const labelInput = fieldByNearbyText(/\\blabel\\b/i)
      || inputs.find((el) => /label/i.test(`${{el.name}} ${{el.placeholder}} ${{el.getAttribute("aria-label") || ""}}`));
    if (labelInput) setValue(labelInput, DATA.label);
    const namedInputs = inputs.filter((el) => ![DATA.label, "Main Artist", "Composer"].includes(el.value));
    const targets = namedInputs.filter((el) => !el.value || el.value === DATA.main_artist || el.value === DATA.songwriter);
    if (targets[0]) setValue(targets[0], DATA.main_artist);
    if (targets[1]) setValue(targets[1], DATA.songwriter);
    await sleep(250);
  }};
  const selectDefaults = async () => {{
    clickText(DATA.explicit ? /^explicit$/i : /not explicit/i);
    await sleep(100);
    if (DATA.wrote_song) clickText(/i wrote this song|represent the writer/i);
    await sleep(100);
    clickText(DATA.has_isrc ? /^yes$/i : /^no$/i);
    await sleep(100);
    if (DATA.confirm_rights) {{
      allVisible("label").forEach((label) => {{
        if (!/rights to monetize/i.test(text(label))) return;
        const input = label.querySelector("input") || document.getElementById(label.getAttribute("for"));
        if (input && !input.checked) label.click();
      }});
    }}
  }};
  const fillAndSubmitCurrentModal = async () => {{
    await fillInputs();
    await selectDefaults();
    await sleep(500);
    const submit = buttons(/^submit$/i)[0];
    if (!submit) throw new Error("No encontre el boton Submit en el modal actual.");
    submit.scrollIntoView({{ block: "center" }});
    await sleep(150);
    submit.click();
    await sleep(2200);
  }};
  (async () => {{
    let processed = 0;
    let idleScrolls = 0;
    if (buttons(/^submit$/i).length) {{
      await fillAndSubmitCurrentModal();
      processed++;
    }}
    while (idleScrolls < 6) {{
      const pending = buttons(/monetize this track/i)[0];
      if (!pending) {{
        window.scrollBy(0, Math.floor(window.innerHeight * 0.75));
        idleScrolls++;
        await sleep(900);
        continue;
      }}
      idleScrolls = 0;
      pending.scrollIntoView({{ block: "center" }});
      await sleep(350);
      pending.click();
      await sleep(1400);
      await fillAndSubmitCurrentModal();
      processed++;
    }}
    const message = `Listo: rellene y envie ${{processed}} tracks pendientes.`;
    console.log(message);
    alert(message);
  }})().catch((err) => {{
    console.error(err);
    alert(`Autofill detenido: ${{err.message}}`);
  }});
}})();"""


def _html_page(profile: SoundCloudAutofillProfile) -> str:
    defaults = json.dumps(asdict(profile), ensure_ascii=False)
    script = json.dumps(generate_autofill_script(profile), ensure_ascii=False)
    return f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>CleepWheel SoundCloud Autofill</title>
  <style>
    :root {{ color-scheme: dark; --bg:#0b1020; --panel:#11182b; --text:#eff4ff; --muted:#91a2c6; --accent:#ff7a1a; --line:rgba(255,255,255,.12); }}
    body {{ margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; background:radial-gradient(circle at top,#1d2545,var(--bg)); color:var(--text); }}
    main {{ max-width:980px; margin:0 auto; padding:28px 18px 44px; }}
    h1 {{ margin:0 0 8px; }}
    p {{ color:var(--muted); line-height:1.5; }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(240px,1fr)); gap:14px; }}
    label {{ display:block; font-size:13px; color:var(--muted); margin:0 0 6px; }}
    input, textarea {{ width:100%; box-sizing:border-box; border:1px solid var(--line); border-radius:12px; background:var(--panel); color:var(--text); padding:11px 12px; }}
    textarea {{ min-height:320px; font-family:ui-monospace,SFMono-Regular,Menlo,monospace; }}
    .card {{ background:rgba(17,24,43,.88); border:1px solid var(--line); border-radius:18px; padding:18px; margin-top:16px; }}
    .checks {{ display:flex; flex-wrap:wrap; gap:12px; margin-top:12px; }}
    .checks label {{ display:flex; align-items:center; gap:8px; margin:0; color:var(--text); }}
    .checks input {{ width:auto; }}
    button {{ border:0; border-radius:12px; padding:11px 14px; background:linear-gradient(135deg,var(--accent),#ffd05a); color:#140800; font-weight:800; cursor:pointer; }}
    .actions {{ display:flex; gap:10px; flex-wrap:wrap; margin:14px 0; }}
    .steps {{ margin:0; padding-left:20px; color:var(--muted); }}
    .steps li {{ margin:8px 0; }}
  </style>
</head>
<body>
  <main>
    <h1>SoundCloud Autofill</h1>
    <p>Configura tus datos una vez, copia el script y pegalo en la consola de Chrome dentro del portal de monetizacion de SoundCloud.</p>
    <section class="card">
      <div class="grid">
        <div><label>Artista principal</label><input id="main_artist" /></div>
        <div><label>Compositor / songwriter</label><input id="songwriter" /></div>
        <div><label>Label</label><input id="label" /></div>
      </div>
      <div class="checks">
        <label><input id="explicit" type="checkbox" /> Explicit</label>
        <label><input id="wrote_song" type="checkbox" /> I wrote this song</label>
        <label><input id="has_isrc" type="checkbox" /> Tengo ISRC</label>
        <label><input id="confirm_rights" type="checkbox" /> Confirmo derechos para monetizar</label>
      </div>
      <div class="actions">
        <button id="generate">Generar script</button>
        <button id="copy">Copiar script</button>
      </div>
    </section>
    <section class="card">
      <ol class="steps">
        <li>Abre SoundCloud for Artists en la pagina de monetizacion.</li>
        <li>Abre DevTools con Option + Command + J.</li>
        <li>Pega el script y presiona Enter.</li>
      </ol>
    </section>
    <section class="card">
      <label>Script generado</label>
      <textarea id="script"></textarea>
    </section>
  </main>
  <script>
    const defaults = {defaults};
    const initialScript = {script};
    const ids = ["main_artist", "songwriter", "label", "explicit", "wrote_song", "has_isrc", "confirm_rights"];
    const profile = () => Object.fromEntries(ids.map((id) => {{
      const el = document.getElementById(id);
      return [id, el.type === "checkbox" ? el.checked : el.value];
    }}));
    for (const [key, value] of Object.entries(defaults)) {{
      const el = document.getElementById(key);
      if (el.type === "checkbox") el.checked = value;
      else el.value = value;
    }}
    document.getElementById("script").value = initialScript;
    document.getElementById("generate").addEventListener("click", async () => {{
      const res = await fetch("/script", {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify(profile()),
      }});
      document.getElementById("script").value = await res.text();
    }});
    document.getElementById("copy").addEventListener("click", async () => {{
      await navigator.clipboard.writeText(document.getElementById("script").value);
      alert("Script copiado.");
    }});
  </script>
</body>
</html>"""


class SoundCloudAutofillHandler(BaseHTTPRequestHandler):
    profile = SoundCloudAutofillProfile()

    def log_message(self, _format: str, *_args) -> None:  # noqa: A003
        return

    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/":
            self._send_text("not found", status=404)
            return
        self._send_text(_html_page(self.profile), content_type="text/html; charset=utf-8")

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/script":
            self._send_text("not found", status=404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
        profile = SoundCloudAutofillProfile(
            main_artist=str(payload.get("main_artist", self.profile.main_artist)),
            songwriter=str(payload.get("songwriter", self.profile.songwriter)),
            label=str(payload.get("label", self.profile.label)),
            explicit=bool(payload.get("explicit", self.profile.explicit)),
            wrote_song=bool(payload.get("wrote_song", self.profile.wrote_song)),
            has_isrc=bool(payload.get("has_isrc", self.profile.has_isrc)),
            confirm_rights=bool(payload.get("confirm_rights", self.profile.confirm_rights)),
        )
        self._send_text(generate_autofill_script(profile), content_type="text/javascript; charset=utf-8")

    def _send_text(self, body: str, status: int = 200, content_type: str = "text/plain; charset=utf-8") -> None:
        raw = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def serve_soundcloud_autofill(
    host: str = "127.0.0.1",
    port: int = 8776,
    *,
    open_browser: bool = True,
    profile: SoundCloudAutofillProfile | None = None,
) -> int:
    handler = type("CleepWheelSoundCloudAutofillHandler", (SoundCloudAutofillHandler,), {})
    handler.profile = profile or SoundCloudAutofillProfile()
    server = ThreadingHTTPServer((host, port), handler)
    url = f"http://{host}:{port}"
    if open_browser:
        threading.Thread(target=lambda: webbrowser.open(url), daemon=True).start()
    try:
        print(f"SoundCloud autofill UI running at {url}")
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0

