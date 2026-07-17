# Clipwheel

Historial local de texto copiado para macOS, escrito en Python y sin servicios en la nube.

[![CI](https://github.com/Blackmvmba88/Clipwheel/actions/workflows/ci.yml/badge.svg)](https://github.com/Blackmvmba88/Clipwheel/actions/workflows/ci.yml)

## Qué hace

- Guarda texto plano copiado en SQLite.
- Permite listar, buscar, borrar y exportar el historial.
- Abre una ventana local para ver, copiar, editar y borrar entradas.
- Tiene un watcher para capturar el clipboard.

## Requisitos

- macOS (la integración del portapapeles usa `pbcopy` y `pbpaste`).
- Python 3.9 o posterior.
- Tk, incluido normalmente con Python para macOS, para la ventana gráfica.

No hay dependencias externas de ejecución.

## Instalación

```bash
git clone https://github.com/Blackmvmba88/Clipwheel.git
cd Clipwheel
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .
```

## Uso

```bash
python3 -m cleepwheel list
python3 -m cleepwheel search "texto"
python3 -m cleepwheel clear
python3 -m cleepwheel export --format json --output history.json
python3 -m cleepwheel doctor
python3 -m cleepwheel watch
python3 -m cleepwheel mouse
```

Después de instalar el paquete también puedes sustituir `python3 -m cleepwheel` por `cleepwheel`.

## Notas

- `mouse` abre la ventana del historial.
- `watch` captura texto copiado y lo guarda en SQLite.
- El historial se guarda de forma predeterminada en `~/.local/share/cleepwheel/clipboard.sqlite3`.
- Dentro de la ventana puedes encender o apagar:
  - `Neon`
  - `Transparency`
  - `Border`
  - `Divider Glow`
- También puedes usar atajos:
  - `Ctrl+N` neon
  - `Ctrl+T` transparencia
  - `Ctrl+B` borde
  - `Ctrl+D` brillo del divisor

## Desarrollo

```bash
python3 -m compileall -q cleepwheel tests
python3 -m unittest discover -s tests -v
```

GitHub Actions ejecuta estas validaciones en Python 3.9, 3.11 y 3.13 para cada pull request dirigida a `main`.

## Licencia

MIT. Consulta [LICENSE](LICENSE).
