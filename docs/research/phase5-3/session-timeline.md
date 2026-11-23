# Cronología del ensayo del cliente oficial

**El AVD disponible llegó al formulario de cuenta vacío el 23 de noviembre de 2026 UTC.** El dispositivo autenticado de 5.1 se descartó al terminar aquel ensayo. En 5.3 se reutilizó la instalación de 5.2, sin reinstalar ni cambiar de cuenta. Se observó el primer fallo y se relanzó la actividad. El acceso normal del titular es el punto donde se detuvo esta ejecución.

## Mediciones de 5.3

Android 11, APK oficial 8.8.0, armeabi-v7a. Se verificaron versión y ABI con Package Manager. Los intervalos entre paréntesis se tomaron de `/proc/uptime` del invitado, en segundos desde el arranque. Las marcas de Unity y del fallo proceden de `logcat -v monotonic` en el mismo arranque. Cada sondeo acota varios comandos sucesivos. Los contadores son acumulados de **wlan0 del invitado**, en el orden RX/TX. Los sockets son TCP establecidos al 443 del UID. Los identificadores P1/P2 se asignaron localmente a procesos sucesivos. Se carece de identificadores de solicitud, destinos por operación, estados HTTP y tamaños de respuesta. La columna de archivo se refiere al resultado de stat sobre el candidato externo game.data. ND significa sin dato observable.

| ID local | Tiempo (s) | Acción y método observado | Sockets | RX / TX (bytes) | Archivo / estado |
| --- | --- | --- | ---: | --- | --- |
| C0 | 35.98–43.37 | Control previo, sin PID del juego | 0 | 0 / 0 | ND |
| P1 | 43.37–45.00 | Lanzar actividad oficial. Muestra posterior 45.00–46.65 | 0 | 19004 / 10184 | ND |
| P1 | 57.86–60.41 | Proceso presente | 6 | 74477 / 28195 | ND |
| P1 | 69.836 y 110.650 | JNI_OnLoad e InitSDK en el log | ND | ND | ND |
| P1 | 135.88–136.08 | Carga en curso | 7 | 2120024 / 460277 | ND |
| P1 | 154.399 | Buffer de crash, SIGSEGV. Después se observó el lanzador | ND | ND | ND |
| C1 | 229.46–229.55 | Control antes del relanzamiento, sin PID del juego | 0 | 38827957 / 1174721 | ND |
| P2 | 229.55–229.88 | Relanzar la misma actividad. Muestra posterior 229.88–230.28 | 0 | 38827957 / 1174721 | ND |
| P2 | 238.233 y 256.782 | JNI_OnLoad e InitSDK | ND | ND | ND |
| P2 | 313.33–313.67 | Carga al 100 % en la observación de pantalla posterior | 5 | 39057099 / 1332335 | ND |
| P2 | 349.77–350.07 | Muestra junto a la observación del selector de acceso | 5 | 39079168 / 1352343 | ND |
| P2 | 358.49–361.43 | Seleccionar ChillyRoom Account. LoginOptions a 361.440. Muestra a 361.54–361.71 | 5 | 39079168 / 1352343 | ND |
| P2 | 386.96–388.17 | Formulario vacío visible. Muestra posterior 388.17–388.51 | 3 | 39092788 / 1360385 | ND |
| — | ND | Login aceptado, reposo autenticado, panel, estado remoto, recuperar, diálogo, cancelar y repetir/confirmar | ND | ND | Etapas sin ejecutar en 5.3 |

Entre las dos muestras junto al formulario hubo 13 620 bytes RX y 8 042 TX de la interfaz. Ninguna de ellas corresponde a un envío del formulario. Los SNI api-gateway.soulknight.chillyroom.com y dc.chillyroom.com se observaron en **5.2**, también antes de autenticar. [Medición anterior](../phase5-trace/timeline.md)

## Evidencia autenticada histórica

Un solo ensayo de 5.1 documenta el envío del formulario (03:11:06 UTC), panel con respaldo (03:13:41), recuperación y fallo de vista previa (03:14:44), diálogo del segundo intento (03:23:01), confirmación (03:23:53) y aplicación desde las 03:24:07 con CoverPlayerPref. La sesión registró FetchData sin hora ni identificador de revisión. Carece de marcas monotónicas conservadas por etapa y de cancelación medida. Mezclar esos eventos con los contadores anteriores produciría una correlación entre sesiones distintas. [Experimento autenticado original](../phase5-experimental/experimentos.md)

## Repetición por etapas

En una sesión oficial del titular, tomar una muestra antes y después de cada acción. El identificador de ensayo y el PID permiten asociar marcas a una ejecución. Las columnas del sondeo son etiqueta, uptime inicial y final, PID, sockets, RX, TX y tamaño/mtime del candidato externo. `events` imprime solo tiempo y nombres permitidos del proceso. Registrar por separado el estado visible, el destino si lo expone un diagnóstico autorizado y cualquier estado de respuesta que ese diagnóstico entregue. Los buffers tienen retención limitada. Tomar los eventos en cada ventana y deduplicar las marcas repetidas. [Sondeo utilizado](session-sample.sh)

```sh
adb shell sh -s -- control < docs/research/phase5-3/session-sample.sh
adb shell sh -s -- events < docs/research/phase5-3/session-sample.sh
```

1. Marcar launch, completar login en la UI y marcar login. Mantener el menú sin interacción durante 30 segundos como control. Marcar idle.
2. Marcar panel antes y después de abrirlo. Registrar summary cuando se vea el estado remoto. Esperar otra ventana igual y observar si ya aparecieron el método calificado y el parser.
3. Separar retrieve, dialog y cancel. En un segundo intento equivalente, detenerse de nuevo en dialog. Confirmar únicamente sobre un estado local de prueba ya respaldado cuya sustitución sea segura. Marcar confirm y applied.
4. Comparar la revisión del documento en la terminación de la lectura con la consumida por el runner si el diagnóstico oficial expone una referencia correlacionable. Una transferencia distinta requiere una segunda operación de adquisición identificada. El mismo digest puede resultar de descargar los mismos bytes dos veces. Coincidencias de tiempo, sockets o resumen visual por sí solos dejan la pregunta pendiente.

**Hipótesis pendiente.** El panel podría precargar una revisión y la confirmación consumir el estado retenido. En el ABI del AVD, ShowView tiene una rama hacia FetchData(false) con el indicador de fetch a cero. LoadGame contempla un objeto nuevo si falta el agregado. El ensayo medido no distingue las dos. [Comparación de métodos](fetch-comparison.md)
