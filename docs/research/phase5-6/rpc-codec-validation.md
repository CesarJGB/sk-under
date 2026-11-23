# Validación del códec RPC: gzip confirmado en el cliente 8.8.0

**Resultado:** el algoritmo de `ZipHelper.Decompress(byte[], int, int)` es
**gzip**. La confirmación ya no depende del nombre ni de una firma sintética:
se obtuvo el cuerpo de la función desde la memoria del proceso oficial en un
emulador propio y se identificó la secuencia `MemoryStream` → `GZipStream` →
`Read`. El marcador RPC `00 00 00 80` sigue siendo el discriminador que llama a
esa función. **No se obtuvo una respuesta RPC real** ni se ejercitó el servidor
con una cuenta; por eso el backend conserva el modo conservador por defecto.

## 1. Cadena confirmada

```text
respuesta byte[] → uint32 LE
  0x80000000 → ZipHelper.Decompress(bytes, 4, len-4) → NetPack
  0xFFFFFFFF → null
  otro       → NetPack(bytes)
```

| Paso | Evidencia | Estado |
| --- | --- | --- |
| `LoginApi._Decompress` lee un `uint32` LE al inicio | Desensamblado del cliente 8.8.0; Fase 5.5 | Confirmado |
| `0x80000000` selecciona la rama comprimida | Bytes `00 00 00 80`; comparación `mov w8, #-0x80000000` | Confirmado |
| La rama llama a `ZipHelper.Decompress(data, 4, len-4)` | `bl` al puntero del método global `ZipHelper.Decompress` | Confirmado |
| El resultado se envuelve en `NetPack` | Metadata de `NetPack`/`ByteBuffer` | Confirmado por tipo |
| `0xFFFFFFFF` devuelve nulo | Rama separada | Confirmado |
| El cuerpo comprimido es gzip | Cuerpo de `Decompress` en memoria | **Confirmado en esta fase** |

## 2. Cómo se obtuvo el cuerpo

El APK 8.8.0 protege la metadata y parte del código con ACE. La Fase 5.5 no
pudo leer el cuerpo de forma estática. En esta fase se usó una instalación
propia en un AVD Android 11 `userdebug` con `adb root`:

1. Se lanzó el cliente oficial y se localizó `libil2cpp.so` en
   `/proc/<pid>/maps`.
2. Se calculó la dirección runtime del puntero del método global
   `ZipHelper.Decompress` (`base + 0x04f02eac` en `armeabi-v7a`).
3. Se leyó un bloque de 4 KiB desde `/proc/<pid>/mem` y se guardó en el
   directorio privado del laboratorio.
4. Se desensambló el bloque con Capstone en modo ARM.

El bloque privado no se publica. La dirección y el método se verificaron contra
la tabla de punteros de métodos ya identificada en la Fase 5.5.

## 3. Evidencia dentro de `Decompress`

El cuerpo leído tiene un prólogo ARM válido y sigue el patrón de una
descompresión gestionada:

- construye un `MemoryStream` sobre `(data, offset, length)`;
- instancia un objeto cuyo constructor llama a `DeflateStream` con
  `(stream, mode, leaveOpen)`;
- el objeto nuevo se guarda en el campo del stream y se usa en un bucle de
  `Read(byte[], int, int)`;
- al terminar, libera los dos streams y devuelve el `byte[]` acumulado.

La llamada al constructor se resolvió como `GZipStream(Stream,
CompressionMode.Decompress, false)`: el segundo argumento es `0`
(`Decompress`) y el tercero es `false`. El constructor interno crea el
`DeflateStream` que implementa el miembro gzip. La clase hermana
`GZipDecompressString` y las cadenas `"gzip"`/`"Corrupted gzip header"` de la
metadata son evidencia concordante, pero la prueba principal es la secuencia de
construcción y lectura del cuerpo.

**Conclusión:** si el servidor envía el marcador comprimido, el cuerpo debe ser
un miembro gzip. No se declara que cualquier respuesta HTTP sea gzip: la
compresión HTTP es otra capa.

## 4. Lo que sigue sin confirmarse

| Pregunta | Estado |
| --- | --- |
| ¿El servidor usa realmente la rama comprimida para las partidas? | Desconocido; falta una respuesta real |
| ¿El `NetPack.Body` descomprimido es JSON UTF-8 directo? | Desconocido; ver [netpack-bytebuffer.md](netpack-bytebuffer.md) |
| ¿Hay una cabecera `NetPack` antes del JSON? | Identificada por tipos, no por bytes reales |
| ¿El cuerpo está además cifrado o firmado? | No observado; no se puede descartar |
| ¿La respuesta usa `Content-Encoding` además del sobre RPC? | No observado en una respuesta real |

## 5. Implementación y límites

`backend/app/cloud/decoder.py` mantiene:

- `decode_rpc_gzip(payload)`: exige el marcador `00 00 00 80`, la firma
  `1f 8b`, valida CRC/ISIZE, truncamiento y bytes posteriores, y limita la
  salida a 16 MiB.
- `decode_copy(..., rpc_body="reject")`: por defecto rechaza el cuerpo
  comprimido con `RpcBodyUnknown`. El valor `gzip_candidate` sigue siendo una
  activación explícita.
- `diagnose_gzip(payload)`: cabecera, `ISIZE`, bytes descomprimidos, bytes
  posteriores, CRC y error tipado.
- `diagnose_payload(payload)`: tamaño, SHA-256, marcador RPC, formato,
  diagnóstico gzip y código de error, sin devolver el contenido.

Límites: entrada total 8 MiB, JSON descomprimido 16 MiB, profundidad 64. Una
bomba de descompresión produce `size_limit`; un miembro truncado o con cola
produce `truncated`/`trailing_bytes`; un cuerpo sin firma gzip produce
`rpc_body_not_gzip`.

## 6. Pruebas

| Prueba | Resultado |
| --- | --- |
| Gzip válido: cabecera, CRC, tamaño y sin cola | Pasa |
| Gzip truncado, con cola, sin cabecera y bomba | Pasa; errores tipados |
| Sobre RPC con gzip y política opt-in | Pasa; conserva el sobre |
| Sobre RPC con cuerpo desconocido | Pasa; no adivina el códec |
| Diagnóstico de un cuerpo desconocido | Pasa; `rpc_body_not_gzip` |

Comando: `cd backend && uv run --locked pytest -q`. La suite completa se
reporta en [README.md](README.md).

## 7. Próximo paso para cerrar el RPC

Se necesita una de estas dos evidencias:

1. Una respuesta RPC real de una cuenta propia autorizada, con el cuerpo
   comprimido y el JSON/estructura que el cliente obtuvo; o
2. una lectura del `NetPack` ya construido en memoria, para comprobar su
   cabecera y el tipo de `Body`.

Sin una de ellas no se declara que el flujo remoto esté cerrado. La rama gzip
está confirmada; la interpretación completa de la respuesta no.
