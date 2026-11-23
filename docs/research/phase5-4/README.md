# Fase 5.4 · Correlación autenticada, transporte RPC y reducción de la dependencia del emulador

**Linux ya procesa una copia de respaldo sin Android; la adquisición remota
sigue bloqueada.** Esta fase no obtuvo una sesión autenticada nueva ni una
muestra real de 8.8.0. Sí construyó una máquina de estados documentada, separó
las capas del transporte, implementó un cliente Linux con transporte remoto
deshabilitado y midió el coste del laboratorio frente al procesamiento local.
La dependencia del emulador **no se declara eliminada**.

## Matriz de resultados

| Objetivo | Estado | Evidencia |
| --- | --- | --- |
| Secuencia de recuperación | **Parcial** | Máquina de estados con evidencia estática y observada; faltan cancelación, reapertura y confirmación medidas. [fetch-state-machine.md](fetch-state-machine.md) |
| Sesión autenticada | **Bloqueado** | AVD en formulario vacío; sin credenciales ni sesión conservada; 0 de 7 pasos ejecutados. [authenticated-session.md](authenticated-session.md) |
| Transporte RPC | **Parcial** | Discriminador de 4 bytes y capas separadas; códec interior y respuesta real desconocidos. [rpc-transport-analysis.md](rpc-transport-analysis.md) · [rpc-format-specification.md](rpc-format-specification.md) |
| Referencia 8.8.0 | **Bloqueado** | Solo APK identificado; sin agregado ni `.data` de 8.8.0. Fixture sintético, no real. [real-880-save-validation.md](real-880-save-validation.md) |
| Prototipo Linux | **Confirmado** (alcance local) | Transporte inyectable, verificación, detección, decodificación, secciones y 15 pruebas nuevas. [linux-client-prototype.md](linux-client-prototype.md) |
| Vista previa | **Parcial** | `preview_issues` distingue nulo/ausente; la excepción oficial no se reprodujo. [preview-validation.md](preview-validation.md) |
| Consumo de recursos | **Confirmado** (medición limitada) | Emulador 2,7–3,3 GiB y ~210 % CPU; Linux 20–46 MiB; 3 corridas. [resource-benchmark.md](resource-benchmark.md) |
| Compatibilidad 8.6.0 | **Confirmado** | 9/9 reconstruidos byte a byte; 178 pruebas con las muestras privadas. |
| Compatibilidad 8.8.0 | **Pendiente** | Sin muestra autorizada; no se declara soporte. |

## Respuestas expresas

### 1. ¿Qué operaciones ya podemos realizar sin emulador?

Recibir una copia local, verificar tamaño y SHA-256, detectar JSON/gzip,
clasificar el sobre RPC, reconstruir el agregado, extraer secciones, resumir su
presencia, inspeccionar los nueve formatos locales de 8.6.0, exportar una copia
intacta y ejecutar toda la suite. También validar la estructura de una copia
antes de interpretarla. El [prototipo](linux-client-prototype.md) y el
[mapa de dependencias](transport-dependency-map.md) detallan cada operación.

### 2. ¿Qué operaciones siguen dependiendo del cliente oficial?

Iniciar sesión, consultar metadatos remotos, descargar la revisión, aplicar la
restauración en el juego y obtener una copia de 8.8.0. El backend no puede
sustituir la autenticación ni la restauración. La descompresión del bloque RPC
tampoco está resuelta, pero eso es una limitación de formato, no una operación
del proveedor.

### 3. ¿Se demostró una transferencia real desde la nube?

**No en 5.4.** La sesión histórica de 5.1 muestra que el titular restauró su
partida por la UI, pero no conservó bytes, revisión ni una transferencia
identificada. En 5.4 no se envió login y no se abrió el panel.

### 4. ¿Se consiguió una referencia auténtica de 8.8.0?

**No.** Se identificó el APK oficial por SHA-256 y se comprobó que no contiene
un archivo de partida. No había un agregado, un `.data` ni una exportación de
la cuenta. El fixture `cloud-save-880-sintetico.json` es sintético y así se
declara.

### 5. ¿Qué partes del RPC podemos interpretar localmente?

El discriminador de cuatro bytes: `00 00 00 80` (comprimido, cuerpo desde el
offset 4), `FF FF FF FF` (marca nula), valores distintos (passthrough) y
entradas de menos de cuatro bytes. No interpretamos el códec interior, el
endpoint, las cabeceras, el DTO HTTP completo ni la semántica de la marca nula.
[Especificación](rpc-format-specification.md).

### 6. ¿Qué información todavía desconocemos?

El formato exacto de la respuesta y sus claves; el algoritmo de
`ZipHelper.Decompress`; qué transporte usó la cuenta; el esquema de 8.8.0 y las
migraciones de `FixData`; la política de la caché `LoadedGameData`; el
comportamiento al cancelar, cerrar, reabrir, confirmar y ante una cuenta sin
respaldo; el argumento nulo de `GetExtraDescribe`; la duración y revocación de
la sesión.

