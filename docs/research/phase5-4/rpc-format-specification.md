# Especificación parcial del formato RPC y del agregado

**Estado: parcial.** El único elemento demostrado del sobre RPC es el
discriminador de cuatro bytes y el desplazamiento del cuerpo. El códec interior
del bloque comprimido, la representación HTTP completa y las claves del DTO no
están resueltos. Esta especificación describe lo que el repositorio puede
clasificar sin adivinar; no autoriza llamadas a endpoints privados.

## 1. Sobre RPC

El cliente lee un `uint32` little-endian con `BitConverter.ToUInt32(bytes, 0)`
y decide la rama. Los bytes del prefijo se escriben en el orden en que viajan.

| Bytes iniciales | `uint32` LE | Rama | Cuerpo | Resultado |
| --- | ---: | --- | --- | --- |
| `00 00 00 80` | `0x80000000` | Comprimida | `payload[4:]` | `ZipHelper.Decompress(body, 4, len-4)`; el resultado no está demostrado. |
| `FF FF FF FF` | `0xFFFFFFFF` | Marca nula | Ninguno | La rama devuelve nulo; su significado de aplicación no está demostrado. |
| `80 00 00 00` | `0x00000080` | Común | `payload` completo | **No** es el marcador comprimido; se conserva. |
| 0–3 bytes | — | Común | `payload` completo | Se conserva; el umbral mínimo es 4. |
| Cualquier otro valor | — | Común | `payload` completo | Se conserva envuelto. |
| Entrada nula | — | Independiente | Ninguno | `null_input`. |

Un prefijo `FF FF FF FF` seguido de datos sigue siendo marca nula: la
comparación se hace sobre los primeros cuatro bytes. Un prefijo
`00 00 00 80` sin cuerpo también selecciona la rama comprimida; el resultado de
descomprimir cero bytes no se conoce.

### Límites locales

| Límite | Valor | Dónde |
| --- | ---: | --- |
| Entrada total | 8 MiB | `MAX_INPUT_BYTES` |
| JSON descomprimido | 16 MiB | `MAX_JSON_BYTES` |
| Profundidad JSON | 64 | `MAX_JSON_DEPTH` |
| Longitud mínima del discriminador | 4 bytes | `inspect_rpc_frame` |

`inspect_rpc_frame` no descomprime. Un cuerpo comprimido produce
`RpcBodyUnknown`; una marca nula produce `RpcNullMarker`. Ambos conservan el
original para inspección local, pero no se entregan como agregado.

## 2. Capas exteriores

| Capa | Representación | Confirmado | Pendiente |
| --- | --- | --- | --- |
| HTTP | `HttpResponseMessage`, estado 200/400/401/500, cabeceras y `Accept-Encoding`. | Código del cliente. | Cuerpo y cabeceras de la respuesta real. |
| DTO BlobSave | `JsonPayload` con un campo administrado `Data` de tipo string. | Tipo y campo. | Clave JSON de red, codificación y límites. |
| RPC | Callback de éxito `Action<string>` y fallo `Action<Err,Exception>`. | Firmas y llamada. | Unión completa entre respuesta y callback. |
| `Data` | Texto que el agente pasa a `ParseJsonToCloudSaveGameData(string)`. | Llamada estática. | Si el texto es el agregado directo o una envoltura adicional. |
| Agregado | Objeto JSON UTF-8 con versión, identidad, `gameData` y subsistemas. | Modelo y contrato provisional. | Esquema efectivo de 8.8.0. |

La compresión HTTP (`Content-Encoding`) y la compresión RPC (marcador +
`ZipHelper`) son capas distintas. **No se demostró que el bloque RPC sea gzip**
aunque el cliente también tenga un helper gzip para HTTP. El nombre
`ZipHelper.Decompress` no identifica por sí solo el algoritmo.

## 3. Agregado JSON: contrato del prototipo

`reconstruct_cloud_save(bytes)` acepta un objeto JSON UTF-8 o un único miembro
gzip que lo contiene. El contrato es provisional y se aplica solo a una copia
ya suministrada.

| Campo | Tipo | Obligatorio | Tratamiento |
| --- | --- | --- | --- |
| `serialzedVersion` | entero ≥ 0 | Sí | Se conserva; no se interpreta como versión del APK. |
| `cloudSaveId` | texto no vacío | Sí | Se conserva; no se publica en resúmenes. |
| `platformId` | texto no vacío | Sí | Se conserva; no se publica en resúmenes. |
| `gameData` | objeto | Sí | Progreso general; se conserva. |
| `itemData`, `statisticData`, `settingData`, `taskData`, `seasonData`, `mallReloadData`, `monsterRiseData`, `weaponEvolutionData`, `miscData`, `pvpData`, `battlePassSaveData`, `escapeSeasonData` | objeto o nulo | No | Se distingue presente, nulo y ausente. |
| `maps`, `sandboxConfig` | forma abierta | No | Se conservan como JSON. |
| Cualquier otro miembro | cualquiera | No | Se conserva en `extra_fields`. |

Se rechazan claves duplicadas, números no finitos, UTF-8 inválido, gzip
truncado o con datos posteriores, tipos incompatibles y una raíz que no sea
objeto. El orden de campos y los enteros de precisión arbitraria se conservan
en la medida en que el lector JSON de Python los preserve.

## 4. Vectores ejecutables

El fixture `rpc-frames-sinteticos.json` contiene once vectores. Los más
importantes:

| `wire` | `kind` | Lectura |
| --- | --- | --- |
| `null` | `null_input` | Entrada ausente. |
| `""`, `00`, `0000`, `000000` | `passthrough` | Menos de cuatro bytes; se conservan. |
| `80000000` | `passthrough` | `0x00000080`; no es el marcador. |
| `00000080` | `compressed` | Cuerpo vacío. |
| `00000080deadbeef` | `compressed` | Cuerpo `deadbeef`; no se descomprime. |
| `ffffffff` | `null_marker` | Marca nula. |
| `ffffffff01` | `null_marker` | La marca prevalece sobre los datos posteriores. |

Las pruebas del clasificador están en
`backend/tests/test_cloud_import.py` y `backend/tests/test_cloud_transport.py`.
Los vectores se generan localmente; no se obtuvo ningún cuerpo de una cuenta.

## 5. Lo que esta especificación no dice

- No define el endpoint, el método HTTP, las cabeceras de autenticación ni los
  parámetros de la cuenta.
- No define el algoritmo de `ZipHelper.Decompress` ni el formato del bloque
  interior.
- No demuestra que `JsonPayload.Data` sea el agregado directo en todos los
  canales.
- No demuestra que la cuenta de prueba usara BlobSave o RPC.
- No fija el esquema de 8.8.0 ni las migraciones de `FixData`.
- No convierte el clasificador local en un cliente remoto.

La [máquina de estados](fetch-state-machine.md) y el
[análisis de transporte](rpc-transport-analysis.md) usan esta especificación
solo para las transiciones que la evidencia sostiene.
