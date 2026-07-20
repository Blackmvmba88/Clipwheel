# CleepWheel

<p align="center">
  <strong>Historial local de portapapeles para macOS, rápido, privado y respaldado por SQLite.</strong>
</p>

<p align="center">
  <a href="https://github.com/Blackmvmba88/Clipwheel/actions"><img alt="CI" src="https://github.com/Blackmvmba88/Clipwheel/actions/workflows/ci.yml/badge.svg"></a>
  <img alt="Python 3.9+" src="https://img.shields.io/badge/python-3.9%2B-blue">
  <img alt="macOS" src="https://img.shields.io/badge/platform-macOS-black">
  <img alt="SQLite" src="https://img.shields.io/badge/storage-SQLite-07405e">
  <img alt="Version" src="https://img.shields.io/badge/version-0.2.0-7c3aed">
  <a href="LICENSE"><img alt="MIT License" src="https://img.shields.io/badge/license-MIT-green"></a>
</p>

CleepWheel captura texto copiado en macOS y lo concentra en una sola base SQLite. El mismo historial alimenta la CLI, la ventana Tk, la WebUI, el diagnóstico y el listener del botón central.

> **Versión actual:** `0.2.0`  
> Consolida todas las interfaces sobre una única fuente de verdad y conserva compatibilidad con el historial creado por `0.1.0`.

## Características

- Historial local y privado respaldado por SQLite WAL.
- Captura persistente del portapapeles mediante watcher.
- CLI para listar, buscar, exportar y diagnosticar.
- Ventana gráfica para copiar, editar y borrar entradas.
- WebUI local con filtrado instantáneo.
- Capa local de inteligencia para clasificar copias como canciones/letras, metacomandos, links, código, contactos, credenciales, comandos, notas o datos estructurados.
- Listener global del botón central con ventana precargada.
- Integración con `launchd` para procesos persistentes.
- Límite visible configurable sin eliminar datos almacenados.
- Herramienta `doctor` con evidencia, confianza y rutas de recuperación.

## Instalación

```bash
git clone https://github.com/Blackmvmba88/Clipwheel.git
cd Clipwheel
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .
```

### Requisitos

- macOS
- Python `3.9+`
- `pbcopy` y `pbpaste`
- Tk para la interfaz gráfica

## Inicio rápido

```bash
cleepwheel doctor
cleepwheel watch
cleepwheel mouse
```

Para abrir la interfaz web:

```bash
cleepwheel webui
```

Para consultar el historial:

```bash
cleepwheel list
cleepwheel search "texto"
cleepwheel classify --category song
cleepwheel classify "Clasifica esta letra por mood"
cleepwheel export --format json --output history.json
```

También puedes ejecutar el paquete como módulo:

```bash
python3 -m cleepwheel doctor
python3 -m cleepwheel list
python3 -m cleepwheel mouse
python3 -m cleepwheel webui
```

## Comandos

| Comando | Función |
|---|---|
| `cleepwheel doctor` | Comprueba SQLite, clipboard, watcher y listener global. |
| `cleepwheel list` | Lista las entradas recientes. |
| `cleepwheel search "texto"` | Busca contenido guardado. |
| `cleepwheel classify` | Muestra categorías, clasifica texto o lista entradas por categoría. |
| `cleepwheel export` | Exporta el historial. |
| `cleepwheel watch` | Captura texto copiado. |
| `cleepwheel mouse` | Abre la ventana gráfica. |
| `cleepwheel webui` | Inicia la interfaz web local. |
| `cleepwheel mouse-launchd` | Administra el listener persistente del botón central. |
| `cleepwheel launchd` | Administra el watcher persistente. |

`clipwill` se conserva como alias de compatibilidad para instalaciones y scripts anteriores. Para uso nuevo, se recomienda `cleepwheel`.

## Ventana gráfica

La ventana permite:

- navegar el historial
- copiar una entrada de vuelta al portapapeles
- editar texto guardado
- borrar entradas
- mover la división entre paneles
- activar o apagar efectos visuales
- mantener un máximo estricto de dos ventanas simultáneas

Atajos:

| Atajo | Acción |
|---|---|
| `Ctrl+N` | Neón |
| `Ctrl+T` | Transparencia |
| `Ctrl+B` | Borde |
| `Ctrl+D` | Brillo del divisor |

