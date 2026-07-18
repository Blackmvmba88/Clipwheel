# CleepWheel

Historial local de texto copiado para macOS.

Versión actual: `0.2.0`. Esta versión consolida todas las interfaces sobre una
sola base SQLite y conserva compatibilidad con el historial creado por `0.1.0`.

## Resumen

- Guarda texto copiado en SQLite.
- Abre una ventana local para ver, copiar, editar y borrar entradas.
- Abre una WebUI local para ver, copiar, editar y borrar entradas desde el navegador.
- Incluye watcher para capturar clipboard.
- Incluye CLI, ventana gráfica y apoyo para `launchd`.
- Permite fijar entradas importantes para mantenerlas arriba del historial.
- Mantiene una ventana precargada para respuesta inmediata al clic central.

## Instalación

```bash
git clone https://github.com/Blackmvmba88/Clipwheel.git
cd Clipwheel
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .
```

Si ya activaste el entorno, el comando correcto es:

```bash
python -m pip install .
```

## Uso rápido

```bash
cleepwheel doctor
cleepwheel list
cleepwheel search "texto"
cleepwheel pin 42
cleepwheel unpin 42
cleepwheel export --format json --output history.json
cleepwheel watch
cleepwheel mouse
cleepwheel mouse-launchd status
cleepwheel webui
```

Si prefieres el módulo:

```bash
python3 -m cleepwheel doctor
python3 -m cleepwheel list
python3 -m cleepwheel mouse
python3 -m cleepwheel webui
```

## Ventana

La ventana gráfica te deja:

- ver el historial
- copiar una entrada de vuelta al clipboard
- editar texto guardado
- borrar entradas
- mover la división entre paneles con el mouse
- activar o apagar efectos visuales
- mantener un máximo estricto de dos ventanas simultáneas

Las acciones aparecen arriba del historial como viñetas compactas; el contenido
queda libre debajo para navegar el historial y los detalles.

Atajos:

- `Ctrl+N` neón
- `Ctrl+T` transparencia
- `Ctrl+B` borde
- `Ctrl+D` brillo del divisor

## Watcher

`watch` captura texto del clipboard y lo guarda en la base local.

```bash
cleepwheel watch
```

La base por defecto vive en:

```text
~/.local/share/cleepwheel/clipboard.sqlite3
```

## Clic de la rueda

Instala una vez el listener global del botón central:

```bash
clipwill mouse-launchd install
clipwill mouse-launchd start
clipwill mouse-launchd status
```

Al presionar la rueda se abre una sola ventana gráfica con el mismo historial.
Al presionarla otra vez, la ventana se oculta. El botón central funciona como
interruptor mostrar/ocultar.
El listener mantiene Tk precargado: el clic solo envía `SIGUSR1` al proceso
oculto, evitando arrancar Python y reconstruir la interfaz cada vez. También
aplica antirrebote para evitar aperturas dobles. macOS puede pedir
permiso para Python en **Configuración del Sistema → Privacidad y seguridad →
Accesibilidad** y **Monitoreo de entrada**.

Para reiniciar el listener después de una actualización:

```bash
clipwill mouse-launchd stop
clipwill mouse-launchd start
```

## Doctor

El diagnóstico comprueba la base SQLite, lectura y escritura, cantidad de
entradas, hashes distintos, `pbcopy`, `pbpaste`, watcher y listener del mouse:

```bash
clipwill doctor
```

La salida incluye:

- `confidence`: confianza global del diagnóstico
- `evidence`: evidencia concreta comprobada
- `warning`: condición degradada que requiere atención
- `fallback_reason`: razón para usar una ruta alternativa
- `status`: resultado final

Recuperación rápida:

```bash
clipwill launchd status
clipwill mouse-launchd status
clipwill launchd stop && clipwill launchd start
clipwill mouse-launchd stop && clipwill mouse-launchd start
```

## Despliegue local

1. Instala el paquete con `python -m pip install .`.
2. Ejecuta `cleepwheel doctor` para validar la base.
3. Ejecuta `cleepwheel watch` para capturar el clipboard.
4. Ejecuta `cleepwheel mouse` para abrir la ventana, o `cleepwheel webui` para abrir la interfaz web local.

## WebUI

La WebUI usa los mismos datos SQLite de la app.

```bash
cleepwheel webui
```

Opciones útiles:

```bash
cleepwheel webui --host 127.0.0.1 --port 8765
cleepwheel webui --no-browser
```

En la WebUI puedes:

- filtrar el historial mientras escribes
- inspeccionar el contenido completo de una entrada
- copiar de vuelta al clipboard
- editar o borrar entradas

## Verificación

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile cleepwheel/*.py
clipwill doctor
clipwill mouse-launchd status
```

## Arquitectura

```text
pbpaste → watcher → SQLite WAL → ClipboardStore
                                ├─ CLI / doctor
                                ├─ Tk window / WebUI / TUI
                                └─ warm window ← SIGUSR1 ← middle-click listener
```

Toda interfaz usa `~/.local/share/cleepwheel/clipboard.sqlite3`; no existen
catálogos paralelos.

## Capacidad del historial

SQLite conserva entradas sin un límite fijo. La ventana, WebUI, TUI y CLI
cargan hasta 10,000 entradas por defecto, en lugar de 200 o 500:

```bash
clipwill doctor
```

```text
storage_capacity: unlimited
history_view_limit: 10000
```

Puedes cambiar el límite visible sin alterar ni borrar la base:

```bash
export CLEEPWHEEL_HISTORY_LIMIT=20000
```

## Notas

- `pbcopy` y `pbpaste` son parte del flujo en macOS.
- `Tk` debe estar disponible para la ventana gráfica.
- `launchd` sigue disponible para el watcher persistente.
- `mouse-launchd` administra el listener persistente del botón central.
