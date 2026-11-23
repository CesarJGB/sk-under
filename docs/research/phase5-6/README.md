# Fase 5.6 · Partida real 8.8.0, códec RPC y puente local

**Resultado en una frase:** se obtuvo un perfil local auténtico de Soul Knight
8.8.0 en un emulador propio, se decodificaron sus 18 archivos de datos
(incluido `game.data`), se confirmó que `ZipHelper.Decompress` usa gzip leyendo
su cuerpo en runtime y se implementó un puente local Linux con roundtrip
binario exacto; **no** se obtuvo el agregado de nube ni se probó la aceptación
por el cliente oficial.

Fecha de trabajo: 2026-11-23. Punto de partida: `bfefb01`.

## 1. Clasificación

**Éxito parcial significativo, con avance por encima del mínimo experimental.**
La referencia local 8.8.0 es auténtica y completa para las secciones locales:
20 archivos inventariados, 18 decodificados (17 DES + `game.data` XOR) y 2 JSON
planos de `sandbox`. El roundtrip binario es exacto en los 18. El códec gzip
está confirmado en el cuerpo del método. Lo que impide el éxito principal es la
falta del `CloudSaveGameData` de nube (`serialzedVersion`, `cloudSaveId`,
`platformId`) y la falta de una prueba de restauración en el cliente.

No se presenta como éxito completo: el flujo remoto sigue bloqueado.

## 2. Matriz de objetivos

| Objetivo | Estado | Evidencia |
| --- | --- | --- |
| Referencia auténtica 8.8.0 | **Local: sí**; nube: no | Perfil guest en AVD propio; 20 archivos; [adquisición](real-save-acquisition.md) |
| Formato real de los datos | **Confirmado localmente** | Base64+DES-CBC+JSON y `game.data` XOR; roundtrip 18/18 |
| Algoritmo del códec RPC | **Gzip confirmado** | Cuerpo runtime de `ZipHelper.Decompress`; [RPC](rpc-codec-validation.md) |
| `NetPack`/`ByteBuffer` | **Identificados, no ejercitados** | Metadata de campos/métodos; sin `NetPack` real; [serialización](netpack-bytebuffer.md) |
| Compatibilidad 8.6.0/8.8.0 | **Estructural con datos reales** | 0 claves 8.6.0 ausentes; 5+7 campos nuevos; [esquema](schema-compatibility.md) |
| Puente local sin emulador permanente | **Funcional** | `backend/app/bridge.py`; CLI y pruebas; [puente](local-bridge.md) |
| Importar/validar/reconstruir | **Sí en local** | 18/18 roundtrip binario; edición estructural; [roundtrip](real-save-roundtrip.md) |
| Aceptación por el cliente | **No probada** | Sin restauración autorizada |
| API/transporte remoto | **Bloqueado** | Sin descarga de nube ni contrato publicado |

## 3. Resultados técnicos nuevos

### 3.1 Referencia real 8.8.0

Se instaló el APK oficial 8.8.0 (`54bb332b…`) en un AVD Android 11
`google_apis` x86_64 `userdebug` con KVM, ABI `armeabi-v7a`, y se eligió
**Guest Account**. El cliente creó el perfil local en
`/data/data/com.ChillyRoom.DungeonShooter/files/`. Se copió con `adb root` a un
directorio privado fuera de Git y se conservó el original. No se usaron
credenciales ni datos de terceros.

El perfil contiene:

- 17 archivos Base64 + DES-CBC + JSON (secciones 8.8.0 y caches pre-login);
- `game.data` con `AboGameData` (41 claves) ofuscado con XOR;
- `sandbox_config` y `sandbox_maps` en JSON plano.

Los valores, el sufijo del perfil y las huellas SHA-256 no se publican. La tabla
redactada está en [real-save-acquisition.md](real-save-acquisition.md).

### 3.2 `game.data` descifrado

La capa de `game.data` es un XOR repetido de 15 bytes, no un cifrado fuerte. Se
verificó contra la muestra auténtica:

- el JSON resultante tiene exactamente las 41 claves declaradas por
  `AboGameData`;
- la recodificación reproduce los 25 461 bytes originales;
- una edición de `gems` reabre con el valor nuevo y conserva las otras 40
  claves.

