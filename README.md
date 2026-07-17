# CleepWheel

Historial local de texto copiado para macOS.

## Qué hace

- Guarda texto plano copiado en SQLite.
- Permite listar, buscar, borrar y exportar el historial.
- Abre una ventana local para ver, copiar, editar y borrar entradas.
- Tiene un watcher para capturar el clipboard.

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

## Notas

- `mouse` abre la ventana del historial.
- `watch` captura texto copiado y lo guarda en SQLite.
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