## Clic de la rueda

Instala una vez el listener global del botón central:

```bash
cleepwheel mouse-launchd install
cleepwheel mouse-launchd start
cleepwheel mouse-launchd status
```

El botón central funciona como interruptor para mostrar u ocultar una ventana precargada. El listener envía `SIGUSR1` al proceso residente, evitando arrancar Python y reconstruir la interfaz en cada clic.

macOS puede solicitar permisos para Python en:

**Configuración del Sistema → Privacidad y seguridad → Accesibilidad**  
**Configuración del Sistema → Privacidad y seguridad → Monitoreo de entrada**

Para reiniciar el listener después de actualizar:

```bash
cleepwheel mouse-launchd stop
cleepwheel mouse-launchd start
```

## WebUI

```bash
cleepwheel webui
```

Opciones útiles:

```bash
cleepwheel webui --host 127.0.0.1 --port 8765
cleepwheel webui --no-browser
```

La WebUI permite filtrar, inspeccionar, copiar, editar y borrar entradas usando los mismos datos que la CLI y la ventana local.

## Inteligencia local

CleepWheel clasifica cada entrada al guardarla o editarla. La clasificación es local, determinística y no llama a servicios externos.

Categorías iniciales:

| Categoría | Uso |
|---|---|
| `song` | Letras de canciones, links musicales, archivos de audio y metadatos como BPM, coro, verso o hook. |
| `metacommand` | Instrucciones/prompts como clasificar, resumir, analizar, traducir, generar o corregir. |
| `credential` | Tokens, passwords, API keys y secretos. |
| `link` | URLs generales. |
| `code` | Fragmentos de código. |
| `command` | Comandos de terminal. |
| `contact` | Emails o teléfonos. |
| `structured-data` | JSON válido. |
| `task-note` | TODOs, notas y listas de tareas. |

Ejemplos:

```bash
cleepwheel classify
cleepwheel classify --entry 12
cleepwheel classify --category song
cleepwheel classify --category metacommand
```

## Diagnóstico

```bash
cleepwheel doctor
```

El diagnóstico comprueba:

- apertura y escritura de SQLite
- cantidad de entradas y hashes distintos
- disponibilidad de `pbcopy` y `pbpaste`
- estado del watcher
- estado del listener del mouse

La salida incluye:

- `confidence`: confianza global del diagnóstico
- `evidence`: evidencia concreta comprobada
- `warning`: condición degradada
- `fallback_reason`: razón para usar una ruta alternativa
- `status`: resultado final

Recuperación rápida:

```bash
cleepwheel launchd status
cleepwheel mouse-launchd status
cleepwheel launchd stop && cleepwheel launchd start
cleepwheel mouse-launchd stop && cleepwheel mouse-launchd start
```

## Arquitectura

```text
pbpaste → watcher → SQLite WAL → ClipboardStore
                                ├─ CLI / doctor
                                ├─ Tk window / WebUI / TUI
                                └─ warm window ← SIGUSR1 ← middle-click listener
```

Toda interfaz consume:

```text
~/.local/share/cleepwheel/clipboard.sqlite3
```

No existen catálogos paralelos ni historiales separados por interfaz.

## Capacidad del historial

SQLite conserva entradas sin un límite fijo. La CLI, TUI, ventana y WebUI cargan hasta `10,000` entradas por defecto.

```text
storage_capacity: unlimited
history_view_limit: 10000
```

Puedes cambiar el límite visible sin alterar la base:

```bash
export CLEEPWHEEL_HISTORY_LIMIT=20000
```

## Verificación

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile cleepwheel/*.py
cleepwheel doctor
cleepwheel mouse-launchd status
```

## Datos y privacidad

CleepWheel funciona localmente. El historial permanece en la máquina del usuario y no requiere servicios externos para operar.

## Estado del proyecto

- Versión estable actual: `0.2.0`
- Plataforma principal: macOS
- Licencia: MIT
- Historial compatible con `0.1.0`

Consulta [CHANGELOG.md](CHANGELOG.md) para ver los cambios por versión.

## Licencia

Distribuido bajo la licencia MIT. Consulta [LICENSE](LICENSE).