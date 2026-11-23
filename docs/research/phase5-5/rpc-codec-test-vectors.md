# Vectores del códec RPC candidato

Todos los vectores son sintéticos y se generan localmente. **No proceden de una
cuenta ni de una respuesta del proveedor.** Se usan para verificar el
clasificador, el decodificador gzip opt-in y los límites, no para declarar que
el juego acepte el formato.

## 1. Vector comprimido válido

Documento base: `backend/tests/fixtures/cloud-save-sintetico.json` (283 bytes).
Cuerpo: `gzip.compress(documento, mtime=0)`, 184 bytes.
Sobre: prefijo `00 00 00 80` + cuerpo, 188 bytes.

| Elemento | Valor |
| --- | --- |
| Documento SHA-256 | `b369be549e995bb24720ce6276e85d8f264092798603f0712f5c8ecd33f38277` |
| Cuerpo SHA-256 | `62e84a0b93c6f7b38886d85a78d97ea97bca99cdb2cae0395f8f8e790a0cbaeb` |
| Cuerpo, primeros 8 bytes | `1f 8b 08 00 00 00 00 00` |
| Sobre SHA-256 | `919d8de8b653e23a82a8f4b6ed31c4dd3968a668570bdf79a84cccec5d011ce1` |
| Sobre, primeros 8 bytes | `00 00 00 80 1f 8b 08 00` |

Resultado esperado:

- `decode_copy(sobre)` → `RpcBodyUnknown` (`rpc_codec_unknown`), política por
  defecto.
- `decode_copy(sobre, rpc_body="gzip_candidate")` → `DecodedCopy("gzip", ...)`.
- `decode_rpc_gzip(sobre)` → agregado con `serialzedVersion=0`.
- `decoded.original == sobre` (se conserva el sobre completo).
- `decoded.aggregate.source_sha256 == SHA-256(cuerpo)`.

## 2. Vectores negativos

| Vector | Entrada | Resultado |
| --- | --- | --- |
| Cuerpo no gzip | `00 00 00 80` + `cuerpo` | `RpcBodyNotGzip` (`rpc_body_not_gzip`). |
| Cuerpo vacío | `00 00 00 80` | `RpcBodyUnknown`. |
| gzip truncado | sobre + cuerpo sin los últimos 4 bytes | `AggregateFormatError`. |
| gzip con basura | sobre + cuerpo + `x` | `AggregateFormatError`. |
| Bomba de descompresión | sobre + gzip de más de 16 MiB de espacios | `CopyLimitError`. |
| Marca nula | `ff ff ff ff` + datos | `RpcNullMarker`. |
| Passthrough | `80 00 00 00` | Se clasifica como `passthrough`, no como comprimido. |
| Entrada corta | `00`, `0000`, `000000` | `passthrough`; no se descomprime. |

Los vectores de marcador y longitud están en
`backend/tests/fixtures/rpc-frames-sinteticos.json`; los de gzip se construyen
en `backend/tests/test_cloud_transport.py`.

## 3. Límites

| Límite | Valor | Dónde |
| --- | ---: | --- |
| Entrada total | 8 MiB | `MAX_INPUT_BYTES` |
| JSON descomprimido | 16 MiB | `MAX_JSON_BYTES` |
| Profundidad JSON | 64 | `MAX_JSON_DEPTH` |
| Longitud mínima del discriminador | 4 bytes | `inspect_rpc_frame` |
| Cuerpo comprimido | `len(payload)-4` | `RpcFrame.body` |

## 4. Comandos

```bash
cd backend
uv run --locked pytest -q tests/test_cloud_transport.py
uv run --locked pytest -q tests/test_cloud_transport.py -k rpc
```

## 5. Lo que estos vectores no prueban

- No prueban que un cuerpo RPC real empiece por `1f 8b`.
- No prueban que `ZipHelper.Decompress` use `GZipStream`.
- No prueban que el `NetPack.Body` descomprimido sea JSON UTF-8.
- No prueban aceptación por Soul Knight.

Para elevar cualquiera de esas afirmaciones hace falta una muestra real con
procedencia y SHA-256, o una copia de memoria del código descifrado.
