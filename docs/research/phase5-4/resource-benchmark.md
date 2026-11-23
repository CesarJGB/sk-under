# Consumo de recursos

**Procesar una copia en Linux cuesta decenas de MiB; mantener el laboratorio
Android cuesta gigabytes y dos núcleos.** En este host, el AVD en reposo usó
2,7–3,3 GiB de RAM, ~210 % de CPU y 52–55 s de arranque. El importador Python
usó 20 MiB en el arranque del módulo y 36–46 MiB para copias de hasta 4 MiB.
La comparación mide procesamiento, no adquisición: sin sesión autorizada, el
emulador sigue siendo necesario para obtener el respaldo.

## Metodología

| Elemento | Valor |
| --- | --- |
| Fecha | 23 de noviembre de 2026 UTC. |
| Host | AMD EPYC 9534, 6 vCPU, 11 GiB de RAM, kernel 6.8.0-142, Linux x86-64. |
| Python | 3.12.3; `uv 0.12.23`; entorno `--locked`. |
| Emulador | `sk-phase51-android-lab:local`; AVD Android 11 API 30, x86_64, 2 vCPU, 3 GiB, `swiftshader`, sin ventana y sin snapshot. |
| Aislamiento | Cada escenario Python se ejecuta en un proceso nuevo; `ru_maxrss` no acumula picos de otros escenarios. |
| Repeticiones | Tres corridas completas del benchmark; se reporta la mediana y el rango. |
| Reloj | `time.perf_counter`; CPU de `resource.getrusage`; RAM de `ru_maxrss`. |
| Emulador | `docker stats --no-stream` y `ps` del proceso QEMU; tres muestras separadas por 10 s tras 30 s de estabilización. |

El script es [benchmark.py](benchmark.py). No imprime contenido de partidas,
identificadores ni huellas privadas. Los bytes procesados de las muestras
reales se reportan solo como total agregado.

## Emulador Android

| Métrica | Resultado | Nota |
| --- | ---: | --- |
| Arranque hasta `sys.boot_completed=1` | 52 s y 55 s | Dos arranques; sin snapshot. |
| CPU del contenedor | 209,7–215,9 % | Límite de 2,5 núcleos; ~2,1 núcleos. |
| CPU de QEMU en el host | 191–195 % | `ps`; tres muestras. |
| RAM del contenedor | 2,69–3,30 GiB | Creció durante la ventana; límite 4,395 GiB. |
| RSS de QEMU | 2,86–3,49 GB | Creció durante la ventana. |
| Memoria del invitado | 2,92 GiB totales; 2,31 GiB disponibles | `/proc/meminfo`. |
| SDK | 15 GB | Emulador 853 MB; platform-tools 22 MB; system-images 14 GB. |
| Datos del AVD | 2,8 GB | `userdata-qemu.img.qcow2`. |
| Imagen del contenedor | 564 MB virtuales; 200 MB de capa escribible | `docker ps --size`. |
| Juego ejecutándose | No medido | No se lanzó para no iniciar una sesión no autorizada. |

El AVD declara 2 núcleos y 3072 MB (`config.ini`). El contenedor tiene un
límite de 4,5 GB de RAM y 2,5 núcleos. La medición es una **cota inferior**:
el proceso del juego añade CPU, RAM y red.

## Arranque de Python

Mediana de tres corridas; el rango entre paréntesis.

| Escenario | Pared | Importación | RSS máximo |
| --- | ---: | ---: | ---: |
| Intérprete vacío | 55 ms (49–62) | — | 14,0 MiB |
| `import app.cloud.importer` | 85 ms (74–85) | 27 ms (26–28) | 19,6 MiB (19,6–19,8) |
| `import app.main` (FastAPI) | 472 ms (441–547) | 345 ms (308–389) | 44,7 MiB (44,7–44,8) |

`import app.cloud.importer` incluye el decodificador, el validador y el
transporte, pero no FastAPI. El arranque del servicio completo es ~0,47 s y
~45 MiB en este host.

## Procesamiento local

