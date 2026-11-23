# Fase 5.5 · Códec RPC, esquema 8.8.0 y adquisición verificable

**Resultado en una frase:** el editor ya descifra e inventaría la metadata real
de 8.8.0, demuestra que las nueve estructuras 8.6.0 conservan todos sus nombres
en el modelo nuevo y añade un laboratorio local de edición; el códec RPC queda
identificado como `ZipHelper.Decompress` pero **no confirmado**, porque ACE
virtualiza su cuerpo y no hay una respuesta real.

Fecha de trabajo: 2026-11-22. Punto de partida: `0d706f2`.

## 1. Matriz de objetivos

| Objetivo | Estado | Evidencia |
| --- | --- | --- |
| Códec RPC | **Parcial** | `ZipHelper.Decompress(byte[],int,int)` identificado; gzip candidato opt-in; cuerpo virtualizado. [rpc-codec-research.md](rpc-codec-research.md) |
| `ZipHelper.Decompress` | **Identificado, no decompilado** | TypeDef 1070, token `0x06002663`, llamada `0x0636cfbc → 0x077b0c0c`. [ziphelper-analysis.md](ziphelper-analysis.md) |
| Esquema 8.8.0 | **Identificado en código** | `CloudSaveGameData` 18 campos; 46 649 typeDefs; inventario JSON. [save-schema-880.md](save-schema-880.md) |
| Diferencias 8.6.0/8.8.0 | **Verificado por nombres** | 0 claves 8.6.0 ausentes; 39+12+6+2+1 campos nuevos. [schema-diff-860-880.md](schema-diff-860-880.md) |
| Adquisición legítima | **Bloqueada** | Solo nube manual del cliente; sin exportación ni API. [acquisition-research.md](acquisition-research.md) |
| Referencia real 8.8.0 | **No obtenida** | Solo APK y `.data` 8.6.0; fixture sintético. [real-880-reference.md](real-880-reference.md) |
| Laboratorio de edición | **Confirmado (sintético)** | `SaveLab`, 9 pruebas, CLI, diff semántico/binario. [save-editing-lab.md](save-editing-lab.md) |
| Integración backend | **Confirmada** | `decode_rpc_gzip` opt-in; `validate_payload(rpc_body=...)`; sin rutas nuevas. |
| CI de GitHub | **Confirmado localmente; remoto pendiente** | `.github/workflows/ci.yml`; pruebas y build locales. |

## 2. Resultados técnicos nuevos

### 2.1 Metadata 8.8.0 descifrada

El `global-metadata.dat` del APK no es un archivo IL2CPP estándar. Se aplicó el
esquema ACE: XOR `0x66` en el encabezado, AES-128-CBC en `[0x1000,0x5000)`, XOR
en los primeros `0x4000` de cada bloque de `0x10000` desde `0x11000`, y cola
XOR. El resultado tiene cabecera válida, versión 31, 46 649 typeDefs, 380 122
métodos y 350 248 campos.

Esto convierte una limitación histórica (“no se puede leer la metadata”) en un
inventario reproducible. El método está en
[`tools/metadata_inventory.py`](tools/metadata_inventory.py).

### 2.2 Esquema 8.8.0

`CloudSaveGameData` (typeDef 3018) declara exactamente las 18 claves del
contrato: `serialzedVersion`, `cloudSaveId`, `platformId`, `gameData`,
`itemData`, `statisticData`, `settingData`, `taskData`, `maps`,
`sandboxConfig`, `seasonData`, `mallReloadData`, `monsterRiseData`,
`weaponEvolutionData`, `miscData`, `pvpData`, `battlePassSaveData` y
`escapeSeasonData`.

Los modelos de sección tienen 118 campos (`ItemData`), 171 (`StatisticData`),
78 (`SeasonData`), 16 (`TaskDatas`), etc. El detalle está en
[`metadata-880-inventory.json`](metadata-880-inventory.json).

### 2.3 Compatibilidad 8.6.0 → 8.8.0

Las nueve muestras 8.6.0 conservan **todas** sus claves superiores en el modelo
8.8.0. Aparecen campos nuevos, sobre todo en `itemData` (39) y
`statisticData` (12). No se declara que el cliente 8.8.0 acepte un archivo
8.6.0; solo se demuestra que los nombres siguen declarados.

### 2.4 Códec RPC

La cadena confirmada es:

```text
respuesta byte[] → uint32 LE
  0x80000000 → ZipHelper.Decompress(bytes, 4, len-4) → NetPack
  0xFFFFFFFF → null
  otro       → NetPack(bytes)
```

