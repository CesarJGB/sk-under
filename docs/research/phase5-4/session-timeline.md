# Cronología de sesiones y marcas monotónicas

**No se mezclan sesiones.** La sesión autenticada de 5.1, la ejecución de 5.3
hasta el formulario y el arranque de laboratorio de 5.4 usan relojes y
artefactos distintos. Ninguna fila de 5.4 corresponde a un login, a una
descarga o a una restauración.

## S1 · Sesión autenticada histórica (5.1)

Se conservan horas UTC y eventos de UI/log, pero no las marcas monotónicas por
etapa. Esta sesión no se reutilizó en 5.4.

| Hora UTC | Etapa | Evidencia | Límite |
| --- | --- | --- | --- |
| 03:11:06 | Envío del formulario; `EmailOrPhoneLogin`, `OnLoginResultAction`, menú. | Acción del operador, log e interfaz. | Sin reloj monotónico conservado. |
| 03:13:41 | Panel de nube con respaldo y **Retrieve Progress**. | Interfaz. | No se identificó la solicitud. |
| 03:14:44 | Primer intento; `CreateFromPlayerPref` y `ArgumentNullException` en `GetExtraDescribe`. | Log del invitado (04:14:48.366 y .817). | Falta el argumento nulo y la revisión. |
| 03:23:01 | Segundo intento; diálogo de reemplazo local. | Interfaz. | Condición local no aislada. |
| 03:23:53–03:24:07 | Confirmación; `CloudSaveRunner` y `CoverPlayerPref`. | Acción, log y comparación visual. | No se demuestra una segunda descarga. |

[Registro original](../phase5-experimental/experimentos.md) ·
[Lectura de la vista previa](../phase5-3/preview-error.md)

## S2 · Ejecución de 5.3 hasta el formulario

Android 11, APK 8.8.0, ABI `armeabi-v7a`. Los tiempos entre paréntesis son
segundos de `/proc/uptime` del invitado desde su arranque; los eventos de
Unity salen de `logcat -v monotonic`. Los contadores RX/TX son acumulados de
`wlan0` del invitado. No hay identificadores de solicitud, destinos por
operación, estados HTTP ni tamaños de respuesta.

| ID | Tiempo (s) | Acción o evento | Sockets | RX / TX (bytes) | Estado |
| --- | --- | --- | ---: | --- | --- |
| C0 | 35,98–43,37 | Control previo sin PID del juego | 0 | 0 / 0 | Sin datos. |
| P1 | 43,37–45,00 | Lanzar actividad oficial; muestra posterior. | 0 | 19 004 / 10 184 | Arranque. |
| P1 | 57,86–60,41 | Proceso presente. | 6 | 74 477 / 28 195 | Carga. |
| P1 | 69,836 / 110,650 | `JNI_OnLoad` / `InitSDK`. | — | — | Carga. |
| P1 | 135,88–136,08 | Carga en curso. | 7 | 2 120 024 / 460 277 | Carga. |
| P1 | 154,399 | Buffer de crash, `SIGSEGV`; vuelta al lanzador. | — | — | Fallo. |
| C1 | 229,46–229,55 | Control antes del relanzamiento. | 0 | 38 827 957 / 1 174 721 | Sin juego. |
| P2 | 229,55–229,88 | Relanzar la misma actividad. | 0 | 38 827 957 / 1 174 721 | Arranque. |
| P2 | 238,233 / 256,782 | `JNI_OnLoad` / `InitSDK`. | — | — | Carga. |
| P2 | 313,33–313,67 | Carga al 100 %. | 5 | 39 057 099 / 1 332 335 | Menú. |
| P2 | 349,77–350,07 | Selector de acceso. | 5 | 39 079 168 / 1 352 343 | Menú. |
| P2 | 358,49–361,43 | Elegir ChillyRoom Account; `LoginOptions` a 361,440. | 5 | 39 079 168 / 1 352 343 | Formulario. |
| P2 | 386,96–388,17 | Formulario vacío visible. | 3 | 39 092 788 / 1 360 385 | Formulario. |
| — | — | Login aceptado, panel, recuperación, cancelación, confirmación. | — | — | **No ejecutado.** |

[Tabla original](../phase5-3/session-timeline.md). La ventana mide el
formulario, no una sesión. Entre las dos muestras junto al formulario hubo
13 620 bytes RX y 8 042 TX de la interfaz; ninguna corresponde a un envío del
formulario.

## S3 · Laboratorio de 5.4 sin autenticación

Se reinició `sk52-lab` para medir recursos. El reloj es el del host; el
intervalo de arranque se midió desde `docker start` hasta
`sys.boot_completed=1`. No se abrió el juego ni se interactuó con la cuenta.

| Tiempo relativo (s) | Evento | Evidencia |
| --- | ---: | --- |
| 0 | `docker start sk52-lab`. | Host. |
| 52–55 | `sys.boot_completed=1`. | `adb shell getprop`. |
| 82–85 | Primera muestra estabilizada: 215,5 % CPU, 2,69 GiB. | `docker stats`. |
| 92–95 | Segunda muestra: 215,9 % CPU, 2,99 GiB. | `docker stats`. |
| 102–105 | Tercera muestra: 209,7 % CPU, 3,30 GiB. | `docker stats`. |
| 105 | `docker stop sk52-lab`. | Host. |

[Diagnóstico](emulator-diagnostics.md) · [Consumo](resource-benchmark.md)

## Lo que falta en la cronología

1. Marcas monotónicas de `ABRIR_PANEL`, `FETCH_OK`, `RECUPERAR`, `CANCELAR` y
   `CONFIRMAR` en una misma sesión autenticada.
2. Un identificador de ensayo y el PID del proceso para asociar las marcas.
3. La revisión recibida y la consumida, si el diagnóstico autorizado las
   expone.
4. Una segunda apertura y una cancelación medida, para distinguir caché de
   nueva descarga.
5. Un caso sin respaldo remoto y otro con sesión expirada.

La [máquina de estados](fetch-state-machine.md) define las transiciones que
esas marcas deben separar. La [sesión autenticada](authenticated-session.md)
explica por qué no se ejecutaron en 5.4.
