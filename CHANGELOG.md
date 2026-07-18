# Changelog

Todos los cambios relevantes de CleepWheel se documentan en este archivo.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el proyecto usa versionado semántico.

## [0.2.0] - 2026-07-18

### Añadido

- WebUI local conectada al mismo historial SQLite.
- Comando `doctor` con estado, evidencia, confianza, advertencias y rutas alternativas.
- Listener persistente para el botón central del mouse.
- Ventana Tk precargada y controlada mediante `SIGUSR1`.
- Administración del watcher y del listener mediante `launchd`.
- Límite visible configurable con `CLEEPWHEEL_HISTORY_LIMIT`.
- Pruebas automatizadas y flujo de integración continua para Python.
- Metadatos de paquete mediante `pyproject.toml`.

### Cambiado

- Todas las interfaces ahora consumen una sola base SQLite mediante `ClipboardStore`.
- La capacidad visible predeterminada aumentó a 10,000 entradas.
- La arquitectura evita catálogos paralelos entre CLI, GUI, TUI y WebUI.
- Se mantiene `clipwill` como alias de compatibilidad; `cleepwheel` es el comando recomendado.

### Compatibilidad

- Conserva el historial creado por la versión `0.1.0`.
- Requiere Python 3.9 o superior.
- Plataforma principal: macOS.

## [0.1.0] - 2026-07-16

### Añadido

- Captura local de texto copiado.
- Persistencia inicial en SQLite.
- CLI y ventana gráfica iniciales.
- Integración básica con el portapapeles de macOS.

[0.2.0]: https://github.com/Blackmvmba88/Clipwheel/releases/tag/v0.2.0
[0.1.0]: https://github.com/Blackmvmba88/Clipwheel/releases/tag/v0.1.0