La pista se corroboró con el paquete externo
[`soul-knight-data-processing`](https://pypi.org/project/soul-knight-data-processing/0.0.9/)
(GPL-3.0), que cita a SKDEditor. La implementación de este repositorio es propia (XOR genérico); no se
incorporó código GPL. La clave se corroboró con ese paquete y se validó contra
los bytes auténticos.

### 3.3 Gzip confirmado en runtime

La Fase 5.5 solo tenía la hipótesis. En esta fase se leyó el cuerpo de
`ZipHelper.Decompress` desde `/proc/<pid>/mem` del proceso oficial en el AVD
propio. El desensamblado muestra:

- construcción de `MemoryStream(data, offset, length)`;
- instanciación de `GZipStream(stream, CompressionMode.Decompress, false)`,
  que a su vez construye un `DeflateStream`;
- bucle `Read(byte[], int, int)` y liberación de streams.

Por tanto, si el marcador `00 00 00 80` selecciona la rama comprimida, el cuerpo
es gzip. **No se obtuvo una respuesta RPC real**; el flujo remoto completo sigue
sin ejercitarse. El backend mantiene `rpc_body="reject"` por defecto y
`gzip_candidate` opt-in. Se añadieron `diagnose_gzip` y `diagnose_payload` con
CRC, `ISIZE`, truncamiento, cola y límites.

### 3.4 Compatibilidad 8.6.0/8.8.0

Las nueve muestras reales 8.6.0 conservan todas sus claves superiores en el
perfil 8.8.0. Se observaron 5 campos nuevos en `itemData` y 7 en
`statisticData`, además de las secciones `gameData`, `setting`,
`mallReloadData` y `escapeSeasonData`. Las diferencias lista/objeto vacío se
clasifican como representación de colecciones vacías, no como cambio de tipo
C#. No se declara aceptación por el cliente. Detalle en
[schema-compatibility.md](schema-compatibility.md).

### 3.5 Puente local

`backend/app/bridge.py` separa:

```text
SaveAcquisitionProvider → SaveDecoder → SaveValidator → SaveEditor → SaveExporter
```

`LocalFileProvider`, `LocalSectionDecoder`, `LocalSectionValidator`,
`LocalSectionEditor` y `LocalFileExporter` implementan el flujo sin red, sin
credenciales y sin emulador. El CLI `python -m app.bridge` permite inspeccionar
un archivo o directorio, exportar una copia intacta y editar una ruta existente
en una copia nueva. Límites: 8 MiB por archivo, 64 archivos/32 MiB por
directorio, archivos regulares, `O_NOFOLLOW`, `O_NONBLOCK`, salida `0600` y sin
sobrescritura por defecto. Detalle en [local-bridge.md](local-bridge.md).

### 3.6 Roundtrip

- **Binario:** 18/18 archivos decodificados se reproducen exactamente sin
  cambios, incluido `game.data`.
- **Estructural:** se editó `item_data.cumulativeFishCount` a `2^60`,
  `item_data.trainingJourney.revision` y `game.data.gems`; las copias reabren, los
  campos desconocidos se conservan y el original no cambia.
- **Cliente:** no probado. No se declara.

Detalle en [real-save-roundtrip.md](real-save-roundtrip.md).

## 4. Respuestas expresas

### 1. ¿Se consiguió una partida auténtica 8.8.0?

**Sí, una referencia local auténtica 8.8.0.** No es el agregado de nube
`CloudSaveGameData`; es el perfil local que el cliente 8.8.0 escribe en Android.

### 2. ¿De dónde se obtuvo y cómo se verificó su procedencia?

Del APK oficial 8.8.0 instalado en un AVD propio `userdebug`, perfil Guest
Account, leyendo `/data/data/com.ChillyRoom.DungeonShooter/files/` con
`adb root`. Se verificaron `versionName=8.8.0`, `versionCode=1080800`, ABI
`armeabi-v7a`, el SHA-256 del APK y el contenido de las secciones contra la
metadata 8.8.0. El original se conserva fuera de Git.

### 3. ¿Se confirmó el algoritmo de compresión RPC?

**Sí: gzip.** Confirmado leyendo el cuerpo de `ZipHelper.Decompress` en runtime:
`MemoryStream` + `GZipStream`/`DeflateStream` + bucle `Read`. No se obtuvo un
cuerpo RPC real; la ruta remota no se ejercitó.

### 4. ¿Qué sabemos ahora de NetPack y ByteBuffer?

Sabemos que `NetPack` deriva de `ByteBuffer` y declara `Body`, `BodySize`,
`MsgId`, `ReqIdx` y `Type`; que `ByteBuffer` tiene `ReadString`,
`ReadStringZipped`, `ReadByTypeId` y tags de tipo; y que
`ParseJsonToCloudSaveGameData(string)` espera un string JSON. No sabemos si el
`Body` es JSON directo, una cadena con longitud prefijada o un buffer con tags,
porque falta un mensaje real.

### 5. ¿Se puede interpretar una partida real 8.8.0?

**Sí, las secciones locales:** 18 archivos decodificados, incluido `game.data`
(41 claves). **No** el agregado de nube completo, porque faltan los tres campos
de envoltura.

### 6. ¿Se puede reconstruir sin pérdida estructural?

**Sí en local:** roundtrip binario 18/18 y roundtrip estructural con ediciones
controladas. **No** se puede afirmar lo mismo del agregado de nube ni del
cliente.

### 7. ¿Se consiguió un puente funcional sin emulador permanente?

**Sí.** El puente y el CLI procesan archivos en Linux; el emulador solo se usó
para adquirir la muestra y no queda encendido.

### 8. ¿Qué operaciones siguen necesitando el cliente oficial?

Iniciar sesión, descargar/subir de la nube, restaurar una copia y confirmar que
el juego la acepta. La generación del perfil local y la validación/reconstrucción
en Linux no lo necesitan.

### 9. ¿Qué componentes nuevos funcionan en Linux?

Adaptador local 8.6.0/8.8.0, `game.data` XOR, decodificador y diagnóstico RPC
gzip, puente con interfaces, laboratorio de edición, CLI y pruebas.

### 10. ¿Se puede editar una partida auténtica sin alterar campos ajenos?

**En laboratorio, sí:** se editó `gems`, `cumulativeFishCount` y un entero
anidado; el diff semántico solo contiene la ruta pedida y los campos desconocidos
se conservan. No se permite reemplazar un objeto o una lista completa. **No está probado en el cliente.**

### 11. ¿Qué pruebas pasaron y cuáles quedaron bloqueadas?

Pasaron backend, frontend, navegador, higiene y las pruebas privadas 8.6.0/8.8.0.
Quedaron bloqueadas: respuesta RPC real, agregado de nube, `FixData` y
aceptación por el cliente. El detalle está en la sección 6.

### 12. ¿Qué falta exactamente para la integración remota?

Una copia de nube autorizada del titular (o una respuesta RPC real), el contrato
de `NetPack`, el checksum/MAC si existe y una restauración controlada. Ver
[blockers-and-next-steps.md](blockers-and-next-steps.md).

### 13. ¿Cuál es el experimento más prometedor para la Fase 5.7?

Obtener una copia de nube propia y autorizada del titular y compararla con el
perfil local; en paralelo, capturar un `NetPack` real de esa misma sesión. El
primero valida la envoltura; el segundo cierra la serialización.

## 5. Hipótesis descartadas

- “`game.data` es opaco o no se puede leer”: **descartada**; es XOR JSON y se
  decodificó.
- “gzip era solo un candidato por nombre”: **descartada**; el cuerpo del método
  construye `GZipStream`.
- “Los archivos locales 8.8.0 usan un códec nuevo”: **descartada**; usan el
  mismo DES-CBC que 8.6.0, con nombres y secciones nuevas.
- “El perfil local es el agregado de nube”: **descartada**; faltan
  `serialzedVersion`, `cloudSaveId` y `platformId`.
- “Una copia con los mismos nombres es aceptada por 8.8.0”: **no demostrada**.

## 6. Verificación

| Comando | Resultado |
| --- | --- |
| `cd backend && uv run --locked pytest -q` | **215 passed, 14 skipped** (sin muestras privadas) |
| Suite con las muestras privadas 8.6.0 + 8.8.0 | **229 passed** |
| `cd frontend && npm run build` | Correcto |
| `cd frontend && npm run test:browser` | **4 passed** |
| `git diff --check` | Sin errores |
| Higiene de secretos/artefactos | Sin partidas ni credenciales rastreadas |
| GitHub Actions | Se reporta tras el push |

Las 14 pruebas omitidas son las 9 muestras 8.6.0 y las 5 pruebas privadas
8.8.0; con el entorno privado pasan todas.

## 7. Cambios de código

- `backend/app/parsers/real_save.py`: esquemas 8.8.0, versiones alternativas,
  colecciones vacías, `game.data` XOR.
- `backend/app/formats/real_save.py`: adaptador de 12 secciones, versión
  `8.6.0–8.8.0`, campos no enteros omitidos con seguridad.
- `backend/app/formats/game_data.py`: adaptador de solo lectura de `game.data`.
- `backend/app/main.py`: registro de `GameDataAdapter`.
- `backend/app/local_save.py`: decodificador, laboratorio y resumen de
  directorio para DES y XOR.
- `backend/app/bridge.py`: interfaces, puente y CLI.
- `backend/app/cloud/decoder.py`: `diagnose_gzip` y `diagnose_payload`.
- Pruebas: `test_local_bridge.py`, `test_private_880_roundtrip.py`,
  ampliaciones de `test_real_save.py` y `test_cloud_transport.py`.
- No se añadieron dependencias de producción ni rutas HTTP nuevas.
- No se publican APK, partidas, volcados de memoria ni claves privadas.

## 8. Entregables

| Documento | Contenido |
| --- | --- |
| [real-save-acquisition.md](real-save-acquisition.md) | APK, AVD, Guest Account, inventario redactado y límites |
| [rpc-codec-validation.md](rpc-codec-validation.md) | Confirmación de gzip y diagnóstico |
| [netpack-bytebuffer.md](netpack-bytebuffer.md) | Tipos, tags y lo que falta del `NetPack` |
| [schema-compatibility.md](schema-compatibility.md) | Comparación real 8.6.0/8.8.0 por sección |
| [local-bridge.md](local-bridge.md) | Interfaces, CLI, seguridad y uso |
| [real-save-roundtrip.md](real-save-roundtrip.md) | Roundtrip binario/estructural y límites |
| [blockers-and-next-steps.md](blockers-and-next-steps.md) | Bloqueos y plan 5.7 |

## 9. Conclusión

La Fase 5.6 convierte una hipótesis en evidencia: hay una referencia local real
8.8.0, el códec local está resuelto, gzip está confirmado y el puente Linux
funciona. La integración remota sigue dependiendo de una copia de nube
autorizada y de una prueba de aceptación en el cliente; no se declara cerrada.
