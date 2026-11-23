# Protocolo de subida observado

## 1. Solicitud ejecutada

| Elemento | Valor observado |
| --- | --- |
| Método | `POST` |
| URL | `https://save.soulknight.chillyroom.com/BlobSave/Upload` |
| Autorización | `Authorization: Bearer <token de sesión de laboratorio>` |
| Identificadores | `x-unique-id`, `x-distro-id` de la instalación autorizada |
| Cabeceras de juego | `x-game-id: 1`, `x-game: Soulknight`, `x-app-version: 8.8.0`, `x-game-version: 8.8.0`, `x-platform: android`, `x-game-lang: en`, `x-locale: en_US` |
| Negociación | `Accept: application/json`, `Accept-Encoding: gzip` |
| Cuerpo | gzip de `{"data":"<agregado JSON como texto>"}` |
| Cabeceras del cuerpo | `Content-Type: application/json`, `Content-Encoding: gzip`, `Content-Length` |
| Token de solicitud | `x-request-token` **no se envió**; la escritura fue aceptada |
| Redirecciones | No se siguieron |
| TLS | Verificación normal de la plataforma, sin interceptación |

La forma del cuerpo ya estaba identificada en las fases 5.9 y 6.0 mediante análisis estático de `BlobSaveClient.UploadAsync`: `JsonConvert.SerializeObject` de `JsonPayload`, `Compress` con `GZipStream`, `ByteArrayContent`, `Content-Type: application/json` y `Content-Encoding: gzip`; `x-request-token` solo se añadía si un callback opcional devolvía un entero positivo. En la instancia observada ambos callbacks eran nulos, y esta ejecución confirma que el servicio acepta la solicitud sin esa cabecera.

## 2. Respuesta auténtica

La respuesta observada en las dos subidas fue idéntica:

| Elemento | Valor observado |
| --- | --- |
| Estado HTTP | `200 OK` |
| Servidor | `Kestrel` |
| `Content-Type` | `application/json; charset=utf-8` |
| `Content-Encoding` | `gzip` |
| Bytes en el cable | `30` |
| SHA-256 del cable | `0635550541b56bcf332a6f4077e3e58d51f4296e7b1e51868b7013943f00ac27` |
| Cuerpo descomprimido | `true` (4 bytes) |

No se observaron cabeceras de revisión, versión, `ETag`, `Last-Modified` ni un hash del contenido. La respuesta es un acuse booleano, no una prueba de persistencia ni una firma del agregado.

## 3. Aceptación frente a persistencia

**Demostrado por ejecución:**

1. `200` + `true` es la respuesta de una solicitud autenticada aceptada.
2. La persistencia se comprobó con una descarga posterior por el mismo canal.
3. La descarga devolvió el agregado byte a byte, incluido el cambio de un solo dígito.
4. El cliente oficial leyó, recuperó y aplicó la copia modificada.

**No demostrado:**

- Que `true` signifique más que «solicitud procesada».
- Que el servidor conserve una revisión histórica o permita volver a una anterior.
- Que el contrato sea universal para otras cuentas, regiones, versiones o canales.
- Que el servicio valide invariantes de progreso o anti-cheat.
- El comportamiento ante concurrencia, reintentos o caducidad de sesión.

La secuencia mínima de verificación es: subir, esperar la respuesta, volver a descargar y comparar tamaño y SHA-256. Un `200` aislado no basta.

## 4. Interpretación de errores

La implementación clasifica los fallos en capas separadas:

| Capa | Comportamiento |
| --- | --- |
| Credenciales | Token o identificadores vacíos o no visibles: `CloudProviderUnauthenticated` antes de abrir el socket |
| Construcción | Agregado inválido: `AggregateFormatError`; no se envía nada |
| Serialización y gzip | `prepare_upload_candidate` verifica que el sobre descomprimido conserva el agregado |
| Transporte | `OSError`, `HTTPException` o TLS: `CloudProviderUnavailable` sin propagar detalles privados |
| Autenticación remota | `401` o `403`: `CloudProviderUnauthenticated` |
| Respuesta del servidor | Otro estado: `CloudUploadRejected` con el estado real |
| Respuesta malformada | gzip corrupto, truncado o cuerpo que no es el booleano observado: `CloudProviderProtocolError` |
| Persistencia | Solo la descarga posterior puede confirmarla; el resultado incluye `matches_uploaded` |

No se interpreta un fallo del cliente oficial como rechazo del servidor ni un fallo local como imposibilidad del protocolo. En esta fase no hubo que reintentar: las dos solicitudes autenticadas fueron aceptadas.

## 5. Condiciones observadas para que el servidor persista

Con la evidencia disponible, la operación persistió cuando se cumplieron estas condiciones:

- sesión y dispositivo de la cuenta de laboratorio ya autenticados;
- `POST` al host de guardados y a la ruta `/BlobSave/Upload`;
- cuerpo gzip con `data` textual y `Content-Type: application/json`;
- cabeceras de juego/plataforma de la misma instalación;
- agregado estructuralmente válido;
- respuesta `200` con `true`.

No se aisló experimentalmente qué cabeceras son obligatorias. La ausencia de `x-request-token` no impidió la escritura en esta sesión.