`ZipHelper` expone `GZipCompressString`, `GZipDecompressString`, `Compress` y
`Decompress`. `Decompress` devuelve `byte[]` y recibe `(byte[], int, int)`. El
cuerpo del método no se puede leer: el puntero `0x077b0c0c` cae en una región
virtualizada por ACE, igual que `ByteBuffer.ReadString` y `ReadStringZipped`.

Se implementó un **gzip candidato opt-in** (`decode_rpc_gzip`) que exige
`1f 8b`, valida CRC/truncamiento y limita la salida a 16 MiB. El flujo por
defecto sigue rechazando el cuerpo con `RpcBodyUnknown`.

### 2.5 Laboratorio de edición

`SaveLab` permite cargar JSON/gzip, editar rutas existentes, conservar campos
desconocidos, respetar tipos y números grandes, serializar, reabrir y comparar.
La CLI crea copia `.bak` si el destino existe y nunca escribe la entrada.

### 2.6 Adquisición

La documentación oficial solo describe carga/descarga manual desde el cliente.
No hay botón de exportación, archivo público ni API para terceros. El soporte
puede recuperar copias de su sistema, pero no publica un formato ni un contrato.

## 3. Respuestas expresas

### 1. ¿Se identificó el algoritmo de compresión RPC?

**Parcialmente.** Se identificó el método (`ZipHelper.Decompress`) y su familia
(`GZipCompressString`/`GZipDecompressString`), y la hipótesis gzip es la mejor
soportada. **No** se pudo leer el cuerpo para confirmar `GZipStream` ni se
obtuvo un cuerpo real. No se declara gzip confirmado.

### 2. ¿Podemos descomprimir un bloque RPC real o sintético compatible?

Un bloque **sintético** con prefijo `00 00 00 80` + gzip de un agregado se
decodifica con `decode_rpc_gzip` y `rpc_body="gzip_candidate"`. Un bloque real
no se probó porque no hay muestra.

### 3. ¿Qué transformaciones faltan para interpretar una respuesta completa?

Confirmar que el cuerpo es gzip; confirmar si el resultado es JSON UTF-8 o un
`NetPack`/`ByteBuffer` binario; conocer la cabecera del `NetPack` y el
`serialzedVersion` efectivo de 8.8.0; y verificar la ruta `FixData` antes del
parseo.

### 4. ¿Qué diferencias verificables existen entre 8.6.0 y 8.8.0?

Todas las claves 8.6.0 siguen declaradas. Hay 39 campos nuevos en `itemData`,
12 en `statisticData`, 6 en `seasonData`, 2 en `taskData` y 1 en
`monsterRiseData`; `weaponEvolutionData`, `miscData`, `pvpData` y
`battlePassSaveData` coinciden en nombres. La lista exacta está en
[`schema-diff-860-880.json`](schema-diff-860-880.json).

### 5. ¿Podemos interpretar una partida real 8.8.0?

**No.** No hay una muestra real. El modelo, el validador y el laboratorio están
listos, pero sin bytes no se puede comprobar el esquema efectivo ni la
aceptación.

### 6. ¿Existe una forma autorizada de obtener respaldos sin emulador?

**No se localizó.** La vía oficial es la nube dentro del cliente; el soporte
puede recuperar copias de su sistema. No hay exportación de archivo ni API
delegada. La alternativa autorizada sería una exportación oficial o una
delegación publicada por ChillyRoom.

### 7. ¿Qué componentes siguen dependiendo de Android?

Iniciar sesión, subir/descargar de la nube, restaurar en el juego y confirmar
que una copia editada es aceptada. Validar, comparar, editar y reconstruir una
copia local ya no dependen de Android.

### 8. ¿Podemos modificar y reconstruir una copia local sin perder campos?

**Sí en el laboratorio sintético:** 9 pruebas confirman conservación de campos
desconocidos, tipos, enteros de 53+ bits, gzip y roundtrip. **No está probado**
en una partida real ni en el cliente.

### 9. ¿Qué validaciones faltan antes de habilitar edición real?

Una muestra 8.8.0 auténtica; confirmar campos opcionales y tipos; ejecutar
`FixData`; comprobar el checksum/MAC que use el proveedor; restaurar una copia
editada en el cliente oficial; y verificar que no se alteran campos ajenos.

### 10. ¿Cuál debería ser el siguiente experimento más valioso?

