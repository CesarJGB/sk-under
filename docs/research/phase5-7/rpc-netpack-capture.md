# Captura RPC y NetPack

**Estado: SIN CAPTURA REAL.** No se obtuvo un `NetPack` de una operación de la
cuenta. Se confirmaron la superficie de rutas, las firmas de los métodos y el
contrato de error del gateway; el cuerpo y la cabecera siguen sin observarse.

## 1. Hipótesis

Si el cliente construye un `NetPack` para `DnloadSave` o `FetchGameData`, una
captura de la respuesta permitiría leer `MsgId`, `ReqIdx`, `BodySize`, `Body` y
el marcador `00 00 00 80`, y decidir si `Body` es JSON directo, una cadena con
longitud prefijada o un buffer con tags.

## 2. Procedimiento

1. Se descifró `global-metadata.dat` de 8.8.0 y se extrajeron sus literales y
   su tabla de cadenas.
2. Se localizaron los tipos y métodos de `LoginApi`, `CloudSaveGameData`,
   `BlobSaveClient` y `NetPack`.
3. Se resolvieron las firmas de los métodos con la tabla de parámetros.
4. Se probaron las rutas del gateway con peticiones de solo lectura para
   obtener el contrato de error.
5. No se instrumentó TLS ni se instaló una CA: el cliente no alcanza un login
   estable en el AVD y no se quiso alterar el pinning ni el cliente.

## 3. Evidencia estática

### 3.1 Rutas confirmadas en literales y metadata

```text
/UserAuth/Login                 /UserAuth/RegisterByEmail
/UserProfile/GetUserProfile     /UserProfile/Logout
/BlobSave/Download              /BlobSave/Upload
/Backup/GetBlobSave             /Backup/FetchGameData
/Migration/Saves                /GameWorld/Time
/AccessToken/Get                /AccessToken/Refresh
```

### 3.2 Firmas de `LoginApi`

Resueltas desde la metadata (nombres de parámetros incluidos):

| Método | Firma |
| --- | --- |
| `AccountLogin` | `(string account, string password, callback, exp)` |
| `PostAsync` | `(string url, object data)` |
| `CallRpc` | `(rid, func, callback, exp)` |
| `CallRpc` | `(client, rid, func, callback, exp)` |
| `DnloadSave` | `(onSuccess, onFail)` |
| `CheckSaveMac` | `(callback)` |
| `GetSaveTimeInfo` | `(callback)` |
| `_Decompress` | `(byte[])` |

`AccountLogin` no se ejecutó con la cuenta real. La firma demuestra que el
cliente envía cuenta, contraseña y un callback, pero **no** demuestra el
cuerpo JSON, las cabeceras ni el cifrado/firma de la petición.

### 3.3 Cabeceras que el cliente declara

Los literales incluyen:

```text
x-game-id  x-game  x-distro-id  x-distro-name
x-app-version  x-game-version  x-game-lang  x-locale
x-platform  x-channel  x-device-id
```

Se enviaron variantes de estas cabeceras en los probes del gateway. El error de
`/UserAuth/Login` siguió siendo `10000` con cuerpo nulo, así que las cabeceras
probadas no bastan para construir una petición válida.

### 3.4 Sobre RPC

La Fase 5.6 confirmó en runtime que `ZipHelper.Decompress` usa gzip
(`MemoryStream` + `GZipStream`/`DeflateStream` + `Read`). La Fase 5.4 confirmó
el discriminador:

| Prefijo | Rama |
| --- | --- |
| `00 00 00 80` | comprimida; `Decompress(body, 4, len-4)` |
| `FF FF FF FF` | marca nula |
| otro | cuerpo conservado |

Esto describe el **códec**, no una respuesta real. No se observó el marcador en
un mensaje de la cuenta.

## 4. Resultado

| Elemento | Estado |
| --- | --- |
| `NetPack` real | **No obtenido** |
| `MsgId` / `ReqIdx` / `BodySize` reales | **No observados** |
| Contenido de `Body` | **No observado** |
| Marcador `00 00 00 80` en una respuesta | **No observado** |
| gzip del bloque RPC | Confirmado en el método, **no en una respuesta** |
| Rutas y firmas | **Confirmadas estáticamente** |
| Contrato de error del gateway | **Confirmado** (`10001`, `10015`, `10000`) |

## 5. Limitaciones

- Sin un cliente estable no hay una sesión de juego desde la que capturar.
- Sin token de juego no se puede provocar una descarga desde Linux.
- No se capturó TLS; no se intentó eludir pinning ni controles del servicio.
- El cuerpo de `AccountLogin` y el esquema de éxito de la descarga siguen sin
  verificarse. Cualquier implementación debe etiquetarse como hipótesis.

## 6. Conclusión

La captura RPC **no se completó**. La evidencia nueva es la superficie exacta
de rutas y firmas, no un `NetPack`. El siguiente intento debe hacerse con un
cliente estable o con un token emitido por el mecanismo oficial; adivinar el
cuerpo de `AccountLogin` no es una base aceptable.
