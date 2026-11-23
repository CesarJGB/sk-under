# Códec RPC: evidencia estática y límite de la virtualización

**Estado: parcial y acotado.** Se identificó la clase y la firma que el cliente
usa para descomprimir el bloque RPC, se confirmó el sobre de cuatro bytes y se
implementó un decodificador **gzip candidato, opt-in**, con vectores sintéticos.
No se obtuvo un cuerpo RPC real ni se pudo leer estáticamente el cuerpo de
`ZipHelper.Decompress`: el APK 8.8.0 lo protege con el mismo empaquetador ACE
que cifra la metadata y virtualiza parte del código.

## 1. Cadena observada

| Paso | Evidencia | Estado |
| --- | --- | --- |
| `LoginApi._Decompress` recibe un `byte[]` y devuelve `ChillyRoom.RPC.NetPack`. | Método `0x06009e07`, VA `0x0636cefc`, signatura resuelta desde metadata. | Confirmado en código. |
| Lee un `uint32` LE en el offset 0. | `+0x84..+0x9c`; umbral de 4 bytes. | Confirmado. |
| `0x80000000` selecciona la rama comprimida. | `+0xa0..+0xc0`; bytes `00 00 00 80`. | Confirmado. |
| Llama a `ZipHelper.Decompress(bytes, 4, len-4)`. | `bl 0x077b0c0c` en `0x0636cfbc`; el destino coincide con el puntero del método `0x06002663`. | Confirmado. |
| El resultado se envuelve en un `NetPack`. | `NetPack` deriva de `ByteBuffer` y expone `Body`, `BodySize`, `ReadString`, `ReadStringZipped`. | Confirmado por metadata. |
| `0xFFFFFFFF` devuelve nulo. | `+0xe8..+0xf0`; rama separada. | Confirmado. |
| Cualquier otro entero conserva el array original. | Rama común. | Confirmado. |

El prefijo es un **discriminador de transporte**, no la cabecera gzip. La
compresión HTTP (`Content-Encoding`) y esta rama RPC son capas distintas.

## 2. `ZipHelper` identificado

En la metadata descifrada de 8.8.0, el tipo global `ZipHelper` (typeDef 1070)
declara cinco métodos:

| Token | Método | Retorno | Parámetros |
| --- | --- | --- | --- |
| `0x06002660` | `GZipCompressString` | `string` | 1 |
| `0x06002661` | `GZipDecompressString` | `string` | 1 |
| `0x06002662` | `Compress` | `byte[]` | 3 |
| `0x06002663` | `Decompress` | `byte[]` | 3 |
| `0x06002664` | `.ctor` | `void` | 0 |

`ChillyRoom.Utils.ZipHelper` (typeDef 15046) repite la familia con otros
tokens; `System.IO.Compression.ZipHelper` y `SharpZipLib` también están
presentes, pero no son el destino de esta llamada. El detalle está en
[ziphelper-analysis.md](ziphelper-analysis.md).

## 3. Por qué no se leyó el cuerpo

El APK usa ACE (`libanogs.so` + `libanort.so`). La metadata se descifra con el
esquema descrito en [save-schema-880.md](save-schema-880.md). El código también
está protegido: los punteros de métodos sensibles apuntan a una región
(XOR `0x03` en los bloques observados) que se comporta como un despachador
virtual, no como el prólogo de la función. Por ejemplo:

- `ZipHelper.Decompress` apunta a `0x077b0c0c`.
- `ByteBuffer.ReadString` apunta a `0x077b0a40`.
- `ByteBuffer.ReadStringZipped` apunta a `0x077b0b30`.
- Los tres caen dentro de la misma región y no empiezan con un prólogo AArch64.

Una lectura con XOR `0x03` produce instrucciones válidas pero **entradas
interiores** de una función mayor; no es una implementación recuperable de
`Decompress`. No se intentó derrotar la virtualización ni ejecutar el cliente.

## 4. Evidencia de que el códec candidato es gzip

La evidencia es **de clase y de firmas**, no del cuerpo:

1. La misma clase expone `GZipCompressString`/`GZipDecompressString`, que por
   nombre y por el patrón público usan `System.IO.Compression.GZipStream`.
2. `Compress`/`Decompress` tienen la firma habitual `(byte[] data, int offset,
   int length) -> byte[]`; el patrón público equivalente envuelve un
   `MemoryStream` en `GZipStream`.
3. `ByteBuffer` expone `ReadString` y `ReadStringZipped`, lo que confirma que
   el protocolo transporta cadenas comprimidas, pero no fija el algoritmo.
4. No se observó ninguna referencia a LZ4, Brotli o Deflate crudo en la ruta
   `_Decompress`; sí hay `System.IO.Compression` y cadenas `"gzip"` en el
   binario, aunque esas cadenas también pueden describir HTTP.

**Conclusión:** gzip es la hipótesis con más apoyo, pero **no está demostrada
para un cuerpo RPC real**. No se declara que el bloque sea gzip.

## 5. Implementación

`backend/app/cloud/decoder.py` añade:

- `decode_rpc_gzip(payload, frame=None)`: exige el marcador comprimido y la
  firma `1f 8b`; delega en `reconstruct_cloud_save`, que valida CRC, tamaño,
  truncamiento y bytes posteriores.
- `decode_copy(..., rpc_body="reject")`: por defecto sigue rechazando el cuerpo
  con `RpcBodyUnknown`. El valor `rpc_body="gzip_candidate"` habilita el intento
  experimental.
- `validate_payload(..., rpc_body=...)` propaga la política.

Límites vigentes: entrada total 8 MiB, JSON descomprimido 16 MiB, profundidad
64. Un cuerpo que no empiece por `1f 8b` produce `RpcBodyNotGzip`; un gzip
truncado o con bytes posteriores produce `AggregateFormatError`; una bomba que
supere 16 MiB produce `CopyLimitError`.

## 6. Lo que falta para cerrar el códec

1. Un cuerpo RPC real, con SHA-256 y el texto/estructura que el cliente obtuvo
   de él, para comparar entrada y salida.
2. O una copia de memoria del `libil2cpp.so` ya descifrado, con el cuerpo de
   `ZipHelper.Decompress`, para leer la llamada a `GZipStream`/`DeflateStream`.
3. Confirmar si el `NetPack.Body` descomprimido es JSON UTF-8, un `ByteBuffer`
   binario o una cadena serializada. La signatura del callback no basta.

Sin uno de esos elementos, la implementación queda como **candidato
experimental** y no se usa en el flujo de producción.

## 7. Capas que no se deben confundir

| Capa | Qué es | Evidencia |
| --- | --- | --- |
| Transporte HTTP | `HttpResponseMessage`, `Accept-Encoding`, `Content-Encoding` | Código del cliente y documentación previa. |
| Sobre RPC | `uint32` inicial + cuerpo | Confirmado en dos ABI. |
| Compresión | `ZipHelper.Decompress` sobre el cuerpo desde offset 4 | Llamada confirmada; algoritmo no confirmado. |
| Serialización | `NetPack`/`ByteBuffer` y `ParseJsonToCloudSaveGameData` | Tipos y llamadas confirmadas; representación efectiva abierta. |
| Cifrado | ACE en metadata y código, no en el cuerpo RPC observado | Esquema ACE confirmado para metadata; no se observó cifrado del cuerpo. |