| Escenario | Entrada | Iteraciones | Tiempo medio | RSS máximo | Rango del tiempo |
| --- | ---: | ---: | ---: | ---: | ---: |
| Importador actual, JSON | 283 B | 200 | 0,097 ms | 19,6 MiB | 0,087–0,131 ms |
| Prototipo, JSON | 283 B | 200 | 0,072 ms | 19,7 MiB | 0,066–0,081 ms |
| Prototipo, gzip | 184 B comprimidos | 200 | 0,081 ms | 19,9 MiB | 0,068–0,108 ms |
| Prototipo, JSON grande | 4 000 141 B | 1 | 25,4 ms | 35,1 MiB | 19,0–26,2 ms |
| Prototipo, gzip grande | 4 020 B comprimidos (4 MB inflados) | 1 | 27,2 ms | 36,4 MiB | 27,0–30,2 ms |
| Nueve archivos 8.6.0 (solo lectura) | 735 244 B | 1 | 59,9 ms | 45,5 MiB | 49,1–78,7 ms |

La fila de 8.6.0 mide lectura, descifrado DES-CBC, parseo JSON y
reconocimiento de las nueve familias. No incluye escritura ni restauración.
El importador actual y el prototipo comparten el mismo decodificador; la
diferencia pequeña corresponde a la envoltura de transporte y al orden de
llamadas, no a un códec distinto.

## Instalación y dependencias

| Componente | Tamaño | Dependencias |
| --- | ---: | --- |
| `backend/.venv` | 43 MB | FastAPI, Pydantic Settings, Uvicorn, PyCryptodome; `pytest`/`httpx2` en dev. |
| `backend/app` | 336 KB | El flujo de agregados usa solo la biblioteca estándar (`hashlib`, `zlib`, `json`). |
| Imagen Docker del backend | 211 MB | `python:3.12-slim` + venv + app. |
| `frontend/dist` | 492 KB | Build estático. |
| `frontend/node_modules` | 174 MB | Solo build; no se despliega. |
| SDK + AVD Android | ~17,8 GB | Emulador, system image y datos del AVD. |

El prototipo de agregados no añadió dependencias. `pycryptodome` sigue siendo
necesario para el adaptador de archivos locales `.data`, no para un agregado
JSON/gzip.

## Comparación y ahorro

| Dimensión | Emulador en reposo | Procesamiento Linux | Lectura |
| --- | ---: | ---: | --- |
| RAM | 2,7–3,3 GiB | 20–46 MiB | ~60–160× menos. |
| CPU | ~2,1 núcleos | Trabajo puntual de milisegundos | No es una comparación directa; el emulador consume en reposo. |
| Arranque | 52–55 s | 0,085 s del módulo; 0,47 s del servicio | El arranque de Android no es equivalente al de Python. |
| Disco | ~17,8 GB SDK+AVD | 43 MB venv; 211 MB imagen | ~40–80× menos. |
| Dependencia | KVM, imagen, AVD, gráficos | Python 3.12 | El AVD requiere mantenimiento y vinculación. |

**Conclusión limitada:** eliminar Android del **procesamiento** evita el coste
del emulador por operación. No elimina la dependencia para **adquirir** el
respaldo. La cifra de ahorro no debe presentarse como independencia completa.

## Limitaciones

- Un solo host virtualizado y compartido; los tiempos absolutos no son
  portables.
- El emulador se midió en reposo, sin el proceso del juego.
- No hay muestra real de 8.8.0 ni sesión autenticada; el procesamiento de un
  agregado real puede diferir.
- `ru_maxrss` es el pico del proceso, no la memoria estable.
- `docker stats` calcula CPU respecto del límite del contenedor; los valores
  >100 % indican varios núcleos.
- No se midieron energía, IOPS ni latencia de red.
- No se midió el frontend en el navegador; solo su build.

## Reproducción

```bash
cd backend
SK_PHASE4_SAMPLES_DIR="/ruta/privada" \
SK_PHASE4_CIPHER_ENV_FILE="$HOME/.config/sk-under/phase3/cipher.env" \
uv run --locked python ../docs/research/phase5-4/benchmark.py
```

Para el emulador:

```bash
docker start sk52-lab
# Esperar sys.boot_completed=1, luego:
docker stats --no-stream sk52-lab
docker stop sk52-lab
```

El APK, el AVD y las muestras privadas no se publican. [Diagnóstico del
emulador](emulator-diagnostics.md) · [Prototipo Linux](linux-client-prototype.md)