**Obtener una exportación 8.8.0 del titular y restaurarla en el cliente
oficial**, conservando el original y su SHA-256. En paralelo, si se autoriza,
una copia de memoria del `libil2cpp.so` descifrado para leer el cuerpo de
`ZipHelper.Decompress`. El primero valida el esquema; el segundo cierra el
códec.

## 4. Hipótesis descartadas

- “El cuerpo RPC es gzip confirmado”: descartada como certeza; queda como
  candidato.
- “`ZipHelper.Decompress` se puede decompilar estáticamente”: descartada; ACE
  virtualiza la región.
- “Los `.data` 8.6.0 son el agregado”: descartada; son caches por subsistema.
- “El APK contiene una partida 8.8.0”: descartada; no hay archivo de partida.
- “El fixture 8.8.0 es una muestra real”: descartada; es sintético.
- “Existe una exportación oficial de archivo”: descartada; no está documentada.
- “El soporte entrega un archivo machine-readable”: no demostrado.

## 5. Bloqueos

| Bloqueo | Consecuencia | Qué falta |
| --- | --- | --- |
| Sin muestra 8.8.0 | No se declara compatibilidad | Exportación del titular o soporte. |
| Código virtualizado | No se lee el cuerpo de `ZipHelper` | Copia de memoria descifrada o cuerpo real. |
| Sin API/exportación | Transporte remoto deshabilitado | Contrato del proveedor. |
| Sin prueba en cliente | No se declara edición real | Restauración autorizada de una copia editada. |

## 6. Cambios de código

- `backend/app/cloud/decoder.py`: `decode_rpc_gzip`, `RpcBodyNotGzip`, política
  `rpc_body`.
- `backend/app/cloud/validator.py`: `rpc_body` propagado.
- `backend/app/cloud/lab.py`: laboratorio de edición y comparación.
- `backend/tests/test_cloud_transport.py`: 4 pruebas RPC/gzip/bomba.
- `backend/tests/test_save_lab.py`: 9 pruebas del laboratorio.
- `.github/workflows/ci.yml`: backend, frontend, navegador e higiene.
- `docs/research/phase5-5/`: informes, inventarios, herramientas CLI.
- No se añadieron rutas HTTP, dependencias de producción ni llamadas de red.

## 7. Verificación

| Comando | Resultado |
| --- | --- |
| `cd backend && uv run --locked pytest -q` | **182 passed, 9 skipped** |
| Suite con las nueve muestras privadas | **191 passed** |
| `cd frontend && npm run build` | Correcto. |
| `cd frontend && npm run test:browser` | **4 passed**. |
| `git diff --check` | Sin errores. |
| CI local de higiene | Sin secretos ni artefactos privados rastreados. |

Las 9 pruebas omitidas son las muestras privadas 8.6.0; con el entorno privado
pasan las 9 y la suite total es 191. No se publican valores, identidades ni
huellas de esas muestras.

## 8. Entregables

| Documento | Contenido |
| --- | --- |
| [rpc-codec-research.md](rpc-codec-research.md) | Cadena RPC, evidencia, virtualización y límites. |
| [ziphelper-analysis.md](ziphelper-analysis.md) | Tipos, firmas, llamada y por qué no se decompila. |
| [rpc-codec-test-vectors.md](rpc-codec-test-vectors.md) | Vectores sintéticos, hashes y límites. |
| [save-schema-880.md](save-schema-880.md) | Metadata descifrada y modelos 8.8.0. |
| [schema-diff-860-880.md](schema-diff-860-880.md) | Diferencias por nombre y clasificación. |
| [fixdata-analysis.md](fixdata-analysis.md) | Superficie de migración declarada. |
| [acquisition-research.md](acquisition-research.md) | Vías oficiales y bloqueo. |
| [client-dependency-analysis.md](client-dependency-analysis.md) | Matriz operación/dependencia. |
| [authorized-export-options.md](authorized-export-options.md) | Opciones y petición al proveedor. |
| [real-880-reference.md](real-880-reference.md) | Procedimiento y archivo exacto que falta. |
| [save-editing-lab.md](save-editing-lab.md) | Garantías, API, CLI y pruebas. |
| [metadata-880-inventory.json](metadata-880-inventory.json) | Tipos y campos 8.8.0. |
| [metadata-880-methods.json](metadata-880-methods.json) | Firmas seleccionadas. |
| [schema-diff-860-880.json](schema-diff-860-880.json) | Diff reproducible. |
