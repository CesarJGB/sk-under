# `NetPack`, `ByteBuffer` y la serialización interior

**Resultado:** la metadata 8.8.0 confirma los contenedores y sus operaciones,
pero **no** hay una respuesta RPC real que permita decidir si el `Body` es JSON
UTF-8 directo, una cadena con longitud prefijada o una estructura binaria. La
Fase 5.6 separa lo confirmado por tipos de lo inferido y evita presentar los
vectores sintéticos como formato real.

## 1. Tipos identificados

| Tipo | Evidencia | Papel |
| --- | --- | --- |
| `ChillyRoom.RPC.NetPack` | Tipo de la metadata descifrada; deriva de `ByteBuffer` | Sobre de mensaje RPC con cuerpo y cabecera |
| `ByteBuffer` | Token `0x0200042b`; métodos de lectura/escritura | Buffer binario y lector de tipos |
| `LoginApi._Decompress` | Método `0x06009e07`; rama gzip | Convierte la respuesta en `NetPack` |
| `NewCloudSaveAgent.ParseJsonToCloudSaveGameData` | `0x06021c00`; recibe `string` y devuelve `CloudSaveGameData` | Parseo del JSON de la nube |
| `NewCloudSaveAgent.FixData` | `0x06021bf5`; `string -> string` | Corrección textual antes o después del parseo |

## 2. Campos y métodos de `NetPack`

La metadata y las cadenas de la tabla de literales muestran:

- campos `Body`, `BodySize`, `MsgId`, `ReqIdx`, `Type`, `MatchState`;
- constantes `HEADER_SIZE`, `TYPE_INDEX`, `OPCODE_INDEX`, `REQ_IDX_INDEX`,
  `TYPE_TCP`, `TYPE_UDP`, `TYPE_UNRELIABLE`;
- métodos `ResetHead`, `GetReqKey`, `get_Body`, `get_BodySize`,
  `get_MsgId`, `get_ReqIdx`, `get_Type`.

Esto confirma que el sobre tiene una cabecera propia y un cuerpo separado. Los
**valores** de `HEADER_SIZE` y de los índices no se han recuperado de una
respuesta real; no se inventan.

## 3. `ByteBuffer`

La metadata enumera, entre otros:

- `SetPosRead`, `GetPos`, `SetPos`, `get_LeftBuf`, `get_Size`;
- `WriteBool/Int8/UInt8/Byte/Int16/UInt16/Int32/UInt32/Int64/UInt64/Float/Double/String/Buf`;
- `ReadInt8/ReadBool/ReadUInt8/ReadByte/ReadInt16/ReadUInt16/ReadInt32/ReadUInt32/ReadInt64/ReadUInt64/ReadFloat/ReadDouble/ReadString/ReadStringZipped`;
- `ReadByTypeId` y los tags `T_BOOL`, `T_INT8`, `T_INT16`, `T_INT32`,
  `T_UINT8`, `T_UINT16`, `T_UINT32`, `T_FLOAT`, `T_DOUBLE`, `T_STRING`,
  `T_UUID`, `T_VEC2F`, `T_FACING`.

La existencia de `ReadStringZipped` demuestra que el protocolo puede transportar
cadenas comprimidas dentro del buffer. También es coherente con que
`GZipDecompressString`/`GZipCompressString` estén en la misma clase `ZipHelper`.
No demuestra que el `Body` completo sea una cadena comprimida.

## 4. Relación con `CloudSaveGameData`

`NewCloudSaveAgent.ParseJsonToCloudSaveGameData(string)` recibe un `string` y
devuelve `CloudSaveGameData`. `FixData(string) -> string` sugiere una corrección
textual antes del parseo. La ruta más probable es:

```text
respuesta RPC → marcador → ZipHelper.Decompress (gzip confirmado)
             → NetPack (cabecera + Body)
             → Body/ReadString o ReadStringZipped
             → string JSON
             → FixData(string)
             → ParseJsonToCloudSaveGameData(string)
             → CloudSaveGameData
```

La ruta es **inferida** a partir de firmas y nombres. No se ha observado un
`NetPack` real ni se ha ejecutado `ParseJsonToCloudSaveGameData` con una
respuesta de nube. Las alternativas siguen abiertas:

| Alternativa | Evidencia a favor | Evidencia en contra o ausente |
| --- | --- | --- |
| `Body` es JSON UTF-8 directo | `ParseJson...` recibe `string`; el contrato sintético es JSON | No se ha visto la cabecera ni el `Body` |
| `Body` es una cadena con longitud prefijada | `ReadString`/`ReadStringZipped`; `ByteBuffer` | No se conoce el prefijo exacto |
| `Body` es un buffer binario con tags | `ReadByTypeId`, tags `T_*` | No se ha observado un mensaje real |
| Hay una compresión adicional | `ReadStringZipped` | gzip del sobre ya está confirmado; no se ha visto otra capa |

## 5. Vectores sintéticos y lo que no prueban

Los vectores de `backend/tests/fixtures/rpc-frames-sinteticos.json` y las
pruebas de `test_cloud_transport.py` comprueban que el backend:

- clasifica `00 00 00 80`, `FF FF FF FF` y el paso directo;
- descomprime un gzip sintético con CRC y límites;
- rechaza cuerpos sin firma gzip y bombas;
- distingue un cuerpo desconocido de un JSON válido.

Estos vectores **no** confirman el formato real. Solo confirman que el
decodificador se comporta de forma conservadora con datos que ya se sabe cómo
tratar.

## 6. Qué falta

1. Un `NetPack` real, aunque sea de una respuesta de configuración o de una
   cuenta propia, para medir `HEADER_SIZE`, `MsgId`, `ReqIdx` y `BodySize`.
2. Comparar el `Body` con el JSON que el cliente muestra o aplica.
3. Confirmar si `ReadStringZipped` se usa para el cuerpo de la partida y con qué
   algoritmo (probablemente gzip, pero no probado en esta ruta).
4. Confirmar el valor de `serialzedVersion` y el orden de `FixData`.

Sin esos datos, `ParseJsonToCloudSaveGameData` queda identificado, no
ejercitado.
