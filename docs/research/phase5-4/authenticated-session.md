# Sesión autenticada: alcance y bloqueo

**Estado: BLOQUEADO.** En 5.4 no se completó una sesión autenticada nueva. No
se envió un formulario, no se abrió el panel de nube y no se observó ninguna
recuperación. El AVD disponible arranca, pero quedó en el formulario vacío; no
hay credenciales ni una sesión autorizada en el entorno. No se inventan
resultados de los pasos que no se ejecutaron.

## Qué se necesitaba

| Paso | Requisito | Estado en 5.4 |
| --- | --- | --- |
| 1. Iniciar sesión | Cuenta propia y acción interactiva del titular. | No ejecutado. |
| 2. Abrir el panel de nube | Sesión aceptada y menú del juego. | No ejecutado. |
| 3. Observar eventos de recuperación | Diagnóstico autorizado y reloj monotónico. | No ejecutado. |
| 4. Registrar marcas monotónicas | Host, invitado y log en la misma ejecución. | No ejecutado. |
| 5. Identificar un agregado válido | Respuesta asociada a la revisión y a la sesión. | No ejecutado. |
| 6. Cancelar sin restaurar | Diálogo de vista previa y cancelación. | No ejecutado. |
| 7. Repetir y confirmar | Segunda ventana equivalente; comparar comportamiento. | No ejecutado. |

## Evidencia disponible

- **5.1 (histórica):** una cuenta propia restauró la partida por la interfaz
  oficial. Hubo login, panel con respaldo, un primer fallo de vista previa y
  un segundo intento con confirmación y `CoverPlayerPref`. Esa sesión no se
  conservó y su AVD se descartó. [Experimento](../phase5-experimental/experimentos.md)
- **5.2:** se midieron arranque, sockets, SNI y tiempos hasta el formulario.
  No se autenticó. [Cronología](../phase5-trace/timeline.md)
- **5.3:** se reutilizó la instalación de 5.2, hubo un crash y un
  relanzamiento hasta el formulario vacío. No se envió login.
  [Cronología](../phase5-3/session-timeline.md)
- **5.4:** se reinició el mismo AVD y se midió su consumo en reposo. No se
  abrió el juego ni se intentó login. [Diagnóstico](emulator-diagnostics.md)

La sesión de 5.1 demuestra que la restauración oficial es posible para el
titular. No demuestra que 5.4 haya obtenido una sesión, ni que el backend
pueda adquirir o leer el agregado.

## Por qué no se completó

| Causa | Consecuencia |
| --- | --- |
| El AVD está en el formulario vacío. | No hay sesión de cuenta activa. |
| La sesión de 5.1 no se conservó. | No hay token ni caché reutilizable. |
| Enviar credenciales requiere al titular. | El agente no puede autenticarse por sí solo. |
| No hay una interfaz delegada autorizada. | El backend no puede sustituir al cliente. |
| El repositorio no contiene secretos. | No se pueden usar credenciales del propietario. |

No se solicitó la contraseña ni el token al usuario. No se leyeron ni
escribieron credenciales, tokens, cookies o contenido privado de la partida.
El AVD y sus imágenes son datos privados del laboratorio y no se publican.

## Protocolo previsto para desbloquear

El titular debe iniciar sesión manualmente en un AVD o dispositivo propio, con
el mismo método de acceso y la misma cuenta que creó el respaldo. Después:

1. Tomar una muestra de control antes de abrir el panel.
2. Marcar `ABRIR_PANEL`; observar si aparece `FetchData` y si hay tráfico.
3. Esperar sin interactuar durante una ventana equivalente.
4. Pulsar **Retrieve Progress**; detenerse antes de confirmar.
5. Registrar el reloj monotónico de inicio y fin de la consulta, el estado
   visible y, si el diagnóstico autorizado lo expone, la revisión recibida.
6. Cancelar el diálogo sin restaurar; reabrir el panel y comparar si se repite
   la descarga o se reutiliza el agregado.
7. Repetir con una segunda recuperación equivalente y confirmar solo sobre un
   estado local de prueba ya respaldado.

El [protocolo de 5.3](../phase5-3/session-timeline.md) y su
[sondeo](../phase5-3/session-sample.sh) describen las marcas y los comandos.
La [máquina de estados](fetch-state-machine.md) enumera las transiciones que
esa instrumentación debe distinguir.

## Qué se verificó en su lugar

Sin sesión remota se ejecutaron las comprobaciones locales que no dependen de
Android:

- 9/9 muestras reales de 8.6.0 se reconstruyeron byte a byte en Linux.
- La suite completa pasó con 178 pruebas (169 públicas + 9 privadas de 8.6.0).
- El importador procesó agregados sintéticos en JSON y gzip, con límites,
  hashes, truncado y marcadores RPC.
- El frontend compiló y las cuatro pruebas de navegador pasaron.

Estas pruebas demuestran procesamiento local, no adquisición remota. La
distinción se mantiene en el [informe final](README.md).