### 7. ¿Existe una interfaz remota autorizada que podamos integrar?

**No se localizó ninguna.** La documentación pública describe la restauración
en el cliente y el soporte asistido, no una API delegada de lectura. El
transporte remoto del prototipo está deshabilitado
(`DisabledRemoteTransport`). Si el proveedor publica una interfaz, el conector
solo necesita implementar `fetch_latest(limit)`.

### 8. ¿Cuánto consumo podemos evitar eliminando Android?

Para **procesar** una copia: el AVD en reposo consumió 2,7–3,3 GiB de RAM,
~210 % de CPU, 52–55 s de arranque y ~17,8 GB de SDK+AVD. El módulo Python usó
20 MiB y 36–46 MiB para copias de hasta 4 MiB, con decenas de milisegundos.
Para **adquirir** el respaldo, el ahorro no está demostrado: sin sesión
autorizada, el cliente sigue siendo necesario. [Medición](resource-benchmark.md).

### 9. ¿Qué riesgos presenta una integración remota?

Dependencia de una autorización y unos términos que pueden cambiar; manejo de
sesiones y tokens; vinculación de cuenta/dispositivo; límites de uso y
antiautomatización; privacidad de la partida; integridad y versión del
agregado; revocación; y riesgo legal si se usan endpoints no autorizados. Por
eso 5.4 no integra ninguno.

### 10. ¿Cuál debería ser la Fase 5.5?

Basada solo en lo obtenido:

1. **P0 · Muestra autorizada de 8.8.0.** Obtener una exportación propia con
   procedencia, tamaño y SHA-256; validarla con el importador y compararla con
   8.6.0. Sin ella no se puede declarar compatibilidad.
2. **P0 · Sesión autenticada manual.** El titular inicia sesión y se
   instrumentan panel → recuperar → cancelar → reabrir, con reloj monotónico y
   revisión recibida/consumida. No se automatiza el login.
3. **P1 · Esquema y códec.** Si hay muestra, contrastar `FixData`, secciones y
   el bloque RPC. Sin muestra, mantener la clasificación y no adivinar.
4. **P1 · Vista previa.** Repetir la excepción con la misma cuenta, versión e
   idioma y aislar el argumento nulo.
5. **P2 · Conector autorizado.** Solo si el proveedor documenta una interfaz
   delegada; en caso contrario, consolidar la importación local y la edición
   verificada.
6. **P2 · Semántica de edición.** Validar campos de los nueve formatos 8.6.0 y
   la aceptación por el juego antes de habilitar escritura.

No se propone eludir autenticación, certificados, controles ni protecciones.

## Entregables

| Documento | Contenido |
| --- | --- |
| [fetch-state-machine.md](fetch-state-machine.md) | Cinco dimensiones de estado, eventos, transiciones y casos abiertos. |
| [authenticated-session.md](authenticated-session.md) | Bloqueo, protocolo y límites de la sesión. |
| [session-timeline.md](session-timeline.md) | Cronologías S1/S2/S3 separadas por reloj y sesión. |
| [emulator-diagnostics.md](emulator-diagnostics.md) | Entorno, fallos ABI/gráficos, medición de reposo y reproducción. |
| [rpc-transport-analysis.md](rpc-transport-analysis.md) | Componentes, capas y secuencia confirmada/hipotética. |
| [rpc-format-specification.md](rpc-format-specification.md) | Discriminador, límites, contrato JSON y vectores. |
| [transport-dependency-map.md](transport-dependency-map.md) | Matriz de operaciones y frontera de autorización. |
| [real-880-save-validation.md](real-880-save-validation.md) | Búsqueda, fixture sintético y requisito pendiente. |
| [linux-client-prototype.md](linux-client-prototype.md) | Arquitectura, uso, errores y pruebas del prototipo. |
| [preview-validation.md](preview-validation.md) | Evidencia, candidatos nulos y validación estructural. |
| [resource-benchmark.md](resource-benchmark.md) | Metodología, resultados y limitaciones. |
| [verification.md](verification.md) | Comandos, resultados de pruebas y comprobaciones de secretos. |

## Cambios de código

- `backend/app/cloud/`: transporte, decoder, validador, importador y vista
  previa estructural.
- `backend/app/cloud_import.py`: reutiliza la verificación del validador sin
  cambiar su API ni su CLI.
- `backend/tests/test_cloud_transport.py`: 15 pruebas nuevas sin red.
- `backend/tests/fixtures/cloud-save-880-sintetico.json`: fixture sintético de
  compatibilidad hacia adelante.
- `docs/research/phase5-4/benchmark.py`: medición reproducible.

No se añadieron dependencias, rutas HTTP ni llamadas a endpoints del
proveedor. No se publican respaldos, credenciales ni datos privados.

## Resultado en una frase

**El backend Linux ya puede validar e interpretar un respaldo legítimo que
reciba; todavía no puede obtenerlo por una vía autorizada, y esa sigue siendo
la dependencia real del cliente oficial.**
